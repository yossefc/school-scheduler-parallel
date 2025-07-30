"""
scheduler_ai/agent.py - Agent IA pour la gestion intelligente des emplois du temps
"""
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import asyncio

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Import du solver existant
from solver_engine import ScheduleSolver

logger = logging.getLogger(__name__)

Base = declarative_base()

class ConstraintPriority(Enum):
    """Niveaux de priorité des contraintes"""
    HARD = 0          # Incontournable
    VERY_STRONG = 1   # Quasi-incompressible
    MEDIUM = 2        # Améliore la qualité
    NORMAL = 3        # Standard
    LOW = 4           # Confort
    MINIMAL = 5       # Préférence mineure

class ConstraintHistory(Base):
    """Historique des contraintes appliquées"""
    __tablename__ = 'constraints_history'
    
    id = Column(Integer, primary_key=True)
    constraint_id = Column(Integer)
    constraint_data = Column(JSON)
    applied_at = Column(DateTime, default=datetime.now)
    applied_by = Column(String(100))
    success = Column(Boolean)
    impact_score = Column(Integer)
    rollback_data = Column(JSON)

class ScheduleAIAgent:
    """Agent IA principal pour la gestion des emplois du temps"""
    
    def __init__(self, db_config: Dict[str, str], llm_config: Optional[Dict] = None):
        self.db_config = db_config
        self.llm_config = llm_config or {}
        
        # Connexion DB
        self.engine = create_engine(
            f"postgresql://{db_config['user']}:{db_config['password']}@"
            f"{db_config['host']}/{db_config['database']}"
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Cache des contraintes
        self.constraints_cache = {}
        self.preferences_cache = {}
        
        # Solveur
        self.solver = ScheduleSolver()
        
        # Chargement des contraintes institutionnelles
        self._load_institutional_constraints()
    
    def _load_institutional_constraints(self):
        """Charge les contraintes institutionnelles depuis la BD"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("""
                SELECT * FROM v_active_institutional_constraints
                ORDER BY priority ASC
            """)
            
            self.institutional_constraints = []
            for row in cur.fetchall():
                constraint = {
                    "id": f"inst_{row['id']}",
                    "name": row['name'],
                    "type": row['type'],
                    "priority": row['priority'],
                    "data": row['data'],
                    "entities": row['entities']
                }
                self.institutional_constraints.append(constraint)
                
            logger.info(f"Loaded {len(self.institutional_constraints)} institutional constraints")
            
        finally:
            cur.close()
            conn.close()
    
    async def apply_constraint(self, constraint_json: Dict) -> Dict[str, Any]:
        """
        Applique une nouvelle contrainte et retourne l'impact
        
        Args:
            constraint_json: {
                "type": str,
                "entity": str,
                "data": dict,
                "priority": int
            }
            
        Returns:
            {
                "status": "success" | "conflict" | "error",
                "plan": [...],
                "solution_diff": {...},
                "score_delta": int,
                "conflicts": [...]
            }
        """
        try:
            # 1. Analyser la contrainte
            analysis = await self._analyze_constraint(constraint_json)
            
            if analysis["has_hard_conflicts"]:
                return {
                    "status": "conflict",
                    "conflicts": analysis["conflicts"],
                    "suggestions": self._generate_suggestions(analysis)
                }
            
            # 2. Créer le plan de modification
            plan = self._create_modification_plan(constraint_json, analysis)
            
            # 3. Simuler l'application
            simulation = await self._simulate_constraint_application(constraint_json)
            
            # 4. Si OK, appliquer réellement
            if simulation["feasible"]:
                result = await self._apply_constraint_to_solver(constraint_json)
                
                # Sauvegarder dans l'historique
                self._save_to_history(constraint_json, result)
                
                return {
                    "status": "success",
                    "plan": plan,
                    "solution_diff": result["diff"],
                    "score_delta": result["score_delta"]
                }
            else:
                return {
                    "status": "conflict",
                    "reason": simulation["reason"],
                    "suggestions": simulation["suggestions"]
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'application de contrainte: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def _analyze_constraint(self, constraint: Dict) -> Dict[str, Any]:
        """Analyse l'impact d'une contrainte"""
        conflicts = []
        soft_conflicts = []
        
        # Récupérer l'état actuel
        current_schedule = self._get_current_schedule()
        existing_constraints = self._get_existing_constraints()
        
        # Vérifier les conflits directs
        for existing in existing_constraints:
            conflict = self._check_constraint_conflict(constraint, existing)
            if conflict:
                if existing["priority"] == ConstraintPriority.HARD.value:
                    conflicts.append(conflict)
                else:
                    soft_conflicts.append(conflict)
        
        # Vérifier la faisabilité
        feasibility = self._check_feasibility(constraint, current_schedule)
        
        return {
            "has_hard_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "soft_conflicts": soft_conflicts,
            "feasibility": feasibility,
            "affected_entities": self._get_affected_entities(constraint)
        }
    
    def _create_modification_plan(self, constraint: Dict, analysis: Dict) -> List[Dict]:
        """Crée un plan détaillé de modification"""
        plan = []
        
        # 1. Ajouter la contrainte
        plan.append({
            "step": "action/add_constraint",
            "description": f"Ajouter contrainte {constraint['type']} pour {constraint['entity']}",
            "priority": constraint.get("priority", 3),
            "affected_entities": analysis["affected_entities"]
        })
        
        # 2. Résoudre les conflits soft si nécessaire
        for conflict in analysis["soft_conflicts"]:
            if conflict["severity"] > 0.5:  # Seuil de sévérité
                plan.append({
                    "step": "action/relax_constraint",
                    "description": f"Relaxer contrainte {conflict['constraint_id']}",
                    "priority_impact": f"-{conflict['priority_delta']}"
                })
        
        # 3. Re-solver
        plan.append({
            "step": "action/solve",
            "description": "Re-lancer le solveur CP-SAT avec les nouvelles contraintes",
            "estimated_time": "10-60s"
        })
        
        # 4. Rapport
        plan.append({
            "step": "action/report",
            "description": "Générer rapport de changements et delta qualité"
        })
        
        return plan
    
    async def _simulate_constraint_application(self, constraint: Dict) -> Dict[str, Any]:
        """Simule l'application d'une contrainte sans modifier l'état"""
        # Créer une copie temporaire du solver
        temp_solver = ScheduleSolver()
        temp_solver.load_data_from_db()
        
        # Ajouter la contrainte temporairement
        self._add_constraint_to_solver(temp_solver, constraint)
        
        # Tenter de résoudre avec timeout court
        result = temp_solver.solve(time_limit=10)
        
        if result:
            old_score = self._calculate_schedule_score(self._get_current_schedule())
            new_score = self._calculate_schedule_score(result)
            
            return {
                "feasible": True,
                "score_delta": new_score - old_score,
                "changes_count": self._count_changes(result)
            }
        else:
            return {
                "feasible": False,
                "reason": "Aucune solution trouvée avec cette contrainte",
                "suggestions": self._generate_relaxation_suggestions(constraint)
            }
    
    async def _apply_constraint_to_solver(self, constraint: Dict) -> Dict[str, Any]:
        """Applique réellement la contrainte au solver"""
        # Sauvegarder l'état actuel
        old_schedule = self._get_current_schedule()
        old_score = self._calculate_schedule_score(old_schedule)
        
        # Ajouter la contrainte à la DB
        constraint_id = self._save_constraint_to_db(constraint)
        
        # Re-solver
        self.solver.load_data_from_db()
        new_schedule = self.solver.solve(time_limit=60)
        
        if new_schedule:
            schedule_id = self.solver.save_schedule(new_schedule)
            new_score = self._calculate_schedule_score(new_schedule)
            
            # Calculer le diff
            diff = self._calculate_schedule_diff(old_schedule, new_schedule)
            
            return {
                "success": True,
                "constraint_id": constraint_id,
                "schedule_id": schedule_id,
                "diff": diff,
                "score_delta": new_score - old_score
            }
        else:
            # Rollback
            self._delete_constraint_from_db(constraint_id)
            raise Exception("Impossible de générer un emploi du temps avec cette contrainte")
    
    def explain_conflict(self, conflict_id: str) -> Dict[str, Any]:
        """Explique un conflit de manière pédagogique"""
        conflict = self._get_conflict_details(conflict_id)
        
        if not conflict:
            return {"error": "Conflit non trouvé"}
        
        explanation = {
            "conflict_id": conflict_id,
            "type": conflict["type"],
            "severity": conflict["severity"],
            "natural_language": self._generate_conflict_explanation(conflict),
            "entities_involved": conflict["entities"],
            "suggestions": self._generate_conflict_resolution_suggestions(conflict),
            "visual_representation": self._create_conflict_visualization(conflict)
        }
        
        return explanation
    
    def _generate_conflict_explanation(self, conflict: Dict) -> str:
        """Génère une explication en langage naturel"""
        templates = {
            "teacher_availability": "Le professeur {teacher} n'est pas disponible le {day} à {time}, "
                                   "mais un cours de {subject} est prévu pour la classe {class}.",
            "room_conflict": "La salle {room} est déjà occupée par {class1} pour {subject1} "
                            "au même créneau que {class2} pour {subject2}.",
            "consecutive_hours": "La classe {class} aurait {hours} heures consécutives de {subject}, "
                                "ce qui dépasse la limite de {limit} heures."
        }
        
        template = templates.get(conflict["type"], "Conflit détecté: {details}")
        return template.format(**conflict["params"])
    
    def _generate_suggestions(self, analysis: Dict) -> List[Dict[str, str]]:
        """Génère des suggestions pour résoudre les conflits"""
        suggestions = []
        
        for conflict in analysis["conflicts"]:
            if conflict["type"] == "teacher_availability":
                suggestions.extend([
                    {
                        "action": "change_teacher",
                        "description": f"Remplacer {conflict['teacher']} par un autre professeur disponible"
                    },
                    {
                        "action": "move_timeslot",
                        "description": f"Déplacer le cours à un créneau où {conflict['teacher']} est disponible"
                    }
                ])
            elif conflict["type"] == "room_conflict":
                suggestions.append({
                    "action": "change_room",
                    "description": f"Utiliser une autre salle que {conflict['room']}"
                })
        
        return suggestions
    
    def _calculate_schedule_score(self, schedule: List[Dict]) -> int:
        """Calcule le score de qualité d'un emploi du temps"""
        score = 100  # Score de base
        
        # Pénalités pour les trous
        gaps = self._count_teacher_gaps(schedule)
        score -= gaps * 5
        
        # Pénalités pour matières difficiles en fin de journée
        late_hard_subjects = self._count_late_hard_subjects(schedule)
        score -= late_hard_subjects * 3
        
        # Bonus pour bonne répartition
        distribution_score = self._calculate_distribution_score(schedule)
        score += distribution_score
        
        return max(0, score)
    
    def _save_to_history(self, constraint: Dict, result: Dict):
        """Sauvegarde dans l'historique"""
        session = self.SessionLocal()
        try:
            history_entry = ConstraintHistory(
                constraint_id=result.get("constraint_id"),
                constraint_data=constraint,
                applied_by="AI_Agent",
                success=result.get("success", False),
                impact_score=result.get("score_delta", 0),
                rollback_data={
                    "old_schedule_id": result.get("old_schedule_id"),
                    "can_rollback": True
                }
            )
            session.add(history_entry)
            session.commit()
        finally:
            session.close()
    
    # Méthodes helper privées...
    def _get_current_schedule(self) -> List[Dict]:
        """Récupère l'emploi du temps actuel"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM schedule_entries 
                WHERE schedule_id = (SELECT MAX(schedule_id) FROM schedules WHERE status = 'active')
            """)
            return cur.fetchall()
        finally:
            cur.close()
            conn.close()
    
    def _get_existing_constraints(self) -> List[Dict]:
        """Récupère toutes les contraintes existantes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SELECT * FROM constraints WHERE is_active = TRUE")
            return cur.fetchall()
        finally:
            cur.close()
            conn.close()
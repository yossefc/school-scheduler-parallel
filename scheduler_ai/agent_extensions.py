"""Extensions pour l'agent IA - méthodes helper"""
from typing import List, Dict, Any
import json

def extend_agent_methods(agent_class):
    """Ajoute les méthodes manquantes à la classe ScheduleAIAgent"""
    
    def _check_constraint_conflict(self, new_constraint: Dict, existing: Dict) -> Dict:
        """Vérifie les conflits entre contraintes"""
        if new_constraint["type"] == existing["constraint_type"]:
            if new_constraint["entity"] == existing["entity_name"]:
                return {
                    "type": "duplicate_constraint",
                    "message": f"Contrainte similaire déjà existante pour {new_constraint['entity']}",
                    "severity": 0.5,
                    "constraint_id": existing.get("constraint_id")
                }
        
        # Vérifier les conflits de disponibilité
        if (new_constraint["type"] == "teacher_availability" and 
            existing["constraint_type"] == "teacher_availability" and
            new_constraint["entity"] == existing["entity_name"]):
            
            new_days = set(new_constraint["data"].get("unavailable_days", []))
            existing_days = set(existing["constraint_data"].get("unavailable_days", []))
            
            if len(new_days | existing_days) >= 5:
                return {
                    "type": "availability_conflict",
                    "message": f"{new_constraint['entity']} n'aurait presque aucun jour disponible",
                    "severity": 0.9,
                    "constraint_id": existing.get("constraint_id")
                }
        
        return None
    
    def _check_feasibility(self, constraint: Dict, schedule: List[Dict]) -> Dict:
        """Vérifie la faisabilité d'une contrainte"""
        feasible = True
        reasons = []
        
        if constraint["type"] == "teacher_availability":
            teacher = constraint["entity"]
            unavailable_days = constraint["data"].get("unavailable_days", [])
            
            # Compter les heures requises pour ce prof
            teacher_lessons = [s for s in schedule if s.get("teacher_name") == teacher]
            days_needed = len(set(s["day_of_week"] for s in teacher_lessons))
            
            if days_needed > (5 - len(unavailable_days)):
                feasible = False
                reasons.append(f"{teacher} n'a pas assez de jours disponibles")
        
        return {
            "feasible": feasible,
            "reasons": reasons,
            "confidence": 0.8 if feasible else 0.2
        }
    
    def _get_affected_entities(self, constraint: Dict) -> List[str]:
        """Identifie les entités affectées par une contrainte"""
        entities = [constraint["entity"]]
        
        if constraint["type"] == "parallel_teaching":
            # Ajouter tous les professeurs du groupe
            if "groups" in constraint["data"]:
                entities.extend(constraint["data"]["groups"])
        
        return list(set(entities))
    
    def _add_constraint_to_solver(self, solver, constraint: Dict):
        """Ajoute une contrainte au solver"""
        # Cette méthode dépend de l'implémentation du solver
        # Pour l'instant, on la laisse vide
        pass
    
    def _generate_relaxation_suggestions(self, constraint: Dict) -> List[Dict]:
        """Génère des suggestions pour relaxer une contrainte"""
        suggestions = []
        
        if constraint["type"] == "teacher_availability":
            days = constraint["data"].get("unavailable_days", [])
            if len(days) > 2:
                suggestions.append({
                    "action": "reduce_unavailability",
                    "description": f"Réduire l'indisponibilité à {len(days)-1} jours"
                })
        
        elif constraint["type"] == "consecutive_hours_limit":
            max_hours = constraint["data"].get("max_consecutive", 2)
            suggestions.append({
                "action": "increase_limit",
                "description": f"Augmenter la limite à {max_hours + 1} heures consécutives"
            })
        
        return suggestions
    
    def _save_constraint_to_db(self, constraint: Dict) -> int:
        """Sauvegarde une contrainte dans la base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO constraints 
                (constraint_type, priority, entity_type, entity_name, constraint_data, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING constraint_id
            """, (
                constraint["type"],
                constraint.get("priority", 3),
                "teacher" if "teacher" in constraint["type"] else "general",
                constraint["entity"],
                json.dumps(constraint["data"]),
                True
            ))
            constraint_id = cur.fetchone()[0]
            conn.commit()
            return constraint_id
        finally:
            cur.close()
            conn.close()
    
    def _delete_constraint_from_db(self, constraint_id: int):
        """Supprime une contrainte de la base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM constraints WHERE constraint_id = %s", (constraint_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()
    
    def _calculate_schedule_diff(self, old_schedule: List[Dict], new_schedule: List[Dict]) -> Dict:
        """Calcule la différence entre deux emplois du temps"""
        old_set = {(s["teacher_name"], s["class_name"], s["day_of_week"], s["period_number"]) 
                   for s in old_schedule}
        new_set = {(s["teacher_name"], s["class_name"], s["day_of_week"], s["period_number"]) 
                   for s in new_schedule}
        
        added = new_set - old_set
        removed = old_set - new_set
        
        return {
            "added": len(added),
            "removed": len(removed),
            "changed": len(added) + len(removed),
            "details": {
                "added_slots": list(added)[:5],  # Max 5 exemples
                "removed_slots": list(removed)[:5]
            }
        }
    
    def _count_changes(self, new_schedule: List[Dict]) -> int:
        """Compte le nombre de changements dans un emploi du temps"""
        current = self._get_current_schedule()
        diff = self._calculate_schedule_diff(current, new_schedule)
        return diff["changed"]
    
    def _get_conflict_details(self, conflict_id: str) -> Dict:
        """Récupère les détails d'un conflit"""
        # Pour l'instant, on retourne un conflit d'exemple
        return {
            "id": conflict_id,
            "type": "teacher_availability",
            "severity": 0.8,
            "entities": ["Cohen", "9A"],
            "params": {
                "teacher": "Cohen",
                "day": "vendredi",
                "time": "14h",
                "subject": "Math",
                "class": "9A"
            }
        }
    
    def _generate_conflict_resolution_suggestions(self, conflict: Dict) -> List[Dict]:
        """Génère des suggestions pour résoudre un conflit"""
        suggestions = []
        
        if conflict["type"] == "teacher_availability":
            suggestions.extend([
                {
                    "action": "change_teacher",
                    "description": f"Remplacer {conflict['params']['teacher']} par un autre professeur",
                    "impact": "minimal"
                },
                {
                    "action": "change_time",
                    "description": f"Déplacer le cours à un autre créneau",
                    "impact": "moderate"
                }
            ])
        
        return suggestions
    
    def _create_conflict_visualization(self, conflict: Dict) -> Dict:
        """Crée une représentation visuelle du conflit"""
        return {
            "type": "timeline",
            "data": {
                "conflict_time": f"{conflict['params'].get('day', 'Unknown')} {conflict['params'].get('time', '')}",
                "entities": conflict["entities"],
                "severity_color": "#ff0000" if conflict["severity"] > 0.7 else "#ff9900"
            }
        }
    
    def _count_teacher_gaps(self, schedule: List[Dict]) -> int:
        """Compte les trous dans l'emploi du temps des professeurs"""
        gaps = 0
        teachers = set(s["teacher_name"] for s in schedule)
        
        for teacher in teachers:
            teacher_schedule = sorted(
                [s for s in schedule if s["teacher_name"] == teacher],
                key=lambda x: (x["day_of_week"], x["period_number"])
            )
            
            for day in range(6):
                day_schedule = [s for s in teacher_schedule if s["day_of_week"] == day]
                if len(day_schedule) > 1:
                    periods = sorted([s["period_number"] for s in day_schedule])
                    for i in range(1, len(periods)):
                        if periods[i] - periods[i-1] > 1:
                            gaps += periods[i] - periods[i-1] - 1
        
        return gaps
    
    def _count_late_hard_subjects(self, schedule: List[Dict]) -> int:
        """Compte les matières difficiles en fin de journée"""
        hard_subjects = ["math", "physique", "chimie", "מתמטיקה", "פיזיקה", "כימיה"]
        count = 0
        
        for entry in schedule:
            if (entry.get("period_number", 0) >= 8 and 
                any(subj in entry.get("subject_name", "").lower() for subj in hard_subjects)):
                count += 1
        
        return count
    
    def _calculate_distribution_score(self, schedule: List[Dict]) -> int:
        """Calcule un score de distribution équilibrée"""
        # Algorithme simple : bonus si les cours sont bien répartis
        score = 0
        
        # Vérifier la distribution par jour
        days_distribution = {}
        for entry in schedule:
            day = entry["day_of_week"]
            days_distribution[day] = days_distribution.get(day, 0) + 1
        
        if days_distribution:
            avg = sum(days_distribution.values()) / len(days_distribution)
            variance = sum((count - avg) ** 2 for count in days_distribution.values())
            
            # Plus la variance est faible, meilleur est le score
            if variance < 10:
                score += 10
            elif variance < 20:
                score += 5
        
        return score
    
    def generate_improvement_suggestions(self) -> List[Dict]:
        """Génère des suggestions d'amélioration pour l'emploi du temps actuel"""
        suggestions = []
        schedule = self._get_current_schedule()
        
        # Analyser les trous
        gaps = self._count_teacher_gaps(schedule)
        if gaps > 10:
            suggestions.append({
                "type": "reduce_gaps",
                "priority": "medium",
                "description": f"Réduire les {gaps} trous dans les emplois du temps des professeurs",
                "impact": f"Économie de {gaps * 45} minutes de temps perdu par semaine"
            })
        
        # Analyser les matières difficiles
        late_hard = self._count_late_hard_subjects(schedule)
        if late_hard > 5:
            suggestions.append({
                "type": "move_hard_subjects",
                "priority": "high",
                "description": f"Déplacer {late_hard} cours difficiles programmés en fin de journée",
                "impact": "Amélioration de l'attention et des résultats"
            })
        
        return suggestions
    
    def get_constraint_history(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Récupère l'historique des contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM constraints_history 
                ORDER BY applied_at DESC 
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return cur.fetchall()
        except:
            # Si la table n'existe pas encore
            return []
        finally:
            cur.close()
            conn.close()
    
    # Ajouter les méthodes à la classe
    agent_class._check_constraint_conflict = _check_constraint_conflict
    agent_class._check_feasibility = _check_feasibility
    agent_class._get_affected_entities = _get_affected_entities
    agent_class._add_constraint_to_solver = _add_constraint_to_solver
    agent_class._generate_relaxation_suggestions = _generate_relaxation_suggestions
    agent_class._save_constraint_to_db = _save_constraint_to_db
    agent_class._delete_constraint_from_db = _delete_constraint_from_db
    agent_class._calculate_schedule_diff = _calculate_schedule_diff
    agent_class._count_changes = _count_changes
    agent_class._get_conflict_details = _get_conflict_details
    agent_class._generate_conflict_resolution_suggestions = _generate_conflict_resolution_suggestions
    agent_class._create_conflict_visualization = _create_conflict_visualization
    agent_class._count_teacher_gaps = _count_teacher_gaps
    agent_class._count_late_hard_subjects = _count_late_hard_subjects
    agent_class._calculate_distribution_score = _calculate_distribution_score
    agent_class.generate_improvement_suggestions = generate_improvement_suggestions
    agent_class.get_constraint_history = get_constraint_history
    
    return agent_class

# Importer psycopg2 pour les méthodes DB
import psycopg2
from psycopg2.extras import RealDictCursor

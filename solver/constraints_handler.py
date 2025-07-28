# constraints_handler.py
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
import re
from typing import Dict, List, Any, Optional
from models import CONSTRAINT_TYPES, DAYS_MAPPING
import logging

logger = logging.getLogger(__name__)

class ConstraintsManager:
    def __init__(self):
        self.db_config = {
            "host": "postgres",
            "database": "school_scheduler",
            "user": "admin",
            "password": "school123"
        }
        
        # Patterns pour la reconnaissance du langage naturel
        self.nl_patterns = {
            "availability": [
                r"(.+) ne (?:peut pas|travaille pas) (?:le |les )?(.+)",
                r"(.+) (?:n'est pas|pas) disponible (?:le |les )?(.+)",
                r"(.+) (?:termine|finit) à (\d+h?\d*) (?:le |les )?(.+)",
                r"(.+) absent (?:le |les )?(.+)"
            ],
            "time_preference": [
                r"(?:les cours de |cours de )?(.+) (?:doivent être|uniquement) (?:le |en )?(.+)",
                r"(.+) (?:seulement|uniquement) (?:le |en )(.+)",
                r"placer (.+) (?:en |pendant )(.+)"
            ],
            "consecutive_limit": [
                r"(?:maximum|max) (\d+) heures? (?:consécutives|de suite)",
                r"pas plus de (\d+) heures? (?:d'affilée|consécutives)"
            ],
            "separation": [
                r"séparer (?:les )?(.+) (?:et|/) (?:les )?(.+) (?:pour|en) (.+)",
                r"(.+) séparés? pour (.+)"
            ]
        }
    
    def add_constraint(self, constraint_type: str, entity: str, data: Dict[str, Any], priority: int = 2) -> int:
        """Ajoute une contrainte dans la base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Valider le type de contrainte
            if constraint_type not in CONSTRAINT_TYPES:
                raise ValueError(f"Type de contrainte non supporté: {constraint_type}")
            
            # Déterminer le type d'entité
            entity_type = CONSTRAINT_TYPES[constraint_type]["entity_type"]
            
            # Insérer la contrainte
            cur.execute("""
                INSERT INTO constraints 
                (constraint_type, priority, entity_type, entity_name, constraint_data)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING constraint_id
            """, (constraint_type, priority, entity_type, entity, Json(data)))
            
            constraint_id = cur.fetchone()[0]
            conn.commit()
            
            logger.info(f"Constraint added: ID={constraint_id}, Type={constraint_type}, Entity={entity}")
            return constraint_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error adding constraint: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def parse_natural_constraint(self, text: str) -> Dict[str, Any]:
        """Convertit une contrainte en langage naturel en format structuré"""
        text = text.lower().strip()
        
        # Essayer de matcher avec les patterns de disponibilité
        for pattern in self.nl_patterns["availability"]:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                teacher = groups[0].strip()
                
                # Identifier le jour
                day_str = groups[-1] if len(groups) > 1 else ""
                day = self._parse_day(day_str)
                
                # Identifier l'heure si mentionnée
                time_match = re.search(r"(\d+)h?(\d*)", text)
                if time_match:
                    hour = int(time_match.group(1))
                    return {
                        "type": "teacher_availability",
                        "entity": teacher,
                        "data": {
                            "day": day,
                            "available_until": f"{hour}:00",
                            "reason": "Parsed from natural language"
                        }
                    }
                else:
                    return {
                        "type": "teacher_availability", 
                        "entity": teacher,
                        "data": {
                            "unavailable_days": [day] if day is not None else [],
                            "reason": "Parsed from natural language"
                        }
                    }
        
        # Essayer les préférences horaires
        for pattern in self.nl_patterns["time_preference"]:
            match = re.search(pattern, text)
            if match:
                subject = match.group(1).strip()
                time_pref = match.group(2).strip()
                
                periods = []
                if "matin" in time_pref:
                    periods = [1, 2, 3, 4]
                elif "après-midi" in time_pref:
                    periods = [5, 6, 7, 8]
                elif "dernière heure" in time_pref:
                    periods = [8, 9, 10]
                elif "première heure" in time_pref:
                    periods = [1]
                
                return {
                    "type": "subject_time_preference",
                    "entity": subject,
                    "data": {
                        "preferred_periods": periods,
                        "weight": 5
                    }
                }
        
        # Essayer les limites consécutives
        for pattern in self.nl_patterns["consecutive_limit"]:
            match = re.search(pattern, text)
            if match:
                max_hours = int(match.group(1))
                return {
                    "type": "consecutive_hours_limit",
                    "entity": "all_teachers",
                    "data": {
                        "max_consecutive": max_hours,
                        "applies_to": "all"
                    }
                }
        
        # Si aucun pattern ne match, retourner une contrainte générique
        return {
            "type": "custom",
            "entity": "unknown",
            "data": {
                "original_text": text,
                "parsed": False
            }
        }
    
    def _parse_day(self, day_str: str) -> Optional[int]:
        """Parse une chaîne de jour en numéro de jour"""
        day_str = day_str.lower().strip()
        
        # Vérifier dans le mapping
        for day_name, day_num in DAYS_MAPPING.items():
            if day_name in day_str:
                return day_num
        
        # Essayer de détecter des patterns spéciaux
        if "tous les jours" in day_str or "chaque jour" in day_str:
            return None  # Signifie tous les jours
        
        return None
    
    def validate_all_constraints(self) -> Dict[str, Any]:
        """Valide toutes les contraintes actives"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        errors = []
        warnings = []
        
        try:
            # Récupérer toutes les contraintes actives
            cur.execute("SELECT * FROM constraints WHERE is_active = TRUE")
            constraints = cur.fetchall()
            
            # Récupérer les données de référence
            cur.execute("SELECT DISTINCT teacher_name FROM teachers")
            teachers = [t['teacher_name'] for t in cur.fetchall()]
            
            cur.execute("SELECT DISTINCT subject FROM teacher_load")
            subjects = [s['subject'] for s in cur.fetchall() if s['subject']]
            
            # Valider chaque contrainte
            for constraint in constraints:
                validation = self._validate_single_constraint(constraint, teachers, subjects)
                errors.extend(validation['errors'])
                warnings.extend(validation['warnings'])
            
            # Vérifier les conflits entre contraintes
            conflicts = self._check_constraint_conflicts(constraints)
            errors.extend(conflicts)
            
            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "total_constraints": len(constraints),
                "suggestions": self._generate_suggestions(errors, warnings)
            }
            
        finally:
            cur.close()
            conn.close()
    
    def _validate_single_constraint(self, constraint: Dict, teachers: List[str], subjects: List[str]) -> Dict[str, List[str]]:
        """Valide une contrainte individuelle"""
        errors = []
        warnings = []
        
        # Vérifier que l'entité existe
        if constraint['entity_type'] == 'teacher' and constraint['entity_name'] not in teachers:
            errors.append(f"Professeur inconnu: {constraint['entity_name']}")
        elif constraint['entity_type'] == 'subject' and constraint['entity_name'] not in subjects:
            warnings.append(f"Matière non trouvée dans les charges: {constraint['entity_name']}")
        
        # Vérifier les champs requis
        if constraint['constraint_type'] in CONSTRAINT_TYPES:
            required_fields = CONSTRAINT_TYPES[constraint['constraint_type']].get('required_fields', [])
            for field in required_fields:
                if field not in constraint['constraint_data']:
                    errors.append(f"Champ manquant '{field}' pour contrainte {constraint['constraint_type']}")
        
        return {"errors": errors, "warnings": warnings}
    
    def _check_constraint_conflicts(self, constraints: List[Dict]) -> List[str]:
        """Vérifie les conflits entre contraintes"""
        conflicts = []
        
        # Grouper les contraintes par professeur
        teacher_constraints = {}
        for c in constraints:
            if c['entity_type'] == 'teacher':
                teacher_name = c['entity_name']
                if teacher_name not in teacher_constraints:
                    teacher_constraints[teacher_name] = []
                teacher_constraints[teacher_name].append(c)
        
        # Vérifier les conflits de disponibilité
        for teacher, teacher_cs in teacher_constraints.items():
            availability_cs = [c for c in teacher_cs if c['constraint_type'] == 'teacher_availability']
            
            if len(availability_cs) > 1:
                # Vérifier si les contraintes sont contradictoires
                unavailable_days = set()
                for c in availability_cs:
                    if 'unavailable_days' in c['constraint_data']:
                        unavailable_days.update(c['constraint_data']['unavailable_days'])
                
                if len(unavailable_days) >= 5:
                    conflicts.append(f"{teacher} n'a presque aucun jour disponible")
        
        return conflicts
    
    def _generate_suggestions(self, errors: List[str], warnings: List[str]) -> List[str]:
        """Génère des suggestions basées sur les erreurs et avertissements"""
        suggestions = []
        
        if any("Professeur inconnu" in e for e in errors):
            suggestions.append("Vérifiez l'orthographe des noms de professeurs ou ajoutez-les d'abord dans la table 'teachers'")
        
        if any("n'a presque aucun jour disponible" in e for e in errors):
            suggestions.append("Réduisez les contraintes de disponibilité ou recrutez des professeurs supplémentaires")
        
        if len(warnings) > 5:
            suggestions.append("Considérez simplifier vos contraintes pour faciliter la génération d'emploi du temps")
        
        return suggestions
    
    def get_constraint_statistics(self) -> Dict[str, Any]:
        """Retourne des statistiques sur les contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Compter par type
            cur.execute("""
                SELECT constraint_type, COUNT(*) as count
                FROM constraints
                WHERE is_active = TRUE
                GROUP BY constraint_type
            """)
            by_type = {row['constraint_type']: row['count'] for row in cur.fetchall()}
            
            # Compter par priorité
            cur.execute("""
                SELECT priority, COUNT(*) as count
                FROM constraints
                WHERE is_active = TRUE
                GROUP BY priority
            """)
            by_priority = {row['priority']: row['count'] for row in cur.fetchall()}
            
            # Total
            cur.execute("SELECT COUNT(*) as total FROM constraints WHERE is_active = TRUE")
            total = cur.fetchone()['total']
            
            return {
                "total": total,
                "by_type": by_type,
                "by_priority": by_priority
            }
            
        finally:
            cur.close()
            conn.close()
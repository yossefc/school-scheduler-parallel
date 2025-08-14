"""
smart_scheduler.py - Module intelligent de répartition et optimisation des cours
Gère la distribution optimale des heures avec priorité aux blocs de 2h
"""
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import time
import json

logger = logging.getLogger(__name__)

@dataclass
class CourseDistribution:
    """Représente la distribution d'un cours sur la semaine"""
    subject: str
    total_hours: int
    blocks: List[Dict]  # [{'day': str, 'duration': int, 'type': 'bloc'|'isolee'}]
    
class SmartScheduler:
    """Planificateur intelligent pour distribution optimale des cours"""
    
    def __init__(self):
        # Jours de la semaine israélienne
        self.days = {
            1: "dimanche",
            2: "lundi", 
            3: "mardi",
            4: "mercredi",
            5: "jeudi",
            6: "vendredi"
        }
        
        # Configuration des matières
        self.subject_config = {
            # Matières principales (préférence matin)
            "מתמטיקה": {"difficulty": "high", "prefer_morning": True, "max_consecutive": 2},
            "פיזיקה": {"difficulty": "high", "prefer_morning": True, "max_consecutive": 2},
            "כימיה": {"difficulty": "high", "prefer_morning": True, "max_consecutive": 2},
            "עברית": {"difficulty": "medium", "prefer_morning": True, "max_consecutive": 2},
            "אנגלית": {"difficulty": "medium", "prefer_morning": False, "max_consecutive": 2},
            
            # Matières religieuses (première heure obligatoire)
            "תורה": {"difficulty": "low", "prefer_morning": True, "fixed_slot": "first", "max_consecutive": 2},
            "תפילה": {"difficulty": "low", "prefer_morning": True, "fixed_slot": "first", "max_consecutive": 1},
            "גמרא": {"difficulty": "medium", "prefer_morning": True, "max_consecutive": 2},
            
            # Autres matières
            "היסטוריה": {"difficulty": "medium", "prefer_morning": False, "max_consecutive": 2},
            "גיאוגרפיה": {"difficulty": "low", "prefer_morning": False, "max_consecutive": 2},
            "ספורט": {"difficulty": "low", "prefer_morning": False, "max_consecutive": 2},
            "אומנות": {"difficulty": "low", "prefer_morning": False, "max_consecutive": 2}
        }
        
        # Créneaux optimaux par type de matière
        self.optimal_slots = {
            "high_difficulty": [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2)],
            "medium_difficulty": [(1, 3), (2, 3), (3, 3), (4, 3), (1, 4), (2, 4)],
            "low_difficulty": [(1, 5), (2, 5), (3, 5), (4, 5), (5, 0), (5, 1)]
        }
    
    def distribute_courses(self, class_name: str, subject: str, total_hours: int) -> CourseDistribution:
        """
        Répartit intelligemment les heures d'une matière sur la semaine
        
        Stratégie:
        - >= 4 heures : préférer des blocs de 2h
        - 3 heures : 1 bloc de 2h + 1h isolée
        - 2 heures : 1 bloc de 2h
        - 1 heure : 1h isolée
        """
        logger.info(f"Distribution de {total_hours}h de {subject} pour {class_name}")
        
        distribution = CourseDistribution(
            subject=subject,
            total_hours=total_hours,
            blocks=[]
        )
        
        # Récupérer la config de la matière
        subject_config = self.subject_config.get(subject, {
            "difficulty": "medium",
            "prefer_morning": False,
            "max_consecutive": 2
        })
        
        # Stratégie de distribution
        if total_hours >= 4:
            # Nombre pair d'heures : que des blocs de 2h
            if total_hours % 2 == 0:
                nb_blocks = total_hours // 2
                for i in range(nb_blocks):
                    distribution.blocks.append({
                        'duration': 2,
                        'type': 'bloc',
                        'day': None,  # À déterminer
                        'preferred_period': self._get_preferred_period(subject_config, i)
                    })
            else:
                # Nombre impair : maximiser les blocs de 2h
                nb_blocks = (total_hours - 1) // 2
                for i in range(nb_blocks):
                    distribution.blocks.append({
                        'duration': 2,
                        'type': 'bloc',
                        'day': None,
                        'preferred_period': self._get_preferred_period(subject_config, i)
                    })
                # Ajouter l'heure isolée
                distribution.blocks.append({
                    'duration': 1,
                    'type': 'isolee',
                    'day': None,
                    'preferred_period': self._get_preferred_period(subject_config, nb_blocks)
                })
        
        elif total_hours == 3:
            # 1 bloc de 2h + 1h isolée
            distribution.blocks.append({
                'duration': 2,
                'type': 'bloc',
                'day': None,
                'preferred_period': self._get_preferred_period(subject_config, 0)
            })
            distribution.blocks.append({
                'duration': 1,
                'type': 'isolee',
                'day': None,
                'preferred_period': self._get_preferred_period(subject_config, 1)
            })
        
        elif total_hours == 2:
            # 1 bloc de 2h
            distribution.blocks.append({
                'duration': 2,
                'type': 'bloc',
                'day': None,
                'preferred_period': self._get_preferred_period(subject_config, 0)
            })
        
        elif total_hours == 1:
            # 1h isolée
            distribution.blocks.append({
                'duration': 1,
                'type': 'isolee',
                'day': None,
                'preferred_period': self._get_preferred_period(subject_config, 0)
            })
        
        # Assigner les jours optimaux
        self._assign_optimal_days(distribution, subject_config)
        
        return distribution
    
    def _get_preferred_period(self, subject_config: Dict, block_index: int) -> str:
        """Détermine la période préférée pour un bloc"""
        if subject_config.get("fixed_slot") == "first":
            return "first"
        elif subject_config.get("prefer_morning", False):
            return "morning"
        else:
            return "any"
    
    def _assign_optimal_days(self, distribution: CourseDistribution, subject_config: Dict):
        """Assigne les jours optimaux pour chaque bloc"""
        nb_blocks = len(distribution.blocks)
        
        if nb_blocks == 0:
            return
        
        # Jours disponibles (dimanche à jeudi principalement)
        available_days = [1, 2, 3, 4, 5]
        
        # Pour les matières religieuses, inclure le vendredi matin
        if distribution.subject in ["תורה", "תפילה", "גמרא"]:
            available_days.append(6)
        
        # Éviter le vendredi pour les matières difficiles
        if subject_config.get("difficulty") == "high":
            available_days = [1, 2, 3, 4]
        
        # Calculer l'espacement optimal
        if nb_blocks == 1:
            # Un seul bloc : préférer lundi ou mardi
            distribution.blocks[0]['day'] = 2 if subject_config.get("difficulty") == "high" else 3
        
        elif nb_blocks == 2:
            # Deux blocs : espacer de 2 jours
            distribution.blocks[0]['day'] = 1  # Dimanche
            distribution.blocks[1]['day'] = 3  # Mardi ou mercredi
        
        elif nb_blocks == 3:
            # Trois blocs : répartir sur la semaine
            distribution.blocks[0]['day'] = 1  # Dimanche
            distribution.blocks[1]['day'] = 3  # Mardi
            distribution.blocks[2]['day'] = 5  # Jeudi
        
        else:
            # Plus de 3 blocs : répartir uniformément
            days_between = len(available_days) / nb_blocks
            for i, block in enumerate(distribution.blocks):
                day_index = int(i * days_between)
                block['day'] = available_days[min(day_index, len(available_days) - 1)]
    
    def analyze_weekly_balance(self, class_schedule: List[Dict]) -> Dict:
        """Analyse l'équilibre hebdomadaire d'un emploi du temps"""
        analysis = {
            "balance_score": 100,
            "issues": [],
            "gaps": [],
            "overloaded_days": []
        }
        
        # Regrouper par matière
        by_subject = {}
        for entry in class_schedule:
            subject = entry["subject"]
            day = entry["day"]
            
            if subject not in by_subject:
                by_subject[subject] = []
            by_subject[subject].append(day)
        
        # Analyser chaque matière
        for subject, days in by_subject.items():
            days_sorted = sorted(set(days))
            
            # Détecter les gaps (plus de 2 jours sans la matière)
            for i in range(len(days_sorted) - 1):
                gap = days_sorted[i+1] - days_sorted[i]
                if gap > 2:
                    analysis["gaps"].append({
                        "subject": subject,
                        "from_day": days_sorted[i],
                        "to_day": days_sorted[i+1],
                        "gap_days": gap - 1
                    })
                    analysis["balance_score"] -= 10
        
        # Analyser la charge par jour
        by_day = {}
        for entry in class_schedule:
            day = entry["day"]
            if day not in by_day:
                by_day[day] = 0
            by_day[day] += 1
        
        # Détecter les jours surchargés
        avg_load = sum(by_day.values()) / len(by_day) if by_day else 0
        for day, load in by_day.items():
            if load > avg_load * 1.5:
                analysis["overloaded_days"].append({
                    "day": day,
                    "load": load,
                    "avg_load": avg_load
                })
                analysis["balance_score"] -= 5
        
        return analysis
    
    def suggest_improvements(self, schedule: List[Dict], issues: List[Dict]) -> List[Dict]:
        """Suggère des améliorations pour un emploi du temps"""
        suggestions = []
        
        for issue in issues:
            if issue["type"] == "TROU":
                suggestions.append({
                    "type": "compact_schedule",
                    "priority": "high",
                    "description": f"Regrouper les cours de {issue['prof']} le {self.days[issue['day']]}",
                    "action": {
                        "move_courses": True,
                        "target_teacher": issue["prof"],
                        "target_day": issue["day"]
                    }
                })
            
            elif issue["type"] == "COURS_ISOLE":
                suggestions.append({
                    "type": "create_block",
                    "priority": "medium",
                    "description": f"Regrouper {issue['matiere']} en bloc de 2h pour {issue['classe']}",
                    "action": {
                        "merge_hours": True,
                        "target_class": issue["classe"],
                        "target_subject": issue["matiere"]
                    }
                })
            
            elif issue["type"] == "GAP_HEBDO":
                suggestions.append({
                    "type": "redistribute",
                    "priority": "low",
                    "description": f"Mieux répartir {issue['matiere']} sur la semaine",
                    "action": {
                        "redistribute": True,
                        "target_subject": issue["matiere"],
                        "max_gap": 2
                    }
                })
        
        return suggestions
    
    def get_optimal_day(self, class_name: str, subject: str, block_index: int) -> int:
        """Détermine le jour optimal pour placer un bloc de cours"""
        subject_config = self.subject_config.get(subject, {})
        
        # Matières difficiles : début de semaine
        if subject_config.get("difficulty") == "high":
            preferred_days = [1, 2, 3, 4]  # Dimanche à mercredi
            return preferred_days[block_index % len(preferred_days)]
        
        # Matières religieuses : peuvent inclure vendredi
        elif subject in ["תורה", "תפילה", "גמרא"]:
            preferred_days = [1, 2, 3, 4, 5, 6]
            return preferred_days[block_index % len(preferred_days)]
        
        # Autres matières : répartition équilibrée
        else:
            all_days = [1, 2, 3, 4, 5]
            return all_days[block_index % len(all_days)]
    
    def validate_distribution(self, distribution: CourseDistribution) -> Dict:
        """Valide une distribution de cours"""
        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Vérifier le total d'heures
        total_distributed = sum(block["duration"] for block in distribution.blocks)
        if total_distributed != distribution.total_hours:
            validation["is_valid"] = False
            validation["errors"].append(
                f"Heures distribuées ({total_distributed}) != heures totales ({distribution.total_hours})"
            )
        
        # Vérifier les blocs de 2h pour les matières importantes
        if distribution.subject in ["מתמטיקה", "פיזיקה", "עברית"]:
            blocks_2h = sum(1 for block in distribution.blocks if block["duration"] == 2)
            if blocks_2h < distribution.total_hours // 2:
                validation["warnings"].append(
                    f"{distribution.subject} devrait avoir plus de blocs de 2h"
                )
        
        # Vérifier l'espacement
        days = [block["day"] for block in distribution.blocks if block["day"]]
        if len(days) > 1:
            days_sorted = sorted(days)
            for i in range(len(days_sorted) - 1):
                if days_sorted[i+1] - days_sorted[i] > 3:
                    validation["warnings"].append(
                        f"Gap trop important entre les cours (jours {days_sorted[i]} et {days_sorted[i+1]})"
                    )
        
        return validation
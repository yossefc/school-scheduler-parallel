"""Parseur NLP amélioré pour toutes les contraintes"""
import re
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime
import logging
from models import ConstraintType, ConstraintPriority, ConstraintInput


logger = logging.getLogger(__name__)


class NaturalLanguageParser:
    """Parse les contraintes en langage naturel avec support complet"""
    
    def __init__(self):
        self.days_map = {
            # Français
            "lundi": 1, "mardi": 2, "mercredi": 3, 
            "jeudi": 4, "vendredi": 5, "dimanche": 0,
            # Hébreu romanisé
            "yom rishon": 0, "yom sheni": 1, "yom shlishi": 2,
            "yom revii": 3, "yom hamishi": 4, "yom shishi": 5,
            # Anglais
            "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "sunday": 0
        }
        
        self.subjects_map = {
            "math": ["math", "mathématiques", "maths"],
            "français": ["français", "francais", "french"],
            "hébreu": ["hébreu", "hebreu", "hebrew", "ivrit"],
            "anglais": ["anglais", "english"],
            "histoire": ["histoire", "history"],
            "sciences": ["sciences", "science", "physique", "chimie", "biologie"],
            "sport": ["sport", "eps", "éducation physique", "gym"]
        }
        
    def parse(self, text: str, language: str = "fr") -> ConstraintInput:
        """Parse une contrainte et retourne un ConstraintInput validé"""
        text = text.lower().strip()
        original_text = text
        
        # Détection du type avec regex améliorés
        constraint_data = None
        
        # 1. Contraintes de limite (votre cas)
        limit_patterns = [
            r"(?:pas plus de|maximum|max)\s+(\d+)\s+(?:à|a)?\s*(\d+)?\s*heure?s?\s+(?:de|d')\s*(\w+)",
            r"(?:limite|limiter)\s+(?:à|a)\s+(\d+)\s+heure?s?\s+(?:de|d')\s*(\w+)",
            r"(\d+)\s+heure?s?\s+(?:de|d')\s*(\w+)\s+(?:maximum|max)",
        ]
        
        for pattern in limit_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                max_hours = int(groups[0])
                subject = self._normalize_subject(groups[-1])
                
                # Détection si c'est consécutif ou par jour
                is_consecutive = any(word in text for word in 
                    ["consécutive", "consecutive", "suite", "d'affilée"])
                
                constraint_data = {
                    "type": ConstraintType.SUBJECT_LIMIT,
                    "entity": "all_classes",  # Par défaut
                    "data": {
                        "subject": subject,
                        "max_consecutive_hours" if is_consecutive else "max_hours_per_day": max_hours
                    },
                    "confidence": 0.85
                }
                break
        
        # 2. Disponibilité professeur
        if not constraint_data:
            availability_patterns = [
                r"(?:le\s+)?(?:professeur|prof\.?)\s+(\w+)\s+(?:ne\s+peut\s+pas|n'est\s+pas\s+disponible).*?(lundi|mardi|mercredi|jeudi|vendredi|dimanche)",
                r"(\w+)\s+(?:ne\s+peut\s+pas|unavailable|absent).*?(lundi|mardi|mercredi|jeudi|vendredi|dimanche)",
            ]
            
            for pattern in availability_patterns:
                match = re.search(pattern, text)
                if match:
                    teacher = match.group(1).capitalize()
                    day_str = match.group(2)
                    day_num = self.days_map.get(day_str, -1)
                    
                    if day_num >= 0:
                        constraint_data = {
                            "type": ConstraintType.TEACHER_AVAILABILITY,
                            "entity": teacher,
                            "data": {"unavailable_days": [day_num]},
                            "confidence": 0.9
                        }
                        break
        
        # 3. Préférences horaires
        if not constraint_data:
            time_patterns = [
                r"(?:les?\s+)?(?:cours?\s+de\s+)?(\w+)\s+(?:doivent\s+être|uniquement|seulement)\s+(?:le\s+)?(\w+)",
                r"(\w+)\s+(?:le\s+)?(\w+)\s+(?:uniquement|seulement)",
            ]
            
            for pattern in time_patterns:
                match = re.search(pattern, text)
                if match:
                    subject = self._normalize_subject(match.group(1))
                    time_pref = match.group(2)
                    
                    time_slots = self._parse_time_preference(time_pref)
                    if time_slots:
                        constraint_data = {
                            "type": ConstraintType.TIME_PREFERENCE,
                            "entity": subject,
                            "data": {"time_slots": time_slots},
                            "confidence": 0.75
                        }
                        break
        
        # 4. Si aucun pattern ne match, créer une contrainte custom
        if not constraint_data:
            constraint_data = {
                "type": ConstraintType.CUSTOM,
                "entity": "unknown",
                "data": {"text": original_text},
                "confidence": 0.3,
                "requires_clarification": True
            }
        
        # Créer et valider le ConstraintInput
        # Éviter le conflit de paramètres en préparant les données
        final_data = constraint_data.copy()
        final_data["original_text"] = original_text
        # confidence est déjà dans constraint_data, ne pas le redéfinir
        
        constraint = ConstraintInput(**final_data)
        
        return constraint
    
    def _normalize_subject(self, subject_str: str) -> str:
        """Normalise le nom de la matière"""
        subject_str = subject_str.lower().strip()
        
        for canonical, variants in self.subjects_map.items():
            if any(variant in subject_str for variant in variants):
                return canonical
                
        return subject_str
    
    def _parse_time_preference(self, time_str: str) -> Optional[List[str]]:
        """Parse une préférence temporelle"""
        time_str = time_str.lower()
        
        if "matin" in time_str:
            return ["morning"]  # periods 1-4
        elif "après-midi" in time_str or "apres-midi" in time_str:
            return ["afternoon"]  # periods 5-8
        elif "début" in time_str:
            return ["early"]  # periods 1-2
        elif "fin" in time_str:
            return ["late"]  # periods 7-8
            
        return None


def extract_constraint(msg: str, language: str = "fr") -> ConstraintInput:
    """Fonction principale d'extraction de contrainte"""
    parser = NaturalLanguageParser()
    return parser.parse(msg, language)
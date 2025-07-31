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
                subject = groups[-1]  # Le dernier groupe est toujours la matière
                hours = int(groups[0])
                return ConstraintInput(
                    type="hour_limit",
                    entity=subject,
                    data={
                        "max_hours": hours,
                        "period": "day"
                    },
                    priority=4,
                    metadata={"detected_by": "limit_pattern"},
                    original_text=original_text,
                    confidence=0.85
                )
        
        # 2. Contraintes de disponibilité professeur
        teacher_patterns = [
            r"(?:le professeur|prof|enseignant)\s+(\w+)\s+(?:ne peut pas|peut pas|pas disponible)",
            r"(\w+)\s+(?:prof|professeur)\s+(?:ne peut pas|peut pas|pas disponible)",
            r"(?:prof|professeur)\s+(?:de\s+)?(\w+)\s+(?:ne peut pas|peut pas|pas disponible)",
        ]
        
        for pattern in teacher_patterns:
            match = re.search(pattern, text)
            if match:
                teacher = match.group(1)
                # Détecter le jour si présent
                day = self._detect_day(text)
                day_num = self.days_map.get(day, None) if day else None
                
                return ConstraintInput(
                    type="teacher_availability",
                    entity=teacher,
                    data={
                        "available": False,
                        "day": day_num,
                        "day_name": day
                    },
                    priority=5,
                    metadata={"detected_by": "teacher_pattern"},
                    original_text=original_text,
                    confidence=0.9
                )
        
        # 3. Contraintes de salle
        room_patterns = [
            r"(?:salle|classe)\s+(\w+)\s+(?:pas disponible|occupée|réservée)",
            r"(?:pas de|sans)\s+(?:salle|classe)\s+(\w+)"
        ]
        
        for pattern in room_patterns:
            match = re.search(pattern, text)
            if match:
                room = match.group(1)
                return ConstraintInput(
                    type="room_constraint",
                    entity=room,
                    data={"available": False},
                    priority=4,
                    metadata={"detected_by": "room_pattern"},
                    original_text=original_text,
                    confidence=0.8
                )
        
        # Si aucune pattern reconnue, retourner une contrainte générique
        return ConstraintInput(
            type="custom",
            entity="unknown",
            data={"raw_text": text},
            priority=3,
            metadata={"detected_by": "fallback"},
            original_text=original_text,
            confidence=0.3,
            requires_clarification=True,
            clarification_questions=[
                "Quel est le type de contrainte que vous souhaitez ajouter ?",
                "À qui ou à quoi s'applique cette contrainte ?",
                "Quand cette contrainte doit-elle s'appliquer ?"
            ]
        )
    
    def _detect_day(self, text: str) -> Optional[str]:
        """Détecte le jour mentionné dans le texte"""
        for day_name, _ in self.days_map.items():
            if day_name in text:
                return day_name
        return None
    
    def _extract_time_constraints(self, text: str) -> Optional[List[str]]:
        """Extrait les contraintes temporelles"""
        time_patterns = [
            r"(?:le\s+)?matin",
            r"(?:l')?après-midi", 
            r"(?:en\s+)?début",
            r"(?:en\s+)?fin"
        ]
        
        found_times = []
        for pattern in time_patterns:
            if re.search(pattern, text):
                found_times.append(pattern.replace(r"(?:le\s+)?", "").replace(r"(?:l')?", "").replace(r"(?:en\s+)?", ""))
        
        if "matin" in text or "début" in text:
            return ["early"]  # periods 1-2
        elif "fin" in time_str:
            return ["late"]  # periods 7-8
            
        return None


def extract_constraint(msg: str, language: str = "fr") -> ConstraintInput:
    """Fonction principale d'extraction de contrainte avec LLM"""
    try:
        from llm_router import LLMRouter
        router = LLMRouter()
        
        # Parser avec LLM
        parsed_data = router.parse_natural_language(msg, language)
        constraint_data = parsed_data.get('constraint', {})
        
        return ConstraintInput(
            type=constraint_data.get('type', 'custom'),
            entity=constraint_data.get('entity', 'unknown'), 
            data=constraint_data.get('data', {'raw_text': msg}),
            priority=constraint_data.get('priority', 3),
            metadata=parsed_data.get('metadata', {}),
            original_text=msg,
            confidence=parsed_data.get('confidence', 0.5),
            requires_clarification=(parsed_data.get('confidence', 0.5) < 0.7)
        )
    except Exception as e:
        logger.error(f'Erreur LLM parser: {e}')
        # Fallback vers parser basique
        parser = NaturalLanguageParser()
        return parser.parse(msg, language)

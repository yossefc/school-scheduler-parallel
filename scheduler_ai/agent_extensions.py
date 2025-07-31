"""Extensions et middleware pour l'agent IA"""
from typing import Dict, Any, Optional, List, Tuple
import logging
from datetime import datetime
import asyncio
from models import ConstraintType

from models import ConstraintInput, ConstraintResponse
from parsers import extract_constraint

logger = logging.getLogger(__name__)


class ClarificationMiddleware:
    """Middleware pour gérer les clarifications de contraintes"""
    
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.clarification_history: Dict[str, List[Dict]] = {}
        
    async def process_constraint(
        self, 
        message: str, 
        session_id: str,
        context: Optional[Dict] = None
    ) -> ConstraintResponse:
        """Process une contrainte avec gestion des clarifications"""
        
        # Historique de la session
        if session_id not in self.clarification_history:
            self.clarification_history[session_id] = []
            
        history = self.clarification_history[session_id]
        
        try:
            # 1. Parser la contrainte
            constraint = extract_constraint(message)
            
            # 2. Vérifier si clarification nécessaire
            if constraint.requires_clarification:
                attempts = len([h for h in history 
                              if h.get("original_text") == constraint.original_text])
                
                if attempts >= self.max_attempts:
                    # Trop d'essais, abandonner
                    return ConstraintResponse(
                        status="error",
                        message="Impossible de comprendre la contrainte après plusieurs essais.",
                        suggestions=[
                            "Essayez une formulation plus simple",
                            "Exemple: 'Maximum 2 heures de math par jour'",
                            "Ou: 'Le professeur X ne peut pas le vendredi'"
                        ]
                    )
                
                # Enregistrer la tentative
                history.append({
                    "timestamp": datetime.now(),
                    "original_text": constraint.original_text,
                    "attempt": attempts + 1,
                    "questions": constraint.clarification_questions
                })
                
                # Retourner les questions de clarification
                return ConstraintResponse(
                    status="clarification_needed",
                    constraint=constraint,
                    message=self._format_clarification_message(constraint, attempts),
                    clarification_questions=constraint.clarification_questions,
                    confidence=constraint.confidence or 0.0
                )
            
            # 3. Contrainte valide, vérifier la confiance
            if constraint.confidence and constraint.confidence >= 0.8:
                # Application automatique
                return ConstraintResponse(
                    status="success",
                    constraint=constraint,
                    message=f"✅ Contrainte comprise et prête à être appliquée",
                    applied_automatically=True,
                    confidence=constraint.confidence
                )
            else:
                # Demander confirmation
                return ConstraintResponse(
                    status="clarification_needed",
                    constraint=constraint,
                    message="J'ai compris votre demande mais j'aimerais confirmer :",
                    clarification_questions=[
                        f"Vous souhaitez bien {self._describe_constraint(constraint)} ?"
                    ],
                    confidence=constraint.confidence or 0.5
                )
                
        except Exception as e:
            logger.error(f"Erreur middleware: {str(e)}")
            return ConstraintResponse(
                status="error",
                message="Une erreur s'est produite lors du traitement.",
                suggestions=["Veuillez réessayer avec une formulation différente"]
            )
    # hebrew_patch.py - Patch temporaire pour supporter l'hébreu natif

    def handle_hebrew_message(text: str, active_sessions: dict, session_id: str):
        """
        Gestion temporaire des messages en hébreu avec traductions pré-définies
        """
        
        # Dictionnaire de traductions communes
        hebrew_translations = {
            # Exemple de l'utilisateur
            "השיעור תפילה צריך להתחיל בכל הכיתו בשעה הראשונה": {
                "type": "scheduled_lesson",
                "subject": "תפילה",
                "period": 1,
                "applies_to": "all_classes",
                "description": "Cours de prière en première heure pour toutes les classes"
            },
            
            # Autres patterns courants
            "המורה כהן לא יכול ללמד ביום שישי": {
                "type": "teacher_availability", 
                "teacher": "כהן",
                "day": 5,  # Vendredi
                "available": False
            },
            
            "כיתה א צריכה הפסקה ארוכה": {
                "type": "class_requirement",
                "class": "א",
                "requirement": "break_extension"
            }
        }
        
        # Vérifier si le message correspond à un pattern connu
        if text in hebrew_translations:
            constraint_info = hebrew_translations[text]
            
            if constraint_info["type"] == "scheduled_lesson":
                return {
                    "status": "success",
                    "message": f"✅ הבנתי! שיעור {constraint_info['subject']} בשעה {constraint_info['period']} לכל הכיתות.\n\nהאם תרצה שאיישם את השינוי הזה?",
                    "constraint": {
                        "type": "parallel_teaching",
                        "data": {
                            "subject": constraint_info["subject"],
                            "period": constraint_info["period"],
                            "all_classes": True
                        },
                        "priority": 5
                    },
                    "requires_confirmation": True,
                    "confidence": 0.95,
                    "model_used": "hebrew_pattern_matcher"
                }
        
        # Patterns génériques pour mots-clés
        keywords = {
            "מורה": "teacher",
            "כיתה": "class", 
            "שיעור": "lesson",
            "תפילה": "prayer",
            "לא יכול": "cannot",
            "צריך": "need/must",
            "בשעה": "at hour",
            "ביום": "on day",
            "הראשונה": "first",
            "שישי": "friday"
        }
        
        detected_keywords = [hebrew for hebrew, english in keywords.items() if hebrew in text]
        
        if detected_keywords:
            return {
                "status": "clarification",
                "message": f"🔍 זיהיתי את המילים: {', '.join(detected_keywords)}\n\nאוכל לעזור אבל אני צריך הבהרה. האם תוכל לנסח את הבקשה באנגלית או בצרפתית?\n\nדוגמה: 'Prayer lesson should start at first period for all classes'",
                "detected_keywords": detected_keywords,
                "model_used": "hebrew_keyword_detector"
            }
        
        # Fallback
        return {
            "status": "error", 
            "message": "🤔 מצטער, אני עדיין לומד עברית. האם תוכל לנסח את הבקשה באנגלית או בצרפתית?\n\nSorry, I'm still learning Hebrew. Could you rephrase in English or French?",
            "model_used": "fallback"
        }
    def _format_clarification_message(
        self, 
        constraint: ConstraintInput, 
        attempts: int
    ) -> str:
        """Formate un message de clarification adapté"""
        
        if attempts == 0:
            prefix = "Je n'ai pas tout compris. "
        elif attempts == 1:
            prefix = "Désolé, j'ai encore besoin de précisions. "
        else:
            prefix = "Une dernière clarification svp. "
            
        if constraint.type == ConstraintType.SUBJECT_LIMIT:
            return prefix + "Pour clarifier votre limite d'heures :"
        elif constraint.type == ConstraintType.CUSTOM:
            return prefix + "Pouvez-vous reformuler votre demande ?"
        else:
            return prefix + "J'ai besoin de quelques précisions :"
    
    def _describe_constraint(self, constraint: ConstraintInput) -> str:
        """Décrit une contrainte en langage naturel"""
        
        if constraint.type == ConstraintType.SUBJECT_LIMIT:
            data = constraint.data
            if "max_hours_per_day" in data:
                return f"limiter à {data['max_hours_per_day']} heures de {data.get('subject', 'cette matière')} par jour"
            elif "max_consecutive_hours" in data:
                return f"limiter à {data['max_consecutive_hours']} heures consécutives de {data.get('subject', 'cette matière')}"
                
        elif constraint.type == ConstraintType.TEACHER_AVAILABILITY:
            days = constraint.data.get("unavailable_days", [])
            day_names = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi"]
            days_str = ", ".join(day_names[d] for d in days if 0 <= d < 6)
            return f"marquer {constraint.entity} comme indisponible le {days_str}"
            
        return "appliquer cette contrainte"
    
    def clear_history(self, session_id: str):
        """Efface l'historique d'une session"""
        if session_id in self.clarification_history:
            del self.clarification_history[session_id]


# Instance globale du middleware
clarification_middleware = ClarificationMiddleware()
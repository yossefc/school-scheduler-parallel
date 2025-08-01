"""Extensions et middleware pour l'agent IA avec apprentissage continu"""
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import asyncio
import json
import os
from collections import defaultdict

from models import ConstraintType, ConstraintInput, ConstraintResponse
from parsers import natural_language_parser

logger = logging.getLogger(__name__)


class ClarificationMiddleware:
    """Middleware pour gérer les clarifications avec apprentissage"""
    
    def __init__(self, max_attempts: int = 3, ttl_seconds: int = 300):
        self.max_attempts = max_attempts
        self.clarification_history: Dict[str, List[Dict]] = {}
        self.pending_constraints: Dict[str, ConstraintInput] = {}
        self.pending_timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        
        # Nouvelles fonctionnalités d'apprentissage
        self.success_patterns = defaultdict(int)
        self.clarification_patterns = defaultdict(list)
        self.user_preferences = self._load_user_preferences()
        
        # Statistiques pour l'amélioration
        self.stats = {
            "total_requests": 0,
            "successful_parses": 0,
            "clarifications_needed": 0,
            "auto_applied": 0,
            "user_corrections": 0
        }
        
        # Charger l'historique d'apprentissage
        self._load_learning_history()

    def _load_user_preferences(self) -> Dict:
        """Charge les préférences utilisateur apprises"""
        try:
            with open('knowledge/user_preferences.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "default": {
                    "language_preference": None,
                    "common_entities": [],
                    "typical_constraints": [],
                    "clarification_style": "detailed"
                }
            }
    
    def _load_learning_history(self):
        """Charge l'historique d'apprentissage"""
        try:
            with open('knowledge/clarification_history.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.success_patterns = defaultdict(int, data.get("success_patterns", {}))
                self.stats = data.get("stats", self.stats)
        except:
            pass

    async def process_constraint(
        self, 
        message: str, 
        session_id: str,
        context: Optional[Dict] = None
    ) -> ConstraintResponse:
        """Process une contrainte avec apprentissage intelligent"""
        
        # Statistiques
        self.stats["total_requests"] += 1
        
        # Historique de session
        if session_id not in self.clarification_history:
            self.clarification_history[session_id] = []
            
        history = self.clarification_history[session_id]
        
        # Purger les contraintes expirées
        self._cleanup_expired_sessions()
        
        # Détecter la langue de l'utilisateur et la mémoriser
        user_prefs = self.user_preferences.get(session_id, self.user_preferences["default"])
        detected_language = self._detect_user_language(message)
        
        if user_prefs["language_preference"] != detected_language:
            user_prefs["language_preference"] = detected_language
            self.user_preferences[session_id] = user_prefs

        # Si une contrainte est en attente, compléter avec le nouveau message
        if session_id in self.pending_constraints:
            partial = self.pending_constraints[session_id]
            filled = self._try_fill_missing_fields(partial, message, detected_language)
            
            if not filled.requires_clarification:
                # Succès ! Apprendre de ce pattern
                self._learn_from_success(partial.original_text, filled, len(history))
                
                del self.pending_constraints[session_id]
                
                # Appliquer la contrainte
                response = ConstraintResponse(
                    status="success",
                    constraint=filled,
                    message=self._format_success_message(filled, detected_language),
                    applied_automatically=filled.confidence >= 0.8,
                    confidence=filled.confidence
                )
                
                self.stats["successful_parses"] += 1
                if response.applied_automatically:
                    self.stats["auto_applied"] += 1
                    
                return response
            else:
                # Encore des questions, mais adaptées selon l'historique
                self.pending_constraints[session_id] = filled
                self.pending_timestamps[session_id] = datetime.utcnow()
                
                # Questions intelligentes basées sur l'apprentissage
                smart_questions = self._generate_smart_questions(filled, history, detected_language)
                
                return ConstraintResponse(
                    status="clarification_needed",
                    constraint=filled,
                    message=self._format_clarification_message(filled, len(history), detected_language),
                    clarification_questions=smart_questions
                )

        # Nouvelle contrainte - parser avec l'agent intelligent
        constraint = natural_language_parser.parse(message, detected_language)
        
        try:
            # Vérifier si clarification nécessaire
            if constraint.requires_clarification:
                self.stats["clarifications_needed"] += 1
                
                attempts = len([h for h in history 
                              if h.get("original_text") == constraint.original_text])
                
                if attempts >= self.max_attempts:
                    # Proposer des exemples basés sur les succès passés
                    return ConstraintResponse(
                        status="error",
                        message=self._get_timeout_message(detected_language),
                        suggestions=self._get_smart_suggestions(constraint.type, detected_language)
                    )
                
                # Enregistrer la tentative avec contexte enrichi
                history.append({
                    "timestamp": datetime.now(),
                    "original_text": constraint.original_text,
                    "attempt": attempts + 1,
                    "questions": constraint.clarification_questions,
                    "partial_data": constraint.data,
                    "detected_type": constraint.type
                })
                
                # Sauvegarder la contrainte partielle
                self.pending_constraints[session_id] = constraint
                self.pending_timestamps[session_id] = datetime.utcnow()
                
                # Questions adaptées selon le profil utilisateur
                questions = self._adapt_questions_to_user(
                    constraint.clarification_questions,
                    user_prefs,
                    detected_language
                )
                
                return ConstraintResponse(
                    status="clarification_needed",
                    constraint=constraint,
                    message=self._format_clarification_message(constraint, attempts, detected_language),
                    clarification_questions=questions,
                    confidence=constraint.confidence or 0.0
                )
            
            # Contrainte complète
            if constraint.confidence and constraint.confidence >= 0.8:
                # Application automatique avec apprentissage
                self._learn_from_success(message, constraint, 0)
                self.stats["successful_parses"] += 1
                self.stats["auto_applied"] += 1
                
                return ConstraintResponse(
                    status="success",
                    constraint=constraint,
                    message=self._format_success_message(constraint, detected_language),
                    applied_automatically=True,
                    confidence=constraint.confidence
                )
            else:
                # Demander confirmation avec suggestion intelligente
                confirmation_text = self._generate_smart_confirmation(constraint, detected_language)
                
                return ConstraintResponse(
                    status="clarification_needed",
                    constraint=constraint,
                    message=confirmation_text,
                    clarification_questions=[
                        self._get_confirmation_question(constraint, detected_language)
                    ],
                    confidence=constraint.confidence or 0.5
                )
                
        except Exception as e:
            logger.error(f"Erreur middleware: {str(e)}")
            return ConstraintResponse(
                status="error",
                message=self._get_error_message(detected_language),
                suggestions=self._get_smart_suggestions("general", detected_language)
            )
    
    def _detect_user_language(self, text: str) -> str:
        """Détecte la langue de l'utilisateur"""
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        return "he" if hebrew_chars > len(text) * 0.3 else "fr"
    
    def _learn_from_success(self, original_text: str, constraint: ConstraintInput, attempts: int):
        """Apprend d'un parsing réussi"""
        # Enregistrer le pattern de succès
        pattern_key = f"{constraint.type}:{constraint.entity}:{len(constraint.data)}"
        self.success_patterns[pattern_key] += 1
        
        # Si c'était après clarifications, apprendre la séquence
        if attempts > 0:
            self.clarification_patterns[constraint.type].append({
                "original": original_text,
                "final_data": constraint.data,
                "attempts": attempts,
                "timestamp": datetime.now().isoformat()
            })
        
        # Sauvegarder périodiquement
        if self.stats["total_requests"] % 10 == 0:
            self._save_learning_history()
    
    def _generate_smart_questions(
        self, 
        constraint: ConstraintInput, 
        history: List[Dict],
        language: str
    ) -> List[str]:
        """Génère des questions intelligentes basées sur l'historique"""
        
        # Regarder les clarifications similaires réussies
        similar_successes = []
        for pattern in self.clarification_patterns.get(constraint.type, []):
            if self._is_similar_context(pattern["original"], constraint.original_text):
                similar_successes.append(pattern)
        
        if similar_successes:
            # Utiliser les questions qui ont fonctionné avant
            successful_data_keys = set()
            for success in similar_successes:
                successful_data_keys.update(success["final_data"].keys())
            
            # Générer des questions pour les champs manquants
            questions = []
            missing_keys = successful_data_keys - set(constraint.data.keys())
            
            for key in missing_keys:
                question = self._generate_question_for_field(key, constraint.type, language)
                if question:
                    questions.append(question)
            
            return questions[:2]  # Max 2 questions à la fois
        
        # Fallback vers questions standards
        return constraint.clarification_questions
    
    def _adapt_questions_to_user(
        self,
        questions: List[str],
        user_prefs: Dict,
        language: str
    ) -> List[str]:
        """Adapte les questions selon les préférences utilisateur"""
        
        adapted = []
        
        for question in questions:
            # Style de clarification
            if user_prefs.get("clarification_style") == "brief":
                # Version courte
                if language == "he":
                    if "באילו ימים" in question:
                        adapted.append("אילו ימים?")
                    elif "באיזה שעות" in question:
                        adapted.append("מתי?")
                    else:
                        adapted.append(question[:30] + "?")
                else:
                    if "Quels jours" in question:
                        adapted.append("Quels jours ?")
                    elif "À quelle heure" in question:
                        adapted.append("Quand ?")
                    else:
                        adapted.append(question[:30] + " ?")
            else:
                # Version détaillée (défaut)
                adapted.append(question)
        
        return adapted
    
    def _generate_smart_confirmation(self, constraint: ConstraintInput, language: str) -> str:
        """Génère une confirmation intelligente"""
        # Vérifier si on a déjà vu ce type de contrainte
        pattern_key = f"{constraint.type}:{constraint.entity}"
        times_seen = self.success_patterns.get(pattern_key, 0)
        
        if times_seen > 5:
            # Pattern fréquent - confirmation courte
            if language == "he":
                return "אני מכיר את הדפוס הזה. לאשר?"
            else:
                return "Je connais ce schéma. Confirmer ?"
        else:
            # Nouvelle pattern - confirmation détaillée
            return self._describe_constraint(constraint, language)
    
    def _get_smart_suggestions(self, constraint_type: Any, language: str) -> List[str]:
        """Suggestions basées sur les succès passés"""
        suggestions = []
        
        # Top 3 des patterns réussis pour ce type
        relevant_patterns = [
            (pattern, count) 
            for pattern, count in self.success_patterns.items()
            if pattern.startswith(str(constraint_type))
        ]
        relevant_patterns.sort(key=lambda x: x[1], reverse=True)
        
        # Convertir en exemples
        for pattern, _ in relevant_patterns[:3]:
            example = self._pattern_to_example(pattern, language)
            if example:
                suggestions.append(example)
        
        # Ajouter des exemples standards si pas assez
        if len(suggestions) < 3:
            if language == "he":
                suggestions.extend([
                    "המורה כהן לא יכול ביום שישי",
                    "מקסימום 3 שעות מתמטיקה ביום",
                    "שיעור תפילה בשעה 8:00"
                ])
            else:
                suggestions.extend([
                    "Le professeur Cohen ne peut pas le vendredi",
                    "Maximum 3 heures de math par jour",
                    "Cours de prière à 8h00"
                ])
        
        return suggestions[:3]
    
    def _format_clarification_message(
        self, 
        constraint: ConstraintInput, 
        attempts: int,
        language: str
    ) -> str:
        """Message de clarification adaptatif"""
        
        if language == "he":
            prefixes = [
                "אני צריך עוד כמה פרטים:",
                "בבקשה עוד הבהרה:",
                "רק עוד שאלה אחת:"
            ]
        else:
            prefixes = [
                "J'ai besoin de quelques précisions :",
                "Encore une clarification svp :",
                "Une dernière question :"
            ]
        
        prefix = prefixes[min(attempts, 2)]
        
        # Ajouter contexte si on a des infos partielles
        if constraint.data:
            if language == "he":
                prefix += f" (הבנתי: {self._summarize_data_he(constraint.data)})"
            else:
                prefix += f" (J'ai compris : {self._summarize_data_fr(constraint.data)})"
        
        return prefix
    
    def _format_success_message(self, constraint: ConstraintInput, language: str) -> str:
        """Message de succès personnalisé"""
        confidence = constraint.confidence or 0.8
        
        if language == "he":
            if confidence > 0.95:
                return f"✅ מצוין! הבנתי perfectly: {self._describe_constraint_he(constraint)}"
            elif confidence > 0.8:
                return f"✅ הבנתי! {self._describe_constraint_he(constraint)}"
            else:
                return f"✓ אני חושב שהבנתי: {self._describe_constraint_he(constraint)}"
        else:
            if confidence > 0.95:
                return f"✅ Parfait ! J'ai compris : {self._describe_constraint_fr(constraint)}"
            elif confidence > 0.8:
                return f"✅ Compris ! {self._describe_constraint_fr(constraint)}"
            else:
                return f"✓ Je pense avoir compris : {self._describe_constraint_fr(constraint)}"
    
    def _save_learning_history(self):
        """Sauvegarde l'historique d'apprentissage"""
        try:
            os.makedirs('knowledge', exist_ok=True)
            
            data = {
                "success_patterns": dict(self.success_patterns),
                "stats": self.stats,
                "last_updated": datetime.now().isoformat()
            }
            
            with open('knowledge/clarification_history.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Sauvegarder les préférences utilisateur
            with open('knowledge/user_preferences.json', 'w', encoding='utf-8') as f:
                json.dump(self.user_preferences, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde apprentissage: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques d'utilisation"""
        success_rate = (
            self.stats["successful_parses"] / max(1, self.stats["total_requests"])
        ) * 100
        
        auto_apply_rate = (
            self.stats["auto_applied"] / max(1, self.stats["successful_parses"])
        ) * 100
        
        return {
            **self.stats,
            "success_rate": f"{success_rate:.1f}%",
            "auto_apply_rate": f"{auto_apply_rate:.1f}%",
            "total_patterns_learned": len(self.success_patterns),
            "active_sessions": len(self.clarification_history),
            "user_profiles": len(self.user_preferences)
        }
    
    # Méthodes helper existantes adaptées...
    
    def _try_fill_missing_fields(
        self, 
        partial: ConstraintInput, 
        user_msg: str,
        language: str
    ) -> ConstraintInput:
        """Complète intelligemment les champs manquants"""
        # Utiliser le parser pour extraire des infos du nouveau message
        new_info = natural_language_parser.parse(user_msg, language)
        
        # Fusionner intelligemment
        if new_info.data:
            for key, value in new_info.data.items():
                if key not in partial.data or partial.data[key] is None:
                    partial.data[key] = value
        
        # Recalculer si clarification nécessaire
        partial.requires_clarification = self._check_if_complete(partial)
        
        # Augmenter la confiance
        partial.confidence = min((partial.confidence or 0.5) + 0.2, 0.95)
        
        return partial
    
    def _check_if_complete(self, constraint: ConstraintInput) -> bool:
        """Vérifie si une contrainte est complète"""
        required_fields = {
            ConstraintType.TEACHER_AVAILABILITY: ["days"],
            ConstraintType.TIME_PREFERENCE: ["start"],  # ← Juste "start" suffit !
            ConstraintType.SUBJECT_LIMIT: ["max_hours_per_day", "subject"],
            ConstraintType.CONSECUTIVE_HOURS_LIMIT: ["max_consecutive"]
        }
        
        # Pour morning_prayer / prayer
        if constraint.type == ConstraintType.TIME_PREFERENCE and constraint.data.get("subject") == "prayer":
            # Si on a start, c'est suffisant !
            return "start" in constraint.data
        
        required = required_fields.get(constraint.type, [])
        has_all = all(field in constraint.data for field in required)
        
        # Ne PAS demander de clarification si on a les champs requis
        return not has_all  # ← Inversé ! True = besoin clarification
    
    def _cleanup_expired_sessions(self):
        """Nettoie les sessions expirées"""
        now = datetime.utcnow()
        expired = []
        
        for sid, timestamp in list(self.pending_timestamps.items()):
            if now - timestamp > self.ttl:
                expired.append(sid)
        
        for sid in expired:
            self.pending_timestamps.pop(sid, None)
            self.pending_constraints.pop(sid, None)
            self.clarification_history.pop(sid, None)
    
    # Méthodes helper pour les messages multilingues
    
    def _describe_constraint_he(self, constraint: ConstraintInput) -> str:
        """Description en hébreu"""
        descriptions = {
            ConstraintType.TEACHER_AVAILABILITY: f"{constraint.entity} לא זמין",
            ConstraintType.TIME_PREFERENCE: f"העדפת זמן עבור {constraint.data.get('subject', 'השיעור')}",
            ConstraintType.SUBJECT_LIMIT: f"הגבלת שעות ל{constraint.data.get('subject', 'מקצוע')}",
            ConstraintType.CONSECUTIVE_HOURS_LIMIT: "הגבלת שעות רצופות"
        }
        return descriptions.get(constraint.type, "אילוץ מותאם אישית")
    
    def _describe_constraint_fr(self, constraint: ConstraintInput) -> str:
        """Description en français"""
        descriptions = {
            ConstraintType.TEACHER_AVAILABILITY: f"{constraint.entity} non disponible",
            ConstraintType.TIME_PREFERENCE: f"Préférence horaire pour {constraint.data.get('subject', 'le cours')}",
            ConstraintType.SUBJECT_LIMIT: f"Limite d'heures pour {constraint.data.get('subject', 'la matière')}",
            ConstraintType.CONSECUTIVE_HOURS_LIMIT: "Limite d'heures consécutives"
        }
        return descriptions.get(constraint.type, "Contrainte personnalisée")
    
    def _get_timeout_message(self, language: str) -> str:
        if language == "he":
            return "מצטער, לא הצלחתי להבין. הנה כמה דוגמאות שעובדות טוב:"
        else:
            return "Désolé, je n'ai pas réussi à comprendre. Voici des exemples qui fonctionnent bien :"
    
    def _get_error_message(self, language: str) -> str:
        if language == "he":
            return "אירעה שגיאה. אנא נסה שוב או השתמש בדוגמאות:"
        else:
            return "Une erreur s'est produite. Veuillez réessayer ou utiliser les exemples :"
    
    def clear_history(self, session_id: str):
        """Efface l'historique d'une session"""
        if session_id in self.clarification_history:
            del self.clarification_history[session_id]
        if session_id in self.pending_constraints:
            del self.pending_constraints[session_id]
        if session_id in self.pending_timestamps:
            del self.pending_timestamps[session_id]
    
    def _is_similar_context(self, text1: str, text2: str) -> bool:
        """Vérifie si deux textes ont un contexte similaire"""
        # Version simple - à améliorer avec embeddings
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) > 0.6
    
    def _generate_question_for_field(self, field: str, constraint_type: Any, language: str) -> Optional[str]:
        """Génère une question pour un champ manquant"""
        questions = {
            "he": {
                "days": "באילו ימים?",
                "subject": "איזה מקצוע?",
                "max_hours_per_day": "כמה שעות מקסימום ביום?",
                "max_consecutive": "כמה שעות רצופות מקסימום?",
                "preferred_periods": "באיזה חלק של היום?"
            },
            "fr": {
                "days": "Quels jours ?",
                "subject": "Quelle matière ?",
                "max_hours_per_day": "Combien d'heures maximum par jour ?",
                "max_consecutive": "Combien d'heures consécutives maximum ?",
                "preferred_periods": "À quel moment de la journée ?"
            }
        }
        
        lang_questions = questions.get(language, questions["fr"])
        return lang_questions.get(field)
    
    def _pattern_to_example(self, pattern: str, language: str) -> Optional[str]:
        """Convertit un pattern en exemple utilisable"""
        # Pattern format: "type:entity:data_count"
        parts = pattern.split(":")
        if len(parts) < 2:
            return None
            
        constraint_type = parts[0]
        entity = parts[1]
        
        if language == "he":
            examples = {
                "teacher_availability": f"המורה {entity} לא יכול ללמד ביום חמישי",
                "time_preference": f"שיעורי {entity} רק בבוקר",
                "subject_limit": f"לא יותר מ-3 שעות {entity} ביום"
            }
        else:
            examples = {
                "teacher_availability": f"Le professeur {entity} ne peut pas le jeudi",
                "time_preference": f"Cours de {entity} uniquement le matin",
                "subject_limit": f"Pas plus de 3 heures de {entity} par jour"
            }
            
        return examples.get(constraint_type)
    
    def _summarize_data_he(self, data: Dict) -> str:
        """Résume les données en hébreu"""
        parts = []
        if "subject" in data:
            parts.append(f"מקצוע: {data['subject']}")
        if "days" in data:
            parts.append(f"ימים: {data['days']}")
        if "max_hours_per_day" in data:
            parts.append(f"מקס׳ {data['max_hours_per_day']} שעות")
        return ", ".join(parts) if parts else "חלק מהמידע"
    
    def _summarize_data_fr(self, data: Dict) -> str:
        """Résume les données en français"""
        parts = []
        if "subject" in data:
            parts.append(f"matière : {data['subject']}")
        if "days" in data:
            parts.append(f"jours : {data['days']}")
        if "max_hours_per_day" in data:
            parts.append(f"max {data['max_hours_per_day']}h")
        return ", ".join(parts) if parts else "données partielles"
    
    def _get_confirmation_question(self, constraint: ConstraintInput, language: str) -> str:
        """Question de confirmation dans la bonne langue"""
        if language == "he":
            return f"האם אתה מאשר: {self._describe_constraint_he(constraint)}?"
        else:
            return f"Confirmez-vous : {self._describe_constraint_fr(constraint)} ?"
    
    def _describe_constraint(self, constraint: ConstraintInput, language: str) -> str:
        """Décrit une contrainte en langage naturel"""
        if language == "he":
            return self._describe_constraint_he(constraint)
        else:
            return self._describe_constraint_fr(constraint)


# Instance globale du middleware
clarification_middleware = ClarificationMiddleware()
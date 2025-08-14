# schedule_advisor_agent.py - Agent AI conseiller pour l'optimisation d'emploi du temps
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass, asdict
from enum import Enum
from hebrew_language_processor import HebrewLanguageProcessor, analyze_hebrew_input
from advanced_scheduling_algorithms import AdvancedSchedulingEngine, OptimizationObjective
from ai_training_system import AITrainingSystem, ProblemPattern

logger = logging.getLogger(__name__)

class ChangeType(Enum):
    MOVE_COURSE = "move_course"
    SWAP_COURSES = "swap_courses" 
    ADD_COURSE = "add_course"
    REMOVE_COURSE = "remove_course"
    ADJUST_HOURS = "adjust_hours"
    MERGE_SESSIONS = "merge_sessions"
    SPLIT_SESSIONS = "split_sessions"

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class UserRequest:
    """Représente une demande utilisateur"""
    request_id: str
    user_input: str
    timestamp: datetime
    priority: Priority
    context: Dict[str, Any]
    status: str = "pending"  # pending, analyzing, proposed, confirmed, rejected

@dataclass
class ScheduleChange:
    """Représente une modification proposée"""
    change_id: str
    change_type: ChangeType
    description: str
    affected_classes: List[str]
    affected_teachers: List[str]
    current_state: Dict[str, Any]
    proposed_state: Dict[str, Any]
    impact_analysis: Dict[str, Any]
    confidence_score: float
    reasoning: str

@dataclass
class UserPreference:
    """Préférence/revendication utilisateur"""
    preference_id: str
    category: str  # "teacher_availability", "class_preference", "time_constraint", etc.
    entity: str    # nom du prof, classe, matière
    rule: str      # description de la règle
    priority: Priority
    active: bool
    created_at: datetime
    examples: List[str]

class ScheduleAdvisorAgent:
    """Agent AI intelligent pour conseiller sur les modifications d'emploi du temps"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.user_requests: Dict[str, UserRequest] = {}
        self.user_preferences: Dict[str, UserPreference] = {}
        self.pending_changes: Dict[str, ScheduleChange] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Processeur de langue hébraïque
        self.hebrew_processor = HebrewLanguageProcessor()
        
        # Moteur d'optimisation avancé
        self.optimization_engine = None  # Sera initialisé avec les données d'emploi du temps
        
        # Système d'entraînement AI
        self.training_system = AITrainingSystem(db_config)
        self.training_system.load_training_results()  # Charger l'apprentissage précédent
        
        # Charger les préférences existantes
        self._load_user_preferences()
        
    def _load_user_preferences(self):
        """Charge les préférences utilisateur depuis la DB"""
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Créer la table si elle n'existe pas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    preference_id VARCHAR(50) PRIMARY KEY,
                    category VARCHAR(100),
                    entity VARCHAR(200),
                    rule TEXT,
                    priority VARCHAR(20),
                    active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT NOW(),
                    examples JSONB
                )
            """)
            
            cur.execute("SELECT * FROM user_preferences WHERE active = true")
            preferences = cur.fetchall()
            
            for pref in preferences:
                self.user_preferences[pref['preference_id']] = UserPreference(
                    preference_id=pref['preference_id'],
                    category=pref['category'],
                    entity=pref['entity'],
                    rule=pref['rule'],
                    priority=Priority(pref['priority']),
                    active=pref['active'],
                    created_at=pref['created_at'],
                    examples=pref['examples'] or []
                )
                
            conn.commit()
            logger.info(f"✓ {len(self.user_preferences)} préférences utilisateur chargées")
            
        except Exception as e:
            logger.error(f"Erreur chargement préférences: {e}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def process_user_request(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Point d'entrée principal pour traiter une demande utilisateur"""
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # DÉTECTION AUTOMATIQUE DE LA LANGUE
        is_hebrew = self._is_hebrew_text(user_input)
        detected_language = "hebrew" if is_hebrew else "french"
        
        logger.info(f"Demande reçue en {detected_language}: {user_input}")
        
        # Créer la demande
        request = UserRequest(
            request_id=request_id,
            user_input=user_input,
            timestamp=datetime.now(),
            priority=self._analyze_priority(user_input),
            context={**(context or {}), "language": detected_language},
            status="analyzing"
        )
        
        self.user_requests[request_id] = request
        self._add_to_conversation("user", user_input)
        
        try:
            # Analyser la demande selon la langue
            if is_hebrew:
                analysis = self._analyze_hebrew_request(request)
            else:
                analysis = self._analyze_request(request)
            
            # Extraire les nouvelles préférences si présentes
            new_preferences = self._extract_preferences(user_input, detected_language)
            for pref in new_preferences:
                self._save_user_preference(pref)
            
            # Générer des propositions de changement
            proposed_changes = self._generate_change_proposals(request, analysis)
            
            # Créer la réponse
            response = self._create_advisor_response(request, analysis, proposed_changes, new_preferences)
            
            request.status = "proposed"
            self._add_to_conversation("assistant", response["message"])
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur traitement demande {request_id}: {e}")
            
            # Message d'erreur adapté à la langue
            if context and context.get("language") == "hebrew":
                error_msg = f"סליחה, נתקלתי בשגיאה בניתוח הבקשה שלך: {str(e)}"
            else:
                error_msg = f"Désolé, j'ai rencontré une erreur en analysant votre demande: {str(e)}"
                
            error_response = {
                "request_id": request_id,
                "message": error_msg,
                "success": False,
                "error": str(e),
                "language": context.get("language", "french") if context else "french"
            }
            self._add_to_conversation("assistant", error_response["message"])
            return error_response

    def _is_hebrew_text(self, text: str) -> bool:
        """Détecte si le texte est principalement en hébreu"""
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars == 0:
            return False
            
        hebrew_ratio = hebrew_chars / total_chars
        return hebrew_ratio > 0.3  # Si plus de 30% de caractères hébreux

    def _analyze_hebrew_request(self, request: UserRequest) -> Dict[str, Any]:
        """Analyse spécialisée pour les demandes en hébreu"""
        hebrew_analysis = self.hebrew_processor.analyze_hebrew_text(request.user_input)
        
        logger.info(f"Analyse hébreu terminée - Intent: {hebrew_analysis['main_intent']}, Confiance: {hebrew_analysis['confidence_score']:.2f}")
        
        return {
            "detected_actions": hebrew_analysis["actions"],
            "entities": hebrew_analysis["entities"], 
            "user_intent": hebrew_analysis["main_intent"],
            "complexity": self._assess_complexity_hebrew(hebrew_analysis),
            "applicable_preferences": self._find_applicable_preferences(hebrew_analysis["entities"]),
            "hebrew_context": hebrew_analysis["translated_context"],
            "confidence": hebrew_analysis["confidence_score"],
            "urgency": hebrew_analysis["urgency_level"],
            "language": "hebrew"
        }

    def _analyze_priority(self, user_input: str) -> Priority:
        """Analyse la priorité de la demande basée sur des mots-clés (multilingue)"""
        # Mots français
        high_priority_words = ["urgent", "critique", "problème", "conflit", "impossible", "erreur"]
        medium_priority_words = ["préféré", "mieux", "améliorer", "optimiser", "ajuster"]
        
        # Mots hébreux
        high_priority_hebrew = ["דחוף", "מיידי", "בעיה", "קונפליקט", "חשוב", "עכשיו"]
        medium_priority_hebrew = ["עדיף", "כדאי", "לשפר", "לייעל", "לתקן"]
        
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in high_priority_words + high_priority_hebrew):
            return Priority.HIGH
        elif any(word in user_lower for word in medium_priority_words + medium_priority_hebrew):
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def _assess_complexity_hebrew(self, hebrew_analysis: Dict) -> str:
        """Évalue la complexité d'une demande en hébreu"""
        actions_count = len(hebrew_analysis["actions"])
        entities_count = sum(len(v) for v in hebrew_analysis["entities"].values() if isinstance(v, list))
        
        if actions_count > 2 or entities_count > 5:
            return "high"
        elif actions_count > 1 or entities_count > 2:
            return "medium"
        else:
            return "low"

    def _analyze_request(self, request: UserRequest) -> Dict[str, Any]:
        """Analyse intelligente de la demande utilisateur"""
        user_input = request.user_input.lower()
        
        # Détecter le type d'action demandée
        action_patterns = {
            "move": ["déplacer", "bouger", "changer l'heure", "move", "décaler", "להזיז", "לזוז", "לנקל"],
            "swap": ["échanger", "swap", "permuter", "inverser", "להחליף", "להקיפ"],
            "add": ["ajouter", "add", "insérer", "créer", "להוסיףק", "לצור"],
            "remove": ["supprimer", "remove", "enlever", "delete", "למחוק", "להסיר"],
            "optimize": ["optimiser", "améliorer", "reorganiser", "mieux", "לשפר", "לקטן"],
            "fix_gaps": ["trous", "gaps", "vide", "pause", "trou", "חור", "חורים", "פער", "פערים", "רווח", "הפסקה", "למלא", "לסגור", "יש חור"],
            "balance": ["équilibrer", "répartir", "balance", "répartition", "לאזן", "לחלק"]
        }
        
        # Détecter les entités mentionnées
        entities = {
            "teachers": self._extract_teacher_names(user_input),
            "classes": self._extract_class_names(user_input),
            "subjects": self._extract_subject_names(user_input),
            "times": self._extract_time_references(user_input),
            "days": self._extract_day_references(user_input)
        }
        
        # Détecter l'action principale
        detected_actions = []
        for action, patterns in action_patterns.items():
            if any(pattern in user_input for pattern in patterns):
                detected_actions.append(action)
        
        return {
            "detected_actions": detected_actions,
            "entities": entities,
            "user_intent": self._determine_user_intent(detected_actions, entities),
            "complexity": self._assess_complexity(detected_actions, entities),
            "applicable_preferences": self._find_applicable_preferences(entities)
        }

    def _extract_preferences(self, user_input: str, language: str = "french") -> List[UserPreference]:
        """Extrait les nouvelles préférences/règles de l'input utilisateur (multilingue)"""
        new_preferences = []
        
        if language == "hebrew":
            preference_indicators = [
                "תמיד", "לעולם לא", "אני מעדיף", "אני אוהב", "חשוב לי", 
                "כדאי", "אסור", "חובה", "אני צריך", "עדיף"
            ]
        else:
            preference_indicators = [
                "toujours", "jamais", "préfère", "éviter", "pas le", "seulement",
                "règle", "contrainte", "pour moi", "c'est important"
            ]
        
        if any(indicator in user_input.lower() for indicator in preference_indicators):
            # Générer ID unique
            pref_id = f"pref_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Analyser le contexte pour créer une préférence
            preference = UserPreference(
                preference_id=pref_id,
                category="user_stated",
                entity="general",
                rule=user_input,
                priority=Priority.MEDIUM,
                active=True,
                created_at=datetime.now(),
                examples=[user_input]
            )
            
            new_preferences.append(preference)
            logger.info(f"Nouvelle préférence extraite ({language}): {user_input[:50]}...")
            
        return new_preferences

    def _generate_change_proposals(self, request: UserRequest, analysis: Dict[str, Any]) -> List[ScheduleChange]:
        """Génère des propositions de changements intelligentes"""
        proposals = []
        
        try:
            # Obtenir l'état actuel de l'emploi du temps
            current_schedule = self._get_current_schedule()
            
            logger.info(f"Intent détecté: '{analysis['user_intent']}'")
            
            if analysis["user_intent"] == "fix_gaps" or analysis["user_intent"] == "fix_schedule_gaps":
                logger.info("Génération de propositions pour combler les trous")
                proposals.extend(self._propose_gap_fixes(current_schedule, analysis))
            elif analysis["user_intent"] == "move_course":
                proposals.extend(self._propose_course_moves(current_schedule, analysis))
            elif analysis["user_intent"] == "balance_load":
                proposals.extend(self._propose_load_balancing(current_schedule, analysis))
            elif analysis["user_intent"] == "optimize_general":
                proposals.extend(self._propose_general_optimizations(current_schedule, analysis))
            else:
                logger.warning(f"Intent non géré: '{analysis['user_intent']}' - génération de propositions génériques")
                # Générer des propositions génériques pour tout intent
                proposals.extend(self._propose_gap_fixes(current_schedule, analysis))
                
        except Exception as e:
            logger.error(f"Erreur génération propositions: {e}")
            
        return proposals

    def _propose_gap_fixes(self, schedule: List[Dict], analysis: Dict[str, Any]) -> List[ScheduleChange]:
        """Propose des solutions pour éliminer les trous"""
        proposals = []
        
        # Analyser les trous existants
        gaps = self._analyze_schedule_gaps(schedule)
        logger.info(f"Trous trouvés avant filtrage: {len(gaps)}")
        
        # Filtrer les trous pour la classe demandée si spécifiée
        target_classes = analysis.get("entities", {}).get("classes", [])
        logger.info(f"Classes cibles: {target_classes}")
        
        if target_classes:
            gaps_before = len(gaps)
            gaps = [g for g in gaps if g['class'] in target_classes]
            logger.info(f"Trous après filtrage pour {target_classes}: {len(gaps)} (avant: {gaps_before})")
        
        # Si pas de classes spécifiques, chercher ז-1 dans tous les cas
        if not gaps and target_classes:
            # Chercher avec différentes variantes du nom de classe
            for target_class in target_classes:
                # Essayer différentes variations
                variations = [target_class, target_class.replace('-', ''), f"כיתה {target_class}"]
                for variation in variations:
                    matching_gaps = [g for g in self._analyze_schedule_gaps(schedule) if variation in g['class'] or g['class'] in variation]
                    if matching_gaps:
                        gaps.extend(matching_gaps)
                        logger.info(f"Trouvé {len(matching_gaps)} trous avec variation '{variation}'")
        
        # Créer des propositions détaillées pour chaque trou
        for gap in gaps:
            change_id = f"fix_gap_{gap['class']}_{gap['day']}_{datetime.now().strftime('%H%M%S')}"
            
            # Chercher des cours disponibles pour combler le trou
            available_solutions = self._find_gap_solutions(gap, schedule)
            
            if available_solutions:
                best_solution = available_solutions[0]  # Prendre la meilleure solution
                
                proposal = ScheduleChange(
                    change_id=change_id,
                    change_type=ChangeType.MOVE_COURSE,
                    description=f"📅 Combler le trou de {gap['size']} période(s) dans {gap['class']} le {gap['day_name']} (périodes {'-'.join(map(str, gap['gap_periods']))})",
                    affected_classes=[gap['class']] + best_solution.get('other_classes', []),
                    affected_teachers=gap.get('teachers', []) + best_solution.get('teachers', []),
                    current_state={
                        'problem': f"Trou entre {gap['before_subject']} et {gap['after_subject']}",
                        'gap_periods': gap['gap_periods'],
                        'class': gap['class'],
                        'day': gap['day_name']
                    },
                    proposed_state=best_solution,
                    impact_analysis={
                        'positive_impact': f"Emploi du temps plus compact pour {gap['class']}",
                        'courses_moved': len(best_solution.get('moves', [])),
                        'efficiency_gain': f"{gap['size']} période(s) récupérée(s)",
                        'risks': best_solution.get('potential_conflicts', [])
                    },
                    confidence_score=best_solution.get('confidence', 0.7),
                    reasoning=best_solution.get('reasoning', f"Optimisation automatique détectée pour {gap['class']}")
                )
                
                proposals.append(proposal)
            else:
                # Même si pas de solution parfaite, expliquer pourquoi
                proposal = ScheduleChange(
                    change_id=change_id,
                    change_type=ChangeType.MOVE_COURSE,
                    description=f"⚠️ Trou détecté dans {gap['class']} le {gap['day_name']} - Solutions limitées",
                    affected_classes=[gap['class']],
                    affected_teachers=gap.get('teachers', []),
                    current_state=gap,
                    proposed_state={'status': 'no_optimal_solution'},
                    impact_analysis=self._analyze_gap_constraints(gap, schedule),
                    confidence_score=0.3,
                    reasoning=f"Trou de {gap['size']} période(s) détecté mais difficile à combler - voir contraintes"
                )
                
                proposals.append(proposal)
        
        if not gaps and target_classes:
            # Si aucun trou trouvé pour cette classe, le dire explicitement
            no_gaps_info = ScheduleChange(
                change_id=f"no_gaps_{datetime.now().strftime('%H%M%S')}",
                change_type=ChangeType.MOVE_COURSE,
                description=f"✅ Bonne nouvelle: Aucun trou majeur détecté dans {', '.join(target_classes)}",
                affected_classes=target_classes,
                affected_teachers=[],
                current_state={'status': 'already_optimized'},
                proposed_state={'status': 'no_action_needed'},
                impact_analysis={'message': 'Emploi du temps déjà bien structuré'},
                confidence_score=0.9,
                reasoning="Analyse automatique: emploi du temps sans trous significatifs"
            )
            proposals.append(no_gaps_info)
            
        return proposals

    def _create_advisor_response(self, request: UserRequest, analysis: Dict[str, Any], 
                               changes: List[ScheduleChange], new_prefs: List[UserPreference]) -> Dict[str, Any]:
        """Crée une réponse intelligente et conversationnelle (multilingue)"""
        
        # Détecter la langue de la demande
        is_hebrew = request.context.get("language") == "hebrew"
        
        # Analyser le contexte pour personnaliser la réponse
        user_name = request.context.get("user_name", "")
        
        if is_hebrew:
            greeting = f"שלום {user_name}, " if user_name else "שלום, "
        else:
            greeting = f"Bonjour {user_name}, " if user_name else "Bonjour, "
        
        # Message principal basé sur l'analyse
        if not changes:
            if is_hebrew:
                message = f"{greeting}ניתחתי את הבקשה שלך '{request.user_input}'. "
                if analysis["user_intent"] == "unknown":
                    message += "האם תוכל לתת לי יותר פרטים על מה שאתה רוצה לשנות במערכת השעות? "
                    message += "לדוגמה: 'להזיז את השיעור מתמטיקה של ז-1', 'למלא חורים במערכת השעות', וכו'."
                else:
                    message += "אני מבין את הצורך שלך אבל לא מצאתי שיפורים אופטימליים להציע כרגע. "
                    message += "נראה שמערכת השעות הנוכחית כבר מותאמת טוב לבקשה הזו."
            else:
                message = f"{greeting}J'ai analysé votre demande '{request.user_input}'. "
                if analysis["user_intent"] == "unknown":
                    message += "Pouvez-vous me donner plus de détails sur ce que vous souhaitez modifier dans l'emploi du temps ? "
                    message += "Par exemple : 'déplacer le cours de maths de ז-1', 'éliminer les trous dans l'emploi du temps', etc."
                else:
                    message += "Je comprends votre besoin mais je n'ai pas trouvé de modifications optimales à proposer pour le moment. "
                    message += "L'emploi du temps actuel semble déjà bien optimisé pour cette demande."
                
        else:
            if is_hebrew:
                message = f"{greeting}ניתחתי את הבקשה שלך ואני מציע {len(changes)} שינוי(ים) לשיפור מערכת השעות:\n\n"
                
                for i, change in enumerate(changes, 1):
                    confidence_emoji = "🟢" if change.confidence_score > 0.8 else "🟡" if change.confidence_score > 0.6 else "🟠"
                    message += f"{confidence_emoji} **הצעה {i}** (ביטחון: {change.confidence_score:.0%})\n"
                    message += f"   {change.description}\n"
                    message += f"   *למה:* {change.reasoning}\n"
                    message += f"   *השפעה:* {len(change.affected_classes)} כיתות, {len(change.affected_teachers)} מורים\n\n"
                
                message += "האם אתה רוצה שאיישם את השינויים האלה? תענה 'כן' לאישור או 'פרטים נוספים' למידע נוסף."
            else:
                message = f"{greeting}J'ai analysé votre demande et je vous propose {len(changes)} modification(s) pour améliorer l'emploi du temps :\n\n"
                
                for i, change in enumerate(changes, 1):
                    confidence_emoji = "🟢" if change.confidence_score > 0.8 else "🟡" if change.confidence_score > 0.6 else "🟠"
                    message += f"{confidence_emoji} **Proposition {i}** (confiance: {change.confidence_score:.0%})\n"
                    message += f"   {change.description}\n"
                    message += f"   *Pourquoi:* {change.reasoning}\n"
                    message += f"   *Impact:* {len(change.affected_classes)} classe(s), {len(change.affected_teachers)} professeur(s)\n\n"
                
                message += "Voulez-vous que j'applique ces modifications ? Répondez 'oui' pour confirmer ou 'plus de détails' pour plus d'informations."
        
        # Mentionner les nouvelles préférences détectées
        if new_prefs:
            if is_hebrew:
                message += f"\n\n📝 גם רשמתי {len(new_prefs)} העדפה/ות חדשה/ות שלך שאשמור בזיכרון לאופטימיזציות הבאות."
            else:
                message += f"\n\n📝 J'ai également noté {len(new_prefs)} nouvelle(s) préférence(s) de votre part que je garderai en mémoire pour les prochaines optimisations."
        
        # Sauvegarder les changements proposés
        for change in changes:
            self.pending_changes[change.change_id] = change
            
        return {
            "request_id": request.request_id,
            "message": message,
            "success": True,
            "analysis": {
                "user_intent": analysis["user_intent"],
                "detected_actions": analysis["detected_actions"],
                "entities_found": {k: len(v) for k, v in analysis["entities"].items() if v},
                "complexity": analysis["complexity"]
            },
            "proposals": [self._serialize_change(change) for change in changes],
            "new_preferences": [asdict(pref) for pref in new_prefs],
            "next_actions": ["confirm", "reject", "modify", "details"] if changes else ["clarify"],
            "conversation_context": {
                "awaiting_confirmation": len(changes) > 0,
                "pending_changes": [c.change_id for c in changes]
            }
        }

    def confirm_changes(self, change_ids: List[str], user_confirmation: str = "yes") -> Dict[str, Any]:
        """Applique les changements confirmés par l'utilisateur"""
        if user_confirmation.lower() not in ["yes", "oui", "confirm", "confirmer", "ok", "כן", "אישור", "בסדר"]:
            # Annuler les changements
            for change_id in change_ids:
                if change_id in self.pending_changes:
                    del self.pending_changes[change_id]
            
            return {
                "message": "D'accord, j'ai annulé ces modifications. N'hésitez pas si vous voulez explorer d'autres options !",
                "success": True,
                "applied_changes": []
            }
        
        applied_changes = []
        errors = []
        
        for change_id in change_ids:
            if change_id not in self.pending_changes:
                errors.append(f"Changement {change_id} introuvable")
                continue
                
            try:
                change = self.pending_changes[change_id]
                success = self._apply_schedule_change(change)
                
                if success:
                    applied_changes.append(change)
                    self._log_applied_change(change)
                    del self.pending_changes[change_id]
                else:
                    errors.append(f"Échec application du changement {change_id}")
                    
            except Exception as e:
                errors.append(f"Erreur pour {change_id}: {str(e)}")
        
        # Message de confirmation
        if applied_changes and not errors:
            message = f"✅ Parfait ! J'ai appliqué {len(applied_changes)} modification(s) à l'emploi du temps. "
            message += "Les changements sont maintenant actifs. Voulez-vous que j'analyse le nouvel emploi du temps ?"
        elif applied_changes and errors:
            message = f"⚠️ J'ai appliqué {len(applied_changes)} modification(s) avec succès, mais il y a eu {len(errors)} problème(s): "
            message += "; ".join(errors[:2])
        else:
            message = "❌ Désolé, je n'ai pas pu appliquer les modifications. Erreurs: " + "; ".join(errors[:3])
            
        self._add_to_conversation("assistant", message)
        
        return {
            "message": message,
            "success": len(applied_changes) > 0,
            "applied_changes": [self._serialize_change(change) for change in applied_changes],
            "errors": errors
        }

    def get_user_preferences_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des préférences/revendications utilisateur"""
        categories = {}
        for pref in self.user_preferences.values():
            if pref.category not in categories:
                categories[pref.category] = []
            categories[pref.category].append({
                "rule": pref.rule,
                "entity": pref.entity,
                "priority": pref.priority.value,
                "created": pref.created_at.strftime("%Y-%m-%d")
            })
            
        return {
            "total_preferences": len(self.user_preferences),
            "categories": categories,
            "active_preferences": len([p for p in self.user_preferences.values() if p.active])
        }

    def _save_user_preference(self, preference: UserPreference):
        """Sauvegarde une préférence utilisateur"""
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO user_preferences 
                (preference_id, category, entity, rule, priority, active, created_at, examples)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (preference_id) DO UPDATE SET
                    rule = EXCLUDED.rule,
                    priority = EXCLUDED.priority,
                    active = EXCLUDED.active
            """, (
                preference.preference_id,
                preference.category,
                preference.entity,
                preference.rule,
                preference.priority.value,
                preference.active,
                preference.created_at,
                json.dumps(preference.examples)
            ))
            
            conn.commit()
            self.user_preferences[preference.preference_id] = preference
            logger.info(f"✓ Préférence sauvegardée: {preference.preference_id}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde préférence: {e}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def _serialize_change(self, change: ScheduleChange) -> Dict[str, Any]:
        """Sérialise un ScheduleChange pour JSON"""
        return {
            'change_id': change.change_id,
            'change_type': change.change_type.value,  # Convertir enum en string
            'description': change.description,
            'affected_classes': change.affected_classes,
            'affected_teachers': change.affected_teachers,
            'current_state': change.current_state,
            'proposed_state': change.proposed_state,
            'impact_analysis': change.impact_analysis,
            'confidence_score': change.confidence_score,
            'reasoning': change.reasoning
        }

    def _add_to_conversation(self, role: str, content: str):
        """Ajoute un message à l'historique de conversation"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Garder seulement les 50 derniers messages
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]

    # Méthodes utilitaires (à implémenter selon vos besoins)
    def _get_current_schedule(self) -> List[Dict]:
        """Récupère l'emploi du temps actuel depuis la DB"""
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Récupérer les entrées d'emploi du temps actuelles
            cur.execute("""
                SELECT 
                    se.id,
                    se.class_name,
                    se.teacher_name,
                    COALESCE(se.subject_name, se.subject) as subject_name,
                    se.time_slot_id,
                    se.day_of_week,
                    se.period_number,
                    ts.start_time,
                    ts.end_time,
                    se.room,
                    CASE se.day_of_week 
                        WHEN 0 THEN 'Dimanche'
                        WHEN 1 THEN 'Lundi' 
                        WHEN 2 THEN 'Mardi'
                        WHEN 3 THEN 'Mercredi'
                        WHEN 4 THEN 'Jeudi'
                        WHEN 5 THEN 'Vendredi'
                        ELSE 'Jour_' || se.day_of_week::text
                    END as day_name
                FROM schedule_entries se
                LEFT JOIN time_slots ts ON se.time_slot_id = ts.slot_id
                WHERE se.schedule_id = (
                    SELECT schedule_id FROM schedules ORDER BY created_at DESC LIMIT 1
                )
                ORDER BY se.day_of_week, se.period_number
            """)
            
            entries = cur.fetchall()
            
            # Convertir en liste de dictionnaires
            schedule_data = []
            for entry in entries:
                schedule_data.append({
                    'id': entry['id'],
                    'class_name': entry['class_name'],
                    'teacher_name': entry['teacher_name'],
                    'subject_name': entry['subject_name'],
                    'day_of_week': entry['day_of_week'],
                    'period_number': entry['period_number'],
                    'start_time': str(entry['start_time']) if entry['start_time'] else '',
                    'end_time': str(entry['end_time']) if entry['end_time'] else '',
                    'room': entry['room'],
                    'day_name': entry['day_name']
                })
            
            logger.info(f"✓ Emploi du temps récupéré: {len(schedule_data)} entrées")
            return schedule_data
            
        except Exception as e:
            logger.error(f"Erreur récupération emploi du temps: {e}")
            return []
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def _analyze_schedule_gaps(self, schedule: List[Dict]) -> List[Dict]:
        """Analyse les trous dans l'emploi du temps"""
        gaps = []
        
        # Grouper par classe
        classes_schedule = {}
        for entry in schedule:
            class_name = entry['class_name']
            if class_name not in classes_schedule:
                classes_schedule[class_name] = {}
            
            day = entry['day_of_week']
            if day not in classes_schedule[class_name]:
                classes_schedule[class_name][day] = []
            
            classes_schedule[class_name][day].append({
                'period': entry['period_number'],
                'subject': entry['subject_name'],
                'teacher': entry['teacher_name'],
                'start_time': entry['start_time'],
                'end_time': entry['end_time']
            })
        
        # Analyser les trous pour chaque classe
        for class_name, days_data in classes_schedule.items():
            for day, periods in days_data.items():
                # Trier par période
                sorted_periods = sorted(periods, key=lambda x: x['period'])
                
                # Chercher les trous entre les cours
                for i in range(len(sorted_periods) - 1):
                    current_period = sorted_periods[i]['period']
                    next_period = sorted_periods[i + 1]['period']
                    
                    # S'il y a un trou (période manquante)
                    if next_period - current_period > 1:
                        gap_size = next_period - current_period - 1
                        gap_periods = list(range(current_period + 1, next_period))
                        
                        gaps.append({
                            'class': class_name,
                            'day': day,
                            'day_name': self._day_name(day),
                            'gap_periods': gap_periods,
                            'size': gap_size,
                            'before_subject': sorted_periods[i]['subject'],
                            'after_subject': sorted_periods[i + 1]['subject'],
                            'before_end': sorted_periods[i]['end_time'],
                            'after_start': sorted_periods[i + 1]['start_time'],
                            'teachers': [sorted_periods[i]['teacher'], sorted_periods[i + 1]['teacher']]
                        })
        
        # Logs de débogage
        classes_found = list(classes_schedule.keys())
        logger.info(f"Classes trouvées dans l'emploi du temps: {classes_found[:5]}...")  # Afficher les 5 premières
        
        if gaps:
            gap_classes = [g['class'] for g in gaps]
            logger.info(f"Classes avec des trous: {list(set(gap_classes))}")
        
        logger.info(f"✓ Analyse des trous terminée: {len(gaps)} trous trouvés")
        return gaps
        
    def _extract_teacher_names(self, text: str) -> List[str]:
        """Extrait les noms de professeurs du texte"""
        # Implementation extraction noms profs
        return []
        
    def _extract_class_names(self, text: str) -> List[str]:
        """Extrait les noms de classes du texte"""
        import re
        # Pattern principal pour les classes hébraïques
        class_pattern = r'[זחטיא]-[0-9]'
        classes = re.findall(class_pattern, text)
        
        # Chercher aussi avec le mot "כיתה" (classe en hébreu)
        kitah_pattern = r'כיתה\s+([זחטיא]-[0-9])'
        kitah_classes = re.findall(kitah_pattern, text)
        classes.extend(kitah_classes)
        
        # Chercher aussi des variations sans tiret
        loose_pattern = r'([זחטיא][0-9])'
        loose_classes = re.findall(loose_pattern, text)
        # Ajouter le tiret manquant
        for loose in loose_classes:
            formatted = f"{loose[0]}-{loose[1]}"
            if formatted not in classes:
                classes.append(formatted)
        
        return list(set(classes))  # Enlever les doublons
        
    def _extract_subject_names(self, text: str) -> List[str]:
        """Extrait les matières du texte"""
        subjects = ["מתמטיקה", "אנגלית", "תנך", "מדעים", "היסטוריה", "אזרחות"]
        found = []
        for subject in subjects:
            if subject in text:
                found.append(subject)
        return found
        
    def _extract_time_references(self, text: str) -> List[str]:
        """Extrait les références temporelles"""
        # Implementation extraction temps
        return []
        
    def _extract_day_references(self, text: str) -> List[str]:
        """Extrait les références aux jours"""
        days = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi"]
        return [day for day in days if day in text.lower()]
        
    def _determine_user_intent(self, actions: List[str], entities: Dict) -> str:
        """Détermine l'intention principale de l'utilisateur"""
        if "fix_gaps" in actions or any("trou" in str(entities).lower() for _ in [1]):
            return "fix_gaps"
        elif "move" in actions:
            return "move_course"
        elif "balance" in actions:
            return "balance_load"
        elif "optimize" in actions:
            return "optimize_general"
        else:
            return "unknown"
            
    def _assess_complexity(self, actions: List[str], entities: Dict) -> str:
        """Évalue la complexité de la demande"""
        total_entities = sum(len(v) for v in entities.values() if isinstance(v, list))
        if len(actions) > 2 or total_entities > 5:
            return "high"
        elif len(actions) > 1 or total_entities > 2:
            return "medium"
        else:
            return "low"
            
    def _find_applicable_preferences(self, entities: Dict) -> List[str]:
        """Trouve les préférences applicables aux entités mentionnées"""
        applicable = []
        for pref_id, pref in self.user_preferences.items():
            if any(entity in str(entities) for entity in [pref.entity]):
                applicable.append(pref_id)
        return applicable

    def _find_gap_solutions(self, gap: Dict, schedule: List[Dict]) -> List[Dict]:
        """Trouve des solutions pour combler un trou"""
        solutions = []
        
        # Chercher des cours de la même classe qui pourraient être déplacés
        class_courses = [entry for entry in schedule if entry['class_name'] == gap['class']]
        
        # Chercher des cours d'autres classes qui pourraient libérer des créneaux
        other_courses = [entry for entry in schedule if entry['class_name'] != gap['class']]
        
        # Solution 1: Déplacer un cours existant dans le trou
        for period in gap['gap_periods']:
            # Chercher des cours à cette période mais un autre jour
            movable_courses = [
                course for course in class_courses 
                if course['period_number'] == period and course['day_of_week'] != gap['day']
            ]
            
            if movable_courses:
                solutions.append({
                    'type': 'move_existing',
                    'moves': [{'course': movable_courses[0], 'to_period': period, 'to_day': gap['day']}],
                    'reasoning': f"Déplacer {movable_courses[0]['subject_name']} vers le trou",
                    'confidence': 0.8,
                    'teachers': [movable_courses[0]['teacher_name']],
                    'potential_conflicts': []
                })
        
        # Solution 2: Échange avec une autre classe
        for period in gap['gap_periods']:
            conflicting_courses = [
                course for course in other_courses
                if course['day_of_week'] == gap['day'] and course['period_number'] == period
            ]
            
            for conflict_course in conflicting_courses[:2]:  # Limiter à 2 options
                solutions.append({
                    'type': 'swap_with_other_class',
                    'moves': [{'swap': conflict_course, 'with_class': gap['class']}],
                    'reasoning': f"Échanger créneau avec {conflict_course['class_name']} pour {conflict_course['subject_name']}",
                    'confidence': 0.6,
                    'teachers': [conflict_course['teacher_name']],
                    'other_classes': [conflict_course['class_name']],
                    'potential_conflicts': ['Vérifier disponibilité professeur']
                })
        
        # Trier par confiance décroissante
        solutions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        return solutions[:3]  # Retourner les 3 meilleures solutions
        
    def _analyze_gap_constraints(self, gap: Dict, schedule: List[Dict]) -> Dict:
        """Analyse pourquoi un trou est difficile à combler"""
        constraints = []
        
        # Vérifier les conflits de professeurs
        busy_teachers = set()
        for period in gap['gap_periods']:
            day_courses = [c for c in schedule if c['day_of_week'] == gap['day'] and c['period_number'] == period]
            for course in day_courses:
                busy_teachers.add(course['teacher_name'])
        
        if busy_teachers:
            constraints.append(f"Professeurs occupés: {', '.join(list(busy_teachers)[:3])}")
        
        # Vérifier les salles disponibles
        occupied_rooms = set()
        for period in gap['gap_periods']:
            day_courses = [c for c in schedule if c['day_of_week'] == gap['day'] and c['period_number'] == period]
            for course in day_courses:
                if course.get('room'):
                    occupied_rooms.add(course['room'])
        
        if len(occupied_rooms) > 5:  # Si beaucoup de salles occupées
            constraints.append("Salles limitées disponibles")
        
        return {
            'constraints': constraints,
            'difficulty': 'high' if len(constraints) > 2 else 'medium' if constraints else 'low',
            'suggestions': [
                "Considérer déplacer des cours vers un autre jour",
                "Vérifier si certains cours peuvent être regroupés",
                "Examiner la possibilité de cours en parallèle"
            ]
        }
        
    def _generate_gap_fix_solution(self, gap: Dict, schedule: List[Dict]) -> Dict:
        """Génère une solution pour combler un trou"""
        return {"proposed_moves": [], "reasoning": "Solution à implémenter"}
        
    def _analyze_gap_fix_impact(self, gap: Dict) -> Dict:
        """Analyse l'impact de combler un trou"""
        return {"positive_impact": "Less gaps", "risks": "Possible conflicts"}
        
    def _day_name(self, day_num: int) -> str:
        """Convertit numéro de jour en nom"""
        days = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
        return days[day_num] if 0 <= day_num < len(days) else str(day_num)
        
    def _apply_schedule_change(self, change: ScheduleChange) -> bool:
        """Applique réellement un changement à l'emploi du temps"""
        try:
            logger.info(f"Application changement: {change.description}")
            
            # Vérifier le type de changement et appliquer la logique appropriée
            if change.change_type == ChangeType.MOVE_COURSE:
                return self._apply_move_course_change(change)
            elif change.change_type == ChangeType.SWAP_COURSES:
                return self._apply_swap_courses_change(change)
            elif change.change_type == ChangeType.ADD_COURSE:
                return self._apply_add_course_change(change)
            elif change.change_type == ChangeType.REMOVE_COURSE:
                return self._apply_remove_course_change(change)
            else:
                logger.warning(f"Type de changement non supporté: {change.change_type}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'application du changement {change.change_id}: {e}")
            return False
    
    def _apply_move_course_change(self, change: ScheduleChange) -> bool:
        """Applique un déplacement de cours"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Récupérer les informations du changement
            proposed_state = change.proposed_state
            moves = proposed_state.get("moves", [])
            
            for move in moves:
                course = move["course"]
                to_day = move["to_day"]
                to_period = move["to_period"]
                
                # Mettre à jour l'entrée dans schedule_entries
                # Gérer les deux champs subject_name et subject
                update_query = """
                    UPDATE schedule_entries 
                    SET day_of_week = %s, period_number = %s
                    WHERE class_name = %s 
                    AND (subject_name = %s OR subject = %s)
                    AND teacher_name = %s
                    AND day_of_week = %s 
                    AND period_number = %s
                """
                
                cur.execute(update_query, (
                    to_day, to_period,
                    course["class_name"], course["subject_name"], course["subject_name"], course["teacher_name"],
                    course["day_of_week"], course["period_number"]
                ))
                
                logger.info(f"Cours déplacé: {course['subject_name']} pour {course['class_name']} " +
                           f"de {course['day_of_week']}/P{course['period_number']} vers {to_day}/P{to_period}")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Erreur déplacement cours: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    def _apply_swap_courses_change(self, change: ScheduleChange) -> bool:
        """Applique un échange de cours"""
        logger.info("Échange de cours - Non implémenté encore")
        return False
    
    def _apply_add_course_change(self, change: ScheduleChange) -> bool:
        """Applique l'ajout d'un cours"""
        logger.info("Ajout de cours - Non implémenté encore")
        return False
    
    def _apply_remove_course_change(self, change: ScheduleChange) -> bool:
        """Applique la suppression d'un cours"""
        logger.info("Suppression de cours - Non implémenté encore")
        return False
        
    def _log_applied_change(self, change: ScheduleChange):
        """Log un changement appliqué"""
        logger.info(f"✓ Changement appliqué: {change.change_id} - {change.description}")
    
    def initialize_optimization_engine(self) -> bool:
        """Initialise le moteur d'optimisation avec les données d'emploi du temps"""
        try:
            schedule_data = self._get_current_schedule_data()
            if schedule_data:
                self.optimization_engine = AdvancedSchedulingEngine(schedule_data)
                logger.info("🧠 Moteur d'optimisation avancé initialisé")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur initialisation moteur d'optimisation: {e}")
            return False
    
    def _get_current_schedule_data(self) -> Optional[Dict]:
        """Récupère les données actuelles de l'emploi du temps"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Récupérer les entrées d'emploi du temps
            cur.execute("""
                SELECT class_name, subject_name, teacher_name, day_of_week, 
                       period_number, room
                FROM schedule_entries 
                WHERE class_name IS NOT NULL
                ORDER BY class_name, day_of_week, period_number
            """)
            
            entries = cur.fetchall()
            schedule_data = {
                'entries': [dict(entry) for entry in entries],
                'metadata': {
                    'total_entries': len(entries),
                    'classes': list(set(entry['class_name'] for entry in entries if entry['class_name'])),
                    'teachers': list(set(entry['teacher_name'] for entry in entries if entry['teacher_name'])),
                    'subjects': list(set(entry['subject_name'] for entry in entries if entry['subject_name']))
                }
            }
            
            return schedule_data
            
        except Exception as e:
            logger.error(f"Erreur récupération données emploi du temps: {e}")
            return None
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def optimize_schedule_with_advanced_algorithms(self, algorithm: str = "hybrid", 
                                                 objectives: List[Dict] = None) -> Dict[str, Any]:
        """
        Optimise l'emploi du temps avec les algorithmes avancés
        
        Args:
            algorithm: 'simulated_annealing', 'tabu_search', 'hybrid', 'multi_objective'
            objectives: Liste des objectifs pour optimisation multi-objectifs
        """
        if not self.optimization_engine:
            if not self.initialize_optimization_engine():
                return {"error": "Impossible d'initialiser le moteur d'optimisation"}
        
        try:
            schedule_data = self._get_current_schedule_data()
            if not schedule_data:
                return {"error": "Impossible de récupérer les données d'emploi du temps"}
            
            logger.info(f"🚀 Démarrage optimisation avec algorithme: {algorithm}")
            
            if algorithm == "simulated_annealing":
                result = self.optimization_engine.simulated_annealing_optimization(schedule_data)
            elif algorithm == "tabu_search":
                result = self.optimization_engine.tabu_search_optimization(schedule_data)
            elif algorithm == "hybrid":
                result = self.optimization_engine.hybrid_optimization(schedule_data)
            elif algorithm == "multi_objective":
                # Créer les objectifs par défaut si non fournis
                if not objectives:
                    objectives = [
                        {"name": "hard_constraints", "weight": 0.4},
                        {"name": "soft_constraints", "weight": 0.3},
                        {"name": "pedagogical_quality", "weight": 0.3}
                    ]
                
                optimization_objectives = [
                    OptimizationObjective(
                        name=obj["name"],
                        weight=obj["weight"],
                        current_value=0.0,
                        is_hard_constraint=obj.get("is_hard_constraint", False)
                    ) for obj in objectives
                ]
                
                result = self.optimization_engine.multi_objective_optimization(
                    schedule_data, optimization_objectives
                )
            else:
                return {"error": f"Algorithme non supporté: {algorithm}"}
            
            # Enrichir le résultat avec des recommandations
            result["recommendations"] = self._generate_optimization_recommendations(result)
            result["algorithm_info"] = self._get_algorithm_info(algorithm)
            
            logger.info(f"✅ Optimisation terminée - Score: {result.get('quality', {}).get('total_score', 0):.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur optimisation avancée: {e}")
            return {"error": f"Erreur optimisation: {str(e)}"}
    
    def _generate_optimization_recommendations(self, optimization_result: Dict) -> List[Dict]:
        """Génère des recommandations basées sur le résultat d'optimisation"""
        recommendations = []
        
        quality = optimization_result.get("quality", {})
        
        # Recommandations basées sur les contraintes dures
        hard_constraints_score = quality.get("hard_constraints_satisfied", 0.0)
        if hard_constraints_score < 0.9:
            recommendations.append({
                "type": "critical",
                "message": f"Contraintes dures non satisfaites ({hard_constraints_score:.1%})",
                "action": "Résoudre les conflits de professeurs et salles en priorité",
                "priority": "high"
            })
        
        # Recommandations basées sur la qualité pédagogique
        pedagogical_score = quality.get("pedagogical_quality", 0.0)
        if pedagogical_score < 0.7:
            recommendations.append({
                "type": "improvement",
                "message": f"Qualité pédagogique faible ({pedagogical_score:.1%})",
                "action": "Créer plus de blocs de cours consécutifs",
                "priority": "medium"
            })
        
        # Recommandations basées sur les trous
        gaps = quality.get("student_gaps", 0)
        if gaps > 10:
            recommendations.append({
                "type": "optimization",
                "message": f"Trop de trous détectés ({gaps})",
                "action": "Réorganiser les créneaux pour minimiser les pauses",
                "priority": "medium"
            })
        
        return recommendations
    
    def _get_algorithm_info(self, algorithm: str) -> Dict[str, str]:
        """Retourne des informations sur l'algorithme utilisé"""
        algorithm_info = {
            "simulated_annealing": {
                "name": "Recuit Simulé",
                "description": "Algorithme métaheuristique inspiré du processus de refroidissement",
                "strengths": "Évite les optima locaux, bon pour l'exploration globale",
                "best_for": "Problèmes avec beaucoup d'optima locaux"
            },
            "tabu_search": {
                "name": "Recherche Tabou", 
                "description": "Recherche locale avec mémoire pour éviter les cycles",
                "strengths": "Efficace pour le raffinement local, robuste",
                "best_for": "Amélioration de solutions existantes"
            },
            "hybrid": {
                "name": "Approche Hybride",
                "description": "Combine PC + Recuit Simulé + Recherche Tabou",
                "strengths": "Synergie des méthodes, qualité supérieure",
                "best_for": "Problèmes complexes nécessitant faisabilité + optimisation"
            },
            "multi_objective": {
                "name": "Optimisation Multi-Objectifs",
                "description": "Optimise plusieurs critères simultanément",
                "strengths": "Équilibre entre objectifs conflictuels",
                "best_for": "Quand il faut concilier coûts, qualité et satisfaction"
            }
        }
        
        return algorithm_info.get(algorithm, {
            "name": algorithm,
            "description": "Algorithme d'optimisation",
            "strengths": "Non spécifié",
            "best_for": "Cas général"
        })
    
    def recommend_best_algorithm(self, problem_context: Dict = None) -> Dict[str, Any]:
        """Recommande le meilleur algorithme selon le contexte du problème"""
        if not problem_context:
            problem_context = self._analyze_current_problem_context()
        
        if not self.optimization_engine:
            if not self.initialize_optimization_engine():
                return {"error": "Impossible d'analyser le contexte"}
        
        recommendation = self.optimization_engine.recommend_algorithm(problem_context)
        
        return {
            "recommended_algorithm": recommendation,
            "problem_analysis": problem_context,
            "reasoning": self._explain_algorithm_choice(recommendation, problem_context),
            "alternatives": self._suggest_alternative_algorithms(recommendation)
        }
    
    def _analyze_current_problem_context(self) -> Dict[str, Any]:
        """Analyse le contexte actuel du problème pour recommander un algorithme"""
        try:
            schedule_data = self._get_current_schedule_data()
            if not schedule_data:
                return {"size": "unknown", "constraint_complexity": "medium"}
            
            metadata = schedule_data.get("metadata", {})
            entries = schedule_data.get("entries", [])
            
            # Analyser la taille du problème
            total_entries = len(entries)
            if total_entries < 100:
                size = "small"
            elif total_entries < 500:
                size = "medium"
            else:
                size = "large"
            
            # Analyser la complexité des contraintes
            unique_teachers = len(metadata.get("teachers", []))
            unique_classes = len(metadata.get("classes", []))
            
            if unique_teachers > 20 and unique_classes > 15:
                constraint_complexity = "high"
            elif unique_teachers > 10 and unique_classes > 8:
                constraint_complexity = "medium"
            else:
                constraint_complexity = "low"
            
            return {
                "size": size,
                "constraint_complexity": constraint_complexity,
                "total_entries": total_entries,
                "unique_teachers": unique_teachers,
                "unique_classes": unique_classes,
                "time_limit_seconds": 300,  # Valeur par défaut
                "optimality_required": False
            }
            
        except Exception as e:
            logger.error(f"Erreur analyse contexte: {e}")
            return {"size": "medium", "constraint_complexity": "medium"}
    
    def _explain_algorithm_choice(self, algorithm: str, context: Dict) -> str:
        """Explique pourquoi un algorithme a été recommandé"""
        explanations = {
            "constraint_programming": "Problème de petite taille nécessitant une solution optimale garantie",
            "simulated_annealing": "Bon compromis temps/qualité pour exploration globale",
            "tabu_search": "Efficace pour améliorer des solutions existantes",
            "hybrid_optimization": "Problème complexe nécessitant la combinaison de plusieurs approches"
        }
        
        base_explanation = explanations.get(algorithm, "Algorithme général recommandé")
        
        # Ajouter des détails spécifiques au contexte
        details = []
        if context.get("size") == "large":
            details.append("taille importante du problème")
        if context.get("constraint_complexity") == "high":
            details.append("contraintes complexes")
        if context.get("time_limit_seconds", 0) < 60:
            details.append("contrainte de temps serrée")
        
        if details:
            base_explanation += f" (basé sur: {', '.join(details)})"
        
        return base_explanation
    
    def _suggest_alternative_algorithms(self, recommended: str) -> List[Dict]:
        """Suggère des algorithmes alternatifs"""
        alternatives = {
            "constraint_programming": [
                {"name": "hybrid_optimization", "reason": "Si temps disponible pour qualité supérieure"},
                {"name": "simulated_annealing", "reason": "Si optimalité stricte non requise"}
            ],
            "simulated_annealing": [
                {"name": "tabu_search", "reason": "Pour un raffinement plus précis"},
                {"name": "hybrid_optimization", "reason": "Pour problèmes très complexes"}
            ],
            "tabu_search": [
                {"name": "simulated_annealing", "reason": "Pour exploration plus large"},
                {"name": "hybrid_optimization", "reason": "Pour combiner exploration et exploitation"}
            ],
            "hybrid_optimization": [
                {"name": "multi_objective", "reason": "Si plusieurs objectifs conflictuels"},
                {"name": "tabu_search", "reason": "Si temps de calcul limité"}
            ]
        }
        
        return alternatives.get(recommended, [])
    
    def optimize_with_intelligent_learning(self) -> Dict[str, Any]:
        """
        Optimisation intelligente basée sur l'apprentissage automatique
        """
        logger.info("🧠 Optimisation intelligente avec apprentissage")
        
        # Analyser le contexte actuel
        schedule_data = self._get_current_schedule_data()
        if not schedule_data:
            return {"error": "Impossible de récupérer les données"}
        
        # Préparer les données pour l'analyse
        analysis_data = self._prepare_analysis_data(schedule_data)
        
        # Obtenir la recommandation intelligente
        recommendation = self.training_system.recommend_algorithm_intelligent(analysis_data)
        
        logger.info(f"🎯 Pattern détecté: {recommendation['pattern_detected']}")
        logger.info(f"🚀 Algorithme sélectionné: {recommendation['primary_algorithm']}")
        logger.info(f"📊 Confiance: {recommendation['confidence']:.1%}")
        
        # Exécuter l'optimisation avec l'algorithme recommandé
        result = self.optimize_schedule_with_advanced_algorithms(
            algorithm=recommendation['primary_algorithm'],
            objectives=self._generate_objectives_from_pattern(recommendation['pattern_detected'])
        )
        
        # Enregistrer le résultat pour apprentissage futur
        if "quality" in result:
            from ai_training_system import LearningOutcome, ProblemPattern
            
            outcome = LearningOutcome(
                pattern=ProblemPattern(recommendation['pattern_detected']),
                algorithm_used=recommendation['primary_algorithm'],
                initial_quality=analysis_data.get("quality_score", 0),
                final_quality=result["quality"]["total_score"],
                improvement=result["quality"]["total_score"] - analysis_data.get("quality_score", 0),
                execution_time=300,  # Estimation
                success=result["quality"]["total_score"] > analysis_data.get("quality_score", 0),
                insights=recommendation.get("learning_insights", [])
            )
            
            self.training_system.update_knowledge(outcome)
            self.training_system.save_training_results()
        
        # Enrichir le résultat avec les informations d'apprentissage
        result["learning_info"] = {
            "pattern_detected": recommendation['pattern_detected'],
            "algorithm_selected": recommendation['primary_algorithm'],
            "confidence": recommendation['confidence'],
            "reasoning": recommendation['reasoning'],
            "insights": recommendation['learning_insights'],
            "alternatives": recommendation['alternative_algorithms']
        }
        
        return result
    
    def _prepare_analysis_data(self, schedule_data: Dict) -> Dict[str, Any]:
        """Prépare les données pour l'analyse de pattern"""
        
        # Analyser les conflits
        conflicts = 0
        gaps = 0
        fragmentation_index = 0
        
        entries = schedule_data.get("entries", [])
        
        # Compter les conflits professeurs
        teacher_slots = {}
        for entry in entries:
            teacher = entry.get("teacher_name", "")
            day = entry.get("day_of_week", 0)
            period = entry.get("period_number", 0)
            slot_key = f"{teacher}_{day}_{period}"
            
            if teacher and teacher != "לא משובץ":
                if slot_key in teacher_slots:
                    conflicts += 1
                teacher_slots[slot_key] = True
        
        # Analyser les trous et la fragmentation
        class_schedules = {}
        for entry in entries:
            class_name = entry.get("class_name", "")
            day = entry.get("day_of_week", 0)
            period = entry.get("period_number", 0)
            
            if class_name not in class_schedules:
                class_schedules[class_name] = {}
            if day not in class_schedules[class_name]:
                class_schedules[class_name][day] = []
            
            class_schedules[class_name][day].append(period)
        
        # Calculer les gaps
        for class_name, days in class_schedules.items():
            for day, periods in days.items():
                if len(periods) > 1:
                    periods.sort()
                    for i in range(len(periods) - 1):
                        gap_size = periods[i + 1] - periods[i] - 1
                        if gap_size > 0:
                            gaps += gap_size
        
        # Calculer l'indice de fragmentation
        consecutive_blocks = 0
        total_blocks = 0
        
        for class_name, days in class_schedules.items():
            for day, periods in days.items():
                total_blocks += len(periods)
                if len(periods) > 1:
                    periods.sort()
                    for i in range(len(periods) - 1):
                        if periods[i + 1] == periods[i] + 1:
                            consecutive_blocks += 1
        
        if total_blocks > 0:
            fragmentation_index = 1.0 - (consecutive_blocks / total_blocks)
        
        # Calculer la qualité actuelle
        quality_score = 0.195  # Valeur par défaut basée sur votre système
        if self.optimization_engine:
            quality_result = self.optimization_engine.analyze_schedule_quality(schedule_data)
            quality_score = quality_result.get("total_score", 0.195)
        
        return {
            "total_entries": len(entries),
            "conflicts": conflicts,
            "gaps": gaps,
            "quality_score": quality_score,
            "fragmentation_index": fragmentation_index,
            "classes": len(schedule_data.get("metadata", {}).get("classes", [])),
            "teachers": len(schedule_data.get("metadata", {}).get("teachers", [])),
            "teacher_conflicts": conflicts,
            "pedagogical_score": quality_score
        }
    
    def _generate_objectives_from_pattern(self, pattern: str) -> List[Dict]:
        """Génère les objectifs d'optimisation selon le pattern détecté"""
        
        objectives_map = {
            "high_conflict": [
                {"name": "hard_constraints", "weight": 0.6, "is_hard_constraint": True},
                {"name": "soft_constraints", "weight": 0.4}
            ],
            "fragmented": [
                {"name": "pedagogical_quality", "weight": 0.5},
                {"name": "gap_minimization", "weight": 0.5}
            ],
            "gaps_heavy": [
                {"name": "gap_minimization", "weight": 0.6},
                {"name": "pedagogical_quality", "weight": 0.4}
            ],
            "unbalanced": [
                {"name": "soft_constraints", "weight": 0.5},
                {"name": "hard_constraints", "weight": 0.3},
                {"name": "pedagogical_quality", "weight": 0.2}
            ],
            "pedagogical_poor": [
                {"name": "pedagogical_quality", "weight": 0.6},
                {"name": "gap_minimization", "weight": 0.2},
                {"name": "hard_constraints", "weight": 0.2}
            ],
            "complex_mixed": [
                {"name": "hard_constraints", "weight": 0.4, "is_hard_constraint": True},
                {"name": "pedagogical_quality", "weight": 0.3},
                {"name": "gap_minimization", "weight": 0.2},
                {"name": "soft_constraints", "weight": 0.1}
            ]
        }
        
        return objectives_map.get(pattern, objectives_map["complex_mixed"])
    
    def train_agent_on_all_scenarios(self) -> Dict[str, Any]:
        """
        Entraîne l'agent sur tous les scénarios possibles
        """
        logger.info("🎓 Début de l'entraînement complet de l'agent AI")
        
        # Effectuer un cycle complet d'entraînement
        training_results = self.training_system.train_full_cycle()
        
        # Sauvegarder les résultats
        self.training_system.save_training_results()
        
        logger.info(f"✅ Entraînement terminé: {training_results['success_rate']:.1%} de succès")
        logger.info(f"📊 Amélioration moyenne: {training_results['average_improvement']:.1%}")
        
        # Afficher les rankings
        logger.info("🏆 Classement des algorithmes:")
        for i, algo in enumerate(training_results['algorithm_rankings'][:3], 1):
            logger.info(f"  {i}. {algo['algorithm']}: Score {algo['score']:.2f}")
        
        # Afficher les insights clés
        logger.info("💡 Insights clés:")
        for insight in training_results['key_insights']:
            logger.info(f"  - {insight}")
        
        # Convertir les données pour la sérialisation JSON
        serializable_results = {
            "total_cases": training_results.get("total_cases", 0),
            "successful_cases": training_results.get("successful_cases", 0),
            "success_rate": training_results.get("success_rate", 0),
            "average_improvement": training_results.get("average_improvement", 0),
            "pattern_performance": training_results.get("pattern_performance", {}),
            "algorithm_rankings": training_results.get("algorithm_rankings", []),
            "key_insights": training_results.get("key_insights", [])
        }
        
        return serializable_results

# Fonctions utilitaires pour l'API
def create_advisor_agent(db_config: Dict[str, str]) -> ScheduleAdvisorAgent:
    """Factory function pour créer un agent conseiller"""
    return ScheduleAdvisorAgent(db_config)
"""Parseur NLP amélioré avec agent conversationnel intelligent"""
import re
import json
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime
import logging
from models import ConstraintType, ConstraintPriority, ConstraintInput

logger = logging.getLogger(__name__)


class NaturalLanguageParser:
    """Parse les contraintes en langage naturel avec intelligence évolutive"""
    
    def __init__(self):
        # Mappings de base (seront enrichis avec le temps)
        self.hebrew_mappings = {
            "ראשון": 0, "שני": 1, "שלישי": 2, "רביעי": 3, "חמישי": 4, "שישי": 5,
            "שעה ראשונה": "08:00", "שעה שנייה": "08:45", "שעה שלישית": "09:30",
            "תפילה": "prayer", "מתמטיקה": "math", "עברית": "hebrew",
        }
        
        self.french_mappings = {
            "lundi": 1, "mardi": 2, "mercredi": 3, "jeudi": 4, "vendredi": 5, "dimanche": 0,
            "matin": [1,2,3,4], "après-midi": [5,6,7,8],
        }
        
        # Base de connaissances qui va s'enrichir
        self.knowledge_base = self._load_knowledge_base()
        
        # Patterns appris (va grandir avec le temps)
        self.learned_patterns = self._load_learned_patterns()
        
        # État de conversation
        self.conversation_state = {}
        
    def _load_knowledge_base(self) -> Dict:
        """Charge la base de connaissances (depuis fichier ou DB)"""
        try:
            # Dans 5 mois, ce fichier contiendra des milliers d'entrées !
            with open('knowledge/constraint_patterns.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            # Base initiale
            return {
                "successful_parses": [],
                "user_corrections": [],
                "common_phrases": {},
                "entity_aliases": {
                    "cohen": ["כהן", "kohen", "cohen", "prof cohen"],
                    "math": ["מתמטיקה", "mathématiques", "maths", "math"],
                },
                "context_rules": {
                    "תפילה": {
                        "default_time": "08:00",
                        "default_days": [0,1,2,3,4],
                        "typical_duration": 30
                    }
                }
            }
    
    def _load_learned_patterns(self) -> List[Dict]:
        """Charge les patterns appris des utilisations précédentes"""
        try:
            with open('knowledge/learned_patterns.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def parse(self, text: str, language: str = "auto") -> ConstraintInput:
        """Parse avec apprentissage continu"""
        original_text = text
        
        # 1. Détecter la langue si auto
        if language == "auto":
            language = self._detect_language(text)
        
        # 2. Chercher d'abord dans les patterns appris
        learned_result = self._check_learned_patterns(text)
        if learned_result and learned_result.get("confidence", 0) > 0.9:
            logger.info(f"Utilisé pattern appris avec confiance {learned_result['confidence']}")
            return self._build_constraint_input(learned_result, original_text)
        
        # 3. Normaliser et extraire
        normalized = self._normalize_text(text, language)
        constraint_data = self._extract_constraint(normalized, language)
        
        # 4. Enrichir avec le contexte
        constraint_data = self._enrich_with_context(constraint_data, text)
        
        # 5. Sauvegarder pour apprentissage futur
        self._save_parse_attempt(text, constraint_data, language)
        
        # 6. Construire la réponse
        return self._build_constraint_input(constraint_data, original_text)
    
    def _detect_language(self, text: str) -> str:
        """Détecte la langue avec amélioration continue"""
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        
        # Vérifier aussi les mots-clés connus
        hebrew_keywords = ["מורה", "כיתה", "שיעור", "לא יכול", "שעה"]
        french_keywords = ["professeur", "classe", "cours", "pas", "heure"]
        
        hebrew_score = hebrew_chars + sum(2 for kw in hebrew_keywords if kw in text)
        french_score = sum(2 for kw in french_keywords if kw in text.lower())
        
        return "he" if hebrew_score > french_score else "fr"
    
    def _check_learned_patterns(self, text: str) -> Optional[Dict]:
        """Vérifie si on a déjà vu un pattern similaire"""
        text_lower = text.lower().strip()
        
        # Recherche exacte d'abord
        for pattern in self.learned_patterns:
            if pattern["text_normalized"] == text_lower:
                pattern["confidence"] = 1.0
                return pattern
        
        # Recherche par similarité (dans le futur : ML embedding)
        best_match = None
        best_score = 0
        
        for pattern in self.learned_patterns:
            score = self._calculate_similarity(text_lower, pattern["text_normalized"])
            if score > best_score and score > 0.85:
                best_score = score
                best_match = pattern
        
        if best_match:
            best_match["confidence"] = best_score
            return best_match
        
        return None
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcule la similarité entre deux textes"""
        # Version simple - dans 5 mois : embeddings vectoriels
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _enrich_with_context(self, constraint_data: Dict, original_text: str) -> Dict:
        """Enrichit avec le contexte et les règles métier"""
        # Exemple : si on parle de תפילה, on sait que c'est le matin
        if "תפילה" in original_text or "prière" in original_text.lower():
            if "time" not in constraint_data.get("data", {}):
                constraint_data.setdefault("data", {})["start"] = "08:00"
                constraint_data["data"]["end"] = "08:30"
            if "days" not in constraint_data.get("data", {}):
                constraint_data["data"]["days"] = [0,1,2,3,4]  # Pas le vendredi après-midi
        if any(x in original_text.lower() for x in ["חובה", "doit", "obligatoire", "מחייב"]):
            constraint_data["priority"] = "HARD"
        elif any(x in original_text.lower() for x in ["מועדף", "préféré", "préférence", "רצוי"]):
            constraint_data["priority"] = "SOFT"

        # Si vendredi mentionné, rappeler que c'est court
        if "vendredi" in original_text.lower() or "שישי" in original_text:
            constraint_data.setdefault("metadata", {})["friday_short"] = True
            
        return constraint_data
    
    def _save_parse_attempt(self, text: str, result: Dict, language: str):
        """Sauvegarde pour apprentissage futur"""
        attempt = {
            "timestamp": datetime.now().isoformat(),
            "text": text,
            "text_normalized": text.lower().strip(),
            "language": language,
            "result": result,
            "success": result.get("confidence", 0) > 0.7
        }
        
        # Ajouter à la base de connaissances
        self.knowledge_base.setdefault("parse_history", []).append(attempt)
        
        # Sauvegarder périodiquement (async en production)
        if len(self.knowledge_base["parse_history"]) % 10 == 0:
            self._persist_knowledge()
    
    def _persist_knowledge(self):
        """Persiste la base de connaissances"""
        try:
            import os
            os.makedirs('knowledge', exist_ok=True)
            
            with open('knowledge/constraint_patterns.json', 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
                
            # Extraire et sauvegarder les patterns réussis
            successful = [p for p in self.knowledge_base.get("parse_history", []) if p["success"]]
            if successful:
                self.learned_patterns.extend([{
                    "text_normalized": p["text_normalized"],
                    "language": p["language"],
                    "type": p["result"].get("type"),
                    "data": p["result"].get("data"),
                    "entity": p["result"].get("entity"),
                    "use_count": 1
                } for p in successful[-5:]])  # Derniers 5 succès
                
                with open('knowledge/learned_patterns.json', 'w', encoding='utf-8') as f:
                    json.dump(self.learned_patterns, f, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            logger.error(f"Erreur persistance knowledge: {e}")
    
    def learn_from_correction(self, original_text: str, corrected_constraint: Dict):
        """Apprend d'une correction utilisateur"""
        # Ajouter aux patterns appris avec haute priorité
        self.learned_patterns.insert(0, {
            "text_normalized": original_text.lower().strip(),
            "language": self._detect_language(original_text),
            "type": corrected_constraint.get("type"),
            "data": corrected_constraint.get("data"),
            "entity": corrected_constraint.get("entity"),
            "confidence": 1.0,
            "source": "user_correction",
            "use_count": 0
        })
        
        # Sauvegarder immédiatement
        self._persist_knowledge()
        
        logger.info(f"Appris nouvelle correction: {original_text[:50]}...")
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques d'apprentissage"""
        history = self.knowledge_base.get("parse_history", [])
        return {
            "total_parses": len(history),
            "successful_parses": sum(1 for p in history if p["success"]),
            "learned_patterns": len(self.learned_patterns),
            "knowledge_entries": len(self.knowledge_base),
            "success_rate": sum(1 for p in history if p["success"]) / max(1, len(history)),
            "languages": {
                "hebrew": sum(1 for p in history if p["language"] == "he"),
                "french": sum(1 for p in history if p["language"] == "fr")
            }
        }
    
    # --- Méthodes existantes adaptées ---
    
    def _normalize_text(self, text: str, language: str) -> str:
        """Normalise le texte selon la langue"""
        text = text.strip().lower()
        
        # Utiliser les mappings enrichis
        if language == "he":
            for heb, mapped in self.hebrew_mappings.items():
                text = text.replace(heb, str(mapped))
        
        # Appliquer les alias d'entités appris
        for entity, aliases in self.knowledge_base.get("entity_aliases", {}).items():
            for alias in aliases:
                if alias in text:
                    text = text.replace(alias, entity)
        
        return text
    
    def _extract_constraint(self, text: str, language: str) -> Dict[str, Any]:
        """Extraction améliorée avec patterns dynamiques"""
        # Patterns de base + patterns appris
        patterns = self._get_all_patterns()
        
        for constraint_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return self._build_constraint_from_match(
                        constraint_type, match, text, language
                    )
        
        # Fallback intelligent
        return self._intelligent_fallback(text, language)
    
    def _intelligent_fallback(self, text: str, language: str) -> Dict[str, Any]:
        """Fallback intelligent qui essaie toujours de comprendre"""
        # Extraire toutes les entités possibles
        entities = self._extract_all_entities(text)
        numbers = re.findall(r'\d+', text)
        
        # Deviner le type basé sur les mots-clés
        guessed_type = self._guess_constraint_type(text, language)
        
        return {
            "type": guessed_type,
            "entity": entities[0] if entities else "unknown",
            "data": {
                "raw_text": text,
                "extracted_numbers": numbers,
                "extracted_entities": entities
            },
            "confidence": 0.4,
            "needs_clarification": True
        }
    
    def _extract_all_entities(self, text: str) -> List[str]:
        """Extrait toutes les entités possibles du texte"""
        entities = []
        
        # Noms propres (majuscules)
        entities.extend(re.findall(r'\b[A-Z][a-z]+\b', text))
        
        # Patterns de classes
        entities.extend(re.findall(r'\b(?:classe|כיתה)\s*(\S+)', text))
        
        # Matières connues
        for subject_key, subject_aliases in self.knowledge_base.get("entity_aliases", {}).items():
            if any(alias in text for alias in subject_aliases):
                entities.append(subject_key)
        
        return list(set(entities))  # Dédupliquer
    
    def _build_constraint_from_match(self, constraint_type: str, match: re.Match, 
                                   full_text: str, language: str) -> Dict[str, Any]:
        """Construction améliorée avec contexte riche"""
        groups = match.groups()
        
        # Base constraint
        constraint = {
            "type": constraint_type,
            "data": {},
            "confidence": 0.7,
            "metadata": {
                "parsed_at": datetime.now().isoformat(),
                "language": language,
                "match_groups": groups
            }
        }
        
        # Logique spécifique par type (comme avant, mais enrichie)
        if constraint_type == "morning_prayer":
            context = self.knowledge_base.get("context_rules", {}).get("תפילה", {})
            constraint.update({
                "entity": "all" if any(w in full_text for w in ["כל", "tous", "all"]) else "unknown",
                "data": {
                    "start": context.get("default_time", "08:00"),
                    "duration": context.get("typical_duration", 30),
                    "days": context.get("default_days", [0,1,2,3,4]),
                    "subject": "prayer"
                },
                "priority": "HARD",
                "confidence": 0.95
            })
        
        # ... autres types avec enrichissement contextuel ...
        
        return constraint
    
    def _build_constraint_input(self, constraint_data: Dict, original_text: str) -> ConstraintInput:
        """Construit le ConstraintInput final"""
        # Mapper les types
        type_map = {
            "morning_prayer": ConstraintType.TIME_PREFERENCE,
            "teacher_availability": ConstraintType.TEACHER_AVAILABILITY,
            "subject_limit": ConstraintType.SUBJECT_LIMIT,
            "consecutive_hours_limit": ConstraintType.CONSECUTIVE_HOURS_LIMIT,
        }
        
        constraint_type = type_map.get(
            constraint_data.get("type", "custom"),
            ConstraintType.CUSTOM
        )
        
        # Créer l'objet validé
        return ConstraintInput(
            type=constraint_type,
            entity=constraint_data.get("entity", "unknown"),
            data=constraint_data.get("data", {}),
            priority=ConstraintPriority.MEDIUM,
            metadata=constraint_data.get("metadata", {}),
            original_text=original_text,
            confidence=constraint_data.get("confidence", 0.5),
            requires_clarification=constraint_data.get("needs_clarification", False),
            clarification_questions=self._generate_clarification_questions(
                constraint_data, 
                constraint_data.get("metadata", {}).get("language", "fr")
            )
        )
    
    def _generate_clarification_questions(self, constraint: Dict, language: str) -> List[str]:
        """Génère des questions intelligentes basées sur l'historique"""
        questions = []
        
        # Questions basées sur les patterns d'échecs précédents
        similar_failures = self._find_similar_failures(constraint)
        if similar_failures:
            # Poser les questions qui ont résolu des cas similaires
            for failure in similar_failures[:2]:
                if "resolved_by_question" in failure:
                    questions.append(failure["resolved_by_question"])
        # Si la priorité n'est pas précisée
        if "priority" not in constraint or not constraint["priority"]:
            if language == "he":
                questions.append("האם זה אילוץ מחייב, מועדף או גמיש?")
            else:
                questions.append("Est-ce une contrainte stricte, une préférence, ou souple ?")

        # Questions standards si pas d'historique
        if not questions:
            if language == "he":
                if "entity" not in constraint or constraint["entity"] == "unknown":
                    questions.append("למי זה מתייחס? (מורה/כיתה/כולם)")
                if "days" not in constraint.get("data", {}):
                    questions.append("באילו ימים?")
            else:
                if "entity" not in constraint or constraint["entity"] == "unknown":
                    questions.append("À qui cela s'applique-t-il ? (professeur/classe/tous)")
                if "days" not in constraint.get("data", {}):
                    questions.append("Quels jours ?")
        
        return questions
    
    def _find_similar_failures(self, constraint: Dict) -> List[Dict]:
        """Trouve des échecs similaires dans l'historique"""
        # Dans le futur : utiliser des embeddings pour la similarité sémantique
        similar = []
        
        for hist in self.knowledge_base.get("parse_history", []):
            if not hist["success"] and hist["result"].get("type") == constraint.get("type"):
                similar.append(hist)
        
        return similar[:5]  # Top 5 plus similaires
    
    def _get_all_patterns(self) -> Dict[str, List[str]]:
        """Retourne tous les patterns (base + appris)"""
        # Patterns de base
        base_patterns = {
            "morning_prayer": [
                r"(תפילה|prayer|prière).*(\d{1,2}:\d{2}|שעה ראשונה|première heure|08:00)",
                r"(כל|tous|all).*(כיתות|classes).*(תפילה|prayer|prière)"
            ],
            "teacher_availability": [
                r"(מורה|prof|professeur|teacher)\s+(\w+).*(לא יכול|ne peut pas|cannot|unavailable)",
                r"(\w+).*(לא זמין|pas disponible|not available).*(יום|jour|day)?\s*(\d+)"
            ],
            "subject_limit": [
                r"(לא יותר מ|pas plus de|maximum)\s*(\d+).*(שעות|heures|hours).*(ביום|par jour|per day)",
                r"(מקסימום|maximum)\s*(\d+).*(שעות|heures).*(מתמטיקה|math|mathématiques|ספורט|sport)"
            ]
        }
        
        # Ajouter les patterns appris
        for pattern in self.learned_patterns:
            pattern_type = pattern.get("type", "custom")
            if pattern_type not in base_patterns:
                base_patterns[pattern_type] = []
            
            # Créer un regex à partir du texte appris
            learned_regex = re.escape(pattern["text_normalized"])
            base_patterns[pattern_type].append(learned_regex)
        
        return base_patterns
    
    def _guess_constraint_type(self, text: str, language: str) -> str:
        """Devine le type de contrainte basé sur les mots-clés"""
        text_lower = text.lower()
        
        # Mots-clés par type
        type_keywords = {
            "teacher_availability": ["מורה", "prof", "professeur", "teacher", "disponible", "זמין"],
            "time_preference": ["matin", "בוקר", "après-midi", "אחר הצהריים", "heure", "שעה"],
            "subject_limit": ["maximum", "מקסימום", "limit", "הגבלה", "heures", "שעות"],
            "consecutive_hours_limit": ["consécutif", "רצוף", "suite", "רצף"],
        }
        
        # Scorer chaque type
        scores = {}
        for ctype, keywords in type_keywords.items():
            scores[ctype] = sum(1 for kw in keywords if kw in text_lower)
        
        # Retourner le type avec le score le plus élevé
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 0:
                return best_type
        
        return "custom"


# Fonction helper pour la compatibilité
def extract_constraint(msg: str, language: str = "auto") -> ConstraintInput:
    """Fonction principale d'extraction avec le nouveau parser intelligent"""
    parser = NaturalLanguageParser()
    return parser.parse(msg, language)


# Instance globale pour réutilisation
natural_language_parser = NaturalLanguageParser()
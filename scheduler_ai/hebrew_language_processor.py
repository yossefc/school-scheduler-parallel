# hebrew_language_processor.py - Traitement spécialisé de l'hébreu pour l'agent conseiller
import re
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HebrewLanguageProcessor:
    """Processeur de langage naturel spécialisé pour l'hébreu dans le contexte scolaire"""
    
    def __init__(self):
        # Dictionnaires hébreu-français pour la compréhension
        self.actions_hebrew = {
            # Verbes d'action
            "לזוז": "move",
            "להזיז": "move", 
            "לעבור": "move",
            "לשנות": "change",
            "להחליף": "swap",
            "להחליק": "swap",
            "לתקן": "fix",
            "לסדר": "organize",
            "לבטל": "cancel",
            "למחוק": "delete",
            "להוסיף": "add",
            "ליצור": "create",
            "לאזן": "balance",
            "לשפר": "improve",
            "לייעל": "optimize",
            
            # Expressions communes
            "אני רוצה": "I want",
            "אפשר": "can you",
            "תוכל": "can you", 
            "בבקשה": "please",
            "עזור לי": "help me",
            "איך": "how",
            "למה": "why",
            "מתי": "when",
            "איפה": "where",
        }
        
        self.schedule_terms_hebrew = {
            # Termes d'emploi du temps
            "מערכת שעות": "schedule",
            "שיעור": "lesson",
            "שיעורים": "lessons",
            "כיתה": "class",
            "כיתות": "classes", 
            "מורה": "teacher",
            "מורים": "teachers",
            "מקצוע": "subject",
            "מקצועות": "subjects",
            "יום": "day",
            "ימים": "days",
            "שעה": "hour",
            "שעות": "hours",
            "זמן": "time",
            "פריודה": "period",
            "הפסקה": "break",
            "חופש": "free",
            "ריק": "empty",
            "חור": "gap",
            "חורים": "gaps",
            "בעיה": "problem",
            "בעיות": "problems",
            "קונפליקט": "conflict",
            "התנגשות": "conflict",
            "עומס": "load",
            "עומסים": "loads",
        }
        
        self.days_hebrew = {
            "ראשון": 0,
            "יום ראשון": 0,
            "א'": 0,
            "שני": 1, 
            "יום שני": 1,
            "ב'": 1,
            "שלישי": 2,
            "יום שלישי": 2,
            "ג'": 2,
            "רביעי": 3,
            "יום רביעי": 3,
            "ד'": 3,
            "חמישי": 4,
            "יום חמישי": 4,
            "ה'": 4,
            "שישי": 5,
            "יום שישי": 5,
            "ו'": 5,
        }
        
        self.subjects_hebrew = {
            "מתמטיקה": "mathematics",
            "מתמטיקות": "mathematics", 
            "מתמ": "mathematics",
            "אנגלית": "english",
            "אנגלי": "english",
            "תנך": "bible",
            "תנ\"ך": "bible",
            "מקרא": "bible",
            "תלמוד": "talmud",
            "גמרא": "talmud",
            "משנה": "talmud",
            "מדעים": "science",
            "מדע": "science",
            "פיזיקה": "physics",
            "כימיה": "chemistry",
            "ביולוגיה": "biology",
            "היסטוריה": "history",
            "הסטוריה": "history",
            "ארץ ישראל": "geography",
            "גיאוגרפיה": "geography",
            "אזרחות": "civics",
            "חינוך": "education",
            "ספורט": "sports",
            "כדורגל": "sports",
            "כדורסל": "sports",
            "אומנות": "art",
            "מוזיקה": "music",
            "הבעה": "expression",
            "שיח": "discussion",
        }
        
        self.time_expressions_hebrew = {
            "בבוקר": "morning",
            "בצהריים": "noon", 
            "אחר הצהריים": "afternoon",
            "בערב": "evening",
            "מוקדם": "early",
            "מאוחר": "late",
            "לפני": "before",
            "אחרי": "after",
            "במהלך": "during",
            "ב-8": "at_8",
            "ב-9": "at_9",
            "ב-10": "at_10",
            "בשעה 8": "at_8",
            "בשעה 9": "at_9",
            "בשעה 10": "at_10",
        }
        
        self.class_pattern = re.compile(r'[זחטיא]-[0-9]')
        self.grade_names = {
            "ז": "7th_grade",
            "ח": "8th_grade", 
            "ט": "9th_grade",
            "י": "10th_grade",
            "יא": "11th_grade",
            "יב": "12th_grade"
        }

    def analyze_hebrew_text(self, text: str) -> Dict[str, any]:
        """Analyse complète d'un texte en hébreu pour extraction des intentions"""
        logger.info(f"Analyse du texte hébreu: {text}")
        
        # Nettoyer et normaliser le texte
        cleaned_text = self._normalize_hebrew_text(text)
        
        # Extraire les composants
        analysis = {
            "original_text": text,
            "normalized_text": cleaned_text,
            "detected_language": "hebrew",
            "actions": self._extract_actions(cleaned_text),
            "entities": {
                "classes": self._extract_classes(cleaned_text),
                "subjects": self._extract_subjects(cleaned_text),
                "teachers": self._extract_teachers(cleaned_text),
                "days": self._extract_days(cleaned_text),
                "times": self._extract_times(cleaned_text)
            },
            "problems_mentioned": self._extract_problems(cleaned_text),
            "preferences_indicators": self._extract_preferences_indicators(cleaned_text),
            "urgency_level": self._assess_urgency(cleaned_text),
            "politeness_level": self._assess_politeness(cleaned_text),
            "confidence_score": 0.0
        }
        
        # Déterminer l'intention principale
        analysis["main_intent"] = self._determine_main_intent(analysis)
        
        # Calculer le score de confiance
        analysis["confidence_score"] = self._calculate_confidence(analysis)
        
        # Traduire en contexte compréhensible
        analysis["translated_context"] = self._translate_to_context(analysis)
        
        logger.info(f"Analyse terminée. Intention: {analysis['main_intent']}, Confiance: {analysis['confidence_score']:.2f}")
        
        return analysis

    def _normalize_hebrew_text(self, text: str) -> str:
        """Normalise le texte hébreu (supprime nikud, normalise les espaces, etc.)"""
        # Supprimer les signes de ponctuation hébraïques (nikud)
        nikud_pattern = re.compile(r'[\u0591-\u05C7]')
        text = nikud_pattern.sub('', text)
        
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normaliser certaines lettres finales
        text = text.replace('ך', 'כ').replace('ם', 'מ').replace('ן', 'נ').replace('ף', 'פ').replace('ץ', 'צ')
        
        return text.lower()

    def _extract_actions(self, text: str) -> List[str]:
        """Extrait les actions demandées depuis le texte hébreu"""
        actions = []
        
        for hebrew_action, english_action in self.actions_hebrew.items():
            if hebrew_action in text:
                actions.append(english_action)
        
        # Patterns spéciaux pour les actions complexes
        if any(word in text for word in ["חור", "חורים", "ריק", "רווח"]):
            actions.append("fix_gaps")
        
        if any(word in text for word in ["התנגשות", "קונפליקט", "חפיפה"]):
            actions.append("fix_conflicts")
        
        if any(word in text for word in ["לאזן", "איזון", "שווה"]):
            actions.append("balance")
        
        return list(set(actions))  # Supprimer les doublons

    def _extract_classes(self, text: str) -> List[str]:
        """Extrait les noms de classes depuis le texte"""
        classes = []
        
        # Pattern principal pour les classes (ז-1, ח-2, etc.)
        class_matches = self.class_pattern.findall(text)
        classes.extend(class_matches)
        
        # Rechercher des mentions plus générales
        for grade_letter, grade_name in self.grade_names.items():
            if grade_letter in text and not any(grade_letter in c for c in classes):
                # Mention générale d'une classe sans numéro spécifique
                classes.append(f"{grade_letter}_general")
        
        return classes

    def _extract_subjects(self, text: str) -> List[str]:
        """Extrait les matières mentionnées"""
        subjects = []
        
        for hebrew_subject, english_subject in self.subjects_hebrew.items():
            if hebrew_subject in text:
                subjects.append(english_subject)
        
        return subjects

    def _extract_teachers(self, text: str) -> List[str]:
        """Extrait les noms de professeurs (détection basique)"""
        teachers = []
        
        # Pattern pour détecter des noms hébreux (très basique)
        # Dans un vrai système, vous auriez une liste de noms de professeurs
        teacher_indicators = ["מורה", "המורה", "הגב'", "האדון", "גב'", "מר"]
        
        for indicator in teacher_indicators:
            if indicator in text:
                # Dans la vraie implémentation, on extrairait le nom après l'indicateur
                teachers.append("teacher_mentioned")
        
        return teachers

    def _extract_days(self, text: str) -> List[int]:
        """Extrait les jours de la semaine mentionnés"""
        days = []
        
        for hebrew_day, day_number in self.days_hebrew.items():
            if hebrew_day in text:
                days.append(day_number)
        
        return days

    def _extract_times(self, text: str) -> List[str]:
        """Extrait les références temporelles"""
        times = []
        
        for hebrew_time, english_time in self.time_expressions_hebrew.items():
            if hebrew_time in text:
                times.append(english_time)
        
        # Pattern pour les heures spécifiques
        hour_pattern = re.compile(r'(\d{1,2}):(\d{2})')
        hour_matches = hour_pattern.findall(text)
        for hour, minute in hour_matches:
            times.append(f"{hour}:{minute}")
        
        return times

    def _extract_problems(self, text: str) -> List[str]:
        """Identifie les problèmes mentionnés"""
        problems = []
        
        problem_indicators = {
            "חור": "gap",
            "חורים": "gaps", 
            "ריק": "empty_slot",
            "התנגשות": "conflict",
            "קונפליקט": "conflict",
            "בעיה": "problem",
            "בעיות": "problems",
            "עומס": "overload",
            "עייפות": "fatigue",
            "לחץ": "pressure"
        }
        
        for hebrew_problem, english_problem in problem_indicators.items():
            if hebrew_problem in text:
                problems.append(english_problem)
        
        return problems

    def _extract_preferences_indicators(self, text: str) -> List[str]:
        """Identifie les indicateurs de préférences personnelles"""
        preferences = []
        
        preference_indicators = {
            "אני אוהב": "preference",
            "אני מעדיף": "preference", 
            "כדאי": "suggestion",
            "עדיף": "better",
            "חשוב לי": "important",
            "אני צריך": "need",
            "חובה": "must",
            "אסור": "forbidden",
            "אל תשים": "dont_put",
            "תמיד": "always",
            "לעולם לא": "never",
            "בדרך כלל": "usually"
        }
        
        for hebrew_pref, english_pref in preference_indicators.items():
            if hebrew_pref in text:
                preferences.append(english_pref)
        
        return preferences

    def _assess_urgency(self, text: str) -> str:
        """Évalue le niveau d'urgence de la demande"""
        urgent_words = ["דחוף", "מיידי", "חשוב", "מהר", "עכשיו", "היום", "בבקשה מיד"]
        medium_words = ["כדאי", "עדיף", "אם אפשר", "בזמן הקרוב"]
        
        if any(word in text for word in urgent_words):
            return "high"
        elif any(word in text for word in medium_words):
            return "medium"
        else:
            return "low"

    def _assess_politeness(self, text: str) -> str:
        """Évalue le niveau de politesse"""
        polite_words = ["בבקשה", "אודה", "תודה", "אם אפשר", "האם תוכל", "סליחה"]
        
        if any(word in text for word in polite_words):
            return "high"
        elif "?" in text or text.endswith("?"):
            return "medium" 
        else:
            return "neutral"

    def _determine_main_intent(self, analysis: Dict) -> str:
        """Détermine l'intention principale basée sur l'analyse"""
        actions = analysis["actions"]
        problems = analysis["problems_mentioned"]
        
        if "fix_gaps" in actions or "gaps" in problems:
            return "fix_schedule_gaps"
        elif "fix_conflicts" in actions or "conflict" in problems:
            return "resolve_conflicts" 
        elif "move" in actions:
            return "move_lessons"
        elif "swap" in actions:
            return "swap_lessons"
        elif "balance" in actions:
            return "balance_workload"
        elif "add" in actions:
            return "add_lessons"
        elif "delete" in actions or "cancel" in actions:
            return "remove_lessons"
        elif analysis["preferences_indicators"]:
            return "set_preferences"
        else:
            return "general_inquiry"

    def _calculate_confidence(self, analysis: Dict) -> float:
        """Calcule un score de confiance pour l'analyse"""
        confidence = 0.5  # Base
        
        # Bonus pour actions claires
        if analysis["actions"]:
            confidence += 0.2 * len(analysis["actions"])
        
        # Bonus pour entités identifiées
        entity_count = sum(len(entities) for entities in analysis["entities"].values() if entities)
        confidence += 0.1 * min(entity_count, 3)
        
        # Bonus pour intention claire
        if analysis["main_intent"] != "general_inquiry":
            confidence += 0.2
        
        # Malus pour ambiguïté
        if len(analysis["actions"]) > 3:
            confidence -= 0.1
        
        return min(confidence, 1.0)

    def _translate_to_context(self, analysis: Dict) -> Dict[str, any]:
        """Traduit l'analyse en contexte compréhensible pour l'agent"""
        return {
            "user_wants_to": analysis["actions"],
            "mentioned_entities": analysis["entities"],
            "problems_to_solve": analysis["problems_mentioned"],
            "user_preferences": analysis["preferences_indicators"],
            "urgency": analysis["urgency_level"],
            "politeness": analysis["politeness_level"],
            "main_goal": analysis["main_intent"]
        }

    def generate_hebrew_response(self, english_response: str, context: Dict = None) -> str:
        """Génère une réponse en hébreu basée sur une réponse anglaise"""
        # Mapping basique anglais -> hébreu pour les réponses
        hebrew_translations = {
            "Hello": "שלום",
            "I understand": "אני מבין",
            "I can help": "אני יכול לעזור",
            "Let me analyze": "תן לי לנתח",
            "I suggest": "אני מציע",
            "The schedule": "מערכת השעות",
            "classes": "כיתות",
            "teachers": "מורים", 
            "lessons": "שיעורים",
            "Do you want": "האם אתה רוצה",
            "Yes": "כן",
            "No": "לא",
            "Thank you": "תודה"
        }
        
        hebrew_response = english_response
        for english, hebrew in hebrew_translations.items():
            hebrew_response = hebrew_response.replace(english, hebrew)
        
        return hebrew_response

# Fonctions utilitaires
def create_hebrew_processor() -> HebrewLanguageProcessor:
    """Factory function pour créer le processeur hébreu"""
    return HebrewLanguageProcessor()

def analyze_hebrew_input(text: str) -> Dict[str, any]:
    """Fonction rapide pour analyser un texte hébreu"""
    processor = HebrewLanguageProcessor()
    return processor.analyze_hebrew_text(text)
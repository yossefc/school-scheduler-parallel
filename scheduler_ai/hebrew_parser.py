"""
hebrew_parser.py - Module d'analyse amélioré pour l'hébreu
À ajouter dans scheduler_ai/
"""

import re
from typing import Dict, List, Optional, Tuple

class HebrewConstraintParser:
    """Parser spécialisé pour les contraintes en hébreu"""
    
    def __init__(self):
        # Dictionnaire de mots-clés hébreux
        self.hebrew_keywords = {
            # Entités
            'teacher': ['מורה', 'מורים', 'מלמד', 'מלמדת', 'המורה'],
            'class': ['כיתה', 'כיתות', 'תלמידים', 'כתה'],
            'room': ['חדר', 'אולם', 'כיתת'],
            
            # Temps
            'hour': ['שעה', 'שעות'],
            'first': ['ראשונה', 'ראשון', 'הראשונה'],
            'last': ['אחרונה', 'אחרון'],
            'morning': ['בוקר', 'בבוקר'],
            'afternoon': ['צהריים', 'אחר הצהריים'],
            
            # Jours
            'sunday': ['ראשון', 'יום ראשון'],
            'monday': ['שני', 'יום שני'],
            'tuesday': ['שלישי', 'יום שלישי'],
            'wednesday': ['רביעי', 'יום רביעי'],
            'thursday': ['חמישי', 'יום חמישי'],
            'friday': ['שישי', 'יום שישי'],
            
            # Actions/Contraintes
            'prayer': ['תפילה', 'תפילת', 'תפלה', 'שחרית', 'מנחה'],
            'no': ['אין', 'לא', 'ללא', 'בלי'],
            'only': ['רק', 'אך', 'בלבד'],
            'need': ['צריך', 'צריכה', 'צריכים', 'חייב'],
            'every': ['כל', 'כול'],
            'other': ['אחר', 'אחרת', 'אחרים'],
            'lesson': ['שיעור', 'שעור', 'שיעורים'],
            'except': ['חוץ', 'מלבד', 'פרט'],
            
            # Quantité
            'one': ['אחד', 'אחת'],
            'two': ['שני', 'שתי', 'שניים', 'שתיים'],
            'three': ['שלוש', 'שלושה'],
        }
        
        # Patterns de détection
        self.patterns = {
            'morning_prayer': [
                r'תפילה.*שעה.*ראשונה',
                r'שעה.*ראשונה.*תפילה',
                r'תפילת.*בוקר',
                r'שחרית'
            ],
            'no_other_lessons': [
                r'אין.*שיעור.*אחר',
                r'לא.*שיעורים.*אחרים',
                r'רק.*תפילה'
            ],
            'one_teacher_per_class': [
                r'מורה.*אחד.*כיתה',
                r'מורה.*לכל.*כיתה',
                r'מורה.*בכל.*כיתה'
            ]
        }
    
    def parse(self, text: str) -> Dict:
        """Analyse une contrainte en hébreu"""
        result = {
            'type': None,
            'entity': 'Global',
            'data': {},
            'confidence': 0.0,
            'detected_elements': []
        }
        
        # Nettoyer le texte
        text = text.strip()
        
        # Détecter le type principal
        if self._contains_keywords(text, ['prayer']):
            result['type'] = 'morning_prayer'
            result['confidence'] += 0.3
            result['detected_elements'].append('prière')
            
            # Détails spécifiques
            if self._contains_keywords(text, ['first']) and self._contains_keywords(text, ['hour']):
                result['data']['time_slot'] = '08:00-08:30'
                result['data']['period'] = 1
                result['confidence'] += 0.2
                result['detected_elements'].append('première heure')
            
            # Pas d'autres cours
            if self._matches_pattern(text, 'no_other_lessons'):
                result['data']['exclusive'] = True
                result['data']['block_other_subjects'] = True
                result['confidence'] += 0.2
                result['detected_elements'].append('exclusif - pas d\'autres cours')
            
            # Un prof par classe
            if self._matches_pattern(text, 'one_teacher_per_class'):
                result['data']['one_teacher_per_class'] = True
                result['confidence'] += 0.1
                result['detected_elements'].append('un enseignant par classe')
            
            # Appliquer à toutes les classes
            if self._contains_keywords(text, ['every']) and self._contains_keywords(text, ['class']):
                result['data']['mandatory_for'] = ['all']
                result['entity'] = 'Toutes les classes'
                result['confidence'] += 0.2
                result['detected_elements'].append('toutes les classes')
        
        # Si on n'a pas trouvé de type spécifique
        if not result['type']:
            # Chercher d'autres indices
            if self._contains_keywords(text, ['teacher']):
                result['type'] = 'teacher_availability'
                result['entity'] = self._extract_teacher_name(text)
                result['confidence'] = 0.5
            elif self._contains_keywords(text, ['class']):
                result['type'] = 'class_preference'
                result['entity'] = self._extract_class_name(text)
                result['confidence'] = 0.5
            else:
                result['type'] = 'time_preference'
                result['confidence'] = 0.3
        
        # Ajouter le texte original
        result['data']['original_hebrew'] = text
        
        # Créer une description en français
        result['data']['description_fr'] = self._generate_french_description(result, text)
        
        return result
    
    def _contains_keywords(self, text: str, keyword_types: List[str]) -> bool:
        """Vérifie si le texte contient des mots-clés d'un certain type"""
        for keyword_type in keyword_types:
            if keyword_type in self.hebrew_keywords:
                for word in self.hebrew_keywords[keyword_type]:
                    if word in text:
                        return True
        return False
    
    def _matches_pattern(self, text: str, pattern_name: str) -> bool:
        """Vérifie si le texte correspond à un pattern"""
        if pattern_name in self.patterns:
            for pattern in self.patterns[pattern_name]:
                if re.search(pattern, text):
                    return True
        return False
    
    def _extract_teacher_name(self, text: str) -> str:
        """Extrait le nom d'un enseignant du texte"""
        # Pattern pour trouver un nom après "מורה"
        pattern = r'(?:מורה|המורה)\s+([א-ת]+(?:\s+[א-ת]+)?)'
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return 'Non spécifié'
    
    def _extract_class_name(self, text: str) -> str:
        """Extrait le nom d'une classe du texte"""
        # Pattern pour trouver une classe (ex: כיתה א, כיתה 9)
        pattern = r'כיתה\s+([א-ת0-9]+)'
        match = re.search(pattern, text)
        if match:
            return f"Classe {match.group(1)}"
        return 'Toutes les classes'
    
    def _generate_french_description(self, result: Dict, original_text: str) -> str:
        """Génère une description en français de la contrainte détectée"""
        desc_parts = []
        
        if result['type'] == 'morning_prayer':
            desc = "Prière du matin"
            if result['data'].get('time_slot'):
                desc += f" de {result['data']['time_slot']}"
            if result['data'].get('exclusive'):
                desc += " (aucun autre cours à cette heure)"
            if result['data'].get('one_teacher_per_class'):
                desc += " avec un enseignant par classe"
            desc_parts.append(desc)
        
        if result['detected_elements']:
            desc_parts.append(f"Éléments détectés: {', '.join(result['detected_elements'])}")
        
        return " | ".join(desc_parts) if desc_parts else "Contrainte en hébreu"


# ============================================
# MIDDLEWARE AMÉLIORÉ
# ============================================

class ImprovedClarificationMiddleware:
    """Middleware amélioré avec support hébreu"""
    
    def __init__(self):
        self.sessions = {}
        self.hebrew_parser = HebrewConstraintParser()
        self.max_clarification_rounds = 2  # Pas de tentatives, mais des rounds
    
    def analyze_constraint(self, text: str, session_id: str, context: Dict = None) -> Dict:
        """Analyse une contrainte avec support multilingue"""
        
        # Initialiser la session
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'clarification_round': 0,
                'history': [],
                'original_text': text,
                'language': self._detect_language(text)
            }
        
        session = self.sessions[session_id]
        
        # Détecter si c'est une réponse à une clarification
        is_clarification_response = context and context.get('is_clarification_response', False)
        
        # Si c'est une nouvelle contrainte (pas une clarification), réinitialiser
        if not is_clarification_response and text != session.get('original_text'):
            session['clarification_round'] = 0
            session['original_text'] = text
            session['language'] = self._detect_language(text)
        
        # Analyser selon la langue
        if session['language'] == 'hebrew':
            result = self._analyze_hebrew(text, session, context)
        elif session['language'] == 'french':
            result = self._analyze_french(text, session, context)
        else:
            result = self._analyze_mixed(text, session, context)
        
        # Gérer les clarifications
        if result.get('needs_clarification'):
            session['clarification_round'] += 1
            
            if session['clarification_round'] > self.max_clarification_rounds:
                # Forcer une interprétation avec les infos disponibles
                return self._force_interpretation(text, session)
            
            return {
                'status': 'clarification_needed',
                'clarification_questions': result.get('questions', [
                    "Pouvez-vous préciser l'heure exacte ?",
                    "Cette contrainte s'applique-t-elle à toutes les classes ?"
                ])
            }
        
        # Succès
        return {
            'status': 'success',
            'constraint': result['constraint']
        }
    
    def _detect_language(self, text: str) -> str:
        """Détecte la langue du texte"""
        hebrew_chars = re.findall(r'[א-ת]', text)
        total_chars = len(re.findall(r'\w', text))
        
        if not total_chars:
            return 'unknown'
        
        hebrew_ratio = len(hebrew_chars) / total_chars
        
        if hebrew_ratio > 0.5:
            return 'hebrew'
        elif hebrew_ratio > 0:
            return 'mixed'
        else:
            return 'french'
    
    def _analyze_hebrew(self, text: str, session: Dict, context: Dict) -> Dict:
        """Analyse spécifique pour l'hébreu"""
        parsed = self.hebrew_parser.parse(text)
        
        # Construire la contrainte
        constraint = {
            'type': parsed['type'],
            'entity': parsed['entity'],
            'data': parsed['data'],
            'confidence': parsed['confidence']
        }
        
        # Déterminer si des clarifications sont nécessaires
        needs_clarification = parsed['confidence'] < 0.6
        
        return {
            'constraint': constraint,
            'needs_clarification': needs_clarification,
            'questions': self._generate_clarification_questions(parsed) if needs_clarification else []
        }
    
    def _analyze_french(self, text: str, session: Dict, context: Dict) -> Dict:
        """Analyse pour le français (comme avant)"""
        text_lower = text.lower()
        
        constraint = {
            'type': 'time_preference',
            'entity': 'Global',
            'data': {'original_text': text},
            'confidence': 0.5
        }
        
        # Détection basique
        if 'professeur' in text_lower or 'prof' in text_lower:
            constraint['type'] = 'teacher_availability'
            import re
            name_match = re.search(r'(?:professeur|prof\.?)\s+(\w+)', text, re.I)
            if name_match:
                constraint['entity'] = name_match.group(1)
                constraint['confidence'] = 0.8
        
        elif 'prière' in text_lower:
            constraint['type'] = 'morning_prayer'
            constraint['data'] = {
                'time_slot': '08:00-08:30',
                'mandatory_for': ['all']
            }
            constraint['confidence'] = 0.9
        
        needs_clarification = constraint['confidence'] < 0.6
        
        return {
            'constraint': constraint,
            'needs_clarification': needs_clarification
        }
    
    def _analyze_mixed(self, text: str, session: Dict, context: Dict) -> Dict:
        """Analyse pour texte mixte français/hébreu"""
        # Essayer les deux analyses et prendre la meilleure
        hebrew_result = self._analyze_hebrew(text, session, context)
        french_result = self._analyze_french(text, session, context)
        
        # Retourner celui avec la meilleure confiance
        if hebrew_result['constraint']['confidence'] > french_result['constraint']['confidence']:
            return hebrew_result
        else:
            return french_result
    
    def _generate_clarification_questions(self, parsed: Dict) -> List[str]:
        """Génère des questions de clarification basées sur l'analyse"""
        questions = []
        
        if parsed['entity'] == 'Global' or parsed['entity'] == 'Non spécifié':
            questions.append("Pour quelle(s) classe(s) cette contrainte s'applique-t-elle ?")
        
        if not parsed['data'].get('time_slot') and parsed['type'] == 'morning_prayer':
            questions.append("À quelle heure exactement doit avoir lieu la prière ?")
        
        if parsed['confidence'] < 0.4:
            questions.append("Pouvez-vous reformuler votre contrainte de manière plus précise ?")
        
        return questions[:2]  # Maximum 2 questions
    
    def _force_interpretation(self, text: str, session: Dict) -> Dict:
        """Force une interprétation avec les informations disponibles"""
        # Utiliser l'analyse la plus probable
        if session['language'] == 'hebrew':
            parsed = self.hebrew_parser.parse(text)
            constraint = {
                'type': parsed['type'] or 'morning_prayer',  # Par défaut pour l'hébreu
                'entity': parsed['entity'],
                'data': {
                    **parsed['data'],
                    'forced_interpretation': True,
                    'note': 'Interprétation automatique après clarifications'
                },
                'confidence': max(parsed['confidence'], 0.5)  # Au moins 50%
            }
        else:
            # Interprétation par défaut pour le français
            constraint = {
                'type': 'time_preference',
                'entity': 'Global',
                'data': {
                    'original_text': text,
                    'forced_interpretation': True
                },
                'confidence': 0.5
            }
        
        return {
            'status': 'success',
            'constraint': constraint,
            'message': 'Contrainte interprétée avec les informations disponibles'
        }
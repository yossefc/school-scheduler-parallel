from difflib import SequenceMatcher
import re
from typing import List, Tuple, Optional

class HebrewFuzzyMatcher:
    def __init__(self, teachers_db: List[Dict]):
        self.teachers = teachers_db
        self._build_nickname_map()
    
    def _build_nickname_map(self):
        """Construit une base de surnoms hébreux courants"""
        self.nickname_map = {
            # Noms complets → surnoms courants
            "יוסף": ["יוסי", "יוס", "יוסף"],
            "דוד": ["דוד", "דודי", "דדי"], 
            "משה": ["משה", "מויש", "מושק"],
            "אברהם": ["אברהם", "אברם", "אבי"],
            "יעקב": ["יעקב", "יקי", "קובי"],
            "כהן": ["כהן", "כה", "כוהן"]  # Noms de famille
        }
        
        # Créer la map inverse
        self.reverse_nicknames = {}
        for full_name, nicknames in self.nickname_map.items():
            for nick in nicknames:
                self.reverse_nicknames[nick] = full_name
    
    def find_teacher(self, input_name: str, min_confidence: float = 0.6) -> Optional[Dict]:
        """Trouve un professeur avec correspondance floue"""
        input_clean = self._normalize_hebrew(input_name)
        
        best_match = None
        best_score = 0
        
        for teacher in self.teachers:
            full_name = teacher["teacher_name"]
            
            # 1. Test exact d'abord
            if input_clean == self._normalize_hebrew(full_name):
                return {"teacher": teacher, "confidence": 1.0, "method": "exact"}
            
            # 2. Test avec surnoms
            nickname_score = self._check_nickname_match(input_clean, full_name)
            if nickname_score > best_score:
                best_score = nickname_score
                best_match = {"teacher": teacher, "confidence": nickname_score, "method": "nickname"}
            
            # 3. Test similarité phonétique
            phonetic_score = self._phonetic_similarity(input_clean, full_name)
            if phonetic_score > best_score:
                best_score = phonetic_score
                best_match = {"teacher": teacher, "confidence": phonetic_score, "method": "phonetic"}
        
        return best_match if best_score >= min_confidence else None
    
    def _normalize_hebrew(self, text: str) -> str:
        """Normalise le texte hébreu (retire nikud, espaces, etc.)"""
        # Retirer les points diacritiques (nikud)
        no_nikud = re.sub(r'[\u0591-\u05C7]', '', text)
        # Nettoyer les espaces
        return re.sub(r'\s+', ' ', no_nikud.strip())
    
    def _check_nickname_match(self, input_name: str, full_name: str) -> float:
        """Vérifie la correspondance avec les surnoms"""
        input_parts = input_name.split()
        full_parts = full_name.split()
        
        match_score = 0
        total_parts = len(input_parts)
        
        for input_part in input_parts:
            for full_part in full_parts:
                # Chercher dans la map des surnoms
                if input_part in self.nickname_map.get(full_part, []):
                    match_score += 1
                    break
                elif full_part in self.nickname_map.get(input_part, []):
                    match_score += 1
                    break
        
        return match_score / total_parts if total_parts > 0 else 0
    
    def _phonetic_similarity(self, text1: str, text2: str) -> float:
        """Calcule la similarité phonétique"""
        return SequenceMatcher(None, text1, text2).ratio()
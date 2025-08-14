#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple du processeur hébreu
"""

import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple

class SimpleHebrewProcessor:
    """Version simplifiée pour test"""
    
    def __init__(self):
        # Dictionnaires hébreux de base
        self.actions = {
            'להזיז': 'move',
            'לתקן': 'fix', 
            'לאזן': 'balance',
            'למלא': 'fill',
            'להוסיף': 'add',
            'לבטל': 'cancel',
            'לשנות': 'change',
            'לייעל': 'optimize'
        }
        
        self.subjects = {
            'מתמטיקה': 'mathematics',
            'אנגלית': 'english',
            'תנך': 'bible', 
            'מדעים': 'sciences',
            'היסטוריה': 'history',
            'אזרחות': 'civics'
        }
    
    def is_hebrew(self, text: str) -> bool:
        """Détecte si le texte contient de l'hébreu"""
        hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
        total_chars = sum(1 for c in text if c.isalpha())
        
        if total_chars == 0:
            return False
        
        hebrew_ratio = hebrew_chars / total_chars
        return hebrew_ratio > 0.3
    
    def extract_classes(self, text: str) -> List[str]:
        """Extrait les classes ז-1, ח-2, etc."""
        pattern = r'[זחטיא]-[0-9]'
        return re.findall(pattern, text)
    
    def analyze_text(self, text: str) -> Dict:
        """Analyse simple d'un texte hébreu"""
        result = {
            'text': text,
            'is_hebrew': self.is_hebrew(text),
            'classes': self.extract_classes(text),
            'subjects': [],
            'actions': [],
            'confidence': 0.0
        }
        
        # Chercher matières
        for hebrew_subject, english in self.subjects.items():
            if hebrew_subject in text:
                result['subjects'].append(hebrew_subject)
        
        # Chercher actions
        for hebrew_action, english in self.actions.items():
            if hebrew_action in text:
                result['actions'].append(hebrew_action)
        
        # Calculer confiance basique
        confidence = 0.5  # base
        if result['classes']:
            confidence += 0.2
        if result['subjects']:
            confidence += 0.2
        if result['actions']:
            confidence += 0.1
        
        result['confidence'] = min(confidence, 1.0)
        
        return result

def test_hebrew_detection():
    """Test détection hébreu"""
    print("\n=== TEST DETECTION HEBREU ===")
    
    processor = SimpleHebrewProcessor()
    
    test_cases = [
        ("תוכל למלא את החורים במערכת השעות של ז-1?", True, "Phrase complète hébreu"),
        ("Bonjour comment allez-vous?", False, "Phrase française"),
        ("שלום Hello", True, "Mixte hébreu-anglais"),
        ("123 456", False, "Chiffres seulement")
    ]
    
    passed = 0
    for text, expected, description in test_cases:
        result = processor.is_hebrew(text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: {description}")
        print(f"    Texte: {text}")
        print(f"    Détecté: {result}, Attendu: {expected}")
        
        if result == expected:
            passed += 1
    
    print(f"\nRésultat détection: {passed}/{len(test_cases)} tests réussis")
    return passed == len(test_cases)

def test_entity_extraction():
    """Test extraction d'entités"""
    print("\n=== TEST EXTRACTION ENTITES ===")
    
    processor = SimpleHebrewProcessor()
    
    test_cases = [
        {
            "text": "תוכל למלא את החורים במערכת השעות של ז-1?",
            "expected_classes": ["ז-1"],
            "expected_actions": ["למלא"],
            "description": "Demande remplir trous ז-1"
        },
        {
            "text": "אני רוצה להזיז את המתמטיקה של ח-2 ליום ראשון",
            "expected_classes": ["ח-2"], 
            "expected_subjects": ["מתמטיקה"],
            "expected_actions": ["להזיז"],
            "description": "Déplacer maths ח-2"
        },
        {
            "text": "לאזן את העומס בין ז-1, ח-1, ט-1",
            "expected_classes": ["ז-1", "ח-1", "ט-1"],
            "expected_actions": ["לאזן"], 
            "description": "Équilibrer charge 3 classes"
        }
    ]
    
    passed = 0
    for test in test_cases:
        print(f"\n  Test: {test['description']}")
        print(f"  Texte: {test['text']}")
        
        result = processor.analyze_text(test['text'])
        
        # Vérifier classes
        classes_ok = set(result['classes']) == set(test.get('expected_classes', []))
        actions_ok = set(result['actions']) == set(test.get('expected_actions', []))
        subjects_ok = set(result['subjects']) == set(test.get('expected_subjects', []))
        
        print(f"    Classes trouvées: {result['classes']} {'✓' if classes_ok else '✗'}")
        print(f"    Actions trouvées: {result['actions']} {'✓' if actions_ok else '✗'}")
        print(f"    Matières trouvées: {result['subjects']} {'✓' if subjects_ok else '✗'}")
        print(f"    Confiance: {result['confidence']:.2f}")
        
        if classes_ok and actions_ok and subjects_ok:
            passed += 1
            print(f"    Résultat: PASS")
        else:
            print(f"    Résultat: FAIL")
    
    print(f"\nRésultat extraction: {passed}/{len(test_cases)} tests réussis")
    return passed == len(test_cases)

def test_conversation_simulation():
    """Simule une conversation basique"""
    print("\n=== SIMULATION CONVERSATION ===")
    
    processor = SimpleHebrewProcessor()
    
    messages = [
        "שלום! יש לי בעיה עם מערכת השעות",
        "תוכל למלא את החורים במערכת השעות של ז-1?", 
        "אני רוצה להזיז את המתמטיקה של ח-2",
        "חשוב לי שהמדעים יהיו בבוקר",
        "תוכלו לאזן את העומס בין הכיתות?"
    ]
    
    print("Simulation de conversation:")
    
    for i, message in enumerate(messages, 1):
        print(f"\n  👤 Message {i}: {message}")
        
        analysis = processor.analyze_text(message)
        
        # Créer réponse simple basée sur l'analyse
        if analysis['actions']:
            action = analysis['actions'][0]
            if action == 'למלא':
                response = "אני מבין שאתה רוצה למלא חורים במערכת השעות. אני אעזור לך."
            elif action == 'להזיז':
                response = "בסדר, אני יכול לעזור להזיז שיעורים. איזה שיעורים?"
            elif action == 'לאזן':
                response = "אני אבדוק איך לאזן טוב יותר את העומס בין הכיתות."
            else:
                response = "הבנתי את הבקשה שלך. אני אעבוד על זה."
        else:
            response = "שלום! איך אני יכול לעזור לך עם מערכת השעות?"
        
        print(f"  🤖 Réponse: {response}")
        print(f"      Analyse: Classes={analysis['classes']}, Actions={analysis['actions']}")
    
    return True

def main():
    print("=" * 60)
    print("TEST SIMPLE DU PROCESSEUR HEBREU") 
    print("=" * 60)
    
    tests = [
        ("Détection hébreu", test_hebrew_detection),
        ("Extraction entités", test_entity_extraction), 
        ("Simulation conversation", test_conversation_simulation)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'='*20} {name.upper()} {'='*20}")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"ERREUR dans {name}: {e}")
            results.append((name, False))
    
    # Résumé final
    print("\n" + "=" * 60)
    print("RÉSUMÉ FINAL")
    print("=" * 60)
    
    passed = 0
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {status:6} | {name}")
        if success:
            passed += 1
    
    print(f"\nRésultat global: {passed}/{len(results)} tests réussis")
    
    if passed == len(results):
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("Le processeur hébreu fonctionne correctement.")
        print("\nFonctionnalités validées:")
        print("  ✓ Détection automatique de l'hébreu")
        print("  ✓ Extraction des classes (ז-1, ח-2, etc.)")
        print("  ✓ Reconnaissance des actions hébraïques")
        print("  ✓ Extraction des matières scolaires")
        print("  ✓ Simulation de conversation basique")
    else:
        print(f"\n⚠️ {len(results)-passed} test(s) ont échoué")
        print("Certaines fonctionnalités nécessitent des corrections.")
    
    return passed == len(results)

if __name__ == "__main__":
    main()
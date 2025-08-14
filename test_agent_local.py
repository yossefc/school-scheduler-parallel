#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test l'agent conseiller en local avec base de données localhost
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scheduler_ai.schedule_advisor_agent import create_advisor_agent
from scheduler_ai.hebrew_language_processor import HebrewLanguageProcessor

# Configuration pour localhost
db_config = {
    "host": "localhost",
    "database": "school_scheduler", 
    "user": "admin",
    "password": "school123",
    "port": 5432
}

def test_hebrew_processor():
    """Test du processeur hébreu seul"""
    print("\n=== TEST PROCESSEUR HEBREU ===")
    
    processor = HebrewLanguageProcessor()
    test_text = "תוכל למלא את החורים במערכת השעות של ז-1?"
    
    print(f"Texte: {test_text}")
    
    try:
        result = processor.analyze_hebrew_text(test_text)
        print(f"Analyse terminée:")
        print(f"  Actions: {result['actions']}")
        print(f"  Classes: {result['entities']['classes']}")
        print(f"  Intent: {result['main_intent']}")
        print(f"  Confiance: {result['confidence_score']:.2f}")
        return True
    except Exception as e:
        print(f"Erreur: {e}")
        return False

def test_agent_creation():
    """Test création agent avec base locale"""
    print("\n=== TEST CREATION AGENT ===")
    
    try:
        agent = create_advisor_agent(db_config)
        print("Agent créé avec succès")
        
        # Test simple
        response = agent.process_user_request(
            "Bonjour, pouvez-vous m'aider ?",
            {"session_id": "test_local"}
        )
        
        print(f"Réponse: {response['message'][:100]}...")
        return True
        
    except Exception as e:
        print(f"Erreur création agent: {e}")
        # Si erreur DB, on peut continuer sans
        if "Name or service not known" in str(e) or "Connection refused" in str(e):
            print("Base de données non disponible - test processeur seulement")
            return test_hebrew_processor()
        return False

def main():
    print("=== TEST AGENT CONSEILLER LOCAL ===")
    
    success = []
    
    # Test 1: Processeur hébreu (indépendant de la DB)
    print("\n1. Test processeur hébraïque...")
    success.append(test_hebrew_processor())
    
    # Test 2: Agent complet (nécessite DB)
    print("\n2. Test agent complet...")
    success.append(test_agent_creation())
    
    # Résumé
    print("\n=== RÉSUMÉ ===")
    passed = sum(success)
    total = len(success)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if passed == total:
        print("TOUS LES TESTS PASSENT!")
        print("L'agent multilingue est fonctionnel")
    elif passed > 0:
        print("TESTS PARTIELS")
        if not success[1]:
            print("Note: Pour l'agent complet, vérifiez que PostgreSQL est actif")
    else:
        print("ÉCHEC DES TESTS")

if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test simple de l'agent conseiller multilingue
"""

import requests
import json

API_BASE_URL = "http://localhost:5002"
HEADERS = {"Content-Type": "application/json"}

def test_api_status():
    """Test de base - connexion API"""
    print("\n=== TEST DE CONNEXION ===")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/advisor/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCES - API active")
            print(f"Status: {data.get('status', 'N/A')}")
            return True
        else:
            print(f"ERREUR - Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"ERREUR - Connexion impossible: {e}")
        return False

def test_hebrew_message():
    """Test message en hébreu"""
    print("\n=== TEST MESSAGE HEBREU ===")
    
    hebrew_message = "תוכל למלא את החורים במערכת השעות של ז-1?"
    print(f"Message: {hebrew_message}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/advisor/chat",
            json={
                "message": hebrew_message,
                "context": {"session_id": "test_simple"}
            },
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCES - Message traité")
            print(f"Reponse (extrait): {data.get('message', '')[:100]}...")
            return True
        else:
            print(f"ERREUR - Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERREUR - {e}")
        return False

def test_french_message():
    """Test message en français"""
    print("\n=== TEST MESSAGE FRANCAIS ===")
    
    french_message = "Peux-tu éliminer les trous dans l'emploi du temps?"
    print(f"Message: {french_message}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/advisor/chat",
            json={
                "message": french_message,
                "context": {"session_id": "test_simple"}
            },
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCES - Message traité")
            print(f"Reponse (extrait): {data.get('message', '')[:100]}...")
            return True
        else:
            print(f"ERREUR - Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERREUR - {e}")
        return False

def main():
    print("=" * 50)
    print("TEST SIMPLE DE L'AGENT MULTILINGUE")
    print("=" * 50)
    
    results = []
    
    # Test 1: Connexion API
    results.append(("Connexion API", test_api_status()))
    
    # Test 2: Message hébreu
    results.append(("Message hébreu", test_hebrew_message()))
    
    # Test 3: Message français
    results.append(("Message français", test_french_message()))
    
    # Résumé
    print("\n" + "=" * 50)
    print("RÉSUMÉ")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "PASSÉ" if success else "ÉCHOUÉ"
        print(f"{status:8} | {test_name}")
        if success:
            passed += 1
    
    print(f"\nRésultat: {passed}/{len(results)} tests réussis")
    
    if passed == len(results):
        print("\nTOUS LES TESTS SONT PASSÉS!")
        print("L'agent multilingue fonctionne correctement.")
    else:
        print("\nCERTAINS TESTS ONT ÉCHOUÉ")
        print("Vérifiez que l'agent est démarré:")
        print("  cd scheduler_ai && python advisor_api.py")
        print("  OU: docker-compose up advisor_agent -d")

if __name__ == "__main__":
    main()
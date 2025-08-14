#!/usr/bin/env python3
"""
Test script for automatic constraint regeneration functionality
Tests the complete workflow: add constraint → auto regeneration → user feedback
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_constraint_auto_regeneration():
    """Test the complete constraint addition and auto-regeneration workflow"""
    
    print("🧪 Test: Ajout de contrainte avec régénération automatique")
    print("=" * 60)
    
    # Test 1: Contrainte critique qui doit déclencher la régénération
    print("\n1. Test contrainte critique (teacher_availability)")
    critical_constraint = {
        "constraint_type": "teacher_availability",
        "entity_name": "Cohen David", 
        "constraint_data": {
            "unavailable_days": [5],  # Vendredi
            "reason": "Formation externe",
            "original_text": "Le professeur Cohen n'est pas disponible le vendredi"
        },
        "priority": 1,  # Haute priorité
        "is_active": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/constraints", 
            json=critical_constraint,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Contrainte ajoutée: ID {result.get('constraint_id', 'N/A')}")
            
            if result.get('auto_regenerated'):
                print("🔄 Régénération automatique déclenchée!")
                regeneration = result.get('regeneration_details', {})
                if regeneration.get('success'):
                    print(f"   ✅ Régénération réussie ({regeneration.get('method', 'unknown')})")
                    if regeneration.get('quality_score'):
                        print(f"   📊 Score qualité: {regeneration['quality_score']:.1f}%")
                    print(f"   🆔 Schedule ID: {regeneration.get('schedule_id', 'N/A')}")
                else:
                    print(f"   ❌ Régénération échouée: {regeneration.get('error', 'Unknown error')}")
            else:
                print("⏳ Pas de régénération automatique (contrainte non critique)")
                
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout - La régénération peut prendre du temps")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    # Test 2: Contrainte non critique qui ne doit PAS déclencher la régénération  
    print("\n2. Test contrainte non critique")
    non_critical_constraint = {
        "constraint_type": "custom",
        "entity_name": "Global",
        "constraint_data": {
            "original_text": "Préférence pour les cours le matin"
        },
        "priority": 3,  # Priorité normale
        "is_active": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/constraints",
            json=non_critical_constraint,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Contrainte ajoutée: ID {result.get('constraint_id', 'N/A')}")
            
            if result.get('auto_regenerated'):
                print("⚠️  ATTENTION: Régénération inattendue pour contrainte non critique!")
            else:
                print("✅ Pas de régénération automatique (comportement attendu)")
                
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    # Test 3: Contrainte avec mot-clé critique dans le texte
    print("\n3. Test contrainte avec mot-clé critique")
    keyword_constraint = {
        "constraint_type": "custom",
        "entity_name": "Global",
        "constraint_data": {
            "original_text": "Il y a trop de trous dans l'emploi du temps de la classe 9A"
        },
        "priority": 2,  # Priorité moyenne
        "is_active": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/constraints",
            json=keyword_constraint,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Contrainte ajoutée: ID {result.get('constraint_id', 'N/A')}")
            
            if result.get('auto_regenerated'):
                print("🔄 Régénération déclenchée par mot-clé critique ('trop de trous')")
                regeneration = result.get('regeneration_details', {})
                if regeneration.get('success'):
                    print(f"   ✅ Régénération réussie")
                else:
                    print(f"   ❌ Régénération échouée")
            else:
                print("⏳ Pas de régénération automatique")
                
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout - La régénération peut prendre du temps")
    except Exception as e:
        print(f"❌ Erreur: {e}")

def test_constraint_toggle_regeneration():
    """Test la régénération lors de l'activation d'une contrainte"""
    print("\n4. Test activation de contrainte critique")
    
    # D'abord créer une contrainte inactive
    inactive_constraint = {
        "constraint_type": "teacher_availability", 
        "entity_name": "Test Teacher",
        "constraint_data": {"unavailable_days": [1], "original_text": "Test indisponible lundi"},
        "priority": 0,  # Critique
        "is_active": False  # Inactive au début
    }
    
    try:
        # Créer la contrainte
        response = requests.post(f"{BASE_URL}/api/constraints", json=inactive_constraint)
        if response.status_code == 200:
            constraint_id = response.json().get('constraint_id')
            print(f"✅ Contrainte inactive créée: ID {constraint_id}")
            
            # L'activer
            toggle_response = requests.post(
                f"{BASE_URL}/api/constraints/{constraint_id}/toggle",
                json={"is_active": True},
                timeout=30
            )
            
            if toggle_response.status_code == 200:
                result = toggle_response.json()
                print("✅ Contrainte activée")
                
                if result.get('auto_regenerated'):
                    print("🔄 Régénération automatique déclenchée lors de l'activation!")
                else:
                    print("⏳ Pas de régénération lors de l'activation")
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout lors de l'activation")
    except Exception as e:
        print(f"❌ Erreur: {e}")

def check_server_status():
    """Vérifie que le serveur est accessible"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Serveur accessible")
            return True
        else:
            print(f"❌ Serveur inaccessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Impossible de joindre le serveur: {e}")
        print("   Assurez-vous que le serveur fonctionne sur http://localhost:8000")
        return False

if __name__ == "__main__":
    print("🚀 Test de la régénération automatique des contraintes")
    print("=" * 60)
    
    if not check_server_status():
        print("\n💡 Pour démarrer le serveur:")
        print("   cd solver && python main.py")
        sys.exit(1)
    
    test_constraint_auto_regeneration()
    test_constraint_toggle_regeneration()
    
    print("\n" + "=" * 60)
    print("✨ Tests terminés!")
    print("\n💡 Pour tester l'interface utilisateur:")
    print("   Ouvrez http://localhost:8000/constraints-manager")
    print("   Ajoutez une contrainte avec 'trop de trous' dans le texte")
    print("   Observez la notification de régénération automatique")
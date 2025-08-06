#!/usr/bin/env python3
"""
Test détaillé de la structure de réponse de génération d'emploi du temps
"""

import requests
import json
from pprint import pprint

API_URL = "http://localhost:8000"

def test_schedule_generation():
    print("🔍 Test détaillé de la génération d'emploi du temps\n")
    
    # Test 1: Sans contraintes
    print("1️⃣ Test sans contraintes:")
    print("-" * 50)
    
    try:
        response = requests.post(
            f"{API_URL}/generate_schedule",
            json={"constraints": [], "time_limit": 30},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\nType de réponse: {type(data)}")
            print(f"Clés présentes: {list(data.keys())}")
            
            # Vérifier la structure
            if isinstance(data, dict):
                if 'schedule' in data:
                    schedule = data['schedule']
                    print(f"\n✅ 'schedule' trouvé: {len(schedule)} entrées")
                    
                    # Afficher un exemple d'entrée
                    if schedule and len(schedule) > 0:
                        print("\nExemple d'entrée:")
                        pprint(schedule[0])
                else:
                    print("\n❌ Clé 'schedule' manquante!")
                    print("Structure reçue:")
                    pprint(data)
                    
                if 'statistics' in data:
                    print(f"\n✅ 'statistics' trouvé:")
                    pprint(data['statistics'])
                else:
                    print("\n⚠️ Clé 'statistics' manquante")
                    
            elif isinstance(data, list):
                print(f"\n⚠️ Réponse est une liste de {len(data)} éléments")
                if data:
                    print("Premier élément:")
                    pprint(data[0])
                    
        else:
            print(f"\n❌ Erreur: {response.status_code}")
            print(response.json())
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        
    # Test 2: Avec une contrainte simple
    print("\n\n2️⃣ Test avec une contrainte:")
    print("-" * 50)
    
    constraint = {
        "constraint_type": "teacher_availability",
        "entity_name": "Cohen",
        "constraint_data": {
            "unavailable_days": [5],
            "unavailable_periods": [7, 8, 9, 10]
        },
        "priority": 1,
        "is_active": True
    }
    
    try:
        response = requests.post(
            f"{API_URL}/generate_schedule",
            json={
                "constraints": [constraint],
                "time_limit": 30
            },
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Génération réussie avec contrainte")
            print(f"Nombre d'entrées: {len(data.get('schedule', []))}")
        else:
            print(f"❌ Échec avec contrainte")
            print(response.json())
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_schedule_generation()
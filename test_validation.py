#!/usr/bin/env python3
"""
test_validation.py - Script pour tester la validation Pydantic
Fonctionne sur Windows et Linux
"""
import requests
import json
import time
from datetime import datetime

# Configuration
API_URL = "http://localhost:5001/api/ai/constraint"
HEADERS = {"Content-Type": "application/json"}

# Couleurs pour l'affichage (fonctionne sur Windows 10+ et Linux)
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_name, test_number):
    print(f"\n{Colors.BLUE}{Colors.BOLD}=== Test {test_number}: {test_name} ==={Colors.END}")

def print_result(response, expected_success=True):
    if response.status_code == 200:
        if expected_success:
            print(f"{Colors.GREEN}✅ Succès (200 OK){Colors.END}")
        else:
            print(f"{Colors.RED}❌ Erreur: Devrait échouer mais a réussi!{Colors.END}")
        print(f"Réponse: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    else:
        if not expected_success:
            print(f"{Colors.GREEN}✅ Échec attendu ({response.status_code}){Colors.END}")
        else:
            print(f"{Colors.RED}❌ Échec inattendu ({response.status_code}){Colors.END}")
        print(f"Erreur: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

def run_tests():
    print(f"{Colors.BOLD}🧪 TESTS DE VALIDATION PYDANTIC{Colors.END}")
    print(f"API: {API_URL}")
    print(f"Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        # Test 1: Valide
        {
            "name": "Contrainte valide complète",
            "expected_success": True,
            "data": {
                "type": "teacher_availability",
                "entity": "Cohen",
                "data": {
                    "unavailable_days": [5],
                    "reason": "Obligations familiales"
                },
                "priority": 2
            }
        },
        
        # Test 2: Jour invalide
        {
            "name": "Jour invalide (7 > 6)",
            "expected_success": False,
            "data": {
                "type": "teacher_availability",
                "entity": "Cohen",
                "data": {
                    "unavailable_days": [7]
                }
            }
        },
        
        # Test 3: Champ requis manquant
        {
            "name": "Champ requis manquant (unavailable_days)",
            "expected_success": False,
            "data": {
                "type": "teacher_availability",
                "entity": "Cohen",
                "data": {
                    "reason": "Test sans jours"
                }
            }
        },
        
        # Test 4: Type invalide
        {
            "name": "Type de contrainte invalide",
            "expected_success": False,
            "data": {
                "type": "type_inexistant",
                "entity": "Cohen",
                "data": {}
            }
        },
        
        # Test 5: Préférence horaire valide
        {
            "name": "Préférence horaire valide",
            "expected_success": True,
            "data": {
                "type": "time_preference",
                "entity": "Math",
                "data": {
                    "preferred_time": "morning",
                    "is_strict": True
                }
            }
        },
        
        # Test 6: Préférence horaire invalide
        {
            "name": "Préférence horaire invalide (midi)",
            "expected_success": False,
            "data": {
                "type": "time_preference",
                "entity": "Math",
                "data": {
                    "preferred_time": "midi"
                }
            }
        },
        
        # Test 7: Heures consécutives valides
        {
            "name": "Limite heures consécutives valide",
            "expected_success": True,
            "data": {
                "type": "consecutive_hours_limit",
                "entity": "all",
                "data": {
                    "max_consecutive": 3,
                    "applies_to": "teachers"
                }
            }
        },
        
        # Test 8: Heures consécutives invalides
        {
            "name": "Limite heures trop élevée (10 > 8)",
            "expected_success": False,
            "data": {
                "type": "consecutive_hours_limit",
                "entity": "all",
                "data": {
                    "max_consecutive": 10
                }
            }
        },
        
        # Test 9: Format heure valide
        {
            "name": "Horaires école valides",
            "expected_success": True,
            "data": {
                "type": "school_hours",
                "entity": "school",
                "data": {
                    "start": "08:00",
                    "end": "18:00"
                },
                "priority": 0
            }
        },
        
        # Test 10: Format heure invalide
        {
            "name": "Format heure invalide",
            "expected_success": False,
            "data": {
                "type": "school_hours",
                "entity": "school",
                "data": {
                    "start": "8h00",  # Format invalide
                    "end": "18:00"
                }
            }
        }
    ]
    
    # Statistiques
    success_count = 0
    total_tests = len(tests)
    
    # Exécuter les tests
    for i, test in enumerate(tests, 1):
        print_test_header(test["name"], i)
        
        try:
            response = requests.post(API_URL, headers=HEADERS, json=test["data"])
            print_result(response, test["expected_success"])
            
            # Compter les succès
            if test["expected_success"] and response.status_code == 200:
                success_count += 1
            elif not test["expected_success"] and response.status_code != 200:
                success_count += 1
                
        except requests.exceptions.ConnectionError:
            print(f"{Colors.RED}❌ Erreur de connexion - L'API est-elle lancée sur {API_URL}?{Colors.END}")
            break
        except Exception as e:
            print(f"{Colors.RED}❌ Erreur: {str(e)}{Colors.END}")
        
        time.sleep(0.5)  # Petite pause entre les tests
    
    # Résumé
    print(f"\n{Colors.BOLD}📊 RÉSUMÉ{Colors.END}")
    print(f"Tests réussis: {success_count}/{total_tests}")
    if success_count == total_tests:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Tous les tests sont passés !{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  {total_tests - success_count} tests ont échoué{Colors.END}")

if __name__ == "__main__":
    print("Assurez-vous que l'agent IA est lancé sur http://localhost:5001")
    print("Appuyez sur Entrée pour commencer les tests...")
    input()
    
    run_tests()
    
    print("\nAppuyez sur Entrée pour terminer...")
    input()
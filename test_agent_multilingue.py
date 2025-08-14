#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test complet de l'agent conseiller multilingue (Hébreu + Français)
Vérifie le bon fonctionnement de toutes les fonctionnalités
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List

# Configuration
API_BASE_URL = "http://localhost:5002"
HEADERS = {"Content-Type": "application/json"}

class TestAgentMultilingue:
    """Tests automatisés pour l'agent conseiller multilingue"""
    
    def __init__(self):
        self.results = []
        self.session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def test_connection(self) -> bool:
        """Test 1: Vérifier la connexion à l'API"""
        print("\nTEST 1: Connexion à l'API")
        print("-" * 50)
        
        try:
            response = requests.get(f"{API_BASE_URL}/api/advisor/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API connectée")
                print(f"   État: {data.get('status', 'N/A')}")
                print(f"   Préférences: {data.get('user_preferences', 0)}")
                print(f"   Changements en attente: {data.get('pending_changes', 0)}")
                self.results.append(("Connexion API", True))
                return True
            else:
                print(f"❌ Erreur connexion: Status {response.status_code}")
                self.results.append(("Connexion API", False))
                return False
        except Exception as e:
            print(f"❌ Erreur: {e}")
            self.results.append(("Connexion API", False))
            return False
    
    def test_hebrew_detection(self) -> bool:
        """Test 2: Détection automatique de l'hébreu"""
        print("\n🔤 TEST 2: Détection de langue hébraïque")
        print("-" * 50)
        
        test_cases = [
            {
                "message": "תוכל למלא את החורים במערכת השעות של ז-1?",
                "expected_language": "hebrew",
                "description": "Demande complète en hébreu"
            },
            {
                "message": "Peux-tu éliminer les trous dans l'emploi du temps?",
                "expected_language": "french",
                "description": "Demande en français"
            },
            {
                "message": "שלום! Comment ça va?",
                "expected_language": "hebrew",  # Commence par hébreu
                "description": "Texte mixte hébreu-français"
            }
        ]
        
        success_count = 0
        for i, test in enumerate(test_cases, 1):
            print(f"\n  Test {i}: {test['description']}")
            print(f"  Message: {test['message']}")
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/advisor/chat",
                    json={
                        "message": test["message"],
                        "context": {"session_id": self.session_id}
                    },
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    data = response.json()
                    detected_lang = data.get("analysis", {}).get("language", "unknown")
                    
                    if detected_lang == test["expected_language"]:
                        print(f"  ✅ Langue détectée correctement: {detected_lang}")
                        success_count += 1
                    else:
                        print(f"  ❌ Détection incorrecte: {detected_lang} (attendu: {test['expected_language']})")
                else:
                    print(f"  ❌ Erreur API: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Erreur: {e}")
        
        success = success_count == len(test_cases)
        self.results.append(("Détection langue", success))
        return success
    
    def test_hebrew_entity_extraction(self) -> bool:
        """Test 3: Extraction d'entités hébraïques"""
        print("\n📚 TEST 3: Extraction d'entités hébraïques")
        print("-" * 50)
        
        test_messages = [
            {
                "message": "אני רוצה להזיז את המתמטיקה של ז-1 ליום ראשון",
                "expected_entities": {
                    "classes": ["ז-1"],
                    "subjects": ["מתמטיקה"],
                    "days": ["ראשון"],
                    "actions": ["move"]
                }
            },
            {
                "message": "תוכל לאזן את העומס בין כיתות ח-1, ח-2 וח-3?",
                "expected_entities": {
                    "classes": ["ח-1", "ח-2", "ח-3"],
                    "actions": ["balance"]
                }
            },
            {
                "message": "חשוב לי שהמדעים והאנגלית יהיו בבוקר",
                "expected_entities": {
                    "subjects": ["מדעים", "אנגלית"],
                    "time_preferences": ["בבוקר"]
                }
            }
        ]
        
        success_count = 0
        for i, test in enumerate(test_messages, 1):
            print(f"\n  Test {i}: {test['message'][:50]}...")
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/advisor/chat",
                    json={
                        "message": test["message"],
                        "context": {"session_id": self.session_id}
                    },
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    data = response.json()
                    analysis = data.get("analysis", {})
                    
                    # Vérifier les entités extraites
                    entities_match = True
                    for entity_type, expected_values in test["expected_entities"].items():
                        extracted = analysis.get("entities_found", {}).get(entity_type, 0)
                        if entity_type in ["classes", "subjects"]:
                            if extracted != len(expected_values):
                                entities_match = False
                                print(f"  ⚠️ {entity_type}: trouvé {extracted}, attendu {len(expected_values)}")
                    
                    if entities_match:
                        print(f"  ✅ Entités extraites correctement")
                        success_count += 1
                    else:
                        print(f"  ❌ Extraction incomplète")
                else:
                    print(f"  ❌ Erreur API: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Erreur: {e}")
        
        success = success_count >= 2  # Au moins 2 sur 3
        self.results.append(("Extraction entités hébraïques", success))
        return success
    
    def test_hebrew_responses(self) -> bool:
        """Test 4: Réponses en hébreu"""
        print("\n💬 TEST 4: Génération de réponses en hébreu")
        print("-" * 50)
        
        hebrew_request = "תוכל למלא את החורים במערכת השעות של ז-1?"
        
        print(f"  Demande: {hebrew_request}")
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/advisor/chat",
                json={
                    "message": hebrew_request,
                    "context": {"session_id": self.session_id}
                },
                headers=HEADERS
            )
            
            if response.status_code == 200:
                data = response.json()
                response_message = data.get("message", "")
                
                # Vérifier que la réponse contient de l'hébreu
                hebrew_chars = sum(1 for c in response_message if '\u0590' <= c <= '\u05FF')
                total_chars = len([c for c in response_message if c.isalpha()])
                
                if total_chars > 0:
                    hebrew_ratio = hebrew_chars / total_chars
                    
                    print(f"\n  Réponse (extrait): {response_message[:100]}...")
                    print(f"  Ratio hébreu: {hebrew_ratio:.1%}")
                    
                    if hebrew_ratio > 0.5:
                        print(f"  ✅ Réponse en hébreu générée")
                        self.results.append(("Réponses hébreu", True))
                        return True
                    else:
                        print(f"  ❌ Réponse pas assez en hébreu")
                        self.results.append(("Réponses hébreu", False))
                        return False
            else:
                print(f"  ❌ Erreur API: {response.status_code}")
                self.results.append(("Réponses hébreu", False))
                return False
                
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            self.results.append(("Réponses hébreu", False))
            return False
    
    def test_preference_memory(self) -> bool:
        """Test 5: Mémorisation des préférences"""
        print("\n🧠 TEST 5: Mémorisation des préférences")
        print("-" * 50)
        
        preferences = [
            "חשוב לי שהמתמטיקה תמיד תהיה בבוקר",
            "Pour moi, les cours de sciences doivent être groupés",
            "אני מעדיף שלא יהיו שיעורים אחרי 15:00"
        ]
        
        print("  Envoi de préférences...")
        success_count = 0
        
        for i, pref in enumerate(preferences, 1):
            print(f"\n  Préférence {i}: {pref[:50]}...")
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/advisor/chat",
                    json={
                        "message": pref,
                        "context": {
                            "session_id": self.session_id,
                            "user_name": "Test User"
                        }
                    },
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    data = response.json()
                    new_prefs = data.get("new_preferences", [])
                    
                    if new_prefs:
                        print(f"  ✅ Préférence mémorisée")
                        success_count += 1
                    else:
                        print(f"  ⚠️ Préférence non détectée")
                else:
                    print(f"  ❌ Erreur API: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Erreur: {e}")
        
        # Vérifier les préférences stockées
        print("\n  Vérification des préférences stockées...")
        try:
            response = requests.get(f"{API_BASE_URL}/api/advisor/preferences")
            if response.status_code == 200:
                data = response.json()
                total_prefs = data.get("preferences", {}).get("total_preferences", 0)
                print(f"  📊 Total préférences en mémoire: {total_prefs}")
                
                if success_count >= 2:
                    print(f"  ✅ Mémorisation fonctionnelle")
                    self.results.append(("Mémorisation préférences", True))
                    return True
                    
        except Exception as e:
            print(f"  ❌ Erreur vérification: {e}")
        
        self.results.append(("Mémorisation préférences", False))
        return False
    
    def test_conversation_flow(self) -> bool:
        """Test 6: Flux de conversation multilingue"""
        print("\n🗣️ TEST 6: Conversation multilingue")
        print("-" * 50)
        
        conversation = [
            ("שלום! יש לי בעיה עם מערכת השעות", "hebrew"),
            ("Bonjour ! Comment puis-je vous aider ?", "french"),
            ("תוכל להסביר איך זה עובד?", "hebrew"),
            ("Je voudrais optimiser les horaires", "french"),
        ]
        
        success_count = 0
        for i, (message, expected_lang) in enumerate(conversation, 1):
            print(f"\n  Message {i} ({expected_lang}): {message[:50]}...")
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/advisor/chat",
                    json={
                        "message": message,
                        "context": {
                            "session_id": self.session_id,
                            "conversation_id": "test_conversation"
                        }
                    },
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        print(f"  ✅ Message traité")
                        success_count += 1
                    else:
                        print(f"  ❌ Échec traitement")
                else:
                    print(f"  ❌ Erreur API: {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ Erreur: {e}")
            
            time.sleep(0.5)  # Petite pause entre messages
        
        success = success_count >= 3  # Au moins 3 sur 4
        self.results.append(("Conversation multilingue", success))
        return success
    
    def test_examples_endpoint(self) -> bool:
        """Test 7: Endpoint des exemples d'usage"""
        print("\n📖 TEST 7: Exemples d'usage")
        print("-" * 50)
        
        try:
            response = requests.get(f"{API_BASE_URL}/api/advisor/examples")
            
            if response.status_code == 200:
                data = response.json()
                
                # Vérifier la présence des exemples
                has_hebrew = "simple_requests_hebrew" in data.get("examples", {})
                has_french = "simple_requests_french" in data.get("examples", {})
                has_tips = "tips_hebrew" in data and "tips_french" in data
                
                print(f"  ✅ Exemples hébreux: {'Oui' if has_hebrew else 'Non'}")
                print(f"  ✅ Exemples français: {'Oui' if has_french else 'Non'}")
                print(f"  ✅ Conseils bilingues: {'Oui' if has_tips else 'Non'}")
                
                if has_hebrew and has_french and has_tips:
                    # Afficher quelques exemples
                    hebrew_examples = data["examples"].get("simple_requests_hebrew", [])
                    french_examples = data["examples"].get("simple_requests_french", [])
                    
                    print(f"\n  Exemples hébreux: {len(hebrew_examples)}")
                    if hebrew_examples:
                        print(f"    - {hebrew_examples[0]}")
                    
                    print(f"\n  Exemples français: {len(french_examples)}")
                    if french_examples:
                        print(f"    - {french_examples[0]}")
                    
                    self.results.append(("Exemples d'usage", True))
                    return True
                else:
                    print(f"  ❌ Exemples incomplets")
                    self.results.append(("Exemples d'usage", False))
                    return False
            else:
                print(f"  ❌ Erreur API: {response.status_code}")
                self.results.append(("Exemples d'usage", False))
                return False
                
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            self.results.append(("Exemples d'usage", False))
            return False
    
    def run_all_tests(self):
        """Exécute tous les tests"""
        print("\n" + "=" * 60)
        print("🚀 DÉMARRAGE DES TESTS DE L'AGENT MULTILINGUE")
        print("=" * 60)
        
        # Exécuter tous les tests
        self.test_connection()
        self.test_hebrew_detection()
        self.test_hebrew_entity_extraction()
        self.test_hebrew_responses()
        self.test_preference_memory()
        self.test_conversation_flow()
        self.test_examples_endpoint()
        
        # Afficher le résumé
        self.print_summary()
    
    def print_summary(self):
        """Affiche le résumé des tests"""
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for _, success in self.results if success)
        
        for test_name, success in self.results:
            status = "✅ PASSÉ" if success else "❌ ÉCHOUÉ"
            print(f"  {status:12} | {test_name}")
        
        print("-" * 60)
        print(f"  Total: {passed_tests}/{total_tests} tests réussis ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🎉 TOUS LES TESTS SONT PASSÉS !")
            print("L'agent multilingue fonctionne parfaitement.")
        elif passed_tests >= total_tests * 0.7:
            print("\n⚠️ La plupart des tests sont passés.")
            print("Quelques fonctionnalités nécessitent attention.")
        else:
            print("\n❌ Plusieurs tests ont échoué.")
            print("Vérifiez que l'API est bien démarrée sur le port 5002.")
            print("Commande: docker-compose up advisor_agent -d")
        
        print("\n📝 FONCTIONNALITÉS VALIDÉES:")
        if any(name == "Connexion API" and success for name, success in self.results):
            print("  ✅ API accessible et fonctionnelle")
        if any(name == "Détection langue" and success for name, success in self.results):
            print("  ✅ Détection automatique hébreu/français")
        if any(name == "Extraction entités hébraïques" and success for name, success in self.results):
            print("  ✅ Extraction d'entités en hébreu (classes, matières)")
        if any(name == "Réponses hébreu" and success for name, success in self.results):
            print("  ✅ Génération de réponses en hébreu")
        if any(name == "Mémorisation préférences" and success for name, success in self.results):
            print("  ✅ Mémorisation des préférences utilisateur")
        if any(name == "Conversation multilingue" and success for name, success in self.results):
            print("  ✅ Conversations fluides multilingues")


def main():
    """Point d'entrée principal"""
    print("\nTEST DE L'AGENT CONSEILLER MULTILINGUE")
    print("=" * 60)
    print("Cet outil teste le bon fonctionnement de l'agent AI")
    print("qui comprend l'hébreu et le français.")
    print("=" * 60)
    
    # Vérifier que l'API est accessible
    print("\n⏳ Vérification de l'API...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/advisor/status", timeout=5)
        if response.status_code != 200:
            print("❌ L'API n'est pas accessible sur le port 5002")
            print("\n💡 Pour démarrer l'agent:")
            print("   1. cd scheduler_ai")
            print("   2. python advisor_api.py")
            print("\n   OU avec Docker:")
            print("   docker-compose up advisor_agent -d")
            return
    except requests.exceptions.RequestException:
        print("❌ Impossible de se connecter à l'API sur le port 5002")
        print("\n💡 Assurez-vous que l'agent est démarré:")
        print("   cd scheduler_ai && python advisor_api.py")
        return
    
    print("✅ API accessible, démarrage des tests...")
    time.sleep(1)
    
    # Créer et exécuter les tests
    tester = TestAgentMultilingue()
    tester.run_all_tests()
    
    print("\n" + "=" * 60)
    print("✨ TESTS TERMINÉS")
    print("=" * 60)


if __name__ == "__main__":
    main()
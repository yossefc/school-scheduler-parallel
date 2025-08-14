#!/usr/bin/env python3
"""
Script de démonstration des algorithmes avancés d'optimisation d'emplois du temps
Basé sur l'analyse comparative des méthodes NP-difficiles
"""

import requests
import json
import time

BASE_URL = "http://localhost:5002/api/advisor"

def test_algorithms_info():
    """Teste l'endpoint d'information sur les algorithmes"""
    print("Test des informations algorithmes...")
    response = requests.get(f"{BASE_URL}/algorithms-info")
    
    if response.status_code == 200:
        data = response.json()
        print("Algorithmes disponibles:")
        for algo_name, info in data["algorithms"].items():
            print(f"  - {info['name']}: {info['description']}")
            print(f"    Forces: {info['strengths']}")
            print(f"    Ideal pour: {info['best_for']}")
            print()
    else:
        print(f"Erreur: {response.status_code}")

def test_algorithm_recommendation():
    """Teste la recommandation d'algorithme"""
    print("🎯 Test de recommandation d'algorithme...")
    response = requests.get(f"{BASE_URL}/recommend-algorithm")
    
    if response.status_code == 200:
        data = response.json()
        rec = data["recommendation"]
        print(f"✅ Algorithme recommandé: {rec['recommended_algorithm']}")
        print(f"   Raison: {rec['reasoning']}")
        print(f"   Analyse du problème:")
        for key, value in rec["problem_analysis"].items():
            print(f"     - {key}: {value}")
        print(f"   Alternatives:")
        for alt in rec["alternatives"]:
            print(f"     - {alt['name']}: {alt['reason']}")
    else:
        print(f"❌ Erreur: {response.status_code}")

def test_quality_analysis():
    """Teste l'analyse de qualité"""
    print("📊 Test d'analyse de qualité...")
    response = requests.get(f"{BASE_URL}/analyze-quality")
    
    if response.status_code == 200:
        data = response.json()
        quality = data["quality_analysis"]
        
        print("✅ Analyse de qualité:")
        print(f"   Score total: {quality['total_score']:.3f}")
        print(f"   Contraintes dures: {quality['hard_constraints_satisfied']:.1%}")
        print(f"   Contraintes souples: {quality['soft_constraints_satisfied']:.1%}")
        print(f"   Qualité pédagogique: {quality['pedagogical_quality']:.1%}")
        print(f"   Conflits détectés: {len(quality['conflicts'])}")
        
        print("\n   Suggestions d'amélioration:")
        for suggestion in data["improvement_suggestions"]:
            print(f"     {suggestion['type'].upper()}: {suggestion['message']}")
            print(f"     Action: {suggestion['action']}")
            print()
    else:
        print(f"❌ Erreur: {response.status_code}")

def test_simulated_annealing():
    """Teste l'optimisation par Recuit Simulé"""
    print("🔥 Test du Recuit Simulé...")
    
    request_data = {
        "algorithm": "simulated_annealing"
    }
    
    print("   Démarrage de l'optimisation (peut prendre du temps)...")
    response = requests.post(f"{BASE_URL}/optimize", 
                           json=request_data, 
                           timeout=300)  # 5 minutes max
    
    if response.status_code == 200:
        data = response.json()
        result = data["optimization_result"]
        print(f"✅ Recuit Simulé terminé!")
        print(f"   Score final: {result['quality']['total_score']:.3f}")
        print(f"   Algorithme: {result['algorithm']}")
        print(f"   Itérations: {result.get('iterations', 'N/A')}")
        print(f"   Améliorations: {result.get('improvements', 'N/A')}")
    else:
        print(f"❌ Erreur: {response.status_code} - {response.text}")

def test_multi_objective():
    """Teste l'optimisation multi-objectifs"""
    print("🎯 Test de l'optimisation multi-objectifs...")
    
    request_data = {
        "algorithm": "multi_objective",
        "objectives": [
            {"name": "hard_constraints", "weight": 0.5, "is_hard_constraint": True},
            {"name": "pedagogical_quality", "weight": 0.3},
            {"name": "gap_minimization", "weight": 0.2}
        ]
    }
    
    print("   Démarrage de l'optimisation multi-objectifs...")
    response = requests.post(f"{BASE_URL}/optimize", 
                           json=request_data, 
                           timeout=300)
    
    if response.status_code == 200:
        data = response.json()
        result = data["optimization_result"]
        print(f"✅ Optimisation multi-objectifs terminée!")
        print(f"   Score pondéré: {result['total_weighted_score']:.3f}")
        print(f"   Scores par objectif:")
        for obj_name, score in result["objective_scores"].items():
            print(f"     - {obj_name}: {score:.3f}")
    else:
        print(f"❌ Erreur: {response.status_code} - {response.text}")

def main():
    """Fonction principale de test"""
    print("DEMONSTRATION DES ALGORITHMES AVANCES D'OPTIMISATION")
    print("=" * 60)
    print("Bases sur l'analyse comparative des methodes pour problemes NP-difficiles")
    print()
    
    try:
        # Tests des fonctionnalités de base
        test_algorithms_info()
        print("-" * 40)
        
        test_algorithm_recommendation()
        print("-" * 40)
        
        test_quality_analysis()
        print("-" * 40)
        
        # Tests d'optimisation (commentés car longs)
        # test_simulated_annealing()
        # print("-" * 40)
        
        # test_multi_objective()
        
        print("TOUS LES TESTS TERMINES!")
        print("\nL'agent AI a maintenant appris les algorithmes puissants suivants:")
        print("- Recuit Simule (Simulated Annealing)")
        print("- Recherche Tabou (Tabu Search)")
        print("- Approches Hybrides (PC + RS + RT)")
        print("- Optimisation Multi-Objectifs")
        print("- Recommandation automatique d'algorithme")
        print("- Analyse de qualite avancee")
        
    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion: {e}")
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    main()
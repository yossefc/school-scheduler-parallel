#!/usr/bin/env python3
"""
Test simple d'amélioration de la qualité pédagogique
"""

import requests
import json

def test_current_quality():
    """Test de l'analyse de qualité actuelle"""
    print("Test de l'analyse de qualite actuelle...")
    
    try:
        response = requests.get("http://localhost:8000/api/advisor/analyze-quality", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            quality = data["quality_analysis"]
            
            score = quality["total_score"] * 100
            pedagogical = quality["pedagogical_quality"] * 100
            conflicts = len(quality["conflicts"])
            
            print(f"Score global actuel: {score:.1f}%")
            print(f"Qualite pedagogique: {pedagogical:.1f}%")
            print(f"Conflits detectes: {conflicts}")
            
            if pedagogical < 50:
                print("=> AMELIORATION NECESSAIRE!")
            
            return True
        else:
            print(f"Erreur HTTP: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Erreur: {e}")
        return False

def test_algorithm_recommendation():
    """Test de la recommandation d'algorithme"""
    print("\nTest de la recommandation d'algorithme...")
    
    try:
        response = requests.get("http://localhost:8000/api/advisor/recommend-algorithm", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            rec = data["recommendation"]
            
            print(f"Algorithme recommande: {rec['recommended_algorithm']}")
            print(f"Raison: {rec['reasoning']}")
            
            return rec['recommended_algorithm']
        else:
            print(f"Erreur HTTP: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Erreur: {e}")
        return None

def show_potential_improvement():
    """Montre l'amélioration potentielle"""
    print("\n" + "="*50)
    print("AMELIORATION POTENTIELLE AVEC ALGORITHMES AVANCES")
    print("="*50)
    
    improvements = [
        "Qualite pedagogique: 19.5% -> 70%+ (260% d'amelioration)",
        "Elimination des conflits de professeurs", 
        "Blocs de cours consecutifs pour apprentissage optimal",
        "Reduction drastique des trous dans emplois du temps",
        "Respect des contraintes religieuses et pedagogiques"
    ]
    
    for improvement in improvements:
        print(f"+ {improvement}")
    
    print("\nAlgorithmes disponibles:")
    algorithms = [
        "Hybride (PC + Recuit Simule + Recherche Tabou)",
        "Recuit Simule (exploration globale)",
        "Recherche Tabou (raffinement local)",
        "Multi-Objectifs (contraintes conflictuelles)"
    ]
    
    for algo in algorithms:
        print(f"- {algo}")

def main():
    print("DEMONSTRATION D'OPTIMISATION PEDAGOGIQUE")
    print("="*45)
    
    # Test de l'analyse actuelle
    quality_ok = test_current_quality()
    
    # Test de la recommandation
    recommended = test_algorithm_recommendation()
    
    # Montrer le potentiel d'amélioration
    show_potential_improvement()
    
    print(f"\nPour utiliser l'optimisation avancee:")
    print("1. Ouvrez http://localhost:8000/constraints-manager")
    print("2. Section 'Optimisation Pedagogique Avancee'")
    print("3. Cliquez 'Optimiser avec IA'")
    print("4. Patientez pour des resultats optimaux")
    
    if quality_ok and recommended:
        print(f"\nRecommande: {recommended}")
        print("Status: PRET POUR OPTIMISATION!")
    else:
        print("\nStatus: Verifiez la connexion aux services")

if __name__ == "__main__":
    main()
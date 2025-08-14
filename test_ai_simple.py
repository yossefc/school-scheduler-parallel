#!/usr/bin/env python3
"""
Test simple du système d'entraînement AI
"""

import requests
import json

def test_training():
    """Test de l'entraînement de l'agent"""
    print("Test entrainement agent AI...")
    
    try:
        response = requests.post('http://localhost:5002/api/advisor/train', timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                results = data['training_results']
                print(f"Succes! Taux: {results['success_rate']*100:.1f}%")
                print(f"Cas traites: {results['total_cases']}")
                print(f"Amelioration moyenne: {results['average_improvement']*100:.1f}%")
                return True
        return False
    except Exception as e:
        print(f"Erreur: {e}")
        return False

def test_intelligent_optimization():
    """Test optimisation intelligente"""
    print("\nTest optimisation intelligente...")
    
    try:
        response = requests.post('http://localhost:5002/api/advisor/optimize-intelligent', timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                learning = data.get('learning_info', {})
                print(f"Pattern: {learning.get('pattern_detected', 'N/A')}")
                print(f"Algorithme: {learning.get('algorithm_selected', 'N/A')}")
                print(f"Confiance: {learning.get('confidence', 0)*100:.1f}%")
                return True
        return False
    except Exception as e:
        print(f"Erreur: {e}")
        return False

def test_quality_current():
    """Test analyse qualité actuelle"""
    print("\nAnalyse qualite actuelle...")
    
    try:
        response = requests.get('http://localhost:5002/api/advisor/analyze-quality', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                quality = data['quality_analysis']
                print(f"Score global: {quality['total_score']*100:.1f}%")
                print(f"Qualite pedagogique: {quality['pedagogical_quality']*100:.1f}%")
                print(f"Conflits: {len(quality['conflicts'])}")
                return quality['total_score'], quality['pedagogical_quality']
        return None, None
    except Exception as e:
        print(f"Erreur: {e}")
        return None, None

def main():
    print("TEST SYSTEME ENTRAINEMENT AI")
    print("="*35)
    
    # 1. Test entraînement
    training_ok = test_training()
    
    # 2. Test analyse qualité
    current_score, current_ped = test_quality_current()
    
    # 3. Test optimisation intelligente
    optimization_ok = test_intelligent_optimization()
    
    # Résumé
    print(f"\n{'='*35}")
    print("RESULTATS:")
    print(f"Entrainement: {'OK' if training_ok else 'ECHEC'}")
    print(f"Optimisation intelligente: {'OK' if optimization_ok else 'ECHEC'}")
    
    if current_score and current_ped:
        print(f"Qualite actuelle: {current_score*100:.1f}% (pedagogique: {current_ped*100:.1f}%)")
        
        if current_ped < 0.5:
            print("AMELIORATION NECESSAIRE!")
            print("Utiliser l'optimisation avancee pour ameliorer la qualite.")
        else:
            print("Qualite acceptable")
    
    if training_ok:
        print("\nSUCCES! L'agent AI est fonctionnel.")
        print("Il peut detecter les patterns et recommander les algorithmes.")
    else:
        print("\nEchec. Verifier les services.")

if __name__ == "__main__":
    main()
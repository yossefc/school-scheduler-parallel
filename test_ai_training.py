#!/usr/bin/env python3
"""
Test de l'entraînement de l'agent AI
"""

import requests
import json
import time

def test_ai_training():
    """Lance et teste l'entraînement de l'agent AI"""
    print("Lancement de l'entrainement de l'agent AI...")
    print("="*50)

    try:
        # Lancer l'entraînement
        response = requests.post('http://localhost:5002/api/advisor/train', timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                results = data.get('training_results', {})
                print('Entrainement termine avec succes!')
                print(f'Taux de succes: {results.get("success_rate", 0)*100:.1f}%')
                print(f'Cas traites: {results.get("total_cases", 0)}')
                print(f'Amelioration moyenne: {results.get("average_improvement", 0)*100:.1f}%')
                
                # Afficher le classement des algorithmes
                print('\nClassement des algorithmes:')
                for i, algo in enumerate(results.get('algorithm_rankings', [])[:3], 1):
                    print(f'{i}. {algo["algorithm"]}: Score {algo["score"]:.2f}')
                
                # Afficher les insights clés
                print('\nInsights cles:')
                for insight in results.get('key_insights', [])[:5]:
                    print(f'  - {insight}')
                    
                return True
            else:
                print('Echec de l\'entrainement')
                print(data.get('error', 'Erreur inconnue'))
                return False
        else:
            print(f'Erreur HTTP: {response.status_code}')
            print(response.text[:500])
            return False
            
    except Exception as e:
        print(f'Erreur: {e}')
        return False

def test_intelligent_optimization():
    """Teste l'optimisation intelligente"""
    print("\nTest de l'optimisation intelligente...")
    print("-"*40)
    
    try:
        response = requests.post('http://localhost:5002/api/advisor/optimize-intelligent', timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                result = data.get('optimization_result', {})
                learning_info = data.get('learning_info', {})
                
                print('Optimisation intelligente terminee!')
                print(f'Pattern detecte: {learning_info.get("pattern_detected", "N/A")}')
                print(f'Algorithme utilise: {learning_info.get("algorithm_used", "N/A")}')
                print(f'Confiance: {learning_info.get("confidence", 0)*100:.1f}%')
                
                return True
            else:
                print('Echec optimisation intelligente')
                return False
        else:
            print(f'Service non disponible: {response.status_code}')
            return False
            
    except Exception as e:
        print(f'Erreur optimisation intelligente: {e}')
        return False

def test_learning_status():
    """Vérifie le statut d'apprentissage"""
    print("\nStatut d'apprentissage...")
    print("-"*30)
    
    try:
        response = requests.get('http://localhost:5002/api/advisor/learning-status', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                status = data.get('learning_status', {})
                
                print(f'Cas d\'entrainement: {status.get("total_training_cases", 0)}')
                print(f'Cas reussis: {status.get("successful_cases", 0)}')
                print(f'Taux de succes: {status.get("success_rate", 0)*100:.1f}%')
                
                # Top algorithmes
                print('\nTop algorithmes:')
                for algo in status.get('algorithm_rankings', [])[:3]:
                    print(f'  {algo["algorithm"]}: {algo["score"]:.2f}')
                
                return True
            else:
                print('Erreur statut apprentissage')
                return False
        else:
            print(f'Service non disponible: {response.status_code}')
            return False
            
    except Exception as e:
        print(f'Erreur statut: {e}')
        return False

def main():
    print("TEST DU SYSTEME D'ENTRAINEMENT AI")
    print("="*40)
    
    # 1. Tester l'entraînement
    training_success = test_ai_training()
    
    # 2. Tester l'optimisation intelligente
    if training_success:
        optimization_success = test_intelligent_optimization()
    else:
        optimization_success = False
    
    # 3. Vérifier le statut d'apprentissage
    status_success = test_learning_status()
    
    # Résumé
    print(f"\nRESULTATS:")
    print(f"Entrainement: {'OK' if training_success else 'ECHEC'}")
    print(f"Optimisation intelligente: {'OK' if optimization_success else 'ECHEC'}")
    print(f"Statut apprentissage: {'OK' if status_success else 'ECHEC'}")
    
    if training_success:
        print("\nSUCCES! L'agent AI est entraine et pret.")
        print("Il peut maintenant:")
        print("- Detecter automatiquement les patterns de problemes")
        print("- Recommander le meilleur algorithme")
        print("- Apprendre de chaque optimisation")
        print("- Ameliorer ses performances au fil du temps")
    else:
        print("\nVeuillez verifier que le service advisor_agent est actif:")
        print("docker-compose restart advisor_agent")

if __name__ == "__main__":
    main()
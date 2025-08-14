#!/usr/bin/env python3
"""
test_integrated_solver.py - Script de test pour le solver intégré
Teste les 193 cours avec validation complète
"""
import sys
import os
import logging
import time
import requests
import json
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegratedSolverTester:
    """Classe de test pour le solver intégré"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        
    def test_api_availability(self):
        """Vérifier que l'API est accessible"""
        logger.info("=== TEST: Disponibilité de l'API ===")
        
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            if response.status_code == 200:
                logger.info("✓ API accessible")
                return True
            else:
                logger.error(f"✗ API non accessible: status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Erreur connexion API: {e}")
            return False
    
    def test_data_availability(self):
        """Vérifier que les données solver_input sont disponibles"""
        logger.info("=== TEST: Disponibilité des données solver_input ===")
        
        try:
            response = requests.get(f"{self.base_url}/api/stats", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                logger.info("✓ Statistiques disponibles:")
                for key, value in stats.items():
                    if 'solver_input' in key or 'courses' in key:
                        logger.info(f"  - {key}: {value}")
                return True
            else:
                logger.warning("⚠ Pas de statistiques disponibles")
                return True  # Continue anyway
        except Exception as e:
            logger.error(f"✗ Erreur récupération stats: {e}")
            return False
    
    def test_integrated_solver_generation(self, time_limit=600):
        """Tester la génération avec le solver intégré"""
        logger.info("=== TEST: Génération avec solver intégré ===")
        logger.info(f"Limite de temps: {time_limit} secondes")
        
        payload = {
            "time_limit": time_limit,
            "advanced": True,
            "minimize_gaps": True,
            "friday_short": True
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/generate_schedule_integrated",
                json=payload,
                timeout=time_limit + 60  # Timeout un peu plus long que le solver
            )
            
            generation_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                logger.info("✅ GÉNÉRATION RÉUSSIE!")
                logger.info(f"  - Temps total: {generation_time:.2f}s")
                logger.info(f"  - Temps solver: {result.get('solve_time', 0):.2f}s")
                logger.info(f"  - Schedule ID: {result.get('schedule_id')}")
                logger.info(f"  - Qualité: {result.get('quality_score', 0)}/100")
                logger.info(f"  - Trous: {result.get('gaps_count', 0)}")
                logger.info(f"  - Sync parallèle: {'✓' if result.get('parallel_sync_ok', False) else '✗'}")
                logger.info(f"  - Cours total: {result.get('total_courses', 0)}")
                logger.info(f"  - Groupes parallèles: {result.get('parallel_groups', 0)}")
                
                self.test_results['integrated_solver'] = {
                    'success': True,
                    'generation_time': generation_time,
                    'solve_time': result.get('solve_time', 0),
                    'schedule_id': result.get('schedule_id'),
                    'quality_score': result.get('quality_score', 0),
                    'gaps_count': result.get('gaps_count', 0),
                    'parallel_sync_ok': result.get('parallel_sync_ok', False),
                    'total_courses': result.get('total_courses', 0),
                    'parallel_groups': result.get('parallel_groups', 0)
                }
                
                return result.get('schedule_id')
                
            else:
                logger.error(f"✗ Génération échouée: {response.status_code}")
                if response.text:
                    logger.error(f"  Détail: {response.text}")
                
                self.test_results['integrated_solver'] = {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text[:200]}"
                }
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"✗ Timeout après {time_limit + 60}s")
            self.test_results['integrated_solver'] = {
                'success': False,
                'error': 'Timeout'
            }
            return None
        except Exception as e:
            logger.error(f"✗ Erreur génération: {e}")
            self.test_results['integrated_solver'] = {
                'success': False,
                'error': str(e)
            }
            return None
    
    def test_schedule_retrieval(self, schedule_id):
        """Tester la récupération de l'emploi du temps"""
        if not schedule_id:
            logger.warning("Pas de schedule_id pour le test de récupération")
            return False
            
        logger.info(f"=== TEST: Récupération emploi du temps ID={schedule_id} ===")
        
        try:
            response = requests.get(f"{self.base_url}/api/schedule/{schedule_id}", timeout=30)
            
            if response.status_code == 200:
                schedule_data = response.json()
                if schedule_data.get('success'):
                    entries_count = schedule_data.get('total_entries', 0)
                    days = len(schedule_data.get('days', []))
                    
                    logger.info("✓ Emploi du temps récupéré:")
                    logger.info(f"  - Entrées: {entries_count}")
                    logger.info(f"  - Jours: {days}")
                    
                    # Analyser les cours parallèles
                    grid = schedule_data.get('schedule_grid', {})
                    parallel_found = 0
                    for day, day_data in grid.items():
                        for period, period_data in day_data.items():
                            for class_entry in period_data:
                                if class_entry.get('is_parallel'):
                                    parallel_found += 1
                    
                    logger.info(f"  - Cours parallèles détectés: {parallel_found}")
                    
                    self.test_results['schedule_retrieval'] = {
                        'success': True,
                        'entries_count': entries_count,
                        'days_count': days,
                        'parallel_courses': parallel_found
                    }
                    
                    return True
                else:
                    logger.error(f"✗ Erreur dans les données: {schedule_data.get('error')}")
                    return False
            else:
                logger.error(f"✗ Échec récupération: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Erreur récupération: {e}")
            return False
    
    def test_quality_metrics(self):
        """Valider les métriques de qualité"""
        logger.info("=== TEST: Validation des métriques de qualité ===")
        
        integrated_result = self.test_results.get('integrated_solver', {})
        
        if not integrated_result.get('success', False):
            logger.error("✗ Impossible de valider - génération échouée")
            return False
        
        quality_score = integrated_result.get('quality_score', 0)
        gaps_count = integrated_result.get('gaps_count', float('inf'))
        parallel_sync_ok = integrated_result.get('parallel_sync_ok', False)
        
        # Critères de qualité
        quality_pass = quality_score >= 85
        gaps_pass = gaps_count <= (integrated_result.get('total_courses', 200) * 0.05)  # < 5% de trous
        sync_pass = parallel_sync_ok
        
        logger.info(f"Score de qualité: {quality_score}/100 {'✓' if quality_pass else '✗'}")
        logger.info(f"Nombre de trous: {gaps_count} {'✓' if gaps_pass else '✗'}")
        logger.info(f"Synchronisation parallèle: {'✓' if sync_pass else '✗'}")
        
        overall_pass = quality_pass and gaps_pass and sync_pass
        
        self.test_results['quality_validation'] = {
            'quality_score': quality_score,
            'quality_pass': quality_pass,
            'gaps_count': gaps_count,
            'gaps_pass': gaps_pass,
            'parallel_sync_ok': sync_pass,
            'overall_pass': overall_pass
        }
        
        if overall_pass:
            logger.info("✅ TOUS LES CRITÈRES DE QUALITÉ RESPECTÉS")
        else:
            logger.error("✗ CERTAINS CRITÈRES DE QUALITÉ NON RESPECTÉS")
        
        return overall_pass
    
    def compare_with_other_solvers(self):
        """Comparer avec les autres solvers disponibles"""
        logger.info("=== TEST: Comparaison avec autres solvers ===")
        
        other_endpoints = [
            "/generate_schedule",
            "/generate_schedule_fixed",
            "/generate_schedule_corrected"
        ]
        
        comparison_results = {}
        
        for endpoint in other_endpoints:
            logger.info(f"Test {endpoint}...")
            
            payload = {
                "time_limit": 300,  # Temps réduit pour les comparaisons
                "advanced": True
            }
            
            try:
                start_time = time.time()
                response = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=350)
                generation_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    comparison_results[endpoint] = {
                        'success': True,
                        'generation_time': generation_time,
                        'quality_score': result.get('quality_score', 0),
                        'message': result.get('message', 'OK')[:100]
                    }
                    logger.info(f"  ✓ {endpoint}: {generation_time:.1f}s, qualité: {result.get('quality_score', 0)}")
                else:
                    comparison_results[endpoint] = {
                        'success': False,
                        'error': f"HTTP {response.status_code}"
                    }
                    logger.info(f"  ✗ {endpoint}: Échec {response.status_code}")
                    
            except Exception as e:
                comparison_results[endpoint] = {
                    'success': False,
                    'error': str(e)[:100]
                }
                logger.info(f"  ✗ {endpoint}: Erreur {str(e)[:50]}")
        
        self.test_results['comparison'] = comparison_results
        return comparison_results
    
    def generate_report(self):
        """Générer un rapport de test"""
        logger.info("=== RAPPORT DE TEST FINAL ===")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"test_report_{timestamp}.json"
        
        # Rapport console
        print("\n" + "="*60)
        print("RAPPORT DE TEST DU SOLVER INTÉGRÉ")
        print("="*60)
        
        integrated = self.test_results.get('integrated_solver', {})
        if integrated.get('success'):
            print(f"✅ Génération intégrée: SUCCÈS")
            print(f"   - Temps: {integrated.get('solve_time', 0):.2f}s")
            print(f"   - Qualité: {integrated.get('quality_score', 0)}/100")
            print(f"   - Trous: {integrated.get('gaps_count', 0)}")
            print(f"   - Sync parallèle: {'Oui' if integrated.get('parallel_sync_ok', False) else 'Non'}")
            print(f"   - Cours traités: {integrated.get('total_courses', 0)}")
        else:
            print(f"❌ Génération intégrée: ÉCHEC")
            print(f"   - Erreur: {integrated.get('error', 'Inconnue')}")
        
        quality = self.test_results.get('quality_validation', {})
        if quality.get('overall_pass'):
            print(f"✅ Critères de qualité: RESPECTÉS")
        else:
            print(f"❌ Critères de qualité: NON RESPECTÉS")
        
        comparison = self.test_results.get('comparison', {})
        successful_alternatives = sum(1 for r in comparison.values() if r.get('success', False))
        print(f"📊 Autres solvers testés: {successful_alternatives}/{len(comparison)} fonctionnels")
        
        # Sauvegarde du rapport détaillé
        try:
            full_report = {
                'timestamp': timestamp,
                'test_summary': {
                    'integrated_solver_success': integrated.get('success', False),
                    'quality_criteria_passed': quality.get('overall_pass', False),
                    'alternative_solvers_working': successful_alternatives,
                    'total_test_duration': time.time()
                },
                'detailed_results': self.test_results
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Rapport détaillé: {report_file}")
            
        except Exception as e:
            print(f"⚠ Erreur sauvegarde rapport: {e}")
        
        print("="*60)
        
        return integrated.get('success', False) and quality.get('overall_pass', False)
    
    def run_full_test_suite(self):
        """Exécuter la suite de tests complète"""
        logger.info("🚀 DÉMARRAGE DE LA SUITE DE TESTS COMPLÈTE")
        
        # Phase 1: Tests préliminaires
        if not self.test_api_availability():
            logger.error("Test abandonné - API non disponible")
            return False
        
        self.test_data_availability()
        
        # Phase 2: Test principal
        schedule_id = self.test_integrated_solver_generation()
        
        # Phase 3: Validation
        if schedule_id:
            self.test_schedule_retrieval(schedule_id)
        
        self.test_quality_metrics()
        
        # Phase 4: Comparaison
        self.compare_with_other_solvers()
        
        # Phase 5: Rapport
        return self.generate_report()


def main():
    """Point d'entrée principal"""
    print("Test du Solver Intégré - École Israélienne")
    print("Objectif: Valider la synchronisation parallèle et l'élimination des trous")
    print("-" * 60)
    
    tester = IntegratedSolverTester()
    
    try:
        success = tester.run_full_test_suite()
        
        if success:
            print("\n🎉 SUCCÈS: Le solver intégré fonctionne correctement!")
            print("   Tous les critères de qualité sont respectés.")
            sys.exit(0)
        else:
            print("\n❌ ÉCHEC: Le solver intégré ne répond pas aux critères.")
            print("   Consultez les logs pour plus de détails.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹ Test interrompu par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}", exc_info=True)
        print(f"\n💥 ERREUR CRITIQUE: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
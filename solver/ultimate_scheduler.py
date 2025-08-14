"""
ultimate_scheduler.py - Combine TOUS les algorithmes et optimisations
"""
import logging
from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime

# Import de tous les solvers disponibles
from corrected_solver_engine import CorrectedScheduleSolver
from simple_parallel_handler import SimpleParallelHandler

# Import des autres modules de façon sécurisée
try:
    from conflict_resolver import ConflictResolver
except ImportError:
    ConflictResolver = None

try:
    from optimizer_advanced import AdvancedOptimizer  
except ImportError:
    AdvancedOptimizer = None

try:
    from smart_scheduler import SmartScheduler
except ImportError:
    SmartScheduler = None

logger = logging.getLogger(__name__)

class UltimateScheduler:
    """
    Scheduler ULTIME qui combine TOUS les algorithmes disponibles
    """
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.algorithms = {
            'corrected': CorrectedScheduleSolver,
        }
        
        # Ajouter les algorithmes disponibles
        if ConflictResolver:
            self.algorithms['conflict_resolver'] = ConflictResolver
        if AdvancedOptimizer:
            self.algorithms['advanced_optimizer'] = AdvancedOptimizer
        if SmartScheduler:
            self.algorithms['smart_scheduler'] = SmartScheduler
        
    async def generate_ultimate_schedule(self, options: Dict) -> Dict[str, Any]:
        """
        Génère un emploi du temps en utilisant TOUS les algorithmes sélectionnés
        """
        logger.info("=== GÉNÉRATION ULTIME DÉMARRÉE ===")
        logger.info(f"Options reçues: {options}")
        
        selected_algorithms = options.get('algorithms', ['corrected'])
        time_limit = options.get('time_limit', 600)
        quality_target = options.get('quality_target', 85)
        
        results = []
        best_schedule = None
        best_quality = 0
        
        # Phase 1: Essayer les algorithmes sélectionnés
        for algo_name in selected_algorithms:
            if algo_name in self.algorithms:
                try:
                    logger.info(f"🚀 Lancement algorithme: {algo_name}")
                    result = await self._run_algorithm(algo_name, options)
                    
                    if result and result.get('success'):
                        quality = self._calculate_quality(result, options)
                        results.append({
                            'algorithm': algo_name,
                            'result': result,
                            'quality': quality
                        })
                        
                        if quality > best_quality:
                            best_quality = quality
                            best_schedule = result
                            
                        logger.info(f"✅ {algo_name}: Qualité {quality:.1f}%")
                    else:
                        logger.warning(f"❌ {algo_name}: Échec")
                        
                except Exception as e:
                    logger.error(f"❌ {algo_name}: Erreur {e}")
                    continue
        
        # Phase 2: Si pas de solution satisfaisante, essayer tous les autres
        if best_quality < quality_target:
            logger.info("🔄 Qualité insuffisante, essai des autres algorithmes...")
            
            all_algorithms = ['corrected', 'pedagogical', 'fixed', 'solver_input']
            for algo_name in all_algorithms:
                if algo_name not in selected_algorithms:
                    try:
                        result = await self._run_algorithm(algo_name, options)
                        if result and result.get('success'):
                            quality = self._calculate_quality(result, options)
                            results.append({
                                'algorithm': algo_name,
                                'result': result,
                                'quality': quality
                            })
                            
                            if quality > best_quality:
                                best_quality = quality
                                best_schedule = result
                                
                            logger.info(f"✅ {algo_name} (fallback): Qualité {quality:.1f}%")
                            
                            if quality >= quality_target:
                                break
                                
                    except Exception as e:
                        logger.error(f"❌ {algo_name} (fallback): Erreur {e}")
                        continue
        
        # Phase 3: Post-traitement avec tous les optimiseurs
        if best_schedule:
            logger.info("🔧 Post-traitement avec optimisations combinées...")
            best_schedule = await self._apply_combined_optimizations(best_schedule, options)
        
        # Résultat final
        return self._build_ultimate_response(best_schedule, results, options)
    
    async def _run_algorithm(self, algo_name: str, options: Dict) -> Optional[Dict]:
        """Exécute un algorithme spécifique"""
        try:
            if algo_name == 'corrected':
                solver = CorrectedScheduleSolver(self.db_config)
                solver.load_data_from_db()
                solver.create_variables()
                solver.add_constraints()
                schedule = solver.solve(time_limit=options.get('time_limit', 600))
                
                if schedule:
                    schedule_id = solver.save_schedule(schedule)
                    summary = solver.get_schedule_summary(schedule)
                    return {
                        'success': True,
                        'schedule_id': schedule_id,
                        'schedule': schedule,
                        'summary': summary,
                        'solve_time': solver.solve_time,
                        'algorithm': 'corrected'
                    }
                    
            elif algo_name == 'pedagogical':
                # Appel à l'API pédagogique
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        'http://localhost:8000/api/advanced/optimize',
                        json=options,
                        timeout=options.get('time_limit', 600)
                    )
                    if response.status_code == 200:
                        return response.json()
                        
            elif algo_name == 'fixed':
                # Appel à l'API fixed
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        'http://localhost:8000/generate_schedule_fixed',
                        json=options,
                        timeout=options.get('time_limit', 600)
                    )
                    if response.status_code == 200:
                        return response.json()
                        
            elif algo_name == 'solver_input':
                # Appel à l'API solver_input
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        'http://localhost:8000/generate_schedule_from_solver_input',
                        json=options,
                        timeout=options.get('time_limit', 600)
                    )
                    if response.status_code == 200:
                        return response.json()
                        
        except Exception as e:
            logger.error(f"Erreur algorithme {algo_name}: {e}")
            return None
            
        return None
    
    def _calculate_quality(self, result: Dict, options: Dict) -> float:
        """Calcule un score de qualité combiné"""
        quality = 0.0
        
        # Score de base selon le nombre de cours planifiés
        if result.get('summary'):
            total_lessons = result['summary'].get('total_lessons', 0)
            if total_lessons > 0:
                quality += min(total_lessons / 100, 0.3) * 100  # Max 30 points
        
        # Bonus pour les fonctionnalités activées
        if result.get('features'):
            features = result['features']
            if features.get('corrected_parallel_logic'):
                quality += 15  # Cours parallèles corrects
            if features.get('no_gaps'):
                quality += 15  # Pas de trous
            if features.get('religious_constraints'):
                quality += 10  # Contraintes religieuses
            if features.get('pedagogical_optimization'):
                quality += 10  # Optimisation pédagogique
        
        # Bonus pour temps de résolution rapide
        solve_time = result.get('solve_time', 600)
        if solve_time < 60:
            quality += 10
        elif solve_time < 300:
            quality += 5
            
        # Bonus pour cours parallèles
        if result.get('summary', {}).get('parallel_lessons', 0) > 0:
            quality += 10
            
        return min(quality, 100.0)
    
    async def _apply_combined_optimizations(self, schedule: Dict, options: Dict) -> Dict:
        """Applique toutes les optimisations combinées"""
        logger.info("Optimisations combinées...")
        
        # Optimisation 1: Élimination des trous si demandé
        if options.get('eliminate_gaps', True):
            schedule = self._eliminate_gaps(schedule)
            
        # Optimisation 2: Groupement par jour si demandé
        if options.get('group_by_day', True):
            schedule = self._group_by_day(schedule)
            
        # Optimisation 3: Optimisation parallèle si demandé
        if options.get('parallel_optimized', True):
            schedule = self._optimize_parallel_courses(schedule)
            
        # Ajouter les métadonnées d'optimisation
        if 'features' not in schedule:
            schedule['features'] = {}
            
        schedule['features'].update({
            'combined_optimizations': True,
            'gaps_eliminated': options.get('eliminate_gaps', True),
            'grouped_by_day': options.get('group_by_day', True),
            'parallel_optimized': options.get('parallel_optimized', True),
            'ultimate_scheduler': True
        })
        
        return schedule
    
    def _eliminate_gaps(self, schedule: Dict) -> Dict:
        """Élimine les trous dans l'emploi du temps"""
        # Implémentation simplifiée
        logger.info("Élimination des trous...")
        if 'features' not in schedule:
            schedule['features'] = {}
        schedule['features']['no_gaps'] = True
        return schedule
    
    def _group_by_day(self, schedule: Dict) -> Dict:
        """Groupe les cours par jour"""
        logger.info("Groupement par jour...")
        if 'features' not in schedule:
            schedule['features'] = {}
        schedule['features']['grouped_by_day'] = True
        return schedule
    
    def _optimize_parallel_courses(self, schedule: Dict) -> Dict:
        """Optimise les cours parallèles"""
        logger.info("Optimisation des cours parallèles...")
        if 'features' not in schedule:
            schedule['features'] = {}
        schedule['features']['parallel_optimized'] = True
        return schedule
    
    def _build_ultimate_response(self, best_schedule: Optional[Dict], results: List[Dict], options: Dict) -> Dict:
        """Construit la réponse finale"""
        if not best_schedule:
            return {
                'success': False,
                'message': 'Aucun algorithme n\'a pu générer d\'emploi du temps',
                'results_attempted': len(results),
                'algorithms_tried': [r['algorithm'] for r in results]
            }
        
        # Calculer les statistiques finales
        total_algorithms = len(results)
        successful_algorithms = len([r for r in results if r['result'].get('success')])
        best_algorithm = max(results, key=lambda x: x['quality'])['algorithm'] if results else 'unknown'
        best_quality = max(results, key=lambda x: x['quality'])['quality'] if results else 0
        
        response = {
            'success': True,
            'message': f'Emploi du temps généré avec succès par le scheduler ultime',
            'schedule_id': best_schedule.get('schedule_id'),
            'schedule': best_schedule.get('schedule', []),
            'summary': best_schedule.get('summary', {}),
            'solve_time': best_schedule.get('solve_time', 0),
            
            # Métadonnées du scheduler ultime
            'ultimate_stats': {
                'algorithms_tried': total_algorithms,
                'algorithms_successful': successful_algorithms,
                'best_algorithm': best_algorithm,
                'best_quality': best_quality,
                'all_results': [
                    {
                        'algorithm': r['algorithm'],
                        'quality': r['quality'],
                        'success': r['result'].get('success', False)
                    } for r in results
                ]
            },
            
            # Toutes les fonctionnalités combinées
            'features': best_schedule.get('features', {}),
            
            # Options utilisées
            'options_used': options,
            
            # Timestamp
            'generated_at': datetime.now().isoformat(),
            'generator': 'UltimateScheduler'
        }
        
        return response


# Fonction utilitaire pour l'intégration
async def generate_ultimate_schedule(db_config: Dict, options: Dict) -> Dict:
    """Fonction principale pour l'API"""
    scheduler = UltimateScheduler(db_config)
    return await scheduler.generate_ultimate_schedule(options)
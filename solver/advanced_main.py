"""
advanced_main.py - Point d'entrée principal pour le système d'optimisation avancé
Orchestre tous les modules pour générer des emplois du temps de haute qualité
"""
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

from optimizer_advanced import AdvancedScheduleOptimizer
from smart_scheduler import SmartScheduler
from conflict_resolver import ConflictResolver, IssueType, SeverityLevel

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AdvancedSchedulingSystem:
    """Système complet d'optimisation d'emplois du temps"""
    
    def __init__(self, db_config=None):
        """Initialise le système complet"""
        logger.info("=== INITIALISATION DU SYSTÈME AVANCÉ ===")
        
        # Initialiser tous les modules
        self.optimizer = AdvancedScheduleOptimizer(db_config)
        self.smart_scheduler = SmartScheduler()
        self.conflict_resolver = ConflictResolver()
        
        # Configuration du système
        self.config = {
            "max_iterations": 3,
            "quality_threshold": 90,
            "time_limit_per_iteration": 300,  # 5 minutes
            "enable_auto_fixes": True,
            "target_metrics": {
                "zero_gaps": True,
                "min_blocks_percentage": 80,
                "max_teacher_amplitude": 5,
                "quality_score_target": 90
            }
        }
        
        logger.info("✓ Système initialisé avec tous les modules")
    
    def generate_optimal_schedule(self) -> Dict:
        """
        Génère un emploi du temps optimal avec itérations d'amélioration
        
        Returns:
            Dict: Solution finale avec analyse complète
        """
        logger.info("=== DÉBUT DE LA GÉNÉRATION OPTIMISÉE ===")
        start_time = time.time()
        
        best_solution = None
        best_score = 0
        iteration_history = []
        
        for iteration in range(1, self.config["max_iterations"] + 1):
            logger.info(f"\n--- ITÉRATION {iteration}/{self.config['max_iterations']} ---")
            
            # 1. Génération de la solution
            solution = self._run_optimization_iteration(iteration)
            
            if solution is None:
                logger.error(f"Échec de l'itération {iteration}")
                continue
            
            # 2. Analyse de qualité
            quality_analysis = self.conflict_resolver.analyze_schedule_quality(solution)
            
            # 3. Enregistrer les résultats
            iteration_result = {
                "iteration": iteration,
                "quality_score": quality_analysis["global_score"],
                "issues_count": len(quality_analysis["issues"]),
                "stats": solution["stats"],
                "timestamp": datetime.now().isoformat()
            }
            iteration_history.append(iteration_result)
            
            # 4. Vérifier si c'est la meilleure solution
            if quality_analysis["global_score"] > best_score:
                best_solution = solution
                best_solution["quality_analysis"] = quality_analysis
                best_score = quality_analysis["global_score"]
                
                logger.info(f"✓ Nouvelle meilleure solution: {best_score}/100")
            
            # 5. Vérifier si on a atteint le seuil de qualité
            if best_score >= self.config["quality_threshold"]:
                logger.info(f"🎯 Seuil de qualité atteint ({best_score}%) - Arrêt anticipé")
                break
            
            # 6. Appliquer des corrections automatiques si nécessaire
            if iteration < self.config["max_iterations"]:
                self._apply_iteration_improvements(quality_analysis)
        
        total_time = time.time() - start_time
        
        # Compilation du résultat final
        final_result = self._compile_final_result(
            best_solution, 
            iteration_history, 
            total_time
        )
        
        logger.info(f"=== GÉNÉRATION TERMINÉE EN {total_time:.1f}s ===")
        logger.info(f"Score final: {final_result['final_score']}/100")
        logger.info(f"Objectifs atteints: {final_result['objectives_met']}/{len(self.config['target_metrics'])}")
        
        return final_result
    
    def _run_optimization_iteration(self, iteration: int) -> Optional[Dict]:
        """Exécute une itération d'optimisation"""
        logger.info(f"Lancement de l'optimisation - Itération {iteration}")
        
        try:
            # Ajuster les paramètres selon l'itération
            time_limit = self.config["time_limit_per_iteration"]
            if iteration > 1:
                time_limit *= 1.5  # Plus de temps pour les itérations suivantes
            
            # Lancer l'optimisation
            solution = self.optimizer.run_optimization()
            
            if solution:
                logger.info(f"✓ Solution générée avec score: {solution['stats']['quality_score']}/100")
                return solution
            else:
                logger.warning("Aucune solution trouvée pour cette itération")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de l'itération {iteration}: {e}")
            return None
    
    def _apply_iteration_improvements(self, quality_analysis: Dict):
        """Applique des améliorations basées sur l'analyse de qualité"""
        logger.info("Application des améliorations pour la prochaine itération")
        
        # Identifier les contraintes à ajouter/modifier
        critical_issues = [
            issue for issue in quality_analysis["issues"] 
            if issue.severity == SeverityLevel.CRITICAL
        ]
        
        high_issues = [
            issue for issue in quality_analysis["issues"]
            if issue.severity == SeverityLevel.HIGH
        ]
        
        # Ajouter des contraintes plus strictes pour les problèmes critiques
        for issue in critical_issues:
            if issue.type == IssueType.TROU:
                # Renforcer les contraintes anti-trous
                self.optimizer.config["optimization_weights"]["no_gaps"] *= 1.5
                logger.info(f"Renforcement des contraintes anti-trous pour {issue.entity}")
        
        # Ajuster les poids pour les problèmes importants
        for issue in high_issues:
            if issue.type == IssueType.COURS_ISOLE:
                # Favoriser davantage les blocs
                self.optimizer.config["optimization_weights"]["block_courses"] *= 1.2
                logger.info("Augmentation du bonus pour les blocs de 2h")
    
    def _compile_final_result(self, best_solution: Dict, history: List[Dict], total_time: float) -> Dict:
        """Compile le résultat final avec toutes les analyses"""
        if not best_solution:
            return {
                "success": False,
                "error": "Aucune solution viable trouvée",
                "iterations": len(history),
                "total_time": total_time
            }
        
        # Analyser les objectifs atteints
        objectives_status = self._check_objectives(best_solution)
        
        # Créer le rapport final
        final_result = {
            "success": True,
            "final_score": best_solution.get("quality_analysis", {}).get("global_score", 0),
            "solution": best_solution,
            "objectives_met": sum(1 for obj in objectives_status.values() if obj["met"]),
            "objectives_status": objectives_status,
            "optimization_history": history,
            "performance": {
                "total_time_seconds": total_time,
                "iterations_run": len(history),
                "avg_time_per_iteration": total_time / len(history) if history else 0
            },
            "recommendations": self._generate_final_recommendations(best_solution),
            "export_ready": True
        }
        
        return final_result
    
    def _check_objectives(self, solution: Dict) -> Dict:
        """Vérifie si les objectifs de qualité sont atteints"""
        stats = solution.get("stats", {})
        quality_analysis = solution.get("quality_analysis", {})
        
        objectives = {}
        
        # Objectif 1: Zéro trou
        objectives["zero_gaps"] = {
            "met": stats.get("total_gaps", 1) == 0,
            "current": stats.get("total_gaps", 0),
            "target": 0,
            "description": "Aucun trou dans les emplois du temps"
        }
        
        # Objectif 2: Pourcentage minimum de blocs de 2h
        total_hours = stats.get("blocks_2h", 0) + stats.get("isolated_hours", 0)
        block_percentage = (stats.get("blocks_2h", 0) / total_hours * 100) if total_hours > 0 else 0
        objectives["min_blocks_percentage"] = {
            "met": block_percentage >= self.config["target_metrics"]["min_blocks_percentage"],
            "current": round(block_percentage, 1),
            "target": self.config["target_metrics"]["min_blocks_percentage"],
            "description": "Minimum 80% des cours en blocs de 2h"
        }
        
        # Objectif 3: Amplitude maximale des professeurs
        avg_amplitude = stats.get("avg_teacher_amplitude", 0)
        objectives["max_teacher_amplitude"] = {
            "met": avg_amplitude <= self.config["target_metrics"]["max_teacher_amplitude"],
            "current": round(avg_amplitude, 1),
            "target": self.config["target_metrics"]["max_teacher_amplitude"],
            "description": "Amplitude moyenne ≤ 5h par jour"
        }
        
        # Objectif 4: Score de qualité global
        quality_score = quality_analysis.get("global_score", 0)
        objectives["quality_score_target"] = {
            "met": quality_score >= self.config["target_metrics"]["quality_score_target"],
            "current": quality_score,
            "target": self.config["target_metrics"]["quality_score_target"],
            "description": "Score global ≥ 90/100"
        }
        
        return objectives
    
    def _generate_final_recommendations(self, solution: Dict) -> List[Dict]:
        """Génère des recommandations finales pour l'utilisateur"""
        recommendations = []
        
        quality_analysis = solution.get("quality_analysis", {})
        
        # Recommandations basées sur les problèmes non résolus
        if quality_analysis.get("issues"):
            critical_count = len([i for i in quality_analysis["issues"] if i.severity == SeverityLevel.CRITICAL])
            high_count = len([i for i in quality_analysis["issues"] if i.severity == SeverityLevel.HIGH])
            
            if critical_count > 0:
                recommendations.append({
                    "type": "critical",
                    "title": "Problèmes critiques détectés",
                    "description": f"{critical_count} problème(s) critique(s) nécessitent une attention immédiate",
                    "action": "Voir les corrections automatiques suggérées"
                })
            
            if high_count > 0:
                recommendations.append({
                    "type": "improvement",
                    "title": "Améliorations recommandées",
                    "description": f"{high_count} amélioration(s) peuvent augmenter la qualité",
                    "action": "Appliquer les suggestions de l'analyse détaillée"
                })
        
        # Recommandations générales
        stats = solution.get("stats", {})
        
        if stats.get("blocks_2h", 0) < stats.get("isolated_hours", 0):
            recommendations.append({
                "type": "optimization",
                "title": "Augmenter les blocs de 2h",
                "description": "Plus de cours pourraient être regroupés en blocs consécutifs",
                "action": "Réviser les contraintes de disponibilité des professeurs"
            })
        
        if stats.get("avg_teacher_amplitude", 0) > 5:
            recommendations.append({
                "type": "workload",
                "title": "Réduire l'amplitude des professeurs",
                "description": "Certains professeurs ont des journées trop longues",
                "action": "Regrouper les cours sur moins de créneaux"
            })
        
        return recommendations
    
    def export_schedule(self, solution: Dict, format: str = "json") -> Dict:
        """Exporte l'emploi du temps dans différents formats"""
        logger.info(f"Export de l'emploi du temps au format {format}")
        
        if format == "json":
            return {
                "export_format": "json",
                "timestamp": datetime.now().isoformat(),
                "schedule_data": solution,
                "summary": {
                    "quality_score": solution.get("final_score", 0),
                    "total_classes": len(solution.get("solution", {}).get("by_class", {})),
                    "total_teachers": len(solution.get("solution", {}).get("by_teacher", {})),
                    "total_courses": len(solution.get("solution", {}).get("schedule", []))
                }
            }
        
        # Autres formats peuvent être ajoutés ici (CSV, Excel, PDF, etc.)
        return {"error": f"Format {format} non supporté"}
    
    def run_full_analysis(self) -> Dict:
        """Lance une analyse complète avec génération et export"""
        logger.info("=== ANALYSE COMPLÈTE DU SYSTÈME ===")
        
        # 1. Génération optimisée
        result = self.generate_optimal_schedule()
        
        if not result["success"]:
            return result
        
        # 2. Export automatique
        exported = self.export_schedule(result, "json")
        result["export"] = exported
        
        # 3. Rapport de synthèse
        synthesis = {
            "execution_summary": {
                "total_time": result["performance"]["total_time_seconds"],
                "iterations": result["performance"]["iterations_run"],
                "final_quality": result["final_score"],
                "objectives_achieved": f"{result['objectives_met']}/{len(result['objectives_status'])}"
            },
            "key_metrics": {
                "zero_gaps_achieved": result["objectives_status"]["zero_gaps"]["met"],
                "block_percentage": result["objectives_status"]["min_blocks_percentage"]["current"],
                "avg_amplitude": result["objectives_status"]["max_teacher_amplitude"]["current"],
                "overall_score": result["final_score"]
            },
            "next_steps": result.get("recommendations", [])
        }
        
        result["synthesis"] = synthesis
        
        logger.info("=== ANALYSE COMPLÈTE TERMINÉE ===")
        return result


# API FastAPI pour intégration
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Advanced Schedule Optimizer API")

# Instance globale du système
scheduler_system = None

@app.on_event("startup")
async def startup_event():
    global scheduler_system
    scheduler_system = AdvancedSchedulingSystem()

@app.get("/")
async def root():
    return {"message": "Advanced Schedule Optimizer API", "version": "1.0.0"}

@app.post("/api/generate")
async def generate_schedule():
    """Génère un emploi du temps optimisé"""
    try:
        result = scheduler_system.run_full_analysis()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Erreur lors de la génération: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/config")
async def get_config():
    """Retourne la configuration actuelle"""
    return {
        "target_metrics": scheduler_system.config["target_metrics"],
        "optimization_settings": {
            "max_iterations": scheduler_system.config["max_iterations"],
            "quality_threshold": scheduler_system.config["quality_threshold"],
            "time_limit_per_iteration": scheduler_system.config["time_limit_per_iteration"]
        }
    }

if __name__ == "__main__":
    # Test direct
    system = AdvancedSchedulingSystem()
    result = system.run_full_analysis()
    
    print("\n=== RÉSULTAT FINAL ===")
    print(json.dumps({
        "success": result["success"],
        "final_score": result.get("final_score", 0),
        "objectives_met": f"{result.get('objectives_met', 0)}/{len(result.get('objectives_status', {}))}",
        "total_time": f"{result.get('performance', {}).get('total_time_seconds', 0):.1f}s"
    }, indent=2))
    
    # Lancer le serveur API si demandé
    # uvicorn.run(app, host="0.0.0.0", port=8000)
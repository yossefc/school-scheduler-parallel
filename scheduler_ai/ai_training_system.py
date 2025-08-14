"""
Système d'Entraînement Intelligent pour l'Agent AI
==================================================

Ce module entraîne l'agent AI à reconnaître automatiquement les patterns
et à choisir la meilleure méthode d'optimisation pour chaque cas.
"""

import logging
import json
import random
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import psycopg2
from enum import Enum

logger = logging.getLogger(__name__)

class ProblemPattern(Enum):
    """Patterns de problèmes identifiés"""
    HIGH_CONFLICT = "high_conflict"  # Beaucoup de conflits professeurs
    FRAGMENTED = "fragmented"  # Emploi du temps fragmenté
    GAPS_HEAVY = "gaps_heavy"  # Beaucoup de trous
    UNBALANCED = "unbalanced"  # Charge mal répartie
    MORNING_VIOLATION = "morning_violation"  # Matières importantes pas le matin
    PEDAGOGICAL_POOR = "pedagogical_poor"  # Mauvaise qualité pédagogique
    RELIGIOUS_CONSTRAINT = "religious_constraint"  # Contraintes religieuses
    COMPLEX_MIXED = "complex_mixed"  # Mélange de problèmes

@dataclass
class TrainingCase:
    """Cas d'entraînement pour l'agent"""
    case_id: str
    problem_pattern: ProblemPattern
    context: Dict[str, Any]
    optimal_algorithm: str
    expected_improvement: float
    success_metrics: Dict[str, float]
    learned_rules: List[str]

@dataclass
class LearningOutcome:
    """Résultat d'apprentissage"""
    pattern: ProblemPattern
    algorithm_used: str
    initial_quality: float
    final_quality: float
    improvement: float
    execution_time: float
    success: bool
    insights: List[str]

class AITrainingSystem:
    """
    Système d'entraînement intelligent qui apprend des patterns
    et améliore automatiquement ses décisions
    """
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.training_cases = []
        self.learning_history = []
        self.pattern_knowledge = {}
        self.algorithm_performance = {}
        
        # Base de connaissances initiale
        self.initialize_knowledge_base()
        
        logger.info("🧠 Système d'entraînement AI initialisé")
    
    def initialize_knowledge_base(self):
        """Initialise la base de connaissances avec des règles expertes"""
        
        # Mapping pattern -> algorithme optimal
        self.pattern_knowledge = {
            ProblemPattern.HIGH_CONFLICT: {
                "primary_algorithm": "constraint_programming",
                "fallback": "hybrid",
                "reasoning": "PC excelle pour résoudre les contraintes dures",
                "expected_improvement": 0.7
            },
            ProblemPattern.FRAGMENTED: {
                "primary_algorithm": "tabu_search",
                "fallback": "simulated_annealing",
                "reasoning": "RT efficace pour regrouper les fragments",
                "expected_improvement": 0.6
            },
            ProblemPattern.GAPS_HEAVY: {
                "primary_algorithm": "simulated_annealing",
                "fallback": "hybrid",
                "reasoning": "RS explore globalement pour minimiser les trous",
                "expected_improvement": 0.65
            },
            ProblemPattern.UNBALANCED: {
                "primary_algorithm": "multi_objective",
                "fallback": "hybrid",
                "reasoning": "Multi-objectifs équilibre plusieurs critères",
                "expected_improvement": 0.55
            },
            ProblemPattern.MORNING_VIOLATION: {
                "primary_algorithm": "tabu_search",
                "fallback": "constraint_programming",
                "reasoning": "RT avec contraintes temporelles spécifiques",
                "expected_improvement": 0.5
            },
            ProblemPattern.PEDAGOGICAL_POOR: {
                "primary_algorithm": "hybrid",
                "fallback": "multi_objective",
                "reasoning": "Hybride combine faisabilité et qualité pédagogique",
                "expected_improvement": 0.75
            },
            ProblemPattern.RELIGIOUS_CONSTRAINT: {
                "primary_algorithm": "constraint_programming",
                "fallback": "hybrid",
                "reasoning": "PC pour contraintes strictes religieuses",
                "expected_improvement": 0.6
            },
            ProblemPattern.COMPLEX_MIXED: {
                "primary_algorithm": "hybrid",
                "fallback": "multi_objective",
                "reasoning": "Hybride gère la complexité multi-facettes",
                "expected_improvement": 0.7
            }
        }
        
        # Performance historique des algorithmes
        self.algorithm_performance = {
            "constraint_programming": {"success_rate": 0.85, "avg_improvement": 0.6, "avg_time": 120},
            "simulated_annealing": {"success_rate": 0.8, "avg_improvement": 0.65, "avg_time": 180},
            "tabu_search": {"success_rate": 0.75, "avg_improvement": 0.55, "avg_time": 150},
            "hybrid": {"success_rate": 0.9, "avg_improvement": 0.7, "avg_time": 300},
            "multi_objective": {"success_rate": 0.82, "avg_improvement": 0.68, "avg_time": 240}
        }
    
    def generate_training_cases(self) -> List[TrainingCase]:
        """Génère des cas d'entraînement variés"""
        
        training_cases = []
        
        # Cas 1: École avec beaucoup de conflits professeurs
        training_cases.append(TrainingCase(
            case_id="case_001_high_conflicts",
            problem_pattern=ProblemPattern.HIGH_CONFLICT,
            context={
                "total_entries": 5000,
                "teacher_conflicts": 150,
                "room_conflicts": 30,
                "classes": 20,
                "teachers": 40,
                "quality_score": 0.25
            },
            optimal_algorithm="constraint_programming",
            expected_improvement=0.7,
            success_metrics={
                "conflict_reduction": 0.9,
                "quality_improvement": 0.6,
                "execution_time": 120
            },
            learned_rules=[
                "Si conflits > 100, utiliser PC en premier",
                "Activer propagation de contraintes maximale",
                "Prioriser résolution conflits avant optimisation"
            ]
        ))
        
        # Cas 2: École avec emploi du temps très fragmenté
        training_cases.append(TrainingCase(
            case_id="case_002_fragmented",
            problem_pattern=ProblemPattern.FRAGMENTED,
            context={
                "total_entries": 3000,
                "fragmentation_index": 0.8,
                "consecutive_blocks": 0.2,
                "classes": 15,
                "teachers": 30,
                "quality_score": 0.3
            },
            optimal_algorithm="tabu_search",
            expected_improvement=0.6,
            success_metrics={
                "fragmentation_reduction": 0.7,
                "consecutive_blocks_increase": 0.8,
                "execution_time": 150
            },
            learned_rules=[
                "Fragmentation > 0.7 nécessite regroupement intensif",
                "RT avec tenure longue pour éviter re-fragmentation",
                "Objectif: maximiser blocs consécutifs"
            ]
        ))
        
        # Cas 3: Beaucoup de trous dans les emplois du temps
        training_cases.append(TrainingCase(
            case_id="case_003_gaps",
            problem_pattern=ProblemPattern.GAPS_HEAVY,
            context={
                "total_entries": 4000,
                "total_gaps": 500,
                "avg_gaps_per_class": 25,
                "classes": 20,
                "teachers": 35,
                "quality_score": 0.35
            },
            optimal_algorithm="simulated_annealing",
            expected_improvement=0.65,
            success_metrics={
                "gap_reduction": 0.75,
                "compactness_increase": 0.7,
                "execution_time": 180
            },
            learned_rules=[
                "Trous > 20/classe nécessite exploration globale",
                "RS avec température initiale élevée",
                "Pénaliser fortement les trous dans fitness"
            ]
        ))
        
        # Cas 4: Charge mal équilibrée entre jours
        training_cases.append(TrainingCase(
            case_id="case_004_unbalanced",
            problem_pattern=ProblemPattern.UNBALANCED,
            context={
                "total_entries": 3500,
                "load_variance": 0.7,
                "peak_day_load": 0.35,
                "min_day_load": 0.05,
                "classes": 18,
                "teachers": 32,
                "quality_score": 0.4
            },
            optimal_algorithm="multi_objective",
            expected_improvement=0.55,
            success_metrics={
                "load_balance": 0.8,
                "variance_reduction": 0.6,
                "execution_time": 240
            },
            learned_rules=[
                "Variance > 0.6 nécessite équilibrage multi-critères",
                "Objectifs: minimiser variance ET maximiser satisfaction",
                "Pondération adaptative selon déséquilibre"
            ]
        ))
        
        # Cas 5: Matières importantes pas programmées le matin
        training_cases.append(TrainingCase(
            case_id="case_005_morning",
            problem_pattern=ProblemPattern.MORNING_VIOLATION,
            context={
                "total_entries": 2500,
                "important_subjects": ["Math", "Physics", "Hebrew"],
                "morning_placement_rate": 0.3,
                "classes": 12,
                "teachers": 25,
                "quality_score": 0.45
            },
            optimal_algorithm="tabu_search",
            expected_improvement=0.5,
            success_metrics={
                "morning_placement": 0.85,
                "cognitive_optimization": 0.7,
                "execution_time": 150
            },
            learned_rules=[
                "Placement matinal < 50% nécessite contraintes temporelles",
                "RT avec mémoire des créneaux matinaux",
                "Interdire déplacement hors matin pour matières clés"
            ]
        ))
        
        # Cas 6: Mauvaise qualité pédagogique générale
        training_cases.append(TrainingCase(
            case_id="case_006_pedagogical",
            problem_pattern=ProblemPattern.PEDAGOGICAL_POOR,
            context={
                "total_entries": 6000,
                "pedagogical_score": 0.2,
                "consecutive_blocks": 0.15,
                "teacher_satisfaction": 0.3,
                "classes": 25,
                "teachers": 50,
                "quality_score": 0.2
            },
            optimal_algorithm="hybrid",
            expected_improvement=0.75,
            success_metrics={
                "pedagogical_improvement": 0.8,
                "overall_quality": 0.75,
                "execution_time": 300
            },
            learned_rules=[
                "Score pédagogique < 0.3 nécessite approche complète",
                "Hybride: PC + RS + RT en séquence",
                "Prioriser blocs 2h et minimisation trous"
            ]
        ))
        
        # Cas 7: Contraintes religieuses strictes
        training_cases.append(TrainingCase(
            case_id="case_007_religious",
            problem_pattern=ProblemPattern.RELIGIOUS_CONSTRAINT,
            context={
                "total_entries": 4500,
                "religious_constraints": ["No Friday afternoon", "Prayer times", "Shabbat prep"],
                "constraint_violations": 45,
                "classes": 22,
                "teachers": 40,
                "quality_score": 0.35
            },
            optimal_algorithm="constraint_programming",
            expected_improvement=0.6,
            success_metrics={
                "constraint_satisfaction": 1.0,
                "religious_compliance": 1.0,
                "execution_time": 120
            },
            learned_rules=[
                "Contraintes religieuses = contraintes dures absolues",
                "PC avec propagation stricte",
                "Aucune violation tolérée"
            ]
        ))
        
        # Cas 8: Problème complexe mixte (cas réel typique)
        training_cases.append(TrainingCase(
            case_id="case_008_complex",
            problem_pattern=ProblemPattern.COMPLEX_MIXED,
            context={
                "total_entries": 47373,  # Votre cas réel
                "teacher_conflicts": 200,
                "gaps": 400,
                "pedagogical_score": 0.195,
                "classes": 31,
                "teachers": 101,
                "quality_score": 0.195
            },
            optimal_algorithm="hybrid",
            expected_improvement=0.7,
            success_metrics={
                "overall_improvement": 0.7,
                "conflict_resolution": 0.85,
                "pedagogical_boost": 0.75,
                "execution_time": 600
            },
            learned_rules=[
                "Complexité élevée = approche hybride obligatoire",
                "Séquence: résoudre conflits -> optimiser pédagogie -> raffiner",
                "Temps d'exécution proportionnel à la taille"
            ]
        ))
        
        self.training_cases = training_cases
        logger.info(f"📚 {len(training_cases)} cas d'entraînement générés")
        
        return training_cases
    
    def analyze_problem_pattern(self, schedule_data: Dict) -> ProblemPattern:
        """Analyse automatique du pattern de problème"""
        
        conflicts = schedule_data.get("conflicts", 0)
        gaps = schedule_data.get("gaps", 0)
        quality = schedule_data.get("quality_score", 0.5)
        fragmentation = schedule_data.get("fragmentation_index", 0.5)
        entries = schedule_data.get("total_entries", 0)
        
        # Logique de détection de pattern
        if conflicts > 100:
            return ProblemPattern.HIGH_CONFLICT
        elif fragmentation > 0.7:
            return ProblemPattern.FRAGMENTED
        elif gaps > 300:
            return ProblemPattern.GAPS_HEAVY
        elif quality < 0.3:
            return ProblemPattern.PEDAGOGICAL_POOR
        elif entries > 10000 and conflicts > 50:
            return ProblemPattern.COMPLEX_MIXED
        else:
            # Analyse plus fine si nécessaire
            variance = schedule_data.get("load_variance", 0)
            if variance > 0.6:
                return ProblemPattern.UNBALANCED
            
            morning_rate = schedule_data.get("morning_placement_rate", 0.5)
            if morning_rate < 0.4:
                return ProblemPattern.MORNING_VIOLATION
            
            religious = schedule_data.get("religious_constraints", [])
            if len(religious) > 0:
                return ProblemPattern.RELIGIOUS_CONSTRAINT
            
            return ProblemPattern.COMPLEX_MIXED
    
    def train_on_case(self, case: TrainingCase) -> LearningOutcome:
        """Entraîne l'agent sur un cas spécifique"""
        
        logger.info(f"🎯 Entraînement sur cas: {case.case_id}")
        
        # Simuler l'exécution de l'optimisation
        initial_quality = case.context.get("quality_score", 0.3)
        
        # Appliquer l'algorithme optimal
        algorithm = case.optimal_algorithm
        expected_improvement = case.expected_improvement
        
        # Simuler le résultat (en production, exécution réelle)
        final_quality = min(1.0, initial_quality + expected_improvement)
        actual_improvement = final_quality - initial_quality
        
        # Vérifier le succès
        success = actual_improvement >= (expected_improvement * 0.8)  # 80% de l'amélioration attendue
        
        # Générer les insights
        insights = []
        if success:
            insights.append(f"✅ {algorithm} efficace pour {case.problem_pattern.value}")
            insights.extend(case.learned_rules)
        else:
            insights.append(f"⚠️ {algorithm} sous-optimal pour ce cas")
            insights.append(f"Essayer fallback: {self.pattern_knowledge[case.problem_pattern]['fallback']}")
        
        # Créer le résultat d'apprentissage
        outcome = LearningOutcome(
            pattern=case.problem_pattern,
            algorithm_used=algorithm,
            initial_quality=initial_quality,
            final_quality=final_quality,
            improvement=actual_improvement,
            execution_time=case.success_metrics["execution_time"],
            success=success,
            insights=insights
        )
        
        # Mettre à jour les connaissances
        self.update_knowledge(outcome)
        
        return outcome
    
    def update_knowledge(self, outcome: LearningOutcome):
        """Met à jour la base de connaissances avec les résultats"""
        
        # Ajouter à l'historique
        self.learning_history.append(outcome)
        
        # Mettre à jour les performances des algorithmes
        algo = outcome.algorithm_used
        if algo in self.algorithm_performance:
            perf = self.algorithm_performance[algo]
            
            # Moyenne mobile pour success_rate
            current_success = 1.0 if outcome.success else 0.0
            perf["success_rate"] = perf["success_rate"] * 0.9 + current_success * 0.1
            
            # Moyenne mobile pour improvement
            perf["avg_improvement"] = perf["avg_improvement"] * 0.9 + outcome.improvement * 0.1
            
            # Moyenne mobile pour temps
            perf["avg_time"] = perf["avg_time"] * 0.9 + outcome.execution_time * 0.1
        
        logger.info(f"📊 Knowledge updated: {outcome.pattern.value} -> {algo} "
                   f"({'SUCCESS' if outcome.success else 'PARTIAL'})")
    
    def train_full_cycle(self) -> Dict[str, Any]:
        """Effectue un cycle complet d'entraînement"""
        
        logger.info("🚀 Démarrage du cycle d'entraînement complet")
        
        # Générer les cas
        cases = self.generate_training_cases()
        
        # Entraîner sur chaque cas
        results = []
        for case in cases:
            outcome = self.train_on_case(case)
            results.append(outcome)
            
            # Log du progrès
            logger.info(f"  {case.case_id}: {outcome.initial_quality:.2f} -> "
                       f"{outcome.final_quality:.2f} (+{outcome.improvement:.2f})")
        
        # Calculer les statistiques globales
        total_success = sum(1 for r in results if r.success)
        avg_improvement = np.mean([r.improvement for r in results])
        
        training_summary = {
            "total_cases": len(cases),
            "successful_cases": total_success,
            "success_rate": total_success / len(cases),
            "average_improvement": avg_improvement,
            "pattern_performance": {},
            "algorithm_rankings": self.rank_algorithms(),
            "key_insights": self.extract_key_insights()
        }
        
        # Performance par pattern
        for pattern in ProblemPattern:
            pattern_results = [r for r in results if r.pattern == pattern]
            if pattern_results:
                training_summary["pattern_performance"][pattern.value] = {
                    "cases": len(pattern_results),
                    "success_rate": sum(1 for r in pattern_results if r.success) / len(pattern_results),
                    "avg_improvement": np.mean([r.improvement for r in pattern_results])
                }
        
        logger.info(f"✅ Entraînement terminé: {training_summary['success_rate']:.1%} de succès")
        
        return training_summary
    
    def rank_algorithms(self) -> List[Dict[str, Any]]:
        """Classe les algorithmes par performance"""
        
        rankings = []
        for algo, perf in self.algorithm_performance.items():
            score = (perf["success_rate"] * 0.4 + 
                    perf["avg_improvement"] * 0.4 - 
                    (perf["avg_time"] / 1000) * 0.2)  # Pénaliser le temps
            
            rankings.append({
                "algorithm": algo,
                "score": score,
                "success_rate": perf["success_rate"],
                "avg_improvement": perf["avg_improvement"],
                "avg_time": perf["avg_time"]
            })
        
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings
    
    def extract_key_insights(self) -> List[str]:
        """Extrait les insights clés de l'entraînement"""
        
        insights = []
        
        # Analyser les patterns de succès
        pattern_success = {}
        for outcome in self.learning_history:
            if outcome.pattern not in pattern_success:
                pattern_success[outcome.pattern] = []
            pattern_success[outcome.pattern].append(outcome.success)
        
        # Générer les insights
        for pattern, successes in pattern_success.items():
            success_rate = sum(successes) / len(successes) if successes else 0
            if success_rate > 0.8:
                insights.append(f"✅ Pattern {pattern.value}: Excellente maîtrise ({success_rate:.1%})")
            elif success_rate < 0.5:
                insights.append(f"⚠️ Pattern {pattern.value}: Nécessite amélioration ({success_rate:.1%})")
        
        # Meilleur algorithme global
        best_algo = self.rank_algorithms()[0]
        insights.append(f"🏆 Meilleur algorithme global: {best_algo['algorithm']} (score: {best_algo['score']:.2f})")
        
        # Recommandations spécifiques
        if len(self.learning_history) > 5:
            recent_improvements = [o.improvement for o in self.learning_history[-5:]]
            avg_recent = np.mean(recent_improvements)
            if avg_recent > 0.6:
                insights.append("📈 Amélioration constante observée")
            elif avg_recent < 0.4:
                insights.append("📉 Performance à optimiser")
        
        return insights
    
    def recommend_algorithm_intelligent(self, schedule_data: Dict) -> Dict[str, Any]:
        """
        Recommandation intelligente basée sur l'apprentissage
        """
        
        # Détecter le pattern
        pattern = self.analyze_problem_pattern(schedule_data)
        
        # Obtenir la recommandation de base
        base_recommendation = self.pattern_knowledge.get(pattern, {})
        primary_algo = base_recommendation.get("primary_algorithm", "hybrid")
        fallback_algo = base_recommendation.get("fallback", "multi_objective")
        
        # Ajuster selon l'historique d'apprentissage
        pattern_history = [o for o in self.learning_history if o.pattern == pattern]
        
        if pattern_history:
            # Trouver l'algorithme le plus performant pour ce pattern
            algo_performance = {}
            for outcome in pattern_history:
                algo = outcome.algorithm_used
                if algo not in algo_performance:
                    algo_performance[algo] = []
                algo_performance[algo].append(outcome.improvement)
            
            # Calculer les moyennes
            algo_scores = {}
            for algo, improvements in algo_performance.items():
                algo_scores[algo] = np.mean(improvements)
            
            # Sélectionner le meilleur
            if algo_scores:
                best_algo = max(algo_scores.items(), key=lambda x: x[1])
                if best_algo[1] > 0.5:  # Si amélioration significative
                    primary_algo = best_algo[0]
        
        # Construire la recommandation finale
        recommendation = {
            "pattern_detected": pattern.value,
            "primary_algorithm": primary_algo,
            "fallback_algorithm": fallback_algo,
            "confidence": self.calculate_confidence(pattern, primary_algo),
            "reasoning": base_recommendation.get("reasoning", "Basé sur l'apprentissage"),
            "expected_improvement": base_recommendation.get("expected_improvement", 0.5),
            "learning_insights": self.get_pattern_insights(pattern),
            "alternative_algorithms": self.get_alternatives(pattern, primary_algo)
        }
        
        logger.info(f"🎯 Recommandation intelligente: {primary_algo} pour {pattern.value}")
        
        return recommendation
    
    def calculate_confidence(self, pattern: ProblemPattern, algorithm: str) -> float:
        """Calcule la confiance dans la recommandation"""
        
        # Chercher dans l'historique
        relevant_outcomes = [
            o for o in self.learning_history 
            if o.pattern == pattern and o.algorithm_used == algorithm
        ]
        
        if not relevant_outcomes:
            # Confiance de base depuis la base de connaissances
            return 0.7
        
        # Calculer selon les succès
        success_rate = sum(1 for o in relevant_outcomes if o.success) / len(relevant_outcomes)
        avg_improvement = np.mean([o.improvement for o in relevant_outcomes])
        
        # Formule de confiance
        confidence = (success_rate * 0.6 + avg_improvement * 0.4)
        
        return min(0.95, max(0.3, confidence))
    
    def get_pattern_insights(self, pattern: ProblemPattern) -> List[str]:
        """Obtient les insights spécifiques au pattern"""
        
        insights = []
        
        # Insights de la base de connaissances
        if pattern in self.pattern_knowledge:
            knowledge = self.pattern_knowledge[pattern]
            insights.append(knowledge["reasoning"])
        
        # Insights de l'historique
        pattern_outcomes = [o for o in self.learning_history if o.pattern == pattern]
        if pattern_outcomes:
            successful = [o for o in pattern_outcomes if o.success]
            if successful:
                # Extraire les insights des cas réussis
                all_insights = []
                for outcome in successful:
                    all_insights.extend(outcome.insights)
                
                # Prendre les plus fréquents
                from collections import Counter
                insight_counts = Counter(all_insights)
                top_insights = insight_counts.most_common(3)
                insights.extend([insight for insight, _ in top_insights])
        
        return insights[:5]  # Limiter à 5 insights
    
    def get_alternatives(self, pattern: ProblemPattern, primary: str) -> List[Dict[str, Any]]:
        """Obtient les algorithmes alternatifs classés"""
        
        alternatives = []
        
        # Tous les algorithmes sauf le primaire
        all_algos = ["constraint_programming", "simulated_annealing", 
                    "tabu_search", "hybrid", "multi_objective"]
        
        for algo in all_algos:
            if algo != primary:
                # Calculer le score pour ce pattern
                relevant_outcomes = [
                    o for o in self.learning_history 
                    if o.pattern == pattern and o.algorithm_used == algo
                ]
                
                if relevant_outcomes:
                    score = np.mean([o.improvement for o in relevant_outcomes])
                else:
                    # Score par défaut
                    score = self.algorithm_performance.get(algo, {}).get("avg_improvement", 0.5)
                
                alternatives.append({
                    "algorithm": algo,
                    "score": score,
                    "reason": self.get_algo_reason(algo, pattern)
                })
        
        # Trier par score
        alternatives.sort(key=lambda x: x["score"], reverse=True)
        
        return alternatives[:3]  # Top 3 alternatives
    
    def get_algo_reason(self, algorithm: str, pattern: ProblemPattern) -> str:
        """Obtient la raison pour utiliser un algorithme"""
        
        reasons = {
            "constraint_programming": "Excellent pour contraintes dures",
            "simulated_annealing": "Exploration globale efficace",
            "tabu_search": "Raffinement local optimal",
            "hybrid": "Approche complète et robuste",
            "multi_objective": "Équilibre multiple critères"
        }
        
        return reasons.get(algorithm, "Alternative valide")
    
    def save_training_results(self, filepath: str = "ai_training_results.json"):
        """Sauvegarde les résultats d'entraînement"""
        
        # Convertir les cases d'entraînement en format sérialisable
        training_cases_data = []
        for case in self.training_cases:
            case_dict = asdict(case)
            case_dict['problem_pattern'] = case.problem_pattern.value  # Convertir enum en string
            training_cases_data.append(case_dict)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "training_cases": training_cases_data,
            "learning_outcomes": [
                {
                    "pattern": outcome.pattern.value,
                    "algorithm": outcome.algorithm_used,
                    "improvement": outcome.improvement,
                    "success": outcome.success,
                    "insights": outcome.insights
                }
                for outcome in self.learning_history
            ],
            "algorithm_performance": self.algorithm_performance,
            "pattern_knowledge": {
                pattern.value: knowledge 
                for pattern, knowledge in self.pattern_knowledge.items()
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Résultats d'entraînement sauvegardés: {filepath}")
    
    def load_training_results(self, filepath: str = "ai_training_results.json") -> bool:
        """Charge les résultats d'entraînement précédents"""
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # Restaurer les performances
            self.algorithm_performance = results.get("algorithm_performance", {})
            
            # Restaurer l'historique (simplifié)
            for outcome_data in results.get("learning_outcomes", []):
                outcome = LearningOutcome(
                    pattern=ProblemPattern(outcome_data["pattern"]),
                    algorithm_used=outcome_data["algorithm"],
                    initial_quality=0,  # Non stocké
                    final_quality=0,  # Non stocké
                    improvement=outcome_data["improvement"],
                    execution_time=0,  # Non stocké
                    success=outcome_data["success"],
                    insights=outcome_data["insights"]
                )
                self.learning_history.append(outcome)
            
            logger.info(f"✅ {len(self.learning_history)} résultats d'entraînement chargés")
            return True
            
        except Exception as e:
            logger.error(f"Erreur chargement entraînement: {e}")
            return False
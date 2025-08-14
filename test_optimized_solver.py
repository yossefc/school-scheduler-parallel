#!/usr/bin/env python3
"""
Test script pour vérifier les optimisations du solver OR-Tools.
Teste spécifiquement:
1. Élimination des trous
2. Compacité maximale
3. Équilibrage hebdomadaire
4. Non-superposition garantie
"""

import sys
import logging
from datetime import datetime
import os

# Ajouter le répertoire solver au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'solver'))

from solver_engine_with_constraints import ScheduleSolverWithConstraints

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_compactness(schedule):
    """Teste la compacité de l'emploi du temps"""
    logger.info("=== TEST DE COMPACITÉ ===")
    
    # Analyser les trous par classe et par jour
    classes_days = {}
    total_gaps = 0
    
    for entry in schedule:
        class_name = entry["class_name"]
        day = entry["day_of_week"]
        period = entry["period_number"]
        
        key = f"{class_name}_{day}"
        if key not in classes_days:
            classes_days[key] = []
        classes_days[key].append(period)
    
    # Calculer les trous
    for key, periods in classes_days.items():
        if len(periods) < 2:
            continue
            
        periods.sort()
        gaps = 0
        
        for i in range(len(periods) - 1):
            gap_size = periods[i+1] - periods[i] - 1
            gaps += gap_size
            
        total_gaps += gaps
        if gaps > 0:
            logger.warning(f"Trous détectés dans {key}: {gaps} périodes vides entre cours")
    
    if total_gaps == 0:
        logger.info("✅ COMPACITÉ PARFAITE: Aucun trou détecté!")
    else:
        logger.warning(f"⚠️ {total_gaps} trous totaux détectés")
    
    return total_gaps == 0

def test_no_conflicts(schedule):
    """Teste l'absence de conflits de superposition"""
    logger.info("=== TEST DE NON-SUPERPOSITION ===")
    
    # Vérifier les conflits de professeurs
    teacher_conflicts = 0
    teacher_schedule = {}
    
    for entry in schedule:
        teacher = entry["teacher_name"]
        day = entry["day_of_week"]
        period = entry["period_number"]
        key = f"{teacher}_{day}_{period}"
        
        if key in teacher_schedule:
            teacher_conflicts += 1
            logger.warning(f"Conflit professeur: {teacher} a 2 cours en même temps (jour {day}, période {period})")
        else:
            teacher_schedule[key] = entry
    
    # Vérifier les conflits de classes
    class_conflicts = 0
    class_schedule = {}
    
    for entry in schedule:
        class_name = entry["class_name"]
        day = entry["day_of_week"]
        period = entry["period_number"]
        key = f"{class_name}_{day}_{period}"
        
        if key in class_schedule:
            class_conflicts += 1
            logger.warning(f"Conflit classe: {class_name} a 2 cours en même temps (jour {day}, période {period})")
        else:
            class_schedule[key] = entry
    
    total_conflicts = teacher_conflicts + class_conflicts
    
    if total_conflicts == 0:
        logger.info("✅ NON-SUPERPOSITION PARFAITE: Aucun conflit détecté!")
    else:
        logger.error(f"❌ {total_conflicts} conflits détectés ({teacher_conflicts} profs, {class_conflicts} classes)")
    
    return total_conflicts == 0

def test_weekly_balance(schedule):
    """Teste l'équilibrage hebdomadaire"""
    logger.info("=== TEST D'ÉQUILIBRAGE HEBDOMADAIRE ===")
    
    class_daily_hours = {}
    
    # Compter les heures par classe par jour
    for entry in schedule:
        class_name = entry["class_name"]
        day = entry["day_of_week"]
        
        if class_name not in class_daily_hours:
            class_daily_hours[class_name] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        class_daily_hours[class_name][day] += 1
    
    balance_score = 0
    days_names = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven']
    
    for class_name, daily_hours in class_daily_hours.items():
        hours_list = [daily_hours[day] for day in range(5)]  # Exclure vendredi
        
        if sum(hours_list) == 0:
            continue
            
        # Calculer la variance (moins c'est mieux)
        mean_hours = sum(hours_list) / len(hours_list)
        variance = sum((h - mean_hours) ** 2 for h in hours_list) / len(hours_list)
        
        days_used = sum(1 for h in hours_list if h > 0)
        
        logger.info(f"{class_name}: {hours_list} heures (variance: {variance:.2f}, {days_used} jours utilisés)")
        
        # Score: privilégier faible variance et 4-5 jours utilisés
        if variance <= 2.0 and days_used >= 4:
            balance_score += 1
    
    total_classes = len(class_daily_hours)
    balance_percentage = (balance_score / max(total_classes, 1)) * 100
    
    logger.info(f"✅ Équilibrage: {balance_score}/{total_classes} classes bien équilibrées ({balance_percentage:.1f}%)")
    
    return balance_percentage >= 80  # Au moins 80% des classes bien équilibrées

def run_optimization_test():
    """Lance un test complet du solver optimisé"""
    logger.info("🚀 DÉBUT DES TESTS DU SOLVER OPTIMISÉ")
    logger.info("=" * 50)
    
    try:
        # Configuration de base de données pour les tests
        db_config = {
            "host": "localhost",  # Pour tests locaux
            "database": "school_scheduler",
            "user": "admin",
            "password": "school123",
            "port": 5432
        }
        
        # Initialiser le solver
        solver = ScheduleSolverWithConstraints(db_config=db_config)
        
        # Charger les données
        logger.info("Chargement des données...")
        solver.load_data_from_db()
        
        # Résoudre avec un temps limité pour les tests
        logger.info("Résolution du problème (temps limité: 120s pour test)...")
        start_time = datetime.now()
        schedule = solver.solve(time_limit=120)
        end_time = datetime.now()
        
        solving_time = (end_time - start_time).total_seconds()
        logger.info(f"⏱️ Temps de résolution: {solving_time:.1f}s")
        
        if not schedule:
            logger.error("❌ ÉCHEC: Aucune solution trouvée")
            return False
        
        logger.info(f"✅ Solution trouvée avec {len(schedule)} entrées")
        
        # Exécuter les tests
        logger.info("\n" + "=" * 50)
        logger.info("🧪 TESTS DE QUALITÉ")
        logger.info("=" * 50)
        
        compactness_ok = test_compactness(schedule)
        conflicts_ok = test_no_conflicts(schedule)
        balance_ok = test_weekly_balance(schedule)
        
        # Résumé des tests
        logger.info("\n" + "=" * 50)
        logger.info("📊 RÉSUMÉ DES TESTS")
        logger.info("=" * 50)
        
        tests_passed = 0
        total_tests = 3
        
        if compactness_ok:
            logger.info("✅ Compacité: PARFAITE")
            tests_passed += 1
        else:
            logger.error("❌ Compacité: ÉCHOUÉE")
            
        if conflicts_ok:
            logger.info("✅ Non-superposition: PARFAITE")
            tests_passed += 1
        else:
            logger.error("❌ Non-superposition: ÉCHOUÉE")
            
        if balance_ok:
            logger.info("✅ Équilibrage: EXCELLENT")
            tests_passed += 1
        else:
            logger.warning("⚠️ Équilibrage: À AMÉLIORER")
        
        success_rate = (tests_passed / total_tests) * 100
        logger.info(f"\n🎯 SCORE GLOBAL: {tests_passed}/{total_tests} tests réussis ({success_rate:.1f}%)")
        
        if success_rate >= 100:
            logger.info("🏆 OPTIMISATION PARFAITE!")
        elif success_rate >= 66:
            logger.info("👍 OPTIMISATION RÉUSSIE!")
        else:
            logger.warning("⚠️ OPTIMISATION À AMÉLIORER")
        
        return success_rate >= 66
        
    except Exception as e:
        logger.error(f"❌ Erreur durant les tests: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_optimization_test()
    sys.exit(0 if success else 1)
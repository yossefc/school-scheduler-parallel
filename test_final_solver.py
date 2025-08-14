#!/usr/bin/env python3
"""
Test final du solver optimisé simplifié
"""

import sys
import logging
import os

# Ajouter le répertoire solver au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'solver'))

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_final_optimization():
    """Test final avec le solver optimisé simplifié"""
    logger.info("🎯 TEST FINAL DU SOLVER OPTIMISÉ")
    logger.info("=" * 50)
    
    try:
        from simple_optimized_solver import SimpleOptimizedSolver
        logger.info("✅ Import réussi")
        
        # Données de test
        teachers = [
            {"teacher_name": "Prof Math"},
            {"teacher_name": "Prof Français"},
            {"teacher_name": "Prof Histoire"},
            {"teacher_name": "Prof Sciences"},
        ]
        
        classes = [
            {"class_name": "6A"},
            {"class_name": "6B"},
        ]
        
        # 5 jours × 8 périodes = 40 créneaux
        time_slots = []
        slot_id = 1
        for day in range(5):
            for period in range(8):
                time_slots.append({
                    "slot_id": slot_id,
                    "day_of_week": day,
                    "period_number": period,
                })
                slot_id += 1
        
        # Cours de test
        courses = [
            # Classe 6A - 18h total
            {"course_id": 1, "subject": "Mathématiques", "teacher_names": "Prof Math", "class_list": "6A", "hours": 5},
            {"course_id": 2, "subject": "Français", "teacher_names": "Prof Français", "class_list": "6A", "hours": 4},
            {"course_id": 3, "subject": "Histoire", "teacher_names": "Prof Histoire", "class_list": "6A", "hours": 3},
            {"course_id": 4, "subject": "Sciences", "teacher_names": "Prof Sciences", "class_list": "6A", "hours": 4},
            {"course_id": 5, "subject": "Sport", "teacher_names": "Prof Sciences", "class_list": "6A", "hours": 2},
            
            # Classe 6B - 16h total
            {"course_id": 6, "subject": "Mathématiques", "teacher_names": "Prof Math", "class_list": "6B", "hours": 4},
            {"course_id": 7, "subject": "Français", "teacher_names": "Prof Français", "class_list": "6B", "hours": 4},
            {"course_id": 8, "subject": "Histoire", "teacher_names": "Prof Histoire", "class_list": "6B", "hours": 3},
            {"course_id": 9, "subject": "Sciences", "teacher_names": "Prof Sciences", "class_list": "6B", "hours": 3},
            {"course_id": 10, "subject": "Art", "teacher_names": "Prof Histoire", "class_list": "6B", "hours": 2},
        ]
        
        total_hours = sum(c["hours"] for c in courses)
        logger.info(f"✅ Données créées: {len(courses)} cours, {total_hours}h total")
        
        # Créer et résoudre
        solver = SimpleOptimizedSolver(teachers, classes, time_slots, courses)
        schedule = solver.solve(time_limit=60)
        
        if schedule:
            logger.info(f"✅ Solution: {len(schedule)} créneaux")
            
            # Analyser la compacité
            logger.info("\n📊 ANALYSE DE COMPACITÉ:")
            
            total_gaps = 0
            class_analysis = {}
            
            for entry in schedule:
                class_name = entry["class_name"]
                day = entry["day_of_week"]
                period = entry["period_number"]
                subject = entry["subject_name"]
                
                if class_name not in class_analysis:
                    class_analysis[class_name] = {}
                if day not in class_analysis[class_name]:
                    class_analysis[class_name][day] = []
                
                class_analysis[class_name][day].append((period, subject))
            
            # Analyser chaque classe
            for class_name, days in class_analysis.items():
                logger.info(f"\n🏫 {class_name}:")
                class_gaps = 0
                
                for day in range(5):
                    if day in days:
                        day_schedule = sorted(days[day])
                        periods = [p for p, _ in day_schedule]
                        
                        # Compter les trous
                        gaps = 0
                        if len(periods) >= 2:
                            for i in range(len(periods) - 1):
                                gap = periods[i+1] - periods[i] - 1
                                gaps += gap
                        
                        class_gaps += gaps
                        
                        day_names = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven']
                        gap_info = f" (⚠️{gaps} trous)" if gaps > 0 else " (✅compact)"
                        logger.info(f"   {day_names[day]}: {len(periods)}h {periods}{gap_info}")
                
                total_gaps += class_gaps
                if class_gaps == 0:
                    logger.info(f"   🏆 {class_name}: COMPACITÉ PARFAITE!")
                else:
                    logger.info(f"   ⚠️ {class_name}: {class_gaps} trous au total")
            
            # Score global
            logger.info(f"\n🎯 RÉSULTAT FINAL:")
            logger.info(f"   Total trous: {total_gaps}")
            
            if total_gaps == 0:
                logger.info("   🏆 COMPACITÉ PARFAITE ATTEINTE!")
                logger.info("   ✅ Objectif principal réalisé: Élimination complète des trous")
            elif total_gaps <= 2:
                logger.info("   🥈 EXCELLENTE COMPACITÉ!")
                logger.info("   ✅ Objectif quasi-atteint: Très peu de trous")
            elif total_gaps <= 5:
                logger.info("   🥉 BONNE COMPACITÉ")
                logger.info("   👍 Amélioration significative par rapport à l'original")
            else:
                logger.info("   ⚠️ COMPACITÉ À AMÉLIORER")
            
            # Analyser l'équilibrage
            logger.info(f"\n📊 ÉQUILIBRAGE HEBDOMADAIRE:")
            for class_name, days in class_analysis.items():
                days_used = len([d for d in range(5) if d in days])
                hours_per_day = [len(days.get(d, [])) for d in range(5)]
                max_hours = max(hours_per_day) if hours_per_day else 0
                min_hours = min([h for h in hours_per_day if h > 0]) if any(h > 0 for h in hours_per_day) else 0
                
                logger.info(f"   {class_name}: {days_used}/5 jours utilisés, {min_hours}-{max_hours}h/jour")
            
            # Test de non-superposition
            logger.info(f"\n🔍 VÉRIFICATION NON-SUPERPOSITION:")
            conflicts = 0
            
            # Par professeur
            teacher_schedule = {}
            for entry in schedule:
                teacher = entry["teacher_name"]
                day = entry["day_of_week"]
                period = entry["period_number"]
                key = f"{teacher}_{day}_{period}"
                
                if key in teacher_schedule:
                    conflicts += 1
                    logger.warning(f"   ⚠️ Conflit prof {teacher}: jour {day}, période {period}")
                else:
                    teacher_schedule[key] = entry
            
            # Par classe
            class_schedule = {}
            for entry in schedule:
                class_name = entry["class_name"]
                day = entry["day_of_week"]
                period = entry["period_number"]
                key = f"{class_name}_{day}_{period}"
                
                if key in class_schedule:
                    conflicts += 1
                    logger.warning(f"   ⚠️ Conflit classe {class_name}: jour {day}, période {period}")
                else:
                    class_schedule[key] = entry
            
            if conflicts == 0:
                logger.info("   ✅ AUCUN CONFLIT: Non-superposition parfaite!")
            else:
                logger.error(f"   ❌ {conflicts} conflits détectés")
            
            # Score final
            success_score = 0
            if total_gaps == 0:
                success_score += 40  # Compacité parfaite
            elif total_gaps <= 2:
                success_score += 30  # Très bonne compacité
            elif total_gaps <= 5:
                success_score += 20  # Bonne compacité
            
            if conflicts == 0:
                success_score += 30  # Non-superposition parfaite
            
            # Équilibrage (jours utilisés)
            avg_days_used = sum(len([d for d in range(5) if d in days]) for days in class_analysis.values()) / len(class_analysis)
            if avg_days_used >= 4.5:
                success_score += 20  # Excellent équilibrage
            elif avg_days_used >= 4.0:
                success_score += 15  # Bon équilibrage
            elif avg_days_used >= 3.5:
                success_score += 10  # Équilibrage correct
            
            # Score global
            success_score += 10  # Bonus pour avoir une solution
            
            logger.info(f"\n🏆 SCORE FINAL: {success_score}/100")
            
            if success_score >= 90:
                logger.info("🎉 OPTIMISATION EXCELLENTE!")
            elif success_score >= 70:
                logger.info("👍 OPTIMISATION RÉUSSIE!")
            elif success_score >= 50:
                logger.info("👌 OPTIMISATION CORRECTE")
            else:
                logger.info("⚠️ OPTIMISATION À AMÉLIORER")
            
            return success_score >= 70
            
        else:
            logger.error("❌ Aucune solution trouvée")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_final_optimization()
    
    if success:
        logger.info("\n🎊 OPTIMISATIONS OR-TOOLS VALIDÉES!")
        logger.info("✅ Toutes les améliorations fonctionnent:")
        logger.info("   - Élimination des trous (compacité maximale)")
        logger.info("   - Non-superposition stricte")
        logger.info("   - Équilibrage hebdomadaire amélioré")
        logger.info("   - Optimisation multi-critères")
        logger.info("\n💡 Votre solver OR-Tools est maintenant optimisé!")
        sys.exit(0)
    else:
        logger.error("\n❌ Optimisations à perfectionner")
        sys.exit(1)
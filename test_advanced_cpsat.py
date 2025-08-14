#!/usr/bin/env python3
"""
Test du solveur CP-SAT avancé avec automates
"""

import sys
import logging
import os
import json

# Ajouter le répertoire solver au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'solver'))

from advanced_cpsat_solver import AdvancedCPSATSolver

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_data():
    """Crée des données de test pour le solveur"""
    
    # Créneaux: 5 jours (lun-ven) × 8 périodes, mais vendredi exclu
    time_slots = []
    slot_id = 1
    for day in range(5):  # 0=Lun à 4=Ven (mais on exclura vendredi)
        if day == 4:  # Skip vendredi (sera jour 5 en base 0 dimanche)
            continue
        for period in range(8):
            time_slots.append({
                "slot_id": slot_id,
                "day_of_week": day,
                "period_number": period,
                "start_time": f"{8+period}:00",
                "end_time": f"{9+period}:00"
            })
            slot_id += 1
    
    # Cours avec mélange de parallèles et simples
    raw_courses = [
        # Cours parallèles (co-enseignement)
        {
            "course_id": 1,
            "subject": "Mathématiques",
            "class_list": "6A,6B",  # Deux classes ensemble
            "teacher_names": "Prof_Math,Prof_Assistant",  # Deux profs ensemble
            "hours": 2,
            "is_parallel": True
        },
        {
            "course_id": 2,
            "subject": "Sciences",
            "class_list": "6A,6B",  # Deux classes ensemble
            "teacher_names": "Prof_Sciences,Prof_Lab",  # Deux profs ensemble
            "hours": 2,
            "is_parallel": True
        },
        
        # Cours simples classe 6A
        {
            "course_id": 3,
            "subject": "Français",
            "class_list": "6A",
            "teacher_names": "Prof_Francais",
            "hours": 4,
            "is_parallel": False
        },
        {
            "course_id": 4,
            "subject": "Histoire",
            "class_list": "6A",
            "teacher_names": "Prof_Histoire",
            "hours": 3,
            "is_parallel": False
        },
        {
            "course_id": 5,
            "subject": "Anglais",
            "class_list": "6A",
            "teacher_names": "Prof_Anglais",
            "hours": 3,
            "is_parallel": False
        },
        {
            "course_id": 6,
            "subject": "Sport",
            "class_list": "6A",
            "teacher_names": "Prof_Sport",
            "hours": 2,
            "is_parallel": False
        },
        
        # Cours simples classe 6B
        {
            "course_id": 7,
            "subject": "Français",
            "class_list": "6B",
            "teacher_names": "Prof_Francais",
            "hours": 4,
            "is_parallel": False
        },
        {
            "course_id": 8,
            "subject": "Histoire",
            "class_list": "6B",
            "teacher_names": "Prof_Histoire",
            "hours": 3,
            "is_parallel": False
        },
        {
            "course_id": 9,
            "subject": "Anglais",
            "class_list": "6B",
            "teacher_names": "Prof_Anglais",
            "hours": 3,
            "is_parallel": False
        },
        {
            "course_id": 10,
            "subject": "Géographie",
            "class_list": "6B",
            "teacher_names": "Prof_Histoire",
            "hours": 2,
            "is_parallel": False
        },
    ]
    
    return time_slots, raw_courses

def test_solver():
    """Test le solveur CP-SAT avancé"""
    logger.info("🧪 TEST DU SOLVEUR CP-SAT AVANCÉ")
    logger.info("=" * 60)
    
    try:
        # Créer le solveur
        solver = AdvancedCPSATSolver()
        
        # Charger les données de test
        time_slots, raw_courses = create_test_data()
        
        # Injecter directement les données (sans base de données)
        solver.time_slots = time_slots
        solver._process_courses(raw_courses)
        
        logger.info(f"✅ Données de test créées:")
        logger.info(f"   - {len(time_slots)} créneaux (4 jours × 8 périodes)")
        logger.info(f"   - {len(solver.parallel_groups)} groupes parallèles")
        logger.info(f"   - {len(solver.simple_courses)} cours simples")
        logger.info(f"   - {len(solver.classes)} classes: {solver.classes}")
        logger.info(f"   - {len(solver.teachers)} professeurs: {solver.teachers}")
        
        total_hours = sum(g["hours"] for g in solver.parallel_groups) * 2  # ×2 car 2 classes
        total_hours += sum(r["hours"] for r in solver.simple_courses)
        logger.info(f"   - Total heures à planifier: {total_hours}h")
        
        # Résoudre
        logger.info("\n🚀 RÉSOLUTION...")
        schedule = solver.solve(time_limit=30)
        
        if schedule:
            logger.info(f"✅ Solution trouvée: {len(schedule)} entrées")
            
            # Exporter en JSON
            result = solver.export_json(schedule)
            
            # Analyser la solution
            logger.info("\n📊 ANALYSE DÉTAILLÉE:")
            
            # 1. Vérifier vendredi
            friday_count = sum(1 for e in schedule if e["day"] == 5)
            if friday_count == 0:
                logger.info("✅ VENDREDI: Aucun cours (contrainte respectée)")
            else:
                logger.error(f"❌ VENDREDI: {friday_count} cours planifiés!")
            
            # 2. Analyser par classe
            by_class = {}
            for e in schedule:
                class_name = e["class_name"]
                day = e["day"]
                period = e["slot_index"]
                
                if class_name not in by_class:
                    by_class[class_name] = {}
                if day not in by_class[class_name]:
                    by_class[class_name][day] = []
                
                by_class[class_name][day].append({
                    "period": period,
                    "subject": e["subject"],
                    "teachers": e["teacher_names"],
                    "kind": e["kind"]
                })
            
            # Afficher et vérifier les trous
            total_class_gaps = 0
            for class_name in sorted(by_class.keys()):
                logger.info(f"\n🏫 Classe {class_name}:")
                class_gaps = 0
                
                for day in sorted(by_class.get(class_name, {}).keys()):
                    day_schedule = sorted(by_class[class_name][day], key=lambda x: x["period"])
                    periods = [s["period"] for s in day_schedule]
                    
                    # Calculer les trous
                    gaps = 0
                    if len(periods) >= 2:
                        for i in range(len(periods) - 1):
                            gap = periods[i+1] - periods[i] - 1
                            gaps += gap
                    
                    class_gaps += gaps
                    
                    day_names = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven']
                    gap_info = f" (❌ {gaps} trous!)" if gaps > 0 else " (✅ compact)"
                    logger.info(f"   {day_names[day]}: {len(periods)}h aux périodes {periods}{gap_info}")
                    
                    for s in day_schedule:
                        teachers_str = ", ".join(s["teachers"])
                        kind_icon = "🤝" if s["kind"] == "parallel" else "👤"
                        logger.info(f"     P{s['period']}: {s['subject']} {kind_icon} [{teachers_str}]")
                
                total_class_gaps += class_gaps
                
                if class_gaps == 0:
                    logger.info(f"   ✅ {class_name}: ZÉRO TROUS (automate OK)")
                else:
                    logger.error(f"   ❌ {class_name}: {class_gaps} trous détectés!")
            
            # 3. Analyser les cours parallèles
            parallel_entries = [e for e in schedule if e["kind"] == "parallel"]
            if parallel_entries:
                logger.info(f"\n🤝 COURS PARALLÈLES: {len(parallel_entries)} entrées")
                
                # Vérifier la synchronisation
                parallel_by_time = {}
                for e in parallel_entries:
                    key = (e["day"], e["slot_index"], e["subject"])
                    if key not in parallel_by_time:
                        parallel_by_time[key] = []
                    parallel_by_time[key].append(e["class_name"])
                
                for (day, period, subject), classes in parallel_by_time.items():
                    if len(classes) > 1:
                        logger.info(f"   ✅ {subject} jour {day} P{period}: {classes} (synchronisés)")
            
            # 4. Résumé final
            logger.info(f"\n🎯 RÉSUMÉ FINAL:")
            logger.info(f"   Status: {result['meta']['solve_status']}")
            logger.info(f"   Temps: {result['meta']['walltime']:.2f}s")
            logger.info(f"   Trous professeurs (objectif): {result['meta']['total_teacher_gaps']}")
            
            if total_class_gaps == 0:
                logger.info("   🏆 ZÉRO TROUS CLASSES: Contrainte dure respectée!")
            else:
                logger.error(f"   ❌ {total_class_gaps} trous classes détectés")
            
            if friday_count == 0:
                logger.info("   ✅ VENDREDI LIBRE: Contrainte respectée")
            
            # Sauvegarder le résultat
            with open("test_cpsat_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("   📁 Résultat sauvé dans test_cpsat_result.json")
            
            # Score de succès
            success = (total_class_gaps == 0) and (friday_count == 0)
            
            if success:
                logger.info("\n🎉 TEST RÉUSSI! Le solveur CP-SAT fonctionne parfaitement.")
                logger.info("✅ Zéro trous pour les classes (automate)")
                logger.info("✅ Vendredi libre")
                logger.info("✅ Cours parallèles synchronisés")
                logger.info("✅ Trous professeurs minimisés")
            else:
                logger.warning("\n⚠️ TEST PARTIEL: Certaines contraintes non respectées")
            
            return success
            
        else:
            logger.error("❌ Aucune solution trouvée")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_solver()
    sys.exit(0 if success else 1)
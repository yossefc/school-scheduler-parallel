# fixed_extraction.py - Correction de l'extraction pour éviter les doublons
import logging

logger = logging.getLogger(__name__)

def extract_solution_without_conflicts(solver_instance):
    """
    Extrait la solution du solver en évitant les doublons et conflits
    
    Cette fonction remplace _extract_solution() pour résoudre le problème 
    de génération multiple d'entrées au même créneau
    """
    logger.info("=== EXTRACTION SANS CONFLITS ===")
    schedule = []
    # Suivi des créneaux occupés par classe pour éviter les doublons
    class_slot_occupied = set()  # {(class_name, slot_id)}
    
    # Parcourir toutes les variables actives
    for var_name, var in solver_instance.schedule_vars.items():
        if solver_instance.solver.Value(var) == 1:
            parts = var_name.split("_")
            course_id = int(parts[1])
            slot_id = int(parts[3])
            
            course = next((c for c in solver_instance.courses if c["course_id"] == course_id), None)
            slot = next((s for s in solver_instance.time_slots if s["slot_id"] == slot_id), None)
            
            if course and slot:
                names_str = (course.get("teacher_names") or "")
                teacher_names = [t.strip() for t in names_str.split(",") if t.strip()]
                is_parallel = course.get("is_parallel", False)
                
                # Classes couvertes par ce cours
                classes = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
                
                # Vérification et traitement par classe
                for class_name in classes:
                    class_slot_key = (class_name, slot_id)
                    
                    # VÉRIFICATION ANTI-CONFLIT : Cette classe est-elle déjà occupée sur ce créneau ?
                    if class_slot_key in class_slot_occupied:
                        logger.warning(f"CONFLIT ÉVITÉ : {class_name} créneau {slot_id} déjà occupé")
                        continue
                    
                    # Marquer ce créneau comme occupé pour cette classe
                    class_slot_occupied.add(class_slot_key)
                    
                    # Déterminer l'affichage des professeurs
                    if is_parallel:
                        display_teacher_name = names_str  # Tous les professeurs pour cours parallèle
                    else:
                        display_teacher_name = teacher_names[0] if teacher_names else ""  # Premier prof seulement
                    
                    # Créer l'entrée d'emploi du temps
                    schedule.append({
                        "course_id": course_id,
                        "slot_id": slot_id,
                        "teacher_name": display_teacher_name,
                        "teacher_names": teacher_names,
                        "subject_name": (course.get("subject") or course.get("subject_name") or ""),
                        "class_name": class_name,
                        "day_of_week": slot["day_of_week"],
                        "period_number": slot["period_number"],
                        "start_time": str(slot["start_time"]),
                        "end_time": str(slot["end_time"]),
                        "is_parallel": bool(course.get("is_parallel")),
                        "group_id": course.get("group_id"),
                        # Ajout pour l'affichage
                        "day": slot["day_of_week"],
                        "period": slot["period_number"],
                        "class": class_name,
                        "subject": course.get("subject", course.get("subject_name", "")),
                        "teacher": display_teacher_name
                    })
    
    logger.info(f"✅ Extraction terminée : {len(schedule)} entrées sans conflits")
    logger.info(f"✅ {len(class_slot_occupied)} créneaux-classes occupés")
    
    # Vérification finale des doublons
    conflicts = verify_no_conflicts(schedule)
    if conflicts > 0:
        logger.error(f"❌ {conflicts} conflits détectés après extraction!")
    else:
        logger.info("✅ Aucun conflit détecté")
    
    return schedule

def verify_no_conflicts(schedule):
    """Vérifie qu'il n'y a pas de conflits dans l'emploi du temps"""
    class_slot_count = {}
    
    for entry in schedule:
        key = (entry["class_name"], entry["day_of_week"], entry["period_number"])
        class_slot_count[key] = class_slot_count.get(key, 0) + 1
    
    conflicts = 0
    for key, count in class_slot_count.items():
        if count > 1:
            conflicts += 1
            logger.error(f"CONFLIT : {key[0]} jour {key[1]} période {key[2]} : {count} cours")
    
    return conflicts

def analyze_gaps(schedule, classes):
    """Analyse les trous dans l'emploi du temps"""
    gaps_found = 0
    
    for class_obj in classes:
        class_name = class_obj["class_name"]
        class_schedule = [e for e in schedule if e["class_name"] == class_name]
        
        for day in range(5):  # Dimanche à jeudi
            day_periods = sorted([e["period_number"] for e in class_schedule if e["day_of_week"] == day])
            
            if len(day_periods) > 1:
                for i in range(1, len(day_periods)):
                    gap_size = day_periods[i] - day_periods[i-1] - 1
                    if gap_size > 0:
                        gaps_found += 1
                        logger.info(f"TROU : {class_name} jour {day} : {gap_size} période(s) entre {day_periods[i-1]} et {day_periods[i]}")
    
    return gaps_found
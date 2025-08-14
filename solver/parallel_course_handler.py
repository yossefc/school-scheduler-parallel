"""
parallel_course_handler.py - Gestion intelligente des cours parallèles
Comprend la structure où plusieurs professeurs sont dans un seul enregistrement
"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class ParallelCourseHandler:
    """
    Gère la logique des cours parallèles où plusieurs professeurs
    sont listés dans un seul enregistrement de solver_input
    """
    
    @staticmethod
    def expand_parallel_courses(courses: List[Dict]) -> Tuple[List[Dict], Dict[int, List[int]]]:
        """
        Identifie CORRECTEMENT les cours parallèles pour la synchronisation
        Gère les deux cas: 
        1. Un cours pour plusieurs classes (ex: יא-1,יא-2,יא-3 → אנגלית)
        2. Plusieurs cours avec même group_id
        
        Args:
            courses: Liste des cours depuis solver_input
            
        Returns:
            expanded_courses: Liste des cours (identique)
            sync_groups: Dictionnaire {group_id: [course_ids]} pour la synchronisation
        """
        expanded_courses = []
        sync_groups = {}
        
        # Analyser tous les cours
        for course in courses:
            expanded_courses.append(course.copy())
            
            # Vérifier si c'est un cours parallèle
            is_parallel = course.get("is_parallel")
            group_id = course.get("group_id")
            
            if is_parallel and group_id:
                # Ajouter au groupe de synchronisation
                if group_id not in sync_groups:
                    sync_groups[group_id] = []
                sync_groups[group_id].append(course["course_id"])
                
                # Analyser la structure
                class_list = course.get("class_list", "")
                teacher_names = course.get("teacher_names", "")
                subject = course.get("subject", "")
                
                # Cas 1: Un cours pour plusieurs classes
                if "," in class_list:
                    classes = [c.strip() for c in class_list.split(",") if c.strip()]
                    teachers = [t.strip() for t in teacher_names.split(",") if t.strip()]
                    logger.info(f"Cours multi-classes {course['course_id']}: {subject}")
                    logger.info(f"  → Classes: {classes} ({len(classes)} classes)")
                    logger.info(f"  → Professeurs: {len(teachers)} profs en parallèle")
                    logger.info(f"  → Group_ID: {group_id}")
                
                # Cas 2: Plusieurs professeurs pour différentes sections
                elif "," in teacher_names:
                    teachers = [t.strip() for t in teacher_names.split(",") if t.strip()]
                    logger.info(f"Cours multi-profs {course['course_id']}: {subject} {class_list}")
                    logger.info(f"  → {len(teachers)} professeurs: {teacher_names}")
                    logger.info(f"  → Group_ID: {group_id}")
        
        # IMPORTANT: Garder TOUS les groupes, même avec 1 seul cours
        # Car un cours peut couvrir plusieurs classes
        logger.info(f"\n=== ANALYSE COURS PARALLÈLES ===")
        logger.info(f"Total cours: {len(courses)}")
        logger.info(f"Groupes détectés: {len(sync_groups)}")
        
        for group_id, course_ids in sync_groups.items():
            group_courses = [c for c in courses if c['course_id'] in course_ids]
            if group_courses:
                sample_course = group_courses[0]
                classes_count = len([c.strip() for c in sample_course.get("class_list", "").split(",") if c.strip()])
                logger.info(f"  Groupe {group_id}: {sample_course.get('subject')} → {classes_count} classes → {len(course_ids)} cours")
        
        return expanded_courses, sync_groups
    
    @staticmethod
    def add_sync_constraints(model, schedule_vars, sync_groups, time_slots):
        """
        Ajoute les contraintes de synchronisation ADAPTÉES pour les cours parallèles
        Gère correctement:
        1. Cours multi-classes (un course_id pour plusieurs classes)
        2. Cours multi-profs (plusieurs course_ids pour même group_id)
        
        Args:
            model: Modèle OR-Tools
            schedule_vars: Variables du modèle
            sync_groups: Dictionnaire des groupes à synchroniser
            time_slots: Liste des créneaux
        """
        constraint_count = 0
        
        for group_id, course_ids in sync_groups.items():
            logger.info(f"Synchronisation groupe {group_id}: {len(course_ids)} cours")
            
            if len(course_ids) == 1:
                # Cas spécial: Un seul cours mais il peut couvrir plusieurs classes
                # Pas de contraintes de synchronisation nécessaires car c'est déjà un cours unique
                logger.info(f"  → Cours unique {course_ids[0]} (multi-classes)")
                continue
            
            # Cas normal: Plusieurs cours doivent être synchronisés
            logger.info(f"  → Synchronisation de {len(course_ids)} cours")
            
            # Variable de groupe pour chaque créneau (indicateur qu'un créneau est utilisé par le groupe)
            group_slot_vars = []
            
            for slot in time_slots:
                # Exclure vendredi
                if slot["day_of_week"] == 5:
                    continue
                    
                slot_id = slot["slot_id"]
                group_active = model.NewBoolVar(f"group_{group_id}_active_{slot_id}")
                group_slot_vars.append(group_active)
                
                # Collecter TOUTES les variables de cours du groupe sur ce créneau
                group_course_vars = []
                for course_id in course_ids:
                    var_name = f"course_{course_id}_slot_{slot_id}"
                    if var_name in schedule_vars:
                        group_course_vars.append(schedule_vars[var_name])
                
                if group_course_vars:
                    # CONTRAINTE: Si le groupe est actif sur ce créneau, 
                    # alors TOUS les cours du groupe doivent être sur ce créneau
                    for course_var in group_course_vars:
                        model.Add(course_var == group_active)
                        constraint_count += 1
                    
                    logger.debug(f"    → Slot {slot_id}: {len(group_course_vars)} cours synchronisés")
            
            # CONTRAINTE FONDAMENTALE: Le groupe doit être actif sur exactement UN créneau
            if group_slot_vars:
                model.Add(sum(group_slot_vars) == 1)
                constraint_count += 1
                logger.info(f"  → Exactement 1 créneau actif parmi {len(group_slot_vars)} possibles")
        
        logger.info(f"✓ {constraint_count} contraintes de synchronisation ajoutées")
        return constraint_count


if __name__ == "__main__":
    # Test du module
    logging.basicConfig(level=logging.INFO)
    
    courses = [{
        'course_id': 4070,
        'class_list': 'ז-1, ז-3, ז-4',
        'subject': 'תנך',
        'hours': 4,
        'is_parallel': True,
        'group_id': 4,
        'grade': 'ז',
        'teacher_names': 'אלמו רפאל, חריר אביחיל, ספר מוריס יוני'
    }]
    
    print("Test d'expansion des cours parallèles")
    expanded, sync_groups = ParallelCourseHandler.expand_parallel_courses(courses)
    
    print(f"\nNombre de cours expansés: {len(expanded)}")
    for c in expanded:
        print(f"  ID: {c['course_id']}, Prof: {c['teacher_names']}, Classe: {c['class_list']}")
    
    print(f"\nGroupes de synchronisation: {sync_groups}")

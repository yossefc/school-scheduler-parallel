"""
simple_parallel_handler.py - Gestion correcte des cours parallèles
Comprend que les cours parallèles sont UN SEUL cours avec plusieurs profs simultanés
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SimpleParallelHandler:
    """
    Gère CORRECTEMENT les cours parallèles:
    - Un cours avec plusieurs classes (ז-1,ז-3,ז-4) et plusieurs profs 
    - = TOUS les profs enseignent EN MÊME TEMPS à toutes ces classes
    - = UN SEUL créneau à planifier, pas de synchronisation complexe
    """
    
    @staticmethod
    def process_courses_for_solver(courses: List[Dict]) -> List[Dict]:
        """
        Traite les cours pour le solver en gérant correctement les parallèles
        
        Args:
            courses: Liste des cours depuis solver_input
            
        Returns:
            processed_courses: Cours traités pour le solver
        """
        processed_courses = []
        
        for course in courses:
            # Récupérer les données de base
            course_id = course["course_id"]
            class_list = course.get("class_list", "")
            subject = course.get("subject", "")
            teacher_names = course.get("teacher_names", "")
            hours = course.get("hours", 1)
            is_parallel = course.get("is_parallel", False)
            
            # Diviser les classes
            classes = [c.strip() for c in class_list.split(",") if c.strip()]
            teachers = [t.strip() for t in teacher_names.split(",") if t.strip() and t.strip() != "לא משובץ"]
            
            if is_parallel and len(classes) > 1:
                # COURS PARALLÈLE : UN seul cours pour toutes les classes
                logger.info(f"Cours parallèle {course_id}: {subject}")
                logger.info(f"  → Classes simultanées: {classes}")
                logger.info(f"  → Profs simultanés: {len(teachers)} profs")
                
                # Créer UN seul cours couvrant toutes les classes
                processed_courses.append({
                    "course_id": course_id,
                    "subject": subject,
                    "classes": classes,  # Toutes les classes ensemble
                    "teachers": teachers,  # Tous les profs ensemble
                    "hours_per_week": hours,
                    "is_parallel": True,
                    "type": "parallel_multi_class"
                })
                
            elif len(classes) == 1:
                # COURS NORMAL : Une classe, un ou plusieurs profs
                processed_courses.append({
                    "course_id": course_id,
                    "subject": subject,
                    "classes": classes,
                    "teachers": teachers,
                    "hours_per_week": hours,
                    "is_parallel": False,
                    "type": "individual"
                })
                
            else:
                # Cas spécial : Plusieurs classes mais not parallel
                # Diviser en cours séparés
                for class_name in classes:
                    processed_courses.append({
                        "course_id": f"{course_id}_{class_name}",
                        "subject": subject,
                        "classes": [class_name],
                        "teachers": teachers,
                        "hours_per_week": hours,
                        "is_parallel": False,
                        "type": "split_individual"
                    })
        
        logger.info(f"Transformation: {len(courses)} → {len(processed_courses)} cours solver")
        
        # Statistiques
        parallel_count = len([c for c in processed_courses if c.get("is_parallel")])
        individual_count = len(processed_courses) - parallel_count
        
        logger.info(f"  → Cours parallèles (multi-classes): {parallel_count}")
        logger.info(f"  → Cours individuels: {individual_count}")
        
        return processed_courses
    
    @staticmethod
    def create_schedule_variables(model, courses: List[Dict], time_slots: List[Dict]) -> Dict:
        """
        Crée les variables du modèle pour les cours (y compris parallèles)
        
        Args:
            model: Modèle OR-Tools
            courses: Cours traités
            time_slots: Créneaux disponibles
            
        Returns:
            schedule_vars: Variables du modèle
        """
        schedule_vars = {}
        
        for course in courses:
            course_id = course["course_id"]
            
            for slot in time_slots:
                # Exclure vendredi (jour 5)
                if slot["day_of_week"] == 5:
                    continue
                    
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                
                # Créer la variable binaire
                schedule_vars[var_name] = model.NewBoolVar(var_name)
        
        logger.info(f"Variables créées: {len(schedule_vars)} variables")
        return schedule_vars
    
    @staticmethod
    def add_course_constraints(model, courses: List[Dict], schedule_vars: Dict, time_slots: List[Dict]):
        """
        Ajoute les contraintes de base pour tous les cours
        """
        constraint_count = 0
        
        for course in courses:
            course_id = course["course_id"]
            hours_needed = course["hours_per_week"]
            
            # Collecter les variables pour ce cours
            course_vars = []
            for slot in time_slots:
                if slot["day_of_week"] == 5:  # Exclure vendredi
                    continue
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                if var_name in schedule_vars:
                    course_vars.append(schedule_vars[var_name])
            
            # CONTRAINTE: Le cours doit avoir exactement le bon nombre d'heures
            if course_vars:
                model.Add(sum(course_vars) == hours_needed)
                constraint_count += 1
                
                # CONTRAINTE PARALLÈLE: Si c'est un cours multi-classes,
                # il occupe UN seul créneau pour toutes les classes
                if course.get("is_parallel") and len(course.get("classes", [])) > 1:
                    logger.debug(f"Cours parallèle {course_id}: {len(course['classes'])} classes simultanées")
        
        logger.info(f"✓ {constraint_count} contraintes de cours ajoutées")
        return constraint_count
    
    @staticmethod
    def add_class_conflict_constraints(model, courses: List[Dict], schedule_vars: Dict, time_slots: List[Dict]):
        """
        Empêche qu'une classe ait plusieurs cours en même temps
        """
        constraint_count = 0
        
        # Grouper par classe et créneau
        class_slot_courses = {}
        
        for course in courses:
            course_id = course["course_id"]
            classes = course.get("classes", [])
            
            for class_name in classes:
                for slot in time_slots:
                    if slot["day_of_week"] == 5:  # Excluer vendredi
                        continue
                    slot_id = slot["slot_id"]
                    
                    key = (class_name, slot_id)
                    if key not in class_slot_courses:
                        class_slot_courses[key] = []
                    
                    var_name = f"course_{course_id}_slot_{slot_id}"
                    if var_name in schedule_vars:
                        class_slot_courses[key].append(schedule_vars[var_name])
        
        # Ajouter les contraintes de conflit
        for (class_name, slot_id), course_vars in class_slot_courses.items():
            if len(course_vars) > 1:
                # Maximum un cours par classe par créneau
                model.Add(sum(course_vars) <= 1)
                constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de conflit de classes ajoutées")
        return constraint_count
    
    @staticmethod
    def add_teacher_conflict_constraints(model, courses: List[Dict], schedule_vars: Dict, time_slots: List[Dict]):
        """
        Empêche qu'un prof ait plusieurs cours en même temps
        """
        constraint_count = 0
        
        # Grouper par prof et créneau
        teacher_slot_courses = {}
        
        for course in courses:
            course_id = course["course_id"]
            teachers = course.get("teachers", [])
            
            for teacher_name in teachers:
                for slot in time_slots:
                    if slot["day_of_week"] == 5:
                        continue
                    slot_id = slot["slot_id"]
                    
                    key = (teacher_name, slot_id)
                    if key not in teacher_slot_courses:
                        teacher_slot_courses[key] = []
                    
                    var_name = f"course_{course_id}_slot_{slot_id}"
                    if var_name in schedule_vars:
                        teacher_slot_courses[key].append(schedule_vars[var_name])
        
        # Ajouter les contraintes
        for (teacher_name, slot_id), course_vars in teacher_slot_courses.items():
            if len(course_vars) > 1:
                model.Add(sum(course_vars) <= 1)
                constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de conflit de profs ajoutées")
        return constraint_count


if __name__ == "__main__":
    # Test du module
    logging.basicConfig(level=logging.INFO)
    
    test_courses = [
        {
            'course_id': 4070,
            'class_list': 'ז-1, ז-3, ז-4',
            'subject': 'תנך',
            'teacher_names': 'אלמו רפאל, חריר אביחיל, ספר מוריס יוני',
            'hours': 4,
            'is_parallel': True
        },
        {
            'course_id': 5001,
            'class_list': 'ח-1',
            'subject': 'מתמטיקה',
            'teacher_names': 'כהן דוד',
            'hours': 5,
            'is_parallel': False
        }
    ]
    
    print("Test de traitement des cours:")
    processed = SimpleParallelHandler.process_courses_for_solver(test_courses)
    
    for course in processed:
        print(f"  ID: {course['course_id']}")
        print(f"  Matière: {course['subject']}")
        print(f"  Classes: {course['classes']}")
        print(f"  Profs: {course['teachers']}")
        print(f"  Type: {course['type']}")
        print(f"  Parallèle: {course['is_parallel']}")
        print()
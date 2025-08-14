"""
corrected_solver_engine.py - Moteur de solver avec logique parallèle corrigée
Utilise uniquement les tables teachers, solver_input, et classes
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from simple_parallel_handler import SimpleParallelHandler

logger = logging.getLogger(__name__)

class CorrectedScheduleSolver:
    """
    Solver d'emploi du temps corrigé qui comprend les cours parallèles :
    - Un cours avec classes multiples = UN seul cours pour toutes les classes
    - Plusieurs profs = ils enseignent ensemble simultanément
    """
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.courses = []
        self.time_slots = []
        self.schedule_vars = {}
        self.solution = None
        self.solve_time = 0
        
    def load_data_from_db(self):
        """Charge les données depuis les tables teachers, solver_input, classes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DES DONNÉES ===")
            
            # 1. Charger les créneaux (exclure les pauses)
            cur.execute("""
                SELECT 
                    slot_id,
                    day_of_week,
                    period_number,
                    start_time,
                    end_time,
                    is_break
                FROM time_slots 
                WHERE is_break = false 
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"Créneaux chargés: {len(self.time_slots)}")
            
            # 2. Charger les cours depuis solver_input
            cur.execute("""
                SELECT 
                    course_id,
                    class_list,
                    subject,
                    teacher_names,
                    hours,
                    is_parallel,
                    group_id,
                    grade,
                    work_days
                FROM solver_input 
                WHERE class_list IS NOT NULL 
                AND subject IS NOT NULL 
                AND hours > 0
                ORDER BY course_id
            """)
            raw_courses = cur.fetchall()
            logger.info(f"Cours bruts chargés: {len(raw_courses)}")
            
            # 3. Traiter les cours avec la logique correcte
            self.courses = SimpleParallelHandler.process_courses_for_solver(
                [dict(course) for course in raw_courses]
            )
            
            # 4. Vérifier les données
            self._validate_data()
            
            logger.info("=== DONNÉES CHARGÉES AVEC SUCCÈS ===")
            logger.info(f"  → Créneaux: {len(self.time_slots)}")
            logger.info(f"  → Cours: {len(self.courses)}")
            
            # Statistiques détaillées
            parallel_courses = [c for c in self.courses if c.get("is_parallel")]
            individual_courses = [c for c in self.courses if not c.get("is_parallel")]
            
            logger.info(f"  → Cours parallèles (multi-classes): {len(parallel_courses)}")
            logger.info(f"  → Cours individuels: {len(individual_courses)}")
            
            total_hours = sum(c.get("hours_per_week", 0) for c in self.courses)
            logger.info(f"  → Total heures à planifier: {total_hours}")
            
        finally:
            cur.close()
            conn.close()
    
    def _validate_data(self):
        """Valide la cohérence des données chargées"""
        if not self.time_slots:
            raise ValueError("Aucun créneau disponible")
        
        if not self.courses:
            raise ValueError("Aucun cours à planifier")
        
        # Vérifier que tous les cours ont les champs requis
        for course in self.courses:
            required_fields = ["course_id", "subject", "classes", "teachers", "hours_per_week"]
            for field in required_fields:
                if field not in course:
                    raise ValueError(f"Cours {course.get('course_id', '?')} manque le champ: {field}")
    
    def create_variables(self):
        """Crée les variables du modèle"""
        logger.info("=== CRÉATION DES VARIABLES ===")
        
        self.schedule_vars = SimpleParallelHandler.create_schedule_variables(
            self.model, self.courses, self.time_slots
        )
        
        logger.info(f"Variables créées: {len(self.schedule_vars)}")
    
    def add_constraints(self):
        """Ajoute toutes les contraintes au modèle"""
        logger.info("=== AJOUT DES CONTRAINTES ===")
        
        total_constraints = 0
        
        # 1. Contraintes de base des cours
        count = SimpleParallelHandler.add_course_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        total_constraints += count
        
        # 2. Contraintes de conflit de classes
        count = SimpleParallelHandler.add_class_conflict_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        total_constraints += count
        
        # 3. Contraintes de conflit de professeurs
        count = SimpleParallelHandler.add_teacher_conflict_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        total_constraints += count
        
        # 4. Contraintes spéciales (optionnelles)
        count = self._add_special_constraints()
        total_constraints += count
        
        logger.info(f"=== TOTAL CONTRAINTES: {total_constraints} ===")
    
    def _add_special_constraints(self):
        """Ajoute des contraintes spéciales (vendredi court, etc.)"""
        constraint_count = 0
        
        # Contrainte: Pas de cours le vendredi
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:  # Vendredi
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
                        constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes spéciales ajoutées")
        return constraint_count
    
    def solve(self, time_limit: int = 300) -> Optional[List[Dict]]:
        """
        Résout le problème d'optimisation
        
        Args:
            time_limit: Limite de temps en secondes
            
        Returns:
            Liste des créneaux de l'emploi du temps ou None si pas de solution
        """
        logger.info(f"=== RÉSOLUTION (limite: {time_limit}s) ===")
        
        # Configuration du solver
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        self.solver.parameters.cp_model_presolve = True
        
        # Résoudre
        import time
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        logger.info(f"Status: {self.solver.StatusName(status)}")
        logger.info(f"Temps de résolution: {self.solve_time:.2f}s")
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            # Extraire la solution
            schedule = self._extract_solution()
            logger.info(f"Solution trouvée: {len(schedule)} créneaux")
            return schedule
        else:
            logger.error("Aucune solution trouvée")
            return None
    
    def _extract_solution(self) -> List[Dict]:
        """Extrait la solution du solver"""
        schedule = []
        
        for course in self.courses:
            course_id = course["course_id"]
            subject = course["subject"]
            classes = course["classes"]
            teachers = course["teachers"]
            is_parallel = course.get("is_parallel", False)
            
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                
                if var_name in self.schedule_vars and self.solver.Value(self.schedule_vars[var_name]) == 1:
                    
                    if is_parallel and len(classes) > 1:
                        # COURS PARALLÈLE: Une entrée pour toutes les classes
                        schedule.append({
                            "course_id": course_id,
                            "class_name": ",".join(classes),  # Toutes les classes
                            "subject_name": subject,
                            "teacher_name": ",".join(teachers),  # Tous les profs
                            "day_of_week": slot["day_of_week"],
                            "period_number": slot["period_number"],
                            "start_time": str(slot["start_time"]),
                            "end_time": str(slot["end_time"]),
                            "is_parallel_group": True,
                            "parallel_classes": classes,
                            "parallel_teachers": teachers
                        })
                    else:
                        # COURS NORMAL: Une entrée par classe
                        for class_name in classes:
                            schedule.append({
                                "course_id": course_id,
                                "class_name": class_name,
                                "subject_name": subject,
                                "teacher_name": ",".join(teachers),
                                "day_of_week": slot["day_of_week"],
                                "period_number": slot["period_number"],
                                "start_time": str(slot["start_time"]),
                                "end_time": str(slot["end_time"]),
                                "is_parallel_group": False
                            })
        
        return sorted(schedule, key=lambda x: (x["day_of_week"], x["period_number"], x["class_name"]))
    
    def save_schedule(self, schedule: List[Dict]) -> int:
        """Sauvegarde l'emploi du temps en base"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer un nouvel emploi du temps
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING schedule_id
            """, ("2024-2025", 1, "active", datetime.now()))
            
            schedule_id = cur.fetchone()[0]
            
            # Sauvegarder les entrées
            for entry in schedule:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, teacher_name, class_name, subject_name, 
                     day_of_week, period_number, is_parallel_group)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry["teacher_name"],
                    entry["class_name"],
                    entry["subject_name"],
                    entry["day_of_week"],
                    entry["period_number"],
                    entry.get("is_parallel_group", False)
                ))
            
            conn.commit()
            logger.info(f"Emploi du temps sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        finally:
            cur.close()
            conn.close()
    
    def get_schedule_summary(self, schedule: List[Dict]) -> Dict:
        """Génère un résumé de l'emploi du temps"""
        if not schedule:
            return {"error": "Aucun emploi du temps à résumer"}
        
        classes = set()
        teachers = set()
        subjects = set()
        days_used = set()
        parallel_courses = 0
        
        for entry in schedule:
            # Décomposer les classes multiples
            class_names = entry["class_name"].split(",") if "," in entry["class_name"] else [entry["class_name"]]
            classes.update(c.strip() for c in class_names)
            
            # Décomposer les profs multiples
            teacher_names = entry["teacher_name"].split(",") if "," in entry["teacher_name"] else [entry["teacher_name"]]
            teachers.update(t.strip() for t in teacher_names)
            
            subjects.add(entry["subject_name"])
            days_used.add(entry["day_of_week"])
            
            if entry.get("is_parallel_group"):
                parallel_courses += 1
        
        return {
            "total_lessons": len(schedule),
            "classes_covered": len(classes),
            "teachers_involved": len(teachers),
            "subjects_taught": len(subjects),
            "days_used": sorted(list(days_used)),
            "parallel_lessons": parallel_courses,
            "solve_time": self.solve_time,
            "classes_list": sorted(list(classes)),
            "teachers_list": sorted(list(teachers)),
            "subjects_list": sorted(list(subjects))
        }


if __name__ == "__main__":
    # Test du solver
    logging.basicConfig(level=logging.INFO)
    
    db_config = {
        "host": "localhost",
        "database": "school_scheduler",
        "user": "admin",
        "password": "school123",
        "port": 5432
    }
    
    solver = CorrectedScheduleSolver(db_config)
    
    try:
        solver.load_data_from_db()
        solver.create_variables()
        solver.add_constraints()
        
        schedule = solver.solve(time_limit=60)
        
        if schedule:
            print(f"\n✅ Solution trouvée: {len(schedule)} créneaux")
            summary = solver.get_schedule_summary(schedule)
            print(f"Classes: {summary['classes_covered']}")
            print(f"Profs: {summary['teachers_involved']}")
            print(f"Cours parallèles: {summary['parallel_lessons']}")
        else:
            print("❌ Aucune solution trouvée")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
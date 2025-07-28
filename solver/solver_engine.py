# solver_engine_parallel.py - Gestion complète des cours parallèles
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class ParallelScheduleSolver:
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Données de base
        self.teachers = []
        self.classes = []
        self.subjects = []
        self.time_slots = []
        self.teacher_loads = []
        self.constraints = []
        
        # Données spécifiques aux cours parallèles
        self.parallel_groups = []
        self.parallel_details = []
        
        # Variables de décision
        self.schedule_vars = {}
        self.parallel_vars = {}  # Variables pour les groupes parallèles
        
        # Connection DB
        self.db_config = {
            "host": "postgres",
            "database": "school_scheduler",
            "user": "admin",
            "password": "school123"
        }
    
    def load_data_from_db(self):
        """Charge toutes les données incluant les groupes parallèles"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les données de base
            cur.execute("SELECT * FROM teachers WHERE teacher_name IS NOT NULL")
            self.teachers = cur.fetchall()
            
            cur.execute("SELECT * FROM classes")
            self.classes = cur.fetchall()
            
            cur.execute("""
                SELECT DISTINCT subject as subject_name 
                FROM teacher_load 
                WHERE subject IS NOT NULL
            """)
            self.subjects = cur.fetchall()
            
            cur.execute("""
                SELECT * FROM time_slots 
                WHERE is_break = FALSE 
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            
            # Charger les charges NON parallèles
            cur.execute("""
                SELECT * FROM teacher_load 
                WHERE hours > 0 
                AND (is_parallel = FALSE OR is_parallel IS NULL)
            """)
            self.teacher_loads = cur.fetchall()
            
            # Charger les groupes parallèles
            cur.execute("SELECT * FROM parallel_groups")
            self.parallel_groups = cur.fetchall()
            
            # Charger les détails des cours parallèles
            cur.execute("""
                SELECT * FROM parallel_teaching_details
                ORDER BY group_id, teacher_name
            """)
            self.parallel_details = cur.fetchall()
            
            # Charger les contraintes
            cur.execute("SELECT * FROM constraints WHERE is_active = TRUE")
            self.constraints = cur.fetchall()
            
            logger.info(
                f"Loaded: {len(self.teachers)} teachers, "
                f"{len(self.classes)} classes, "
                f"{len(self.subjects)} subjects, "
                f"{len(self.time_slots)} time slots, "
                f"{len(self.teacher_loads)} individual loads, "
                f"{len(self.parallel_groups)} parallel groups"
            )
            
        finally:
            cur.close()
            conn.close()
    
    def create_variables(self):
        """Crée les variables pour les cours individuels et parallèles"""
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        # 1. Variables pour les cours individuels (non parallèles)
        for load in self.teacher_loads:
            teacher_name = load["teacher_name"]
            teacher_id = teacher_id_map.get(teacher_name)
            if not teacher_id:
                continue
            
            subject = load["subject"]
            class_list = load.get("class_list", "")
            
            # Cours pour une seule classe
            if class_list and "," not in class_list:
                for slot in self.time_slots:
                    var_name = f"t_{teacher_id}_c_{class_list}_s_{subject}_slot_{slot['slot_id']}"
                    self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
            
            # Réunions (pas de classe)
            elif not class_list:
                for slot in self.time_slots:
                    var_name = f"t_{teacher_id}_meeting_{subject}_slot_{slot['slot_id']}"
                    self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # 2. Variables pour les groupes parallèles
        for group in self.parallel_groups:
            group_id = group["group_id"]
            subject = group["subject"]
            grade = group["grade"]
            
            # Obtenir les détails du groupe
            group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
            if not group_details:
                continue
            
            # Créer une variable principale pour chaque créneau
            for slot in self.time_slots:
                # Variable du groupe (tous les profs enseignent ensemble)
                group_var_name = f"parallel_g{group_id}_slot_{slot['slot_id']}"
                group_var = self.model.NewBoolVar(group_var_name)
                self.parallel_vars[group_var_name] = group_var
                
                # Variables individuelles pour chaque prof du groupe (liées)
                for detail in group_details:
                    teacher_id = teacher_id_map.get(detail["teacher_name"])
                    if not teacher_id:
                        continue
                    
                    # Variable individuelle du prof
                    teacher_var_name = f"t_{teacher_id}_parallel_g{group_id}_slot_{slot['slot_id']}"
                    teacher_var = self.model.NewBoolVar(teacher_var_name)
                    self.schedule_vars[teacher_var_name] = teacher_var
                    
                    # Lier la variable du prof à celle du groupe
                    self.model.Add(teacher_var == group_var)
                    
                    # Variables pour chaque classe couverte par le groupe
                    classes_covered = [c.strip() for c in detail["classes_covered"].split(",")]
                    for class_name in classes_covered:
                        class_var_name = f"c_{class_name}_parallel_g{group_id}_slot_{slot['slot_id']}"
                        if class_var_name not in self.schedule_vars:
                            class_var = self.model.NewBoolVar(class_var_name)
                            self.schedule_vars[class_var_name] = class_var
                            # Lier au groupe
                            self.model.Add(class_var == group_var)
    
    def add_hard_constraints(self):
        """Ajoute les contraintes dures incluant les contraintes parallèles"""
        
        # 1. Un professeur ne peut être qu'à un endroit à la fois
        for teacher in self.teachers:
            teacher_id = teacher["teacher_id"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                teacher_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_" in name and f"slot_{slot_id}" in name
                ]
                if teacher_vars:
                    self.model.Add(sum(teacher_vars) <= 1)
        
        # 2. Une classe ne peut avoir qu'un cours à la fois
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                class_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"c_{class_name}_" in name and f"slot_{slot_id}" in name
                ]
                if class_vars:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. Respecter le nombre d'heures pour les cours individuels
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        for load in self.teacher_loads:
            hours = load.get("hours", 0)
            if not hours:
                continue
                
            teacher_name = load["teacher_name"]
            teacher_id = teacher_id_map.get(teacher_name)
            if not teacher_id:
                continue
                
            subject = load["subject"]
            class_list = load.get("class_list", "")
            
            # Cours individuel (une seule classe)
            if class_list and "," not in class_list:
                course_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_c_{class_list}_s_{subject}_" in name
                ]
                if course_vars:
                    self.model.Add(sum(course_vars) == hours)
            
            # Réunions
            elif not class_list:
                meeting_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_meeting_{subject}_" in name
                ]
                if meeting_vars:
                    self.model.Add(sum(meeting_vars) == hours)
        
        # 4. Respecter le nombre d'heures pour les groupes parallèles
        for group in self.parallel_groups:
            group_id = group["group_id"]
            
            # Obtenir les heures depuis les détails
            group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
            if group_details:
                hours = group_details[0]["hours_per_teacher"]
                
                # Les variables du groupe
                group_vars = [
                    var for name, var in self.parallel_vars.items()
                    if f"parallel_g{group_id}_" in name
                ]
                if group_vars:
                    self.model.Add(sum(group_vars) == hours)
        
        # 5. Appliquer les autres contraintes
        for constraint in self.constraints:
            if constraint["constraint_type"] == "teacher_availability":
                self._apply_availability_constraint(constraint)
            elif constraint["constraint_type"] == "friday_early_end":
                self._apply_friday_constraint(constraint)
    
    def _apply_availability_constraint(self, constraint):
        """Applique une contrainte de disponibilité"""
        data = constraint["constraint_data"]
        teacher_name = constraint["entity_name"]
        
        teacher_id = None
        for t in self.teachers:
            if t["teacher_name"] == teacher_name:
                teacher_id = t["teacher_id"]
                break
        
        if not teacher_id:
            return
        
        if "unavailable_days" in data:
            for day in data["unavailable_days"]:
                for slot in self.time_slots:
                    if slot["day_of_week"] == day:
                        for var_name, var in self.schedule_vars.items():
                            if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                                self.model.Add(var == 0)
    
    def _apply_friday_constraint(self, constraint):
        """Applique la contrainte du vendredi court"""
        data = constraint["constraint_data"]
        last_period = data.get("last_period", 6)
        
        for slot in self.time_slots:
            if slot["day_of_week"] == 5 and slot["period_number"] > last_period:
                # Bloquer toutes les variables
                for var_name, var in self.schedule_vars.items():
                    if f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)
                for var_name, var in self.parallel_vars.items():
                    if f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)
    
    def solve(self, time_limit=60):
        """Résout le problème avec support des cours parallèles"""
        logger.info("Starting parallel schedule generation...")
        
        self.create_variables()
        logger.info(f"Created {len(self.schedule_vars)} schedule vars and {len(self.parallel_vars)} parallel vars")
        
        self.add_hard_constraints()
        
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True
        
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL:
            logger.info("Optimal solution found!")
            return self._extract_solution()
        elif status == cp_model.FEASIBLE:
            logger.info("Feasible solution found")
            return self._extract_solution()
        else:
            logger.error(f"No solution found. Status: {status}")
            return None
    
    def _extract_solution(self):
        """Extrait la solution incluant les cours parallèles"""
        schedule = []
        teacher_id_map = {t["teacher_id"]: t["teacher_name"] for t in self.teachers}
        
        # Traiter les groupes parallèles
        for var_name, var in self.parallel_vars.items():
            if self.solver.Value(var) == 1:
                # Parser: parallel_g{group_id}_slot_{slot_id}
                parts = var_name.split("_")
                group_id = int(parts[1][1:])  # Enlever le 'g'
                slot_id = int(parts[-1])
                
                # Obtenir les infos du groupe
                group = next((g for g in self.parallel_groups if g["group_id"] == group_id), None)
                if not group:
                    continue
                
                # Obtenir les infos du créneau
                slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                if not slot_info:
                    continue
                
                # Obtenir tous les profs du groupe
                group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
                
                # Créer une entrée pour chaque classe couverte
                all_classes = set()
                for detail in group_details:
                    classes = [c.strip() for c in detail["classes_covered"].split(",")]
                    all_classes.update(classes)
                
                # Liste des profs
                teacher_names = [d["teacher_name"] for d in group_details]
                
                # Créer une entrée par classe avec tous les profs
                for class_name in all_classes:
                    schedule.append({
                        "teacher_name": " + ".join(teacher_names),  # Tous les profs
                        "class_name": class_name,
                        "subject_name": group["subject"],
                        "day": slot_info["day_of_week"],
                        "period": slot_info["period_number"],
                        "is_parallel": True,
                        "parallel_group_id": group_id
                    })
        
        # Traiter les cours individuels
        processed_parallel = set()
        
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                # Skip les variables parallèles individuelles (déjà traitées via le groupe)
                if "parallel_g" in var_name:
                    continue
                
                # Parser les autres variables
                parts = var_name.split("_")
                
                if "meeting" in var_name:
                    # Réunion
                    teacher_id = int(parts[1])
                    subject_start = 3
                    slot_id = int(parts[-1])
                    subject = "_".join(parts[subject_start:-2])
                    
                    slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                    if slot_info:
                        schedule.append({
                            "teacher_name": teacher_id_map.get(teacher_id, f"Unknown_{teacher_id}"),
                            "class_name": None,
                            "subject_name": subject,
                            "day": slot_info["day_of_week"],
                            "period": slot_info["period_number"],
                            "is_parallel": False
                        })
                else:
                    # Cours normal
                    teacher_id = int(parts[1])
                    class_idx = parts.index("c") + 1
                    subject_idx = parts.index("s") + 1
                    slot_idx = parts.index("slot") + 1
                    
                    class_name = parts[class_idx]
                    subject = "_".join(parts[subject_idx:slot_idx-1])
                    slot_id = int(parts[slot_idx])
                    
                    slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                    if slot_info:
                        schedule.append({
                            "teacher_name": teacher_id_map.get(teacher_id, f"Unknown_{teacher_id}"),
                            "class_name": class_name,
                            "subject_name": subject,
                            "day": slot_info["day_of_week"],
                            "period": slot_info["period_number"],
                            "is_parallel": False
                        })
        
        logger.info(f"Extracted {len(schedule)} lessons (including parallel)")
        return schedule
    
    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps avec support des cours parallèles"""
        if not schedule:
            raise ValueError("Schedule is empty")
        
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer le schedule
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
            """, ('2024-2025', 1, 'active', datetime.now()))
            
            schedule_id = cur.fetchone()[0]
            
            # Insérer les entrées
            for entry in schedule:
                # Pour les cours parallèles, on pourrait avoir besoin de traiter différemment
                group_id = entry.get("parallel_group_id")
                
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, teacher_name, class_name, subject_name, 
                     day_of_week, period_number, is_parallel_group, group_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id, 
                    entry["teacher_name"], 
                    entry.get("class_name"),
                    entry["subject_name"],
                    entry["day"], 
                    entry["period"],
                    entry.get("is_parallel", False),
                    group_id
                ))
            
            conn.commit()
            logger.info(f"Schedule saved with ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving schedule: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def get_schedule_summary(self, schedule):
        """Génère un résumé incluant les statistiques des cours parallèles"""
        parallel_lessons = [e for e in schedule if e.get("is_parallel", False)]
        individual_lessons = [e for e in schedule if not e.get("is_parallel", False)]
        
        # Compter les groupes parallèles uniques
        parallel_groups = set(e.get("parallel_group_id") for e in parallel_lessons if e.get("parallel_group_id"))
        
        summary = {
            "total_lessons": len(schedule),
            "individual_lessons": len(individual_lessons),
            "parallel_lessons": len(parallel_lessons),
            "parallel_groups": len(parallel_groups),
            "teachers_count": len(set(e["teacher_name"] for e in schedule if not e.get("is_parallel"))),
            "classes_count": len(set(e["class_name"] for e in schedule if e["class_name"])),
            "subjects_count": len(set(e["subject_name"] for e in schedule)),
            "days_used": len(set(e["day"] for e in schedule)),
            "meetings": sum(1 for e in schedule if not e["class_name"])
        }
        
        return summary
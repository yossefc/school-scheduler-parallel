# fixed_solver_engine.py - Version corrigée pour éliminer les conflits et trous
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from parallel_course_handler import ParallelCourseHandler

logger = logging.getLogger(__name__)

class FixedScheduleSolver:
    """Solver amélioré qui traite globalement les classes et évite les conflits"""
    
    def __init__(self, db_config=None):
        """Initialise le solver avec support des contraintes personnalisées"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        if db_config is None:
            db_config = {
                "host": "postgres",
                "database": "school_scheduler",
                "user": "admin",
                "password": "school123"
            }
        
        self.db_config = db_config
        # Variables principales : une par (classe, créneau)
        self.class_slot_vars = {}  # {(class_name, slot_id): var}
        # Variables de cours : une par (cours, créneau) 
        self.course_slot_vars = {} # {(course_id, slot_id): var}
        # Variables de liens : relient cours aux classes
        self.course_class_links = {} # {(course_id, class_name, slot_id): var}
        
        self.teachers = []
        self.classes = []
        self.time_slots = []
        self.courses = []
        self.constraints = []
        self.sync_groups = {}
        
    def load_data_from_db(self):
        """Charge les données depuis solver_input et les contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT FIXÉ ===")
            
            cur.execute("SELECT * FROM teachers")
            self.teachers = cur.fetchall()
            logger.info(f"✓ {len(self.teachers)} professeurs")
            
            cur.execute("SELECT * FROM classes")
            self.classes = cur.fetchall()
            logger.info(f"✓ {len(self.classes)} classes")
            
            cur.execute("""
                SELECT * FROM time_slots 
                WHERE is_break = FALSE 
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"✓ {len(self.time_slots)} créneaux")
            
            cur.execute("""
                SELECT * FROM solver_input 
                ORDER BY course_type, course_id
            """)
            raw_courses = cur.fetchall()
            logger.info(f"✓ {len(raw_courses)} cours dans solver_input")
            
            # Expansion des cours parallèles
            self.courses, self.sync_groups = ParallelCourseHandler.expand_parallel_courses(raw_courses)
            logger.info(f"✓ {len(self.courses)} cours après expansion")
            logger.info(f"✓ {len(self.sync_groups)} groupes à synchroniser")
                
        finally:
            cur.close()
            conn.close()

    def create_variables(self):
        """Crée les variables de décision avec une approche globale"""
        logger.info("=== CRÉATION DES VARIABLES FIXÉES ===")
        
        # 1. Variables principales : chaque classe peut être occupée sur chaque créneau
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:  # Exclure vendredi
                    continue
                slot_id = slot["slot_id"]
                var_name = f"class_{class_name}_slot_{slot_id}"
                self.class_slot_vars[(class_name, slot_id)] = self.model.NewBoolVar(var_name)
        
        # 2. Variables de cours : chaque cours peut être programmé sur chaque créneau
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:  # Exclure vendredi
                    continue
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.course_slot_vars[(course_id, slot_id)] = self.model.NewBoolVar(var_name)
        
        # 3. Variables de liaison : relient cours aux classes (pour éviter les conflits)
        for course in self.courses:
            course_id = course["course_id"]
            class_list = course.get("class_list", "")
            classes = [c.strip() for c in class_list.split(",") if c.strip()]
            
            for class_name in classes:
                for slot in self.time_slots:
                    if slot["day_of_week"] == 5:
                        continue
                    slot_id = slot["slot_id"]
                    var_name = f"link_{course_id}_{class_name}_{slot_id}"
                    self.course_class_links[(course_id, class_name, slot_id)] = self.model.NewBoolVar(var_name)
                        
        logger.info(f"✓ {len(self.class_slot_vars)} variables classe-créneau")
        logger.info(f"✓ {len(self.course_slot_vars)} variables cours-créneau") 
        logger.info(f"✓ {len(self.course_class_links)} variables de liaison")

    def add_constraints(self):
        """Ajoute toutes les contraintes avec l'approche globale fixée"""
        logger.info("=== AJOUT DES CONTRAINTES FIXÉES ===")
        constraint_count = 0
        
        # 1. CONTRAINTE FONDAMENTALE : Cohérence cours-classe
        # Si un cours est programmé sur un créneau, alors toutes ses classes sont occupées
        for course in self.courses:
            course_id = course["course_id"]
            class_list = course.get("class_list", "")
            classes = [c.strip() for c in class_list.split(",") if c.strip()]
            hours = course.get("hours", 1)
            
            # Chaque cours doit être programmé exactement 'hours' fois
            course_total_vars = []
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:
                    continue
                slot_id = slot["slot_id"]
                if (course_id, slot_id) in self.course_slot_vars:
                    course_total_vars.append(self.course_slot_vars[(course_id, slot_id)])
            
            if course_total_vars:
                self.model.Add(sum(course_total_vars) == hours)
                constraint_count += 1
            
            # Liaison cours-classe : si cours programmé, alors classes occupées
            for class_name in classes:
                for slot in self.time_slots:
                    if slot["day_of_week"] == 5:
                        continue
                    slot_id = slot["slot_id"]
                    
                    course_var = self.course_slot_vars.get((course_id, slot_id))
                    class_var = self.class_slot_vars.get((class_name, slot_id))
                    link_var = self.course_class_links.get((course_id, class_name, slot_id))
                    
                    if course_var is not None and class_var is not None and link_var is not None:
                        # link_var = course_var ET class_var
                        self.model.Add(link_var <= course_var)
                        self.model.Add(link_var <= class_var)
                        self.model.Add(link_var >= course_var + class_var - 1)
                        constraint_count += 3
        
        # 2. CONTRAINTE CRITIQUE : Une classe = maximum 1 cours par créneau
        # Empêche les conflits multiples identifiés
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:
                    continue
                slot_id = slot["slot_id"]
                
                # Collecter tous les liens de cours vers cette classe sur ce créneau
                class_links = []
                for course in self.courses:
                    course_id = course["course_id"]
                    class_list = course.get("class_list", "")
                    classes = [c.strip() for c in class_list.split(",") if c.strip()]
                    
                    if class_name in classes:
                        link_var = self.course_class_links.get((course_id, class_name, slot_id))
                        if link_var is not None:
                            class_links.append(link_var)
                
                if class_links:
                    # MAXIMUM 1 cours par classe par créneau
                    self.model.Add(sum(class_links) <= 1)
                    constraint_count += 1
        
        # 3. Contraintes professeur (pas de conflit)
        for teacher in self.teachers:
            teacher_name = teacher.get("teacher_name", "")
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:
                    continue
                slot_id = slot["slot_id"]
                
                teacher_vars = []
                for course in self.courses:
                    teacher_names_str = course.get("teacher_names", "")
                    if teacher_name in [t.strip() for t in teacher_names_str.split(",")]:
                        course_var = self.course_slot_vars.get((course["course_id"], slot_id))
                        if course_var is not None:
                            teacher_vars.append(course_var)
                
                if teacher_vars:
                    self.model.Add(sum(teacher_vars) <= 1)
                    constraint_count += 1
        
        # 4. Synchronisation des cours parallèles (méthode existante)
        sync_constraints = self._add_parallel_sync_constraints()
        constraint_count += sync_constraints
        
        # 5. CONTRAINTE ANTI-TROUS : Minimiser les trous
        gap_constraints = self._add_zero_gaps_constraints()
        constraint_count += gap_constraints
        
        logger.info(f"✓ {constraint_count} contraintes fixées ajoutées")

    def _add_parallel_sync_constraints(self):
        """Synchronise les cours parallèles correctement"""
        logger.info("=== SYNCHRONISATION PARALLÈLE FIXÉE ===")
        constraint_count = 0
        
        for group_id, course_ids in self.sync_groups.items():
            if len(course_ids) <= 1:
                continue
                
            logger.info(f"Synchronisation groupe {group_id}: {len(course_ids)} cours")
            
            # Tous les cours du groupe doivent être programmés sur les mêmes créneaux
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:
                    continue
                slot_id = slot["slot_id"]
                
                group_vars = []
                for course_id in course_ids:
                    course_var = self.course_slot_vars.get((course_id, slot_id))
                    if course_var is not None:
                        group_vars.append(course_var)
                
                if len(group_vars) > 1:
                    # Tous identiques : var1 = var2 = var3 = ...
                    for i in range(1, len(group_vars)):
                        self.model.Add(group_vars[0] == group_vars[i])
                        constraint_count += 1
        
        return constraint_count

    def _add_zero_gaps_constraints(self):
        """Contraintes pour éliminer complètement les trous"""
        logger.info("=== CONTRAINTES ZÉRO TROUS ===")
        constraint_count = 0
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):  # Dimanche à jeudi
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                if len(day_slots) < 3:
                    continue
                
                # Variables : classe a cours à chaque période
                day_vars = []
                for slot in day_slots:
                    slot_id = slot["slot_id"]
                    class_var = self.class_slot_vars.get((class_name, slot_id))
                    if class_var is not None:
                        day_vars.append(class_var)
                
                # Contrainte : si classe a cours ce jour, alors pas de trous
                # Modèle : si période i et j ont cours (j > i+1), alors toutes les périodes intermédiaires ont cours
                for i in range(len(day_vars)):
                    for j in range(i + 2, len(day_vars)):  # j > i + 1 (au moins un gap)
                        # Si day_vars[i] = 1 ET day_vars[j] = 1, alors toutes les périodes entre i et j = 1
                        gap_indicator = self.model.NewBoolVar(f"gap_{class_name}_{day}_{i}_{j}")
                        
                        # gap_indicator = 1 ssi day_vars[i] = 1 ET day_vars[j] = 1
                        self.model.Add(gap_indicator <= day_vars[i])
                        self.model.Add(gap_indicator <= day_vars[j])
                        self.model.Add(gap_indicator >= day_vars[i] + day_vars[j] - 1)
                        
                        # Si gap_indicator = 1, alors toutes les périodes intermédiaires = 1
                        for k in range(i + 1, j):
                            if k < len(day_vars):
                                self.model.Add(day_vars[k] >= gap_indicator)
                                constraint_count += 1
                        
                        constraint_count += 3
        
        return constraint_count

    def solve(self, time_limit=600):
        """Résout avec la logique fixée"""
        logger.info("\n=== RÉSOLUTION FIXÉE ===")
        
        try:
            self.create_variables()
            if not self.class_slot_vars:
                logger.error("Aucune variable créée!")
                return []
                
            self.add_constraints()
            
            # Configuration du solver
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.num_search_workers = 8
            self.solver.parameters.log_search_progress = True
            
            logger.info(f"Lancement du solver fixé (limite: {time_limit}s)...")
            status = self.solver.Solve(self.model)
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution fixée trouvée! Status: {self.solver.StatusName(status)}")
                schedule = self._extract_fixed_solution()
                
                # Vérification de la solution
                self._verify_solution(schedule)
                
                return schedule
            else:
                logger.error(f"❌ Pas de solution. Status: {self.solver.StatusName(status)}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la résolution fixée : {e}")
            raise

    def _extract_fixed_solution(self):
        """Extrait la solution sans doublons ni conflits"""
        logger.info("=== EXTRACTION FIXÉE ===")
        schedule = []
        processed_entries = set()  # Pour éviter les doublons
        
        # Parcourir toutes les variables de liaison actives
        for (course_id, class_name, slot_id), var in self.course_class_links.items():
            if self.solver.Value(var) == 1:
                # Créer une clé unique pour éviter les doublons
                entry_key = (class_name, slot_id)
                
                if entry_key in processed_entries:
                    logger.warning(f"Doublon évité : {class_name} créneau {slot_id}")
                    continue
                
                processed_entries.add(entry_key)
                
                # Trouver les données du cours et du créneau
                course = next((c for c in self.courses if c["course_id"] == course_id), None)
                slot = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if course and slot:
                    teacher_names_str = course.get("teacher_names", "")
                    is_parallel = course.get("is_parallel", False)
                    
                    # Pour les cours parallèles, garder tous les profs. Sinon, le premier
                    if is_parallel:
                        display_teacher = teacher_names_str
                    else:
                        teachers = [t.strip() for t in teacher_names_str.split(",") if t.strip()]
                        display_teacher = teachers[0] if teachers else ""
                    
                    schedule.append({
                        "course_id": course_id,
                        "slot_id": slot_id,
                        "teacher_name": display_teacher,
                        "subject_name": course.get("subject", course.get("subject_name", "")),
                        "class_name": class_name,
                        "day_of_week": slot["day_of_week"],
                        "period_number": slot["period_number"],
                        "is_parallel": is_parallel,
                        "group_id": course.get("group_id")
                    })
        
        logger.info(f"✅ Solution extraite : {len(schedule)} entrées uniques")
        return schedule

    def _verify_solution(self, schedule):
        """Vérifie que la solution n'a pas de conflits"""
        logger.info("=== VÉRIFICATION DE LA SOLUTION ===")
        
        # Vérifier les conflits de classe (plus d'un cours au même moment)
        class_conflicts = {}
        for entry in schedule:
            key = (entry["class_name"], entry["day_of_week"], entry["period_number"])
            if key not in class_conflicts:
                class_conflicts[key] = []
            class_conflicts[key].append(entry)
        
        conflicts_found = 0
        for key, entries in class_conflicts.items():
            if len(entries) > 1:
                conflicts_found += 1
                logger.error(f"CONFLIT : {key[0]} jour {key[1]} période {key[2]} : {len(entries)} cours")
        
        if conflicts_found == 0:
            logger.info("✅ Aucun conflit de classe détecté")
        else:
            logger.error(f"❌ {conflicts_found} conflits de classe détectés")
        
        # Vérifier les trous
        gaps_found = 0
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            class_schedule = [e for e in schedule if e["class_name"] == class_name]
            
            for day in range(5):
                day_periods = sorted([e["period_number"] for e in class_schedule if e["day_of_week"] == day])
                
                if len(day_periods) > 1:
                    for i in range(1, len(day_periods)):
                        if day_periods[i] - day_periods[i-1] > 1:
                            gaps_found += 1
                            logger.warning(f"TROU : {class_name} jour {day} entre périodes {day_periods[i-1]} et {day_periods[i]}")
        
        if gaps_found == 0:
            logger.info("✅ Aucun trou détecté")
        else:
            logger.warning(f"⚠️ {gaps_found} trous détectés")

    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps fixé"""
        if not schedule:
            raise ValueError("Schedule vide")

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            # Supprimer l'ancien schedule actif
            cur.execute("UPDATE schedules SET status = 'inactive' WHERE status = 'active'")
            
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
            """, ("2024-2025", 1, "active", datetime.now()))
            schedule_id = cur.fetchone()[0]

            for entry in schedule:
                cur.execute("""
                    INSERT INTO schedule_entries (
                        schedule_id, teacher_name, class_name, subject,
                        day_of_week, period_number, is_parallel_group, group_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry.get("teacher_name"),
                    entry.get("class_name"),
                    entry.get("subject_name"),
                    entry.get("day_of_week"),
                    entry.get("period_number"),
                    bool(entry.get("is_parallel", False)),
                    entry.get("group_id")
                ))

            conn.commit()
            logger.info(f"✅ Emploi du temps fixé sauvegardé (ID {schedule_id})")
            return schedule_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    def get_schedule_summary(self, schedule):
        """Retourne des statistiques sur l'emploi du temps fixé"""
        if not schedule:
            return {"error": "Pas d'emploi du temps généré"}

        days_used = sorted(set(e["day_of_week"] for e in schedule))
        classes_covered = len(set(e["class_name"] for e in schedule if e.get("class_name")))
        
        # Calculer la distribution par jour
        by_day = {}
        for entry in schedule:
            day = entry["day_of_week"]
            by_day[day] = by_day.get(day, 0) + 1
        
        return {
            "total_lessons": len(schedule),
            "days_used": days_used,
            "classes_covered": classes_covered,
            "subjects_count": len(set(e.get("subject_name") or "" for e in schedule)),
            "distribution_by_day": by_day,
            "average_per_day": len(schedule) / max(len(days_used), 1)
        }
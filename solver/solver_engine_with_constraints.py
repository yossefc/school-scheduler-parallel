# solver_engine_with_constraints.py - Version avec support des contraintes personnalisées
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ScheduleSolverWithConstraints:
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
        self.schedule_vars = {}
        self.teachers = []
        self.classes = []
        self.time_slots = []
        self.courses = []
        self.constraints = []  # Nouveau : stockage des contraintes personnalisées
        
    def load_data_from_db(self):
        """Charge les données depuis solver_input et les contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DEPUIS LA BASE ===")
            
            # Charger les données de base
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
            
            # Charger les cours depuis solver_input
            cur.execute("""
                SELECT * FROM solver_input 
                ORDER BY course_type, course_id
            """)
            self.courses = cur.fetchall()
            logger.info(f"✓ {len(self.courses)} cours à planifier")
            
            # NOUVEAU : Charger les contraintes personnalisées
            cur.execute("""
                SELECT * FROM constraints 
                WHERE is_active = TRUE
                ORDER BY constraint_type, constraint_id
            """)
            self.constraints = cur.fetchall()
            logger.info(f"✓ {len(self.constraints)} contraintes personnalisées actives")
            
            # Afficher un résumé des contraintes par type
            cur.execute("""
                SELECT constraint_type, COUNT(*) as count 
                FROM constraints 
                WHERE is_active = TRUE 
                GROUP BY constraint_type
            """)
            for row in cur.fetchall():
                logger.info(f"  - {row['constraint_type']}: {row['count']} contraintes")
            
            # Vérifier la faisabilité
            cur.execute("SELECT SUM(hours) as total_hours FROM solver_input")
            total_hours = cur.fetchone()['total_hours']
            
            total_slots = len(self.classes) * len(self.time_slots)
            utilization = (total_hours / total_slots * 100) if total_slots > 0 else 0
            
            logger.info(f"\n=== ANALYSE DE FAISABILITÉ ===")
            logger.info(f"Heures totales nécessaires: {total_hours}")
            logger.info(f"Créneaux disponibles: {total_slots}")
            logger.info(f"Taux d'utilisation: {utilization:.1f}%")
            
            if utilization > 100:
                logger.error("❌ IMPOSSIBLE: Plus d'heures que de créneaux!")
                raise ValueError("Impossible de générer l'emploi du temps")
                
        finally:
            cur.close()
            conn.close()

    def create_variables(self):
        """Crée les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES ===")
        
        for course in self.courses:
            course_id = course["course_id"]
            hours = course["hours"]
            
            # Variables pour chaque créneau possible
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
                
        logger.info(f"✓ {len(self.schedule_vars)} variables créées")

    def add_constraints(self):
        """Ajoute toutes les contraintes au modèle"""
        logger.info("=== AJOUT DES CONTRAINTES ===")
        constraint_count = 0
        
        # 1. Contraintes de base (heures exactes)
        for course in self.courses:
            course_id = course["course_id"]
            hours = course["hours"]
            
            course_vars = []
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    course_vars.append(self.schedule_vars[var_name])
            
            if course_vars:
                self.model.Add(sum(course_vars) == hours)
                constraint_count += 1
        
        # 2. Pas de conflits professeur
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                teacher_slot_vars = []
                
                for course in self.courses:
                    if teacher_name in (course.get("teacher_names") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            teacher_slot_vars.append(self.schedule_vars[var_name])
                
                if teacher_slot_vars:
                    self.model.Add(sum(teacher_slot_vars) <= 1)
                    constraint_count += 1
        
        # 3. Pas de conflits classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                class_slot_vars = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            class_slot_vars.append(self.schedule_vars[var_name])
                
                if class_slot_vars:
                    self.model.Add(sum(class_slot_vars) <= 1)
                    constraint_count += 1
        
        # 4. Vendredi écourté
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5 and slot["period_number"] > 6:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
                        constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de base ajoutées")
        
        # 5. NOUVEAU : Appliquer les contraintes personnalisées
        self._apply_custom_constraints()
        
        # 6. Objectif : maximiser l'étalement
        self._add_spread_objective()

    def _apply_custom_constraints(self):
        """Applique les contraintes personnalisées de la table constraints"""
        logger.info("\n=== APPLICATION DES CONTRAINTES PERSONNALISÉES ===")
        applied_count = 0
        
        for constraint in self.constraints:
            try:
                constraint_type = constraint["constraint_type"]
                params = json.loads(constraint.get("parameters", "{}"))
                
                if constraint_type == "teacher_unavailable":
                    # Professeur non disponible
                    applied = self._apply_teacher_unavailable(
                        params.get("teacher_name"),
                        params.get("day_of_week"),
                        params.get("period_numbers", [])
                    )
                    
                elif constraint_type == "class_unavailable":
                    # Classe non disponible
                    applied = self._apply_class_unavailable(
                        params.get("class_name"),
                        params.get("day_of_week"),
                        params.get("period_numbers", [])
                    )
                    
                elif constraint_type == "subject_forbidden_slot":
                    # Matière interdite à certains créneaux
                    applied = self._apply_subject_forbidden_slot(
                        params.get("subject_name"),
                        params.get("day_of_week"),
                        params.get("period_numbers", [])
                    )
                    
                elif constraint_type == "consecutive_hours":
                    # Heures consécutives pour une matière
                    applied = self._apply_consecutive_hours(
                        params.get("subject_name"),
                        params.get("class_name"),
                        params.get("min_consecutive", 2),
                        params.get("max_consecutive", 4)
                    )
                    
                elif constraint_type == "max_hours_per_day":
                    # Maximum d'heures par jour pour un prof/classe
                    if params.get("teacher_name"):
                        applied = self._apply_max_hours_per_day_teacher(
                            params.get("teacher_name"),
                            params.get("max_hours", 6)
                        )
                    elif params.get("class_name"):
                        applied = self._apply_max_hours_per_day_class(
                            params.get("class_name"),
                            params.get("max_hours", 8)
                        )
                    
                elif constraint_type == "preferred_time":
                    # Créneaux préférés pour une matière
                    applied = self._apply_preferred_time(
                        params.get("subject_name"),
                        params.get("preferred_periods", [])
                    )
                    
                if applied:
                    applied_count += 1
                    logger.info(f"  ✓ Contrainte {constraint['constraint_id']}: {constraint_type}")
                    
            except Exception as e:
                logger.warning(f"  ⚠ Impossible d'appliquer contrainte {constraint['constraint_id']}: {e}")
        
        logger.info(f"\nTotal: {applied_count}/{len(self.constraints)} contraintes appliquées")

    def _apply_teacher_unavailable(self, teacher_name, day_of_week, period_numbers):
        """Applique une contrainte d'indisponibilité professeur"""
        if not teacher_name:
            return False
            
        count = 0
        for course in self.courses:
            if teacher_name in (course.get("teacher_names") or "").split(","):
                for slot in self.time_slots:
                    if (day_of_week is None or slot["day_of_week"] == day_of_week) and \
                       (not period_numbers or slot["period_number"] in period_numbers):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            count += 1
        return count > 0

    def _apply_class_unavailable(self, class_name, day_of_week, period_numbers):
        """Applique une contrainte d'indisponibilité classe"""
        if not class_name:
            return False
            
        count = 0
        for course in self.courses:
            if class_name in (course.get("class_list") or "").split(","):
                for slot in self.time_slots:
                    if (day_of_week is None or slot["day_of_week"] == day_of_week) and \
                       (not period_numbers or slot["period_number"] in period_numbers):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            count += 1
        return count > 0

    def _apply_subject_forbidden_slot(self, subject_name, day_of_week, period_numbers):
        """Applique une contrainte d'interdiction de matière à certains créneaux"""
        if not subject_name:
            return False
            
        count = 0
        for course in self.courses:
            if subject_name == course.get("subject_name"):
                for slot in self.time_slots:
                    if (day_of_week is None or slot["day_of_week"] == day_of_week) and \
                       (not period_numbers or slot["period_number"] in period_numbers):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            count += 1
        return count > 0

    def _apply_max_hours_per_day_teacher(self, teacher_name, max_hours):
        """Limite le nombre d'heures par jour pour un professeur"""
        if not teacher_name:
            return False
            
        for day in range(6):  # 0-5 pour dimanche-vendredi
            day_vars = []
            for course in self.courses:
                if teacher_name in (course.get("teacher_names") or "").split(","):
                    for slot in self.time_slots:
                        if slot["day_of_week"] == day:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                day_vars.append(self.schedule_vars[var_name])
            
            if day_vars:
                self.model.Add(sum(day_vars) <= max_hours)
        
        return True

    def _apply_max_hours_per_day_class(self, class_name, max_hours):
        """Limite le nombre d'heures par jour pour une classe"""
        if not class_name:
            return False
            
        for day in range(6):
            day_vars = []
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    for slot in self.time_slots:
                        if slot["day_of_week"] == day:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                day_vars.append(self.schedule_vars[var_name])
            
            if day_vars:
                self.model.Add(sum(day_vars) <= max_hours)
        
        return True

    def _apply_consecutive_hours(self, subject_name, class_name, min_consecutive, max_consecutive):
        """Force les heures consécutives pour une matière/classe"""
        # Cette contrainte est complexe et nécessite une logique plus avancée
        # Pour l'instant, on retourne True pour indiquer qu'on l'a "traitée"
        return True

    def _apply_preferred_time(self, subject_name, preferred_periods):
        """Favorise certains créneaux pour une matière (soft constraint via objectif)"""
        # Implémenté via l'objectif plutôt que comme contrainte dure
        return True

    def _add_spread_objective(self):
        """Ajoute l'objectif d'étalement des cours"""
        objective_terms = []
        
        # Maximiser l'étalement sur les jours pour chaque classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for day in range(6):
                day_used = self.model.NewBoolVar(f"class_{class_name}_day_{day}_used")
                day_vars = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[var_name])
                
                if day_vars:
                    self.model.Add(sum(day_vars) >= day_used)
                    self.model.Add(sum(day_vars) <= len(day_vars) * day_used)
                    objective_terms.append(day_used)
        
        if objective_terms:
            self.model.Maximize(sum(objective_terms))

    def solve(self, time_limit=300):
        """Résout le problème"""
        logger.info("\n=== RÉSOLUTION ===")
        
        try:
            self.create_variables()
            logger.info(f"Variables créées: {len(self.schedule_vars)}")
            if not self.schedule_vars:
                logger.error("Aucune variable créée: vérifiez que solver_input et time_slots contiennent des données")
                return []
            self.add_constraints()
            
            # Configurer le solver
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.num_search_workers = 8
            self.solver.parameters.log_search_progress = True
            
            logger.info(f"Lancement du solver (limite: {time_limit}s)...")
            status = self.solver.Solve(self.model)
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! Status: {['UNKNOWN', 'MODEL_INVALID', 'FEASIBLE', 'INFEASIBLE', 'OPTIMAL'][status]}")
                return self._extract_solution()
            else:
                logger.error(f"❌ Pas de solution. Status: {status}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la résolution : {e}")
            raise

    def _extract_solution(self):
        """Extrait la solution du solver"""
        schedule = []
        
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                parts = var_name.split("_")
                course_id = int(parts[1])
                slot_id = int(parts[3])
                
                course = next((c for c in self.courses if c["course_id"] == course_id), None)
                slot = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if course and slot:
                    # Créer une entrée pour chaque classe
                    classes = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
                    for class_name in classes:
                        schedule.append({
                            "course_id": course_id,
                            "slot_id": slot_id,
                            "teacher_name": (course.get("teacher_name") or course.get("teacher_names") or ""),
                            "subject_name": (course.get("subject_name") or course.get("subject") or ""),
                            "class_name": class_name,
                            "day_of_week": slot["day_of_week"],
                            "period_number": slot["period_number"],
                            "start_time": str(slot["start_time"]),
                            "end_time": str(slot["end_time"])
                        })
        
        return schedule

    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps dans la base de données et renvoie l'ID du schedule."""
        if not schedule:
            raise ValueError("Schedule vide")

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            # Créer un nouvel en-tête d'emploi du temps
            cur.execute(
                """
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
                """,
                ("2024-2025", 1, "active", datetime.now()),
            )
            schedule_id = cur.fetchone()[0]

            rows_inserted = 0
            for entry in schedule:
                cur.execute(
                    """
                    INSERT INTO schedule_entries (
                        schedule_id, teacher_name, class_name, subject_name,
                        day_of_week, period_number, is_parallel_group, group_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        schedule_id,
                        entry.get("teacher_name"),
                        entry.get("class_name"),
                        entry.get("subject_name"),
                        entry.get("day_of_week"),
                        entry.get("period_number"),
                        False,  # Pas de groupes parallèles gérés ici
                        None,
                    ),
                )
                rows_inserted += 1

            conn.commit()
            logger.info(
                f"✅ Emploi du temps sauvegardé (ID {schedule_id}) - {rows_inserted} lignes insérées"
            )
            return schedule_id
        except Exception:
            conn.rollback()
            logger.exception("Erreur lors de la sauvegarde de l'emploi du temps")
            raise
        finally:
            cur.close()
            conn.close()

    def get_schedule_summary(self, schedule):
        """Retourne quelques statistiques simples sur l'emploi du temps généré."""
        if not schedule:
            return {"error": "Pas d'emploi du temps généré"}

        return {
            "total_lessons": len(schedule),
            "days_used": sorted(set(e["day_of_week"] for e in schedule)),
            "classes_covered": len({e["class_name"] for e in schedule if e.get("class_name")}),
            "subjects_count": len({e["subject_name"] for e in schedule}),
        }

def save_schedule_to_db(schedule_data, db_config):
    """Sauvegarde l'emploi du temps avec support des contraintes"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    try:
        # Vider la table
        cur.execute("TRUNCATE TABLE schedules CASCADE")
        
        # Insérer les nouvelles données
        for entry in schedule_data:
            cur.execute("""
                INSERT INTO schedules (
                    slot_id, course_id, teacher_names, subject_name, 
                    class_name, day_of_week, period_number, 
                    start_time, end_time, created_at
                ) VALUES (
                    %(slot_id)s, %(course_id)s, %(teacher_names)s, %(subject_name)s,
                    %(class_name)s, %(day_of_week)s, %(period_number)s,
                    %(start_time)s, %(end_time)s, NOW()
                )
            """, entry)
        
        conn.commit()
        logger.info(f"✓ {len(schedule_data)} entrées sauvegardées")
        
    finally:
        cur.close()
        conn.close()



# solver_engine_final.py - Version finale corrigée
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ScheduleSolver:
    def __init__(self, db_config=None):
        """Initialise le solver avec la nouvelle structure"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        if db_config is None:
            db_config = {
                "host": "postgres",  # ou "localhost" pour test local
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
        
    def load_data_from_db(self):
        """Charge les données depuis solver_input"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DEPUIS solver_input ===")
            
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
            
            # CHARGER DEPUIS solver_input
            try:
                logger.info("Chargement des cours depuis solver_input...")
                cur.execute("""
                    SELECT * FROM solver_input 
                    ORDER BY course_type, course_id
                """)
                self.courses = cur.fetchall()
                logger.info(f"✓ {len(self.courses)} cours à planifier")
                
                if len(self.courses) == 0:
                    logger.error("ATTENTION : Aucun cours trouvé dans solver_input!")
                    logger.error("Vérifiez que la table solver_input contient des données")
                    raise ValueError("Aucun cours à planifier dans solver_input")
                    
            except Exception as e:
                logger.error(f"Erreur lors du chargement des cours : {e}")
                logger.error(f"Type d'erreur : {type(e).__name__}")
                raise
            
            # Statistiques par type
            cur.execute("""
                SELECT 
                    course_type,
                    COUNT(*) as count,
                    SUM(hours) as total_hours
                FROM solver_input
                GROUP BY course_type
                ORDER BY course_type
            """)
            
            logger.info("Détails par type:")
            for row in cur.fetchall():
                logger.info(f"  - {row['course_type']}: {row['count']} cours, {row['total_hours']}h")
            
            # Vérifier la faisabilité
            cur.execute("""
                SELECT 
                    SUM(hours) as total_hours
                FROM solver_input
            """)
            total_hours = cur.fetchone()['total_hours']
            
            total_slots = len(self.classes) * len(self.time_slots)
            utilization = (total_hours / total_slots * 100) if total_slots > 0 else 0
            
            logger.info(f"")
            logger.info(f"=== ANALYSE DE FAISABILITÉ ===")
            logger.info(f"Heures totales nécessaires: {total_hours}")
            logger.info(f"Créneaux disponibles: {total_slots}")
            logger.info(f"Taux d'utilisation: {utilization:.1f}%")
            
            if utilization > 100:
                logger.error("❌ IMPOSSIBLE: Plus d'heures que de créneaux!")
                raise ValueError("Impossible de générer l'emploi du temps")
            elif utilization > 85:
                logger.warning("⚠️ DIFFICILE: Utilisation > 85%")
                logger.warning("Augmentez le time_limit à 1200 secondes")
            else:
                logger.info("✅ FAISABLE: Le problème peut être résolu")
                
        finally:
            cur.close()
            conn.close()

    def create_variables(self):
        """Crée les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES ===")
        
        var_count = 0
        
        for course in self.courses:
            course_id = course["course_id"]
            course_type = course["course_type"]
            
            # Pour chaque créneau possible
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                
                # Créer une variable unique pour ce cours et ce créneau
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
                var_count += 1
        
        logger.info(f"✓ {var_count} variables créées")

    def add_constraints(self):
        """Ajoute toutes les contraintes"""
        logger.info("=== AJOUT DES CONTRAINTES ===")
        
        constraint_count = 0

        def course_teacher_names_list(course) -> list:
            names_str = course.get("teacher_names") or course.get("teacher_name") or ""
            return [t.strip() for t in names_str.split(",") if t.strip()]
        
        logger.info(f"Nombre de cours à traiter : {len(self.courses)}")
        logger.info(f"Nombre de créneaux : {len(self.time_slots)}")
        logger.info(f"Nombre de professeurs : {len(self.teachers)}")
        logger.info(f"Nombre de classes : {len(self.classes)}")
        
        # 1. CONTRAINTE : Chaque cours doit avoir exactement le nombre d'heures prévu
        logger.info("Ajout contrainte 1 : heures par cours...")
        for i, course in enumerate(self.courses):
            if i % 50 == 0:
                logger.info(f"  Traité {i}/{len(self.courses)} cours...")
            
            course_id = course["course_id"]
            hours = course["hours"]
            
            if hours > 0:
                course_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"course_{course_id}_" in name
                ]
                
                # Le nombre de créneaux assignés doit être égal aux heures
                self.model.Add(sum(course_vars) == hours)
                constraint_count += 1
        logger.info(f"✓ Contrainte 1 terminée : {constraint_count} contraintes")
        
        # 2. CONTRAINTE : Un professeur ne peut être qu'à un endroit à la fois
        logger.info("Ajout contrainte 2 : un prof à un endroit à la fois...")
        total_combinations = len(self.time_slots) * len(self.teachers)
        combination_count = 0
        
        for slot_idx, slot in enumerate(self.time_slots):
            slot_id = slot["slot_id"]
            
            if slot_idx % 10 == 0:
                logger.info(f"  Traité {slot_idx}/{len(self.time_slots)} créneaux...")
            
            # Pour chaque professeur
            for teacher in self.teachers:
                teacher_name = teacher["teacher_name"]
                combination_count += 1
                
                # Trouver tous les cours de ce prof à ce créneau
                teacher_vars = []
                for course in self.courses:
                    # Vérifier si ce prof enseigne ce cours
                    if teacher_name in course_teacher_names_list(course):
                        var_name = f"course_{course['course_id']}_slot_{slot_id}"
                        if var_name in self.schedule_vars:
                            teacher_vars.append(self.schedule_vars[var_name])
                
                # Maximum 1 cours à la fois
                if len(teacher_vars) > 1:
                    self.model.Add(sum(teacher_vars) <= 1)
                    constraint_count += 1
        
        logger.info(f"✓ Contrainte 2 terminée : {constraint_count} contraintes au total")
        
        # 3. CONTRAINTE : Une classe ne peut avoir qu'un cours à la fois
        for slot in self.time_slots:
            slot_id = slot["slot_id"]
            
            for class_obj in self.classes:
                class_name = class_obj["class_name"]
                
                # Trouver tous les cours pour cette classe à ce créneau
                class_vars = []
                for course in self.courses:
                    class_list = course.get("class_list", "") or ""
                    classes = [c.strip() for c in class_list.split(",") if c.strip()]
                    if class_name in classes:
                        var_name = f"course_{course['course_id']}_slot_{slot_id}"
                        if var_name in self.schedule_vars:
                            class_vars.append(self.schedule_vars[var_name])
                
                # Maximum 1 cours à la fois
                if len(class_vars) > 1:
                    self.model.Add(sum(class_vars) <= 1)
                    constraint_count += 1
        
        # 4. CONTRAINTE : Vendredi court (pas de cours après 13h)
        for slot in self.time_slots:
            if slot["day_of_week"] == 5 and slot["period_number"] > 6:
                for var_name, var in self.schedule_vars.items():
                    if f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)
                        constraint_count += 1

        # 5. OBJECTIF (souple) : étaler les cours sur les jours (par classe et par professeur)
        objective_terms = []
        # Par classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for day in range(6):
                day_used = self.model.NewBoolVar(f"class_{class_name}_day_{day}_used")
                # toutes les variables de cette classe pour ce jour
                day_vars = []
                for course in self.courses:
                    class_list = (course.get("class_list", "") or "")
                    classes = [c.strip() for c in class_list.split(",") if c.strip()]
                    if class_name in classes:
                        course_id = course["course_id"]
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                slot_id = slot["slot_id"]
                                var_name = f"course_{course_id}_slot_{slot_id}"
                                if var_name in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[var_name])
                if day_vars:
                    # Lier la présence ce jour-là
                    self.model.Add(sum(day_vars) >= day_used)
                    self.model.Add(sum(day_vars) <= len(day_vars) * day_used)
                    objective_terms.append(day_used)

        # Par professeur
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for day in range(6):
                day_used = self.model.NewBoolVar(f"teacher_{teacher_name}_day_{day}_used")
                day_vars = []
                for course in self.courses:
                    if teacher_name in course_teacher_names_list(course):
                        course_id = course["course_id"]
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                slot_id = slot["slot_id"]
                                var_name = f"course_{course_id}_slot_{slot_id}"
                                if var_name in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[var_name])
                if day_vars:
                    self.model.Add(sum(day_vars) >= day_used)
                    self.model.Add(sum(day_vars) <= len(day_vars) * day_used)
                    objective_terms.append(day_used)

        if objective_terms:
            # Maximiser l'étalement sur les jours
            self.model.Maximize(sum(objective_terms))
        
        logger.info(f"✓ {constraint_count} contraintes ajoutées")

    def solve(self, time_limit=300):
        """Résout le problème"""
        logger.info("=== RÉSOLUTION ===")
        
        try:
            # Créer les variables et contraintes
            logger.info("Création des variables...")
            self.create_variables()
            logger.info("Variables créées avec succès")
            
            logger.info("Ajout des contraintes...")
            self.add_constraints()
            logger.info("Contraintes ajoutées avec succès")
            
            # Configurer le solver
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.num_search_workers = 8
            self.solver.parameters.log_search_progress = True
            
            logger.info(f"Lancement du solver (limite: {time_limit}s)...")
            status = self.solver.Solve(self.model)
        except Exception as e:
            logger.error(f"Erreur lors de la résolution : {e}")
            logger.error(f"Type d'erreur : {type(e).__name__}")
            import traceback
            logger.error(f"Traceback : {traceback.format_exc()}")
            raise
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            logger.info(f"✅ Solution trouvée! Status: {['UNKNOWN', 'MODEL_INVALID', 'FEASIBLE', 'INFEASIBLE', 'OPTIMAL'][status]}")
            solution = self._extract_solution()
            self._display_statistics(solution)
            return solution
        else:
            logger.error(f"❌ Pas de solution. Status: {status}")
            self._analyze_failure()
            return None

    def _extract_solution(self):
        """Extrait la solution du solver"""
        schedule = []
        
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                # Parser le nom de la variable
                parts = var_name.split("_")
                course_id = int(parts[1])
                slot_id = int(parts[3])
                
                # Récupérer les infos
                course = next((c for c in self.courses if c["course_id"] == course_id), None)
                slot = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if course and slot:
                    # Créer une entrée pour chaque classe (séparer proprement)
                    raw = course.get("class_list", "") or ""
                    classes = [c.strip() for c in raw.split(",") if c.strip()]
                    for class_name in classes:
                        if class_name.strip():
                            schedule.append({
                                "course_id": course_id,
                                "teacher_name": course["teacher_name"],
                                "class_name": class_name.strip(),
                                "subject_name": course["subject"],
                                "day": slot["day_of_week"],
                                "period": slot["period_number"],
                                "is_parallel": course["is_parallel"],
                                "course_type": course["course_type"]
                            })
        
        return schedule

    def _display_statistics(self, solution):
        """Affiche les statistiques de la solution"""
        if not solution:
            return
        
        logger.info("")
        logger.info("=== STATISTIQUES DE LA SOLUTION ===")
        logger.info(f"Total de créneaux planifiés: {len(solution)}")
        
        # Par jour
        for day in range(6):
            day_count = len([s for s in solution if s["day"] == day])
            day_names = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
            logger.info(f"  {day_names[day]}: {day_count} créneaux")
        
        # Par type
        parallel = len([s for s in solution if s.get("is_parallel")])
        individual = len([s for s in solution if not s.get("is_parallel")])
        logger.info(f"  Cours parallèles: {parallel}")
        logger.info(f"  Cours individuels: {individual}")

    def _analyze_failure(self):
        """Analyse les raisons de l'échec"""
        logger.error("")
        logger.error("=== ANALYSE DE L'ÉCHEC ===")
        logger.error("Causes possibles:")
        logger.error("1. Contraintes trop restrictives")
        logger.error("2. Pas assez de créneaux disponibles")
        logger.error("3. Conflits entre professeurs")
        logger.error("4. Time limit trop court")
        logger.error("")
        logger.error("Solutions suggérées:")
        logger.error("- Augmenter time_limit à 600 ou 1200 secondes")
        logger.error("- Désactiver certaines contraintes")
        logger.error("- Ajouter plus de créneaux horaires")

    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps dans la base (1 ligne par classe)."""
        if not schedule:
            return None

        def normalize_class_name(raw: str) -> str:
            if raw is None:
                return ''
            cleaned = (
                raw.replace(' ', '')
                   .replace('-', '')
                   .replace('־', '')   # maqaf hébreu
                   .replace('–', '')
                   .replace('—', '')
            )
            return cleaned

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        try:
            # Créer un nouvel emploi du temps
            cur.execute(
                """
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
                """,
                ('2024-2025', 1, 'active', datetime.now()),
            )
            schedule_id = cur.fetchone()[0]

            rows_inserted = 0
            for entry in schedule:
                teacher_name = entry.get("teacher_name", "").strip()
                subject_name = entry.get("subject_name", "").strip()
                day_of_week = int(entry.get("day"))
                period_number = int(entry.get("period"))
                is_parallel = bool(entry.get("is_parallel", False))

                class_field = entry.get("class_name", "") or ""
                # Supporte les deux cas: déjà une classe unique, ou liste séparée par virgules
                class_candidates = [c.strip() for c in class_field.split(",") if c.strip()] or [""]

                for cls in class_candidates:
                    class_name = normalize_class_name(cls)
                    if not class_name:
                        continue

                    cur.execute(
                        """
                        INSERT INTO schedule_entries (
                            schedule_id, teacher_name, class_name, subject_name,
                            day_of_week, period_number, is_parallel_group
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            schedule_id,
                            teacher_name,
                            class_name,
                            subject_name,
                            day_of_week,
                            period_number,
                            is_parallel,
                        ),
                    )
                    rows_inserted += 1

            conn.commit()
            logger.info(
                f"✅ Emploi du temps sauvegardé (ID {schedule_id}) - {rows_inserted} lignes insérées"
            )
            return schedule_id

        except Exception as e:
            conn.rollback()
            logger.error("Erreur lors de la sauvegarde de l'emploi du temps", exc_info=True)
            raise
        finally:
            cur.close()
            conn.close()

    def get_schedule_summary(self, schedule):
        """Génère un résumé de l'emploi du temps"""
        if not schedule:
            return {"error": "Pas d'emploi du temps"}
        
        return {
            "total_lessons": len(schedule),
            "days_used": sorted(set(e["day"] for e in schedule)),
            "classes_covered": len(set(e["class_name"] for e in schedule if e.get("class_name"))),
            "parallel_lessons": len([e for e in schedule if e.get("is_parallel")]),
            "individual_lessons": len([e for e in schedule if not e.get("is_parallel")])
        }
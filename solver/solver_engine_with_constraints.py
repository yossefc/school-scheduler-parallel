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
            teacher_name = teacher.get("teacher_name", "")
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
        
        # 4. Interdiction complète du vendredi (aucun cours planifié le jour 5)
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
                        constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de base ajoutées")
        
        # 5. Contraintes spécifiques de l'école
        self._add_school_specific_constraints(constraint_count)
        
        # 6. Objectif de compacité - pas de trous
        self._add_compactness_objective()

    def _add_school_specific_constraints(self, constraint_count):
        """Ajoute les contraintes spécifiques de l'école"""
        logger.info("=== CONTRAINTES SPÉCIFIQUES DE L'ÉCOLE ===")
        
        # 1. Lundi 12:00-13:30 - équipes חטיבה libres
        monday_slots_12_13 = []
        for slot in self.time_slots:
            if slot["day_of_week"] == 1:  # Lundi
                start_time = str(slot["start_time"])
                if "12:00" <= start_time < "13:30":
                    monday_slots_12_13.append(slot["slot_id"])
        
        if monday_slots_12_13:
            # Identifier les classes חטיבה (ז, ח, ט)
            chetiba_grades = ['ז', 'ח', 'ט']
            for course in self.courses:
                if any(grade in course.get("grade", "") for grade in chetiba_grades):
                    for slot_id in monday_slots_12_13:
                        var_name = f"course_{course['course_id']}_slot_{slot_id}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            constraint_count += 1
        
        # 2. Lundi 13:30-15:15 - réunions dirigeants et mentors
        monday_slots_13_15 = []
        for slot in self.time_slots:
            if slot["day_of_week"] == 1:  # Lundi
                start_time = str(slot["start_time"])
                if "13:30" <= start_time < "15:15":
                    monday_slots_13_15.append(slot["slot_id"])
        
        # TODO: Identifier les cours des dirigeants et mentors quand on aura cette info
        
        # 3. Dirigeants lycée - préférer 3 premières périodes
        # Sera traité dans l'objectif de qualité
        
        logger.info(f"✓ {constraint_count} contraintes école ajoutées")
        
    def _add_compactness_objective(self):
        """Ajoute un objectif pour minimiser les trous dans l'emploi du temps"""
        logger.info("=== OBJECTIF DE COMPACITÉ ===")
        
        gap_penalty = []
        
        # Pour chaque classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Pour chaque jour
            for day in range(5):  # 0-4 (dimanche-jeudi)
                # Trouver tous les créneaux de ce jour pour cette classe
                day_slots = []
                for slot in self.time_slots:
                    if slot["day_of_week"] == day:
                        day_slots.append(slot)
                
                # Trier par période
                day_slots.sort(key=lambda s: s["period_number"])
                
                if len(day_slots) > 1:
                    # Variables pour suivre si un cours est planifié
                    has_course = []
                    for slot in day_slots:
                        slot_has_course = self.model.NewBoolVar(f"has_course_{class_name}_{day}_{slot['period_number']}")
                        
                        # Ce slot a un cours si AU MOINS un cours de cette classe y est planifié
                        course_vars_for_slot = []
                        for course in self.courses:
                            if class_name in (course.get("class_list") or "").split(","):
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    course_vars_for_slot.append(self.schedule_vars[var_name])
                        
                        if course_vars_for_slot:
                            self.model.Add(slot_has_course <= len(course_vars_for_slot))
                            self.model.Add(sum(course_vars_for_slot) >= slot_has_course)
                            has_course.append((slot['period_number'], slot_has_course))
                    
                    # Pénaliser les trous
                    for i in range(1, len(has_course) - 1):
                        # Si has_course[i] = 0 mais has_course[i-1] = 1 et has_course[i+1] = 1, c'est un trou
                        gap = self.model.NewBoolVar(f"gap_{class_name}_{day}_{has_course[i][0]}")
                        # gap = 1 si (pas de cours à i) ET (cours avant) ET (cours après)
                        self.model.Add(gap >= has_course[i-1][1] + has_course[i+1][1] - has_course[i][1] - 1)
                        self.model.Add(gap <= 1 - has_course[i][1])
                        gap_penalty.append(gap)
        
        # Ajouter aussi une pénalité pour commencer tard
        late_start_penalty = []
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for day in range(5):  # 0-4
                # Pénaliser si le premier cours ne commence pas à la période 0 ou 1
                for period in range(2, 12):  # Périodes 2-11
                    first_course = self.model.NewBoolVar(f"first_{class_name}_{day}_{period}")
                    # first_course = 1 si c'est le premier cours du jour
                    course_vars = []
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            for slot in self.time_slots:
                                if slot["day_of_week"] == day and slot["period_number"] == period:
                                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                    if var_name in self.schedule_vars:
                                        course_vars.append(self.schedule_vars[var_name])
                    
                    if course_vars:
                        # C'est le premier cours si : il y a un cours ici ET pas de cours avant
                        no_course_before = []
                        for p in range(period):
                            for course in self.courses:
                                if class_name in (course.get("class_list") or "").split(","):
                                    for slot in self.time_slots:
                                        if slot["day_of_week"] == day and slot["period_number"] == p:
                                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                            if var_name in self.schedule_vars:
                                                no_course_before.append(1 - self.schedule_vars[var_name])
                        
                        if no_course_before and course_vars:
                            # Pénalité proportionnelle à la période (plus c'est tard, plus c'est pénalisé)
                            late_start_penalty.append(first_course * period)
        
        # Combiner les objectifs
        total_penalty = []
        if gap_penalty:
            total_penalty.extend([g * 1000 for g in gap_penalty])  # Très forte pénalité pour les trous
        if late_start_penalty:
            total_penalty.extend([l * 10 for l in late_start_penalty])  # Pénalité pour commencer tard
        
        if total_penalty:
            self.model.Minimize(sum(total_penalty))
            logger.info(f"✓ Objectifs de qualité ajoutés: {len(gap_penalty)} trous à éviter, {len(late_start_penalty)} débuts tardifs à minimiser")

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
        """Extrait la solution du solver avec support des cours parallèles"""
        schedule = []
        
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                parts = var_name.split("_")
                course_id = int(parts[1])
                slot_id = int(parts[3])
                
                course = next((c for c in self.courses if c["course_id"] == course_id), None)
                slot = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if course and slot:
                    # Extraire la liste des profs depuis teacher_names
                    names_str = (course.get("teacher_names") or "")
                    teacher_names = [t.strip() for t in names_str.split(",") if t.strip()]
                    # Pour compatibilité avec l'affichage, garder le premier nom
                    teacher_name_single = teacher_names[0] if teacher_names else ""
                    
                    # Créer une entrée pour chaque classe
                    classes = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
                    for class_name in classes:
                        schedule.append({
                            "course_id": course_id,
                            "slot_id": slot_id,
                            "teacher_name": names_str,  # Liste complète des profs
                            "teacher_names": teacher_names,
                            "subject_name": (course.get("subject_name") or course.get("subject") or ""),
                            "class_name": class_name,
                            "day_of_week": slot["day_of_week"],
                            "period_number": slot["period_number"],
                            "start_time": str(slot["start_time"]),
                            "end_time": str(slot["end_time"]),
                            "is_parallel": bool(course.get("is_parallel")),
                            "group_id": course.get("group_id")
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
            # Rotation simple par cours pour répartir plusieurs profs en parallèle si présent
            rotation_index_by_course = {}
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
                        # Choisir le prof: si plusieurs profs sont listés, on alterne
                        (lambda: (
                            (lambda names: (
                                names.__getitem__(
                                    (rotation_index_by_course.setdefault(entry.get("course_id"), 0)) % len(names)
                                ) if names else ""
                            ))(entry.get("teacher_names") or [])
                        ))(),
                        entry.get("class_name"),
                        entry.get("subject_name"),
                        entry.get("day_of_week"),
                        entry.get("period_number"),
                        bool(entry.get("is_parallel", False)),
                        entry.get("group_id"),
                    ),
                )
                # Mettre à jour l'index de rotation si plusieurs profs
                if entry.get("teacher_names"):
                    rotation_index_by_course[entry.get("course_id")] = rotation_index_by_course.get(entry.get("course_id"), 0) + 1
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

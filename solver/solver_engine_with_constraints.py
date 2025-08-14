# solver_engine_with_constraints.py - Version corrigée avec meilleure distribution
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from parallel_course_handler import ParallelCourseHandler
# Removed fixed_extraction import - functions integrated directly

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
        self.constraints = []
        self.sync_groups = {}  # Groupes de cours à synchroniser
        
    def load_data_from_db(self):
        """Charge les données depuis solver_input et les contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DEPUIS LA BASE ===")
            
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
            logger.info(f"✓ {len(self.courses)} cours après expansion des parallèles")
            logger.info(f"✓ {len(self.sync_groups)} groupes à synchroniser")
            
            cur.execute("""
                SELECT * FROM constraints 
                WHERE is_active = TRUE
                ORDER BY constraint_type, constraint_id
            """)
            self.constraints = cur.fetchall()
            logger.info(f"✓ {len(self.constraints)} contraintes personnalisées actives")
            
            # Vérifier la faisabilité
            cur.execute("SELECT SUM(hours) as total_hours FROM solver_input")
            total_hours = cur.fetchone()['total_hours']
            
            # Calculer les créneaux disponibles en excluant complètement le vendredi
            available_slots = 0
            for slot in self.time_slots:
                # Vendredi complètement exclu
                if slot["day_of_week"] == 5:
                    continue
                available_slots += len(self.classes)
            
            utilization = (total_hours / available_slots * 100) if available_slots > 0 else 0
            
            logger.info(f"\n=== ANALYSE DE FAISABILITÉ ===")
            logger.info(f"Heures totales nécessaires: {total_hours}")
            logger.info(f"Créneaux disponibles (sans vendredi): {available_slots}")
            logger.info(f"Taux d'utilisation: {utilization:.1f}%")
            
            if utilization > 95:
                logger.warning("⚠️ Taux d'utilisation très élevé - emploi du temps difficile à générer")
                
        finally:
            cur.close()
            conn.close()

    def create_variables(self):
        """Crée les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES ===")
        
        for course in self.courses:
            course_id = course["course_id"]
            
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
                
        logger.info(f"✓ {len(self.schedule_vars)} variables créées")

    def add_constraints(self):
        """Ajoute toutes les contraintes au modèle"""
        logger.info("=== AJOUT DES CONTRAINTES ===")
        constraint_count = 0
        
        # 1. CONTRAINTES DE BASE - Heures exactes pour chaque cours
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
        
        # 2. PAS DE CONFLITS PROFESSEUR
        for teacher in self.teachers:
            teacher_name = teacher.get("teacher_name", "")
            for slot in self.time_slots:
                teacher_slot_vars = []
                
                for course in self.courses:
                    if teacher_name in (course.get("teacher_names") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            teacher_slot_vars.append(self.schedule_vars[var_name])
                
                if teacher_slot_vars:
                    self.model.Add(sum(teacher_slot_vars) <= 1)
                    constraint_count += 1
        
        # 3. PAS DE CONFLITS CLASSE
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                class_slot_vars = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            class_slot_vars.append(self.schedule_vars[var_name])
                
                if class_slot_vars:
                    self.model.Add(sum(class_slot_vars) <= 1)
                    constraint_count += 1
        
        # 4. VENDREDI INTERDIT (plus aucun cours le vendredi)
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                # Plus aucun cours le vendredi (jour 5)
                if slot["day_of_week"] == 5:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
                        constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de base ajoutées")
        
        # 5. CONTRAINTES SPÉCIFIQUES DE L'ÉCOLE
        self._add_school_specific_constraints()
        
        # 6. ✅ NOUVELLE: CONTRAINTE DE DISTRIBUTION ÉQUILIBRÉE
        self._add_distribution_constraints()
        
        # 7. LIMITE QUOTIDIENNE PAR MATIÈRE (3h, sauf י/יא/יב: 4h)
        self._add_subject_daily_limits()

        # 8. SYNCHRONISATION DES COURS PARALLÈLES
        self._add_parallel_sync_constraints()

        # 9. CONTRAINTES FORTES: Blocs de matières consécutives (2×2h minimum)
        self._add_subject_block_constraints()

        # 10. CONTRAINTES: PAS DE TROUS (dur) + MAX 3 CONSÉCUTIFS (dur)
        self._add_no_gaps_constraints()
        self._add_subject_run_constraints(max_run=4)  # Augmenté pour permettre 4h d'affilée
        
        # 11. OBJECTIFS DE QUALITÉ
        self._add_quality_objectives()
        
        # 11. TOUS COMMENCENT À LA PREMIÈRE PÉRIODE (période 0)
        self._add_start_first_period_constraints()

    def _add_school_specific_constraints(self):
        """Ajoute les contraintes spécifiques assouplies pour le lundi"""
        logger.info("=== CONTRAINTES LUNDI (ASSOUPLIES) ===")
        
        # Slots du lundi
        monday_slots = [s for s in self.time_slots if s["day_of_week"] == 1]
        
        # Réunions uniquement pour les profs principaux qui enseignent חינוך ou שיח בוקר
        # On considère qu'un "prof principal" est tout enseignant apparaissant sur des cours
        # dont la matière est l'une des deux ci-dessous
        homeroom_subjects = {"חינוך", "שיח בוקר"}
        homeroom_teachers = set()
        for course in self.courses:
            subject = (course.get("subject") or course.get("subject_name") or "").strip()
            if subject in homeroom_subjects:
                for t in (course.get("teacher_names") or "").split(","):
                    t = t.strip()
                    if t:
                        homeroom_teachers.add(t)
        
        # Plages de réunions le lundi à bloquer pour ces enseignants seulement
        # 13:30-15:15 ≈ périodes 6-7, 15:15-16:00 ≈ période 8 (approximatif par périodes)
        monday_meeting_slots = [s for s in monday_slots if 6 <= s["period_number"] <= 8]
        
        if homeroom_teachers and monday_meeting_slots:
            for course in self.courses:
                # Si un des enseignants de ce cours est homeroom ET la classe est en חטיבה (ז/ח/ט)
                course_teachers = {(t or "").strip() for t in (course.get("teacher_names") or "").split(",") if (t or "").strip()}
                course_grade = (course.get("grade") or "").strip()
                if (course_teachers & homeroom_teachers) and (course_grade in {"ז", "ח", "ט"}):
                    for slot in monday_meeting_slots:
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
        
        logger.info("✓ Lundi assoupli: réunions bloquées uniquement pour חינוך/שיח בוקר")

    def _add_distribution_constraints(self):
        """✅ NOUVELLE MÉTHODE: Force une distribution équilibrée sur tous les jours"""
        logger.info("=== CONTRAINTES DE DISTRIBUTION ===")
        
        # Pour chaque classe, forcer une présence minimale chaque jour
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Compter les cours par jour pour cette classe
            for day in range(6):  # Dimanche(0) à Vendredi(5)
                day_courses = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                # Exclure complètement le vendredi
                                if day == 5:
                                    continue
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    day_courses.append(self.schedule_vars[var_name])
                
                if day_courses and day < 5:  # Pas le vendredi
                    # Limiter à max 10 cours par jour (soft), pas de minimum dur
                    self.model.Add(sum(day_courses) <= 10)
                elif day == 5 and day_courses:  # Vendredi
                    # Limiter le vendredi matin à max 5 cours
                    self.model.Add(sum(day_courses) <= 5)
        
        # Pour chaque professeur, éviter la surcharge sur un seul jour
        for teacher in self.teachers:
            teacher_name = teacher.get("teacher_name", "")
            
            for day in range(6):  # Tous les jours
                day_courses = []
                
                for course in self.courses:
                    if teacher_name in (course.get("teacher_names") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                if day == 5:
                                    continue
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    day_courses.append(self.schedule_vars[var_name])
                
                if day_courses:
                    # Maximum 6 heures par jour pour un professeur
                    self.model.Add(sum(day_courses) <= 6)
        
        logger.info("✓ Contraintes de distribution ajoutées")

    def _add_parallel_sync_constraints(self):
        """Synchronise les cours qui doivent être enseignés en parallèle"""
        logger.info("=== CONTRAINTES DE SYNCHRONISATION PARALLÈLE ===")
        
        # Utiliser les groupes de synchronisation créés lors de l'expansion
        constraint_count = ParallelCourseHandler.add_sync_constraints(
            self.model, 
            self.schedule_vars, 
            self.sync_groups, 
            self.time_slots
        )
        
        logger.info(f"✓ Total: {constraint_count} contraintes de synchronisation pour {len(self.sync_groups)} groupes")

    def _add_subject_block_constraints(self):
        """CONTRAINTES FORTES pour regrouper les matières en blocs consécutifs (2×2h ou 4h)"""
        logger.info("=== CONTRAINTES: BLOCS DE MATIÈRES CONSÉCUTIFS ===")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Regrouper les cours par matière pour cette classe
            subjects_courses = {}
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subject = course.get("subject") or course.get("subject_name") or ""
                    if subject:
                        subjects_courses.setdefault(subject, []).append(course)
            
            for subject, courses in subjects_courses.items():
                total_hours = sum(c["hours"] for c in courses)
                
                # Seulement pour les matières avec assez d'heures (≥2h)
                if total_hours < 2:
                    continue
                
                logger.info(f"  → {class_name}/{subject}: {total_hours}h à regrouper")
                
                # Pour chaque jour, créer des variables de blocs consécutifs
                for day in range(5):  # Dimanche à Jeudi
                    day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                    day_slots.sort(key=lambda s: s["period_number"])
                    
                    if len(day_slots) < 2:
                        continue
                    
                    # Variables: cette matière est-elle enseignée sur chaque période ?
                    subject_period_vars = {}
                    for slot in day_slots:
                        period = slot["period_number"]
                        has_subject = self.model.NewBoolVar(f"subj_{class_name}_{subject}_{day}_{period}")
                        
                        # Cette période a cette matière si au moins un cours correspondant y est programmé
                        subject_course_vars = []
                        for course in courses:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                subject_course_vars.append(self.schedule_vars[var_name])
                        
                        if subject_course_vars:
                            # has_subject = 1 ssi au moins un cours de cette matière sur cette période
                            self.model.Add(sum(subject_course_vars) >= has_subject)
                            self.model.Add(sum(subject_course_vars) <= len(subject_course_vars) * has_subject)
                        else:
                            self.model.Add(has_subject == 0)
                        
                        subject_period_vars[period] = has_subject
                    
                    periods = sorted(subject_period_vars.keys())
                    
                    # CONTRAINTE FORTE: Si cette matière est enseignée ce jour,
                    # alors elle DOIT former des blocs consécutifs de minimum 2h
                    
                    # Détecter s'il y a des cours de cette matière ce jour
                    has_subject_today = self.model.NewBoolVar(f"has_{class_name}_{subject}_{day}")
                    period_vars_list = [subject_period_vars[p] for p in periods]
                    self.model.Add(sum(period_vars_list) >= has_subject_today)
                    
                    # Si has_subject_today = 1, alors appliquer les contraintes de blocs
                    if len(periods) >= 2:
                        # Variables pour début et fin de blocs de cette matière
                        for i in range(len(periods)):
                            for j in range(i + 1, len(periods)):  # j > i
                                # Bloc de la période i à j (inclus)
                                block_size = j - i + 1
                                if block_size < 2:  # On veut des blocs d'au moins 2h
                                    continue
                                    
                                # Variable: ce bloc est-il utilisé ?
                                block_var = self.model.NewBoolVar(f"block_{class_name}_{subject}_{day}_{i}_{j}")
                                
                                # Si ce bloc est utilisé, alors toutes les périodes dans [i,j] ont cette matière
                                for k in range(i, j + 1):
                                    if k < len(periods):
                                        period_idx = periods[k]
                                        self.model.Add(subject_period_vars[period_idx] >= block_var)
                                
                                # Et les périodes juste avant/après ne doivent PAS avoir cette matière
                                if i > 0:
                                    before_period = periods[i-1]
                                    self.model.Add(subject_period_vars[before_period] + block_var <= 1)
                                if j < len(periods) - 1:
                                    after_period = periods[j+1]
                                    self.model.Add(subject_period_vars[after_period] + block_var <= 1)
                    
                    # CONTRAINTE SIMPLIFIÉE: Interdire les cours isolés (1h seule)
                    for i, period in enumerate(periods):
                        period_var = subject_period_vars[period]
                        
                        # Si cette période a la matière, alors au moins une période adjacente doit aussi l'avoir
                        adjacent_vars = []
                        if i > 0:
                            adjacent_vars.append(subject_period_vars[periods[i-1]])
                        if i < len(periods) - 1:
                            adjacent_vars.append(subject_period_vars[periods[i+1]])
                        
                        if adjacent_vars:
                            # period_var <= sum(adjacent_vars) 
                            # (si cette période est active, au moins une adjacente doit l'être)
                            self.model.Add(sum(adjacent_vars) >= period_var)
        
        logger.info("  ✓ Contraintes de blocs consécutifs ajoutées")

    def _add_quality_objectives(self):
        """Objectifs pour améliorer la qualité de l'emploi du temps"""
        logger.info("=== OBJECTIFS DE QUALITÉ ===")
        
        penalties = []
        
        # 1. MINIMISER LES TROUS dans l'emploi du temps (objectif fort au lieu de contrainte dure)
        gap_penalties = self._calculate_gap_penalties()
        penalties.extend([p * 10 for p in gap_penalties])
        
        
        # 3. PRIVILÉGIER LE REGROUPEMENT DES MATIÈRES
        scatter_penalties = self._calculate_scatter_penalties()
        penalties.extend(scatter_penalties)
        
        # 4. MATHÉMATIQUES - Éviter 4 heures dispersées sur une journée
        math_penalties = self._calculate_math_dispersion_penalties()
        penalties.extend(math_penalties)

        # 5. ÉTALER SUR 5 JOURS: encourager l'utilisation de tous les jours (dim-jeu)
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            day_used_vars = []
            for day in range(5):
                day_vars = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[vname])
                if day_vars:
                    day_has = self.model.NewBoolVar(f"day_used_{class_name}_{day}")
                    self.model.Add(day_has <= len(day_vars))
                    self.model.Add(sum(day_vars) >= day_has)
                    day_used_vars.append(day_has)
            if day_used_vars:
                # Pénaliser les jours non utilisés (viser 5 jours utilisés)
                penalties.append((5 - sum(day_used_vars)) * 50)

        # 6. FIN TARDIVE: pénaliser fortement l'utilisation des 2 dernières périodes (tout en restant soft)
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for day in range(5):
                late_vars = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day and slot["period_number"] >= 10:  # très tard
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    late_vars.append(self.schedule_vars[vname])
                if late_vars:
                    # Pénalité par occurrence tardive
                    penalties.append(sum(late_vars) * 40)
        
        # Appliquer l'objectif global
        if penalties:
            self.model.Minimize(sum(penalties))
            logger.info(f"✓ {len(penalties)} pénalités ajoutées à l'objectif")

    def _add_no_gaps_constraints(self):
        """Contraintes RENFORCÉES pour minimiser les trous."""
        logger.info("=== CONTRAINTES: MINIMISATION DES TROUS ===")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):  # Dimanche(0) à Jeudi(4) - pas le vendredi
                # Récupérer tous les créneaux du jour, triés par période
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                if len(day_slots) < 3:
                    continue
                
                # Variables: la classe a-t-elle cours à chaque période ?
                period_has_course = {}
                for slot in day_slots:
                    period = slot["period_number"]
                    has_course = self.model.NewBoolVar(f"has_course_{class_name}_{day}_{period}")
                    
                    # Collecter tous les cours de cette classe sur ce créneau
                    course_vars = []
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                course_vars.append(self.schedule_vars[var_name])
                    
                    if course_vars:
                        # has_course = 1 si au moins un cours sur cette période
                        self.model.Add(sum(course_vars) >= has_course)
                        self.model.Add(sum(course_vars) <= len(course_vars) * has_course)
                    else:
                        self.model.Add(has_course == 0)
                    
                    period_has_course[period] = has_course
                
                # CONTRAINTE RENFORCÉE: Interdire les trous isolés
                # Modèle [1,0,1] et [1,0,0,1] et [1,0,1,0,1] etc.
                periods = sorted(period_has_course.keys())
                
                # Interdire tous les motifs de trous sur 3, 4 et 5 périodes consécutives
                for window_size in [3, 4, 5]:
                    for i in range(len(periods) - window_size + 1):
                        window_periods = periods[i:i + window_size]
                        
                        # Vérifier que les périodes sont vraiment consécutives
                        consecutive = True
                        for j in range(1, len(window_periods)):
                            if window_periods[j] != window_periods[j-1] + 1:
                                consecutive = False
                                break
                        
                        if not consecutive:
                            continue
                        
                        # Interdire le motif [1, 0, ..., 0, 1] (cours-trous-cours)
                        # Si première ET dernière période de la fenêtre ont cours,
                        # alors au moins une période intermédiaire doit avoir cours
                        if len(window_periods) >= 3:
                            first_period = window_periods[0]
                            last_period = window_periods[-1]
                            middle_periods = window_periods[1:-1]
                            
                            if middle_periods:
                                # Si first ET last ont cours, alors au moins un middle doit avoir cours
                                middle_sum = sum(period_has_course[p] for p in middle_periods)
                                self.model.Add(
                                    middle_sum >= period_has_course[first_period] + period_has_course[last_period] - 1
                                )
                
                logger.debug(f"  ✓ {class_name} jour {day}: contraintes anti-trous sur {len(periods)} périodes")
        
        logger.info("  ✓ Contraintes de minimisation des trous ajoutées")

    def _add_subject_run_constraints(self, max_run: int = 3):
        """Limite la longueur des séquences consécutives d'une même matière par classe et par jour."""
        logger.info("=== CONTRAINTES: LONGUEUR DE SÉQUENCE PAR MATIÈRE ===")
        # Indexer cours par (classe, matière)
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            # Collecter toutes les matières pour cette classe
            subjects = set()
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subjects.add(course.get("subject") or course.get("subject_name") or "")
            for subject in subjects:
                for day in range(5):
                    day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                    day_slots.sort(key=lambda s: s["period_number"])
                    # subject_at[p]
                    subj_vars = []
                    for slot in day_slots:
                        var = self.model.NewBoolVar(f"subj_{class_name}_{day}_{subject}_{slot['period_number']}")
                        course_vars = []
                        for course in self.courses:
                            same_class = class_name in (course.get("class_list") or "").split(",")
                            same_subject = (course.get("subject") or course.get("subject_name") or "") == subject
                            if same_class and same_subject:
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    course_vars.append(self.schedule_vars[vname])
                        if course_vars:
                            # var == OR(course_vars)
                            self.model.Add(sum(course_vars) >= var)
                            self.model.Add(sum(course_vars) <= len(course_vars) * var)
                        else:
                            self.model.Add(var == 0)
                        subj_vars.append(var)
                    # Fenêtre glissante de taille max_run+1: somme <= max_run
                    w = max_run + 1
                    for start in range(0, max(0, len(subj_vars) - w + 1)):
                        window = subj_vars[start:start + w]
                        self.model.Add(sum(window) <= max_run)

    def _add_subject_daily_limits(self):
        """Impose une limite quotidienne d'heures par matière: 3h par jour (par classe),
        sauf pour les classes de lycée (י/יא/יב) où la limite est 4h."""
        logger.info("=== CONTRAINTES: LIMITE QUOTIDIENNE PAR MATIÈRE ===")
        hs_grades = {"י", "יא", "יב"}
        # Préparer un mapping classe -> grade (premier grade rencontré)
        class_to_grade = {}
        for course in self.courses:
            grade = (course.get("grade") or "").strip()
            classes = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
            for cn in classes:
                class_to_grade.setdefault(cn, grade or class_to_grade.get(cn, ""))

        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            grade = class_to_grade.get(class_name, "")
            daily_limit = 4 if grade in hs_grades else 3

            # Récupérer les matières enseignées à cette classe
            subjects = set()
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subjects.add((course.get("subject") or course.get("subject_name") or "").strip())

            for subject in subjects:
                if not subject:
                    continue
                for day in range(6):  # Dimanche(0) à Vendredi(5)
                    day_subject_vars = []
                    for course in self.courses:
                        same_class = class_name in (course.get("class_list") or "").split(",")
                        same_subject = ((course.get("subject") or course.get("subject_name") or "").strip() == subject)
                        if same_class and same_subject:
                            for slot in self.time_slots:
                                if slot["day_of_week"] == day:
                                    vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                    if vname in self.schedule_vars:
                                        day_subject_vars.append(self.schedule_vars[vname])
                    if day_subject_vars:
                        self.model.Add(sum(day_subject_vars) <= daily_limit)

    def _add_start_first_period_constraints(self):
        """Impose: chaque classe commence à la première période (0) chaque jour où elle a cours."""
        logger.info("=== CONTRAINTES: DÉBUT À LA PÉRIODE 0 ===")
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for day in range(5):  # Dimanche (0) à Jeudi (4)
                # Tous les créneaux de ce jour
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                if not day_slots:
                    continue
                day_slots.sort(key=lambda s: s["period_number"])
                has_vars = []
                for slot in day_slots:
                    period = slot["period_number"]
                    has_var = self.model.NewBoolVar(f"has_{class_name}_{day}_{period}")
                    # OR de tous les cours de cette classe sur ce créneau
                    course_vars = []
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if vname in self.schedule_vars:
                                course_vars.append(self.schedule_vars[vname])
                    if course_vars:
                        self.model.Add(sum(course_vars) >= has_var)
                        self.model.Add(sum(course_vars) <= len(course_vars) * has_var)
                    else:
                        self.model.Add(has_var == 0)
                    has_vars.append(has_var)
                # has_day = OR des has_vars
                has_day = self.model.NewBoolVar(f"hasday_{class_name}_{day}")
                self.model.Add(sum(has_vars) >= has_day)
                self.model.Add(sum(has_vars) <= len(has_vars) * has_day)
                # Si la classe a cours ce jour-là, alors la première période (index 0) doit être occupée
                first_has = has_vars[0]
                self.model.Add(first_has >= has_day)

    def _calculate_gap_penalties(self):
        """Calcule les pénalités pour les trous dans l'emploi du temps"""
        gap_penalties = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(6):
                # Créer des variables pour détecter les trous
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                for i in range(1, len(day_slots) - 1):
                    # Un trou existe si: pas de cours à i, mais cours avant et après
                    gap = self.model.NewBoolVar(f"gap_{class_name}_{day}_{i}")
                    
                    has_before = []
                    has_current = []
                    has_after = []
                    
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            # Cours avant
                            if i > 0:
                                var_before = f"course_{course['course_id']}_slot_{day_slots[i-1]['slot_id']}"
                                if var_before in self.schedule_vars:
                                    has_before.append(self.schedule_vars[var_before])
                            
                            # Cours actuel
                            var_current = f"course_{course['course_id']}_slot_{day_slots[i]['slot_id']}"
                            if var_current in self.schedule_vars:
                                has_current.append(self.schedule_vars[var_current])
                            
                            # Cours après
                            if i < len(day_slots) - 1:
                                var_after = f"course_{course['course_id']}_slot_{day_slots[i+1]['slot_id']}"
                                if var_after in self.schedule_vars:
                                    has_after.append(self.schedule_vars[var_after])
                    
                    # Désactivé: CP-SAT ne supporte pas directement ces comparaisons booléennes dans Add
        
        return gap_penalties

    def _calculate_late_subject_penalties(self):
        """Pénalise les matières difficiles en fin de journée"""
        penalties = []
        
        difficult_subjects = ['מתמטיקה', 'math', 'physique', 'פיזיקה', 'כימיה', 'chimie']
        
        for course in self.courses:
            subject = course.get("subject", course.get("subject_name", "")).lower()
            if any(subj in subject for subj in difficult_subjects):
                for slot in self.time_slots:
                    # Après 14h (période 7+)
                    if slot["period_number"] >= 7:
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            # Pénalité proportionnelle à l'heure tardive
                            penalty = (slot["period_number"] - 6) * 20
                            penalties.append(self.schedule_vars[var_name] * penalty)
        
        return penalties

    def _calculate_scatter_penalties(self):
        """Pénalise l'éparpillement d'une même matière sur plusieurs jours"""
        penalties = []
        
        # Pour chaque combinaison classe-matière
        subject_by_class = {}
        for course in self.courses:
            classes = [c.strip() for c in (course.get("class_list") or "").split(",")]
            subject = course.get("subject", course.get("subject_name", ""))
            
            for class_name in classes:
                key = f"{class_name}_{subject}"
                if key not in subject_by_class:
                    subject_by_class[key] = []
                subject_by_class[key].append(course)
        
        # Pénaliser si une matière est sur trop de jours différents
        for key, courses in subject_by_class.items():
            if len(courses) > 2:  # Si plus de 2 heures de cette matière
                days_used = []
                for day in range(6):
                    day_has_course = self.model.NewBoolVar(f"has_{key}_day_{day}")
                    
                    day_vars = []
                    for course in courses:
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[var_name])
                    
                    if day_vars:
                        # day_has_course = 1 si au moins un cours ce jour
                        self.model.Add(day_has_course <= len(day_vars))
                        self.model.Add(sum(day_vars) >= day_has_course)
                        days_used.append(day_has_course)
                
                # Pénaliser si plus de 3 jours utilisés
                if len(days_used) > 3:
                    penalties.append(sum(days_used) * 30)
        
        return penalties

    def _calculate_math_dispersion_penalties(self):
        """Évite d'avoir 4 heures de maths dispersées sur une journée"""
        penalties = []
        
        math_keywords = ['מתמטיקה', 'math', 'mathématiques']
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Trouver les cours de maths pour cette classe
            math_courses = []
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subject = course.get("subject", course.get("subject_name", "")).lower()
                    if any(kw in subject for kw in math_keywords):
                        math_courses.append(course)
            
            # Pour chaque jour, pénaliser s'il y a 4 heures de maths non consécutives
            for day in range(6):
                day_math_slots = []
                
                for course in math_courses:
                    for slot in self.time_slots:
                        if slot["day_of_week"] == day:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                day_math_slots.append((slot["period_number"], 
                                                      self.schedule_vars[var_name]))
                
                if len(day_math_slots) >= 4:
                    # Trier par période
                    day_math_slots.sort(key=lambda x: x[0])
                    
                    # Calculer la dispersion (écart entre première et dernière heure)
                    first_period = day_math_slots[0][0]
                    last_period = day_math_slots[-1][0]
                    dispersion = last_period - first_period
                    
                    # Pénaliser si trop dispersé (plus de 5 périodes d'écart)
                    if dispersion > 5:
                        for _, var in day_math_slots:
                            penalties.append(var * (dispersion - 5) * 25)
        
        return penalties
    
    def _add_weekly_balance_objectives(self):
        """Objectifs pour équilibrer la charge sur la semaine avec variables binaires"""
        logger.info("=== OBJECTIFS: ÉQUILIBRAGE HEBDOMADAIRE OPTIMAL ===")
        
        balance_penalties = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Variables binaires: cette classe a-t-elle des cours le jour X?
            day_used_vars = []
            daily_hours = []
            
            for day in range(5):  # Dimanche à Jeudi
                # Variable binaire: jour utilisé
                day_used = self.model.NewBoolVar(f"day_used_{class_name}_{day}")
                
                # Compter les heures ce jour
                day_hours = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    day_hours.append(self.schedule_vars[vname])
                
                if day_hours:
                    # Variable entière: nombre d'heures ce jour
                    hours_today = self.model.NewIntVar(0, len(day_hours), f"hours_{class_name}_{day}")
                    self.model.Add(hours_today == sum(day_hours))
                    daily_hours.append(hours_today)
                    
                    # day_used = 1 si au moins 1 heure ce jour
                    self.model.Add(day_used <= len(day_hours))
                    self.model.Add(sum(day_hours) >= day_used)
                    self.model.Add(sum(day_hours) <= len(day_hours) * day_used)
                    
                    day_used_vars.append(day_used)
                    
                    # Pénaliser les déséquilibres extrêmes (plus de 8h par jour)
                    excess_hours = self.model.NewIntVar(0, len(day_hours), f"excess_{class_name}_{day}")
                    self.model.Add(excess_hours >= hours_today - 8)
                    balance_penalties.append(excess_hours * 500)  # Pénalité forte
                    
                    # Pénaliser les journées trop légères (moins de 4h si jour utilisé)
                    light_penalty = self.model.NewIntVar(0, 4, f"light_{class_name}_{day}")
                    self.model.Add(light_penalty >= (4 - hours_today) * day_used)
                    balance_penalties.append(light_penalty * 200)
            
            # Objectif: utiliser exactement 5 jours (ou le maximum possible)
            if day_used_vars:
                days_unused = self.model.NewIntVar(0, 5, f"unused_days_{class_name}")
                self.model.Add(days_unused == 5 - sum(day_used_vars))
                balance_penalties.append(days_unused * 300)  # Pénalité modérée
                
                # Pénaliser si moins de 4 jours utilisés (trop concentré)
                too_concentrated = self.model.NewBoolVar(f"concentrated_{class_name}")
                self.model.Add(too_concentrated == (sum(day_used_vars) <= 3))
                balance_penalties.append(too_concentrated * 800)  # Pénalité très forte
        
        logger.info(f"✓ {len(balance_penalties)} objectifs d'équilibrage hebdomadaire créés")
        return balance_penalties
    
    def _calculate_late_slot_penalties(self):
        """Calcule les pénalités pour l'utilisation des créneaux tardifs"""
        penalties = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                period = slot["period_number"]
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                
                                if vname in self.schedule_vars:
                                    # Pénalité progressive selon l'heure tardive
                                    if period >= 8:  # Après 16h
                                        late_penalty = (period - 7) * 2
                                        penalties.append(self.schedule_vars[vname] * late_penalty)
        
        return penalties
    
    def _calculate_consecutive_bonuses(self):
        """Calcule les bonus pour les cours consécutifs (même classe, même jour)"""
        bonuses = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                # Variables: cours de cette classe à chaque période
                period_vars = []
                for slot in day_slots:
                    class_courses = []
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if vname in self.schedule_vars:
                                class_courses.append(self.schedule_vars[vname])
                    
                    if class_courses:
                        period_var = self.model.NewBoolVar(f"period_{class_name}_{day}_{slot['period_number']}")
                        self.model.Add(sum(class_courses) >= period_var)
                        self.model.Add(sum(class_courses) <= len(class_courses) * period_var)
                        period_vars.append(period_var)
                
                # Bonus pour les séquences consécutives de 2+ périodes
                for i in range(len(period_vars) - 1):
                    consecutive_pair = self.model.NewBoolVar(f"consec_{class_name}_{day}_{i}")
                    self.model.Add(consecutive_pair <= period_vars[i])
                    self.model.Add(consecutive_pair <= period_vars[i + 1])
                    self.model.Add(consecutive_pair >= period_vars[i] + period_vars[i + 1] - 1)
                    bonuses.append(consecutive_pair)  # Bonus pour chaque paire consécutive
        
        return bonuses
    
    def _configure_solver_for_compactness(self, time_limit):
        """Configure le solver OR-Tools de manière optimale pour maximiser la compacité"""
        logger.info("=== CONFIGURATION SOLVER POUR COMPACITÉ ===")
        
        # Temps de calcul optimisé
        self.solver.parameters.max_time_in_seconds = time_limit
        
        # Parallélisation maximale
        self.solver.parameters.num_search_workers = 8
        
        # Logging pour diagnostics
        self.solver.parameters.log_search_progress = True
        
        # Stratégie de recherche optimisée pour l'optimisation
        self.solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        
        # Linéarisation avancée pour les contraintes complexes
        self.solver.parameters.linearization_level = 2
        
        # Prétraitement du modèle activé
        self.solver.parameters.cp_model_presolve = True
        
        # Optimisation des coupes pour l'objectif
        self.solver.parameters.cut_level = 1
        
        # Stratégie d'optimisation focalisée sur l'objectif
        self.solver.parameters.optimize_with_core = True
        
        # Amélioration continue même après solution trouvée
        self.solver.parameters.find_multiple_cores = True
        
        # Réduction agressive pour améliorer performance
        self.solver.parameters.cp_model_probing_level = 2
        
        logger.info("✓ Solver configuré pour optimisation maximale de la compacité")

    def solve(self, time_limit=600):
        """Résout le problème avec temps augmenté"""
        logger.info("\n=== RÉSOLUTION ===")
        
        try:
            self.create_variables()
            if not self.schedule_vars:
                logger.error("Aucune variable créée!")
                return []
                
            self.add_constraints()
            
            # Configuration optimisée du solver pour la compacité
            self._configure_solver_for_compactness(time_limit)
            
            logger.info(f"Lancement du solver (limite: {time_limit}s)...")
            status = self.solver.Solve(self.model)
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! Status: {self.solver.StatusName(status)}")
                schedule = self._extract_solution()
                
                # Afficher les statistiques de la solution
                self._log_solution_stats(schedule)
                
                return schedule
            else:
                logger.error(f"❌ Pas de solution. Status: {self.solver.StatusName(status)}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la résolution : {e}")
            raise

    def _log_solution_stats(self, schedule):
        """Affiche les statistiques de la solution trouvée"""
        if not schedule:
            return
            
        # Analyser la distribution
        by_day = {}
        by_class = {}
        
        for entry in schedule:
            day = entry["day_of_week"]
            class_name = entry["class_name"]
            
            by_day[day] = by_day.get(day, 0) + 1
            by_class[class_name] = by_class.get(class_name, 0) + 1
        
        logger.info("\n=== STATISTIQUES DE LA SOLUTION ===")
        logger.info(f"Total de créneaux: {len(schedule)}")
        logger.info("Distribution par jour:")
        days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        for day in range(6):
            count = by_day.get(day, 0)
            logger.info(f"  {days[day]}: {count} créneaux")
        
        logger.info(f"Classes couvertes: {len(by_class)}")
        logger.info(f"Moyenne par classe: {len(schedule) / max(len(by_class), 1):.1f} heures")

    def _extract_solution(self):
        """Extrait la solution du solver sans conflits ni doublons"""
        logger.info("Extraction directe de la solution...")
        schedule = []
        
        # Extraction simple et directe
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars and self.solver.Value(self.schedule_vars[var_name]) == 1:
                    schedule_entry = {
                        'teacher_name': course.get('teacher_name', 'Unknown'),
                        'class_name': course.get('class_name', 'Unknown'),
                        'subject_name': course.get('subject_name', course.get('subject', 'Unknown')),
                        'day_of_week': slot['day_of_week'],
                        'period_number': slot['period_number'],
                        'is_parallel_group': course.get('is_parallel', False),
                        'group_id': course.get('group_id')
                    }
                    schedule.append(schedule_entry)
        
        # Analyser les trous simplement
        gaps_count = self._simple_gaps_analysis(schedule)
        if gaps_count > 0:
            logger.warning(f"⚠️ {gaps_count} trous détectés dans l'emploi du temps")
        else:
            logger.info("✅ Aucun trou détecté")
            
        return schedule
    
    def _simple_gaps_analysis(self, schedule):
        """Analyse simple des trous"""
        gaps_count = 0
        
        # Grouper par classe et jour
        for class_info in self.classes:
            class_name = class_info.get('class_name', class_info)
            
            for day in range(5):  # Dimanche-Jeudi
                # Périodes de cette classe ce jour
                day_periods = []
                for entry in schedule:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        day_periods.append(entry['period_number'])
                
                if len(day_periods) >= 2:
                    day_periods.sort()
                    # Compter trous entre première et dernière période
                    for period in range(day_periods[0] + 1, day_periods[-1]):
                        if period not in day_periods:
                            gaps_count += 1
        
        return gaps_count

    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps dans la base de données"""
        if not schedule:
            raise ValueError("Schedule vide")

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
            """, ("2024-2025", 1, "active", datetime.now()))
            schedule_id = cur.fetchone()[0]

            for entry in schedule:
                # Afficher TOUS les professeurs seulement pour les cours parallèles
                if entry.get("is_parallel"):
                    teacher_names_list = entry.get("teacher_names") or []
                    if isinstance(teacher_names_list, str):
                        teacher_names_list = [name.strip() for name in teacher_names_list.split(",") if name.strip()]
                    teacher_name = ", ".join(teacher_names_list) if teacher_names_list else ""
                else:
                    # Cours normal : un seul professeur
                    teacher_name = (entry.get("teacher_names") or [""])[0] if entry.get("teacher_names") else ""
                
                cur.execute("""
                    INSERT INTO schedule_entries (
                        schedule_id, teacher_name, class_name, subject,
                        day_of_week, period_number, is_parallel_group, group_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    teacher_name,
                    entry.get("class_name"),
                    entry.get("subject_name") or entry.get("subject"),
                    entry.get("day_of_week"),
                    entry.get("period_number"),
                    bool(entry.get("is_parallel", False)),
                    entry.get("group_id")
                ))

            conn.commit()
            logger.info(f"✅ Emploi du temps sauvegardé (ID {schedule_id})")
            return schedule_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    def get_schedule_summary(self, schedule):
        """Retourne des statistiques sur l'emploi du temps généré"""
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
            "subjects_count": len(set(e.get("subject_name") or e.get("subject") or "" for e in schedule)),
            "distribution_by_day": by_day,
            "average_per_day": len(schedule) / max(len(days_used), 1)
        }
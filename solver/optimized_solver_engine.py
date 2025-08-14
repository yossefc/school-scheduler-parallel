# optimized_solver_engine.py - Version optimisée avec toutes les améliorations
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from parallel_course_handler import ParallelCourseHandler

logger = logging.getLogger(__name__)

class OptimizedScheduleSolver:
    def __init__(self, db_config=None):
        """Initialise le solver avec optimisations pour la compacité"""
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
        self.sync_groups = {}
        
        # Variables pour l'optimisation de la compacité
        self.compacity_penalties = []
        self.balance_penalties = []

    def load_data_from_db(self):
        """Charge les données depuis solver_input et les contraintes"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DEPUIS LA BASE (SOLVER OPTIMISÉ) ===")
            
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
            
        finally:
            cur.close()
            conn.close()

    def create_variables(self):
        """Crée les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES (OPTIMISÉ) ===")
        
        for course in self.courses:
            course_id = course["course_id"]
            
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
                
        logger.info(f"✓ {len(self.schedule_vars)} variables créées")

    def add_basic_constraints(self):
        """Ajoute les contraintes de base (non-superposition, heures exactes)"""
        logger.info("=== CONTRAINTES DE BASE ===")
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
                if slot["day_of_week"] == 5:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
                        constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes de base ajoutées")

    def add_compactness_optimization(self):
        """Ajoute l'optimisation pour la compacité maximale (élimination des trous)"""
        logger.info("=== OPTIMISATION DE LA COMPACITÉ ===")
        
        self.compacity_penalties = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):  # Dimanche(0) à Jeudi(4)
                # Récupérer tous les créneaux du jour
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                if len(day_slots) < 2:
                    continue
                
                # Variables: cette classe a-t-elle cours à chaque période?
                period_vars = []
                for slot in day_slots:
                    period_var = self.model.NewBoolVar(f"has_{class_name}_{day}_{slot['period_number']}")
                    
                    # Cours de cette classe sur ce créneau
                    class_courses = []
                    for course in self.courses:
                        if class_name in (course.get("class_list") or "").split(","):
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                class_courses.append(self.schedule_vars[var_name])
                    
                    if class_courses:
                        # period_var = 1 si au moins un cours
                        self.model.Add(sum(class_courses) >= period_var)
                        self.model.Add(sum(class_courses) <= len(class_courses) * period_var)
                    else:
                        self.model.Add(period_var == 0)
                    
                    period_vars.append(period_var)
                
                # COMPACITÉ: Variables pour première et dernière période utilisée
                if len(period_vars) >= 2:
                    # Variables pour début et fin
                    first_used = self.model.NewIntVar(0, len(period_vars)-1, f"first_{class_name}_{day}")
                    last_used = self.model.NewIntVar(0, len(period_vars)-1, f"last_{class_name}_{day}")
                    
                    # Cette classe a-t-elle des cours ce jour?
                    has_courses_today = self.model.NewBoolVar(f"active_{class_name}_{day}")
                    self.model.Add(sum(period_vars) >= has_courses_today)
                    self.model.Add(sum(period_vars) <= len(period_vars) * has_courses_today)
                    
                    # Contraintes pour first_used et last_used
                    for i, period_var in enumerate(period_vars):
                        # Si cette période est utilisée:
                        # first_used <= i et last_used >= i
                        big_m = len(period_vars)
                        self.model.Add(first_used <= i + (1 - period_var) * big_m)
                        self.model.Add(last_used >= i - (1 - period_var) * big_m)
                    
                    # CONTRAINTE DE COMPACITÉ: Toutes les périodes entre first et last doivent être utilisées
                    for i, period_var in enumerate(period_vars):
                        # Si first_used <= i <= last_used ET has_courses_today, alors period_var = 1
                        in_range = self.model.NewBoolVar(f"in_range_{class_name}_{day}_{i}")
                        
                        # in_range = (first_used <= i) AND (i <= last_used) AND has_courses_today
                        self.model.Add(first_used <= i + (1 - in_range) * big_m)
                        self.model.Add(last_used >= i - (1 - in_range) * big_m)
                        self.model.Add(has_courses_today >= in_range)
                        
                        # Si in_range, alors period_var doit être 1
                        self.model.Add(period_var >= in_range)
                    
                    # Objectif: minimiser la span (last - first) quand il y a des cours
                    span = self.model.NewIntVar(0, len(period_vars), f"span_{class_name}_{day}")
                    self.model.Add(span >= last_used - first_used)
                    
                    # Pénalité: span seulement si has_courses_today = 1
                    span_penalty = self.model.NewIntVar(0, len(period_vars), f"span_pen_{class_name}_{day}")
                    # span_penalty = span si has_courses_today, 0 sinon
                    self.model.Add(span_penalty <= span)
                    self.model.Add(span_penalty <= has_courses_today * len(period_vars))
                    self.model.Add(span_penalty >= span - (1 - has_courses_today) * len(period_vars))
                    
                    self.compacity_penalties.append(span_penalty)
        
        logger.info(f"✓ {len(self.compacity_penalties)} pénalités de compacité créées")

    def add_weekly_balance_optimization(self):
        """Ajoute l'optimisation pour l'équilibrage hebdomadaire"""
        logger.info("=== OPTIMISATION DE L'ÉQUILIBRAGE HEBDOMADAIRE ===")
        
        self.balance_penalties = []
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Variables: cette classe utilise-t-elle le jour X?
            day_used_vars = []
            daily_hours_vars = []
            
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
                    daily_hours_vars.append(hours_today)
                    
                    # day_used = 1 si au moins 1 heure
                    self.model.Add(day_used <= len(day_hours))
                    self.model.Add(sum(day_hours) >= day_used)
                    self.model.Add(sum(day_hours) <= len(day_hours) * day_used)
                    day_used_vars.append(day_used)
                    
                    # Pénaliser les journées trop chargées (>8h)
                    excess = self.model.NewIntVar(0, len(day_hours), f"excess_{class_name}_{day}")
                    self.model.Add(excess >= hours_today - 8)
                    self.balance_penalties.append(excess * 10)  # Pénalité forte
                    
                    # Pénaliser les journées trop légères (<4h si utilisées) - version simplifiée
                    light_day = self.model.NewBoolVar(f"light_day_{class_name}_{day}")
                    # light_day = 1 si day_used = 1 ET hours_today < 4
                    self.model.Add(hours_today >= 4 - (1 - light_day) * 10)  # Si light_day=0, pas de contrainte
                    self.model.Add(hours_today <= 3 + (1 - light_day) * 10)  # Si light_day=1, hours_today <= 3
                    self.model.Add(light_day <= day_used)  # light_day ne peut être 1 que si day_used = 1
                    self.balance_penalties.append(light_day * 20)  # Pénalité fixe pour jour trop léger
            
            # Encourager l'utilisation de tous les jours (5 jours idéal)
            if day_used_vars:
                unused_days = self.model.NewIntVar(0, 5, f"unused_{class_name}")
                self.model.Add(unused_days == 5 - sum(day_used_vars))
                self.balance_penalties.append(unused_days * 20)  # Pénalité modérée
        
        logger.info(f"✓ {len(self.balance_penalties)} pénalités d'équilibrage créées")

    def add_optimization_objective(self):
        """Configure l'objectif d'optimisation multi-critères"""
        logger.info("=== OBJECTIF D'OPTIMISATION MULTI-CRITÈRES ===")
        
        objectives = []
        
        # 1. PRIORITÉ MAXIMALE: Compacité (élimination des trous)
        if self.compacity_penalties:
            objectives.extend([penalty * 1000 for penalty in self.compacity_penalties])  # Poids très élevé
            logger.info(f"✓ Compacité: {len(self.compacity_penalties)} pénalités (poids 1000)")
        
        # 2. PRIORITÉ ÉLEVÉE: Équilibrage hebdomadaire
        if self.balance_penalties:
            objectives.extend([penalty * 100 for penalty in self.balance_penalties])  # Poids élevé
            logger.info(f"✓ Équilibrage: {len(self.balance_penalties)} pénalités (poids 100)")
        
        # 3. PRIORITÉ MODÉRÉE: Éviter les créneaux tardifs
        late_penalties = []
        for course in self.courses:
            for slot in self.time_slots:
                if slot["period_number"] >= 8:  # Après 16h
                    vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if vname in self.schedule_vars:
                        penalty_weight = (slot["period_number"] - 7) * 5
                        late_penalties.append(self.schedule_vars[vname] * penalty_weight)
        
        objectives.extend(late_penalties)  # Poids modéré (5-25)
        logger.info(f"✓ Créneaux tardifs: {len(late_penalties)} pénalités (poids 5-25)")
        
        # Appliquer l'objectif global
        if objectives:
            self.model.Minimize(sum(objectives))
            logger.info(f"✓ Objectif multi-critères avec {len(objectives)} composants")
        else:
            logger.warning("Aucun objectif défini")

    def configure_solver_for_optimization(self, time_limit=600):
        """Configure le solver pour l'optimisation avancée"""
        logger.info("=== CONFIGURATION SOLVER POUR OPTIMISATION ===")
        
        # Temps et parallélisation
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.num_search_workers = 8
        
        # Stratégies d'optimisation
        self.solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        self.solver.parameters.optimize_with_core = True
        
        # Prétraitement et coupes
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.cut_level = 1
        
        # Logging
        self.solver.parameters.log_search_progress = True
        
        logger.info(f"✓ Solver configuré (temps limite: {time_limit}s)")

    def solve(self, time_limit=600):
        """Résout le problème avec optimisation maximale"""
        logger.info("\n=== RÉSOLUTION AVEC OPTIMISATION MAXIMALE ===")
        
        try:
            # 1. Créer les variables
            self.create_variables()
            if not self.schedule_vars:
                logger.error("Aucune variable créée!")
                return []
            
            # 2. Contraintes de base (obligatoires)
            self.add_basic_constraints()
            
            # 3. Optimisations avancées
            self.add_compactness_optimization()
            self.add_weekly_balance_optimization()
            
            # 4. Objectif multi-critères
            self.add_optimization_objective()
            
            # 5. Configuration du solver
            self.configure_solver_for_optimization(time_limit)
            
            # 6. Résolution
            logger.info(f"Lancement de la résolution optimisée (limite: {time_limit}s)...")
            start_time = datetime.now()
            status = self.solver.Solve(self.model)
            end_time = datetime.now()
            
            solving_time = (end_time - start_time).total_seconds()
            logger.info(f"⏱️ Temps de résolution: {solving_time:.1f}s")
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! Status: {self.solver.StatusName(status)}")
                schedule = self._extract_solution()
                
                # Analyser la qualité de la solution
                self._analyze_solution_quality(schedule)
                
                return schedule
            else:
                logger.error(f"❌ Pas de solution. Status: {self.solver.StatusName(status)}")
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
                    names_str = (course.get("teacher_names") or "")
                    teacher_names = [t.strip() for t in names_str.split(",") if t.strip()]
                    is_parallel = course.get("is_parallel", False)
                    
                    if is_parallel:
                        display_teacher_name = names_str
                    else:
                        display_teacher_name = teacher_names[0] if teacher_names else ""
                    
                    classes = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
                    for class_name in classes:
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
                        })
        
        return schedule

    def _analyze_solution_quality(self, schedule):
        """Analyse la qualité de la solution trouvée"""
        if not schedule:
            return
            
        logger.info("\n=== ANALYSE DE LA QUALITÉ DE LA SOLUTION ===")
        
        # 1. Analyser la compacité (trous)
        total_gaps = 0
        classes_days = {}
        
        for entry in schedule:
            class_name = entry["class_name"]
            day = entry["day_of_week"]
            period = entry["period_number"]
            
            key = f"{class_name}_{day}"
            if key not in classes_days:
                classes_days[key] = []
            classes_days[key].append(period)
        
        for key, periods in classes_days.items():
            if len(periods) < 2:
                continue
                
            periods.sort()
            for i in range(len(periods) - 1):
                gap_size = periods[i+1] - periods[i] - 1
                total_gaps += gap_size
        
        if total_gaps == 0:
            logger.info("✅ COMPACITÉ PARFAITE: 0 trous détectés")
        else:
            logger.warning(f"⚠️ {total_gaps} trous détectés")
        
        # 2. Analyser l'équilibrage
        class_daily_hours = {}
        for entry in schedule:
            class_name = entry["class_name"]
            day = entry["day_of_week"]
            
            if class_name not in class_daily_hours:
                class_daily_hours[class_name] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
            
            class_daily_hours[class_name][day] += 1
        
        balanced_classes = 0
        for class_name, daily_hours in class_daily_hours.items():
            hours_list = [daily_hours[day] for day in range(5)]
            days_used = sum(1 for h in hours_list if h > 0)
            
            if days_used >= 4:  # Au moins 4 jours utilisés
                balanced_classes += 1
        
        balance_percentage = (balanced_classes / max(len(class_daily_hours), 1)) * 100
        logger.info(f"✅ ÉQUILIBRAGE: {balance_percentage:.1f}% des classes bien équilibrées")
        
        # 3. Résumé
        logger.info(f"📊 RÉSUMÉ: {len(schedule)} créneaux générés")
        logger.info(f"📊 Classes: {len(set(e['class_name'] for e in schedule))}")
        logger.info(f"📊 Professeurs: {len(set(e['teacher_name'] for e in schedule))}")
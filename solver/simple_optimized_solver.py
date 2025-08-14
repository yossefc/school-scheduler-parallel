# simple_optimized_solver.py - Version simplifiée mais efficace des optimisations OR-Tools
from ortools.sat.python import cp_model
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleOptimizedSolver:
    def __init__(self, teachers=None, classes=None, time_slots=None, courses=None):
        """Initialise le solver avec optimisations simples mais efficaces"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        self.teachers = teachers or []
        self.classes = classes or []
        self.time_slots = time_slots or []
        self.courses = courses or []
        
        self.schedule_vars = {}

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

    def add_basic_constraints(self):
        """Ajoute les contraintes de base (non-superposition, heures exactes)"""
        logger.info("=== CONTRAINTES DE BASE ===")
        
        # 1. Heures exactes pour chaque cours
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
        
        # 2. Pas de conflits professeur
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
        
        # 3. Pas de conflits classe
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
        
        logger.info("✓ Contraintes de base ajoutées")

    def add_compactness_constraints(self):
        """Ajoute les contraintes pour maximiser la compacité (éliminer les trous)"""
        logger.info("=== CONTRAINTES DE COMPACITÉ ===")
        
        # Pour chaque classe et chaque jour, forcer la compacité
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):  # Lundi à vendredi
                # Récupérer tous les créneaux du jour
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                day_slots.sort(key=lambda s: s["period_number"])
                
                if len(day_slots) < 3:
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
                
                # CONTRAINTE DE COMPACITÉ: Interdire les motifs avec trous
                # Fenêtre glissante de 3 périodes: [1,0,1] interdit
                for i in range(len(period_vars) - 2):
                    # Si période i et i+2 ont des cours, alors i+1 doit aussi en avoir
                    self.model.Add(period_vars[i+1] >= period_vars[i] + period_vars[i+2] - 1)
        
        logger.info("✓ Contraintes de compacité ajoutées")

    def add_balance_constraints(self):
        """Ajoute les contraintes pour l'équilibrage hebdomadaire"""
        logger.info("=== CONTRAINTES D'ÉQUILIBRAGE ===")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Limiter les heures par jour (max 8h par jour)
            for day in range(5):  # Lundi à vendredi
                day_hours = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    day_hours.append(self.schedule_vars[vname])
                
                if day_hours:
                    # Maximum 8 heures par jour
                    self.model.Add(sum(day_hours) <= 8)
                    # Minimum 2 heures si le jour est utilisé (évite les journées avec 1h seulement)
                    day_used = self.model.NewBoolVar(f"day_used_{class_name}_{day}")
                    self.model.Add(sum(day_hours) >= 2 * day_used)
                    self.model.Add(sum(day_hours) <= 8 * day_used)
        
        logger.info("✓ Contraintes d'équilibrage ajoutées")

    def add_optimization_objective(self):
        """Configure l'objectif d'optimisation"""
        logger.info("=== OBJECTIF D'OPTIMISATION ===")
        
        objectives = []
        
        # 1. Minimiser l'utilisation des créneaux tardifs (après 15h)
        for course in self.courses:
            for slot in self.time_slots:
                if slot["period_number"] >= 7:  # Après 15h
                    vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if vname in self.schedule_vars:
                        # Pénalité progressive selon l'heure
                        penalty = (slot["period_number"] - 6) * 10
                        objectives.append(self.schedule_vars[vname] * penalty)
        
        # 2. Encourager l'utilisation de tous les jours de la semaine
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            day_used_vars = []
            for day in range(5):  # Lundi à vendredi
                day_courses = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                vname = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if vname in self.schedule_vars:
                                    day_courses.append(self.schedule_vars[vname])
                
                if day_courses:
                    day_used = self.model.NewBoolVar(f"used_{class_name}_{day}")
                    self.model.Add(sum(day_courses) >= day_used)
                    self.model.Add(sum(day_courses) <= 10 * day_used)  # max 10h par jour
                    day_used_vars.append(day_used)
            
            # Encourager l'utilisation de 4-5 jours (pénaliser si moins de 4 jours)
            if len(day_used_vars) >= 4:
                unused_penalty = self.model.NewIntVar(0, 5, f"unused_penalty_{class_name}")
                self.model.Add(unused_penalty >= 4 - sum(day_used_vars))
                objectives.append(unused_penalty * 100)  # Forte pénalité
        
        # Appliquer l'objectif
        if objectives:
            self.model.Minimize(sum(objectives))
            logger.info(f"✓ Objectif avec {len(objectives)} composants")

    def solve(self, time_limit=60):
        """Résout le problème avec optimisation"""
        logger.info("\n=== RÉSOLUTION OPTIMISÉE ===")
        
        try:
            # 1. Créer variables et contraintes
            self.create_variables()
            if not self.schedule_vars:
                logger.error("Aucune variable créée!")
                return []
            
            self.add_basic_constraints()
            self.add_compactness_constraints()
            self.add_balance_constraints()
            self.add_optimization_objective()
            
            # 2. Configurer le solver
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.num_search_workers = 4
            self.solver.parameters.log_search_progress = True
            
            # 3. Résoudre
            logger.info(f"Résolution (limite: {time_limit}s)...")
            start_time = datetime.now()
            status = self.solver.Solve(self.model)
            end_time = datetime.now()
            
            solving_time = (end_time - start_time).total_seconds()
            logger.info(f"⏱️ Temps: {solving_time:.1f}s")
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! ({self.solver.StatusName(status)})")
                return self._extract_solution()
            else:
                logger.error(f"❌ Pas de solution ({self.solver.StatusName(status)})")
                return None
                
        except Exception as e:
            logger.error(f"Erreur: {e}")
            raise

    def _extract_solution(self):
        """Extrait la solution"""
        schedule = []
        
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                parts = var_name.split("_")
                course_id = int(parts[1])
                slot_id = int(parts[3])
                
                course = next((c for c in self.courses if c["course_id"] == course_id), None)
                slot = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if course and slot:
                    classes = [c.strip() for c in (course.get("class_list") or "").split(",")]
                    for class_name in classes:
                        schedule.append({
                            "course_id": course_id,
                            "slot_id": slot_id,
                            "teacher_name": course.get("teacher_names", ""),
                            "subject_name": course.get("subject", ""),
                            "class_name": class_name,
                            "day_of_week": slot["day_of_week"],
                            "period_number": slot["period_number"],
                        })
        
        return schedule
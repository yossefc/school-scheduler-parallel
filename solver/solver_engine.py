# solver_engine_fixed.py - Version corrigֳ©e avec les 3 bugs rֳ©solus
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class ScheduleSolver:
    def __init__(self, db_config=None):
        """Initialise le solver avec configuration optionnelle"""
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
        self.parallel_vars = {}
        self.teachers = []
        self.classes = []
        self.subjects = []
        self.rooms = []
        self.time_slots = []
        self.teacher_load = []
        self.constraints = []
        self.parallel_groups = []
        self.parallel_details = []
        self.objective_terms = []
    def load_data_from_db(self):
        """Charge toutes les donnֳ©es incluant les groupes parallֳ¨les"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les donnֳ©es de base
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
            
            # נ”§ FIX BUG #1: Utiliser IS DISTINCT FROM pour exclure NULL
            cur.execute("""
                SELECT * FROM teacher_load 
                WHERE hours > 0 
                AND is_parallel IS DISTINCT FROM TRUE
            """)
            self.teacher_loads = cur.fetchall()
            
            # Charger les groupes parallֳ¨les
            cur.execute("SELECT * FROM parallel_groups")
            self.parallel_groups = cur.fetchall()
            
            # Charger les dֳ©tails des cours parallֳ¨les
            cur.execute("""
                SELECT * FROM parallel_teaching_details
                ORDER BY group_id, teacher_name
            """)
            self.parallel_details = cur.fetchall()
            
            # Charger les contraintes
            cur.execute("SELECT * FROM constraints WHERE is_active = TRUE")
            self.constraints = cur.fetchall()
            
            # נ“ Log les statistiques importantes
            logger.info(
                f"Loaded: {len(self.teachers)} teachers, "
                f"{len(self.classes)} classes, "
                f"{len(self.time_slots)} time slots, "
                f"{len(self.teacher_loads)} individual loads, "
                f"{len(self.parallel_groups)} parallel groups"
            )
            
            # Calculer les besoins rֳ©els en crֳ©neaux
            individual_hours = sum(load["hours"] for load in self.teacher_loads)
            parallel_hours = sum(
                details[0]["hours_per_teacher"] 
                for group_id in set(d["group_id"] for d in self.parallel_details)
                for details in [[d for d in self.parallel_details if d["group_id"] == group_id][:1]]
                if details
            )
            total_slots_needed = individual_hours + parallel_hours
            available_slots = len(self.classes) * len(self.time_slots)
            
            logger.info(
                f"Schedule feasibility: {total_slots_needed} hours needed / "
                f"{available_slots} slots available = "
                f"{total_slots_needed/available_slots:.2f} ratio"
            )
            
        finally:
            cur.close()
            conn.close()
    def add_constraint(self, constraint_dict):
        """CORRECTION BUG 2: Ajoute une contrainte au solver"""
        # Ajouter à la liste des contraintes
        self.constraints.append(constraint_dict)
        
        # Sauvegarder dans la BD si nécessaire
        if 'constraint_id' not in constraint_dict:
            self._save_constraint_to_db(constraint_dict)
        
        logger.info(f"Added constraint: {constraint_dict}")

    def _save_constraint_to_db(self, constraint):
        """CORRECTION BUG 3: Sauvegarde une contrainte dans la BD"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO constraints 
                (constraint_type, priority, entity_type, entity_name, constraint_data, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING constraint_id
            """, (
                constraint.get('constraint_type', 'custom'),
                constraint.get('priority', 3),
                constraint.get('entity_type', 'teacher'),
                constraint.get('entity_name', ''),
                json.dumps(constraint.get('constraint_data', {})),
                True
            ))
            
            constraint_id = cur.fetchone()[0]
            constraint['constraint_id'] = constraint_id
            conn.commit()
            
            logger.info(f"Saved constraint to DB with ID: {constraint_id}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving constraint: {e}")
            raise
        finally:
            cur.close()
            conn.close()
        def _explain_failure_to_user(self) -> str:
            """Explique à l'utilisateur pourquoi la génération a échoué"""
            explanations = []
            
            # Test de faisabilité basique
            total_hours = sum(load["hours"] for load in self.teacher_loads)
            total_slots = len(self.time_slots) * len(self.classes)
            
            if total_hours > total_slots * 0.8:  # Plus de 80% d'occupation
                explanations.append("🔴 Trop d'heures à planifier par rapport aux créneaux disponibles")
            
            # Vérifier les professeurs sur-contraints
            for teacher in self.teachers:
                available_slots = self._count_available_slots(teacher)
                required_hours = self._get_teacher_hours(teacher)
                
                if required_hours > available_slots:
                    explanations.append(f"🔴 {teacher['name']} : {required_hours}h requises mais seulement {available_slots} créneaux disponibles")
            
            return "\n".join(explanations) if explanations else "❓ Problème non identifié - vérifiez les logs détaillés"
    def create_variables(self):
        """Crֳ©e les variables pour les cours individuels et parallֳ¨les"""
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        # 1. Variables pour les cours individuels (non parallֳ¨les)
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
            
            # Rֳ©unions (pas de classe)
            elif not class_list:
                for slot in self.time_slots:
                    var_name = f"t_{teacher_id}_meeting_{subject}_slot_{slot['slot_id']}"
                    self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # 2. Variables pour les groupes parallֳ¨les
        for group in self.parallel_groups:
            group_id = group["group_id"]
            subject = group["subject"]
            
            # Obtenir les dֳ©tails du groupe
            group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
            if not group_details:
                continue
            
            # Crֳ©er une variable principale pour chaque crֳ©neau
            for slot in self.time_slots:
                # Variable du groupe (tous les profs enseignent ensemble)
                group_var_name = f"parallel_g{group_id}_slot_{slot['slot_id']}"
                group_var = self.model.NewBoolVar(group_var_name)
                self.parallel_vars[group_var_name] = group_var
                
                # Variables individuelles pour chaque prof du groupe
                for detail in group_details:
                    teacher_id = teacher_id_map.get(detail["teacher_name"])
                    if not teacher_id:
                        continue
                    
                    # Variable individuelle du prof
                    teacher_var_name = f"t_{teacher_id}_parallel_g{group_id}_slot_{slot['slot_id']}"
                    teacher_var = self.model.NewBoolVar(teacher_var_name)
                    self.schedule_vars[teacher_var_name] = teacher_var
                    
                    # Lier la variable du prof ֳ  celle du groupe
                    self.model.Add(teacher_var == group_var)
                    
                    # Variables pour chaque classe couverte
                    classes_covered = [c.strip() for c in detail["classes_covered"].split(",")]
                    for class_name in classes_covered:
                        class_var_name = f"c_{class_name}_parallel_g{group_id}_slot_{slot['slot_id']}"
                        if class_var_name not in self.schedule_vars:
                            class_var = self.model.NewBoolVar(class_var_name)
                            self.schedule_vars[class_var_name] = class_var
                            # Lier au groupe
                            self.model.Add(class_var == group_var)
        self.create_prayer_variables()
       # Appel de la nouvelle méthode

    def create_prayer_variables(self):
        """Créer des variables spécifiques pour תפילה"""
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        # Identifier les professeurs qui enseignent תפילה
        prayer_teachers = [
            load for load in self.teacher_loads 
            if load["subject"] in ["תפילה", "tefila", "prayer", "tfila", "תפלה"]
        ]
        
        # Pour chaque classe, créer des variables pour la première heure
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Créneaux de première heure (dimanche-jeudi)
            first_hour_slots = [
                s for s in self.time_slots 
                if s["period_number"] == 1 and s["day_of_week"] < 5
            ]
            
            for slot in first_hour_slots:
                # Variables pour chaque professeur possible
                for teacher_load in prayer_teachers:
                    teacher_name = teacher_load["teacher_name"]
                    teacher_id = teacher_id_map.get(teacher_name)
                    if not teacher_id:
                        continue
                        
                    var_name = f"t_{teacher_id}_c_{class_name}_s_תפילה_slot_{slot['slot_id']}"
                    self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
    def add_hard_constraints(self):
        """Ajoute les contraintes dures incluant les contraintes parallֳ¨les"""
        
        # 1. Un professeur ne peut ֳ×tre qu'ֳ  un endroit ֳ  la fois
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
        
        # 2. Une classe ne peut avoir qu'un cours ֳ  la fois
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
        
        # נ”§ FIX BUG #2: Limiter le nombre total de cours simultanֳ©s
        for slot in self.time_slots:
            slot_id = slot["slot_id"]
            # Compter tous les cours actifs ֳ  ce crֳ©neau (sauf rֳ©unions)
            active_class_vars = [
                var for name, var in self.schedule_vars.items()
                if f"slot_{slot_id}" in name and "_c_" in name and "meeting" not in name
            ]
            if active_class_vars:
                # Ne pas dֳ©passer le nombre de classes disponibles
                self.model.Add(sum(active_class_vars) <= len(self.classes))
        
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
            
            # Cours individuel
            if class_list and "," not in class_list:
                course_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_c_{class_list}_s_{subject}_" in name
                ]
                if course_vars:
                    self.model.Add(sum(course_vars) == hours)
            
            # Rֳ©unions
            elif not class_list:
                meeting_vars = [
                    var for name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_meeting_{subject}_" in name
                ]
                if meeting_vars:
                    self.model.Add(sum(meeting_vars) == hours)
        self._apply_prayer_assignment_constraint()
        # 4. Respecter le nombre d'heures pour les groupes parallֳ¨les
        for load in self.teacher_loads:
            hours = load.get("hours", 0)
            if not hours:
                continue
            
            # AJOUTER CETTE LIGNE :
            if load["subject"] in ["תפילה", "tefila", "prayer", "tfila"]:
                continue  # Traité séparément
        
        # 5. Appliquer les contraintes personnalisֳ©es
        for constraint in self.constraints:
            self._apply_custom_constraint(constraint)
        self.add_prayer_hours_constraint()

    
    def _apply_custom_constraint(self, constraint):
        """Applique une contrainte personnalisֳ©e"""
        if constraint["constraint_type"] == "teacher_availability":
            self._apply_availability_constraint(constraint)
        elif constraint["constraint_type"] == "friday_early_end":
            self._apply_friday_constraint(constraint)
        elif constraint["constraint_type"] == "morning_prayer":
            self._apply_morning_prayer_constraint(constraint)
        elif constraint["constraint_type"] == "subject_timing":
            self._apply_subject_timing_constraint(constraint) 
        # Ajouter d'autres types selon les besoins
    
    def _apply_availability_constraint(self, constraint):
        """Applique une contrainte de disponibilitֳ©"""
        data = constraint["constraint_data"]
        teacher_name = constraint["entity_name"]
        
        teacher_id = next((t["teacher_id"] for t in self.teachers 
                          if t["teacher_name"] == teacher_name), None)
        if not teacher_id:
            return
        
        # Jours non disponibles
        if "unavailable_days" in data:
            for day in data["unavailable_days"]:
                for slot in self.time_slots:
                    if slot["day_of_week"] == day:
                        for var_name, var in self.schedule_vars.items():
                            if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                                self.model.Add(var == 0)
        
        # Pֳ©riodes non disponibles
        if "unavailable_periods" in data:
            for period in data["unavailable_periods"]:
                for slot in self.time_slots:
                    if slot["period_number"] == period:
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
                for var in self.schedule_vars.values():
                    if f"slot_{slot['slot_id']}" in str(var):
                        self.model.Add(var == 0)
                for var in self.parallel_vars.values():
                    if f"slot_{slot['slot_id']}" in str(var):
                        self.model.Add(var == 0)
    
    def _apply_morning_prayer_constraint(self, constraint):
        """Réserve les premières périodes pour la prière"""
        data = constraint["constraint_data"]
        duration = data.get("duration", 1)
        
        for day in range(5):  # Dimanche à Jeudi
            for period in range(1, duration + 1):
                slot = next((s for s in self.time_slots 
                        if s["day_of_week"] == day and s["period_number"] == period), None)
                if slot:
                    # MODIFIER : Bloquer SEULEMENT les matières non-religieuses ET non-תפילה
                    for var_name, var in self.schedule_vars.items():
                        if (f"slot_{slot['slot_id']}" in var_name and 
                            # NE PAS bloquer les variables de תפילה
                            not any(religious in var_name.lower() 
                                for religious in ["torah", "talmud", "priere", "תפילה", 
                                                    "tefila", "tfila", "תפלה", "prayer"])):
                            self.model.Add(var == 0)
    # ------------------------------------------------------------------
    # Sujet : subject_timing (ex. כל שיעור תורה ... בשעה ראשונה)
    # ------------------------------------------------------------------
    def _apply_subject_timing_constraint(self, constraint):
        """Force une matière à commencer uniquement à certaines périodes"""
        data = constraint["constraint_data"]
        subject_name = constraint.get("entity_name")  # "תורה"
        preferred_period = data.get("preferred_period", 1)
        
        if not subject_name:
            return  # Pas d'info -> ignorer
        
        # Parcourir tous les créneaux qui ne correspondent pas à la période souhaitée
        for slot in self.time_slots:
            if slot["period_number"] != preferred_period:
                # Cherche les variables contenant le nom de la matière + slot
                for var_name, var in self.schedule_vars.items():
                    # Exemple de nom : _s_Torah_slot_123
                    if f"_{subject_name}_" in var_name or subject_name.lower() in var_name.lower():
                        if f"slot_{slot['slot_id']}" in var_name:
                            self.model.Add(var == 0)
    def _apply_prayer_assignment_constraint(self):
        """Assigner UN professeur de תפילה par classe en première heure"""
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        prayer_teachers = [
            t for t in self.teacher_loads 
            if t["subject"] in ["תפילה", "tefila", "prayer", "tfila", "תפלה"]
        ]
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Pour chaque jour (dimanche-jeudi)
            for day in range(5):
                first_slot = next(
                    (s for s in self.time_slots 
                    if s["day_of_week"] == day and s["period_number"] == 1),
                    None
                )
                
                if not first_slot:
                    continue
                
                # Variables de tous les profs possibles pour cette classe/créneau
                possible_teachers = []
                for teacher in prayer_teachers:
                    teacher_name = teacher["teacher_name"]
                    teacher_id = teacher_id_map.get(teacher_name)
                    if not teacher_id:
                        continue
                        
                    var_name = f"t_{teacher_id}_c_{class_name}_s_תפילה_slot_{first_slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        possible_teachers.append(self.schedule_vars[var_name])
                
                if possible_teachers:
                    # Maximum UN professeur (0 ou 1)
                    self.model.Add(sum(possible_teachers) <= 1)

    def add_prayer_hours_constraint(self):
        """Respecter le nombre d'heures de תפילה par professeur"""
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in self.teachers}
        
        for teacher_load in self.teacher_loads:
            if teacher_load["subject"] not in ["תפילה", "tefila", "prayer", "tfila", "תפלה"]:
                continue
                
            teacher_name = teacher_load["teacher_name"]
            teacher_id = teacher_id_map.get(teacher_name)
            if not teacher_id:
                continue
                
            hours_required = teacher_load["hours"]
            
            # Toutes les variables תפילה de ce professeur
            prayer_vars = [
                var for name, var in self.schedule_vars.items()
                if f"t_{teacher_id}_" in name and "תפילה" in name
            ]
            
            if prayer_vars:
                # Le professeur doit enseigner exactement le nombre d'heures spécifié
                self.model.Add(sum(prayer_vars) == hours_required)
    def add_soft_constraints(self):
        """Ajoute des contraintes souples pour optimiser la qualitֳ©"""
        
        # 1. Minimiser les trous dans l'emploi du temps des professeurs
        for teacher in self.teachers:
            teacher_id = teacher["teacher_id"]
            for day in range(6):
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                if len(day_slots) < 3:
                    continue
                
                # Variables pour ce prof ce jour-lֳ 
                day_vars = []
                for slot in day_slots:
                    slot_vars = [
                        var for name, var in self.schedule_vars.items()
                        if f"t_{teacher_id}_" in name and f"slot_{slot['slot_id']}" in name
                    ]
                    day_vars.append(self.model.NewBoolVar(f"has_course_t{teacher_id}_d{day}_s{slot['slot_id']}"))
                    if slot_vars:
                        self.model.Add(day_vars[-1] == sum(slot_vars) > 0)
                
                # Pֳ©naliser les trous
                for i in range(1, len(day_vars) - 1):
                    gap_var = self.model.NewBoolVar(f"gap_t{teacher_id}_d{day}_s{i}")
                    # Gap = pas de cours ֳ  i, mais cours avant et aprֳ¨s
                    # Temporairement désactivé - problème de syntaxe OR-Tools
                    # self.model.AddBoolAnd([day_vars[i-1], day_vars[i+1].Not(), day_vars[i]]).OnlyEnforceIf(gap_var)
                    # self.model.Add(gap_var == 0).OnlyEnforceIf(day_vars[i])
                    pass  # Contraintes souples désactivées temporairement
                    # Ajouter ֳ  la fonction objectif (ֳ  implֳ©menter)
        
        # 2. ֳ‰viter les matiֳ¨res difficiles en fin de journֳ©e
        difficult_subjects = ["math", "physique", "chimie", "׳׳×׳׳˜׳™׳§׳”", "׳₪׳™׳–׳™׳§׳”", "׳›׳™׳׳™׳”"]
        
        for slot in self.time_slots:
            if slot["period_number"] >= 8:  # Derniֳ¨res pֳ©riodes
                for var_name, var in self.schedule_vars.items():
                    if any(subj in var_name.lower() for subj in difficult_subjects):
                        # Pֳ©naliser mais ne pas interdire
                        # (nֳ©cessite une fonction objectif - ֳ  implֳ©menter)
                        pass
    
    def solve(self, time_limit=60):
        """Rֳ©sout le problֳ¨me avec support des cours parallֳ¨les"""
        logger.info("Starting schedule generation...")
        
        self.create_variables()
        logger.info(f"Created {len(self.schedule_vars)} schedule vars and {len(self.parallel_vars)} parallel vars")
        
        self.add_hard_constraints()
        # self.add_soft_constraints()  # Désactivé temporairement
        
        # Configuration du solver
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = 8  # Parallֳ©lisation
        
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL:
            logger.info("Optimal solution found!")
            return self._extract_solution()
        elif status == cp_model.FEASIBLE:
            logger.info("Feasible solution found")
            return self._extract_solution()
        else:
            logger.error(f"No solution found. Status: {status}")
            self._analyze_failure()
            return None
    
    def _analyze_failure(self):
        """Analyse pourquoi le solver a ֳ©chouֳ©"""
        logger.error("Analyzing failure reasons...")
        
        # Statistiques du problֳ¨me
        logger.info(f"Problem size: {len(self.schedule_vars)} variables")
        logger.info(f"Number of constraints: {self.model.Proto().constraints}")
        
        # Vֳ©rifier la faisabilitֳ© basique
        total_hours_needed = sum(load["hours"] for load in self.teacher_loads)
        parallel_slots_needed = sum(
            details[0]["hours_per_teacher"] 
            for group_id in set(d["group_id"] for d in self.parallel_details)
            for details in [[d for d in self.parallel_details if d["group_id"] == group_id][:1]]
            if details
        )
        total_slots_available = len(self.classes) * len(self.time_slots)
        
        logger.error(f"Feasibility check:")
        logger.error(f"  Individual hours: {total_hours_needed}")
        logger.error(f"  Parallel slots: {parallel_slots_needed}")
        logger.error(f"  Total needed: {total_hours_needed + parallel_slots_needed}")
        logger.error(f"  Available: {total_slots_available}")
        logger.error(f"  Ratio: {(total_hours_needed + parallel_slots_needed) / total_slots_available:.2f}")
        
        if (total_hours_needed + parallel_slots_needed) > total_slots_available:
            logger.error("INFEASIBLE: More hours needed than slots available!")
    
    def _extract_solution(self):
        """Extrait la solution incluant les cours parallֳ¨les"""
        schedule = []
        teacher_id_map = {t["teacher_id"]: t["teacher_name"] for t in self.teachers}
        
        # Traiter les groupes parallֳ¨les
        for var_name, var in self.parallel_vars.items():
            if self.solver.Value(var) == 1:
                # Parser: parallel_g{group_id}_slot_{slot_id}
                parts = var_name.split("_")
                group_id = int(parts[1][1:])  # Enlever le 'g'
                slot_id = int(parts[-1])
                
                # Obtenir les infos
                group = next((g for g in self.parallel_groups if g["group_id"] == group_id), None)
                slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if not group or not slot_info:
                    continue
                
                # Dֳ©tails du groupe
                group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
                
                # Toutes les classes couvertes
                all_classes = set()
                for detail in group_details:
                    classes = [c.strip() for c in detail["classes_covered"].split(",")]
                    all_classes.update(classes)
                
                # Liste des profs
                teacher_names = [d["teacher_name"] for d in group_details]
                
                # Une entrֳ©e par classe
                for class_name in all_classes:
                    schedule.append({
                        "teacher_name": " + ".join(teacher_names),
                        "class_name": class_name,
                        "subject_name": group["subject"],
                        "day": slot_info["day_of_week"],
                        "period": slot_info["period_number"],
                        "is_parallel": True,
                        "parallel_group_id": group_id
                    })
        
        # Traiter les cours individuels
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1 and "parallel_g" not in var_name:
                # Parser les variables
                parts = var_name.split("_")
                
                if "meeting" in var_name:
                    # Rֳ©union
                    teacher_id = int(parts[1])
                    subject_start = 3
                    slot_id = int(parts[-1])
                    subject = "_".join(parts[subject_start:-2])
                    
                    slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                    if slot_info:
                        schedule.append({
                            "teacher_name": teacher_id_map.get(teacher_id, f"Unknown_{teacher_id}"),
                            "class_name": "_MEETING",  # Classe virtuelle pour les rֳ©unions
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
        
        logger.info(f"Extracted {len(schedule)} lessons")
        return schedule
    
    def save_schedule(self, schedule):
        """Sauvegarde l'emploi du temps avec support des cours parallֳ¨les"""
        if not schedule:
            raise ValueError("Schedule is empty")
        
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Crֳ©er le schedule
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s) RETURNING schedule_id
            """, ('2024-2025', 1, 'active', datetime.now()))
            
            schedule_id = cur.fetchone()[0]
            
            # Insֳ©rer les entrֳ©es
            for entry in schedule:
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
        """Gֳ©nֳ¨re un rֳ©sumֳ© incluant les statistiques des cours parallֳ¨les"""
        parallel_lessons = [e for e in schedule if e.get("is_parallel", False)]
        individual_lessons = [e for e in schedule if not e.get("is_parallel", False)]
        meetings = [e for e in schedule if e.get("class_name") == "_MEETING"]
        
        # Groupes parallֳ¨les uniques
        parallel_groups = set(e.get("parallel_group_id") for e in parallel_lessons if e.get("parallel_group_id"))
        
        # Classes couvertes
        classes_with_schedule = set(e["class_name"] for e in schedule if e["class_name"] and e["class_name"] != "_MEETING")
        
        summary = {
            "total_lessons": len(schedule),
            "individual_lessons": len(individual_lessons) - len(meetings),
            "parallel_lessons": len(parallel_lessons),
            "meetings": len(meetings),
            "parallel_groups": len(parallel_groups),
            "teachers_count": len(set(e["teacher_name"] for e in schedule if not e.get("is_parallel"))),
            "classes_count": len(classes_with_schedule),
            "classes_covered": list(sorted(classes_with_schedule)),
            "subjects_count": len(set(e["subject_name"] for e in schedule)),
            "days_used": len(set(e["day"] for e in schedule)),
            "utilization_rate": f"{(len(schedule) / (len(self.classes) * len(self.time_slots)) * 100):.1f}%"
        }
        
        return summary

# solver_engine_fixed.py - Version corrigée avec tous les bugs résolus

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
        self.teacher_loads = []  # Correction du nom de variable
        self.constraints = []
        self.parallel_groups = []
        self.parallel_details = []
        self.objective_terms = []

    def load_data_from_db(self):
        """Charge toutes les données incluant les groupes parallèles"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les données de base
            cur.execute("SELECT * FROM teachers WHERE teacher_name IS NOT NULL")
            self.teachers = cur.fetchall()
            
            # Assurer que toutes les classes utilisées dans teacher_load existent dans la table classes
            cur.execute("""
                INSERT INTO classes (grade, section, class_name, student_count)
                SELECT 0, 'X', TRIM(class_name), NULL
                FROM (
                    SELECT DISTINCT unnest(string_to_array(class_list, ',')) AS class_name
                    FROM teacher_load
                    WHERE class_list IS NOT NULL
                      AND class_list <> ''
                      AND class_list <> 'NULL'
                ) AS all_cls
                WHERE TRIM(class_name) <> ''
                ON CONFLICT (class_name) DO NOTHING;
            """)
            conn.commit()

            # Recharger la table des classes après éventuelle insertion
            cur.execute("SELECT * FROM classes")
            self.classes = cur.fetchall()
            
            cur.execute("""
                SELECT DISTINCT subject as subject_name 
                FROM teacher_load 
                WHERE subject IS NOT NULL
            """)
            self.subjects = cur.fetchall()
            
            # IMPORTANT: Charger TOUS les créneaux pour TOUS les jours
            cur.execute("""
                SELECT * FROM time_slots 
                WHERE is_break = FALSE 
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            
            # Vérifier qu'on a bien tous les jours
            days_in_slots = set(slot["day_of_week"] for slot in self.time_slots)
            logger.info(f"Days in time_slots: {sorted(days_in_slots)}")
            
            # Charger les cours individuels (non parallèles)
            cur.execute("""
                SELECT * FROM teacher_load 
                WHERE hours > 0 
                AND (is_parallel IS NULL OR is_parallel = FALSE)
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
            
            # Log les statistiques importantes
            logger.info(
                f"Loaded: {len(self.teachers)} teachers, "
                f"{len(self.classes)} classes, "
                f"{len(self.time_slots)} time slots for days {sorted(days_in_slots)}, "
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
                # IMPORTANT: Créer des variables pour TOUS les créneaux
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
                
                # Variables individuelles pour chaque prof du groupe
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
                    
                    # Variables pour chaque classe couverte
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
            
            # Cours individuel
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
        
        # 4. CORRECTION: Forcer l'assignation des groupes parallèles
        for group in self.parallel_groups:
            group_id = group["group_id"]
            
            # Obtenir les heures requises depuis les détails
            group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
            if group_details:
                hours_needed = group_details[0]["hours_per_teacher"]
                
                # Variables de ce groupe
                group_vars = [
                    var for name, var in self.parallel_vars.items()
                    if f"parallel_g{group_id}_" in name
                ]
                
                if group_vars:
                    # Le groupe doit être assigné exactement le nombre d'heures requis
                    self.model.Add(sum(group_vars) == hours_needed)
                    logger.info(f"Parallel group {group_id} must have {hours_needed} hours")
        
        # 5. Appliquer les contraintes personnalisées CORRECTEMENT
        for constraint in self.constraints:
            self._apply_custom_constraint_fixed(constraint)

    def _apply_custom_constraint_fixed(self, constraint):
        """Version corrigée de l'application des contraintes"""
        constraint_type = constraint.get("constraint_type")
        
        if constraint_type == "teacher_availability":
            self._apply_availability_constraint_fixed(constraint)
        elif constraint_type == "teacher_unavailable":
            self._apply_unavailability_constraint(constraint)
        elif constraint_type == "friday_early_end":
            self._apply_friday_constraint(constraint)
        elif constraint_type == "morning_prayer":
            self._apply_morning_prayer_constraint(constraint)
        elif constraint_type == "parallel_group":
            # Les groupes parallèles sont déjà gérés dans create_variables
            pass
        elif constraint_type == "parallel_teaching":
            # Contrainte déjà prise en compte via create_variables ; on ignore pour éviter des warnings
            pass
        else:
            logger.warning(f"Unknown constraint type: {constraint_type}")

    def _apply_availability_constraint_fixed(self, constraint):
        """CORRECTION: Interpréter correctement les disponibilités"""
        data = constraint.get("constraint_data", {})
        
        # Si c'est une string JSON, la parser
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        teacher_name = constraint.get("entity_name")
        
        teacher_id = next((t["teacher_id"] for t in self.teachers 
                          if t["teacher_name"] == teacher_name), None)
        if not teacher_id:
            return
        
        # NOUVEAU: Gestion des options de congé (3 possibilités, choisir UNE seule)
        if "day_off_options" in data:
            self._apply_day_off_options(teacher_id, data["day_off_options"])
            return
        
        # CORRECTION: Interpréter les disponibilités selon le contexte
        
        # Si on a des "available_days", ce sont les SEULS jours où le prof peut enseigner
        if "available_days" in data:
            available_days = data["available_days"]
            # Bloquer tous les AUTRES jours
            for slot in self.time_slots:
                if slot["day_of_week"] not in available_days:
                    for var_name, var in self.schedule_vars.items():
                        if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                            self.model.Add(var == 0)
        
        # Si on a des "unavailable_days", ce sont les jours interdits
        elif "unavailable_days" in data:
            for day in data["unavailable_days"]:
                for slot in self.time_slots:
                    if slot["day_of_week"] == day:
                        for var_name, var in self.schedule_vars.items():
                            if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                                self.model.Add(var == 0)
        
        # Gérer les périodes spécifiques
        if "unavailable_periods" in data:
            for period in data["unavailable_periods"]:
                for slot in self.time_slots:
                    if slot["period_number"] == period:
                        for var_name, var in self.schedule_vars.items():
                            if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                                self.model.Add(var == 0)

    def _apply_day_off_options(self, teacher_id, day_off_options):
        """
        Gère les options de congé : 3 possibilités, le système doit en choisir UNE seule.
        Format attendu: [
            {"day": 1, "priority": 1, "description": "Lundi (meilleur choix)"},
            {"day": 3, "priority": 2, "description": "Mercredi (2ème choix)"},
            {"day": 5, "priority": 3, "description": "Vendredi (3ème choix)"}
        ]
        """
        if not day_off_options or len(day_off_options) == 0:
            return
        
        logger.info(f"Processing day-off options for teacher {teacher_id}: {len(day_off_options)} options")
        
        # Créer une variable booléenne pour chaque option
        option_vars = []
        
        for i, option in enumerate(day_off_options):
            day = option.get("day")
            priority = option.get("priority", i + 1)
            
            if day is None:
                continue
            
            # Variable pour cette option de congé
            option_var = self.model.NewBoolVar(f"day_off_option_{teacher_id}_{i}")
            option_vars.append((option_var, day, priority))
            
            # Si cette option est choisie, bloquer TOUS les créneaux de ce jour
            day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
            for slot in day_slots:
                slot_id = slot["slot_id"]
                # Chercher toutes les variables de ce prof pour ce créneau
                teacher_vars_for_slot = [
                    var for var_name, var in self.schedule_vars.items()
                    if f"t_{teacher_id}_" in var_name and f"_slot_{slot_id}" in var_name
                ]
                
                # Si cette option de congé est choisie, aucun cours pour ce prof ce jour-là
                for var in teacher_vars_for_slot:
                    self.model.Add(var == 0).OnlyEnforceIf(option_var)
        
        # CONTRAINTE PRINCIPALE: Exactement UNE option doit être choisie
        if option_vars:
            self.model.Add(sum(var for var, _, _ in option_vars) == 1)
            
            # BONUS: Ajouter une préférence pour les options avec priorité plus faible (meilleure)
            # Plus la priorité est faible, plus on veut choisir cette option
            for var, day, priority in option_vars:
                # Récompenser les priorités plus faibles (1 est meilleur que 3)
                penalty = priority * 10  # Ajustez ce coefficient selon vos besoins
                self.objective_terms.append(penalty * var)
            
            logger.info(f"Added day-off constraint: exactly 1 of {len(option_vars)} options must be chosen")

    def _apply_unavailability_constraint(self, constraint):
        """Gère les contraintes de type teacher_unavailable"""
        data = constraint.get("constraint_data", {})
        
        # Parser si nécessaire
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        teacher_name = constraint.get("entity_name")
        
        teacher_id = next((t["teacher_id"] for t in self.teachers 
                          if t["teacher_name"] == teacher_name), None)
        if not teacher_id:
            return
        
        # Extraire le jour et la période
        day = data.get("day")
        period = data.get("period")
        
        # Convertir le jour si c'est en hébreu
        day_mapping = {'א': 0, 'ב': 1, 'ג': 2, 'ד': 3, 'ה': 4, 'ו': 5}
        if day in day_mapping:
            day = day_mapping[day]
        
        # Bloquer ce créneau spécifique
        for slot in self.time_slots:
            should_block = False
            
            if day is not None and slot["day_of_week"] == day:
                if period is not None and slot["period_number"] == period:
                    should_block = True
                elif period is None:
                    should_block = True  # Toute la journée
            
            if should_block:
                for var_name, var in self.schedule_vars.items():
                    if f"t_{teacher_id}" in var_name and f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)

    def _apply_friday_constraint(self, constraint):
        """Applique la contrainte du vendredi court"""
        data = constraint.get("constraint_data", {})
        
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        # Par défaut, fin à 13h (période 6)
        last_period = data.get("last_period", 6)
        
        # Bloquer les créneaux après la dernière période le vendredi
        for slot in self.time_slots:
            if slot["day_of_week"] == 5 and slot["period_number"] > last_period:
                # Bloquer toutes les variables pour ce créneau
                for var_name, var in self.schedule_vars.items():
                    if f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)
                for var_name, var in self.parallel_vars.items():
                    if f"slot_{slot['slot_id']}" in var_name:
                        self.model.Add(var == 0)

    def _apply_morning_prayer_constraint(self, constraint):
        """Réserve les premières périodes pour la prière"""
        data = constraint.get("constraint_data", {})
        
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                data = {}
        
        duration = data.get("duration", 1)
        
        # Pour chaque jour dimanche-jeudi
        for day in range(5):  # 0-4 = Dimanche-Jeudi
            for period in range(1, duration + 1):
                slot = next((s for s in self.time_slots 
                        if s["day_of_week"] == day and s["period_number"] == period), None)
                if slot:
                    # Bloquer les matières non-religieuses
                    for var_name, var in self.schedule_vars.items():
                        if (f"slot_{slot['slot_id']}" in var_name and 
                            not any(religious in var_name.lower() 
                                for religious in ["torah", "talmud", "priere", "תפילה", 
                                                 "tefila", "tfila", "תפלה", "prayer"])):
                            self.model.Add(var == 0)

    def add_soft_constraints(self):
        """Contraintes souples pour améliorer la qualité du planning"""

        penalty_per_unused_day = 100   # poids élevé pour forcer la distribution sur tous les jours

        for teacher in self.teachers:
            t_id = teacher["teacher_id"]
            for day in range(6):        # 0-5 = dim-ven
                # 1 si le prof n’enseigne rien ce jour-là
                unused = self.model.NewBoolVar(f"t{t_id}_unused_day{day}")
                # Tous les cours (indiv. + parallèles) du prof pour ce jour
                day_vars = [
                    v for n, v in self.schedule_vars.items()
                    if f"t_{t_id}_" in n and f"_slot_" in n
                    and any(f"slot_{s['slot_id']}" in n for s in self.time_slots
                            if s["day_of_week"] == day)
                ]
                # unused == 1  ↔  aucune variable à 1
                self.model.Add(sum(day_vars) == 0).OnlyEnforceIf(unused)
                self.model.Add(sum(day_vars) >= 1).OnlyEnforceIf(unused.Not())
                # pénaliser unused
                self.objective_terms.append(penalty_per_unused_day * unused)
        
        # Contrainte forte : professeurs avec >6h doivent enseigner sur au moins 3 jours différents
        for teacher in self.teachers:
            t_id = teacher["teacher_id"]
            
            # Calculer le total d'heures du professeur
            total_hours = sum(
                load["hours"] for load in self.teacher_loads 
                if load["teacher_name"] == teacher["teacher_name"]
            )
            
            if total_hours > 6:  # Seulement pour les profs avec plus de 6h
                # Variables pour savoir si le prof enseigne chaque jour
                day_used_vars = []
                for day in range(6):  # 0-5 = dim-ven
                    day_used = self.model.NewBoolVar(f"t{t_id}_teaches_day{day}")
                    day_used_vars.append(day_used)
                    
                    # Tous les cours du prof pour ce jour
                    day_vars = [
                        v for n, v in self.schedule_vars.items()
                        if f"t_{t_id}_" in n and f"_slot_" in n
                        and any(f"slot_{s['slot_id']}" in n for s in self.time_slots
                                if s["day_of_week"] == day)
                    ]
                    
                    # day_used == 1 si le prof a au moins un cours ce jour
                    if day_vars:
                        self.model.Add(sum(day_vars) >= day_used)
                        self.model.Add(sum(day_vars) <= len(day_vars) * day_used)
                
                # Contrainte : au moins 3 jours différents
                if len(day_used_vars) >= 3:
                    self.model.Add(sum(day_used_vars) >= 3)

    def solve(self, time_limit=300):  # Augmenté à 5 minutes
        """Résout le problème avec support des cours parallèles"""
        logger.info("Starting schedule generation...")
        
        self.create_variables()
        logger.info(f"Created {len(self.schedule_vars)} schedule vars and {len(self.parallel_vars)} parallel vars")
        
        self.add_hard_constraints()
        self.add_soft_constraints()
        
        # Configuration du solver
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = 8  # Parallélisation
        
        # Stratégie de recherche améliorée
        all_vars = list(self.schedule_vars.values()) + list(self.parallel_vars.values())
        self.model.AddDecisionStrategy(
            all_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE
        )
        
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
        """Analyse pourquoi le solver a échoué"""
        logger.error("Analyzing failure reasons...")
        
        # Statistiques du problème
        logger.info(f"Problem size: {len(self.schedule_vars)} variables")
        
        # Vérifier la faisabilité basique
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
        
        # Analyser les contraintes
        logger.error("Constraint analysis:")
        for constraint in self.constraints:
            logger.error(f"  - {constraint['constraint_type']}: {constraint['entity_name']}")

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
                
                # Obtenir les infos
                group = next((g for g in self.parallel_groups if g["group_id"] == group_id), None)
                slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                
                if not group or not slot_info:
                    continue
                
                # Détails du groupe
                group_details = [d for d in self.parallel_details if d["group_id"] == group_id]
                
                # Toutes les classes couvertes
                all_classes = set()
                for detail in group_details:
                    classes = [c.strip() for c in detail["classes_covered"].split(",")]
                    all_classes.update(classes)
                
                # Liste des profs
                teacher_names = [d["teacher_name"] for d in group_details]
                
                # Une entrée par classe
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
                    # Réunion
                    teacher_id = int(parts[1])
                    subject_start = 3
                    slot_id = int(parts[-1])
                    subject = "_".join(parts[subject_start:-2])
                    
                    slot_info = next((s for s in self.time_slots if s["slot_id"] == slot_id), None)
                    if slot_info:
                        schedule.append({
                            "teacher_name": teacher_id_map.get(teacher_id, f"Unknown_{teacher_id}"),
                            "class_name": "_MEETING",
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
        
        logger.info(f"Extracted {len(schedule)} lessons covering days: {sorted(set(s['day'] for s in schedule))}")
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
        meetings = [e for e in schedule if e.get("class_name") == "_MEETING"]
        
        # Groupes parallèles uniques
        parallel_groups = set(e.get("parallel_group_id") for e in parallel_lessons if e.get("parallel_group_id"))
        
        # Classes couvertes
        classes_with_schedule = set(e["class_name"] for e in schedule if e["class_name"] and e["class_name"] != "_MEETING")
        
        # Jours utilisés
        days_used = sorted(set(e["day"] for e in schedule))
        
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
            "days_used": days_used,
            "days_used_count": len(days_used),
            "utilization_rate": f"{(len(schedule) / (len(self.classes) * len(self.time_slots)) * 100):.1f}%"
        }
        
        # Analyse par jour
        summary["by_day"] = {}
        for day in range(6):
            day_lessons = [e for e in schedule if e["day"] == day]
            summary["by_day"][day] = len(day_lessons)
        
        return summary
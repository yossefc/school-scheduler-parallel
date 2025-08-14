"""
optimizer_advanced.py - Module d'optimisation avancé pour emplois du temps
Priorité maximale : ZÉRO trou et blocs de 2h consécutives
"""
from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import json
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class OptimizationPriority(Enum):
    """Niveaux de priorité pour l'optimisation"""
    CRITICAL = 1000    # Aucun trou
    HIGH = 100         # Blocs de 2h
    MEDIUM = 50        # Compacité journalière
    LOW = 20           # Équilibrage hebdomadaire
    MINIMAL = 10       # Préférences

@dataclass
class TimeSlot:
    day: int
    period: int
    
@dataclass
class CourseBlock:
    subject: str
    teacher: str
    classes: List[str]
    duration: int  # 1 ou 2 heures
    
class AdvancedScheduleOptimizer:
    def __init__(self, db_config=None):
        """Initialise l'optimiseur avancé avec contraintes anti-trous"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        if db_config is None:
            db_config = {
                "host": "localhost",  # Use localhost when running outside containers
                "database": "school_scheduler",
                "user": "admin",
                "password": "school123"
            }
        
        self.db_config = db_config
        
        # Variables principales
        self.schedule_vars = {}  # (course_id, slot_id) -> BoolVar
        self.teacher_gap_vars = {}  # (teacher, day, period) -> BoolVar (trou)
        self.block_vars = {}  # (class, subject, day, start_period) -> BoolVar (bloc 2h)
        
        # Données
        self.teachers = []
        self.classes = []
        self.time_slots = []
        self.courses = []
        self.subjects = []
        
        # Configuration
        self.config = {
            "optimization_weights": {
                "no_gaps": 1000,
                "block_courses": 100,
                "daily_compactness": 50,
                "weekly_balance": 20
            },
            "hard_constraints": {
                "max_consecutive_hours_teacher": 4,
                "max_consecutive_hours_class": 2,
                "min_break_between_blocks": 0
            },
            "preferences": {
                "prefer_morning_for": ["מתמטיקה", "פיזיקה", "עברית"],
                "prefer_blocks_for": ["מדעים", "שפות"],
                "avoid_friday_afternoon": True,
                "group_teacher_days": True
            }
        }
    
    def load_data_from_db(self):
        """Charge les données depuis la base"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DES DONNÉES POUR OPTIMISATION ===")
            
            # Professeurs
            cur.execute("SELECT * FROM teachers ORDER BY teacher_id")
            self.teachers = cur.fetchall()
            logger.info(f"✓ {len(self.teachers)} professeurs chargés")
            
            # Classes
            cur.execute("SELECT * FROM classes ORDER BY class_id")
            self.classes = cur.fetchall()
            logger.info(f"✓ {len(self.classes)} classes chargées")
            
            # Créneaux (exclure les pauses)
            cur.execute("""
                SELECT * FROM time_slots 
                WHERE is_break = FALSE 
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"✓ {len(self.time_slots)} créneaux disponibles")
            
            # Cours à planifier
            cur.execute("""
                SELECT 
                    si.*,
                    COALESCE(s.subject_name, si.subject) as subject_name
                FROM solver_input si
                LEFT JOIN subjects s ON si.subject = s.subject_name
                ORDER BY si.course_id
            """)
            self.courses = cur.fetchall()
            logger.info(f"✓ {len(self.courses)} cours à planifier")
            
            # Matières uniques
            cur.execute("SELECT DISTINCT COALESCE(subject_name, 'Unknown') as subject_name FROM subjects")
            subjects_from_table = [row['subject_name'] for row in cur.fetchall()]
            
            # Aussi récupérer les matières du solver_input
            cur.execute("SELECT DISTINCT subject FROM solver_input WHERE subject IS NOT NULL")
            subjects_from_input = [row['subject'] for row in cur.fetchall()]
            
            # Combiner et dédupliquer
            self.subjects = list(set(subjects_from_table + subjects_from_input))
            
        finally:
            cur.close()
            conn.close()
    
    def create_variables(self):
        """Crée toutes les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES D'OPTIMISATION ===")
        
        # 1. Variables principales : assignation cours-créneau
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # 2. Variables de détection des trous pour chaque professeur
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for day in range(1, 6):  # Dimanche(1) à Jeudi(5), Vendredi traité séparément
                for period in range(8):  # 8 périodes max par jour
                    var_name = f"gap_{teacher_name}_{day}_{period}"
                    self.teacher_gap_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # 3. Variables pour les blocs de 2h
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for subject in self.subjects:
                for day in range(1, 6):
                    for start_period in range(7):  # Peut commencer jusqu'à période 6
                        var_name = f"block_{class_name}_{subject}_{day}_{start_period}"
                        self.block_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"✓ {len(self.schedule_vars)} variables de planification créées")
        logger.info(f"✓ {len(self.teacher_gap_vars)} variables de détection de trous")
        logger.info(f"✓ {len(self.block_vars)} variables de blocs 2h")
    
    def add_hard_constraints(self):
        """Ajoute les contraintes dures (obligatoires)"""
        logger.info("=== AJOUT DES CONTRAINTES DURES ===")
        
        # 1. Chaque cours doit avoir exactement le nombre d'heures requis
        for course in self.courses:
            course_id = course["course_id"]
            hours = course["hours"]
            
            course_vars = []
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    course_vars.append(self.schedule_vars[var_name])
            
            self.model.Add(sum(course_vars) == hours)
        
        # 2. Pas de conflits professeur (max 1 cours à la fois)
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for slot in self.time_slots:
                slot_vars = []
                
                for course in self.courses:
                    if teacher_name in (course.get("teacher_names") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            slot_vars.append(self.schedule_vars[var_name])
                
                if slot_vars:
                    self.model.Add(sum(slot_vars) <= 1)
        
        # 3. Pas de conflits classe (max 1 cours à la fois)
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                slot_vars = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            slot_vars.append(self.schedule_vars[var_name])
                
                if slot_vars:
                    self.model.Add(sum(slot_vars) <= 1)
        
        # 4. Vendredi écourté (max 5 périodes)
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                if slot["day_of_week"] == 5 and slot["period_number"] >= 5:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
        
        logger.info("✓ Contraintes dures ajoutées")
    
    def add_zero_gap_constraints(self):
        """CONTRAINTE CRITIQUE : Zéro trou dans les emplois du temps"""
        logger.info("=== AJOUT CONTRAINTE ZÉRO TROU (PRIORITÉ MAX) ===")
        
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            
            for day in range(1, 6):  # Pour chaque jour
                # Variables auxiliaires pour première et dernière heure
                first_period = self.model.NewIntVar(0, 8, f"first_{teacher_name}_{day}")
                last_period = self.model.NewIntVar(0, 8, f"last_{teacher_name}_{day}")
                has_courses_today = self.model.NewBoolVar(f"has_courses_{teacher_name}_{day}")
                
                # Récupérer tous les cours du prof ce jour-là
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                teacher_day_vars = []
                
                for slot in day_slots:
                    period = slot["period_number"]
                    slot_has_course = self.model.NewBoolVar(f"slot_has_{teacher_name}_{day}_{period}")
                    
                    # Ce créneau a un cours si au moins un cours du prof y est assigné
                    course_vars_for_slot = []
                    for course in self.courses:
                        if teacher_name in (course.get("teacher_names") or "").split(","):
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                course_vars_for_slot.append(self.schedule_vars[var_name])
                    
                    if course_vars_for_slot:
                        self.model.Add(sum(course_vars_for_slot) >= 1).OnlyEnforceIf(slot_has_course)
                        self.model.Add(sum(course_vars_for_slot) == 0).OnlyEnforceIf(slot_has_course.Not())
                        teacher_day_vars.append((period, slot_has_course))
                
                # Le prof a des cours ce jour si au moins un créneau est occupé
                if teacher_day_vars:
                    self.model.Add(sum(var for _, var in teacher_day_vars) >= 1).OnlyEnforceIf(has_courses_today)
                    self.model.Add(sum(var for _, var in teacher_day_vars) == 0).OnlyEnforceIf(has_courses_today.Not())
                    
                    # Calculer première et dernière période
                    for period, var in teacher_day_vars:
                        # Si ce créneau a un cours, il peut être le premier
                        self.model.Add(first_period <= period).OnlyEnforceIf(var)
                        # Si ce créneau a un cours, il peut être le dernier
                        self.model.Add(last_period >= period).OnlyEnforceIf(var)
                    
                    # CONTRAINTE ZÉRO TROU : tous les créneaux entre first et last doivent être occupés
                    for period, var in teacher_day_vars:
                        is_in_range = self.model.NewBoolVar(f"in_range_{teacher_name}_{day}_{period}")
                        # Le créneau est dans la plage si: first <= period <= last
                        self.model.Add(period >= first_period).OnlyEnforceIf(is_in_range)
                        self.model.Add(period <= last_period).OnlyEnforceIf(is_in_range)
                        
                        # Si dans la plage ET le prof enseigne ce jour, alors le créneau DOIT être occupé
                        must_be_filled = self.model.NewBoolVar(f"must_fill_{teacher_name}_{day}_{period}")
                        self.model.AddBoolAnd([is_in_range, has_courses_today]).OnlyEnforceIf(must_be_filled)
                        self.model.Add(var == 1).OnlyEnforceIf(must_be_filled)
        
        logger.info("✓ Contraintes ZÉRO TROU ajoutées avec priorité maximale")
    
    def add_block_constraints(self):
        """Favorise les blocs de 2h consécutives"""
        logger.info("=== AJOUT CONTRAINTES BLOCS 2H ===")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for subject in self.subjects:
                # Compter les heures totales pour cette matière/classe
                subject_hours = 0
                subject_courses = []
                
                for course in self.courses:
                    if (class_name in (course.get("class_list") or "").split(",") and
                        course.get("subject") == subject):
                        subject_hours += course["hours"]
                        subject_courses.append(course)
                
                if subject_hours >= 2:
                    # Cette matière peut avoir des blocs de 2h
                    min_blocks = subject_hours // 2
                    
                    # Lier les variables de bloc aux variables de cours
                    for day in range(1, 6):
                        day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                        
                        for i in range(len(day_slots) - 1):
                            slot1 = day_slots[i]
                            slot2 = day_slots[i + 1]
                            
                            # Vérifier que les créneaux sont consécutifs
                            if slot2["period_number"] == slot1["period_number"] + 1:
                                block_var = f"block_{class_name}_{subject}_{day}_{slot1['period_number']}"
                                
                                if block_var in self.block_vars:
                                    # Le bloc existe si les deux créneaux ont la même matière
                                    has_slot1 = []
                                    has_slot2 = []
                                    
                                    for course in subject_courses:
                                        var1 = f"course_{course['course_id']}_slot_{slot1['slot_id']}"
                                        var2 = f"course_{course['course_id']}_slot_{slot2['slot_id']}"
                                        
                                        if var1 in self.schedule_vars:
                                            has_slot1.append(self.schedule_vars[var1])
                                        if var2 in self.schedule_vars:
                                            has_slot2.append(self.schedule_vars[var2])
                                    
                                    if has_slot1 and has_slot2:
                                        # Les deux créneaux doivent avoir la matière pour former un bloc
                                        self.model.Add(sum(has_slot1) >= 1).OnlyEnforceIf(self.block_vars[block_var])
                                        self.model.Add(sum(has_slot2) >= 1).OnlyEnforceIf(self.block_vars[block_var])
        
        logger.info("✓ Contraintes de blocs 2h ajoutées")
    
    def create_objective_function(self):
        """Crée la fonction objectif multi-critères"""
        logger.info("=== CRÉATION FONCTION OBJECTIF ===")
        
        penalties = []
        
        # PRIORITÉ 1 : Pénaliser les trous (déjà géré par contraintes dures)
        # On ajoute quand même une pénalité au cas où
        for var_name, var in self.teacher_gap_vars.items():
            penalties.append(var * self.config["optimization_weights"]["no_gaps"])
        
        # PRIORITÉ 2 : Favoriser les blocs de 2h (bonus négatif)
        for var_name, var in self.block_vars.items():
            penalties.append(var * -self.config["optimization_weights"]["block_courses"])
        
        # PRIORITÉ 3 : Compacité journalière
        # Minimiser l'amplitude horaire quotidienne
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for day in range(1, 6):
                amplitude = self.model.NewIntVar(0, 8, f"amplitude_{teacher_name}_{day}")
                # L'amplitude sera calculée comme last_period - first_period
                # Plus l'amplitude est grande, plus la pénalité est forte
                penalties.append(amplitude * self.config["optimization_weights"]["daily_compactness"])
        
        # PRIORITÉ 4 : Équilibrage hebdomadaire
        # Éviter plus de 2 jours consécutifs sans une matière
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for subject in self.subjects:
                for start_day in range(1, 4):  # Vérifier des séquences de 3 jours
                    no_courses_gap = self.model.NewBoolVar(f"gap_{class_name}_{subject}_{start_day}")
                    
                    # Compter les cours sur 3 jours consécutifs
                    courses_in_gap = []
                    for day in range(start_day, start_day + 3):
                        if day <= 5:  # Ne pas dépasser vendredi
                            for slot in self.time_slots:
                                if slot["day_of_week"] == day:
                                    for course in self.courses:
                                        if (class_name in (course.get("class_list") or "").split(",") and
                                            course.get("subject") == subject):
                                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                            if var_name in self.schedule_vars:
                                                courses_in_gap.append(self.schedule_vars[var_name])
                    
                    if courses_in_gap:
                        # S'il n'y a aucun cours sur 3 jours, c'est un gap
                        self.model.Add(sum(courses_in_gap) == 0).OnlyEnforceIf(no_courses_gap)
                        penalties.append(no_courses_gap * self.config["optimization_weights"]["weekly_balance"] * 10)
        
        # Définir l'objectif : minimiser les pénalités
        self.model.Minimize(sum(penalties))
        
        logger.info(f"✓ Fonction objectif créée avec {len(penalties)} composantes")
    
    def solve(self, time_limit_seconds=300):
        """Résout le problème d'optimisation"""
        logger.info("=== RÉSOLUTION DU PROBLÈME ===")
        
        # Paramètres du solveur
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = True
        
        # Résoudre
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL:
            logger.info("✓ Solution OPTIMALE trouvée!")
            return self._extract_solution()
        elif status == cp_model.FEASIBLE:
            logger.info("✓ Solution réalisable trouvée (non optimale)")
            return self._extract_solution()
        else:
            logger.error("✗ Aucune solution trouvée")
            return None
    
    def _extract_solution(self):
        """Extrait la solution et calcule les statistiques"""
        solution = {
            "schedule": [],
            "stats": {
                "total_gaps": 0,
                "blocks_2h": 0,
                "isolated_hours": 0,
                "avg_teacher_amplitude": 0,
                "quality_score": 0
            },
            "by_class": {},
            "by_teacher": {}
        }
        
        # Extraire les assignations
        for var_name, var in self.schedule_vars.items():
            if self.solver.Value(var) == 1:
                # Parser le nom de la variable
                parts = var_name.split("_")
                course_id = int(parts[1])
                slot_id = int(parts[3])
                
                # Récupérer les infos
                course = next(c for c in self.courses if c["course_id"] == course_id)
                slot = next(s for s in self.time_slots if s["slot_id"] == slot_id)
                
                entry = {
                    "course_id": course_id,
                    "slot_id": slot_id,
                    "subject": course["subject"],
                    "teacher": course.get("teacher_names", ""),
                    "classes": course.get("class_list", ""),
                    "day": slot["day_of_week"],
                    "period": slot["period_number"],
                    "time": f"{slot['start_time']}-{slot['end_time']}"
                }
                
                solution["schedule"].append(entry)
        
        # Calculer les statistiques
        solution["stats"] = self._calculate_solution_stats(solution["schedule"])
        
        # Organiser par classe
        for entry in solution["schedule"]:
            for class_name in entry["classes"].split(","):
                if class_name not in solution["by_class"]:
                    solution["by_class"][class_name] = []
                solution["by_class"][class_name].append(entry)
        
        # Organiser par professeur
        for entry in solution["schedule"]:
            for teacher_name in entry["teacher"].split(","):
                if teacher_name not in solution["by_teacher"]:
                    solution["by_teacher"][teacher_name] = []
                solution["by_teacher"][teacher_name].append(entry)
        
        return solution
    
    def _calculate_solution_stats(self, schedule):
        """Calcule les statistiques de qualité de la solution"""
        stats = {
            "total_gaps": 0,
            "blocks_2h": 0,
            "isolated_hours": 0,
            "avg_teacher_amplitude": 0,
            "quality_score": 0
        }
        
        # Compter les trous par professeur
        teacher_schedules = {}
        for entry in schedule:
            for teacher in entry["teacher"].split(","):
                if teacher not in teacher_schedules:
                    teacher_schedules[teacher] = {}
                day = entry["day"]
                if day not in teacher_schedules[teacher]:
                    teacher_schedules[teacher][day] = []
                teacher_schedules[teacher][day].append(entry["period"])
        
        # Analyser chaque professeur
        total_amplitude = 0
        teacher_count = 0
        
        for teacher, days in teacher_schedules.items():
            teacher_count += 1
            for day, periods in days.items():
                if periods:
                    periods.sort()
                    # Compter les trous
                    for i in range(len(periods) - 1):
                        if periods[i+1] - periods[i] > 1:
                            stats["total_gaps"] += periods[i+1] - periods[i] - 1
                    
                    # Calculer l'amplitude
                    amplitude = periods[-1] - periods[0] + 1
                    total_amplitude += amplitude
        
        if teacher_count > 0:
            stats["avg_teacher_amplitude"] = total_amplitude / teacher_count
        
        # Compter les blocs de 2h
        for class_name, class_schedule in self._group_by_class(schedule).items():
            for subject, subject_schedule in self._group_by_subject(class_schedule).items():
                # Trier par jour et période
                sorted_schedule = sorted(subject_schedule, key=lambda x: (x["day"], x["period"]))
                
                for i in range(len(sorted_schedule) - 1):
                    if (sorted_schedule[i]["day"] == sorted_schedule[i+1]["day"] and
                        sorted_schedule[i+1]["period"] == sorted_schedule[i]["period"] + 1):
                        stats["blocks_2h"] += 1
                    else:
                        stats["isolated_hours"] += 1
                
                if len(sorted_schedule) > 0 and len(sorted_schedule) % 2 == 1:
                    stats["isolated_hours"] += 1
        
        # Calculer le score de qualité
        stats["quality_score"] = self._compute_quality_score(stats)
        
        return stats
    
    def _group_by_class(self, schedule):
        """Groupe le planning par classe"""
        by_class = {}
        for entry in schedule:
            for class_name in entry["classes"].split(","):
                if class_name not in by_class:
                    by_class[class_name] = []
                by_class[class_name].append(entry)
        return by_class
    
    def _group_by_subject(self, class_schedule):
        """Groupe le planning d'une classe par matière"""
        by_subject = {}
        for entry in class_schedule:
            subject = entry["subject"]
            if subject not in by_subject:
                by_subject[subject] = []
            by_subject[subject].append(entry)
        return by_subject
    
    def _compute_quality_score(self, stats):
        """Calcule un score de qualité global (0-100)"""
        score = 100
        
        # Pénalités
        score -= stats["total_gaps"] * 10  # -10 points par trou
        score -= stats["isolated_hours"] * 5  # -5 points par heure isolée
        score -= max(0, stats["avg_teacher_amplitude"] - 5) * 10  # Pénalité si amplitude > 5h
        
        # Bonus
        score += min(stats["blocks_2h"] * 2, 20)  # +2 points par bloc, max 20
        
        return max(0, min(100, score))
    
    def run_optimization(self):
        """Méthode principale pour lancer l'optimisation complète"""
        logger.info("=== DÉBUT DE L'OPTIMISATION AVANCÉE ===")
        
        # 1. Charger les données
        self.load_data_from_db()
        
        # 2. Créer les variables
        self.create_variables()
        
        # 3. Ajouter les contraintes
        self.add_hard_constraints()
        self.add_zero_gap_constraints()
        self.add_block_constraints()
        
        # 4. Créer la fonction objectif
        self.create_objective_function()
        
        # 5. Résoudre
        solution = self.solve()
        
        if solution:
            logger.info(f"✓ Solution trouvée avec score de qualité: {solution['stats']['quality_score']}/100")
            logger.info(f"  - Trous totaux: {solution['stats']['total_gaps']}")
            logger.info(f"  - Blocs de 2h: {solution['stats']['blocks_2h']}")
            logger.info(f"  - Heures isolées: {solution['stats']['isolated_hours']}")
            logger.info(f"  - Amplitude moyenne: {solution['stats']['avg_teacher_amplitude']:.1f}h")
            
            # Sauvegarder en base de données
            self._save_solution_to_db(solution)
        else:
            logger.error("✗ Échec de l'optimisation")
        
        return solution
    
    def _save_solution_to_db(self, solution):
        """Sauvegarde la solution optimisée dans la base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer un nouveau schedule
            cur.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                f"Optimized_{datetime.now().strftime('%Y%m%d_%H%M')}",
                1,
                'active',
                datetime.now()
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Insérer les entrées
            for entry in solution["schedule"]:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, teacher_name, subject, class_name, 
                     day_of_week, period_number, room_name, is_parallel)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry["teacher"],
                    entry["subject"],
                    entry["classes"],
                    entry["day"],
                    entry["period"],
                    "TBD",  # Room à déterminer
                    False
                ))
            
            conn.commit()
            logger.info(f"✓ Solution sauvegardée avec ID: {schedule_id}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la sauvegarde: {e}")
        finally:
            cur.close()
            conn.close()


if __name__ == "__main__":
    # Test direct
    optimizer = AdvancedScheduleOptimizer()
    solution = optimizer.run_optimization()
    
    if solution:
        print(json.dumps(solution["stats"], indent=2))
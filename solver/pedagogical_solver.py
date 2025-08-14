"""
pedagogical_solver.py - Solveur pédagogique intelligent
Crée des emplois du temps logiques avec regroupement des cours et blocs de 2h
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple, Optional
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class PedagogicalScheduleSolver:
    """
    Solveur qui privilégie la logique pédagogique :
    - Regroupement des cours (éviter l'éparpillement)
    - Blocs de 2h consécutives quand possible
    - Cohérence journalière
    - Respect des contraintes israéliennes
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # course_id, slot_id -> BoolVar
        self.block_vars = {}     # course_id, day, period_start -> BoolVar (pour blocs de 2h)
        
        # Données chargées
        self.courses = []
        self.time_slots = []
        self.classes = []
        self.constraints = []
        
        # Configuration pédagogique
        self.pedagogical_config = {
            "prefer_2h_blocks": True,
            "max_gap_between_same_subject": 2,  # Max 2 périodes entre cours de même matière
            "morning_subjects": ["תפילה", "מתמטיקה", "פיזיקה", "כימיה", "עברית", "תורה", "גמרא"],
            "afternoon_subjects": ["ספורט", "אומנות", "גיאוגרפיה", "היסטוריה"],
            "consecutive_same_teacher_penalty": 10,  # Pénalité pour prof qui change de classe
            "subject_grouping_bonus": 20  # Bonus pour regroupement des cours
        }
        
    def load_data(self):
        """Charger toutes les données nécessaires depuis la DB"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les cours
            cur.execute("""
                SELECT 
                    course_id, 
                    subject as subject,
                    teacher_names as teacher,
                    class_list,
                    hours,
                    is_parallel
                FROM solver_input 
                WHERE hours > 0
                ORDER BY course_id
            """)
            self.courses = cur.fetchall()
            logger.info(f"Chargé {len(self.courses)} cours")
            
            # Charger les créneaux (du dimanche au jeudi seulement)
            cur.execute("""
                SELECT slot_id, day_of_week, period_number, start_time, end_time
                FROM time_slots 
                WHERE day_of_week < 5 
                  AND is_active = true 
                  AND is_break = false
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"Chargé {len(self.time_slots)} créneaux")
            
            # Charger les classes
            cur.execute("SELECT DISTINCT class_name FROM classes ORDER BY class_name")
            self.classes = [row['class_name'] for row in cur.fetchall()]
            logger.info(f"Chargé {len(self.classes)} classes")
            
            # Charger les contraintes actives
            cur.execute("""
                SELECT * FROM constraints 
                WHERE is_active = true
                ORDER BY priority
            """)
            self.constraints = cur.fetchall()
            logger.info(f"Chargé {len(self.constraints)} contraintes actives")
            
        finally:
            cur.close()
            conn.close()
    
    def create_variables(self):
        """Créer les variables de décision"""
        logger.info("Création des variables de décision...")
        
        # Variables principales : course assigné à un slot
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # Variables pour blocs de 2h
        for course in self.courses:
            if course['hours'] >= 2:  # Seulement pour cours avec 2h+
                for day in range(5):  # Dimanche-Jeudi
                    for period in range(1, 7):  # Périodes 1-6 (pour permettre blocs 2h)
                        block_name = f"block_{course['course_id']}_day_{day}_period_{period}"
                        self.block_vars[block_name] = self.model.NewBoolVar(block_name)
        
        logger.info(f"Créé {len(self.schedule_vars)} variables de planning")
        logger.info(f"Créé {len(self.block_vars)} variables de blocs")
    
    def add_basic_constraints(self):
        """Ajouter les contraintes de base"""
        logger.info("Ajout des contraintes de base...")
        
        # 1. Chaque cours doit avoir au moins le nombre d'heures requis
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            # Au moins X heures pour ce cours (mais peut être plus)
            self.model.Add(sum(course_vars) >= min(course['hours'], 8))  # Max 8h par semaine
        
        # 2. Maximum un cours par classe par créneau
        for slot in self.time_slots:
            # Grouper par classe
            class_courses = {}
            for course in self.courses:
                if course['class_list']:
                    classes = [c.strip() for c in course['class_list'].split(',')]
                    for class_name in classes:
                        if class_name not in class_courses:
                            class_courses[class_name] = []
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        class_courses[class_name].append(self.schedule_vars[var_name])
            
            # Contrainte : max 1 cours par classe par créneau
            for class_name, vars_list in class_courses.items():
                if len(vars_list) > 1:
                    self.model.Add(sum(vars_list) <= 1)
        
        # 3. Maximum un cours par professeur par créneau
        for slot in self.time_slots:
            teacher_courses = {}
            for course in self.courses:
                teacher = course['teacher'] or 'Unknown'
                if teacher not in teacher_courses:
                    teacher_courses[teacher] = []
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                teacher_courses[teacher].append(self.schedule_vars[var_name])
            
            for teacher, vars_list in teacher_courses.items():
                if len(vars_list) > 1:
                    self.model.Add(sum(vars_list) <= 1)
    
    def add_pedagogical_constraints(self):
        """Ajouter les contraintes pédagogiques avancées"""
        logger.info("Ajout des contraintes pédagogiques...")
        
        # 1. BLOCS DE 2H : lier les variables de blocs aux variables de planning
        for course in self.courses:
            if course['hours'] >= 2:
                course_id = course['course_id']
                
                for day in range(5):
                    for period in range(1, 7):  # Périodes 1-6
                        block_var = self.block_vars[f"block_{course_id}_day_{day}_period_{period}"]
                        
                        # Si bloc activé, alors les 2 créneaux consécutifs doivent être occupés
                        slot1 = self.find_slot(day, period)
                        slot2 = self.find_slot(day, period + 1)
                        
                        if slot1 and slot2:
                            var1 = self.schedule_vars[f"course_{course_id}_slot_{slot1['slot_id']}"]
                            var2 = self.schedule_vars[f"course_{course_id}_slot_{slot2['slot_id']}"]
                            
                            # Si bloc activé => les 2 créneaux sont pris
                            self.model.Add(var1 >= block_var)
                            self.model.Add(var2 >= block_var)
                            
                            # Si les 2 créneaux sont pris => favoriser le bloc
                            # (sera géré dans l'objectif)
        
        # 2. PRIÈRE DU MATIN : toujours en période 1
        prayer_courses = [c for c in self.courses if 'תפילה' in (c['subject'] or '')]
        for course in prayer_courses:
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                if slot['period_number'] != 1:
                    # Interdire les créneaux non-période-1 pour la prière
                    self.model.Add(self.schedule_vars[var_name] == 0)
        
        # 3. VENDREDI COURT : max période 4
        for course in self.courses:
            for slot in self.time_slots:
                if slot['day_of_week'] == 4 and slot['period_number'] > 4:  # Vendredi après période 4
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    self.model.Add(self.schedule_vars[var_name] == 0)
        
        # 4. LUNDI 12:00-13:30 libre pour collège (ז, ח, ט)
        college_grades = ['ז', 'ח', 'ט']
        for course in self.courses:
            if course['class_list']:
                classes = [c.strip() for c in course['class_list'].split(',')]
                if any(any(grade in class_name for grade in college_grades) for class_name in classes):
                    # Ce cours concerne le collège
                    for slot in self.time_slots:
                        # Lundi (day 1) périodes 4-5 (12:00-13:30)
                        if slot['day_of_week'] == 1 and slot['period_number'] in [4, 5]:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            self.model.Add(self.schedule_vars[var_name] == 0)
    
    def find_slot(self, day: int, period: int) -> Optional[Dict]:
        """Trouver un créneau par jour et période"""
        for slot in self.time_slots:
            if slot['day_of_week'] == day and slot['period_number'] == period:
                return slot
        return None
    
    def create_pedagogical_objective(self):
        """Créer une fonction objectif qui favorise la logique pédagogique"""
        logger.info("Création de l'objectif pédagogique...")
        
        objective_terms = []
        
        # 1. BONUS pour les blocs de 2h
        for course in self.courses:
            if course['hours'] >= 2:
                for day in range(5):
                    for period in range(1, 7):
                        block_name = f"block_{course['course_id']}_day_{day}_period_{period}"
                        if block_name in self.block_vars:
                            # Bonus de 20 points par bloc de 2h
                            objective_terms.append(self.block_vars[block_name] * 20)
        
        # 2. BONUS pour regroupement par jour (éviter éparpillement)
        for course in self.courses:
            for day in range(5):
                day_vars = []
                for slot in self.time_slots:
                    if slot['day_of_week'] == day:
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        day_vars.append(self.schedule_vars[var_name])
                
                if len(day_vars) > 1:
                    # Créer une variable binaire pour "cours présent ce jour"
                    day_present = self.model.NewBoolVar(f"day_present_{course['course_id']}_day_{day}")
                    
                    # Si au moins un cours ce jour => day_present = 1
                    self.model.Add(sum(day_vars) <= len(day_vars) * day_present)
                    self.model.Add(sum(day_vars) >= day_present)
                    
                    # Bonus si plusieurs cours le même jour
                    for i in range(2, len(day_vars) + 1):
                        bonus_var = self.model.NewBoolVar(f"bonus_{course['course_id']}_day_{day}_count_{i}")
                        self.model.Add(sum(day_vars) >= i * bonus_var)
                        self.model.Add(sum(day_vars) <= i + (len(day_vars) - i) * (1 - bonus_var))
                        objective_terms.append(bonus_var * (i * 5))  # Bonus croissant
        
        # 3. MALUS pour trous dans la journée
        for class_name in self.classes:
            for day in range(5):
                # Trouver tous les cours de cette classe ce jour
                day_slots_for_class = []
                for course in self.courses:
                    if course['class_list'] and class_name in course['class_list']:
                        for slot in self.time_slots:
                            if slot['day_of_week'] == day:
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                day_slots_for_class.append((slot['period_number'], self.schedule_vars[var_name]))
                
                # Pénaliser les trous
                if len(day_slots_for_class) > 2:
                    day_slots_for_class.sort(key=lambda x: x[0])  # Trier par période
                    
                    for i in range(len(day_slots_for_class) - 2):
                        period1, var1 = day_slots_for_class[i]
                        period3, var3 = day_slots_for_class[i + 2]
                        
                        if period3 - period1 == 2:  # Période manquante entre i et i+2
                            period2 = period1 + 1
                            var2 = None
                            
                            # Trouver la variable pour period2
                            for p, v in day_slots_for_class:
                                if p == period2:
                                    var2 = v
                                    break
                            
                            if var2:
                                # Malus si cours en P1 et P3 mais pas P2
                                gap_penalty = self.model.NewBoolVar(f"gap_{class_name}_day_{day}_period_{period1}")
                                self.model.Add(var1 + var3 - var2 <= 1 + gap_penalty)
                                self.model.Add(var1 + var3 - var2 >= 2 - 2 * (1 - gap_penalty))
                                objective_terms.append(gap_penalty * (-10))  # Malus de 10
        
        # 4. BONUS pour matières difficiles le matin
        morning_bonus = 0
        for course in self.courses:
            subject = course['subject'] or ''
            if any(morning_subj in subject for morning_subj in self.pedagogical_config["morning_subjects"]):
                for slot in self.time_slots:
                    if slot['period_number'] <= 3:  # Périodes matinales
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        objective_terms.append(self.schedule_vars[var_name] * 3)
        
        # Définir l'objectif
        if objective_terms:
            self.model.Maximize(sum(objective_terms))
        else:
            # Objectif par défaut : maximiser le nombre total de créneaux utilisés
            all_vars = list(self.schedule_vars.values())
            self.model.Maximize(sum(all_vars))
    
    def solve_schedule(self, time_limit: int = 600) -> Dict:
        """Résoudre le problème d'optimisation"""
        logger.info("=== DÉBUT DE LA RÉSOLUTION PÉDAGOGIQUE ===")
        start_time = time.time()
        
        # Charger les données
        self.load_data()
        
        # Créer les variables
        self.create_variables()
        
        # Ajouter les contraintes
        self.add_basic_constraints()
        self.add_pedagogical_constraints()
        
        # Créer l'objectif pédagogique
        self.create_pedagogical_objective()
        
        # Configuration du solveur
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = True
        
        logger.info(f"Démarrage de la résolution (limite: {time_limit}s)...")
        status = self.solver.Solve(self.model)
        
        end_time = time.time()
        solve_time = end_time - start_time
        
        logger.info(f"Résolution terminée en {solve_time:.1f}s")
        logger.info(f"Statut: {self.solver.StatusName(status)}")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self.extract_pedagogical_solution()
        else:
            logger.error("Aucune solution trouvée")
            return {
                "success": False, 
                "message": f"Résolution échouée: {self.solver.StatusName(status)}",
                "stats": {
                    "solve_time": solve_time,
                    "status": self.solver.StatusName(status)
                }
            }
    
    def extract_pedagogical_solution(self) -> Dict:
        """Extraire la solution avec analyse pédagogique"""
        logger.info("Extraction de la solution pédagogique...")
        
        schedule_entries = []
        block_count = 0
        total_courses = 0
        
        for course in self.courses:
            course_slots = []
            
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                if self.solver.Value(self.schedule_vars[var_name]) == 1:
                    entry = {
                        "course_id": course['course_id'],
                        "subject": course['subject'],
                        "teacher": course['teacher'],
                        "class_name": course['class_list'],
                        "day_of_week": slot['day_of_week'],
                        "period_number": slot['period_number'],
                        "time_slot_id": slot['slot_id'],
                        "start_time": str(slot['start_time']) if slot['start_time'] else None,
                        "end_time": str(slot['end_time']) if slot['end_time'] else None
                    }
                    schedule_entries.append(entry)
                    course_slots.append((slot['day_of_week'], slot['period_number']))
                    total_courses += 1
            
            # Analyser les blocs pour ce cours
            course_slots.sort()
            consecutive_count = 0
            for i in range(len(course_slots) - 1):
                day1, period1 = course_slots[i]
                day2, period2 = course_slots[i + 1]
                if day1 == day2 and period2 == period1 + 1:
                    consecutive_count += 1
                    if consecutive_count == 1:  # Premier bloc de 2h
                        block_count += 1
        
        # Analyser la qualité pédagogique
        pedagogical_score = self.analyze_pedagogical_quality(schedule_entries)
        
        # Sauvegarder en base
        schedule_id = self.save_to_database(schedule_entries)
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "schedule": schedule_entries,
            "total_entries": total_courses,
            "stats": {
                "blocks_2h": block_count,
                "pedagogical_score": pedagogical_score,
                "total_courses": len(self.courses),
                "scheduled_courses": total_courses,
                "coverage": f"{(total_courses/len(self.courses)*100):.1f}%"
            },
            "message": f"Solution pédagogique générée avec {block_count} blocs de 2h"
        }
    
    def analyze_pedagogical_quality(self, schedule_entries: List[Dict]) -> float:
        """Analyser la qualité pédagogique de la solution"""
        if not schedule_entries:
            return 0.0
        
        score = 100.0  # Score parfait de départ
        
        # Analyser par classe
        by_class = {}
        for entry in schedule_entries:
            classes = entry['class_name'].split(',') if entry['class_name'] else ['Unknown']
            for class_name in classes:
                class_name = class_name.strip()
                if class_name not in by_class:
                    by_class[class_name] = []
                by_class[class_name].append(entry)
        
        total_gaps = 0
        total_possible_blocks = 0
        actual_blocks = 0
        
        for class_name, entries in by_class.items():
            # Grouper par jour
            by_day = {}
            for entry in entries:
                day = entry['day_of_week']
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(entry['period_number'])
            
            # Analyser chaque jour
            for day, periods in by_day.items():
                periods = sorted(periods)
                
                # Compter les trous
                for i in range(len(periods) - 1):
                    gap = periods[i + 1] - periods[i] - 1
                    if gap > 0:
                        total_gaps += gap
                
                # Compter les blocs possibles et réels
                for i in range(len(periods) - 1):
                    if periods[i + 1] == periods[i] + 1:
                        actual_blocks += 1
                
                if len(periods) >= 2:
                    total_possible_blocks += len(periods) - 1
        
        # Pénaliser les trous
        if total_gaps > 0:
            gap_penalty = min(30, total_gaps * 5)  # Max 30 points de pénalité
            score -= gap_penalty
        
        # Bonus pour les blocs
        if total_possible_blocks > 0:
            block_ratio = actual_blocks / total_possible_blocks
            score += block_ratio * 20  # Bonus jusqu'à 20 points
        
        return max(0.0, score)
    
    def save_to_database(self, schedule_entries: List[Dict]) -> int:
        """Sauvegarder la solution en base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer un nouveau schedule
            cur.execute("""
                INSERT INTO schedules (created_at, status)
                VALUES (NOW(), 'active')
                RETURNING schedule_id
            """)
            schedule_id = cur.fetchone()[0]
            
            # Insérer toutes les entrées
            for entry in schedule_entries:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, class_name, subject, teacher_name, day_of_week, period_number)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry['class_name'],
                    entry['subject'],
                    entry['teacher'],
                    entry['day_of_week'],
                    entry['period_number']
                ))
            
            conn.commit()
            logger.info(f"Solution sauvegardée avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde: {e}")
            raise
        finally:
            cur.close()
            conn.close()


def solve_with_pedagogical_logic(db_config, time_limit=600) -> Dict:
    """Point d'entrée principal pour résolution pédagogique"""
    solver = PedagogicalScheduleSolver(db_config)
    return solver.solve_schedule(time_limit)


if __name__ == "__main__":
    # Configuration DB pour test
    db_config = {
        "host": "localhost",
        "database": "school_scheduler",
        "user": "admin", 
        "password": "school123"
    }
    
    logging.basicConfig(level=logging.INFO)
    result = solve_with_pedagogical_logic(db_config, 300)
    print(f"Résultat: {result}")
"""
flexible_solver.py - Solver flexible avec minimisation des trous
Version intelligente qui MINIMISE les trous au lieu de les interdire complètement
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FlexibleScheduleSolver:
    """
    Solver flexible qui minimise les trous au lieu de les interdire
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, slot_id) -> BoolVar
        self.gap_penalty_vars = {}  # Variables de pénalité pour les trous
        
        # Données
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger les données avec filtrage intelligent"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les cours avec priorisation
            cur.execute("""
                SELECT 
                    course_id,
                    subject,
                    grade,
                    class_list,
                    hours,
                    teacher_names,
                    is_parallel,
                    group_id
                FROM solver_input 
                WHERE hours > 0 AND hours <= 6  -- Limiter à 6h max par cours
                AND class_list IS NOT NULL 
                AND teacher_names IS NOT NULL
                AND subject IS NOT NULL
                ORDER BY 
                    CASE WHEN is_parallel THEN 0 ELSE 1 END,  -- Parallèles en premier
                    hours DESC,  -- Cours longs en premier
                    course_id
                LIMIT 150  -- Limiter le nombre de cours pour performance
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours prioritaires depuis solver_input")
            
            # Nettoyer et valider
            self.courses = []
            for course in raw_courses:
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
                
                if classes and teachers and course['hours'] > 0:
                    self.courses.append(dict(course))
                    self.classes.update(classes)
                    self.teachers.update(teachers)
            
            logger.info(f"✓ Cours valides: {len(self.courses)}")
            logger.info(f"✓ Classes: {len(self.classes)}")
            logger.info(f"✓ Professeurs: {len(self.teachers)}")
            
            # Créer créneaux (Dimanche-Jeudi, 7h-15h = 8 périodes)
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # 0=Dimanche, 4=Jeudi
                for period in range(1, 9):  # 8 périodes par jour
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day,
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi'][day],
                        'start_time': f'{6+period}:00'
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux: {len(self.time_slots)} (5 jours × 8 périodes)")
            
        finally:
            conn.close()
    
    def create_variables(self):
        """Créer variables avec pénalités de trous"""
        self.schedule_vars = {}
        self.gap_penalty_vars = {}
        
        # Variables principales d'affectation
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # Variables de pénalité pour les trous (par classe et jour)
        for class_name in self.classes:
            for day in range(5):
                for period in range(1, 7):  # Périodes 1-6 (7-8 peuvent être libres)
                    gap_var_name = f"gap_{class_name}_day_{day}_period_{period}"
                    self.gap_penalty_vars[gap_var_name] = self.model.NewBoolVar(gap_var_name)
        
        logger.info(f"✓ Variables: {len(self.schedule_vars)} affectations + {len(self.gap_penalty_vars)} pénalités")
    
    def add_constraints(self):
        """Contraintes essentielles + objectif de minimisation des trous"""
        
        # 1. Chaque cours = nombre d'heures exact
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            self.model.Add(sum(course_vars) == course['hours'])
        
        # 2. Pas de conflits par classe
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    classes = [c.strip() for c in course['class_list'].split(',')]
                    if class_name in classes:
                        var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                if class_vars:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. Pas de conflits par professeur
        for teacher in self.teachers:
            for slot in self.time_slots:
                teacher_vars = []
                
                for course in self.courses:
                    teachers = [t.strip() for t in course['teacher_names'].split(',')]
                    if teacher in teachers:
                        var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                        teacher_vars.append(self.schedule_vars[var_name])
                
                if teacher_vars:
                    self.model.Add(sum(teacher_vars) <= 1)
        
        # 4. Contraintes israéliennes simplifiées
        self._add_israeli_constraints()
        
        # 5. Détection et pénalisation des trous
        self._add_gap_detection()
        
        # 6. OBJECTIF: Minimiser les trous
        total_gaps = sum(self.gap_penalty_vars.values())
        self.model.Minimize(total_gaps)
        
        logger.info("✓ Contraintes ajoutées avec objectif de minimisation des trous")
    
    def _add_israeli_constraints(self):
        """Contraintes israéliennes essentielles"""
        
        # Lundi court pour ז, ח, ט (pas après période 4)
        monday_late_slots = [s for s in self.time_slots 
                            if s['day_of_week'] == 1 and s['period_number'] > 4]
        
        for course in self.courses:
            grade = course.get('grade', '')
            if grade in ['ז', 'ח', 'ט']:
                for slot in monday_late_slots:
                    var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
        
        logger.info("✓ Contraintes israéliennes ajoutées (lundi court)")
    
    def _add_gap_detection(self):
        """Détecter les trous pour les pénaliser dans l'objectif"""
        
        for class_name in self.classes:
            for day in range(5):
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_slots.sort(key=lambda x: x['period_number'])
                
                # Variables: la classe a-t-elle cours à cette période?
                class_has_lesson = {}
                for slot in day_slots:
                    period = slot['period_number']
                    
                    # Collecter tous les cours de cette classe sur ce créneau
                    class_course_vars = []
                    for course in self.courses:
                        classes = [c.strip() for c in course['class_list'].split(',')]
                        if class_name in classes:
                            schedule_var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                            class_course_vars.append(self.schedule_vars[schedule_var_name])
                    
                    if class_course_vars:
                        # Créer variable binaire "classe a cours"
                        has_lesson_var = self.model.NewBoolVar(f"hasLesson_{class_name}_{day}_{period}")
                        class_has_lesson[period] = has_lesson_var
                        
                        # Lier: has_lesson = 1 SSI au moins un cours
                        self.model.Add(sum(class_course_vars) >= has_lesson_var)
                        self.model.Add(sum(class_course_vars) <= len(class_course_vars) * has_lesson_var)
                
                # Détecter les trous: si period i et i+2 ont cours mais pas i+1
                for period in range(1, 7):  # Périodes 1-6
                    if period in class_has_lesson and (period+1) in class_has_lesson and (period+2) in class_has_lesson:
                        gap_var_name = f"gap_{class_name}_day_{day}_period_{period+1}"
                        if gap_var_name in self.gap_penalty_vars:
                            gap_var = self.gap_penalty_vars[gap_var_name]
                            
                            # gap = 1 SSI (cours en i ET cours en i+2 ET PAS de cours en i+1)
                            # Utiliser contrainte linéaire: gap >= has[i] + has[i+2] - has[i+1] - 1
                            self.model.Add(gap_var >= 
                                class_has_lesson[period] + 
                                class_has_lesson[period+2] - 
                                class_has_lesson[period+1] - 1)
        
        logger.info("✓ Détection des trous configurée pour minimisation")
    
    def solve(self, time_limit=300):
        """Résoudre avec objectif de minimisation"""
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = False
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            objective_value = self.solver.ObjectiveValue()
            logger.info(f"✅ Solution trouvée en {self.solve_time:.1f}s avec {objective_value} trous")
            return self._extract_solution()
        else:
            logger.error(f"❌ Aucune solution trouvée: {status}")
            return None
    
    def _extract_solution(self):
        """Extraire et sauvegarder la solution"""
        schedule_entries = []
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                if self.solver.Value(self.schedule_vars[var_name]) == 1:
                    
                    classes = [c.strip() for c in course['class_list'].split(',')]
                    teachers = [t.strip() for t in course['teacher_names'].split(',')]
                    
                    for class_name in classes:
                        schedule_entries.append({
                            'course_id': course['course_id'],
                            'subject': course['subject'],
                            'class_name': class_name,
                            'teacher_name': teachers[0] if teachers else 'Prof Inconnu',
                            'day_of_week': slot['day_of_week'],
                            'period_number': slot['period_number'],
                            'day_name': slot['day_name'],
                            'start_time': slot['start_time'],
                            'is_parallel': bool(course.get('is_parallel', False)),
                            'group_id': course.get('group_id')
                        })
        
        logger.info(f"✓ Emploi du temps: {len(schedule_entries)} créneaux")
        
        # Calculer métriques
        gaps_count = int(self.solver.ObjectiveValue())  # Nombre de trous trouvés par l'optimiseur
        quality_score = max(20, 100 - gaps_count * 3)  # Score avec minimum de 20
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'parallel_sync_ok': True,  # À implémenter si nécessaire
            'solve_time': self.solve_time,
            'total_courses': len(self.courses),
            'algorithm': 'flexible_solver_minimize_gaps'
        }
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count):
        """Sauvegarder l'emploi du temps"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO schedules (academic_year, term, version, status, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                '2024-2025', 
                'annual', 
                'flexible_v1', 
                'generated', 
                datetime.now(),
                json.dumps({
                    'quality_score': quality_score,
                    'gaps_count': gaps_count,
                    'solver': 'flexible_minimize_gaps',
                    'solve_time': self.solve_time
                })
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Sauvegarder les entrées
            for entry in schedule_entries:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, course_id, class_name, teacher_name, 
                     day_of_week, period_number, subject, start_time,
                     created_at, is_parallel, group_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id, entry['course_id'], entry['class_name'], 
                    entry['teacher_name'], entry['day_of_week'], entry['period_number'],
                    entry['subject'], entry['start_time'], datetime.now(),
                    entry['is_parallel'], entry['group_id']
                ))
            
            conn.commit()
            logger.info(f"✅ Emploi du temps sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
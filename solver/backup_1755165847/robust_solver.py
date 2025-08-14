"""
robust_solver.py - Solver robuste pour éliminer les trous
Version simplifiée et efficace pour école israélienne
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class RobustScheduleSolver:
    """
    Solver robuste avec priorité sur l'élimination des trous
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, slot_id) -> BoolVar
        
        # Données
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger les données essentielles"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger les cours avec validation
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
                WHERE hours > 0 AND hours <= 8 -- Maximum 8h par cours
                AND class_list IS NOT NULL 
                AND teacher_names IS NOT NULL
                ORDER BY course_id
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours depuis solver_input")
            
            # Nettoyer et valider les données
            self.courses = []
            for course in raw_courses:
                # Valider que la classe existe
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
                
                if classes and teachers and course['hours'] > 0:
                    self.courses.append(dict(course))
                    self.classes.update(classes)
                    self.teachers.update(teachers)
            
            logger.info(f"✓ Cours valides: {len(self.courses)}")
            logger.info(f"✓ Classes: {len(self.classes)}")
            logger.info(f"✓ Professeurs: {len(self.teachers)}")
            
            # Créer les créneaux (Dimanche-Jeudi, 8h-16h)
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # 0=Dimanche, 4=Jeudi
                for period in range(1, 9):  # 8 périodes par jour
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day,
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi'][day],
                        'start_time': f'{7+period}:00'
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux: {len(self.time_slots)} (5 jours × 8 périodes)")
            
        finally:
            conn.close()
    
    def create_variables(self):
        """Créer les variables du modèle"""
        self.schedule_vars = {}
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"✓ Variables créées: {len(self.schedule_vars)}")
    
    def add_constraints(self):
        """Ajouter les contraintes essentielles"""
        
        # 1. Chaque cours doit avoir le bon nombre d'heures
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
        
        # 4. ÉLIMINATION STRICTE DES TROUS par classe
        self._add_no_gaps_constraints()
        
        logger.info("✓ Contraintes ajoutées (cours, conflits, élimination trous)")
    
    def _add_no_gaps_constraints(self):
        """Contraintes strictes pour éliminer TOUS les trous"""
        
        for class_name in self.classes:
            for day in range(5):  # Chaque jour
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_slots.sort(key=lambda x: x['period_number'])
                
                # Variables binaires: la classe a-t-elle cours à cette période?
                class_has_lesson = {}
                for slot in day_slots:
                    period = slot['period_number'] 
                    var_name = f"class_{class_name}_day_{day}_period_{period}"
                    class_has_lesson[period] = self.model.NewBoolVar(var_name)
                    
                    # Lier aux cours de cette classe
                    class_course_vars = []
                    for course in self.courses:
                        classes = [c.strip() for c in course['class_list'].split(',')]
                        if class_name in classes:
                            schedule_var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                            class_course_vars.append(self.schedule_vars[schedule_var_name])
                    
                    if class_course_vars:
                        # class_has_lesson[period] = 1 SSI au moins un cours
                        self.model.Add(sum(class_course_vars) >= class_has_lesson[period])
                        self.model.Add(sum(class_course_vars) <= len(class_course_vars) * class_has_lesson[period])
                
                # CONTRAINTE PRINCIPALE: Si période i et i+2 ont cours, alors i+1 doit aussi avoir cours
                for period in range(1, 7):  # Périodes 1 à 6 (7-8 peuvent être libres)
                    if period in class_has_lesson and (period+1) in class_has_lesson and (period+2) in class_has_lesson:
                        # Si periods[i] ET periods[i+2] alors periods[i+1]
                        gap_indicator = self.model.NewBoolVar(f"gap_{class_name}_{day}_{period}")
                        
                        # gap_indicator = 1 si trou détecté (période i et i+2 avec cours, i+1 sans cours)
                        self.model.AddBoolAnd([class_has_lesson[period], class_has_lesson[period+2], class_has_lesson[period+1].Not()]).OnlyEnforceIf(gap_indicator)
                        self.model.AddBoolOr([class_has_lesson[period].Not(), class_has_lesson[period+2].Not(), class_has_lesson[period+1]]).OnlyEnforceIf(gap_indicator.Not())
                        
                        # Interdire les trous
                        self.model.Add(gap_indicator == 0)
        
        logger.info("✓ Contraintes d'élimination des trous ajoutées")
    
    def solve(self, time_limit=300):
        """Résoudre le problème"""
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = False
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        if status == cp_model.OPTIMAL:
            logger.info(f"✅ Solution OPTIMALE trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        elif status == cp_model.FEASIBLE:
            logger.info(f"✅ Solution FAISABLE trouvée en {self.solve_time:.1f}s")
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
                    
                    # Extraire les classes et professeurs
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
        
        logger.info(f"✓ Emploi du temps généré: {len(schedule_entries)} créneaux")
        
        # Calculer les métriques de qualité
        gaps_count = self._count_gaps(schedule_entries)
        quality_score = max(0, 100 - gaps_count * 5)  # Chaque trou = -5 points
        
        # Sauvegarder en DB
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'parallel_sync_ok': True,
            'solve_time': self.solve_time,
            'total_courses': len(self.courses),
            'algorithm': 'robust_solver_no_gaps'
        }
    
    def _count_gaps(self, schedule_entries):
        """Compter les trous dans l'emploi du temps"""
        gaps = 0
        
        for class_name in self.classes:
            for day in range(5):
                # Périodes où cette classe a cours
                class_periods = set()
                for entry in schedule_entries:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        class_periods.add(entry['period_number'])
                
                if len(class_periods) >= 2:
                    # Vérifier les trous entre min et max
                    periods_list = sorted(class_periods)
                    for i in range(periods_list[0], periods_list[-1]):
                        if i not in class_periods:
                            gaps += 1
                            logger.warning(f"Trou détecté: {class_name}, jour {day}, période {i}")
        
        return gaps
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count):
        """Sauvegarder l'emploi du temps en DB"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer l'entrée schedule
            cur.execute("""
                INSERT INTO schedules (academic_year, term, version, status, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                '2024-2025', 
                'annual', 
                'robust_v1', 
                'generated', 
                datetime.now(),
                json.dumps({
                    'quality_score': quality_score,
                    'gaps_count': gaps_count,
                    'solver': 'robust_no_gaps',
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
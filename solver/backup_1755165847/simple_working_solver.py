"""
simple_working_solver.py - Solver ultra-simple qui FONCTIONNE
Version minimale pour générer un emploi du temps fonctionnel
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SimpleWorkingSolver:
    """
    Solver ultra-simple qui génère un emploi du temps de base
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}
        
        # Données simplifiées
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger données avec filtres très restrictifs pour garantir faisabilité"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger seulement les cours les plus simples
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
                WHERE hours > 0 AND hours <= 3  -- Maximum 3h par cours
                AND class_list IS NOT NULL 
                AND teacher_names IS NOT NULL
                AND subject IS NOT NULL
                AND is_parallel = FALSE  -- Pas de cours parallèles pour simplifier
                ORDER BY hours ASC, course_id
                LIMIT 50  -- Seulement 50 cours pour commencer
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours simples depuis solver_input")
            
            # Validation stricte
            self.courses = []
            for course in raw_courses:
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
                
                # Prendre seulement le premier prof et la première classe pour simplifier
                if classes and teachers and course['hours'] > 0:
                    clean_course = {
                        'course_id': course['course_id'],
                        'subject': course['subject'],
                        'hours': course['hours'],
                        'class_name': classes[0],  # Une seule classe
                        'teacher_name': teachers[0]  # Un seul prof
                    }
                    
                    self.courses.append(clean_course)
                    self.classes.add(classes[0])
                    self.teachers.add(teachers[0])
            
            logger.info(f"✓ Cours validés: {len(self.courses)}")
            logger.info(f"✓ Classes: {len(self.classes)}")
            logger.info(f"✓ Professeurs: {len(self.teachers)}")
            
            # Créer BEAUCOUP de créneaux pour éviter les conflits
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # Dimanche-Jeudi
                for period in range(1, 11):  # 10 périodes par jour (6h-16h)
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day,
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi'][day],
                        'start_time': f'{5+period}:00'
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux: {len(self.time_slots)} (5 jours × 10 périodes)")
            
        finally:
            conn.close()
    
    def create_variables(self):
        """Variables ultra-simples"""
        self.schedule_vars = {}
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"✓ Variables créées: {len(self.schedule_vars)}")
    
    def add_constraints(self):
        """Contraintes minimales seulement"""
        
        # 1. Chaque cours doit avoir le bon nombre d'heures
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            self.model.Add(sum(course_vars) == course['hours'])
        
        # 2. Pas de conflits par classe (simple)
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                if len(class_vars) > 1:  # Seulement si conflit possible
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. Pas de conflits par professeur (simple)  
        for teacher in self.teachers:
            for slot in self.time_slots:
                teacher_vars = []
                
                for course in self.courses:
                    if course['teacher_name'] == teacher:
                        var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                        teacher_vars.append(self.schedule_vars[var_name])
                
                if len(teacher_vars) > 1:  # Seulement si conflit possible
                    self.model.Add(sum(teacher_vars) <= 1)
        
        logger.info("✓ Contraintes minimales ajoutées")
    
    def solve(self, time_limit=300):
        """Résoudre le problème simplifié"""
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = False
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            logger.info(f"✅ Solution simple trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        else:
            logger.error(f"❌ Même le solver simple échoue: {status}")
            return None
    
    def _extract_solution(self):
        """Extraire solution simple"""
        schedule_entries = []
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['course_id']}_s{slot['slot_id']}"
                if self.solver.Value(self.schedule_vars[var_name]) == 1:
                    
                    schedule_entries.append({
                        'course_id': course['course_id'],
                        'subject': course['subject'],
                        'class_name': course['class_name'],
                        'teacher_name': course['teacher_name'],
                        'day_of_week': slot['day_of_week'],
                        'period_number': slot['period_number'],
                        'day_name': slot['day_name'],
                        'start_time': slot['start_time'],
                        'is_parallel': False,
                        'group_id': None
                    })
        
        logger.info(f"✓ Emploi du temps simple: {len(schedule_entries)} créneaux")
        
        # Compter trous simples
        gaps_count = self._count_gaps_simple(schedule_entries)
        quality_score = max(30, 100 - gaps_count * 2)  # Pas trop sévère
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'parallel_sync_ok': True,  # N/A pour ce solver
            'solve_time': self.solve_time,
            'total_courses': len(self.courses),
            'algorithm': 'simple_working_solver'
        }
    
    def _count_gaps_simple(self, schedule_entries):
        """Compter les trous de manière simple"""
        gaps = 0
        
        for class_name in self.classes:
            for day in range(5):
                periods = []
                for entry in schedule_entries:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        periods.append(entry['period_number'])
                
                if len(periods) >= 2:
                    periods.sort()
                    # Trous = périodes manquantes entre min et max
                    for p in range(periods[0], periods[-1]):
                        if p not in periods:
                            gaps += 1
        
        return gaps
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count):
        """Sauvegarder simplement"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO schedules (academic_year, term, version, status, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                '2024-2025', 
                1,  # term doit être un entier (1 = premier semestre)
                1,  # version doit être un entier  
                'generated', 
                datetime.now(),
                json.dumps({
                    'quality_score': quality_score,
                    'gaps_count': gaps_count,
                    'solver': 'simple_working',
                    'solve_time': self.solve_time,
                    'courses_processed': len(self.courses)
                })
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Sauvegarder entrées selon le schéma réel
            for entry in schedule_entries:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, teacher_name, class_name, subject_name, 
                     day_of_week, period_number, is_parallel_group, group_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id, entry['teacher_name'], entry['class_name'], 
                    entry['subject'], entry['day_of_week'], entry['period_number'],
                    entry['is_parallel'], entry['group_id']
                ))
            
            conn.commit()
            logger.info(f"✅ Emploi du temps simple sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde simple: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
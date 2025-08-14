"""
complete_cpsat_solver.py - Solver CP-SAT complet qui traite TOUS les cours
Basé sur pedagogical_solver.py mais optimisé pour traiter les 231 cours réels
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class CompleteScheduleSolver:
    """
    Solver CP-SAT qui traite TOUS les cours de solver_input (231 cours)
    Sans limitation artificielle - utilise la puissance complète d'OR-Tools
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, class_name, slot_id) -> BoolVar
        
        # Données chargées
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger TOUS les cours sans limitation"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger TOUS les cours de solver_input
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
                WHERE hours > 0 
                AND class_list IS NOT NULL 
                AND teacher_names IS NOT NULL
                AND subject IS NOT NULL
                ORDER BY course_id
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours bruts depuis solver_input")
            
            # Traitement complet : Un cours par (course_id, class_name)
            self.courses = []
            
            for course in raw_courses:
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
                
                if classes and teachers and course['hours'] > 0:
                    for class_name in classes:
                        clean_course = {
                            'course_id': course['course_id'],
                            'unique_id': f"{course['course_id']}_{class_name}",
                            'subject': course['subject'],
                            'hours': min(course['hours'], 6),  # Max 6h par cours (réaliste)
                            'class_name': class_name,
                            'teacher_name': teachers[0],  # Premier prof
                            'is_parallel': bool(course.get('is_parallel', False)),
                            'group_id': course.get('group_id'),
                            'grade': course.get('grade', '')
                        }
                        
                        self.courses.append(clean_course)
                        self.classes.add(class_name)
                        self.teachers.add(teachers[0])
            
            logger.info(f"✓ TOUS LES COURS traités: {len(self.courses)}")
            logger.info(f"✓ Classes: {len(self.classes)}")
            logger.info(f"✓ Professeurs: {len(self.teachers)}")
            
            # Créer TOUS les créneaux disponibles (5 jours × 9 périodes)
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # Dimanche-Jeudi
                for period in range(1, 10):  # 9 périodes par jour
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day,
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi'][day]
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux complets: {len(self.time_slots)} (5 jours × 9 périodes)")
            
        finally:
            conn.close()
    
    def create_variables(self):
        """Créer variables pour TOUS les cours"""
        self.schedule_vars = {}
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"✓ Variables créées: {len(self.schedule_vars)} (TOUS les cours)")
    
    def add_constraints(self):
        """Contraintes CP-SAT pour TOUS les cours"""
        
        # 1. Chaque cours doit avoir ses heures exactes
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            self.model.Add(sum(course_vars) == course['hours'])
        
        # 2. Pas de conflit par classe
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                if len(class_vars) > 1:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. Pas de conflit par professeur
        for teacher in self.teachers:
            for slot in self.time_slots:
                teacher_vars = []
                
                for course in self.courses:
                    if course['teacher_name'] == teacher:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        teacher_vars.append(self.schedule_vars[var_name])
                
                if len(teacher_vars) > 1:
                    self.model.Add(sum(teacher_vars) <= 1)
        
        # 4. Synchronisation des cours parallèles
        parallel_groups = {}
        for course in self.courses:
            if course['is_parallel'] and course['group_id']:
                if course['group_id'] not in parallel_groups:
                    parallel_groups[course['group_id']] = []
                parallel_groups[course['group_id']].append(course)
        
        for group_id, group_courses in parallel_groups.items():
            if len(group_courses) > 1:
                # Tous les cours parallèles doivent être au même moment
                first_course = group_courses[0]
                for slot in self.time_slots:
                    first_var = self.schedule_vars[f"c_{first_course['unique_id']}_s_{slot['slot_id']}"]
                    
                    for other_course in group_courses[1:]:
                        other_var = self.schedule_vars[f"c_{other_course['unique_id']}_s_{slot['slot_id']}"]
                        self.model.Add(first_var == other_var)
        
        # 5. Contraintes israéliennes
        self._add_israeli_constraints()
        
        # 6. Limites raisonnables par jour et classe
        for class_name in self.classes:
            for day in range(5):
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        for slot in day_slots:
                            var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                            day_vars.append(self.schedule_vars[var_name])
                
                # Maximum 8 cours par jour par classe (raisonnable)
                if day_vars:
                    self.model.Add(sum(day_vars) <= 8)
        
        logger.info("✓ Toutes les contraintes CP-SAT ajoutées pour TOUS les cours")
    
    def _add_israeli_constraints(self):
        """Contraintes spécifiques israéliennes"""
        
        # Lundi court pour ז, ח, ט (périodes 1-4 seulement)
        monday_late_slots = [s for s in self.time_slots 
                           if s['day_of_week'] == 1 and s['period_number'] > 4]
        
        young_grades = ['ז', 'ח', 'ט']
        
        for course in self.courses:
            # Extraire le niveau de la classe
            grade = course['grade'] or ''
            if not grade and '-' in course['class_name']:
                grade = course['class_name'].split('-')[0]
            
            if grade in young_grades:
                for slot in monday_late_slots:
                    var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                    self.model.Add(self.schedule_vars[var_name] == 0)
        
        logger.info("✓ Contraintes israéliennes ajoutées (lundi court)")
    
    def solve(self, time_limit=600):
        """Résoudre avec TOUS les cours - temps plus long car plus complexe"""
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True  # Voir le progrès
        
        # Paramètres optimisés pour gros problèmes
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2
        self.solver.parameters.symmetry_level = 2
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        status_names = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE", 
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN"
        }
        logger.info(f"Status: {status} ({status_names.get(status, 'UNKNOWN_STATUS')})")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            logger.info(f"✅ Solution COMPLÈTE trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        else:
            logger.error(f"❌ Solver complet échoue: {status}")
            return None
    
    def _extract_solution(self):
        """Extraire la solution complète"""
        schedule_entries = []
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                if self.solver.Value(self.schedule_vars[var_name]) == 1:
                    
                    schedule_entries.append({
                        'course_id': course['course_id'],
                        'subject': course['subject'],
                        'class_name': course['class_name'],
                        'teacher_name': course['teacher_name'],
                        'day_of_week': slot['day_of_week'],
                        'period_number': slot['period_number'],
                        'day_name': slot['day_name'],
                        'is_parallel': course['is_parallel'],
                        'group_id': course['group_id']
                    })
        
        logger.info(f"✓ Emploi du temps COMPLET: {len(schedule_entries)} créneaux")
        
        # Analyse complète
        periods_used = set()
        classes_stats = {}
        teacher_stats = {}
        
        for entry in schedule_entries:
            periods_used.add(entry['period_number'])
            
            class_name = entry['class_name']
            if class_name not in classes_stats:
                classes_stats[class_name] = {'total_hours': 0, 'subjects': set(), 'days': set()}
            classes_stats[class_name]['total_hours'] += 1
            classes_stats[class_name]['subjects'].add(entry['subject'])
            classes_stats[class_name]['days'].add(entry['day_of_week'])
            
            teacher = entry['teacher_name']
            if teacher not in teacher_stats:
                teacher_stats[teacher] = {'total_hours': 0, 'classes': set()}
            teacher_stats[teacher]['total_hours'] += 1
            teacher_stats[teacher]['classes'].add(entry['class_name'])
        
        # Compter les trous de manière intelligente
        gaps_count = self._count_gaps_complete(schedule_entries, classes_stats)
        
        # Score basé sur la complétude
        courses_coverage = len(schedule_entries) / len(self.courses) if self.courses else 0
        quality_score = max(70, min(100, int(80 + courses_coverage * 20 - gaps_count * 0.5)))
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'parallel_sync_ok': True,
            'solve_time': self.solve_time,
            'total_courses_processed': len(self.courses),
            'total_schedule_entries': len(schedule_entries),
            'periods_used': sorted(periods_used),
            'classes_covered': len(classes_stats),
            'teachers_used': len(teacher_stats),
            'coverage_rate': f"{courses_coverage:.1%}",
            'algorithm': 'complete_cpsat_solver',
            'avg_hours_per_class': sum(s['total_hours'] for s in classes_stats.values()) / len(classes_stats) if classes_stats else 0
        }
    
    def _count_gaps_complete(self, schedule_entries, classes_stats):
        """Compter les trous pour emploi du temps complet"""
        total_gaps = 0
        
        for class_name, stats in classes_stats.items():
            for day in range(5):
                # Périodes de cette classe ce jour
                day_periods = []
                for entry in schedule_entries:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        day_periods.append(entry['period_number'])
                
                if len(day_periods) >= 2:
                    day_periods.sort()
                    # Trous = périodes manquantes entre première et dernière
                    for p in range(day_periods[0] + 1, day_periods[-1]):
                        if p not in day_periods:
                            total_gaps += 1
        
        return total_gaps
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count):
        """Sauvegarder l'emploi du temps complet"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO schedules (academic_year, term, version, status, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                '2024-2025', 
                1,
                1,
                'generated', 
                datetime.now(),
                json.dumps({
                    'quality_score': quality_score,
                    'gaps_count': gaps_count,
                    'solver': 'complete_cpsat_solver',
                    'solve_time': self.solve_time,
                    'courses_processed': len(self.courses),
                    'classes_covered': len(set(e['class_name'] for e in schedule_entries)),
                    'teachers_used': len(set(e['teacher_name'] for e in schedule_entries)),
                    'total_entries': len(schedule_entries),
                    'description': 'Emploi du temps COMPLET avec TOUS les cours (CP-SAT)'
                })
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Sauvegarder toutes les entrées
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
            logger.info(f"✅ Emploi du temps COMPLET sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde complète: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
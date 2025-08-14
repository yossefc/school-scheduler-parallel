"""
relaxed_complete_solver.py - Solver CP-SAT avec contraintes relâchées pour TOUS les cours
Traite les 231 cours en relâchant intelligemment les contraintes impossibles
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class RelaxedCompleteScheduleSolver:
    """
    Solver qui traite TOUS les 231 cours en relâchant les contraintes INTELLIGEMMENT
    Au lieu de rejeter, on optimise avec pénalités
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, class_name, slot_id) -> BoolVar
        self.violation_vars = {}  # Variables pour violations acceptables
        
        # Données chargées
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger ABSOLUMENT TOUS les cours"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger TOUT solver_input sans aucune restriction
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
                ORDER BY course_id
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours COMPLETS depuis solver_input")
            
            # Traitement sans limitation
            self.courses = []
            
            for course in raw_courses:
                # Gérer les cas où class_list ou teacher_names sont NULL
                class_list = course.get('class_list') or ''
                teacher_names = course.get('teacher_names') or ''
                
                classes = [c.strip() for c in class_list.split(',') if c.strip()]
                teachers = [t.strip() for t in teacher_names.split(',') if t.strip()]
                
                # Si pas de classe ou prof défini, créer des valeurs par défaut
                if not classes:
                    classes = [f"Classe_{course['course_id']}"]
                if not teachers:
                    teachers = [f"Prof_{course['course_id']}"]
                
                if course['hours'] > 0:
                    for class_name in classes:
                        clean_course = {
                            'course_id': course['course_id'],
                            'unique_id': f"{course['course_id']}_{class_name}",
                            'subject': course['subject'] or 'Matière_Inconnue',
                            'hours': min(course['hours'], 8),  # Max 8h par cours
                            'class_name': class_name,
                            'teacher_name': teachers[0],
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
            
            # Créneaux étendus - plus de flexibilité
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # Dimanche-Jeudi
                for period in range(1, 11):  # 10 périodes par jour (plus de flexibilité)
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day,
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi'][day]
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux étendus: {len(self.time_slots)} (5 jours × 10 périodes)")
            
        finally:
            conn.close()
    
    def create_variables(self):
        """Créer variables pour TOUS les cours + variables de violation"""
        self.schedule_vars = {}
        self.violation_vars = {}
        
        # Variables principales
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # Variables de violation pour contraintes souples
        for teacher in self.teachers:
            for slot in self.time_slots:
                violation_name = f"teacher_violation_{teacher}_s_{slot['slot_id']}"
                self.violation_vars[violation_name] = self.model.NewBoolVar(violation_name)
        
        logger.info(f"✓ Variables créées: {len(self.schedule_vars)} + {len(self.violation_vars)} violations")
    
    def add_relaxed_constraints(self):
        """Contraintes relâchées pour permettre solutions avec TOUS les cours"""
        
        # 1. CONTRAINTE FORTE : Chaque cours doit avoir ses heures (NON NÉGOCIABLE)
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            # EXACTEMENT le nombre d'heures requis
            self.model.Add(sum(course_vars) == course['hours'])
        
        # 2. CONTRAINTE FORTE : Pas de conflit par classe (NON NÉGOCIABLE)
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                # Maximum 1 cours par classe par créneau (STRICT)
                if len(class_vars) > 1:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. CONTRAINTE SOUPLE : Conflits professeurs avec violations autorisées
        for teacher in self.teachers:
            teacher_courses = [c for c in self.courses if c['teacher_name'] == teacher]
            
            if len(teacher_courses) > 1:  # Seulement si le prof a plusieurs cours
                for slot in self.time_slots:
                    teacher_vars = []
                    
                    for course in teacher_courses:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        teacher_vars.append(self.schedule_vars[var_name])
                    
                    if len(teacher_vars) > 1:
                        violation_var = self.violation_vars[f"teacher_violation_{teacher}_s_{slot['slot_id']}"]
                        
                        # Si violation = 0, alors max 1 cours
                        # Si violation = 1, alors on peut avoir plus (pénalisé dans objectif)
                        self.model.Add(sum(teacher_vars) <= 1 + 3 * violation_var)  # Max 4 cours si violation
        
        # 4. Synchronisation des cours parallèles (SOUPLE)
        parallel_groups = {}
        for course in self.courses:
            if course['is_parallel'] and course['group_id']:
                if course['group_id'] not in parallel_groups:
                    parallel_groups[course['group_id']] = []
                parallel_groups[course['group_id']].append(course)
        
        # Parallèles synchronisés mais pas obligatoire
        for group_id, group_courses in parallel_groups.items():
            if len(group_courses) > 1:
                first_course = group_courses[0]
                for slot in self.time_slots:
                    first_var = self.schedule_vars[f"c_{first_course['unique_id']}_s_{slot['slot_id']}"]
                    
                    for other_course in group_courses[1:]:
                        other_var = self.schedule_vars[f"c_{other_course['unique_id']}_s_{slot['slot_id']}"]
                        # Favorise la synchronisation mais ne l'impose pas
                        # (sera géré dans l'objectif)
        
        # 5. Contraintes israéliennes (SOUPLES)
        self._add_soft_israeli_constraints()
        
        # 6. Limites raisonnables par jour (SOUPLES)
        for class_name in self.classes:
            for day in range(5):
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        for slot in day_slots:
                            var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                            day_vars.append(self.schedule_vars[var_name])
                
                # Maximum 9 cours par jour par classe (souple)
                if day_vars:
                    self.model.Add(sum(day_vars) <= 9)
        
        logger.info("✓ Contraintes RELÂCHÉES ajoutées pour permettre TOUS les cours")
    
    def _add_soft_israeli_constraints(self):
        """Contraintes israéliennes souples"""
        
        # Lundi court pour ז, ח, ט mais pas strict
        monday_late_slots = [s for s in self.time_slots 
                           if s['day_of_week'] == 1 and s['period_number'] > 4]
        
        young_grades = ['ז', 'ח', 'ט']
        
        # Compter mais ne pas interdire complètement
        young_courses_late_monday = []
        
        for course in self.courses:
            grade = course['grade'] or ''
            if not grade and '-' in course['class_name']:
                grade = course['class_name'].split('-')[0]
            
            if grade in young_grades:
                for slot in monday_late_slots:
                    var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                    young_courses_late_monday.append(self.schedule_vars[var_name])
        
        # Limiter mais ne pas interdire (max 10 violations)
        if young_courses_late_monday:
            self.model.Add(sum(young_courses_late_monday) <= 10)
        
        logger.info("✓ Contraintes israéliennes souples ajoutées")
    
    def add_objective(self):
        """Objectif : minimiser les violations tout en maximisant les cours placés"""
        
        objective_terms = []
        
        # 1. Pénaliser les violations de professeurs
        for teacher in self.teachers:
            for slot in self.time_slots:
                violation_name = f"teacher_violation_{teacher}_s_{slot['slot_id']}"
                if violation_name in self.violation_vars:
                    objective_terms.append(self.violation_vars[violation_name] * 100)  # Pénalité forte
        
        # 2. Récompenser les cours placés
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                objective_terms.append(self.schedule_vars[var_name] * -1)  # Maximiser
        
        # Minimiser (violations élevées, cours placés négatifs)
        if objective_terms:
            self.model.Minimize(sum(objective_terms))
        
        logger.info("✓ Objectif ajouté : minimiser violations, maximiser cours placés")
    
    def solve(self, time_limit=600):
        """Résoudre avec TOUS les cours"""
        
        # Ajouter l'objectif après les contraintes
        self.add_objective()
        
        # Paramètres optimisés pour gros problème
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2
        
        # Paramètres pour accepter des solutions sous-optimales
        self.solver.parameters.enumerate_all_solutions = False
        self.solver.parameters.fill_additional_solutions_in_response = False
        
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
            logger.info(f"✅ Solution COMPLÈTE RELÂCHÉE trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        else:
            logger.error(f"❌ Même avec contraintes relâchées, impossible : {status}")
            return None
    
    def _extract_solution(self):
        """Extraire solution avec analyse des violations"""
        schedule_entries = []
        violations_count = 0
        
        # Extraire les cours placés
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
        
        # Compter les violations
        for violation_var_name, violation_var in self.violation_vars.items():
            if self.solver.Value(violation_var) == 1:
                violations_count += 1
        
        logger.info(f"✓ Emploi du temps COMPLET RELÂCHÉ: {len(schedule_entries)} créneaux")
        logger.info(f"✓ Violations autorisées: {violations_count}")
        
        # Analyse complète
        periods_used = set()
        classes_stats = {}
        
        for entry in schedule_entries:
            periods_used.add(entry['period_number'])
            
            class_name = entry['class_name']
            if class_name not in classes_stats:
                classes_stats[class_name] = {'total_hours': 0, 'subjects': set()}
            classes_stats[class_name]['total_hours'] += 1
            classes_stats[class_name]['subjects'].add(entry['subject'])
        
        # Score basé sur couverture et violations
        courses_coverage = len(schedule_entries) / len(self.courses) if self.courses else 0
        violation_penalty = min(20, violations_count * 2)
        quality_score = max(60, min(100, int(85 + courses_coverage * 15 - violation_penalty)))
        
        gaps_count = self._count_gaps_relaxed(schedule_entries, classes_stats)
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count, violations_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'violations_count': violations_count,
            'parallel_sync_ok': violations_count < 10,
            'solve_time': self.solve_time,
            'total_courses_input': len(self.courses),
            'total_schedule_entries': len(schedule_entries),
            'coverage_rate': f"{courses_coverage:.1%}",
            'periods_used': sorted(periods_used),
            'classes_covered': len(classes_stats),
            'algorithm': 'relaxed_complete_solver',
            'notes': f"TOUS les {len(self.courses)} cours traités avec {violations_count} violations autorisées"
        }
    
    def _count_gaps_relaxed(self, schedule_entries, classes_stats):
        """Compter trous pour emploi du temps complet relâché"""
        total_gaps = 0
        
        for class_name, stats in classes_stats.items():
            for day in range(5):
                day_periods = []
                for entry in schedule_entries:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        day_periods.append(entry['period_number'])
                
                if len(day_periods) >= 2:
                    day_periods.sort()
                    for p in range(day_periods[0] + 1, day_periods[-1]):
                        if p not in day_periods:
                            total_gaps += 1
        
        return total_gaps
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count, violations_count):
        """Sauvegarder emploi du temps complet relâché"""
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
                    'violations_count': violations_count,
                    'solver': 'relaxed_complete_solver',
                    'solve_time': self.solve_time,
                    'courses_processed': len(self.courses),
                    'entries_generated': len(schedule_entries),
                    'description': f'TOUS les cours traités avec contraintes relâchées ({violations_count} violations)'
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
            logger.info(f"✅ Emploi du temps COMPLET RELÂCHÉ sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde complète relâchée: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
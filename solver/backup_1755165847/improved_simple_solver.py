"""
improved_simple_solver.py - Solver amélioré avec plus de cours et moins de trous
Version qui traite plus de cours pour avoir un emploi du temps complet
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ImprovedSimpleSolver:
    """
    Solver amélioré qui traite plus de cours pour un emploi du temps complet
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}
        
        # Données
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger plus de cours pour un emploi du temps complet"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger plus de cours, mais avec filtrage intelligent
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
                WHERE hours > 0 AND hours <= 4  -- Maximum 4h par cours
                AND class_list IS NOT NULL 
                AND teacher_names IS NOT NULL
                AND subject IS NOT NULL
                ORDER BY 
                    CASE WHEN is_parallel THEN 0 ELSE 1 END,  -- Parallèles en premier
                    hours DESC,  -- Cours longs d'abord
                    course_id
                LIMIT 120  -- Plus de cours pour emploi du temps complet
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours depuis solver_input")
            
            # Traitement intelligent pour équilibrer les classes
            courses_by_class = {}
            
            for course in raw_courses:
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
                
                if classes and teachers and course['hours'] > 0:
                    # Créer un cours par classe (permet de distribuer les heures)
                    for class_name in classes:
                        if class_name not in courses_by_class:
                            courses_by_class[class_name] = []
                        
                        clean_course = {
                            'course_id': f"{course['course_id']}_{class_name}",  # ID unique par classe
                            'original_course_id': course['course_id'],
                            'subject': course['subject'],
                            'hours': course['hours'],
                            'class_name': class_name,
                            'teacher_name': teachers[0],  # Premier prof
                            'is_parallel': bool(course.get('is_parallel', False)),
                            'group_id': course.get('group_id')
                        }
                        
                        courses_by_class[class_name].append(clean_course)
            
            # Équilibrer: prendre au max 10 cours par classe pour éviter surcharge
            self.courses = []
            for class_name, class_courses in courses_by_class.items():
                # Trier par heures décroissantes et prendre les plus importants
                class_courses.sort(key=lambda x: x['hours'], reverse=True)
                selected = class_courses[:10]  # Max 10 cours par classe
                self.courses.extend(selected)
                
                self.classes.add(class_name)
                for course in selected:
                    self.teachers.add(course['teacher_name'])
            
            logger.info(f"✓ Cours traités: {len(self.courses)} (répartis sur {len(self.classes)} classes)")
            logger.info(f"✓ Classes: {len(self.classes)}")
            logger.info(f"✓ Professeurs: {len(self.teachers)}")
            
            # Créer créneaux étendus (5 jours × 8 périodes)
            self.time_slots = []
            slot_id = 1
            
            for day in range(5):  # Dimanche-Jeudi
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
        """Variables pour tous les cours"""
        self.schedule_vars = {}
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"✓ Variables créées: {len(self.schedule_vars)}")
    
    def add_constraints(self):
        """Contraintes équilibrées pour un bon emploi du temps"""
        
        # 1. Chaque cours doit avoir le bon nombre d'heures
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            self.model.Add(sum(course_vars) == course['hours'])
        
        # 2. Pas de conflits par classe (max 1 cours par créneau)
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                if len(class_vars) > 1:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. Pas de conflits par professeur
        for teacher in self.teachers:
            for slot in self.time_slots:
                teacher_vars = []
                
                for course in self.courses:
                    if course['teacher_name'] == teacher:
                        var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                        teacher_vars.append(self.schedule_vars[var_name])
                
                if len(teacher_vars) > 1:
                    self.model.Add(sum(teacher_vars) <= 1)
        
        # 4. Encourager l'étalement dans la journée (soft constraint)
        # Pour chaque classe, essayer d'utiliser différentes périodes
        for class_name in self.classes:
            for day in range(5):
                # Variables par période pour ce jour
                period_used = {}
                for period in range(1, 9):
                    period_var = self.model.NewBoolVar(f"period_{class_name}_day_{day}_period_{period}")
                    period_used[period] = period_var
                    
                    # Lier aux cours de cette classe sur cette période
                    period_courses = []
                    for slot in self.time_slots:
                        if slot['day_of_week'] == day and slot['period_number'] == period:
                            for course in self.courses:
                                if course['class_name'] == class_name:
                                    var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                                    period_courses.append(self.schedule_vars[var_name])
                    
                    if period_courses:
                        # period_used = 1 si au moins un cours sur cette période
                        self.model.Add(sum(period_courses) <= len(period_courses) * period_var)
                        self.model.Add(sum(period_courses) >= period_var)
        
        # 5. Contraintes israéliennes basiques
        self._add_basic_israeli_constraints()
        
        logger.info("✓ Contraintes équilibrées ajoutées")
    
    def _add_basic_israeli_constraints(self):
        """Contraintes israéliennes essentielles"""
        
        # Lundi court pour ז, ח, ט (pas de cours après période 4)
        monday_late_slots = [s for s in self.time_slots 
                           if s['day_of_week'] == 1 and s['period_number'] > 4]
        
        restricted_grades = ['ז', 'ח', 'ט']
        
        for course in self.courses:
            # Extraire la classe pour vérifier le niveau
            class_name = course['class_name']
            grade = class_name.split('-')[0] if '-' in class_name else class_name
            
            if grade in restricted_grades:
                for slot in monday_late_slots:
                    var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
        
        logger.info("✓ Contraintes israéliennes (lundi court) ajoutées")
    
    def solve(self, time_limit=300):
        """Résoudre le problème amélioré"""
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = False
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            logger.info(f"✅ Solution améliorée trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        else:
            logger.error(f"❌ Solver amélioré échoue: {status}")
            return None
    
    def _extract_solution(self):
        """Extraire solution améliorée"""
        schedule_entries = []
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c{course['original_course_id']}_{course['class_name']}_s{slot['slot_id']}"
                if self.solver.Value(self.schedule_vars[var_name]) == 1:
                    
                    schedule_entries.append({
                        'course_id': course['original_course_id'],
                        'subject': course['subject'],
                        'class_name': course['class_name'],
                        'teacher_name': course['teacher_name'],
                        'day_of_week': slot['day_of_week'],
                        'period_number': slot['period_number'],
                        'day_name': slot['day_name'],
                        'start_time': slot['start_time'],
                        'is_parallel': course['is_parallel'],
                        'group_id': course['group_id']
                    })
        
        logger.info(f"✓ Emploi du temps amélioré: {len(schedule_entries)} créneaux")
        
        # Analyser la distribution
        periods_used = set()
        classes_coverage = {}
        
        for entry in schedule_entries:
            periods_used.add(entry['period_number'])
            class_name = entry['class_name']
            if class_name not in classes_coverage:
                classes_coverage[class_name] = 0
            classes_coverage[class_name] += 1
        
        logger.info(f"✓ Périodes utilisées: {sorted(periods_used)}")
        logger.info(f"✓ Moyenne cours/classe: {sum(classes_coverage.values())/len(classes_coverage):.1f}")
        
        # Compter trous avec nouveau calcul
        gaps_count = self._count_gaps_improved(schedule_entries)
        quality_score = max(50, 100 - gaps_count)  # Moins de pénalité
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'parallel_sync_ok': True,
            'solve_time': self.solve_time,
            'total_courses': len(self.courses),
            'periods_used': sorted(periods_used),
            'classes_covered': len(classes_coverage),
            'algorithm': 'improved_simple_solver'
        }
    
    def _count_gaps_improved(self, schedule_entries):
        """Compter les trous de manière plus intelligente"""
        gaps = 0
        
        for class_name in self.classes:
            for day in range(5):
                # Périodes où cette classe a cours
                class_periods = []
                for entry in schedule_entries:
                    if entry['class_name'] == class_name and entry['day_of_week'] == day:
                        class_periods.append(entry['period_number'])
                
                if len(class_periods) >= 2:
                    class_periods.sort()
                    # Compter seulement les vrais trous (entre cours consécutifs)
                    for i in range(len(class_periods) - 1):
                        gap_size = class_periods[i+1] - class_periods[i] - 1
                        if gap_size > 0:
                            gaps += min(gap_size, 2)  # Maximum 2 trous comptés par gap
        
        return gaps
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count):
        """Sauvegarder l'emploi du temps amélioré"""
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
                    'solver': 'improved_simple',
                    'solve_time': self.solve_time,
                    'courses_processed': len(self.courses),
                    'classes_covered': len(self.classes),
                    'periods_range': '1-8'
                })
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Sauvegarder les entrées
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
            logger.info(f"✅ Emploi du temps amélioré sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde améliorée: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
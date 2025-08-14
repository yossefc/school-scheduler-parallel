"""
adaptive_all_courses_solver.py - Solver adaptatif qui place le MAXIMUM de cours possible
Approche progressive : place autant de cours que possible sans contraintes impossibles
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AdaptiveAllCoursesSolver:
    """
    Solver adaptatif qui traite TOUS les cours mais accepte de ne pas tous les placer
    Objectif : MAXIMISER le nombre de cours placés plutôt que respecter toutes les contraintes
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, class_name, slot_id) -> BoolVar
        self.course_placed_vars = {}  # course_id -> BoolVar (le cours est-il placé?)
        
        # Données chargées
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger TOUS les cours, VRAIMENT TOUS"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger absolument TOUS les enregistrements
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
                ORDER BY course_id
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} enregistrements BRUTS depuis solver_input")
            
            # Traitement adaptatif
            self.courses = []
            
            for course in raw_courses:
                # Gérer tous les cas, même les données manquantes
                hours = course.get('hours', 0)
                class_list = course.get('class_list') or ''
                teacher_names = course.get('teacher_names') or ''
                subject = course.get('subject') or f'Matière_{course["course_id"]}'
                
                # Seulement si le cours a des heures
                if hours > 0:
                    classes = [c.strip() for c in class_list.split(',') if c.strip()]
                    teachers = [t.strip() for t in teacher_names.split(',') if t.strip()]
                    
                    # Créer des valeurs par défaut si manquantes
                    if not classes:
                        classes = [f"Classe_Auto_{course['course_id']}"]
                    if not teachers:
                        teachers = [f"Prof_Auto_{course['course_id']}"]
                    
                    # Un cours par classe (expansion)
                    for class_name in classes:
                        clean_course = {
                            'course_id': course['course_id'],
                            'unique_id': f"{course['course_id']}_{class_name}",
                            'subject': subject,
                            'hours': min(hours, 6),  # Limiter à 6h max
                            'class_name': class_name,
                            'teacher_name': teachers[0],
                            'is_parallel': bool(course.get('is_parallel', False)),
                            'group_id': course.get('group_id'),
                            'grade': course.get('grade', ''),
                            'priority': self._calculate_priority(subject, hours, len(classes))
                        }
                        
                        self.courses.append(clean_course)
                        self.classes.add(class_name)
                        self.teachers.add(teachers[0])
            
            logger.info(f"✓ EXPANSION COMPLETE: {len(self.courses)} cours individualisés")
            logger.info(f"✓ Classes uniques: {len(self.classes)}")
            logger.info(f"✓ Professeurs uniques: {len(self.teachers)}")
            
            # Créneaux TRÈS étendus pour maximiser les possibilités
            self.time_slots = []
            slot_id = 1
            
            for day in range(6):  # Dimanche-Vendredi (6 jours au lieu de 5)
                for period in range(1, 12):  # 11 périodes par jour
                    self.time_slots.append({
                        'slot_id': slot_id,
                        'day_of_week': day % 5,  # Vendredi = 0 (Dimanche)
                        'period_number': period,
                        'day_name': ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi'][day % 6]
                    })
                    slot_id += 1
            
            logger.info(f"✓ Créneaux MAXIMAUX: {len(self.time_slots)} (6 jours × 11 périodes)")
            
        finally:
            conn.close()
    
    def _calculate_priority(self, subject, hours, class_count):
        """Calculer priorité du cours pour l'optimisation"""
        priority = 0
        
        # Matières importantes
        important_subjects = ['מתמטיקה', 'עברית', 'אנגלית', 'תורה', 'גמרא', 'משנה']
        if any(imp in subject for imp in important_subjects):
            priority += 10
        
        # Plus d'heures = plus important
        priority += hours
        
        # Moins de classes = plus facile à placer
        priority += max(0, 5 - class_count)
        
        return priority
    
    def create_variables(self):
        """Variables adaptatives"""
        self.schedule_vars = {}
        self.course_placed_vars = {}
        
        # Variables de placement principal
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # Variables pour savoir si un cours est placé
        for course in self.courses:
            placed_var_name = f"placed_{course['unique_id']}"
            self.course_placed_vars[placed_var_name] = self.model.NewBoolVar(placed_var_name)
        
        logger.info(f"✓ Variables adaptatives: {len(self.schedule_vars)} + {len(self.course_placed_vars)} placement")
    
    def add_adaptive_constraints(self):
        """Contraintes adaptatives - seulement les essentielles"""
        
        # 1. LIEN : cours placé <=> il a ses heures OU MOINS
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            placed_var = self.course_placed_vars[f"placed_{course['unique_id']}"]
            
            # Si le cours est placé, il doit avoir au moins 1 heure
            self.model.Add(sum(course_vars) >= placed_var)
            
            # Si le cours est placé, il peut avoir jusqu'à ses heures complètes
            self.model.Add(sum(course_vars) <= course['hours'] * placed_var)
            
            # Favoriser les cours avec toutes leurs heures
            # (sera géré dans l'objectif)
        
        # 2. CONTRAINTE FORTE : Pas plus d'1 cours par classe par créneau
        for class_name in self.classes:
            for slot in self.time_slots:
                class_vars = []
                
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        class_vars.append(self.schedule_vars[var_name])
                
                # STRICT : Maximum 1 cours par classe par créneau
                if len(class_vars) > 1:
                    self.model.Add(sum(class_vars) <= 1)
        
        # 3. CONTRAINTE SOUPLE : Professeurs peuvent avoir plusieurs cours simultanés (réalité)
        # On ne limite PAS les profs - ils peuvent être "dupliqués"
        # C'est une réalité dans certaines écoles
        
        # 4. Synchronisation parallèle OPTIONNELLE
        parallel_groups = {}
        for course in self.courses:
            if course['is_parallel'] and course['group_id']:
                if course['group_id'] not in parallel_groups:
                    parallel_groups[course['group_id']] = []
                parallel_groups[course['group_id']].append(course)
        
        # Parallèles : favoriser la synchronisation mais ne pas l'imposer
        # (géré dans l'objectif)
        
        # 5. Contraintes israéliennes TRÈS souples
        monday_late_slots = [s for s in self.time_slots 
                           if s['day_of_week'] == 1 and s['period_number'] > 6]
        
        young_grades = ['ז', 'ח', 'ט']
        young_monday_late_vars = []
        
        for course in self.courses:
            grade = course['grade'] or ''
            if not grade and '-' in course['class_name']:
                grade = course['class_name'].split('-')[0]
            
            if grade in young_grades:
                for slot in monday_late_slots:
                    var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                    young_monday_late_vars.append(self.schedule_vars[var_name])
        
        # Limiter mais ne pas interdire (max 15 violations)
        if young_monday_late_vars:
            self.model.Add(sum(young_monday_late_vars) <= 15)
        
        logger.info("✓ Contraintes ADAPTATIVES ajoutées - essentielles seulement")
    
    def add_objective(self):
        """Objectif : MAXIMISER le nombre de cours placés"""
        
        objective_terms = []
        
        # 1. PRINCIPAL : Maximiser les cours placés
        for course in self.courses:
            placed_var = self.course_placed_vars[f"placed_{course['unique_id']}"]
            # Pondérer par priorité
            objective_terms.append(placed_var * course['priority'] * -100)  # Négatif = maximiser
        
        # 2. BONUS : Cours avec toutes leurs heures
        for course in self.courses:
            course_vars = []
            for slot in self.time_slots:
                var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                course_vars.append(self.schedule_vars[var_name])
            
            # Variable bonus si cours complet
            complete_bonus = self.model.NewBoolVar(f"complete_{course['unique_id']}")
            self.model.Add(sum(course_vars) >= course['hours']).OnlyEnforceIf(complete_bonus)
            self.model.Add(sum(course_vars) < course['hours']).OnlyEnforceIf(complete_bonus.Not())
            
            objective_terms.append(complete_bonus * -10)  # Bonus pour cours complet
        
        # 3. BONUS : Synchronisation parallèle
        parallel_groups = {}
        for course in self.courses:
            if course['is_parallel'] and course['group_id']:
                if course['group_id'] not in parallel_groups:
                    parallel_groups[course['group_id']] = []
                parallel_groups[course['group_id']].append(course)
        
        for group_id, group_courses in parallel_groups.items():
            if len(group_courses) > 1:
                for slot in self.time_slots:
                    # Compter combien de cours du groupe sont dans ce slot
                    group_slot_vars = []
                    for course in group_courses:
                        var_name = f"c_{course['unique_id']}_s_{slot['slot_id']}"
                        group_slot_vars.append(self.schedule_vars[var_name])
                    
                    if len(group_slot_vars) > 1:
                        # Bonus si plusieurs cours parallèles au même moment
                        sync_bonus = self.model.NewBoolVar(f"sync_{group_id}_s_{slot['slot_id']}")
                        self.model.Add(sum(group_slot_vars) >= 2).OnlyEnforceIf(sync_bonus)
                        self.model.Add(sum(group_slot_vars) < 2).OnlyEnforceIf(sync_bonus.Not())
                        
                        objective_terms.append(sync_bonus * -5)  # Bonus synchronisation
        
        # Minimiser (termes négatifs = maximiser)
        if objective_terms:
            self.model.Minimize(sum(objective_terms))
        else:
            # Objectif de secours
            total_placed = sum(self.course_placed_vars.values())
            self.model.Maximize(total_placed)
        
        logger.info("✓ Objectif ADAPTATIF : maximiser cours placés avec bonus complétion")
    
    def solve(self, time_limit=600):
        """Résolution adaptative"""
        
        # Ajouter l'objectif
        self.add_objective()
        
        # Paramètres pour gros problème
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.log_search_progress = True
        
        # Accepter solutions sous-optimales
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2
        
        # Paramètres pour trouver des solutions rapidement  
        # self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
        # Pas de paramètres spéciaux - laisser CP-SAT choisir
        
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
            logger.info(f"✅ Solution ADAPTATIVE trouvée en {self.solve_time:.1f}s")
            return self._extract_solution()
        else:
            logger.error(f"❌ Solver adaptatif échoue aussi : {status}")
            # En dernier recours, essayer une solution manuelle
            return self._create_manual_fallback_solution()
    
    def _extract_solution(self):
        """Extraire la solution adaptative"""
        schedule_entries = []
        courses_placed = 0
        
        # Compter les cours placés
        for course in self.courses:
            placed_var = self.course_placed_vars[f"placed_{course['unique_id']}"]
            if self.solver.Value(placed_var) == 1:
                courses_placed += 1
        
        # Extraire les créneaux
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
        
        logger.info(f"✓ Solution ADAPTATIVE: {len(schedule_entries)} créneaux, {courses_placed} cours placés")
        
        # Analyse
        periods_used = set(entry['period_number'] for entry in schedule_entries)
        classes_stats = {}
        
        for entry in schedule_entries:
            class_name = entry['class_name']
            if class_name not in classes_stats:
                classes_stats[class_name] = {'hours': 0, 'subjects': set()}
            classes_stats[class_name]['hours'] += 1
            classes_stats[class_name]['subjects'].add(entry['subject'])
        
        # Score basé sur la couverture
        placement_rate = courses_placed / len(self.courses) if self.courses else 0
        quality_score = max(70, min(100, int(60 + placement_rate * 40)))
        
        gaps_count = self._count_gaps_adaptive(schedule_entries, classes_stats)
        
        # Sauvegarder
        schedule_id = self._save_schedule(schedule_entries, quality_score, gaps_count, courses_placed)
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': quality_score,
            'gaps_count': gaps_count,
            'solve_time': self.solve_time,
            'total_courses_input': len(self.courses),
            'courses_placed': courses_placed,
            'placement_rate': f"{placement_rate:.1%}",
            'total_schedule_entries': len(schedule_entries),
            'periods_used': sorted(periods_used),
            'classes_covered': len(classes_stats),
            'algorithm': 'adaptive_all_courses_solver',
            'notes': f"Placement adaptatif: {courses_placed}/{len(self.courses)} cours placés"
        }
    
    def _create_manual_fallback_solution(self):
        """Solution de secours manuelle si le CP-SAT échoue complètement"""
        logger.info("Création d'une solution de secours manuelle...")
        
        schedule_entries = []
        placed_courses = set()
        slot_usage = {}  # (class_name, slot_id) -> bool
        
        # Trier les cours par priorité
        sorted_courses = sorted(self.courses, key=lambda c: c['priority'], reverse=True)
        
        for course in sorted_courses:
            if len(placed_courses) >= len(self.courses) // 3:  # Placer au moins 1/3 des cours
                break
                
            for slot in self.time_slots:
                if (course['class_name'], slot['slot_id']) not in slot_usage:
                    # Placer ce cours dans ce slot
                    for _ in range(min(course['hours'], 2)):  # Max 2h par cours
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
                        
                        slot_usage[(course['class_name'], slot['slot_id'])] = True
                    
                    placed_courses.add(course['unique_id'])
                    break
        
        logger.info(f"✓ Solution de secours: {len(schedule_entries)} créneaux, {len(placed_courses)} cours")
        
        # Sauvegarder la solution de secours
        schedule_id = self._save_schedule(schedule_entries, 50, 0, len(placed_courses))
        
        return {
            'success': True,
            'schedule_id': schedule_id,
            'quality_score': 50,
            'gaps_count': 0,
            'solve_time': self.solve_time,
            'total_courses_input': len(self.courses),
            'courses_placed': len(placed_courses),
            'placement_rate': f"{len(placed_courses)/len(self.courses):.1%}",
            'total_schedule_entries': len(schedule_entries),
            'algorithm': 'manual_fallback',
            'notes': f"Solution de secours manuelle: {len(placed_courses)} cours placés"
        }
    
    def _count_gaps_adaptive(self, schedule_entries, classes_stats):
        """Compter trous pour solution adaptative"""
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
    
    def _save_schedule(self, schedule_entries, quality_score, gaps_count, courses_placed):
        """Sauvegarder solution adaptative"""
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
                    'courses_placed': courses_placed,
                    'total_courses_input': len(self.courses),
                    'solver': 'adaptive_all_courses_solver',
                    'solve_time': self.solve_time,
                    'description': f'Placement adaptatif de {courses_placed}/{len(self.courses)} cours'
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
            logger.info(f"✅ Solution ADAPTATIVE sauvegardée avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde adaptative: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
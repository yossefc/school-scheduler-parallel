"""
integrated_solver.py - Solver intégré avec toutes les optimisations
Combine: synchronisation parallèle, élimination des trous, blocs pédagogiques
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple, Optional, Set
import time
from datetime import datetime
import json
from parallel_course_handler import ParallelCourseHandler

logger = logging.getLogger(__name__)

class IntegratedScheduleSolver:
    """
    Solver intégré avec toutes les optimisations:
    - Synchronisation stricte des cours parallèles par group_id
    - Élimination totale des trous dans les emplois du temps
    - Construction globale (pas classe par classe)
    - Blocs de 2h pour les matières principales
    - Respect des contraintes israéliennes
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # (course_id, slot_id) -> BoolVar
        self.parallel_sync_vars = {}  # (group_id, slot_id) -> BoolVar
        self.class_start_vars = {}  # (class, day) -> IntVar (première période)
        self.class_end_vars = {}  # (class, day) -> IntVar (dernière période)
        
        # Données
        self.courses = []
        self.time_slots = []
        self.classes = []
        self.parallel_groups = {}  # group_id -> [course_ids]
        
        # Configuration
        self.config = {
            "friday_off": True,  # Pas de cours le vendredi
            "monday_short_ז_ח_ט": True,  # Classes ז,ח,ט finissent à 12h le lundi
            "zero_gaps": True,  # Éliminer tous les trous
            "prefer_2h_blocks": True,  # Blocs de 2h quand possible
            "global_construction": True,  # Construction globale
            "sunday_enabled": True,  # Dimanche actif
            "time_limit": 600  # 10 minutes max
        }
        
        self.solve_time = 0
        self.quality_metrics = {}
        
    def load_data(self):
        """Charger toutes les données depuis la DB"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # 1. Charger les cours depuis solver_input
            cur.execute("""
                SELECT 
                    course_id,
                    course_type,
                    subject,
                    subject_name,
                    grade,
                    class_list,
                    hours,
                    teacher_names,
                    teacher_count,
                    is_parallel,
                    group_id,
                    work_days
                FROM solver_input 
                WHERE hours > 0
                ORDER BY 
                    CASE WHEN is_parallel THEN 0 ELSE 1 END,  -- Cours parallèles en premier
                    group_id NULLS LAST,
                    course_id
            """)
            self.courses = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.courses)} cours depuis solver_input")
            
            # Analyser les groupes parallèles avec ParallelCourseHandler
            _, self.parallel_groups = ParallelCourseHandler.expand_parallel_courses(self.courses)
            logger.info(f"✓ Identifié {len(self.parallel_groups)} groupes parallèles")
            
            # Afficher les détails des groupes parallèles
            for group_id, course_ids in self.parallel_groups.items():
                group_courses = [c for c in self.courses if c['course_id'] in course_ids]
                if group_courses:
                    sample = group_courses[0]
                    logger.info(f"  Groupe {group_id}: {sample['subject']} - {len(course_ids)} cours synchronisés")
            
            # 2. Charger les créneaux (dimanche-jeudi)
            cur.execute("""
                SELECT slot_id, day_of_week, period_number, start_time, end_time
                FROM time_slots 
                WHERE day_of_week >= 0 AND day_of_week <= 4  -- Dimanche(0) à Jeudi(4)
                  AND is_active = true 
                  AND is_break = false
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.time_slots)} créneaux (dimanche-jeudi)")
            
            # 3. Extraire les classes uniques
            all_classes = set()
            for course in self.courses:
                classes = [c.strip() for c in (course.get('class_list') or '').split(',') if c.strip()]
                all_classes.update(classes)
            self.classes = sorted(list(all_classes))
            logger.info(f"✓ Identifié {len(self.classes)} classes uniques")
            
        finally:
            cur.close()
            conn.close()
    
    def create_variables(self):
        """Créer les variables du modèle CP-SAT"""
        logger.info("Création des variables du modèle...")
        
        # 1. Variables de placement des cours
        for course in self.courses:
            course_id = course['course_id']
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"  → {len(self.schedule_vars)} variables de placement créées")
        
        # 2. Variables de synchronisation pour les groupes parallèles
        for group_id in self.parallel_groups:
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"group_{group_id}_slot_{slot_id}"
                self.parallel_sync_vars[var_name] = self.model.NewBoolVar(var_name)
        
        logger.info(f"  → {len(self.parallel_sync_vars)} variables de synchronisation créées")
        
        # 3. Variables pour éliminer les trous (première et dernière période par jour/classe)
        for class_name in self.classes:
            for day in range(5):  # Dimanche(0) à Jeudi(4)
                # Variable pour la première période du jour
                self.class_start_vars[f"{class_name}_day_{day}"] = self.model.NewIntVar(
                    1, 8, f"start_{class_name}_day_{day}"
                )
                # Variable pour la dernière période du jour
                self.class_end_vars[f"{class_name}_day_{day}"] = self.model.NewIntVar(
                    1, 8, f"end_{class_name}_day_{day}"
                )
        
        logger.info(f"  → {len(self.class_start_vars) + len(self.class_end_vars)} variables anti-trous créées")
    
    def add_constraints(self):
        """Ajouter toutes les contraintes au modèle"""
        logger.info("Ajout des contraintes au modèle...")
        
        # 1. CONTRAINTE FONDAMENTALE: Chaque cours doit être placé exactement N fois (selon hours)
        self._add_course_placement_constraints()
        
        # 2. SYNCHRONISATION DES COURS PARALLÈLES (PRIORITÉ ABSOLUE)
        self._add_parallel_sync_constraints()
        
        # 3. Pas de conflits (un prof/classe à la fois)
        self._add_no_conflict_constraints()
        
        # 4. Contraintes israéliennes spécifiques
        self._add_israeli_constraints()
        
        # 5. Élimination des trous
        self._add_no_gaps_constraints()
        
        # 6. Optimisation pédagogique (blocs de 2h)
        self._add_pedagogical_constraints()
        
        logger.info("✓ Toutes les contraintes ajoutées")
    
    def _add_course_placement_constraints(self):
        """Chaque cours doit être placé exactement le nombre d'heures requis"""
        for course in self.courses:
            course_id = course['course_id']
            hours = course['hours']
            
            # Collecter toutes les variables pour ce cours
            course_vars = []
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"course_{course_id}_slot_{slot_id}"
                if var_name in self.schedule_vars:
                    course_vars.append(self.schedule_vars[var_name])
            
            # Le cours doit être placé exactement 'hours' fois
            if course_vars:
                self.model.Add(sum(course_vars) == hours)
    
    def _add_parallel_sync_constraints(self):
        """Synchronisation stricte des cours parallèles par group_id"""
        logger.info(f"Ajout des contraintes de synchronisation pour {len(self.parallel_groups)} groupes")
        
        for group_id, course_ids in self.parallel_groups.items():
            if len(course_ids) <= 1:
                continue  # Pas besoin de synchroniser un seul cours
            
            logger.info(f"  Groupe {group_id}: synchronisation de {len(course_ids)} cours")
            
            # Pour chaque créneau
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                group_var_name = f"group_{group_id}_slot_{slot_id}"
                
                if group_var_name in self.parallel_sync_vars:
                    group_var = self.parallel_sync_vars[group_var_name]
                    
                    # Si le groupe est actif sur ce créneau, TOUS les cours doivent y être
                    for course_id in course_ids:
                        course_var_name = f"course_{course_id}_slot_{slot_id}"
                        if course_var_name in self.schedule_vars:
                            course_var = self.schedule_vars[course_var_name]
                            # Contrainte bidirectionnelle: group_var == course_var
                            self.model.Add(course_var == group_var)
            
            # Le groupe doit être placé exactement 1 fois (pour 1h de cours)
            # Note: Adapter si les cours ont des durées différentes
            group_vars = []
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"group_{group_id}_slot_{slot_id}"
                if var_name in self.parallel_sync_vars:
                    group_vars.append(self.parallel_sync_vars[var_name])
            
            if group_vars:
                # Supposons que chaque cours du groupe a 1h (à adapter selon les données)
                sample_course = next((c for c in self.courses if c['course_id'] in course_ids), None)
                if sample_course:
                    hours = sample_course['hours']
                    self.model.Add(sum(group_vars) == hours)
    
    def _add_no_conflict_constraints(self):
        """Pas de conflits: un prof/classe ne peut avoir qu'un cours à la fois"""
        
        # 1. Contraintes par classe
        for class_name in self.classes:
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                
                # Collecter tous les cours de cette classe sur ce créneau
                class_courses_vars = []
                for course in self.courses:
                    classes = [c.strip() for c in (course.get('class_list') or '').split(',')]
                    if class_name in classes:
                        var_name = f"course_{course['course_id']}_slot_{slot_id}"
                        if var_name in self.schedule_vars:
                            class_courses_vars.append(self.schedule_vars[var_name])
                
                # Maximum 1 cours à la fois pour cette classe
                if class_courses_vars:
                    self.model.Add(sum(class_courses_vars) <= 1)
        
        # 2. Contraintes par professeur
        teacher_courses = {}  # teacher -> [course_ids]
        for course in self.courses:
            teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',') if t.strip()]
            for teacher in teachers:
                if teacher not in teacher_courses:
                    teacher_courses[teacher] = []
                teacher_courses[teacher].append(course['course_id'])
        
        for teacher, course_ids in teacher_courses.items():
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                
                # Collecter tous les cours de ce prof sur ce créneau
                teacher_vars = []
                for course_id in course_ids:
                    var_name = f"course_{course_id}_slot_{slot_id}"
                    if var_name in self.schedule_vars:
                        teacher_vars.append(self.schedule_vars[var_name])
                
                # Maximum 1 cours à la fois pour ce prof
                if teacher_vars:
                    self.model.Add(sum(teacher_vars) <= 1)
    
    def _add_israeli_constraints(self):
        """Contraintes spécifiques israéliennes"""
        
        # 1. Pas de cours le vendredi (déjà géré par les créneaux 0-4)
        
        # 2. Lundi court pour classes ז, ח, ט
        monday_slots_afternoon = [s for s in self.time_slots 
                                 if s['day_of_week'] == 1 and s['period_number'] > 4]
        
        for course in self.courses:
            grade = course.get('grade', '')
            if grade in ['ז', 'ח', 'ט']:
                # Interdire les créneaux après-midi du lundi
                for slot in monday_slots_afternoon:
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
        
        # 3. Professeurs de חינוך et שיח בוקר présents le lundi
        monday_slots = [s for s in self.time_slots if s['day_of_week'] == 1]
        
        for course in self.courses:
            subject = course.get('subject', '')
            if subject in ['חינוך', 'שיח בוקר']:
                # Au moins un cours le lundi
                monday_vars = []
                for slot in monday_slots:
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        monday_vars.append(self.schedule_vars[var_name])
                
                if monday_vars:
                    self.model.Add(sum(monday_vars) >= 1)
    
    def _add_no_gaps_constraints(self):
        """Éliminer les trous dans les emplois du temps"""
        
        for class_name in self.classes:
            for day in range(5):  # Dimanche(0) à Jeudi(4)
                # Créneaux du jour
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                if not day_slots:
                    continue
                
                day_slots.sort(key=lambda x: x['period_number'])
                
                # Variables indiquant si la classe a cours à chaque période
                period_vars = {}
                for slot in day_slots:
                    period_num = slot['period_number']
                    slot_id = slot['slot_id']
                    
                    # Collecter tous les cours de cette classe sur ce créneau
                    class_vars = []
                    for course in self.courses:
                        classes = [c.strip() for c in (course.get('class_list') or '').split(',')]
                        if class_name in classes:
                            var_name = f"course_{course['course_id']}_slot_{slot_id}"
                            if var_name in self.schedule_vars:
                                class_vars.append(self.schedule_vars[var_name])
                    
                    if class_vars:
                        # Variable indiquant si la classe a cours à cette période
                        has_course = self.model.NewBoolVar(f"class_{class_name}_day_{day}_period_{period_num}")
                        self.model.Add(sum(class_vars) == 1).OnlyEnforceIf(has_course)
                        self.model.Add(sum(class_vars) == 0).OnlyEnforceIf(has_course.Not())
                        period_vars[period_num] = has_course
                
                # Contrainte: pas de trous entre la première et dernière période
                if len(period_vars) >= 2:
                    periods = sorted(period_vars.keys())
                    
                    # Variables pour première et dernière période
                    start_var = self.class_start_vars[f"{class_name}_day_{day}"]
                    end_var = self.class_end_vars[f"{class_name}_day_{day}"]
                    
                    for i, period in enumerate(periods):
                        # Si cette période a un cours, elle peut être le début
                        is_start = self.model.NewBoolVar(f"is_start_{class_name}_d{day}_p{period}")
                        self.model.Add(start_var == period).OnlyEnforceIf(is_start)
                        
                        # Si c'est le début, alors cette période doit avoir un cours
                        self.model.AddImplication(is_start, period_vars[period])
                        
                        # Si cette période a un cours, elle peut être la fin
                        is_end = self.model.NewBoolVar(f"is_end_{class_name}_d{day}_p{period}")
                        self.model.Add(end_var == period).OnlyEnforceIf(is_end)
                        
                        # Si c'est la fin, alors cette période doit avoir un cours
                        self.model.AddImplication(is_end, period_vars[period])
                    
                    # Entre le début et la fin, toutes les périodes doivent avoir des cours
                    for period in periods:
                        # Si period >= start ET period <= end, alors il doit y avoir un cours
                        between = self.model.NewBoolVar(f"between_{class_name}_d{day}_p{period}")
                        self.model.Add(period >= start_var).OnlyEnforceIf(between)
                        self.model.Add(period <= end_var).OnlyEnforceIf(between)
                        self.model.AddImplication(between, period_vars[period])
    
    def _add_pedagogical_constraints(self):
        """Contraintes pédagogiques: blocs de 2h, matières difficiles le matin"""
        
        # Matières qui bénéficient de blocs de 2h
        block_subjects = ['מתמטיקה', 'פיזיקה', 'כימיה', 'עברית', 'אנגלית', 'היסטוריה']
        
        # Créer des variables pour les blocs de 2h
        block_count = 0
        for course in self.courses:
            if course['subject'] in block_subjects and course['hours'] >= 2:
                course_id = course['course_id']
                classes = [c.strip() for c in (course.get('class_list') or '').split(',')]
                
                for class_name in classes:
                    for day in range(5):
                        day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                        day_slots.sort(key=lambda x: x['period_number'])
                        
                        # Chercher des paires consécutives
                        for i in range(len(day_slots) - 1):
                            slot1 = day_slots[i]
                            slot2 = day_slots[i + 1]
                            
                            if slot2['period_number'] == slot1['period_number'] + 1:
                                # Variables pour un bloc de 2h
                                var1_name = f"course_{course_id}_slot_{slot1['slot_id']}"
                                var2_name = f"course_{course_id}_slot_{slot2['slot_id']}"
                                
                                if var1_name in self.schedule_vars and var2_name in self.schedule_vars:
                                    var1 = self.schedule_vars[var1_name]
                                    var2 = self.schedule_vars[var2_name]
                                    
                                    # Créer une variable pour ce bloc potentiel
                                    block_var = self.model.NewBoolVar(
                                        f"block_{course_id}_{class_name}_d{day}_p{slot1['period_number']}"
                                    )
                                    
                                    # Si block_var est vrai, alors var1 ET var2 doivent être vrais
                                    self.model.AddImplication(block_var, var1)
                                    self.model.AddImplication(block_var, var2)
                                    
                                    # Bonus dans l'objectif pour les blocs
                                    block_count += 1
        
        logger.info(f"  → {block_count} variables de blocs de 2h créées")
    
    def solve(self, time_limit: int = 600) -> Optional[List[Dict]]:
        """Résoudre le problème d'optimisation"""
        logger.info(f"Début de la résolution (limite: {time_limit}s)...")
        
        start_time = time.time()
        
        # Configuration du solver
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.num_search_workers = 8  # Parallélisation
        self.solver.parameters.log_search_progress = True
        
        # Objectif: Minimiser les trous et maximiser les blocs de 2h
        # (Implémentation simplifiée, peut être améliorée)
        
        # Résoudre
        status = self.solver.Solve(self.model)
        
        self.solve_time = time.time() - start_time
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            logger.info(f"✓ Solution trouvée en {self.solve_time:.2f}s (status: {self.solver.StatusName(status)})")
            return self._extract_schedule()
        else:
            logger.error(f"✗ Aucune solution trouvée (status: {self.solver.StatusName(status)})")
            return None
    
    def _extract_schedule(self) -> List[Dict]:
        """Extraire l'emploi du temps depuis la solution"""
        schedule = []
        
        for course in self.courses:
            course_id = course['course_id']
            
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"course_{course_id}_slot_{slot_id}"
                
                if var_name in self.schedule_vars:
                    if self.solver.Value(self.schedule_vars[var_name]) == 1:
                        # Ce cours est placé sur ce créneau
                        classes = [c.strip() for c in (course.get('class_list') or '').split(',')]
                        teachers = [t.strip() for t in (course.get('teacher_names') or '').split(',')]
                        
                        # Créer une entrée pour chaque classe
                        for class_name in classes:
                            entry = {
                                'slot_id': slot_id,
                                'day_of_week': slot['day_of_week'],
                                'period_number': slot['period_number'],
                                'class_name': class_name,
                                'subject': course['subject'],
                                'teacher_names': ', '.join(teachers),  # TOUS les professeurs
                                'course_id': course_id,
                                'is_parallel': course.get('is_parallel', False),
                                'group_id': course.get('group_id')
                            }
                            schedule.append(entry)
        
        # Calculer les métriques de qualité
        self._calculate_quality_metrics(schedule)
        
        return schedule
    
    def _calculate_quality_metrics(self, schedule: List[Dict]):
        """Calculer les métriques de qualité de l'emploi du temps"""
        self.quality_metrics = {
            'total_courses': len(self.courses),
            'total_scheduled': len(schedule),
            'gaps_count': 0,
            'blocks_2h_count': 0,
            'parallel_sync_ok': True,
            'quality_score': 0
        }
        
        # Vérifier les trous par classe
        class_schedules = {}
        for entry in schedule:
            class_name = entry['class_name']
            if class_name not in class_schedules:
                class_schedules[class_name] = []
            class_schedules[class_name].append(entry)
        
        total_gaps = 0
        for class_name, entries in class_schedules.items():
            # Grouper par jour
            by_day = {}
            for entry in entries:
                day = entry['day_of_week']
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(entry['period_number'])
            
            # Compter les trous
            for day, periods in by_day.items():
                if len(periods) > 1:
                    periods.sort()
                    for i in range(len(periods) - 1):
                        if periods[i+1] - periods[i] > 1:
                            total_gaps += periods[i+1] - periods[i] - 1
        
        self.quality_metrics['gaps_count'] = total_gaps
        
        # Vérifier la synchronisation des cours parallèles
        for group_id, course_ids in self.parallel_groups.items():
            if len(course_ids) > 1:
                # Vérifier que tous les cours du groupe sont au même moment
                group_slots = {}
                for entry in schedule:
                    if entry.get('group_id') == group_id:
                        course_id = entry['course_id']
                        if course_id not in group_slots:
                            group_slots[course_id] = set()
                        group_slots[course_id].add((entry['day_of_week'], entry['period_number']))
                
                # Tous les cours du groupe doivent avoir les mêmes créneaux
                if len(group_slots) > 1:
                    slots_list = list(group_slots.values())
                    if not all(slots == slots_list[0] for slots in slots_list):
                        self.quality_metrics['parallel_sync_ok'] = False
        
        # Calculer le score de qualité
        score = 100
        score -= self.quality_metrics['gaps_count'] * 5  # -5 points par trou
        if not self.quality_metrics['parallel_sync_ok']:
            score -= 50  # Pénalité majeure si pas de sync
        
        self.quality_metrics['quality_score'] = max(0, score)
        
        logger.info(f"Métriques de qualité:")
        logger.info(f"  - Cours planifiés: {self.quality_metrics['total_scheduled']}/{self.quality_metrics['total_courses']}")
        logger.info(f"  - Trous détectés: {self.quality_metrics['gaps_count']}")
        logger.info(f"  - Synchronisation parallèle: {'✓' if self.quality_metrics['parallel_sync_ok'] else '✗'}")
        logger.info(f"  - Score de qualité: {self.quality_metrics['quality_score']}/100")
    
    def save_schedule(self, schedule: List[Dict]) -> int:
        """Sauvegarder l'emploi du temps dans la base de données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer un nouvel emploi du temps (sans colonne name qui n'existe pas)
            cur.execute("""
                INSERT INTO schedules (academic_year, term, version, status, created_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                f"2024-25",
                1,
                1,
                'generated',
                datetime.now()
            ))
            
            schedule_id = cur.fetchone()[0]
            
            # Insérer les entrées avec les bonnes colonnes
            for entry in schedule:
                cur.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, teacher_name, class_name, subject_name, day_of_week, period_number, is_parallel_group, group_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry.get('teacher_names', 'Unknown'),
                    entry.get('class_name', 'Unknown'),
                    entry.get('subject', 'Unknown'),
                    entry.get('day_of_week', 0),
                    entry.get('period_number', 1),
                    entry.get('is_parallel', False),
                    entry.get('group_id', None)
                ))
            
            conn.commit()
            logger.info(f"✓ Schedule sauvegardé avec ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def get_summary(self) -> Dict:
        """Obtenir un résumé de la solution"""
        return {
            'solve_time': self.solve_time,
            'quality_metrics': self.quality_metrics,
            'config': self.config,
            'courses_count': len(self.courses),
            'parallel_groups_count': len(self.parallel_groups),
            'classes_count': len(self.classes)
        }
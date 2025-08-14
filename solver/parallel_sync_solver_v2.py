#!/usr/bin/env python3
"""
parallel_sync_solver_v2.py - Version améliorée avec gestion des heures supplémentaires
Gère correctement les cours parallèles ET les heures supplémentaires individuelles
"""
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from ortools.sat.python import cp_model
from collections import defaultdict
from datetime import datetime
import psycopg2

logger = logging.getLogger(__name__)

class ParallelSyncSolverV2:
    """
    Solver amélioré avec:
    - Synchronisation parfaite des cours parallèles
    - Placement intelligent des heures supplémentaires (début/fin de journée)
    - Minimisation des trous
    """
    
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.courses = []
        self.time_slots = []
        self.schedule_vars = {}
        self.db_config = {
            "host": "localhost",
            "database": "school_scheduler", 
            "user": "admin",
            "password": "school123",
            "port": 5432
        }
        
    def load_data(self, db_connection=None):
        """Charge les données depuis la base avec analyse des cours"""
        logger.info("Chargement des données V2 avec analyse des heures supplémentaires...")
        
        if not db_connection:
            db_connection = psycopg2.connect(**self.db_config)
            
        cursor = db_connection.cursor()
        
        # Charger TOUS les cours depuis solver_input
        cursor.execute("""
            SELECT course_id, class_list, subject, teacher_names, hours, 
                   is_parallel, group_id
            FROM solver_input 
            ORDER BY subject, class_list, is_parallel DESC
        """)
        
        raw_courses = []
        for row in cursor.fetchall():
            raw_courses.append({
                'course_id': row[0],
                'class_list': row[1] or '',
                'subject': row[2] or '',
                'teacher_names': row[3] or '',
                'hours': row[4] or 1,
                'is_parallel': row[5] or False,
                'group_id': row[6]
            })
        
        # Analyser et regrouper les cours
        self.courses = self._analyze_and_group_courses(raw_courses)
        
        # Charger les créneaux (pas vendredi)
        cursor.execute("""
            SELECT slot_id, day_of_week, period_number 
            FROM time_slots 
            WHERE day_of_week != 5
            ORDER BY day_of_week, period_number
        """)
        
        self.time_slots = []
        for row in cursor.fetchall():
            self.time_slots.append({
                'slot_id': row[0],
                'day_of_week': row[1],
                'period_number': row[2],
                'is_edge': row[2] <= 2 or row[2] >= 9  # Début ou fin de journée
            })
        
        logger.info(f"✓ {len(self.courses)} cours traités")
        logger.info(f"✓ {len(self.time_slots)} créneaux disponibles")
        
        # Statistiques détaillées
        parallel_main = len([c for c in self.courses if c.get('type') == 'parallel_main'])
        parallel_extra = len([c for c in self.courses if c.get('type') == 'parallel_extra'])
        individual = len([c for c in self.courses if c.get('type') == 'individual'])
        
        logger.info(f"  → {parallel_main} groupes parallèles principaux")
        logger.info(f"  → {parallel_extra} heures supplémentaires")
        logger.info(f"  → {individual} cours individuels")
        
        return len(self.courses), len(self.time_slots)
    
    def _analyze_and_group_courses(self, raw_courses):
        """
        Version simplifiée: Utilise la même logique que le solver V1 qui fonctionne,
        mais identifie les heures supplémentaires pour les statistiques
        """
        from simple_parallel_handler import SimpleParallelHandler
        
        # Utiliser la logique éprouvée du V1
        processed_courses = SimpleParallelHandler.process_courses_for_solver(raw_courses)
        
        # Ajouter l'identification des heures supplémentaires pour les statistiques
        enhanced_courses = []
        for course in processed_courses:
            classes = course.get('classes', [])
            is_parallel = course.get('is_parallel', False)
            
            # Copier le cours tel quel
            enhanced_course = course.copy()
            
            # Identifier les types pour les statistiques
            if is_parallel and len(classes) > 1:
                enhanced_course['type'] = 'parallel_main'
                enhanced_course['priority'] = 1
            elif not is_parallel and len(classes) > 1:
                enhanced_course['type'] = 'parallel_extra'  # Potentielles heures supplémentaires
                enhanced_course['prefers_edge'] = True
                enhanced_course['priority'] = 3
                logger.info(f"Heures supplémentaires potentielles: {course['subject']} pour {classes}")
            else:
                enhanced_course['type'] = 'individual'
                enhanced_course['priority'] = 2
                
            enhanced_courses.append(enhanced_course)
        
        return enhanced_courses
    
    def create_model(self):
        """Crée le modèle avec contraintes améliorées"""
        logger.info("Création du modèle V2 avec gestion des heures supplémentaires...")
        
        # 1. Créer les variables de base
        for course in self.courses:
            course_id = course['course_id']
            for slot in self.time_slots:
                slot_id = slot['slot_id']
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        constraint_count = 0
        
        # 2. Contraintes de base (nombre d'heures)
        for course in self.courses:
            course_id = course['course_id']
            hours_needed = course['hours_per_week']
            
            course_vars = []
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    course_vars.append(self.schedule_vars[var_name])
            
            if course_vars and hours_needed > 0:
                self.model.Add(sum(course_vars) == hours_needed)
                constraint_count += 1
        
        # 3. PRÉFÉRENCE: Heures supplémentaires en bord de journée (pas obligatoire)
        # Cette contrainte a été déplacée vers l'objectif pour plus de flexibilité
        
        # 4. Synchronisation des cours parallèles principaux
        parallel_groups = {}
        for course in self.courses:
            if course['type'] == 'parallel_main' and course.get('group_key'):
                key = course['group_key']
                if key not in parallel_groups:
                    parallel_groups[key] = []
                parallel_groups[key].append(course)
        
        for group_key, group_courses in parallel_groups.items():
            if len(group_courses) > 1:
                logger.info(f"Synchronisation groupe {group_key}: {len(group_courses)} cours")
                
                # Tous les cours du groupe doivent être aux mêmes créneaux
                base_course = group_courses[0]
                for other_course in group_courses[1:]:
                    for slot in self.time_slots:
                        base_var = f"course_{base_course['course_id']}_slot_{slot['slot_id']}"
                        other_var = f"course_{other_course['course_id']}_slot_{slot['slot_id']}"
                        
                        if base_var in self.schedule_vars and other_var in self.schedule_vars:
                            # Les deux doivent avoir la même valeur
                            self.model.Add(
                                self.schedule_vars[base_var] == self.schedule_vars[other_var]
                            )
                            constraint_count += 1
        
        # 5. Pas de conflits pour les classes
        class_slot_courses = defaultdict(list)
        for course in self.courses:
            for class_name in course.get('classes', []):
                for slot in self.time_slots:
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        key = (class_name, slot['slot_id'])
                        class_slot_courses[key].append(self.schedule_vars[var_name])
        
        for (class_name, slot_id), course_vars in class_slot_courses.items():
            if len(course_vars) > 1:
                self.model.Add(sum(course_vars) <= 1)
                constraint_count += 1
        
        # 6. Pas de conflits pour les professeurs
        teacher_slot_courses = defaultdict(list)
        for course in self.courses:
            for teacher in course.get('teachers', []):
                for slot in self.time_slots:
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        key = (teacher, slot['slot_id'])
                        teacher_slot_courses[key].append(self.schedule_vars[var_name])
        
        for (teacher, slot_id), course_vars in teacher_slot_courses.items():
            if len(course_vars) > 1:
                self.model.Add(sum(course_vars) <= 1)
                constraint_count += 1
        
        # 7. Contraintes israéliennes
        israeli_constraints = self._add_israeli_constraints()
        constraint_count += israeli_constraints
        
        # 8. Objectif: minimiser les trous et favoriser les blocs
        self._set_optimization_objective()
        
        logger.info(f"✓ Modèle créé avec {constraint_count} contraintes")
        return constraint_count
    
    def _add_israeli_constraints(self):
        """Contraintes spécifiques israéliennes"""
        constraint_count = 0
        young_grades = ['ז-1', 'ז-2', 'ז-3', 'ז-4', 'ח-1', 'ח-2', 'ח-3', 'ח-4', 'ט-1', 'ט-2', 'ט-3', 'ט-4', 'ט-5']
        
        for course in self.courses:
            course_id = course['course_id']
            classes = course.get('classes', [])
            
            # Vérifier si ce cours affecte des jeunes classes
            affects_young = any(cls in young_grades for cls in classes)
            
            if affects_young:
                # Interdire lundi après période 4
                for slot in self.time_slots:
                    if slot['day_of_week'] == 1 and slot['period_number'] > 4:
                        var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            constraint_count += 1
        
        return constraint_count
    
    def _set_optimization_objective(self):
        """Objectif d'optimisation amélioré"""
        logger.info("Configuration de l'objectif V2...")
        
        objective_terms = []
        
        # 1. Minimiser les trous (PRIORITÉ MAXIMALE)
        gap_penalty = self._create_gap_penalty_v2()
        objective_terms.extend(gap_penalty)
        
        # 2. Favoriser les blocs de 2h
        block_bonus = self._create_block_bonus_terms()
        objective_terms.extend(block_bonus)
        
        # 3. Pénaliser les heures supplémentaires au milieu de la journée
        edge_bonus = self._create_edge_preference_terms()
        objective_terms.extend(edge_bonus)
        
        if objective_terms:
            self.model.Minimize(sum(objective_terms))
            logger.info(f"✓ Objectif avec {len(objective_terms)} termes")
    
    def _create_gap_penalty_v2(self):
        """Pénalité forte pour les trous"""
        gap_terms = []
        
        # Pour chaque classe et chaque jour
        classes_set = set()
        for course in self.courses:
            classes_set.update(course.get('classes', []))
        
        for class_name in classes_set:
            for day in range(5):  # Lundi à jeudi
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_slots.sort(key=lambda x: x['period_number'])
                
                if len(day_slots) >= 3:
                    # Créer des variables pour détecter les trous
                    for i in range(1, len(day_slots) - 1):
                        gap_var = self.model.NewBoolVar(f"gap_{class_name}_day_{day}_pos_{i}")
                        
                        # Collecter les variables pour cette classe à ces positions
                        before_vars = []
                        current_vars = []
                        after_vars = []
                        
                        for course in self.courses:
                            if class_name in course.get('classes', []):
                                before_var = f"course_{course['course_id']}_slot_{day_slots[i-1]['slot_id']}"
                                current_var = f"course_{course['course_id']}_slot_{day_slots[i]['slot_id']}"
                                after_var = f"course_{course['course_id']}_slot_{day_slots[i+1]['slot_id']}"
                                
                                if before_var in self.schedule_vars:
                                    before_vars.append(self.schedule_vars[before_var])
                                if current_var in self.schedule_vars:
                                    current_vars.append(self.schedule_vars[current_var])
                                if after_var in self.schedule_vars:
                                    after_vars.append(self.schedule_vars[after_var])
                        
                        if before_vars and current_vars and after_vars:
                            # Un trou existe si: cours avant ET après, mais PAS au milieu
                            has_before = self.model.NewBoolVar(f"has_before_{class_name}_{day}_{i}")
                            has_current = self.model.NewBoolVar(f"has_current_{class_name}_{day}_{i}")
                            has_after = self.model.NewBoolVar(f"has_after_{class_name}_{day}_{i}")
                            
                            self.model.AddMaxEquality(has_before, before_vars)
                            self.model.AddMaxEquality(has_current, current_vars)
                            self.model.AddMaxEquality(has_after, after_vars)
                            
                            # gap_var = 1 si (has_before AND has_after AND NOT has_current)
                            self.model.AddBoolAnd([has_before, has_after, has_current.Not()]).OnlyEnforceIf(gap_var)
                            self.model.AddBoolOr([has_before.Not(), has_after.Not(), has_current]).OnlyEnforceIf(gap_var.Not())
                            
                            # Pénalité TRÈS FORTE pour les trous
                            gap_terms.append(gap_var * 1000)
        
        return gap_terms
    
    def _create_block_bonus_terms(self):
        """Bonus pour les blocs de 2h consécutives"""
        block_terms = []
        
        for course in self.courses:
            if course.get('hours_per_week', 0) >= 2:
                course_id = course['course_id']
                
                for day in range(5):
                    day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                    day_slots.sort(key=lambda x: x['period_number'])
                    
                    for i in range(len(day_slots) - 1):
                        if day_slots[i+1]['period_number'] == day_slots[i]['period_number'] + 1:
                            var1_name = f"course_{course_id}_slot_{day_slots[i]['slot_id']}"
                            var2_name = f"course_{course_id}_slot_{day_slots[i+1]['slot_id']}"
                            
                            if var1_name in self.schedule_vars and var2_name in self.schedule_vars:
                                block_var = self.model.NewBoolVar(f"block_{course_id}_day_{day}_pos_{i}")
                                
                                self.model.AddBoolAnd([
                                    self.schedule_vars[var1_name],
                                    self.schedule_vars[var2_name]
                                ]).OnlyEnforceIf(block_var)
                                
                                self.model.AddBoolOr([
                                    self.schedule_vars[var1_name].Not(),
                                    self.schedule_vars[var2_name].Not()
                                ]).OnlyEnforceIf(block_var.Not())
                                
                                # Bonus pour les blocs (négatif car on minimise)
                                priority_factor = 1 if course['priority'] == 1 else 0.5
                                block_terms.append(block_var * (-100 * priority_factor))
        
        return block_terms
    
    def _create_edge_preference_terms(self):
        """Préférence pour placer les heures supplémentaires en bord de journée"""
        edge_terms = []
        
        for course in self.courses:
            if course.get('prefers_edge', False) or course.get('type') == 'parallel_extra':
                course_id = course['course_id']
                
                # Bonus fort pour les créneaux de bord
                for slot in self.time_slots:
                    var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        if slot['is_edge']:
                            # Bonus pour utiliser ce créneau de bord (négatif car on minimise)
                            edge_terms.append(self.schedule_vars[var_name] * (-200))
                        else:
                            # Pénalité légère pour utiliser le milieu
                            edge_terms.append(self.schedule_vars[var_name] * 50)
        
        return edge_terms
    
    def solve(self, time_limit_seconds=300):
        """Lance la résolution"""
        logger.info(f"Résolution V2 (limite: {time_limit_seconds}s)...")
        
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = True
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        solve_time = time.time() - start_time
        
        logger.info(f"✓ Résolution terminée en {solve_time:.1f}s")
        
        if status == cp_model.OPTIMAL:
            logger.info("🎯 Solution OPTIMALE trouvée")
        elif status == cp_model.FEASIBLE:
            logger.info("✅ Solution FAISABLE trouvée")
        else:
            logger.error(f"❌ Pas de solution trouvée (statut: {status})")
            return None
        
        return self._extract_solution(solve_time)
    
    def _extract_solution(self, solve_time):
        """Extrait la solution avec toutes les informations"""
        logger.info("Extraction de la solution V2...")
        
        schedule = []
        stats = {
            'total_entries': 0,
            'parallel_main_courses': 0,
            'parallel_extra_courses': 0,
            'individual_courses': 0,
            'edge_slots_used': 0,
            'middle_slots_used': 0,
            'solve_time': solve_time,
            'gaps_detected': 0
        }
        
        for course in self.courses:
            course_id = course['course_id']
            classes = course.get('classes', [])
            teachers = course.get('teachers', [])
            course_type = course.get('type', 'individual')
            
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    if self.solver.Value(self.schedule_vars[var_name]) == 1:
                        
                        # Statistiques selon le type de créneau
                        if slot['is_edge']:
                            stats['edge_slots_used'] += 1
                        else:
                            stats['middle_slots_used'] += 1
                        
                        # Créer les entrées pour chaque classe
                        for class_name in classes:
                            schedule.append({
                                'class_name': class_name,
                                'day': slot['day_of_week'],
                                'slot_index': slot['period_number'],
                                'subject': course['subject'],
                                'teacher_names': teachers,
                                'kind': 'parallel' if course_type == 'parallel_main' else 'individual',
                                'slot_id': slot['slot_id'],
                                'is_extra': course_type == 'parallel_extra'
                            })
                            stats['total_entries'] += 1
                        
                        # Statistiques par type
                        if course_type == 'parallel_main':
                            stats['parallel_main_courses'] += 1
                        elif course_type == 'parallel_extra':
                            stats['parallel_extra_courses'] += 1
                        else:
                            stats['individual_courses'] += 1
        
        # Analyser les trous
        stats['gaps_detected'] = self._count_gaps_in_solution(schedule)
        
        logger.info(f"✓ Solution extraite: {stats['total_entries']} entrées")
        logger.info(f"  → Cours parallèles principaux: {stats['parallel_main_courses']}")
        logger.info(f"  → Heures supplémentaires: {stats['parallel_extra_courses']}")
        logger.info(f"  → Cours individuels: {stats['individual_courses']}")
        logger.info(f"  → Créneaux de bord utilisés: {stats['edge_slots_used']}")
        logger.info(f"  → Trous détectés: {stats['gaps_detected']}")
        
        return {
            'success': True,
            'schedule': schedule,
            'stats': stats,
            'solver_status': 'OPTIMAL' if self.solver.ObjectiveValue() else 'FEASIBLE',
            'quality_score': max(0, 100 - stats['gaps_detected'] * 2)  # Score basé sur les trous
        }
    
    def _count_gaps_in_solution(self, schedule):
        """Compte les trous dans la solution générée"""
        gaps = 0
        
        # Organiser par classe et jour
        class_day_periods = defaultdict(lambda: defaultdict(list))
        for entry in schedule:
            class_name = entry['class_name']
            day = entry['day']
            period = entry['slot_index']
            class_day_periods[class_name][day].append(period)
        
        # Compter les trous
        for class_name, days in class_day_periods.items():
            for day, periods in days.items():
                if len(periods) >= 2:
                    periods.sort()
                    for i in range(periods[0], periods[-1]):
                        if i not in periods:
                            gaps += 1
        
        return gaps


def main():
    """Test du solver V2"""
    logging.basicConfig(level=logging.INFO)
    
    solver = ParallelSyncSolverV2()
    
    # Connexion DB
    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        database="school_scheduler",
        user="admin",
        password="school123",
        port=5432
    )
    
    try:
        solver.load_data(conn)
        solver.create_model()
        result = solver.solve(300)
        
        if result:
            print("\n=== RÉSULTAT V2 ===")
            print(f"Succès: {result['success']}")
            print(f"Entrées: {result['stats']['total_entries']}")
            print(f"Heures supplémentaires placées: {result['stats']['parallel_extra_courses']}")
            print(f"Trous: {result['stats']['gaps_detected']}")
            print(f"Score qualité: {result['quality_score']}/100")
        else:
            print("❌ Échec de la résolution")
            
    finally:
        conn.close()


if __name__ == "__main__":
    main()
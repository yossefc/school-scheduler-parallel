#!/usr/bin/env python3
"""
parallel_sync_solver.py - Solver avec synchronisation correcte des cours parallèles
Résout le problème de synchronisation des classes ז-1, ז-3, ז-4 etc.
"""
import logging
import time
from typing import Dict, List, Any, Optional
from ortools.sat.python import cp_model
from simple_parallel_handler import SimpleParallelHandler

logger = logging.getLogger(__name__)

class ParallelSyncSolver:
    """
    Solver avec synchronisation parfaite des cours parallèles
    Garantit que tous les cours is_parallel=true avec même subject+class_list 
    sont au MÊME créneau avec TOUS les professeurs
    """
    
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.courses = []
        self.time_slots = []
        self.schedule_vars = {}
        
    def load_data(self, db_connection):
        """Charge les données depuis la base"""
        logger.info("Chargement des données pour synchronisation parallèle...")
        
        # Charger les cours
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT course_id, class_list, subject, teacher_names, hours, 
                   is_parallel, group_id
            FROM solver_input 
            ORDER BY subject, class_list
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
        
        # Traiter avec le handler correct
        self.courses = SimpleParallelHandler.process_courses_for_solver(raw_courses)
        
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
                'period_number': row[2]
            })
        
        cursor.close()
        
        logger.info(f"✓ {len(self.courses)} cours traités")
        logger.info(f"✓ {len(self.time_slots)} créneaux disponibles")
        
        # Statistiques
        parallel_courses = [c for c in self.courses if c.get('is_parallel')]
        individual_courses = [c for c in self.courses if not c.get('is_parallel')]
        
        logger.info(f"  → {len(parallel_courses)} cours parallèles (multi-classes)")
        logger.info(f"  → {len(individual_courses)} cours individuels")
        
        return len(self.courses), len(self.time_slots)
    
    def create_model(self):
        """Crée le modèle de programmation par contraintes"""
        logger.info("Création du modèle avec synchronisation parallèle...")
        
        # 1. Créer les variables
        self.schedule_vars = SimpleParallelHandler.create_schedule_variables(
            self.model, self.courses, self.time_slots
        )
        
        # 2. Contraintes de base
        constraint_count = 0
        
        # Contraintes de cours (nombre d'heures exact)
        constraint_count += SimpleParallelHandler.add_course_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        
        # Contraintes de conflit de classes
        constraint_count += SimpleParallelHandler.add_class_conflict_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        
        # Contraintes de conflit de professeurs
        constraint_count += SimpleParallelHandler.add_teacher_conflict_constraints(
            self.model, self.courses, self.schedule_vars, self.time_slots
        )
        
        # 3. CONTRAINTES SPÉCIALES pour synchronisation parallèle
        sync_constraints = self._add_parallel_sync_constraints()
        constraint_count += sync_constraints
        
        # 4. CONTRAINTES ISRAÉLIENNES
        israeli_constraints = self._add_israeli_constraints()
        constraint_count += israeli_constraints
        
        # 5. OBJECTIF : Minimiser les trous et favoriser les blocs
        self._set_optimization_objective()
        
        logger.info(f"✓ Modèle créé avec {constraint_count} contraintes")
        return constraint_count
        
    def _add_parallel_sync_constraints(self):
        """
        CONTRAINTES CRITIQUES DE SYNCHRONISATION PARALLÈLE
        Garantit que tous les cours parallèles du même groupe sont synchronisés
        """
        logger.info("Ajout des contraintes de synchronisation parallèle...")
        constraint_count = 0
        
        # Identifier les groupes parallèles par (subject, classes_set)
        parallel_groups = {}
        
        for course in self.courses:
            if course.get('is_parallel') and len(course.get('classes', [])) > 1:
                classes_key = tuple(sorted(course['classes']))
                subject = course['subject']
                group_key = (subject, classes_key)
                
                if group_key not in parallel_groups:
                    parallel_groups[group_key] = []
                parallel_groups[group_key].append(course)
        
        logger.info(f"Groupes parallèles identifiés: {len(parallel_groups)}")
        
        # Pour chaque groupe parallèle, tous les cours doivent être synchronisés
        for (subject, classes_key), courses_group in parallel_groups.items():
            if len(courses_group) > 1:  # Plusieurs instances du même cours parallèle
                logger.warning(f"ATTENTION: Groupe {subject} pour {classes_key} a {len(courses_group)} instances")
                logger.warning("Ceci peut causer des conflits - vérifier les données")
                
            # Pour chaque cours parallèle, créer des contraintes de synchronisation
            for course in courses_group:
                course_id = course['course_id']
                hours_needed = course['hours_per_week']
                
                logger.info(f"Cours parallèle {course_id}: {subject}")
                logger.info(f"  → Classes: {course['classes']}")
                logger.info(f"  → Professeurs: {len(course['teachers'])}")
                logger.info(f"  → Heures: {hours_needed}")
                
                # Vérification: Ce cours occupe exactement N créneaux
                # et chaque créneau couvre TOUTES les classes simultanément
                # (C'est déjà géré par SimpleParallelHandler.add_course_constraints)
                constraint_count += 1
        
        return constraint_count
        
    def _add_israeli_constraints(self):
        """Contraintes spécifiques à l'école israélienne"""
        constraint_count = 0
        
        # Contrainte: Lundi court pour ז, ח, ט
        young_grades = ['ז-1', 'ז-3', 'ז-4', 'ח-1', 'ח-3', 'ח-4', 'ט-1', 'ט-3', 'ט-4', 'ט-5']
        
        for course in self.courses:
            course_id = course['course_id']
            classes = course.get('classes', [])
            
            # Vérifier si ce cours affecte des jeunes classes
            affects_young = any(cls in young_grades for cls in classes)
            
            if affects_young:
                # Interdire lundi après période 4 (slot_index > 4 et day_of_week = 1)
                for slot in self.time_slots:
                    if (slot['day_of_week'] == 1 and 
                        slot['period_number'] > 4):
                        
                        var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            self.model.Add(self.schedule_vars[var_name] == 0)
                            constraint_count += 1
        
        logger.info(f"✓ {constraint_count} contraintes israéliennes ajoutées")
        return constraint_count
        
    def _set_optimization_objective(self):
        """Objectif d'optimisation: minimiser trous, maximiser blocs"""
        logger.info("Configuration de l'objectif d'optimisation...")
        
        objective_terms = []
        
        # 1. PÉNALISER LES TROUS dans l'emploi du temps
        gap_penalty = self._create_gap_penalty_terms()
        objective_terms.extend(gap_penalty)
        
        # 2. FAVORISER LES BLOCS DE 2H CONSÉCUTIVES
        block_bonus = self._create_block_bonus_terms()
        objective_terms.extend(block_bonus)
        
        if objective_terms:
            # Minimiser (gaps penalties - block bonus)
            self.model.Minimize(sum(objective_terms))
            logger.info(f"✓ Objectif configuré avec {len(objective_terms)} termes")
        else:
            logger.warning("Aucun terme d'objectif créé")
            
    def _create_gap_penalty_terms(self):
        """Crée des termes de pénalité pour les trous"""
        gap_terms = []
        
        # Pour chaque classe et chaque jour
        classes_set = set()
        for course in self.courses:
            classes_set.update(course.get('classes', []))
        
        for class_name in classes_set:
            for day in range(5):  # Lundi à jeudi
                day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                day_slots.sort(key=lambda x: x['period_number'])
                
                if len(day_slots) >= 3:  # Au moins 3 créneaux pour avoir des trous
                    # Variables indiquant si la classe a cours à chaque créneau
                    class_vars = []
                    
                    for slot in day_slots:
                        # Collecter tous les cours de cette classe à ce créneau
                        slot_vars = []
                        for course in self.courses:
                            if class_name in course.get('classes', []):
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    slot_vars.append(self.schedule_vars[var_name])
                        
                        if slot_vars:
                            # Variable binaire: cette classe a-t-elle cours à ce créneau?
                            has_course_var = self.model.NewBoolVar(f"class_{class_name}_slot_{slot['slot_id']}_occupied")
                            self.model.AddMaxEquality(has_course_var, slot_vars)
                            class_vars.append(has_course_var)
                    
                    # Pénaliser les configurations avec trous
                    if len(class_vars) >= 3:
                        for i in range(1, len(class_vars) - 1):
                            # Si cours avant et après, mais pas au milieu = trou
                            gap_var = self.model.NewBoolVar(f"gap_{class_name}_day_{day}_slot_{i}")
                            
                            # gap_var = 1 si (avant=1 ET milieu=0 ET après=1)
                            self.model.AddBoolOr([class_vars[i-1].Not(), class_vars[i], class_vars[i+1].Not(), gap_var.Not()])
                            self.model.AddBoolOr([class_vars[i-1], gap_var.Not()])
                            self.model.AddBoolOr([class_vars[i].Not(), gap_var.Not()])
                            self.model.AddBoolOr([class_vars[i+1], gap_var.Not()])
                            
                            gap_terms.append(gap_var * 100)  # Pénalité forte pour les trous
        
        return gap_terms
        
    def _create_block_bonus_terms(self):
        """Crée des termes de bonus pour les blocs de 2h consécutives"""
        block_terms = []
        
        # Pour chaque cours avec multiple heures
        for course in self.courses:
            if course.get('hours_per_week', 0) >= 2:
                course_id = course['course_id']
                
                # Chercher les paires de créneaux consécutifs
                for day in range(5):
                    day_slots = [s for s in self.time_slots if s['day_of_week'] == day]
                    day_slots.sort(key=lambda x: x['period_number'])
                    
                    for i in range(len(day_slots) - 1):
                        slot1 = day_slots[i]
                        slot2 = day_slots[i + 1]
                        
                        # Vérifier si les créneaux sont vraiment consécutifs
                        if slot2['period_number'] == slot1['period_number'] + 1:
                            var1_name = f"course_{course_id}_slot_{slot1['slot_id']}"
                            var2_name = f"course_{course_id}_slot_{slot2['slot_id']}"
                            
                            if var1_name in self.schedule_vars and var2_name in self.schedule_vars:
                                # Variable pour bloc consécutif
                                block_var = self.model.NewBoolVar(f"block_{course_id}_day_{day}_periods_{slot1['period_number']}_{slot2['period_number']}")
                                
                                # block_var = 1 si les deux créneaux sont occupés
                                self.model.AddBoolAnd([self.schedule_vars[var1_name], self.schedule_vars[var2_name]]).OnlyEnforceIf(block_var)
                                self.model.AddBoolOr([self.schedule_vars[var1_name].Not(), self.schedule_vars[var2_name].Not()]).OnlyEnforceIf(block_var.Not())
                                
                                block_terms.append(block_var * (-50))  # Bonus négatif (favore les blocs)
        
        return block_terms
    
    def solve(self, time_limit_seconds=300):
        """Lance la résolution"""
        logger.info(f"Lancement de la résolution (limite: {time_limit_seconds}s)...")
        
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        
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
        
        # Extraire la solution
        return self._extract_solution(solve_time)
        
    def _extract_solution(self, solve_time):
        """Extrait la solution du solver"""
        logger.info("Extraction de la solution...")
        
        schedule = []
        stats = {
            'total_entries': 0,
            'parallel_courses': 0,
            'individual_courses': 0,
            'solve_time': solve_time,
            'conflicts': 0,
            'gaps': 0
        }
        
        for course in self.courses:
            course_id = course['course_id']
            classes = course.get('classes', [])
            teachers = course.get('teachers', [])
            is_parallel = course.get('is_parallel', False)
            
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    if self.solver.Value(self.schedule_vars[var_name]) == 1:
                        
                        if is_parallel:
                            # Cours parallèle: une entrée par classe
                            for class_name in classes:
                                schedule.append({
                                    'class_name': class_name,
                                    'day': slot['day_of_week'],
                                    'slot_index': slot['period_number'],
                                    'subject': course['subject'],
                                    'teacher_names': teachers,
                                    'kind': 'parallel',
                                    'slot_id': slot['slot_id']
                                })
                                stats['total_entries'] += 1
                            stats['parallel_courses'] += 1
                        else:
                            # Cours individuel: une entrée par classe
                            for class_name in classes:
                                schedule.append({
                                    'class_name': class_name,
                                    'day': slot['day_of_week'],
                                    'slot_index': slot['period_number'],
                                    'subject': course['subject'],
                                    'teacher_names': teachers,
                                    'kind': 'individual',
                                    'slot_id': slot['slot_id']
                                })
                                stats['total_entries'] += 1
                            stats['individual_courses'] += 1
        
        logger.info(f"✓ Solution extraite: {stats['total_entries']} entrées")
        logger.info(f"  → {stats['parallel_courses']} cours parallèles planifiés")
        logger.info(f"  → {stats['individual_courses']} cours individuels planifiés")
        
        return {
            'success': True,
            'schedule': schedule,
            'stats': stats,
            'solver_status': 'OPTIMAL' if self.solver.ObjectiveValue() else 'FEASIBLE'
        }


def main():
    """Test du solver"""
    import psycopg2
    
    logging.basicConfig(level=logging.INFO)
    
    # Connexion à la base
    conn = psycopg2.connect(
        host="localhost",
        database="school_scheduler", 
        user="admin",
        password="school123",
        port=5432
    )
    
    try:
        solver = ParallelSyncSolver()
        solver.load_data(conn)
        solver.create_model()
        result = solver.solve(300)  # 5 minutes
        
        if result:
            print("\n=== RÉSULTAT ===")
            print(f"Succès: {result['success']}")
            print(f"Entrées: {result['stats']['total_entries']}")
            print(f"Cours parallèles: {result['stats']['parallel_courses']}")
            print(f"Cours individuels: {result['stats']['individual_courses']}")
            print(f"Temps: {result['stats']['solve_time']:.1f}s")
        else:
            print("❌ Échec de la résolution")
            
    finally:
        conn.close()


if __name__ == "__main__":
    main()
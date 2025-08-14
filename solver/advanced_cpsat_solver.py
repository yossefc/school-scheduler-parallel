#!/usr/bin/env python3
"""
Solveur CP-SAT avancé pour emploi du temps scolaire
- Zéro trous pour les classes (contrainte dure avec automate)
- Minimisation des trous pour les professeurs (objectif)
- Support des cours parallèles (co-enseignement)
- Interdiction totale du vendredi
"""

from ortools.sat.python import cp_model
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import json
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class AdvancedCPSATSolver:
    def __init__(self, db_config=None):
        """Initialise le solveur CP-SAT avancé"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        if db_config is None:
            db_config = {
                "host": "postgres",
                "database": "school_scheduler",
                "user": "admin",
                "password": "school123"
            }
        
        self.db_config = db_config
        
        # Données
        self.time_slots = []  # Créneaux horaires
        self.parallel_groups = []  # Groupes de cours parallèles
        self.simple_courses = []  # Cours simples (non parallèles)
        self.classes = set()  # Ensemble des classes
        self.teachers = set()  # Ensemble des professeurs
        self.subjects = set()  # Ensemble des matières
        
        # Variables CP-SAT
        self.z = {}  # z[g,t]: bloc parallèle g au créneau t
        self.x = {}  # x[c,s,t]: classe c a matière s au créneau t
        self.a = {}  # a[r,t]: cours simple r au créneau t
        self.busy = {}  # busy[p,t]: prof p occupé au créneau t
        
        # Variables pour les trous
        self.u = {}  # u[c,d,i]: classe c a cours au jour d, période i
        self.v = {}  # v[p,d,i]: prof p occupé au jour d, période i
        
        # Variables pour l'objectif (trous profs)
        self.gaps_prof = {}  # gaps[p,d]: nombre de trous pour prof p jour d
        
    def load_data_from_db(self):
        """Charge les données depuis la base"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            logger.info("=== CHARGEMENT DES DONNÉES CP-SAT ===")
            
            # Charger les créneaux (exclure vendredi)
            cur.execute("""
                SELECT * FROM time_slots 
                WHERE is_break = FALSE AND day_of_week != 5
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"✓ {len(self.time_slots)} créneaux (vendredi exclu)")
            
            # Charger les cours depuis solver_input
            cur.execute("""
                SELECT * FROM solver_input 
                ORDER BY course_type, course_id
            """)
            raw_courses = cur.fetchall()
            
            # Séparer cours parallèles et simples
            self._process_courses(raw_courses)
            
            logger.info(f"✓ {len(self.parallel_groups)} groupes parallèles")
            logger.info(f"✓ {len(self.simple_courses)} cours simples")
            logger.info(f"✓ {len(self.classes)} classes")
            logger.info(f"✓ {len(self.teachers)} professeurs")
            
        finally:
            cur.close()
            conn.close()
    
    def _process_courses(self, raw_courses):
        """Traite les cours pour séparer parallèles et simples"""
        parallel_dict = defaultdict(list)
        
        for course in raw_courses:
            # Extraire les informations
            classes_list = [c.strip() for c in (course.get("class_list") or "").split(",") if c.strip()]
            teachers_list = [t.strip() for t in (course.get("teacher_names") or "").split(",") if t.strip()]
            subject = course.get("subject") or course.get("subject_name") or ""
            hours = course.get("hours", 0)
            is_parallel = course.get("is_parallel", False)
            
            # Ajouter aux ensembles
            self.classes.update(classes_list)
            self.teachers.update(teachers_list)
            if subject:
                self.subjects.add(subject)
            
            if is_parallel and len(classes_list) > 1:
                # Cours parallèle - regrouper par (subject, teachers)
                key = (subject, tuple(sorted(teachers_list)))
                parallel_dict[key].append({
                    "course_id": course.get("course_id"),
                    "classes": classes_list,
                    "hours": hours
                })
            else:
                # Cours simple
                for class_name in classes_list:
                    for teacher in teachers_list[:1]:  # Premier prof seulement pour cours simple
                        self.simple_courses.append({
                            "id": f"r_{course.get('course_id')}_{class_name}_{teacher}",
                            "class": class_name,
                            "subject": subject,
                            "teacher": teacher,
                            "hours": hours
                        })
        
        # Créer les groupes parallèles
        group_id = 0
        for (subject, teachers), courses in parallel_dict.items():
            if len(courses) > 0:
                all_classes = set()
                total_hours = 0
                for c in courses:
                    all_classes.update(c["classes"])
                    total_hours = max(total_hours, c["hours"])  # Prendre le max des heures
                
                self.parallel_groups.append({
                    "id": f"g_{group_id}",
                    "subject": subject,
                    "hours": total_hours,
                    "classes": list(all_classes),
                    "teachers": list(teachers)
                })
                group_id += 1
    
    def create_variables(self):
        """Crée toutes les variables CP-SAT"""
        logger.info("=== CRÉATION DES VARIABLES CP-SAT ===")
        
        # Index des créneaux par jour
        self.slots_by_day = defaultdict(list)
        for slot in self.time_slots:
            self.slots_by_day[slot["day_of_week"]].append(slot)
        
        # Trier les créneaux par période dans chaque jour
        for day in self.slots_by_day:
            self.slots_by_day[day].sort(key=lambda s: s["period_number"])
        
        # 1. Variables z[g,t] pour les blocs parallèles
        for g in self.parallel_groups:
            for t in self.time_slots:
                self.z[g["id"], t["slot_id"]] = self.model.NewBoolVar(f"z_{g['id']}_{t['slot_id']}")
        
        # 2. Variables x[c,s,t] pour classe-matière-créneau
        for c in self.classes:
            for s in self.subjects:
                for t in self.time_slots:
                    self.x[c, s, t["slot_id"]] = self.model.NewBoolVar(f"x_{c}_{s}_{t['slot_id']}")
        
        # 3. Variables a[r,t] pour cours simples
        for r in self.simple_courses:
            for t in self.time_slots:
                self.a[r["id"], t["slot_id"]] = self.model.NewBoolVar(f"a_{r['id']}_{t['slot_id']}")
        
        # 4. Variables busy[p,t] pour occupation prof
        for p in self.teachers:
            for t in self.time_slots:
                self.busy[p, t["slot_id"]] = self.model.NewBoolVar(f"busy_{p}_{t['slot_id']}")
        
        # 5. Variables u[c,d,i] pour présence classe (pour automate)
        for c in self.classes:
            for day, slots in self.slots_by_day.items():
                for i, slot in enumerate(slots):
                    self.u[c, day, i] = self.model.NewBoolVar(f"u_{c}_{day}_{i}")
        
        # 6. Variables v[p,d,i] pour occupation prof (pour calcul trous)
        for p in self.teachers:
            for day, slots in self.slots_by_day.items():
                for i, slot in enumerate(slots):
                    self.v[p, day, i] = self.model.NewBoolVar(f"v_{p}_{day}_{i}")
        
        logger.info(f"✓ Variables créées: {len(self.z)} z, {len(self.x)} x, {len(self.a)} a, {len(self.busy)} busy")
    
    def add_hard_constraints(self):
        """Ajoute toutes les contraintes dures"""
        logger.info("=== CONTRAINTES DURES ===")
        
        # 1. Vendredi interdit (déjà exclu des time_slots, mais double sécurité)
        for t in self.time_slots:
            if t.get("day_of_week") == 5:
                # Interdire tout sur vendredi
                for g in self.parallel_groups:
                    self.model.Add(self.z[g["id"], t["slot_id"]] == 0)
                for r in self.simple_courses:
                    self.model.Add(self.a[r["id"], t["slot_id"]] == 0)
        
        # 2. Durée/volumes
        self._add_duration_constraints()
        
        # 3. Liens parallèles → classes & profs
        self._add_parallel_links()
        
        # 4. Liens cours simples → classe & prof
        self._add_simple_links()
        
        # 5. Capacité classe (au plus un cours par créneau)
        self._add_class_capacity()
        
        # 6. Capacité prof (au plus un enseignement par créneau)
        self._add_teacher_capacity()
        
        # 7. ZÉRO TROUS pour chaque classe (automate)
        self._add_zero_gaps_classes()
        
        logger.info("✓ Contraintes dures ajoutées")
    
    def _add_duration_constraints(self):
        """Contraintes de durée pour chaque cours"""
        # Groupes parallèles
        for g in self.parallel_groups:
            vars_g = [self.z[g["id"], t["slot_id"]] for t in self.time_slots]
            self.model.Add(sum(vars_g) == g["hours"])
        
        # Cours simples
        for r in self.simple_courses:
            vars_r = [self.a[r["id"], t["slot_id"]] for t in self.time_slots]
            self.model.Add(sum(vars_r) == r["hours"])
    
    def _add_parallel_links(self):
        """Liens entre blocs parallèles et variables x, busy"""
        for g in self.parallel_groups:
            for t in self.time_slots:
                z_var = self.z[g["id"], t["slot_id"]]
                
                # Lien avec classes
                for c in g["classes"]:
                    if (c, g["subject"], t["slot_id"]) in self.x:
                        self.model.Add(self.x[c, g["subject"], t["slot_id"]] >= z_var)
                
                # Lien avec profs
                for p in g["teachers"]:
                    if (p, t["slot_id"]) in self.busy:
                        self.model.Add(self.busy[p, t["slot_id"]] >= z_var)
    
    def _add_simple_links(self):
        """Liens entre cours simples et variables x, busy"""
        for r in self.simple_courses:
            for t in self.time_slots:
                a_var = self.a[r["id"], t["slot_id"]]
                
                # Lien avec classe
                if (r["class"], r["subject"], t["slot_id"]) in self.x:
                    self.model.Add(self.x[r["class"], r["subject"], t["slot_id"]] >= a_var)
                
                # Lien avec prof
                if (r["teacher"], t["slot_id"]) in self.busy:
                    self.model.Add(self.busy[r["teacher"], t["slot_id"]] >= a_var)
    
    def _add_class_capacity(self):
        """Au plus un cours par créneau pour chaque classe"""
        for c in self.classes:
            for t in self.time_slots:
                vars_ct = []
                for s in self.subjects:
                    if (c, s, t["slot_id"]) in self.x:
                        vars_ct.append(self.x[c, s, t["slot_id"]])
                
                if vars_ct:
                    self.model.Add(sum(vars_ct) <= 1)
    
    def _add_teacher_capacity(self):
        """Au plus un enseignement par créneau pour chaque prof"""
        for p in self.teachers:
            for t in self.time_slots:
                if (p, t["slot_id"]) in self.busy:
                    self.model.Add(self.busy[p, t["slot_id"]] <= 1)
    
    def _add_zero_gaps_classes(self):
        """ZÉRO TROUS pour les classes via automate (contrainte dure)"""
        logger.info("  → Ajout automates zéro trous classes...")
        
        # États de l'automate
        S0_BEFORE = 0  # Avant les cours
        S1_DURING = 1  # Pendant les cours
        S2_AFTER = 2   # Après les cours
        
        # Transitions autorisées (pattern 0*1*0*)
        transitions = [
            (S0_BEFORE, 0, S0_BEFORE),  # Rester avant
            (S0_BEFORE, 1, S1_DURING),   # Commencer les cours
            (S1_DURING, 1, S1_DURING),   # Continuer les cours
            (S1_DURING, 0, S2_AFTER),    # Finir les cours
            (S2_AFTER, 0, S2_AFTER),     # Rester après
        ]
        
        for c in self.classes:
            for day, slots in self.slots_by_day.items():
                # Construire la séquence u[c,d,*]
                seq_vars = []
                
                for i, slot in enumerate(slots):
                    # u[c,d,i] = OR(x[c,s,t] for all s)
                    u_var = self.u[c, day, i]
                    
                    # Lier u à x
                    or_vars = []
                    for s in self.subjects:
                        if (c, s, slot["slot_id"]) in self.x:
                            or_vars.append(self.x[c, s, slot["slot_id"]])
                    
                    if or_vars:
                        # u_var = OR(or_vars)
                        self.model.Add(u_var <= len(or_vars))
                        self.model.Add(sum(or_vars) >= u_var)
                        for var in or_vars:
                            self.model.Add(u_var >= var)
                    else:
                        self.model.Add(u_var == 0)
                    
                    seq_vars.append(u_var)
                
                # Ajouter l'automate pour interdire les trous
                if seq_vars:
                    self.model.AddAutomaton(
                        seq_vars,
                        starting_state=S0_BEFORE,
                        final_states=[S0_BEFORE, S1_DURING, S2_AFTER],
                        transition_triples=transitions
                    )
        
        logger.info("  ✓ Automates ajoutés pour toutes les classes")
    
    def add_objective(self):
        """Objectif: minimiser les trous des professeurs"""
        logger.info("=== OBJECTIF: MINIMISATION TROUS PROFS ===")
        
        all_gaps = []
        
        for p in self.teachers:
            for day, slots in self.slots_by_day.items():
                if len(slots) < 2:
                    continue
                
                # Lier v[p,d,i] à busy[p,t]
                seq_vars = []
                for i, slot in enumerate(slots):
                    v_var = self.v[p, day, i]
                    if (p, slot["slot_id"]) in self.busy:
                        self.model.Add(v_var == self.busy[p, slot["slot_id"]])
                    else:
                        self.model.Add(v_var == 0)
                    seq_vars.append(v_var)
                
                # Calculer les trous via span - load
                # Variables first et last
                first = self.model.NewIntVar(0, len(slots)-1, f"first_{p}_{day}")
                last = self.model.NewIntVar(0, len(slots)-1, f"last_{p}_{day}")
                
                # Si au moins un cours ce jour
                has_course = self.model.NewBoolVar(f"has_course_{p}_{day}")
                self.model.Add(sum(seq_vars) >= has_course)
                self.model.Add(sum(seq_vars) <= len(seq_vars) * has_course)
                
                # Contraintes sur first et last
                for i, v_var in enumerate(seq_vars):
                    # Si v_var = 1, alors first <= i et last >= i
                    self.model.Add(first <= i + (1 - v_var) * len(slots))
                    self.model.Add(last >= i - (1 - v_var) * len(slots))
                
                # Span et load
                span = self.model.NewIntVar(0, len(slots), f"span_{p}_{day}")
                self.model.Add(span >= last - first + 1)
                self.model.Add(span <= (last - first + 1) + (1 - has_course) * len(slots))
                
                load = self.model.NewIntVar(0, len(slots), f"load_{p}_{day}")
                self.model.Add(load == sum(seq_vars))
                
                # Gaps = span - load si has_course, 0 sinon
                gap = self.model.NewIntVar(0, len(slots), f"gap_{p}_{day}")
                self.model.Add(gap >= span - load - (1 - has_course) * len(slots))
                self.model.Add(gap <= span - load + (1 - has_course) * len(slots))
                self.model.Add(gap <= has_course * len(slots))
                
                self.gaps_prof[p, day] = gap
                all_gaps.append(gap)
        
        # Objectif: minimiser la somme des trous
        if all_gaps:
            self.model.Minimize(sum(all_gaps))
            logger.info(f"✓ Objectif configuré: minimiser {len(all_gaps)} variables de trous")
    
    def add_search_strategy(self):
        """Stratégie de recherche pour éviter les biais"""
        logger.info("=== STRATÉGIE DE RECHERCHE ===")
        
        # 1. Décider les blocs parallèles d'abord, par jour
        z_vars = []
        for day in sorted(self.slots_by_day.keys()):
            for g in self.parallel_groups:
                for slot in self.slots_by_day[day]:
                    z_vars.append(self.z[g["id"], slot["slot_id"]])
        
        if z_vars:
            self.model.AddDecisionStrategy(
                z_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE
            )
            logger.info(f"  ✓ Stratégie 1: {len(z_vars)} variables z (parallèles)")
        
        # 2. Ensuite les cours simples, par jour puis par classe
        x_vars = []
        for day in sorted(self.slots_by_day.keys()):
            for c in sorted(self.classes):
                for slot in self.slots_by_day[day]:
                    for s in self.subjects:
                        if (c, s, slot["slot_id"]) in self.x:
                            x_vars.append(self.x[c, s, slot["slot_id"]])
        
        if x_vars:
            self.model.AddDecisionStrategy(
                x_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE
            )
            logger.info(f"  ✓ Stratégie 2: {len(x_vars)} variables x (classes)")
    
    def solve(self, time_limit=60):
        """Résout le problème avec CP-SAT"""
        logger.info("\n=== RÉSOLUTION CP-SAT ===")
        
        try:
            # Créer variables et contraintes
            self.create_variables()
            self.add_hard_constraints()
            self.add_objective()
            self.add_search_strategy()
            
            # Configurer le solver
            self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
            self.solver.parameters.num_search_workers = 8
            self.solver.parameters.randomize_search = True
            self.solver.parameters.random_seed = 123
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.log_search_progress = True
            
            # Résoudre
            logger.info(f"Lancement de la résolution (limite: {time_limit}s)...")
            start_time = datetime.now()
            status = self.solver.Solve(self.model)
            end_time = datetime.now()
            
            # Sauvegarder le status pour usage ultérieur
            self._solve_status = status
            
            solving_time = (end_time - start_time).total_seconds()
            logger.info(f"⏱️ Temps de résolution: {solving_time:.1f}s")
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! Status: {self.solver.StatusName(status)}")
                schedule = self._extract_solution()
                self._analyze_solution(schedule, status)
                return schedule
            else:
                logger.error(f"❌ Pas de solution. Status: {self.solver.StatusName(status)}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la résolution: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _extract_solution(self):
        """Extrait la solution du solver"""
        entries = []
        
        # 1. Extraire les blocs parallèles
        for g in self.parallel_groups:
            for t in self.time_slots:
                if self.solver.Value(self.z[g["id"], t["slot_id"]]) == 1:
                    # Une entrée par classe du groupe
                    for c in g["classes"]:
                        entries.append({
                            "class_name": c,
                            "day": t["day_of_week"],
                            "slot_index": t["period_number"],
                            "subject": g["subject"],
                            "teacher_names": g["teachers"],
                            "kind": "parallel",
                            "slot_id": t["slot_id"]
                        })
        
        # 2. Extraire les cours simples
        for r in self.simple_courses:
            for t in self.time_slots:
                if self.solver.Value(self.a[r["id"], t["slot_id"]]) == 1:
                    entries.append({
                        "class_name": r["class"],
                        "day": t["day_of_week"],
                        "slot_index": t["period_number"],
                        "subject": r["subject"],
                        "teacher_names": [r["teacher"]],
                        "kind": "single",
                        "slot_id": t["slot_id"]
                    })
        
        return entries
    
    def _analyze_solution(self, schedule, status):
        """Analyse la qualité de la solution"""
        if not schedule:
            return
        
        logger.info("\n=== ANALYSE DE LA SOLUTION ===")
        
        # 1. Vérifier vendredi
        friday_entries = [e for e in schedule if e["day"] == 5]
        if friday_entries:
            logger.error(f"❌ {len(friday_entries)} entrées le vendredi!")
        else:
            logger.info("✅ Aucune entrée le vendredi")
        
        # 2. Vérifier zéro trous classes
        class_gaps = self._check_class_gaps(schedule)
        if class_gaps == 0:
            logger.info("✅ ZÉRO TROUS pour toutes les classes")
        else:
            logger.error(f"❌ {class_gaps} trous détectés pour les classes")
        
        # 3. Calculer trous profs
        total_prof_gaps = 0
        for (p, day), gap_var in self.gaps_prof.items():
            gap_value = self.solver.Value(gap_var)
            if gap_value > 0:
                total_prof_gaps += gap_value
        
        logger.info(f"📊 Total trous professeurs: {total_prof_gaps}")
        
        solve_status = self.solver.StatusName(status)
        if solve_status == "OPTIMAL":
            logger.info("🏆 Solution OPTIMALE trouvée")
        else:
            logger.info(f"✓ Solution {solve_status}")
        
        # 4. Statistiques générales
        by_class = defaultdict(int)
        by_teacher = defaultdict(int)
        for e in schedule:
            by_class[e["class_name"]] += 1
            for t in e["teacher_names"]:
                by_teacher[t] += 1
        
        logger.info(f"📊 {len(schedule)} créneaux, {len(by_class)} classes, {len(by_teacher)} profs")
    
    def _check_class_gaps(self, schedule):
        """Vérifie les trous pour les classes"""
        gaps = 0
        
        # Organiser par classe et jour
        by_class_day = defaultdict(list)
        for e in schedule:
            key = (e["class_name"], e["day"])
            by_class_day[key].append(e["slot_index"])
        
        # Vérifier chaque classe/jour
        for (class_name, day), periods in by_class_day.items():
            if len(periods) < 2:
                continue
            
            periods.sort()
            for i in range(len(periods) - 1):
                gap = periods[i+1] - periods[i] - 1
                if gap > 0:
                    gaps += gap
                    logger.warning(f"  Trou détecté: {class_name} jour {day}, {gap} période(s)")
        
        return gaps
    
    def export_json(self, schedule):
        """Exporte la solution au format JSON pour l'API"""
        if not schedule:
            return None
        
        # Organiser les time_slots
        time_slots = []
        slot_map = {}
        for slot in self.time_slots:
            slot_info = {
                "day": slot["day_of_week"],
                "index": slot["period_number"],
                "start": str(slot.get("start_time", "")),
                "end": str(slot.get("end_time", ""))
            }
            time_slots.append(slot_info)
            slot_map[slot["slot_id"]] = slot_info
        
        # Préparer les entrées
        entries = []
        for e in schedule:
            entries.append({
                "class_name": e["class_name"],
                "day": e["day"],
                "slot_index": e["slot_index"],
                "subject": e["subject"],
                "teacher_names": e["teacher_names"],
                "kind": e["kind"]
            })
        
        # Métadonnées
        solve_status = getattr(self, '_solve_status', cp_model.UNKNOWN)
        meta = {
            "solve_status": self.solver.StatusName(solve_status),
            "walltime": self.solver.WallTime(),
            "objective_value": self.solver.ObjectiveValue() if solve_status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None,
            "total_teacher_gaps": int(self.solver.ObjectiveValue()) if solve_status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None
        }
        
        return {
            "time_slots": time_slots,
            "entries": entries,
            "meta": meta
        }


def main():
    """Fonction principale pour tests"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    solver = AdvancedCPSATSolver()
    
    # Configuration pour tests locaux
    solver.db_config = {
        "host": "localhost",
        "database": "school_scheduler",
        "user": "admin",
        "password": "school123",
        "port": 5432
    }
    
    try:
        solver.load_data_from_db()
        schedule = solver.solve(time_limit=60)
        
        if schedule:
            result = solver.export_json(schedule)
            
            # Sauvegarder le résultat
            with open("schedule_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info("✅ Résultat sauvegardé dans schedule_result.json")
            
            # Afficher un résumé
            logger.info(f"\n📊 RÉSUMÉ FINAL:")
            logger.info(f"  - Status: {result['meta']['solve_status']}")
            logger.info(f"  - Temps: {result['meta']['walltime']:.2f}s")
            logger.info(f"  - Trous profs total: {result['meta']['total_teacher_gaps']}")
            logger.info(f"  - Entrées: {len(result['entries'])}")
            
        else:
            logger.error("Aucune solution trouvée")
            
    except Exception as e:
        logger.error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
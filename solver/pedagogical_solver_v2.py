"""
pedagogical_solver_v2.py - Solveur pédagogique amélioré avec toutes les contraintes
Inclut: synchronisation parallèle, zéro trou, regroupement matières, support dimanche
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple, Optional, Set
import time
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class PedagogicalScheduleSolverV2:
    """
    Solveur pédagogique complet avec:
    - Synchronisation des cours parallèles
    - Zéro trou garanti
    - Regroupement intelligent des matières
    - Support complet dimanche-vendredi
    """
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables du modèle
        self.schedule_vars = {}  # course_id, slot_id -> BoolVar
        self.block_vars = {}     # class_name, subject, day, period -> BoolVar (blocs 2h)
        self.parallel_sync_vars = {}  # group_id, slot_id -> BoolVar
        
        # Données
        self.courses = []
        self.time_slots = []
        self.classes = []
        self.teachers = []
        self.constraints = []
        self.parallel_groups = []
        # Variables de pénalité (ex: manque de blocs 2h)
        self.block_shortage_vars: List[cp_model.IntVar] = []
        
        # Configuration des jours (convention israélienne)
        self.DAYS = {
            0: "dimanche",   # IMPORTANT: Dimanche = 0
            1: "lundi",
            2: "mardi", 
            3: "mercredi",
            4: "jeudi",
            5: "vendredi"
        }
        
        # Configuration pédagogique
        self.config = {
            "zero_gaps": True,
            "prefer_2h_blocks": True,
            "max_days_per_subject": 3,
            "morning_subjects": ["תפילה", "מתמטיקה", "פיזיקה", "כימיה", "עברית", "תורה", "גמרא"],
            "friday_short": True,  # Vendredi écourté
            "friday_off": True,    # Désactiver complètement le vendredi (prioritaire)
            "sunday_enabled": True,  # Activer le dimanche
            "two_hour_blocks_strict": True  # Imposer des blocs 2h minimum
        }
        
        self.solve_time = 0
        
    def load_data(self):
        """Charger toutes les données depuis la DB"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # 1. Charger les cours
            cur.execute("""
                SELECT 
                    course_id,
                    subject,
                    teacher_names,
                    class_list,
                    hours,
                    is_parallel,
                    group_id,
                    grade
                FROM solver_input 
                WHERE hours > 0
                ORDER BY course_id
            """)
            self.courses = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.courses)} cours")

            # Normaliser classes/enseignants pour chaque cours
            for c in self.courses:
                classes = [x.strip() for x in (c.get("class_list") or "").split(",") if x.strip()]
                teachers = [x.strip() for x in (c.get("teacher_names") or "").split(",") if x.strip()]
                c["_classes"] = classes
                c["_teachers"] = teachers
            
            # 2. Charger les créneaux (INCLURE DIMANCHE!)
            cur.execute("""
                SELECT slot_id, day_of_week, period_number, start_time, end_time
                FROM time_slots 
                WHERE day_of_week >= 0 AND day_of_week <= 5  -- Dimanche(0) à Vendredi(5)
                  AND is_active = true 
                  AND is_break = false
                ORDER BY day_of_week, period_number
            """)
            self.time_slots = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.time_slots)} créneaux (dimanche-vendredi)")
            
            # Vérifier qu'on a bien des créneaux dimanche
            sunday_slots = [s for s in self.time_slots if s["day_of_week"] == 0]
            logger.info(f"  → {len(sunday_slots)} créneaux le dimanche")
            
            # 3. Charger les classes
            cur.execute("""
                SELECT class_name, grade, student_count 
                FROM classes 
                ORDER BY class_name
            """)
            self.classes = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.classes)} classes")
            
            # 4. Charger les professeurs
            cur.execute("""
                SELECT DISTINCT teacher_name 
                FROM teachers 
                WHERE is_active = true
                ORDER BY teacher_name
            """)
            self.teachers = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.teachers)} professeurs")
            
            # 5. Charger les groupes parallèles
            cur.execute("""
                SELECT 
                    pg.group_id,
                    pg.subject,
                    pg.grade,
                    pg.teachers,
                    array_agg(DISTINCT ptd.classes_covered) as all_classes
                FROM parallel_groups pg
                LEFT JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
                GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
            """)
            self.parallel_groups = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.parallel_groups)} groupes parallèles")
            
            # 6. Charger les contraintes
            cur.execute("""
                SELECT * FROM constraints 
                WHERE is_active = true
                ORDER BY priority
            """)
            self.constraints = cur.fetchall()
            logger.info(f"✓ Chargé {len(self.constraints)} contraintes")
            
        finally:
            cur.close()
            conn.close()
    
    def create_variables(self):
        """Créer toutes les variables de décision"""
        logger.info("=== CRÉATION DES VARIABLES ===")
        
        # 1. Variables principales : assignation cours-créneau
        for course in self.courses:
            course_id = course["course_id"]
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                # Exclure vendredi entier si demandé, sinon après-midi
                if (self.config.get("friday_off") and slot["day_of_week"] == 5) or \
                   (self.config["friday_short"] and slot["day_of_week"] == 5 and slot["period_number"] >= 5):
                    continue
                    
                var_name = f"course_{course_id}_slot_{slot_id}"
                self.schedule_vars[var_name] = self.model.NewBoolVar(var_name)
        
        # 2. Variables pour synchronisation des groupes parallèles
        # IMPORTANT: se baser EXCLUSIVEMENT sur `solver_input` (self.courses), pas sur la table parallel_groups
        groups_from_input = {}
        for c in self.courses:
            if c.get("is_parallel") and c.get("group_id"):
                groups_from_input.setdefault(c["group_id"], []).append(c)

        for group_id in groups_from_input.keys():
            for slot in self.time_slots:
                slot_id = slot["slot_id"]
                if (self.config.get("friday_off") and slot["day_of_week"] == 5) or \
                   (self.config["friday_short"] and slot["day_of_week"] == 5 and slot["period_number"] >= 5):
                    continue
                sync_var = f"parallel_sync_{group_id}_slot_{slot_id}"
                self.parallel_sync_vars[sync_var] = self.model.NewBoolVar(sync_var)
        
        # 3. Variables pour blocs de 2h
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            # Collecter les matières enseignées à cette classe
            subjects = set()
            for course in self.courses:
                if class_name in (course.get("_classes") or []):
                    subjects.add(course.get("subject", ""))
            
            for subject in subjects:
                if not subject:
                    continue
                for day in range(6):  # 0-5 (dimanche-vendredi)
                    for period in range(0, 10):  # Permettre blocs sur toute la journée
                        block_var = f"block_{class_name}_{subject}_{day}_{period}"
                        self.block_vars[block_var] = self.model.NewBoolVar(block_var)
        
        logger.info(f"✓ Créé {len(self.schedule_vars)} variables de cours")
        logger.info(f"✓ Créé {len(self.parallel_sync_vars)} variables de synchronisation")
        logger.info(f"✓ Créé {len(self.block_vars)} variables de blocs")
    
    def add_constraints(self):
        """Ajouter toutes les contraintes au modèle"""
        logger.info("=== AJOUT DES CONTRAINTES ===")
        
        # 1. Contraintes de base
        self._add_basic_constraints()
        
        # 2. Synchronisation des cours parallèles
        self._add_parallel_sync_constraints()
        
        # 3. Zéro trou (contrainte dure)
        self._add_zero_gap_constraints()
        
        # 4. Regroupement des matières
        self._add_subject_grouping_constraints()
        
        # 5. Contraintes spécifiques école
        self._add_school_specific_constraints()
        
        # 6. Début à la première période
        self._add_start_first_period_constraints()
        
        # 7. Objectifs de qualité
        # 6bis. Blocs de 2h obligatoires (avec slack pénalisé)
        self._add_two_hour_block_constraints()
        # 7. Objectifs de qualité
        self._add_quality_objectives()

    def _add_two_hour_block_constraints(self):
        """Ajoute des contraintes FORTES pour obtenir des blocs de 2h consécutives
        pour une matière donnée d'une classe. Si impossible, autorise un slack pénalisé.
        """
        logger.info("→ Contraintes fortes: blocs de 2h consécutives...")

        for class_obj in self.classes:
            class_name = class_obj["class_name"]

            # Regrouper par matière tous les cours de cette classe
            subject_to_courses: Dict[str, List[Dict]] = {}
            for course in self.courses:
                if class_name in (course.get("_classes") or []):
                    subject = course.get("subject", "")
                if not subject:
                    continue
                subject_to_courses.setdefault(subject, []).append(course)

            for subject, subject_courses in subject_to_courses.items():
                total_hours = sum(int(c.get("hours", 0)) for c in subject_courses)
                if total_hours < 2:
                    continue  # Pas de blocs si moins de 2 heures

                # Construire les variables de bloc valides (paires de créneaux consécutifs)
                block_vars_for_subject: List[cp_model.BoolVar] = []

                for day in range(6):  # Dimanche (0) à Vendredi (5)
                    day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                    day_slots.sort(key=lambda s: s["period_number"])

                    for i in range(len(day_slots) - 1):
                        slot1 = day_slots[i]
                        slot2 = day_slots[i + 1]

                        # Vérifier consécutivité
                        if slot2["period_number"] != slot1["period_number"] + 1:
                            continue

                        # has_slotX = OR(assignations de TOUS les cours de cette matière à ce créneau)
                        has_slot1 = self.model.NewBoolVar(f"has_{class_name}_{subject}_{day}_{slot1['period_number']}")
                        has_slot2 = self.model.NewBoolVar(f"has_{class_name}_{subject}_{day}_{slot2['period_number']}")

                        slot1_course_vars = []
                        slot2_course_vars = []
                        for course in subject_courses:
                            v1 = f"course_{course['course_id']}_slot_{slot1['slot_id']}"
                            v2 = f"course_{course['course_id']}_slot_{slot2['slot_id']}"
                            if v1 in self.schedule_vars:
                                slot1_course_vars.append(self.schedule_vars[v1])
                            if v2 in self.schedule_vars:
                                slot2_course_vars.append(self.schedule_vars[v2])

                        if not slot1_course_vars or not slot2_course_vars:
                            continue

                        # Lier OR linéairement
                        self.model.Add(sum(slot1_course_vars) >= has_slot1)
                        self.model.Add(sum(slot1_course_vars) <= len(slot1_course_vars) * has_slot1)
                        self.model.Add(sum(slot2_course_vars) >= has_slot2)
                        self.model.Add(sum(slot2_course_vars) <= len(slot2_course_vars) * has_slot2)

                        # Variable de bloc existante (créée dans create_variables)
                        block_name = f"block_{class_name}_{subject}_{day}_{slot1['period_number']}"
                        if block_name not in self.block_vars:
                            self.block_vars[block_name] = self.model.NewBoolVar(block_name)
                        block_var = self.block_vars[block_name]

                        # Bloc <=> has_slot1 ET has_slot2
                        self.model.Add(block_var <= has_slot1)
                        self.model.Add(block_var <= has_slot2)
                        self.model.Add(block_var >= has_slot1 + has_slot2 - 1)

                        block_vars_for_subject.append(block_var)

                if not block_vars_for_subject:
                    continue

                # Minimum de blocs requis (fort mais avec slack pénalisé)
                max_possible = len(block_vars_for_subject)
                min_required = min(total_hours // 2, max_possible)
                if min_required <= 0:
                    continue

                shortage = self.model.NewIntVar(0, max(0, min_required), f"block_shortage_{class_name}_{subject}")
                self.block_shortage_vars.append(shortage)

                # sum(blocks) + shortage >= min_required
                self.model.Add(sum(block_vars_for_subject) + shortage >= min_required)
                logger.info(f"  ✓ {class_name}/{subject}: blocs requis >= {min_required} (possibles {max_possible})")
    
    def _add_basic_constraints(self):
        """Contraintes fondamentales"""
        logger.info("→ Contraintes de base...")
        
        # 1. Pour chaque (classe, matière), couvrir exactement le total d'heures requis
        requirements = {}
        for course in self.courses:
            subject = course.get("subject", "")
            hours = int(course.get("hours", 0))
            for cls in (course.get("_classes") or []):
                if not subject:
                    continue
                key = (cls, subject)
                requirements[key] = requirements.get(key, 0) + hours

        for (cls, subject), total_hours in requirements.items():
            vars_for_cls_subject = []
            for course in self.courses:
                if course.get("subject") != subject:
                    continue
                if cls not in (course.get("_classes") or []):
                    continue
                for slot in self.time_slots:
                    if (self.config.get("friday_off") and slot["day_of_week"] == 5) or \
                       (self.config["friday_short"] and slot["day_of_week"] == 5 and slot["period_number"] >= 5):
                        continue
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        vars_for_cls_subject.append(self.schedule_vars[var_name])
            if vars_for_cls_subject:
                self.model.Add(sum(vars_for_cls_subject) == total_hours)
        
        # 2. Pas de conflit professeur
        for teacher in self.teachers:
            teacher_name = teacher["teacher_name"]
            for slot in self.time_slots:
                slot_vars = []
                for course in self.courses:
                    if teacher_name in (course.get("_teachers") or []):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            slot_vars.append(self.schedule_vars[var_name])
                
                if slot_vars:
                    self.model.Add(sum(slot_vars) <= 1)
        
        # 3. Pas de conflit classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            for slot in self.time_slots:
                slot_vars = []
                for course in self.courses:
                    if class_name in (course.get("_classes") or []):
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            slot_vars.append(self.schedule_vars[var_name])
                
                if slot_vars:
                    self.model.Add(sum(slot_vars) <= 1)
        
        logger.info("  ✓ Contraintes de base ajoutées")
    
    def _add_parallel_sync_constraints(self):
        """Synchronisation des cours en parallèle"""
        logger.info("→ Synchronisation des cours parallèles...")
        
        # Grouper les cours par group_id depuis solver_input
        courses_by_group = {}
        for course in self.courses:
            if course.get("is_parallel") and course.get("group_id"):
                group_id = course["group_id"]
                if group_id not in courses_by_group:
                    courses_by_group[group_id] = []
                courses_by_group[group_id].append(course)
        
        # Pour chaque groupe avec plusieurs cours
        for group_id, group_courses in courses_by_group.items():
            if len(group_courses) < 2:
                # Même si une seule ligne solver_input, appliquer la sync si plusieurs classes/profs
                # Traiter le cas d'une seule ligne avec plusieurs classes: forcer un seul créneau partagé
                pass
            
            # Extraire les infos du premier cours pour le log
            subject = group_courses[0].get("subject", "")
            grade = group_courses[0].get("grade", "")
            logger.info(f"  → Groupe {group_id}: {subject} {grade} - {len(group_courses)} cours")
            
            # Construire la liste des variables de sync du groupe (tous les créneaux valides)
            group_sync_vars = []
            eligible_slots = []
            for slot in self.time_slots:
                if (self.config.get("friday_off") and slot["day_of_week"] == 5) or \
                   (self.config["friday_short"] and slot["day_of_week"] == 5 and slot["period_number"] >= 5):
                    continue
                key = f"parallel_sync_{group_id}_slot_{slot['slot_id']}"
                if key in self.parallel_sync_vars:
                    group_sync_vars.append(self.parallel_sync_vars[key])
                    eligible_slots.append(slot)

            if group_sync_vars:
                # Exactement un créneau actif pour le groupe
                self.model.Add(sum(group_sync_vars) == 1)

                # Lier chaque créneau: si sync=1 alors tous les cours du groupe sont placés sur ce créneau
                for idx, slot in enumerate(eligible_slots):
                    slot_id = slot["slot_id"]
                    sync_key = f"parallel_sync_{group_id}_slot_{slot_id}"
                    course_vars = []
                    for course in group_courses:
                        var_name = f"course_{course['course_id']}_slot_{slot_id}"
                        if var_name in self.schedule_vars:
                            course_vars.append(self.schedule_vars[var_name])
                    if course_vars:
                        # Tous les cours de ce groupe doivent être 1 si sync=1, 0 sinon
                        for v in course_vars:
                            self.model.Add(v == self.parallel_sync_vars[sync_key])

                # En plus, empêcher d'autres cours de la même שכבה (grade) et matière d'être en parallèle à ce créneau
                try:
                    grade = group_courses[0].get("grade")
                    subject = group_courses[0].get("subject")
                except Exception:
                    grade = None
                    subject = None
                if grade and subject:
                    for slot in self.time_slots:
                        slot_id = slot["slot_id"]
                        sync_key = f"parallel_sync_{group_id}_slot_{slot_id}"
                        if sync_key not in self.parallel_sync_vars:
                            continue
                        # Si ce créneau est choisi pour le groupe parallèle, alors aucun autre cours du même grade/subject ne peut être mis ici
                        other_vars = []
                        for course in self.courses:
                            if course in group_courses:
                                continue
                            if course.get("subject") == subject and course.get("grade") == grade:
                                var_name = f"course_{course['course_id']}_slot_{slot_id}"
                                if var_name in self.schedule_vars:
                                    other_vars.append(self.schedule_vars[var_name])
                        if other_vars:
                            # sum(other_vars) == 0 quand sync=1
                            self.model.Add(sum(other_vars) == 0).OnlyEnforceIf(self.parallel_sync_vars[sync_key])
        
        logger.info("  ✓ Contraintes de synchronisation ajoutées")
    
    def _add_zero_gap_constraints(self):
        """Contrainte dure : aucun trou dans l'emploi du temps"""
        logger.info("→ Contraintes zéro trou...")
        
        # Pour chaque classe
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Pour chaque jour
            for day in range(6):  # 0-5 (dimanche-vendredi)
                has_courses = self.model.NewBoolVar(f"has_courses_{class_name}_{day}")
                
                # Collecter les périodes occupées
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                period_vars = {}
                
                for slot in day_slots:
                    period = slot["period_number"]
                    occupied = self.model.NewBoolVar(f"occupied_{class_name}_{day}_{period}")
                    
                    # Une période est occupée si au moins un cours y est
                    course_vars = []
                    for course in self.courses:
                        if class_name in (course.get("_classes") or []):
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                course_vars.append(self.schedule_vars[var_name])
                    
                    if course_vars:
                        # occupied = OR(course_vars)
                        self.model.Add(sum(course_vars) >= occupied)
                        self.model.Add(sum(course_vars) <= len(course_vars) * occupied)
                        period_vars[period] = occupied
                
                if not period_vars:
                    continue
                
                # La classe a des cours ce jour si au moins une période est occupée
                all_periods = list(period_vars.values())
                self.model.Add(sum(all_periods) >= has_courses)
                self.model.Add(sum(all_periods) <= len(all_periods) * has_courses)

                # CONTRAINTE ZÉRO-TROU FORTE: un seul bloc continu par jour s'il y a des cours
                sorted_periods = sorted(period_vars.keys())
                starts = []
                ends = []
                for idx, p in enumerate(sorted_periods):
                    v = period_vars[p]
                    # start at p
                    s = self.model.NewBoolVar(f"start_{class_name}_{day}_{p}")
                    if idx == 0:
                        self.model.Add(s == v)
                    else:
                        prev_v = period_vars[sorted_periods[idx-1]]
                        self.model.Add(s <= v)
                        self.model.Add(s <= 1 - prev_v)
                        self.model.Add(s >= v - prev_v)
                    starts.append(s)
                    
                    # end at p
                    e = self.model.NewBoolVar(f"end_{class_name}_{day}_{p}")
                    if idx == len(sorted_periods) - 1:
                        self.model.Add(e == v)
                    else:
                        next_v = period_vars[sorted_periods[idx+1]]
                        self.model.Add(e <= v)
                        self.model.Add(e <= 1 - next_v)
                        self.model.Add(e >= v - next_v)
                    ends.append(e)

                # Si des cours existent ce jour: exactement un début et une fin
                self.model.Add(sum(starts) == has_courses)
                self.model.Add(sum(ends) == has_courses)
        
        logger.info("  ✓ Contraintes zéro trou ajoutées")
    
    def _add_subject_grouping_constraints(self):
        """Regrouper les cours de même matière sur peu de jours"""
        logger.info("→ Contraintes de regroupement des matières...")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Grouper les cours par matière
            subjects_courses = {}
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subject = course.get("subject", "")
                    if subject:
                        if subject not in subjects_courses:
                            subjects_courses[subject] = []
                        subjects_courses[subject].append(course)
            
            # Pour chaque matière
            for subject, courses in subjects_courses.items():
                total_hours = sum(c["hours"] for c in courses)
                
                if total_hours >= 2:
                    # Compter sur combien de jours cette matière est enseignée
                    days_used = []
                    
                    for day in range(6):  # 0-5
                        day_has_subject = self.model.NewBoolVar(f"has_{class_name}_{subject}_{day}")
                        
                        day_vars = []
                        for course in courses:
                            for slot in self.time_slots:
                                if slot["day_of_week"] == day:
                                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                    if var_name in self.schedule_vars:
                                        day_vars.append(self.schedule_vars[var_name])
                        
                        if day_vars:
                            # day_has_subject = 1 si au moins un cours ce jour
                            self.model.Add(sum(day_vars) >= day_has_subject)
                            self.model.Add(sum(day_vars) <= len(day_vars) * day_has_subject)
                            days_used.append(day_has_subject)
                    
                    # Limiter le nombre de jours
                    if days_used:
                        max_days = min(3, (total_hours + 1) // 2)  # 2h->1j, 3-4h->2j, 5-6h->3j
                        self.model.Add(sum(days_used) <= max_days)
                        
                        # Favoriser les jours consécutifs (soft)
                        # Sera géré dans l'objectif
        
        logger.info("  ✓ Contraintes de regroupement ajoutées")
    
    def _add_school_specific_constraints(self):
        """Contraintes spécifiques à l'école"""
        logger.info("→ Contraintes spécifiques école...")
        
        # 1. Lundi après-midi : réunions pour profs de חינוך/שיח בוקר
        homeroom_subjects = {"חינוך", "שיח בוקר"}
        homeroom_teachers = set()
        
        for course in self.courses:
            subject = course.get("subject", "").strip()
            if subject in homeroom_subjects:
                for t in (course.get("teacher_names") or "").split(","):
                    if t.strip():
                        homeroom_teachers.add(t.strip())
        
        # Bloquer lundi périodes 6-8 pour ces profs
        monday_afternoon = [s for s in self.time_slots 
                           if s["day_of_week"] == 1 and 6 <= s["period_number"] <= 8]
        
        for course in self.courses:
            teachers = set(t.strip() for t in (course.get("teacher_names") or "").split(",") if t.strip())
            if teachers & homeroom_teachers:
                for slot in monday_afternoon:
                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                    if var_name in self.schedule_vars:
                        self.model.Add(self.schedule_vars[var_name] == 0)
        
        # 2. Limite quotidienne par matière (3h ou 4h pour lycée)
        hs_grades = {"י", "יא", "יב"}
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            grade = class_obj.get("grade", "")
            daily_limit = 4 if grade in hs_grades else 3
            
            # Collecter matières pour cette classe
            subjects = set()
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    subjects.add(course.get("subject", ""))
            
            for subject in subjects:
                if not subject:
                    continue
                    
                for day in range(6):
                    day_vars = []
                    for course in self.courses:
                        if (class_name in (course.get("class_list") or "").split(",") and
                            course.get("subject") == subject):
                            for slot in self.time_slots:
                                if slot["day_of_week"] == day:
                                    var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                    if var_name in self.schedule_vars:
                                        day_vars.append(self.schedule_vars[var_name])
                    
                    if day_vars:
                        self.model.Add(sum(day_vars) <= daily_limit)
        
        logger.info("  ✓ Contraintes école ajoutées")
    
    def _add_start_first_period_constraints(self):
        """Les classes commencent à la première période chaque jour"""
        logger.info("→ Contraintes début première période...")
        
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            for day in range(5):  # 0-4 (dimanche-jeudi, pas vendredi)
                # Trouver la première période du jour
                day_slots = [s for s in self.time_slots if s["day_of_week"] == day]
                if not day_slots:
                    continue
                    
                day_slots.sort(key=lambda s: s["period_number"])
                first_slot = day_slots[0]
                
                # Variables pour savoir si la classe a cours ce jour
                has_any_course = self.model.NewBoolVar(f"has_any_{class_name}_{day}")
                
                all_day_vars = []
                first_period_vars = []
                
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        # Toutes les variables du jour
                        for slot in day_slots:
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                all_day_vars.append(self.schedule_vars[var_name])
                                
                                # Variables de la première période
                                if slot["slot_id"] == first_slot["slot_id"]:
                                    first_period_vars.append(self.schedule_vars[var_name])
                
                if all_day_vars and first_period_vars:
                    # has_any_course = 1 si au moins un cours ce jour
                    self.model.Add(sum(all_day_vars) >= has_any_course)
                    
                    # Si has_any_course = 1, alors au moins un cours à la première période
                    self.model.Add(sum(first_period_vars) >= 1).OnlyEnforceIf(has_any_course)
        
        logger.info("  ✓ Contraintes première période ajoutées")
    
    def _add_quality_objectives(self):
        """Objectifs pour améliorer la qualité"""
        logger.info("→ Objectifs de qualité...")
        
        penalties = []
        
        # 1. Favoriser fortement les blocs de 2h et pénaliser le manque
        for var_name, var in self.block_vars.items():
            penalties.append(var * -15)  # bonus (négatif)
        for shortage in self.block_shortage_vars:
            penalties.append(shortage * 80)  # pénalité forte si on manque des blocs requis
        
        # 2. Pénaliser les matières difficiles l'après-midi
            difficult_subjects = ['מתמטיקה', 'פיזיקה', 'כימיה', 'math', 'physique', 'chimie']
            exempt_subjects = {'מגמה'}
        
        for course in self.courses:
            subj_raw = course.get("subject", "")
            subject = subj_raw.lower()
            if subj_raw not in exempt_subjects and any(s in subject for s in difficult_subjects):
                for slot in self.time_slots:
                    if slot["period_number"] >= 7:  # Après-midi
                        var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                        if var_name in self.schedule_vars:
                            penalty = (slot["period_number"] - 6) * 15
                            penalties.append(self.schedule_vars[var_name] * penalty)
        
        # 3. Équilibrer la charge hebdomadaire des classes
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            
            # Pénaliser les journées très chargées (>8h)
            for day in range(5):
                day_vars = []
                for course in self.courses:
                    if class_name in (course.get("class_list") or "").split(","):
                        for slot in self.time_slots:
                            if slot["day_of_week"] == day:
                                var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                                if var_name in self.schedule_vars:
                                    day_vars.append(self.schedule_vars[var_name])
                
                if day_vars:
                    # Variable pour excès de charge
                    excess = self.model.NewIntVar(0, 10, f"excess_{class_name}_{day}")
                    self.model.Add(sum(day_vars) - 8 <= excess)
                    self.model.Add(excess >= 0)
                    penalties.append(excess * 30)
        
        # 4. Favoriser l'utilisation du dimanche
        # Pénaliser si dimanche sous-utilisé
        sunday_usage = []
        for class_obj in self.classes:
            class_name = class_obj["class_name"]
            sunday_vars = []
            
            for course in self.courses:
                if class_name in (course.get("class_list") or "").split(","):
                    for slot in self.time_slots:
                        if slot["day_of_week"] == 0:  # Dimanche
                            var_name = f"course_{course['course_id']}_slot_{slot['slot_id']}"
                            if var_name in self.schedule_vars:
                                sunday_vars.append(self.schedule_vars[var_name])
            
            if sunday_vars:
                # Pénaliser si moins de 4 cours le dimanche
                sunday_count = sum(sunday_vars)
                sunday_shortage = self.model.NewIntVar(0, 4, f"sunday_short_{class_name}")
                self.model.Add(4 - sunday_count <= sunday_shortage)
                self.model.Add(sunday_shortage >= 0)
                penalties.append(sunday_shortage * 10)
        
        # Appliquer l'objectif
        if penalties:
            self.model.Minimize(sum(penalties))
            logger.info(f"  ✓ {len(penalties)} composantes d'objectif ajoutées")
    
    def solve(self, time_limit=600):
        """Résoudre le problème d'optimisation"""
        logger.info(f"\n=== RÉSOLUTION (limite: {time_limit}s) ===")
        
        self.solver.parameters.max_time_in_seconds = time_limit
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = True
        
        start_time = time.time()
        status = self.solver.Solve(self.model)
        self.solve_time = time.time() - start_time
        
        logger.info(f"Statut: {self.solver.StatusName(status)}")
        logger.info(f"Temps: {self.solve_time:.2f}s")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self._extract_solution()
        else:
            logger.error("Aucune solution trouvée!")
            return None
    
    def _extract_solution(self):
        """Extraire la solution du modèle"""
        schedule = []
        
        for course in self.courses:
            course_id = course["course_id"]
            assigned_slots = []
            
            for slot in self.time_slots:
                var_name = f"course_{course_id}_slot_{slot['slot_id']}"
                if var_name in self.schedule_vars:
                    if self.solver.Value(self.schedule_vars[var_name]) == 1:
                        assigned_slots.append(slot)
            
            # Créer une entrée pour chaque créneau assigné
            for slot in assigned_slots:
                # Gérer les cours parallèles avec plusieurs profs
                teachers = course.get("teacher_names", "").split(",")
                classes = course.get("class_list", "").split(",")
                
                for class_name in classes:
                    schedule.append({
                        "teacher_name": course.get("teacher_names", ""),
                        "subject": course.get("subject", ""),
                        "class_name": class_name.strip(),
                        "day_of_week": slot["day_of_week"],
                        "period_number": slot["period_number"],
                        "start_time": slot["start_time"],
                        "end_time": slot["end_time"],
                        "is_parallel": course.get("is_parallel", False),
                        "group_id": course.get("group_id"),
                        "course_id": course_id
                    })
        
        # Analyser la qualité
        quality = self._analyze_solution_quality(schedule)
        logger.info(f"\n=== QUALITÉ DE LA SOLUTION ===")
        logger.info(f"Score global: {quality['score']}/100")
        logger.info(f"Cours le dimanche: {quality['sunday_usage']} cours")
        logger.info(f"Trous détectés: {quality['gaps_count']}")
        logger.info(f"Matières bien regroupées: {quality['grouped_subjects']}%")
        
        return schedule
    
    def _analyze_solution_quality(self, schedule):
        """Analyser la qualité de la solution"""
        quality = {
            "score": 100,
            "gaps_count": 0,
            "sunday_usage": 0,
            "grouped_subjects": 0,
            "parallel_sync": True
        }
        
        # Compter les cours du dimanche
        sunday_courses = [e for e in schedule if e["day_of_week"] == 0]
        quality["sunday_usage"] = len(sunday_courses)
        
        # Vérifier les trous (par classe par jour)
        by_class_day = {}
        for entry in schedule:
            key = (entry["class_name"], entry["day_of_week"])
            if key not in by_class_day:
                by_class_day[key] = []
            by_class_day[key].append(entry["period_number"])
        
        for (class_name, day), periods in by_class_day.items():
            periods = sorted(periods)
            if len(periods) > 1:
                # Vérifier les trous
                for i in range(len(periods) - 1):
                    if periods[i+1] - periods[i] > 1:
                        quality["gaps_count"] += 1
                        quality["score"] -= 5
        
        # Vérifier le regroupement des matières
        by_class_subject = {}
        for entry in schedule:
            key = (entry["class_name"], entry["subject"])
            if key not in by_class_subject:
                by_class_subject[key] = set()
            by_class_subject[key].add(entry["day_of_week"])
        
        well_grouped = 0
        total = 0
        for (class_name, subject), days in by_class_subject.items():
            total += 1
            if len(days) <= 2:  # Bien regroupé si sur 2 jours max
                well_grouped += 1
        
        if total > 0:
            quality["grouped_subjects"] = int(100 * well_grouped / total)
        
        return quality
    
    def save_schedule(self, schedule):
        """Sauvegarder l'emploi du temps dans la base de données"""
        if not schedule:
            return None
            
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Créer un nouveau schedule
            metadata = {
                "solver": "pedagogical_v2",
                "solve_time": self.solve_time,
                "quality": self._analyze_solution_quality(schedule),
                "config": self.config,
                "timestamp": datetime.now().isoformat()
            }
            
            cur.execute("""
                INSERT INTO schedules (status, metadata)
                VALUES ('active', %s)
                RETURNING schedule_id
            """, (json.dumps(metadata),))
            
            schedule_id = cur.fetchone()[0]
            
            # Insérer les entrées
            for entry in schedule:
                cur.execute("""
                    INSERT INTO schedule_entries (
                        schedule_id, teacher_name, subject_name, class_name,
                        day_of_week, period_number, room,
                        is_parallel_group, group_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    schedule_id,
                    entry.get("teacher_name", ""),
                    entry.get("subject", ""),
                    entry.get("class_name", ""),
                    entry.get("day_of_week"),
                    entry.get("period_number"),
                    entry.get("room", ""),
                    entry.get("is_parallel", False),
                    entry.get("group_id")
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
    
    def get_quality_score(self):
        """Retourner le score de qualité de la dernière solution"""
        if hasattr(self, '_last_quality'):
            return self._last_quality.get('score', 0)
        return 0

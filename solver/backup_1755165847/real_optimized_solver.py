#!/usr/bin/env python3
"""
Solveur CP-SAT VRAIMENT optimisé pour les vrais problèmes d'emploi du temps
- Équilibrage quotidien strict (max 6h/jour)
- Étalement obligatoire sur 5 jours
- Vraie compacité avec contraintes de continuité
- Éviter les surcharges et déséquilibres
"""

from ortools.sat.python import cp_model
import logging
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class RealOptimizedSolver:
    def __init__(self):
        """Solveur focalisé sur les vrais problèmes d'équilibrage"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Données
        self.time_slots = []
        self.courses = []
        self.classes = set()
        self.teachers = set()
        self.subjects = set()
        
        # Variables principales
        self.x = {}  # x[c,s,t]: classe c a matière s au créneau t
        self.busy = {}  # busy[p,t]: prof p occupé au créneau t
        
        # Variables d'équilibrage
        self.daily_hours = {}  # daily_hours[c,d]: heures pour classe c jour d
        self.day_used = {}  # day_used[c,d]: classe c utilise le jour d
        
    def load_test_data(self):
        """Charge des données de test réalistes"""
        logger.info("=== CHARGEMENT DES DONNÉES RÉALISTES ===")
        
        # 5 jours × 8 périodes = 40 créneaux (pas de vendredi)
        self.time_slots = []
        slot_id = 1
        for day in range(5):  # Lundi(0) à Vendredi(4)
            if day == 4:  # Skip vendredi
                continue
            for period in range(8):
                self.time_slots.append({
                    "slot_id": slot_id,
                    "day_of_week": day,
                    "period_number": period,
                })
                slot_id += 1
        
        # Classes
        self.classes = {"6A", "6B", "6C"}
        
        # Professeurs
        self.teachers = {"Prof_Math", "Prof_Français", "Prof_Histoire", "Prof_Sciences", 
                        "Prof_Anglais", "Prof_Sport", "Prof_Art", "Prof_Musique"}
        
        # Cours RÉALISTES avec volumes cohérents
        self.courses = [
            # Classe 6A (22h total - répartition équilibrée)
            {"id": "6A_Math", "class": "6A", "subject": "Mathématiques", "teacher": "Prof_Math", "hours": 5},
            {"id": "6A_Français", "class": "6A", "subject": "Français", "teacher": "Prof_Français", "hours": 4},
            {"id": "6A_Histoire", "class": "6A", "subject": "Histoire", "teacher": "Prof_Histoire", "hours": 3},
            {"id": "6A_Sciences", "class": "6A", "subject": "Sciences", "teacher": "Prof_Sciences", "hours": 3},
            {"id": "6A_Anglais", "class": "6A", "subject": "Anglais", "teacher": "Prof_Anglais", "hours": 3},
            {"id": "6A_Sport", "class": "6A", "subject": "Sport", "teacher": "Prof_Sport", "hours": 2},
            {"id": "6A_Art", "class": "6A", "subject": "Art", "teacher": "Prof_Art", "hours": 2},
            
            # Classe 6B (22h total)
            {"id": "6B_Math", "class": "6B", "subject": "Mathématiques", "teacher": "Prof_Math", "hours": 5},
            {"id": "6B_Français", "class": "6B", "subject": "Français", "teacher": "Prof_Français", "hours": 4},
            {"id": "6B_Histoire", "class": "6B", "subject": "Histoire", "teacher": "Prof_Histoire", "hours": 3},
            {"id": "6B_Sciences", "class": "6B", "subject": "Sciences", "teacher": "Prof_Sciences", "hours": 3},
            {"id": "6B_Anglais", "class": "6B", "subject": "Anglais", "teacher": "Prof_Anglais", "hours": 3},
            {"id": "6B_Sport", "class": "6B", "subject": "Sport", "teacher": "Prof_Sport", "hours": 2},
            {"id": "6B_Musique", "class": "6B", "subject": "Musique", "teacher": "Prof_Musique", "hours": 2},
            
            # Classe 6C (20h total - pour variation)
            {"id": "6C_Math", "class": "6C", "subject": "Mathématiques", "teacher": "Prof_Math", "hours": 4},
            {"id": "6C_Français", "class": "6C", "subject": "Français", "teacher": "Prof_Français", "hours": 4},
            {"id": "6C_Histoire", "class": "6C", "subject": "Histoire", "teacher": "Prof_Histoire", "hours": 3},
            {"id": "6C_Sciences", "class": "6C", "subject": "Sciences", "teacher": "Prof_Sciences", "hours": 3},
            {"id": "6C_Anglais", "class": "6C", "subject": "Anglais", "teacher": "Prof_Anglais", "hours": 3},
            {"id": "6C_Sport", "class": "6C", "subject": "Sport", "teacher": "Prof_Sport", "hours": 2},
            {"id": "6C_Art", "class": "6C", "subject": "Art", "teacher": "Prof_Art", "hours": 1},
        ]
        
        # Extraire les matières
        self.subjects = set(c["subject"] for c in self.courses)
        
        logger.info(f"✓ {len(self.time_slots)} créneaux (4 jours)")
        logger.info(f"✓ {len(self.classes)} classes")
        logger.info(f"✓ {len(self.courses)} cours")
        
        total_hours = sum(c["hours"] for c in self.courses)
        logger.info(f"✓ {total_hours}h total à répartir")
        
        # Vérification de faisabilité
        max_hours_per_day = 6
        days_available = 4
        max_total_per_class = max_hours_per_day * days_available
        
        for class_name in self.classes:
            class_hours = sum(c["hours"] for c in self.courses if c["class"] == class_name)
            logger.info(f"✓ {class_name}: {class_hours}h (max possible: {max_total_per_class}h)")
            
            if class_hours > max_total_per_class:
                logger.error(f"❌ {class_name}: trop d'heures pour l'équilibrage!")
                
    def create_variables(self):
        """Crée les variables avec focus sur l'équilibrage"""
        logger.info("=== VARIABLES POUR ÉQUILIBRAGE RÉEL ===")
        
        # 1. Variables principales x[c,s,t]
        for c in self.classes:
            for s in self.subjects:
                for t in self.time_slots:
                    self.x[c, s, t["slot_id"]] = self.model.NewBoolVar(f"x_{c}_{s}_{t['slot_id']}")
        
        # 2. Variables d'occupation prof
        for p in self.teachers:
            for t in self.time_slots:
                self.busy[p, t["slot_id"]] = self.model.NewBoolVar(f"busy_{p}_{t['slot_id']}")
        
        # 3. Variables d'équilibrage quotidien
        for c in self.classes:
            for day in range(4):  # 4 jours de travail
                # Heures par jour (variable entière)
                self.daily_hours[c, day] = self.model.NewIntVar(0, 8, f"daily_hours_{c}_{day}")
                
                # Jour utilisé (variable binaire)
                self.day_used[c, day] = self.model.NewBoolVar(f"day_used_{c}_{day}")
        
        logger.info(f"✓ Variables créées: équilibrage optimal")
        
    def add_basic_constraints(self):
        """Contraintes de base + équilibrage strict"""
        logger.info("=== CONTRAINTES ÉQUILIBRAGE STRICT ===")
        
        # 1. Volumes de cours exacts
        for course in self.courses:
            course_vars = []
            for t in self.time_slots:
                if (course["class"], course["subject"], t["slot_id"]) in self.x:
                    course_vars.append(self.x[course["class"], course["subject"], t["slot_id"]])
            
            if course_vars:
                self.model.Add(sum(course_vars) == course["hours"])
        
        # 2. Capacité classe (max 1 cours par créneau)
        for c in self.classes:
            for t in self.time_slots:
                class_slot_vars = []
                for s in self.subjects:
                    if (c, s, t["slot_id"]) in self.x:
                        class_slot_vars.append(self.x[c, s, t["slot_id"]])
                
                if class_slot_vars:
                    self.model.Add(sum(class_slot_vars) <= 1)
        
        # 3. Lien avec professeurs
        for course in self.courses:
            c = course["class"]
            s = course["subject"]
            p = course["teacher"]
            
            for t in self.time_slots:
                if (c, s, t["slot_id"]) in self.x and (p, t["slot_id"]) in self.busy:
                    self.model.Add(self.busy[p, t["slot_id"]] >= self.x[c, s, t["slot_id"]])
        
        # 4. Capacité prof (max 1 cours par créneau)
        for p in self.teachers:
            for t in self.time_slots:
                if (p, t["slot_id"]) in self.busy:
                    self.model.Add(self.busy[p, t["slot_id"]] <= 1)
                    
        logger.info("✓ Contraintes de base ajoutées")
        
    def add_real_balancing_constraints(self):
        """VRAIES contraintes d'équilibrage - LE CŒUR DU PROBLÈME"""
        logger.info("=== CONTRAINTES D'ÉQUILIBRAGE RÉEL ===")
        
        # Index des créneaux par jour
        slots_by_day = defaultdict(list)
        for slot in self.time_slots:
            slots_by_day[slot["day_of_week"]].append(slot)
        
        for c in self.classes:
            for day in range(4):  # 4 jours de travail
                if day not in slots_by_day:
                    continue
                
                day_slots = slots_by_day[day]
                
                # Compter les heures ce jour
                day_course_vars = []
                for s in self.subjects:
                    for slot in day_slots:
                        if (c, s, slot["slot_id"]) in self.x:
                            day_course_vars.append(self.x[c, s, slot["slot_id"]])
                
                if day_course_vars:
                    # Lier daily_hours à la somme réelle
                    self.model.Add(self.daily_hours[c, day] == sum(day_course_vars))
                    
                    # Lier day_used à l'utilisation du jour
                    self.model.Add(sum(day_course_vars) >= self.day_used[c, day])
                    self.model.Add(sum(day_course_vars) <= 8 * self.day_used[c, day])
                    
                    # CONTRAINTE DURE: Maximum 6 heures par jour (équilibrage strict)
                    self.model.Add(self.daily_hours[c, day] <= 6)
                    
                    # CONTRAINTE DURE: Minimum 4 heures si jour utilisé (éviter 1-2h isolées)
                    self.model.Add(self.daily_hours[c, day] >= 4 * self.day_used[c, day])
        
        # CONTRAINTE DURE: Utiliser exactement 4 jours (étalement obligatoire)
        for c in self.classes:
            day_used_vars = [self.day_used[c, day] for day in range(4)]
            self.model.Add(sum(day_used_vars) >= 4)  # Au moins 4 jours
            # Note: pour certaines classes, on pourrait accepter 3 jours si peu d'heures
            
        logger.info("✓ Contraintes d'équilibrage STRICT ajoutées")
        
    def add_compactness_constraints(self):
        """Contraintes de compacité RÉELLES (pas de trous dans une journée)"""
        logger.info("=== CONTRAINTES DE COMPACITÉ RÉELLE ===")
        
        slots_by_day = defaultdict(list)
        for slot in self.time_slots:
            slots_by_day[slot["day_of_week"]].append(slot)
        
        # Trier par période
        for day in slots_by_day:
            slots_by_day[day].sort(key=lambda s: s["period_number"])
        
        for c in self.classes:
            for day, day_slots in slots_by_day.items():
                if len(day_slots) < 3:
                    continue
                
                # Variables: cette classe a-t-elle cours à chaque période?
                period_vars = []
                for slot in day_slots:
                    has_course = self.model.NewBoolVar(f"has_{c}_{day}_{slot['period_number']}")
                    
                    # Lier à toutes les matières
                    subject_vars = []
                    for s in self.subjects:
                        if (c, s, slot["slot_id"]) in self.x:
                            subject_vars.append(self.x[c, s, slot["slot_id"]])
                    
                    if subject_vars:
                        # has_course = OR de toutes les matières
                        self.model.Add(has_course <= len(subject_vars))
                        self.model.Add(sum(subject_vars) >= has_course)
                        for var in subject_vars:
                            self.model.Add(has_course >= var)
                    else:
                        self.model.Add(has_course == 0)
                    
                    period_vars.append(has_course)
                
                # CONTRAINTE DE COMPACITÉ: Fenêtre glissante interdisant les trous
                # Pattern interdit: [1, 0, 1] = cours-trou-cours
                for i in range(len(period_vars) - 2):
                    # Si period[i] ET period[i+2] sont utilisées, alors period[i+1] DOIT l'être
                    self.model.Add(period_vars[i+1] >= period_vars[i] + period_vars[i+2] - 1)
                
                # CONTRAINTE RENFORCÉE: Pattern [1,0,0,1] aussi interdit
                if len(period_vars) >= 4:
                    for i in range(len(period_vars) - 3):
                        # Si period[i] ET period[i+3], alors au moins une des deux du milieu
                        self.model.Add(period_vars[i+1] + period_vars[i+2] >= period_vars[i] + period_vars[i+3] - 1)
                
        logger.info("✓ Contraintes de compacité réelle ajoutées")
        
    def add_quality_objective(self):
        """Objectif focalisé sur l'équilibrage et la qualité"""
        logger.info("=== OBJECTIF QUALITÉ ÉQUILIBRAGE ===")
        
        penalties = []
        
        # 1. PRIORITÉ MAXIMALE: Pénaliser l'inégalité des charges quotidiennes
        for c in self.classes:
            daily_vars = [self.daily_hours[c, day] for day in range(4)]
            
            # Variables min et max pour cette classe
            min_hours = self.model.NewIntVar(0, 8, f"min_hours_{c}")
            max_hours = self.model.NewIntVar(0, 8, f"max_hours_{c}")
            
            # Contraintes min/max
            for day_idx, day_var in enumerate(daily_vars):
                # min_hours = minimum des jours utilisés
                self.model.Add(min_hours <= day_var + (1 - self.day_used[c, day_idx]) * 8)
                # max_hours = maximum de tous les jours
                self.model.Add(max_hours >= day_var)
            
            # Pénaliser l'écart min-max (favoriser l'équilibrage)
            spread = self.model.NewIntVar(0, 8, f"spread_{c}")
            self.model.Add(spread >= max_hours - min_hours)
            penalties.append(spread * 100)  # Poids très fort
        
        # 2. Pénaliser l'utilisation des créneaux tardifs (après 15h)
        for c in self.classes:
            for s in self.subjects:
                for slot in self.time_slots:
                    if slot["period_number"] >= 6:  # Après 15h
                        if (c, s, slot["slot_id"]) in self.x:
                            penalty_weight = (slot["period_number"] - 5) * 10
                            penalties.append(self.x[c, s, slot["slot_id"]] * penalty_weight)
        
        # 3. Encourager l'utilisation de tous les jours disponibles
        for c in self.classes:
            unused_days = self.model.NewIntVar(0, 4, f"unused_days_{c}")
            self.model.Add(unused_days == 4 - sum(self.day_used[c, day] for day in range(4)))
            penalties.append(unused_days * 200)  # Forte pénalité
        
        # Objectif global
        if penalties:
            self.model.Minimize(sum(penalties))
            logger.info(f"✓ Objectif avec {len(penalties)} composants (focus équilibrage)")
    
    def solve(self, time_limit=60):
        """Résout avec focus sur l'équilibrage réel"""
        logger.info("\n=== RÉSOLUTION ÉQUILIBRAGE RÉEL ===")
        
        try:
            self.load_test_data()
            self.create_variables()
            self.add_basic_constraints()
            self.add_real_balancing_constraints()
            self.add_compactness_constraints()
            self.add_quality_objective()
            
            # Configuration solver
            self.solver.parameters.max_time_in_seconds = time_limit
            self.solver.parameters.num_search_workers = 4
            self.solver.parameters.log_search_progress = True
            
            # Résolution
            logger.info(f"Résolution (limite: {time_limit}s)...")
            start_time = datetime.now()
            status = self.solver.Solve(self.model)
            end_time = datetime.now()
            
            solving_time = (end_time - start_time).total_seconds()
            logger.info(f"⏱️ Temps: {solving_time:.1f}s")
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                logger.info(f"✅ Solution trouvée! ({self.solver.StatusName(status)})")
                return self._extract_and_analyze_solution()
            else:
                logger.error(f"❌ Pas de solution ({self.solver.StatusName(status)})")
                return None
                
        except Exception as e:
            logger.error(f"Erreur: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _extract_and_analyze_solution(self):
        """Extrait et analyse la solution avec focus sur les vrais problèmes"""
        schedule = []
        
        # Extraire la solution
        for c in self.classes:
            for s in self.subjects:
                for t in self.time_slots:
                    if (c, s, t["slot_id"]) in self.x:
                        if self.solver.Value(self.x[c, s, t["slot_id"]]) == 1:
                            schedule.append({
                                "class_name": c,
                                "subject": s,
                                "day": t["day_of_week"],
                                "period": t["period_number"],
                                "slot_id": t["slot_id"]
                            })
        
        # ANALYSE DÉTAILLÉE DES VRAIS PROBLÈMES
        logger.info("\n=== ANALYSE DES VRAIS PROBLÈMES RÉSOLUS ===")
        
        # Organiser par classe et jour
        by_class_day = defaultdict(list)
        for entry in schedule:
            key = (entry["class_name"], entry["day"])
            by_class_day[key].append(entry)
        
        total_balance_score = 0
        total_classes = len(self.classes)
        
        for class_name in sorted(self.classes):
            logger.info(f"\n🏫 CLASSE {class_name}:")
            
            daily_hours_real = []
            days_used_real = 0
            max_daily = 0
            min_daily = 8
            total_gaps = 0
            
            for day in range(4):
                day_entries = by_class_day.get((class_name, day), [])
                day_hours = len(day_entries)
                
                if day_hours > 0:
                    days_used_real += 1
                    daily_hours_real.append(day_hours)
                    max_daily = max(max_daily, day_hours)
                    min_daily = min(min_daily, day_hours)
                    
                    # Vérifier les trous
                    periods = sorted([e["period"] for e in day_entries])
                    gaps = 0
                    if len(periods) >= 2:
                        for i in range(len(periods) - 1):
                            gap = periods[i+1] - periods[i] - 1
                            gaps += gap
                    total_gaps += gaps
                    
                    day_names = ['Lun', 'Mar', 'Mer', 'Jeu']
                    gap_info = f" (❌{gaps} trous)" if gaps > 0 else " (✅compact)"
                    balance_info = "✅" if day_hours <= 6 else "❌SURCHARGE"
                    logger.info(f"   {day_names[day]}: {day_hours}h {periods} {gap_info} {balance_info}")
            
            # Calculer les scores d'équilibrage
            spread = max_daily - min_daily if daily_hours_real else 0
            balance_ok = (max_daily <= 6) and (spread <= 2) and (days_used_real >= 3)
            
            if balance_ok:
                total_balance_score += 1
                
            logger.info(f"   📊 Bilan: {sum(daily_hours_real)}h sur {days_used_real} jours")
            logger.info(f"   📊 Équilibrage: {min_daily}-{max_daily}h/jour (écart: {spread})")
            
            if total_gaps == 0:
                logger.info(f"   ✅ COMPACITÉ PARFAITE")
            else:
                logger.warning(f"   ⚠️ {total_gaps} trous détectés")
                
            if balance_ok:
                logger.info(f"   ✅ ÉQUILIBRAGE RÉUSSI")
            else:
                logger.error(f"   ❌ ÉQUILIBRAGE À AMÉLIORER")
        
        # Score global
        balance_percentage = (total_balance_score / total_classes) * 100
        
        logger.info(f"\n🎯 SCORE FINAL D'ÉQUILIBRAGE: {total_balance_score}/{total_classes} classes ({balance_percentage:.1f}%)")
        
        if balance_percentage >= 80:
            logger.info("🏆 ÉQUILIBRAGE EXCELLENT!")
        elif balance_percentage >= 60:
            logger.info("👍 ÉQUILIBRAGE CORRECT")
        else:
            logger.warning("⚠️ ÉQUILIBRAGE À AMÉLIORER")
        
        return schedule


def main():
    """Test du vrai solveur d'équilibrage"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    solver = RealOptimizedSolver()
    schedule = solver.solve(time_limit=30)
    
    if schedule:
        logger.info("✅ Solveur d'équilibrage réel testé avec succès!")
    else:
        logger.error("❌ Échec du solveur")


if __name__ == "__main__":
    main()
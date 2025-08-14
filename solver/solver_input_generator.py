#!/usr/bin/env python3
"""
Générateur d'emploi du temps utilisant UNIQUEMENT les données de solver_input
Remplace complètement les anciennes données
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from ortools.sat.python import cp_model
import logging
import json
from datetime import datetime
import random

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SolverInputGenerator:
    """Générateur qui utilise UNIQUEMENT solver_input"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Données chargées depuis solver_input
        self.courses = []
        self.time_slots = []
        self.classes = set()
        self.teachers = set()
        self.subjects = set()
        
        # Variables de décision
        self.course_vars = {}  # {(course_id, day, period): var}
        
    def load_solver_input_data(self):
        """Charge les données depuis solver_input UNIQUEMENT"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Charger tous les cours depuis solver_input
            cur.execute("""
                SELECT 
                    course_id,
                    class_list,
                    subject,
                    hours,
                    teacher_names,
                    work_days,
                    grade,
                    is_parallel
                FROM solver_input 
                ORDER BY course_id
            """)
            
            raw_courses = cur.fetchall()
            logger.info(f"Chargé {len(raw_courses)} cours depuis solver_input")
            
            # Traiter chaque cours
            for raw_course in raw_courses:
                # Diviser class_list en classes individuelles
                class_names = [c.strip() for c in raw_course['class_list'].split(',') if c.strip()]
                
                # Diviser teacher_names en professeurs individuels
                teacher_names = []
                if raw_course['teacher_names']:
                    teachers = [t.strip() for t in raw_course['teacher_names'].split(',') if t.strip()]
                    teacher_names = [t for t in teachers if t != 'לא משובץ']
                
                # Créer un cours pour chaque classe
                for class_name in class_names:
                    course = {
                        'course_id': raw_course['course_id'],
                        'class_name': class_name.strip(),
                        'subject': raw_course['subject'],
                        'hours': raw_course['hours'] or 1,
                        'teachers': teacher_names,
                        'work_days': raw_course['work_days'] or '0,1,2,3,4',
                        'grade': raw_course['grade'],
                        'is_parallel': raw_course['is_parallel'] or False
                    }
                    
                    self.courses.append(course)
                    self.classes.add(class_name.strip())
                    self.subjects.add(raw_course['subject'])
                    for teacher in teacher_names:
                        self.teachers.add(teacher)
            
            logger.info(f"Données traitées:")
            logger.info(f"  - {len(self.courses)} cours individuels")
            logger.info(f"  - {len(self.classes)} classes: {sorted(list(self.classes))[:5]}...")
            logger.info(f"  - {len(self.subjects)} matières: {sorted(list(self.subjects))[:5]}...")
            logger.info(f"  - {len(self.teachers)} professeurs")
            
            # Créer les créneaux horaires standards
            self.create_time_slots()
            
        finally:
            cur.close()
            conn.close()
    
    def create_time_slots(self):
        """Crée les créneaux horaires standards"""
        days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi']  # Pas de vendredi/samedi
        periods_per_day = 8  # 8 périodes par jour
        
        slot_id = 1
        for day_idx, day_name in enumerate(days):
            for period in range(periods_per_day):
                start_hour = 8 + (period * 45) // 60
                start_min = (8 * 60 + period * 45) % 60
                end_hour = 8 + ((period + 1) * 45) // 60  
                end_min = (8 * 60 + (period + 1) * 45) % 60
                
                self.time_slots.append({
                    'slot_id': slot_id,
                    'day': day_idx,
                    'period': period,
                    'day_name': day_name,
                    'start': f"{start_hour:02d}:{start_min:02d}",
                    'end': f"{end_hour:02d}:{end_min:02d}"
                })
                slot_id += 1
        
        logger.info(f"Créé {len(self.time_slots)} créneaux horaires")
    
    def create_variables(self):
        """Crée les variables de décision"""
        logger.info("Création des variables de décision...")
        
        for course in self.courses:
            for slot in self.time_slots:
                var_name = f"course_{course['course_id']}_{course['class_name']}_{slot['day']}_{slot['period']}"
                self.course_vars[(course['course_id'], course['class_name'], slot['day'], slot['period'])] = \
                    self.model.NewBoolVar(var_name)
        
        logger.info(f"Créé {len(self.course_vars)} variables de décision")
    
    def add_constraints(self):
        """Ajoute les contraintes"""
        logger.info("Ajout des contraintes...")
        
        # 1. Chaque cours doit avoir exactement ses heures requises
        for course in self.courses:
            course_slots = []
            for slot in self.time_slots:
                var_key = (course['course_id'], course['class_name'], slot['day'], slot['period'])
                if var_key in self.course_vars:
                    course_slots.append(self.course_vars[var_key])
            
            if course_slots:
                self.model.Add(sum(course_slots) == course['hours'])
        
        # 2. Une classe ne peut pas avoir deux cours simultanément
        for class_name in self.classes:
            for slot in self.time_slots:
                class_courses = []
                for course in self.courses:
                    if course['class_name'] == class_name:
                        var_key = (course['course_id'], class_name, slot['day'], slot['period'])
                        if var_key in self.course_vars:
                            class_courses.append(self.course_vars[var_key])
                
                if len(class_courses) > 1:
                    self.model.Add(sum(class_courses) <= 1)
        
        # 3. Un professeur ne peut pas enseigner deux cours simultanément
        for teacher in self.teachers:
            for slot in self.time_slots:
                teacher_courses = []
                for course in self.courses:
                    if teacher in course['teachers']:
                        var_key = (course['course_id'], course['class_name'], slot['day'], slot['period'])
                        if var_key in self.course_vars:
                            teacher_courses.append(self.course_vars[var_key])
                
                if len(teacher_courses) > 1:
                    self.model.Add(sum(teacher_courses) <= 1)
        
        # 4. Éviter les trous (optionnel - soft constraint)
        # Cette contrainte encourage les cours consécutifs
        
        logger.info("Contraintes ajoutées")
    
    def solve_schedule(self, time_limit=300):
        """Résout l'emploi du temps"""
        logger.info(f"Résolution avec time_limit={time_limit}s...")
        
        self.solver.parameters.max_time_in_seconds = time_limit
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL:
            logger.info("✅ Solution optimale trouvée")
            return self.extract_solution()
        elif status == cp_model.FEASIBLE:
            logger.info("✅ Solution faisable trouvée")
            return self.extract_solution()
        else:
            logger.error("❌ Aucune solution trouvée")
            return None
    
    def extract_solution(self):
        """Extrait la solution"""
        schedule_entries = []
        
        for course in self.courses:
            for slot in self.time_slots:
                var_key = (course['course_id'], course['class_name'], slot['day'], slot['period'])
                if var_key in self.course_vars:
                    if self.solver.Value(self.course_vars[var_key]) == 1:
                        entry = {
                            'course_id': course['course_id'],
                            'class_name': course['class_name'],
                            'subject': course['subject'],
                            'day': slot['day'],
                            'slot_index': slot['period'],
                            'teacher_names': course['teachers'],
                            'day_of_week': slot['day'],
                            'period_number': slot['period'] + 1,
                            'subject_name': course['subject']
                        }
                        schedule_entries.append(entry)
        
        logger.info(f"Solution extraite: {len(schedule_entries)} créneaux planifiés")
        return schedule_entries
    
    def save_to_database(self, schedule_entries):
        """Sauvegarde dans la base de données en remplaçant les anciennes données"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # VIDER les anciennes données
            logger.info("Suppression des anciennes données...")
            cur.execute("DELETE FROM schedule_entries")
            cur.execute("DELETE FROM schedules")
            
            # Créer un nouveau schedule
            cur.execute("""
                INSERT INTO schedules (created_at, status, metadata) 
                VALUES (NOW(), 'active', %s) 
                RETURNING schedule_id
            """, (Json({
                'source': 'solver_input',
                'method': 'cp_sat_clean',
                'total_entries': len(schedule_entries),
                'generated_at': datetime.now().isoformat()
            }),))
            
            schedule_id = cur.fetchone()[0]
            logger.info(f"Nouveau schedule créé: ID={schedule_id}")
            
            # Insérer les nouvelles entrées
            for entry in schedule_entries:
                cur.execute("""
                    INSERT INTO schedule_entries (
                        schedule_id, class_name, subject, day, slot_index,
                        teacher_names, day_of_week, period_number, subject_name
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    entry['class_name'],
                    entry['subject'], 
                    entry['day'],
                    entry['slot_index'],
                    entry['teacher_names'],
                    entry['day_of_week'],
                    entry['period_number'],
                    entry['subject_name']
                ))
            
            conn.commit()
            logger.info(f"✅ Sauvegardé {len(schedule_entries)} entrées avec schedule_id={schedule_id}")
            return schedule_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erreur sauvegarde: {e}")
            raise
        finally:
            cur.close()
            conn.close()

def generate_from_solver_input():
    """Fonction principale de génération"""
    db_config = {
        "host": "postgres",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123"
    }
    
    try:
        logger.info("=== GÉNÉRATION DEPUIS SOLVER_INPUT ===")
        
        # Créer le générateur
        generator = SolverInputGenerator(db_config)
        
        # Charger les données
        generator.load_solver_input_data()
        
        if len(generator.courses) == 0:
            logger.error("❌ Aucun cours trouvé dans solver_input")
            return {"success": False, "error": "Aucun cours dans solver_input"}
        
        # Créer les variables et contraintes
        generator.create_variables()
        generator.add_constraints()
        
        # Résoudre
        schedule_entries = generator.solve_schedule(time_limit=300)
        
        if schedule_entries is None:
            return {"success": False, "error": "Impossible de résoudre"}
        
        # Sauvegarder
        schedule_id = generator.save_to_database(schedule_entries)
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "total_entries": len(schedule_entries),
            "classes": len(generator.classes),
            "subjects": len(generator.subjects),
            "teachers": len(generator.teachers),
            "message": f"Emploi du temps généré depuis solver_input avec {len(schedule_entries)} créneaux"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur génération: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = generate_from_solver_input()
    print(json.dumps(result, indent=2))
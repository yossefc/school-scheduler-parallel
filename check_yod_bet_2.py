#!/usr/bin/env python3
"""Vérification des cours de יב-2 dans solver_input"""

import requests
import json

def check_yod_bet_2():
    """Vérifie les cours de יב-2"""
    
    try:
        # Récupérer solver_input
        response = requests.get("http://localhost:8000/api/solver_input")
        if not response.ok:
            print(f"Erreur API solver_input: {response.status_code}")
            return
        
        data = response.json()
        courses = data.get('courses', [])
        
        print("=== VERIFICATION DES COURS YOD BET 2 ===")
        print(f"Total cours dans solver_input: {len(courses)}")
        print()
        
        # Analyser par classe
        class_courses = {}
        for course in courses:
            class_list = course.get('class_list', '')
            subject = course.get('subject', '')
            hours = course.get('hours', 0)
            
            if class_list and ',' in class_list:
                # Cours parallele
                classes = [c.strip() for c in class_list.split(',')]
                for cls in classes:
                    if cls not in class_courses:
                        class_courses[cls] = []
                    class_courses[cls].append({'subject': subject, 'hours': hours})
            elif class_list:
                # Cours normal
                if class_list not in class_courses:
                    class_courses[class_list] = []
                class_courses[class_list].append({'subject': subject, 'hours': hours})
        
        # Analyser יב-2 spécifiquement
        target_class_bytes = 'יב-2'.encode('utf-8')
        target_class = target_class_bytes.decode('utf-8')
        
        print(f"Recherche de la classe: {repr(target_class)}")
        
        if target_class in class_courses:
            courses_for_class = class_courses[target_class]
            total_hours = sum(c['hours'] for c in courses_for_class)
            subjects = [c['subject'] for c in courses_for_class]
            
            print(f"TROUVE: {len(courses_for_class)} cours definis")
            print(f"Total heures prevues: {total_hours}")
            print("Matieres:")
            for subject in set(subjects):
                print(f"  - {subject}")
        else:
            print("PROBLEME: AUCUN COURS TROUVE dans solver_input!")
            print("Classes disponibles:")
            for cls in sorted(class_courses.keys()):
                if 'יב' in cls:  # Chercher toutes les classes yod-bet
                    print(f"  - {repr(cls)}")
        
        print()
        print("COMPARAISON AVEC AUTRES CLASSES YOD-BET:")
        for class_name in sorted(class_courses.keys()):
            if class_name.startswith('\u05d9\u05d1'):  # יב en Unicode
                count = len(class_courses[class_name])
                total_h = sum(c['hours'] for c in class_courses[class_name])
                print(f"  {class_name}: {count} cours, {total_h}h")
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_yod_bet_2()
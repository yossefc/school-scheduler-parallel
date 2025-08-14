#!/usr/bin/env python3
"""Analyse de l'emploi du temps pour identifier les déséquilibres"""

import requests
import json
from collections import defaultdict

def analyze_schedule():
    """Analyse la distribution des cours par classe"""
    
    try:
        # Récupérer les données
        response = requests.get("http://localhost:8000/api/schedule_entries?format=analysis")
        if not response.ok:
            print(f"Erreur API: {response.status_code}")
            return
        
        data = response.json()
        entries = data.get('entries', [])
        
        print(f"=== ANALYSE DE L'EMPLOI DU TEMPS ===")
        print(f"Total entrees: {len(entries)}")
        print()
        
        # Analyser par classe
        class_counts = defaultdict(int)
        class_subjects = defaultdict(set)
        
        for entry in entries:
            class_name = entry.get('class_name', '')
            subject = entry.get('subject', '')
            
            if class_name and subject:
                # Gérer les classes multiples (cours parallèles)
                if ',' in class_name:
                    classes = [c.strip() for c in class_name.split(',')]
                    for cls in classes:
                        class_counts[cls] += 1
                        class_subjects[cls].add(subject)
                else:
                    class_counts[class_name] += 1
                    class_subjects[class_name].add(subject)
        
        # Trier par nombre de cours
        sorted_classes = sorted(class_counts.items(), key=lambda x: x[1])
        
        print("DISTRIBUTION DES COURS PAR CLASSE:")
        print("=" * 50)
        
        for class_name, count in sorted_classes:
            subjects_count = len(class_subjects[class_name])
            print(f"{class_name:>8}: {count:>3} cours, {subjects_count:>2} matieres")
        
        print()
        
        # Identifier les problèmes
        min_courses = sorted_classes[0][1] if sorted_classes else 0
        max_courses = sorted_classes[-1][1] if sorted_classes else 0
        avg_courses = sum(count for _, count in sorted_classes) / len(sorted_classes) if sorted_classes else 0
        
        print(f"STATISTIQUES:")
        print(f"  Minimum de cours: {min_courses}")
        print(f"  Maximum de cours: {max_courses}")
        print(f"  Moyenne: {avg_courses:.1f}")
        print(f"  Ecart: {max_courses - min_courses}")
        print()
        
        # Classes avec le moins de cours
        threshold = avg_courses * 0.7  # 70% de la moyenne
        problematic_classes = [cls for cls, count in sorted_classes if count < threshold]
        
        if problematic_classes:
            print(f"CLASSES AVEC PEU DE COURS (< {threshold:.1f}):")
            for class_name in problematic_classes[:10]:
                count = class_counts[class_name]
                subjects = sorted(list(class_subjects[class_name]))
                print(f"  {class_name}: {count} cours")
                print(f"    Matieres: {', '.join(subjects[:5])}")
                if len(subjects) > 5:
                    print(f"    ... et {len(subjects) - 5} autres")
                print()
        
        # Analyser les matieres manquantes
        print("ANALYSE DES MATIERES:")
        print("=" * 30)
        
        # Toutes les matieres enseignees
        all_subjects = set()
        for subjects in class_subjects.values():
            all_subjects.update(subjects)
        
        print(f"Matieres enseignees au total: {len(all_subjects)}")
        sorted_subjects = sorted(list(all_subjects))
        for subject in sorted_subjects:
            classes_with_subject = [cls for cls, subjects in class_subjects.items() if subject in subjects]
            print(f"  {subject}: {len(classes_with_subject)} classes")
        
        return sorted_classes, class_subjects

    except Exception as e:
        print(f"Erreur: {e}")
        return None, None

if __name__ == "__main__":
    analyze_schedule()
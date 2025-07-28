#!/usr/bin/env python3
"""
Script de test pour vérifier le bon fonctionnement des cours parallèles
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"

def print_section(title):
    """Affiche un titre de section"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")

def test_parallel_groups():
    """Test 1: Récupérer les groupes parallèles"""
    print_section("Test 1: Groupes Parallèles")
    
    response = requests.get(f"{API_BASE}/api/parallel/groups")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Trouvé {data['total']} groupes parallèles")
        
        for group in data['parallel_groups']:
            print(f"\n  Groupe #{group['group_id']}:")
            print(f"  - Matière: {group['subject']}")
            print(f"  - Niveau: {group['grade']}")
            print(f"  - Professeurs: {group['teachers']}")
            print(f"  - Heures: {group['hours']}h par prof")
            print(f"  - Classes: {group['all_classes']}")
    else:
        print(f"✗ Erreur: {response.status_code}")

def test_consistency_check():
    """Test 2: Vérifier la cohérence"""
    print_section("Test 2: Vérification de Cohérence")
    
    response = requests.get(f"{API_BASE}/api/parallel/check")
    if response.status_code == 200:
        data = response.json()
        if data['is_valid']:
            print(f"✓ {data['message']}")
        else:
            print(f"✗ Problèmes détectés:")
            for issue in data['issues']:
                print(f"  - {issue['issue_type']}: {issue['details']}")
    else:
        print(f"✗ Erreur: {response.status_code}")

def test_teacher_parallel_courses(teacher_name="Cohen"):
    """Test 3: Cours parallèles d'un professeur"""
    print_section(f"Test 3: Cours de {teacher_name}")
    
    response = requests.get(f"{API_BASE}/api/parallel/teacher/{teacher_name}")
    if response.status_code == 200:
        data = response.json()
        print(f"Professeur: {data['teacher']}")
        print(f"\nCours parallèles ({data['total_parallel_hours']}h):")
        for course in data['parallel_courses']:
            print(f"  - {course['subject']} niveau {course['grade']}: {course['hours']}h")
            print(f"    Avec: {course['teachers']}")
            
        print(f"\nCours individuels ({data['total_individual_hours']}h):")
        for course in data['individual_courses']:
            print(f"  - {course['subject']} {course['grade']}: {course['hours']}h")
    else:
        print(f"✗ Erreur: {response.status_code}")

def test_analyze_data():
    """Test 4: Analyser des données pour détecter les cours parallèles"""
    print_section("Test 4: Analyse Automatique")
    
    # Données de test
    test_data = {
        "teacher_loads": [
            {"teacher_name": "Prof A", "subject": "Math", "grade": "9", "class_list": "9-1,9-2,9-3", "hours": 6},
            {"teacher_name": "Prof B", "subject": "Math", "grade": "9", "class_list": "9-1,9-2,9-3", "hours": 6},
            {"teacher_name": "Prof C", "subject": "Math", "grade": "9", "class_list": "9-1,9-2,9-3", "hours": 6},
            {"teacher_name": "Prof D", "subject": "Histoire", "grade": "9", "class_list": "9-1", "hours": 3},
        ]
    }
    
    response = requests.post(f"{API_BASE}/api/parallel/analyze", json=test_data)
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Trouvé {data['total_found']} groupes parallèles potentiels")
        
        for group in data['potential_parallel_groups']:
            print(f"\n  {group['subject']} niveau {group['grade']}:")
            print(f"  - {group['teacher_count']} professeurs: {', '.join(group['teachers'])}")
            print(f"  - {group['hours']}h chacun")
            print(f"  - Valide: {'✓' if group['is_valid'] else '✗'}")
    else:
        print(f"✗ Erreur: {response.status_code}")

def test_generate_schedule():
    """Test 5: Générer un emploi du temps avec cours parallèles"""
    print_section("Test 5: Génération d'Emploi du Temps")
    
    request_data = {
        "time_limit": 30,
        "constraints": []
    }
    
    print("Lancement de la génération...")
    response = requests.post(f"{API_BASE}/generate_schedule", json=request_data)
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            print(f"✓ Emploi du temps généré avec succès!")
            print(f"  ID: {data['schedule_id']}")
            summary = data['summary']
            print(f"\n  Résumé:")
            print(f"  - Total leçons: {summary['total_lessons']}")
            print(f"  - Leçons parallèles: {summary.get('parallel_lessons', 0)}")
            print(f"  - Groupes parallèles: {summary.get('parallel_groups', 0)}")
            print(f"  - Professeurs: {summary['teachers_count']}")
            print(f"  - Classes: {summary['classes_count']}")
        else:
            print(f"✗ Échec: {data['reason']}")
            if 'suggestion' in data:
                print(f"  Suggestion: {data['suggestion']}")
    else:
        print(f"✗ Erreur: {response.status_code}")
        print(response.text)

def test_parallel_statistics():
    """Test 6: Statistiques des cours parallèles"""
    print_section("Test 6: Statistiques Parallèles")
    
    response = requests.get(f"{API_BASE}/api/stats/parallel")
    if response.status_code == 200:
        data = response.json()
        print(f"Résumé: {data['summary']}")
        
        print("\nPar matière:")
        for subject in data['by_subject']:
            print(f"  - {subject['subject']}: {subject['group_count']} groupes, "
                  f"{subject['teacher_count']} profs, {subject['total_hours']}h total")
    else:
        print(f"✗ Erreur: {response.status_code}")

def test_schedule_visualization():
    """Test 7: Récupérer un emploi du temps avec cours parallèles"""
    print_section("Test 7: Visualisation")
    
    # Test pour une classe
    class_name = "ט-1"
    response = requests.get(f"{API_BASE}/api/schedule/class/{class_name}")
    
    if response.status_code == 200:
        data = response.json()
        schedule = data['schedule']
        print(f"✓ Emploi du temps de {class_name}: {len(schedule)} créneaux")
        
        # Chercher les cours parallèles
        parallel_slots = [s for s in schedule if s.get('teachers') and ' + ' in s.get('teachers', '')]
        if parallel_slots:
            print(f"\nCours parallèles trouvés:")
            for slot in parallel_slots[:3]:  # Montrer max 3 exemples
                print(f"  - {slot['subject_name']} (Jour {slot['day_of_week']}, Période {slot['period_number']})")
                print(f"    Professeurs: {slot['teachers']}")
    else:
        print(f"✗ Erreur: {response.status_code}")

def main():
    """Exécuter tous les tests"""
    print(f"\n🧪 TESTS DES COURS PARALLÈLES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API: {API_BASE}")
    
    try:
        # Vérifier que l'API est accessible
        response = requests.get(f"{API_BASE}/")
        if response.status_code == 200:
            api_info = response.json()
            print(f"✓ API accessible - Version {api_info.get('version', '?')}")
            print(f"  Features: {', '.join(api_info.get('features', []))}")
        else:
            print("✗ API non accessible")
            return
            
        # Exécuter les tests
        test_parallel_groups()
        test_consistency_check()
        test_teacher_parallel_courses()
        test_analyze_data()
        test_parallel_statistics()
        test_generate_schedule()
        test_schedule_visualization()
        
        print(f"\n{'='*60}")
        print(" Tests terminés!")
        print(f"{'='*60}\n")
        
    except requests.exceptions.ConnectionError:
        print("\n✗ ERREUR: Impossible de se connecter à l'API")
        print("  Assurez-vous que le serveur est lancé:")
        print("  docker-compose up -d")
    except Exception as e:
        print(f"\n✗ ERREUR: {str(e)}")

if __name__ == "__main__":
    main()
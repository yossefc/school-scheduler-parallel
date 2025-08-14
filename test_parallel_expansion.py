#!/usr/bin/env python3
"""Test de l'expansion des cours parallèles"""

import sys
sys.path.append('solver')

from parallel_course_handler import ParallelCourseHandler
import json

# Exemple de cours parallèle
courses = [
    {
        'course_id': 4070,
        'class_list': 'ז-1, ז-3, ז-4',
        'subject': 'תנך',
        'hours': 4,
        'is_parallel': True,
        'group_id': 4,
        'grade': 'ז',
        'teacher_names': 'אלמו רפאל, חריר אביחיל, ספר מוריס יוני, צברי יגאל'
    }
]

print("=== TEST EXPANSION COURS PARALLÈLES ===")
print(f"Cours original: {courses[0]['subject']} {courses[0]['grade']}")
print(f"Professeurs: {courses[0]['teacher_names']}")
print(f"Classes: {courses[0]['class_list']}")
print("")

expanded, sync_groups = ParallelCourseHandler.expand_parallel_courses(courses)

print("Cours après expansion:")
for c in expanded:
    print(f"  ID: {c['course_id']}, Prof: {c['teacher_names']}, Classe: {c['class_list']}")

print(f"\nGroupes de synchronisation:")
print(json.dumps(sync_groups, indent=2))

# Test avec des nombres différents
print("\n\n=== TEST 2: Plus de profs que de classes ===")
courses2 = [
    {
        'course_id': 5000,
        'class_list': 'יא-1, יא-2',
        'subject': 'מתמטיקה',
        'hours': 5,
        'is_parallel': True,
        'group_id': 100,
        'grade': 'יא',
        'teacher_names': 'אהרון יניב, וייס לירן, וייצמן מוריה, יפרח אורי'
    }
]

expanded2, sync_groups2 = ParallelCourseHandler.expand_parallel_courses(courses2)

print(f"Original: {courses2[0]['teacher_names']}")
print(f"Classes: {courses2[0]['class_list']}")
print("\nAprès expansion:")
for c in expanded2:
    print(f"  Prof: {c['teacher_names']} → Classe: {c['class_list']}")





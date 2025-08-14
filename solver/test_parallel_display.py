"""
Test d'affichage des cours parallèles
Montre comment les cours parallèles sont gérés
"""

# Exemples de cours depuis solver_input
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
    },
    {
        'course_id': 3747,
        'class_list': 'יא-1, יא-2, יא-3',
        'subject': 'מתמטיקה',
        'hours': 5,
        'is_parallel': True,
        'group_id': 138,
        'grade': 'יא',
        'teacher_names': 'אהרון יניב, וייס לירן, וייצמן מוריה, יפרח אורי, קנימח ניר, שמעוני נירית'
    }
]

print("=== AFFICHAGE DES COURS PARALLÈLES ===\n")

for course in courses:
    if course.get('is_parallel'):
        teachers = course['teacher_names'].split(', ')
        classes = course['class_list'].split(', ')
        
        print(f"📚 {course['subject']} - Niveau {course['grade']} ({course['hours']}h/semaine)")
        print(f"   ID: {course['course_id']}, Groupe: {course['group_id']}")
        print(f"   👥 {len(teachers)} professeurs enseignent ENSEMBLE:")
        for teacher in teachers:
            print(f"      • {teacher}")
        print(f"   📍 à {len(classes)} classes RÉUNIES: {course['class_list']}")
        print(f"   ⏰ Tous au MÊME créneau horaire")
        print()

print("\n=== CONTRAINTES POUR LE SOLVER ===")
print("✅ Les cours avec le même group_id doivent être synchronisés")
print("✅ Tous les professeurs d'un cours parallèle enseignent au même moment")
print("✅ Toutes les classes listées sont réunies pour ce cours")
print("✅ Un professeur ne peut pas avoir deux cours au même moment")

print("\n=== EXEMPLE D'EMPLOI DU TEMPS ===")
print("Lundi 10h-11h:")
print("  • Salle polyvalente: תנך niveau ז")
print("    - 4 professeurs (אלמו רפאל, חריר אביחיל, ספר מוריס יוני, צברי יגאל)")
print("    - 3 classes réunies (ז-1, ז-3, ז-4)")
print("    - Enseignement en parallèle/co-enseignement")





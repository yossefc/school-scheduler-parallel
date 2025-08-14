"""Test simple de synchronisation des cours parallèles"""

# Simuler l'expansion manuelle
course = {
    'course_id': 4070,
    'class_list': 'ז-1, ז-3, ז-4',
    'subject': 'תנך',
    'hours': 4,
    'is_parallel': True,
    'group_id': 4,
    'grade': 'ז',
    'teacher_names': 'אלמו רפאל, חריר אביחיל, ספר מוריס יוני'
}

# Extraction des données
teachers = course['teacher_names'].split(', ')
classes = course['class_list'].split(', ')

print(f"Cours original: {course['subject']} {course['grade']}")
print(f"Professeurs ({len(teachers)}): {teachers}")
print(f"Classes ({len(classes)}): {classes}")

# Logique d'expansion
print("\nExpansion:")
if len(teachers) == len(classes):
    print("Cas 1: 1 prof par classe")
    for teacher, classe in zip(teachers, classes):
        print(f"  {teacher} → {classe}")
else:
    print(f"Cas 2: Répartition {len(teachers)} profs sur {len(classes)} classes")

# Ce que le solver doit faire:
print("\nPour le solver:")
print("- Ces 3 cours DOIVENT être au même créneau horaire")
print("- Si un prof enseigne à 10h le lundi, TOUS enseignent à 10h le lundi")
print("- C'est une contrainte DURE, pas une préférence")





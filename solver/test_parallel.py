from parallel_course_handler import ParallelCourseHandler

# Test simple
courses = [{
    'course_id': 4070,
    'class_list': 'ז-1, ז-3, ז-4',
    'subject': 'תנך',
    'hours': 4,
    'is_parallel': True,
    'group_id': 4,
    'grade': 'ז',
    'teacher_names': 'אלמו רפאל, חריר אביחיל, ספר מוריס יוני'
}]

expanded, sync_groups = ParallelCourseHandler.expand_parallel_courses(courses)

print("Expansion:")
for c in expanded:
    print(f"ID: {c['course_id']}, Prof: {c['teacher_names']}, Classe: {c['class_list']}")
print(f"\nSync groups: {sync_groups}")





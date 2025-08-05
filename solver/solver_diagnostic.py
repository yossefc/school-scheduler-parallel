# solver_diagnostic.py - Diagnostic approfondi du problème de génération
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configuration DB
db_config = {
    "host": "postgres",  # Changé pour test local
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

def analyze_class_consistency():
    """Vérifie la cohérence entre les classes référencées et existantes"""
    print("\n=== ANALYSE DES CLASSES ===")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Classes définies dans la table classes
        cur.execute("SELECT class_name FROM classes ORDER BY class_name")
        defined_classes = set(row['class_name'] for row in cur.fetchall())
        print(f"Classes définies dans 'classes': {len(defined_classes)}")
        print(f"Exemples: {list(sorted(defined_classes))[:10]}")
        
        # Classes référencées dans teacher_load
        cur.execute("""
            SELECT DISTINCT trim(unnest(string_to_array(class_list, ','))) as class_name
            FROM teacher_load 
            WHERE class_list IS NOT NULL AND class_list != ''
        """)
        referenced_classes = set(row['class_name'] for row in cur.fetchall() if row['class_name'])
        print(f"\nClasses référencées dans 'teacher_load': {len(referenced_classes)}")
        print(f"Exemples: {list(sorted(referenced_classes))[:10]}")
        
        # Classes manquantes
        missing_classes = referenced_classes - defined_classes
        extra_classes = defined_classes - referenced_classes
        
        print(f"\n❌ Classes référencées mais non définies: {len(missing_classes)}")
        if missing_classes:
            print(f"Exemples: {list(sorted(missing_classes))[:10]}")
        
        print(f"\n⚠️  Classes définies mais non utilisées: {len(extra_classes)}")
        if extra_classes:
            print(f"Exemples: {list(sorted(extra_classes))[:10]}")
            
        return len(missing_classes) == 0
        
    finally:
        cur.close()
        conn.close()

def analyze_teacher_consistency():
    """Vérifie la cohérence des professeurs"""
    print("\n=== ANALYSE DES PROFESSEURS ===")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Professeurs dans la table teachers
        cur.execute("SELECT teacher_name FROM teachers")
        defined_teachers = set(row['teacher_name'] for row in cur.fetchall())
        print(f"Professeurs définis: {len(defined_teachers)}")
        
        # Professeurs dans teacher_load
        cur.execute("SELECT DISTINCT teacher_name FROM teacher_load")
        referenced_teachers = set(row['teacher_name'] for row in cur.fetchall())
        print(f"Professeurs référencés: {len(referenced_teachers)}")
        
        missing_teachers = referenced_teachers - defined_teachers
        print(f"\n❌ Professeurs référencés mais non définis: {len(missing_teachers)}")
        if missing_teachers:
            print(f"Exemples: {list(sorted(missing_teachers))[:5]}")
            
        return len(missing_teachers) == 0
        
    finally:
        cur.close()
        conn.close()

def analyze_time_slots():
    """Analyse les créneaux horaires"""
    print("\n=== ANALYSE DES CRÉNEAUX ===")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                day_of_week,
                COUNT(*) as slots_count,
                COUNT(*) FILTER (WHERE is_break) as breaks,
                COUNT(*) FILTER (WHERE NOT is_break) as work_slots
            FROM time_slots 
            GROUP BY day_of_week 
            ORDER BY day_of_week
        """)
        
        for row in cur.fetchall():
            day_names = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven']
            day_name = day_names[row['day_of_week']] if row['day_of_week'] < 6 else f"Jour{row['day_of_week']}"
            print(f"{day_name}: {row['work_slots']} créneaux de travail, {row['breaks']} pauses")
            
    finally:
        cur.close()
        conn.close()

def analyze_parallel_courses():
    """Analyse les cours parallèles pour détecter les problèmes"""
    print("\n=== ANALYSE DES COURS PARALLÈLES ===")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Cours parallèles avec détails
        cur.execute("""
            SELECT 
                teacher_name,
                subject,
                class_list,
                hours,
                array_length(string_to_array(class_list, ','), 1) as nb_classes
            FROM teacher_load 
            WHERE is_parallel = true
            ORDER BY nb_classes DESC, hours DESC
            LIMIT 10
        """)
        
        print("Top 10 des cours parallèles les plus complexes:")
        for row in cur.fetchall():
            print(f"- {row['teacher_name']}: {row['subject']} → {row['nb_classes']} classes ({row['hours']}h)")
            print(f"  Classes: {row['class_list']}")
            
    finally:
        cur.close()
        conn.close()

def analyze_workload_distribution():
    """Analyse la répartition de la charge de travail"""
    print("\n=== ANALYSE DE LA CHARGE DE TRAVAIL ===")
    
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Charge par professeur
        cur.execute("""
            SELECT 
                teacher_name,
                COUNT(*) as nb_courses,
                SUM(hours) as total_hours,
                SUM(CASE WHEN is_parallel THEN hours ELSE 0 END) as parallel_hours
            FROM teacher_load
            GROUP BY teacher_name
            ORDER BY total_hours DESC
            LIMIT 10
        """)
        
        print("Top 10 des professeurs les plus chargés:")
        for row in cur.fetchall():
            print(f"- {row['teacher_name']}: {row['total_hours']}h total ({row['parallel_hours']}h parallèles)")
            
        # Charge par classe
        cur.execute("""
            WITH class_hours AS (
                SELECT 
                    trim(unnest(string_to_array(class_list, ','))) as class_name,
                    hours
                FROM teacher_load 
                WHERE class_list IS NOT NULL
            )
            SELECT 
                class_name,
                COUNT(*) as nb_subjects,
                SUM(hours) as total_hours
            FROM class_hours
            WHERE class_name != ''
            GROUP BY class_name
            ORDER BY total_hours DESC
            LIMIT 10
        """)
        
        print("\nTop 10 des classes les plus chargées:")
        for row in cur.fetchall():
            print(f"- {row['class_name']}: {row['total_hours']}h ({row['nb_subjects']} matières)")
            
    finally:
        cur.close()
        conn.close()

def test_solver_data_loading():
    """Test le chargement des données par le solver"""
    print("\n=== TEST DE CHARGEMENT DES DONNÉES ===")
    
    try:
        # Simuler le chargement comme dans solver_engine.py
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test 1: Professeurs
        cur.execute("SELECT * FROM teachers WHERE teacher_name IS NOT NULL")
        teachers = cur.fetchall()
        print(f"✓ {len(teachers)} professeurs chargés")
        
        # Test 2: Classes
        cur.execute("SELECT * FROM classes")
        classes = cur.fetchall()
        print(f"✓ {len(classes)} classes chargées")
        
        # Test 3: Créneaux
        cur.execute("SELECT * FROM time_slots WHERE is_break = FALSE ORDER BY day_of_week, period_number")
        time_slots = cur.fetchall()
        print(f"✓ {len(time_slots)} créneaux de travail")
        
        # Test 4: Charges d'enseignement
        cur.execute("SELECT * FROM teacher_load WHERE hours > 0")
        teacher_loads = cur.fetchall()
        print(f"✓ {len(teacher_loads)} charges d'enseignement")
        
        # Test 5: Variables potentielles
        total_vars = 0
        for load in teacher_loads:
            class_list = load.get("class_list", "")
            if not class_list:  # Réunion
                total_vars += len(time_slots)
            else:
                classes_count = len([c.strip() for c in class_list.split(",") if c.strip()])
                total_vars += classes_count * len(time_slots)
        
        print(f"✓ ~{total_vars} variables de décision potentielles")
        
        # Test 6: Cohérence des données
        teacher_id_map = {t["teacher_name"]: t["teacher_id"] for t in teachers}
        missing_teacher_ids = 0
        
        for load in teacher_loads:
            if load["teacher_name"] not in teacher_id_map:
                missing_teacher_ids += 1
        
        if missing_teacher_ids > 0:
            print(f"❌ {missing_teacher_ids} charges sans teacher_id valide")
        else:
            print("✓ Tous les professeurs ont un ID valide")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")

def suggest_fixes():
    """Propose des corrections"""
    print("\n=== RECOMMANDATIONS ===")
    
    recommendations = [
        "1. Vérifier et corriger les noms de classes incohérents",
        "2. Ajouter plus de logging dans le solver pour identifier le blocage exact",
        "3. Tester avec un sous-ensemble de données plus simple",
        "4. Vérifier les contraintes de disponibilité des professeurs",
        "5. Simplifier temporairement les cours parallèles",
        "6. S'assurer que tous les créneaux sont bien définis pour tous les jours"
    ]
    
    for rec in recommendations:
        print(rec)

def main():
    print("🔍 DIAGNOSTIC APPROFONDI DU SOLVER D'EMPLOI DU TEMPS")
    print("=" * 60)
    
    classes_ok = analyze_class_consistency()
    teachers_ok = analyze_teacher_consistency()
    analyze_time_slots()
    analyze_parallel_courses()
    analyze_workload_distribution()
    test_solver_data_loading()
    
    print(f"\n=== RÉSUMÉ ===")
    print(f"Classes cohérentes: {'✓' if classes_ok else '❌'}")
    print(f"Professeurs cohérents: {'✓' if teachers_ok else '❌'}")
    
    suggest_fixes()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Script pour reconstruire proprement les données depuis l'Excel source
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import json

def load_excel_data():
    """Charger et nettoyer les données Excel"""
    print("📊 CHARGEMENT DES DONNÉES EXCEL")
    print("=" * 40)
    
    excel_path = "exports/template_import_v22_WORKFLOW_READY.xlsx"
    
    # Charger les feuilles
    teachers_df = pd.read_excel(excel_path, sheet_name='Teachers')
    teacher_subjects_df = pd.read_excel(excel_path, sheet_name='Teacher_Subjects')
    parallel_groups_df = pd.read_excel(excel_path, sheet_name='Parallel_Groups')
    constraints_df = pd.read_excel(excel_path, sheet_name='Constraints')
    
    print(f"✓ Teachers: {len(teachers_df)} lignes")
    print(f"✓ Teacher_Subjects: {len(teacher_subjects_df)} lignes")
    print(f"✓ Parallel_Groups: {len(parallel_groups_df)} lignes")
    print(f"✓ Constraints: {len(constraints_df)} lignes")
    print("")
    
    return {
        'teachers': teachers_df,
        'teacher_subjects': teacher_subjects_df,
        'parallel_groups': parallel_groups_df,
        'constraints': constraints_df
    }

def analyze_parallel_groups(data):
    """Analyser les groupes parallèles pour détecter les doublons"""
    print("🔍 ANALYSE DES GROUPES PARALLÈLES")
    print("=" * 41)
    
    teacher_subjects = data['teacher_subjects']
    parallel_groups = data['parallel_groups']
    
    # Analyser TOUS les cours pour détecter les vrais groupes parallèles
    # Un groupe parallèle = même matière, même niveau, mêmes classes, plusieurs profs
    all_courses = teacher_subjects.copy()
    
    # Grouper par matière/niveau/classes pour trouver les cours avec plusieurs profs
    grouped = all_courses.groupby(['Subject', 'Grade', 'Class List']).agg({
        'Teacher Name': lambda x: ', '.join(sorted(set(x))),  # Concaténer tous les profs uniques
        'Hours': 'first'  # Les heures devraient être identiques
    }).reset_index()
    
    # Ajouter le nombre de profs
    grouped['Nb_Teachers'] = grouped['Teacher Name'].apply(lambda x: len(x.split(', ')))
    
    # Séparer les cours parallèles (plusieurs profs) et individuels (un seul prof)
    parallel_courses = grouped[grouped['Nb_Teachers'] > 1]
    individual_courses = grouped[grouped['Nb_Teachers'] == 1]
    
    print(f"Cours trouvés: {len(grouped)} au total")
    print(f"  - Cours parallèles (plusieurs profs): {len(parallel_courses)}")
    print(f"  - Cours individuels (un seul prof): {len(individual_courses)}")
    
    print("\nTop 10 des vrais groupes parallèles:")
    for _, row in parallel_courses.head(10).iterrows():
        print(f"  {row['Subject']} - {row['Grade']} - {row['Class List']}")
        print(f"    {row['Nb_Teachers']} profs: {row['Teacher Name']}")
        print(f"    {row['Hours']}h")
    print("")
    
    return parallel_courses

def calculate_real_load(data):
    """Calculer la vraie charge en regroupant correctement les cours parallèles"""
    print("📊 CALCUL DE LA VRAIE CHARGE")
    print("=" * 33)
    
    teacher_subjects = data['teacher_subjects']
    
    # Regrouper TOUS les cours par (Subject, Grade, Class List)
    print("Regroupement des cours par matière/niveau/classes...")
    
    grouped = teacher_subjects.groupby(['Subject', 'Grade', 'Class List']).agg({
        'Teacher Name': lambda x: ', '.join(sorted(set(x))),  # Tous les profs uniques
        'Hours': 'first'  # Les heures devraient être identiques pour un même groupe
    }).reset_index()
    
    # Identifier parallèles vs individuels
    grouped['Nb_Teachers'] = grouped['Teacher Name'].apply(lambda x: len(x.split(', ')))
    grouped['Is_Parallel'] = grouped['Nb_Teachers'] > 1
    
    parallel_courses = grouped[grouped['Is_Parallel']]
    individual_courses = grouped[~grouped['Is_Parallel']]
    
    total_parallel_hours = parallel_courses['Hours'].sum()
    total_individual_hours = individual_courses['Hours'].sum()
    total_courses = len(grouped)
    total_hours = total_parallel_hours + total_individual_hours
    
    print(f"  Cours parallèles: {len(parallel_courses)} cours, {total_parallel_hours}h")
    print(f"  Cours individuels: {len(individual_courses)} cours, {total_individual_hours}h")
    print(f"  TOTAL: {total_courses} cours, {total_hours}h")
    print("")
    
    # Calculer la faisabilité
    slots_available = 57  # Nous savons qu'il y en a 57
    utilization = (total_hours / slots_available) * 100
    
    print(f"📈 FAISABILITÉ:")
    print(f"  Heures à planifier: {total_hours}")
    print(f"  Créneaux disponibles: {slots_available}")
    print(f"  Taux d'utilisation: {utilization:.1f}%")
    
    if utilization > 100:
        print(f"  ❌ IMPOSSIBLE - {utilization-100:.1f}% de surcharge")
    elif utilization > 85:
        print(f"  ⚠️  DIFFICILE - Très proche de la limite")
    else:
        print(f"  ✅ FAISABLE")
    
    print("")
    
    return {
        'parallel_courses': parallel_courses,
        'individual_courses': individual_courses,
        'all_courses': grouped,
        'total_hours': total_hours,
        'total_courses': total_courses,
        'utilization': utilization
    }

def rebuild_solver_input(clean_data):
    """Reconstruire solver_input avec les données nettoyées et support correct des cours parallèles"""
    print("🔧 RECONSTRUCTION DE SOLVER_INPUT")
    print("=" * 42)
    
    db_config = {
        "host": "localhost",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123"
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Sauvegarder l'ancien
        cur.execute("DROP TABLE IF EXISTS solver_input_before_rebuild;")
        cur.execute("CREATE TABLE solver_input_before_rebuild AS SELECT * FROM solver_input;")
        
        # Vider solver_input
        cur.execute("TRUNCATE solver_input;")
        
        # Ajouter la colonne teacher_names si elle n'existe pas
        cur.execute("""
            ALTER TABLE solver_input 
            ADD COLUMN IF NOT EXISTS teacher_names VARCHAR(500);
        """)
        
        # Insérer TOUS les cours avec le bon marquage parallèle/individuel
        print("Insertion des cours...")
        course_id = 1
        total_courses = len(clean_data['all_courses'])
        
        for idx, (_, course) in enumerate(clean_data['all_courses'].iterrows()):
            if idx % 10 == 0:
                print(f"  Progression: {idx}/{total_courses} cours...")
            
            # Insérer avec teacher_names seulement
            cur.execute("""
                INSERT INTO solver_input (course_type, teacher_names, subject, grade, class_list, hours, is_parallel, group_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'regular',
                course['Teacher Name'],  # Tous les profs (déjà concaténés)
                course['Subject'],
                course['Grade'], 
                course['Class List'],
                course['Hours'],
                course['Is_Parallel'],  # True si plusieurs profs
                course_id if course['Is_Parallel'] else None  # group_id seulement pour les parallèles
            ))
            course_id += 1
        
        print(f"✓ {total_courses} cours insérés")
        
        conn.commit()
        
        # Vérifier le résultat
        cur.execute("SELECT COUNT(*), SUM(hours), COUNT(*) FILTER (WHERE is_parallel = TRUE) as parallel_count FROM solver_input;")
        result = cur.fetchone()
        
        print(f"✓ Nouveau solver_input: {result[0]} cours, {result[1]}h")
        print(f"  dont {result[2]} cours parallèles")
        print("")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║       RECONSTRUCTION DEPUIS DONNÉES EXCEL              ║")
    print("╚════════════════════════════════════════════════════════╝")
    print("")
    
    # 1. Charger Excel
    data = load_excel_data()
    
    # 2. Analyser les groupes parallèles
    duplicates = analyze_parallel_groups(data)
    
    # 3. Calculer la vraie charge
    clean_data = calculate_real_load(data)
    
    # 4. Reconstruire si acceptable
    if clean_data['utilization'] <= 1500:  # Seuil augmenté temporairement
        print("🚀 RECONSTRUCTION DE LA BASE DE DONNÉES")
        print("=" * 47)
        
        if rebuild_solver_input(clean_data):
            print("✅ Reconstruction réussie!")
            print("")
            print("🎯 PROCHAINES ÉTAPES:")
            print("1. Tester la génération:")
            print("   curl -X POST 'http://localhost:8000/generate_schedule' -H 'Content-Type: application/json' -d '{\"time_limit\": 1200}'")
            print("")
            print("2. Si ça échoue encore, réduire davantage les données")
        else:
            print("❌ Échec de la reconstruction")
    else:
        print("⚠️  Données encore trop volumineuses pour la génération")
        print("   Considérez:")
        print("   - Réduire le nombre d'heures par matière")
        print("   - Tester sur quelques niveaux seulement")
        print("   - Augmenter le nombre de créneaux disponibles")

if __name__ == "__main__":
    main()


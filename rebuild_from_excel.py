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
    
    excel_path = "exports/template_import_v22.xlsx"
    
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
    
    # Analyser les cours multi-classes dans Teacher_Subjects
    multi_class_courses = teacher_subjects[teacher_subjects['Class List'].str.contains(',', na=False)]
    print(f"Cours multi-classes dans Teacher_Subjects: {len(multi_class_courses)}")
    
    # Grouper par matière/niveau/classes pour détecter les doublons
    duplicates = multi_class_courses.groupby(['Subject', 'Grade', 'Class List']).agg({
        'Teacher Name': 'count',
        'Hours': ['min', 'max', 'sum']
    }).reset_index()
    
    duplicates.columns = ['Subject', 'Grade', 'Class List', 'Nb_Teachers', 'Hours_Min', 'Hours_Max', 'Hours_Total']
    duplicates = duplicates[duplicates['Nb_Teachers'] > 1]
    
    print("Top 10 des vrais groupes parallèles (plusieurs profs):")
    for _, row in duplicates.head(10).iterrows():
        print(f"  {row['Subject']} - {row['Grade']} - {row['Class List']}")
        print(f"    {row['Nb_Teachers']} profs, {row['Hours_Total']}h total")
    print("")
    
    return duplicates

def calculate_real_load(data):
    """Calculer la vraie charge en évitant les doublons"""
    print("📊 CALCUL DE LA VRAIE CHARGE")
    print("=" * 33)
    
    teacher_subjects = data['teacher_subjects']
    
    # Approche 1: Groupes parallèles = 1 seul cours par groupe
    print("Approche 1: Un cours par groupe parallèle")
    
    # Cours multi-classes: regrouper par (Subject, Grade, Class List)
    multi_class = teacher_subjects[teacher_subjects['Class List'].str.contains(',', na=False)]
    multi_class_grouped = multi_class.groupby(['Subject', 'Grade', 'Class List']).agg({
        'Hours': 'first',  # Prendre les heures du premier prof (ils devraient être identiques)
        'Teacher Name': lambda x: ', '.join(x)  # Concat tous les profs
    }).reset_index()
    
    # Cours mono-classe: garder tel quel
    mono_class = teacher_subjects[~teacher_subjects['Class List'].str.contains(',', na=False)]
    
    total_multi_hours = multi_class_grouped['Hours'].sum()
    total_mono_hours = mono_class['Hours'].sum()
    total_courses = len(multi_class_grouped) + len(mono_class)
    total_hours = total_multi_hours + total_mono_hours
    
    print(f"  Cours multi-classes: {len(multi_class_grouped)} cours, {total_multi_hours}h")
    print(f"  Cours mono-classe: {len(mono_class)} cours, {total_mono_hours}h")
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
        'multi_class_courses': multi_class_grouped,
        'mono_class_courses': mono_class,
        'total_hours': total_hours,
        'total_courses': total_courses,
        'utilization': utilization
    }

def rebuild_solver_input(clean_data):
    """Reconstruire solver_input avec les données nettoyées"""
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
        
        # Insérer les cours multi-classes (1 par groupe)
        print("Insertion des cours parallèles...")
        for _, course in clean_data['multi_class_courses'].iterrows():
            cur.execute("""
                INSERT INTO solver_input (course_type, teacher_name, subject, grade, class_list, hours, is_parallel, group_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'regular',
                course['Teacher Name'].split(',')[0].strip(),  # Premier prof seulement
                course['Subject'],
                course['Grade'], 
                course['Class List'],
                course['Hours'],
                True,
                hash(f"{course['Subject']}_{course['Grade']}_{course['Class List']}") % 10000
            ))
        
        # Insérer les cours mono-classe
        print("Insertion des cours individuels...")
        for _, course in clean_data['mono_class_courses'].iterrows():
            cur.execute("""
                INSERT INTO solver_input (course_type, teacher_name, subject, grade, class_list, hours, is_parallel, group_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                'regular',
                course['Teacher Name'],
                course['Subject'],
                course['Grade'],
                course['Class List'],
                course['Hours'],
                False,
                None
            ))
        
        conn.commit()
        
        # Vérifier le résultat
        cur.execute("SELECT COUNT(*), SUM(hours) FROM solver_input;")
        result = cur.fetchone()
        
        print(f"✓ Nouveau solver_input: {result[0]} cours, {result[1]}h")
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
    if clean_data['utilization'] <= 150:  # Seuil tolérable pour test
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


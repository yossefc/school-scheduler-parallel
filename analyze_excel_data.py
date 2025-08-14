#!/usr/bin/env python3
"""
Script pour analyser le fichier Excel d'import et comparer avec les données en base
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
import os

def analyze_excel():
    """Analyser le fichier Excel source"""
    excel_path = "exports/template_import_v22.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"❌ Fichier non trouvé: {excel_path}")
        return None
    
    print("📊 ANALYSE DU FICHIER EXCEL SOURCE")
    print("=" * 50)
    
    try:
        # Lire toutes les feuilles
        xlsx_file = pd.ExcelFile(excel_path)
        print(f"Feuilles disponibles: {xlsx_file.sheet_names}")
        print("")
        
        sheets_data = {}
        
        for sheet_name in xlsx_file.sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            sheets_data[sheet_name] = df
            
            print(f"📋 Feuille '{sheet_name}':")
            print(f"   Lignes: {len(df)}")
            print(f"   Colonnes: {list(df.columns)}")
            
            # Aperçu des données
            if len(df) > 0:
                print("   Aperçu des 3 premières lignes:")
                for i, row in df.head(3).iterrows():
                    print(f"   {i+1}: {dict(row)}")
            print("")
            
        return sheets_data
        
    except Exception as e:
        print(f"❌ Erreur lecture Excel: {e}")
        return None

def analyze_database():
    """Analyser les données actuelles en base"""
    print("🗄️  ANALYSE DES DONNÉES EN BASE")
    print("=" * 40)
    
    db_config = {
        "host": "localhost",  # Depuis l'hôte Windows
        "port": "5432",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123"
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Tables principales
        tables = ['teacher_load', 'solver_input', 'teachers', 'classes', 'time_slots']
        
        for table in tables:
            cur.execute(f"SELECT COUNT(*) as count FROM {table};")
            count = cur.fetchone()['count']
            print(f"📋 Table '{table}': {count} lignes")
            
            # Aperçu des colonnes
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position;
            """)
            
            columns = cur.fetchall()
            print(f"   Colonnes: {[col['column_name'] for col in columns]}")
            print("")
        
        # 2. Analyse détaillée de teacher_load
        print("🔍 ANALYSE DÉTAILLÉE DE TEACHER_LOAD")
        print("=" * 45)
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_lignes,
                COUNT(DISTINCT teacher_name) as nb_profs,
                COUNT(DISTINCT subject) as nb_matieres,
                COUNT(DISTINCT grade) as nb_niveaux,
                COUNT(DISTINCT class_list) as nb_groupes_classes,
                SUM(hours) as total_heures
            FROM teacher_load;
        """)
        
        stats = cur.fetchone()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print("")
        
        # 3. Répartition par niveau
        cur.execute("""
            SELECT 
                grade,
                COUNT(*) as nb_cours,
                SUM(hours) as heures_totales,
                COUNT(DISTINCT teacher_name) as nb_profs
            FROM teacher_load
            WHERE grade IS NOT NULL
            GROUP BY grade
            ORDER BY grade;
        """)
        
        print("📊 Répartition par niveau (grade):")
        for row in cur.fetchall():
            print(f"   {row['grade']}: {row['nb_cours']} cours, {row['heures_totales']}h, {row['nb_profs']} profs")
        print("")
        
        # 4. Top matières par heures
        cur.execute("""
            SELECT 
                subject,
                COUNT(*) as nb_cours,
                SUM(hours) as heures_totales
            FROM teacher_load
            WHERE subject IS NOT NULL
            GROUP BY subject
            ORDER BY heures_totales DESC
            LIMIT 10;
        """)
        
        print("📚 Top 10 matières par volume horaire:")
        for row in cur.fetchall():
            print(f"   {row['subject']}: {row['nb_cours']} cours, {row['heures_totales']}h")
        print("")
        
        # 5. Groupes de classes les plus chargés
        cur.execute("""
            SELECT 
                class_list,
                COUNT(*) as nb_cours,
                SUM(hours) as heures_totales
            FROM teacher_load
            WHERE class_list IS NOT NULL
            GROUP BY class_list
            ORDER BY heures_totales DESC
            LIMIT 10;
        """)
        
        print("🏫 Top 10 groupes de classes par charge:")
        for row in cur.fetchall():
            print(f"   {row['class_list']}: {row['nb_cours']} cours, {row['heures_totales']}h")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur base de données: {e}")

def compare_data():
    """Comparer Excel vs Base de données"""
    print("\n🔄 COMPARAISON EXCEL vs BASE")
    print("=" * 35)
    
    # Cette partie nécessiterait une analyse plus poussée
    # pour mapper les colonnes Excel avec les tables DB
    print("Pour une comparaison détaillée, il faudrait:")
    print("1. Identifier quelle feuille Excel correspond à quelle table DB")
    print("2. Mapper les colonnes Excel avec les champs DB")
    print("3. Comparer les volumes et détecter les écarts")

def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║           ANALYSE DES DONNÉES D'IMPORT                 ║")
    print("╚════════════════════════════════════════════════════════╝")
    print("")
    
    # 1. Analyser Excel
    excel_data = analyze_excel()
    
    # 2. Analyser base
    analyze_database()
    
    # 3. Comparaison
    compare_data()
    
    print("\n✅ Analyse terminée!")

if __name__ == "__main__":
    main()









#!/usr/bin/env python3
"""
Script pour effacer toutes les données de la base et repartir à zéro
"""

import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    print("🧹 REMISE À ZÉRO COMPLÈTE DE LA BASE DE DONNÉES")
    print("=" * 55)
    print("")

    db_config = {
        "host": "localhost",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123"
    }

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✓ Connexion établie")
        print("")
        
        # 1. Afficher l'état AVANT suppression
        print("📊 ÉTAT AVANT SUPPRESSION:")
        print("-" * 30)
        
        tables = ['teacher_load', 'solver_input', 'teachers', 'classes', 'schedules', 'constraints', 'time_slots']
        
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) as count FROM {table};")
                count = cur.fetchone()['count']
                print(f"  {table}: {count} lignes")
            except:
                print(f"  {table}: table non trouvée")
        
        print("")
        
        # 2. Confirmer la suppression
        print("⚠️  ATTENTION: Cette opération va supprimer TOUTES les données!")
        print("   Tables qui seront vidées:")
        print("   - teacher_load (données des professeurs)")
        print("   - solver_input (données du solveur)")
        print("   - schedules (emplois du temps générés)")
        print("   - constraints (contraintes personnalisées)")
        print("")
        
        # 3. Effectuer les suppressions
        print("🗑️  SUPPRESSION EN COURS...")
        print("-" * 25)
        
        # Ordre important pour éviter les erreurs de contraintes
        suppression_order = [
            'schedules',
            'solver_input', 
            'constraints',
            'teacher_load'
        ]
        
        for table in suppression_order:
            try:
                cur.execute(f"TRUNCATE {table} CASCADE;")
                print(f"  ✓ {table} vidée")
            except Exception as e:
                print(f"  ⚠ {table}: {e}")
        
        # Commit des changements
        conn.commit()
        print("")
        
        # 4. Vérifier l'état APRÈS suppression
        print("📊 ÉTAT APRÈS SUPPRESSION:")
        print("-" * 30)
        
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) as count FROM {table};")
                count = cur.fetchone()['count']
                print(f"  {table}: {count} lignes")
            except:
                print(f"  {table}: table non trouvée")
        
        print("")
        
        # 5. Garder les données de structure (teachers, classes, time_slots)
        print("📋 DONNÉES DE STRUCTURE CONSERVÉES:")
        print("-" * 40)
        print("  ✓ teachers (liste des professeurs)")
        print("  ✓ classes (liste des classes)")  
        print("  ✓ time_slots (créneaux horaires)")
        print("")
        print("❌ DONNÉES SUPPRIMÉES:")
        print("-" * 20)
        print("  ❌ teacher_load (charge des profs)")
        print("  ❌ solver_input (données du solveur)")
        print("  ❌ schedules (emplois du temps)")
        print("  ❌ constraints (contraintes)")
        print("")
        
        print("✅ REMISE À ZÉRO TERMINÉE!")
        print("")
        print("🚀 PROCHAINES ÉTAPES:")
        print("1. Réimporter les données depuis Excel")
        print("2. Reconstruire solver_input proprement")
        print("3. Tester la génération par petites étapes")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()


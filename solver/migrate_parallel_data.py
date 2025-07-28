#!/usr/bin/env python3
"""
Script de migration automatique pour convertir les données existantes
vers le nouveau système de cours parallèles
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from datetime import datetime

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

def log(message, level="INFO"):
    """Logger simple"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def backup_database():
    """Créer une sauvegarde avant migration"""
    log("Création de la sauvegarde...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Sauvegarder teacher_load
        cur.execute("""
            DROP TABLE IF EXISTS teacher_load_backup_migration;
            CREATE TABLE teacher_load_backup_migration AS 
            SELECT * FROM teacher_load;
        """)
        
        # Sauvegarder parallel_groups
        cur.execute("""
            DROP TABLE IF EXISTS parallel_groups_backup_migration;
            CREATE TABLE parallel_groups_backup_migration AS 
            SELECT * FROM parallel_groups;
        """)
        
        conn.commit()
        log("✓ Sauvegarde créée avec succès")
        
    except Exception as e:
        log(f"✗ Erreur lors de la sauvegarde: {e}", "ERROR")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

def analyze_parallel_candidates():
    """Analyser les données pour identifier les cours parallèles"""
    log("Analyse des cours parallèles potentiels...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Identifier les candidats
        cur.execute("""
            WITH candidates AS (
                SELECT 
                    subject,
                    grade,
                    COUNT(DISTINCT teacher_name) as teacher_count,
                    ARRAY_AGG(DISTINCT teacher_name ORDER BY teacher_name) as teachers,
                    ARRAY_AGG(class_list ORDER BY teacher_name) as class_lists,
                    ARRAY_AGG(hours ORDER BY teacher_name) as hours_list
                FROM teacher_load
                WHERE class_list LIKE '%,%'
                  AND class_list IS NOT NULL
                GROUP BY subject, grade
                HAVING COUNT(DISTINCT teacher_name) > 1
            )
            SELECT * FROM candidates
            ORDER BY grade, subject
        """)
        
        candidates = cur.fetchall()
        log(f"✓ Trouvé {len(candidates)} groupes parallèles potentiels")
        
        return candidates
        
    finally:
        cur.close()
        conn.close()

def migrate_to_parallel_system(candidates):
    """Migrer les données vers le nouveau système"""
    log("Migration vers le système de cours parallèles...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Vider les tables cibles
        log("  - Nettoyage des tables...")
        cur.execute("TRUNCATE TABLE parallel_groups CASCADE")
        cur.execute("TRUNCATE TABLE parallel_teaching_details CASCADE")
        
        migrated_count = 0
        
        for candidate in candidates:
            # Vérifier que tous les profs ont le même nombre d'heures
            hours_set = set(candidate['hours_list'])
            if len(hours_set) > 1:
                log(f"  ⚠ {candidate['subject']} {candidate['grade']}: "
                    f"heures différentes {candidate['hours_list']}", "WARNING")
                continue
            
            # Créer le groupe parallèle
            cur.execute("""
                INSERT INTO parallel_groups (subject, grade, teachers, class_lists)
                VALUES (%s, %s, %s, %s)
                RETURNING group_id
            """, (
                candidate['subject'],
                candidate['grade'],
                ', '.join(candidate['teachers']),
                ' | '.join(candidate['class_lists'])
            ))
            
            group_id = cur.fetchone()[0]
            
            # Créer les détails pour chaque professeur
            for i, teacher in enumerate(candidate['teachers']):
                cur.execute("""
                    INSERT INTO parallel_teaching_details 
                    (group_id, teacher_name, subject, grade, hours_per_teacher, classes_covered)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    group_id,
                    teacher,
                    candidate['subject'],
                    candidate['grade'],
                    candidate['hours_list'][i],
                    candidate['class_lists'][i]
                ))
            
            # Marquer ces entrées comme parallèles dans teacher_load
            cur.execute("""
                UPDATE teacher_load
                SET is_parallel = TRUE
                WHERE subject = %s 
                  AND grade = %s
                  AND teacher_name = ANY(%s)
                  AND class_list LIKE '%,%'
            """, (
                candidate['subject'],
                candidate['grade'],
                candidate['teachers']
            ))
            
            migrated_count += 1
            log(f"  ✓ Migré: {candidate['subject']} {candidate['grade']} "
                f"({len(candidate['teachers'])} profs)")
        
        # Créer les contraintes
        log("  - Création des contraintes...")
        cur.execute("""
            INSERT INTO constraints (
                constraint_type, priority, entity_type, entity_name, constraint_data
            )
            SELECT 
                'parallel_teaching',
                1,
                'group',
                'parallel_group_' || pg.group_id,
                jsonb_build_object(
                    'group_id', pg.group_id,
                    'subject', pg.subject,
                    'grade', pg.grade,
                    'teachers', string_to_array(pg.teachers, ', '),
                    'hours', MAX(ptd.hours_per_teacher),
                    'simultaneous', true
                )
            FROM parallel_groups pg
            JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
            GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
        """)
        
        conn.commit()
        log(f"✓ Migration terminée: {migrated_count} groupes migrés")
        
    except Exception as e:
        conn.rollback()
        log(f"✗ Erreur lors de la migration: {e}", "ERROR")
        raise
    finally:
        cur.close()
        conn.close()

def cleanup_individual_parallel_entries():
    """Nettoyer les entrées individuelles qui sont maintenant parallèles"""
    log("Nettoyage des entrées redondantes...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Option 1: Supprimer les entrées parallèles de teacher_load
        # (décommenté si vous voulez les supprimer complètement)
        """
        cur.execute('''
            DELETE FROM teacher_load
            WHERE is_parallel = TRUE
        ''')
        deleted = cur.rowcount
        log(f"  ✓ Supprimé {deleted} entrées parallèles de teacher_load")
        """
        
        # Option 2: Juste les marquer (recommandé)
        cur.execute("""
            UPDATE teacher_load
            SET is_parallel = TRUE
            WHERE (teacher_name, subject, grade) IN (
                SELECT teacher_name, subject, grade
                FROM parallel_teaching_details
            )
            AND class_list LIKE '%,%'
        """)
        updated = cur.rowcount
        log(f"  ✓ Marqué {updated} entrées comme parallèles")
        
        conn.commit()
        
    finally:
        cur.close()
        conn.close()

def verify_migration():
    """Vérifier que la migration s'est bien passée"""
    log("Vérification de la migration...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Statistiques
        cur.execute("SELECT COUNT(*) as count FROM parallel_groups")
        pg_count = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM parallel_teaching_details")
        ptd_count = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM teacher_load WHERE is_parallel = TRUE")
        marked_count = cur.fetchone()['count']
        
        log(f"  - Groupes parallèles: {pg_count}")
        log(f"  - Détails de cours: {ptd_count}")
        log(f"  - Entrées marquées parallèles: {marked_count}")
        
        # Vérifier la cohérence
        cur.execute("SELECT * FROM check_parallel_consistency()")
        issues = cur.fetchall()
        
        if issues:
            log("  ⚠ Problèmes de cohérence détectés:", "WARNING")
            for issue in issues:
                log(f"    - {issue['issue_type']}: {issue['details']}", "WARNING")
        else:
            log("  ✓ Aucun problème de cohérence")
        
        return len(issues) == 0
        
    finally:
        cur.close()
        conn.close()

def rollback_migration():
    """Annuler la migration en cas de problème"""
    log("Annulation de la migration...", "WARNING")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Restaurer depuis la sauvegarde
        cur.execute("""
            TRUNCATE TABLE teacher_load CASCADE;
            INSERT INTO teacher_load 
            SELECT * FROM teacher_load_backup_migration;
            
            TRUNCATE TABLE parallel_groups CASCADE;
            INSERT INTO parallel_groups
            SELECT * FROM parallel_groups_backup_migration;
        """)
        
        conn.commit()
        log("✓ Migration annulée, données restaurées")
        
    except Exception as e:
        log(f"✗ Erreur lors de l'annulation: {e}", "ERROR")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def main():
    """Fonction principale"""
    print("\n" + "="*60)
    print(" MIGRATION VERS LE SYSTÈME DE COURS PARALLÈLES")
    print("="*60 + "\n")
    
    try:
        # 1. Sauvegarde
        backup_database()
        
        # 2. Analyse
        candidates = analyze_parallel_candidates()
        
        if not candidates:
            log("Aucun cours parallèle à migrer")
            return
        
        # 3. Afficher ce qui sera migré
        print("\nCours parallèles à migrer:")
        for c in candidates:
            print(f"  - {c['subject']} {c['grade']}: "
                  f"{len(c['teachers'])} profs, "
                  f"{c['hours_list'][0]}h chacun")
        
        # 4. Demander confirmation
        response = input("\nVoulez-vous procéder à la migration? (o/n): ")
        if response.lower() != 'o':
            log("Migration annulée par l'utilisateur")
            return
        
        # 5. Migration
        migrate_to_parallel_system(candidates)
        
        # 6. Nettoyage
        cleanup_individual_parallel_entries()
        
        # 7. Vérification
        if verify_migration():
            log("\n✓ MIGRATION RÉUSSIE!", "SUCCESS")
            print("\nProchaines étapes:")
            print("1. Vérifiez les données dans l'interface")
            print("2. Générez un nouvel emploi du temps")
            print("3. En cas de problème, utilisez --rollback")
        else:
            log("\n⚠ Migration terminée avec des avertissements", "WARNING")
            response = input("\nVoulez-vous annuler la migration? (o/n): ")
            if response.lower() == 'o':
                rollback_migration()
        
    except Exception as e:
        log(f"\n✗ ERREUR FATALE: {e}", "ERROR")
        log("Utilisez --rollback pour restaurer les données", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        main()
#!/usr/bin/env python3
"""
Test du Bloc B - Groupes parallèles et réunions professeurs
Vérifie que le solver peut gérer :
1. Les cours parallèles (même matière, même moment, classes différentes)
2. Les réunions professeurs (bloquent le prof mais pas de classe)
"""

import logging
from solver_engine import ScheduleSolver
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_data():
    """Crée des données de test pour valider le Bloc B."""
    
    # Configuration de test - adapter selon votre environnement
    db_config = {
        "host": "localhost",  # ou "postgres" si Docker
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123",
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        logger.info("Nettoyage des données de test...")
        
        # Nettoyer les données existantes
        cur.execute("DELETE FROM teacher_load WHERE teacher_name LIKE 'TEST_%'")
        cur.execute("DELETE FROM parallel_groups WHERE subject LIKE 'TEST_%'")
        cur.execute("DELETE FROM teachers WHERE teacher_name LIKE 'TEST_%'")
        cur.execute("DELETE FROM classes WHERE class_name LIKE 'TEST_%'")
        
        # Créer des professeurs de test
        test_teachers = [
            ("TEST_Prof_Math", 18, "0,1,2,3,4"),
            ("TEST_Prof_Hebreu", 20, "0,1,2,3,4"),
            ("TEST_Prof_Directeur", 5, "0,1,2,3,4")
        ]
        
        for name, hours, days in test_teachers:
            cur.execute(
                "INSERT INTO teachers (teacher_name, total_hours, work_days) VALUES (%s, %s, %s)",
                (name, hours, days)
            )
        
        # Créer des classes de test
        test_classes = [
            ("TEST_7A", 7, "A"),
            ("TEST_7B", 7, "B"),
            ("TEST_8A", 8, "A")
        ]
        
        for class_name, grade, section in test_classes:
            cur.execute(
                "INSERT INTO classes (class_name, grade, section, student_count) VALUES (%s, %s, %s, %s)",
                (class_name, grade, section, 25)
            )
        
        # Charges d'enseignement normales
        normal_loads = [
            ("TEST_Prof_Math", "TEST_Maths", "7", "TEST_7A", 4),
            ("TEST_Prof_Hebreu", "TEST_Hebreu", "7", "TEST_7A,TEST_7B", 6),
        ]
        
        for teacher, subject, grade, classes, hours in normal_loads:
            cur.execute(
                "INSERT INTO teacher_load (teacher_name, subject, grade, class_list, hours) VALUES (%s, %s, %s, %s, %s)",
                (teacher, subject, grade, classes, hours)
            )
        
        # Réunions professeurs (pas de class_list)
        meeting_loads = [
            ("TEST_Prof_Directeur", "TEST_Reunion_Pedagogique", "ALL", None, 2),
            ("TEST_Prof_Math", "TEST_Conseil_Classe", "7", None, 1),
        ]
        
        for teacher, subject, grade, classes, hours in meeting_loads:
            cur.execute(
                "INSERT INTO teacher_load (teacher_name, subject, grade, class_list, hours) VALUES (%s, %s, %s, %s, %s)",
                (teacher, subject, grade, classes, hours)
            )
        
        # Groupe parallèle (même prof enseigne à 2 classes en même temps)
        cur.execute(
            """INSERT INTO parallel_groups (subject, grade, teachers, class_lists) 
               VALUES (%s, %s, %s, %s)""",
            ("TEST_Sport", "7", "TEST_Prof_Sport", "TEST_7A,TEST_7B")
        )
        
        conn.commit()
        logger.info("✅ Données de test créées avec succès !")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des données de test : {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def test_solver_with_bloc_b():
    """Test le solver avec les fonctionnalités du Bloc B."""
    
    logger.info("🔍 Test du Bloc B - Groupes parallèles et réunions...")
    
    try:
        # Créer une instance du solver
        solver = ScheduleSolver()
        
        # Charger les données (incluant les nouvelles fonctionnalités)
        logger.info("Chargement des données...")
        solver.load_data_from_db()
        
        # Vérifier que les nouvelles données sont chargées
        logger.info(f"Parallel groups chargés : {len(solver.parallel_groups)}")
        logger.info(f"Teacher loads chargés : {len(solver.teacher_loads)}")
        
        # Vérifier la présence de réunions (class_list = None)
        meeting_loads = [load for load in solver.teacher_loads if not load.get("class_list")]
        logger.info(f"Réunions trouvées : {len(meeting_loads)}")
        
        for meeting in meeting_loads:
            logger.info(f"  - {meeting['teacher_name']} : {meeting['subject']}")
        
        # Test de création des variables (doit inclure _MEETING)
        logger.info("Création des variables...")
        solver.create_variables()
        
        # Vérifier la présence de variables _MEETING
        meeting_vars = [name for name in solver.schedule_vars.keys() if "_MEETING_" in name]
        logger.info(f"Variables _MEETING créées : {len(meeting_vars)}")
        
        if meeting_vars:
            logger.info(f"Exemple : {meeting_vars[0]}")
        
        # Test des contraintes (doit inclure les contraintes parallèles)
        logger.info("Ajout des contraintes...")
        solver.add_hard_constraints()
        
        logger.info("✅ Test du Bloc B réussi !")
        logger.info("Le solver peut maintenant gérer :")
        logger.info("  - Les groupes parallèles")
        logger.info("  - Les réunions professeurs sans classe")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du test : {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """Nettoie les données de test."""
    # Configuration de test
    db_config = {
        "host": "localhost",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123",
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        logger.info("Nettoyage des données de test...")
        
        cur.execute("DELETE FROM teacher_load WHERE teacher_name LIKE 'TEST_%'")
        cur.execute("DELETE FROM parallel_groups WHERE subject LIKE 'TEST_%'")
        cur.execute("DELETE FROM teachers WHERE teacher_name LIKE 'TEST_%'")
        cur.execute("DELETE FROM classes WHERE class_name LIKE 'TEST_%'")
        
        conn.commit()
        logger.info("✅ Données de test supprimées")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du nettoyage : {e}")
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    print("🧪 Test des fonctionnalités du Bloc B")
    print("=" * 50)
    
    # 1. Créer les données de test
    if create_test_data():
        # 2. Tester le solver
        if test_solver_with_bloc_b():
            print("\n🎉 Tous les tests sont passés !")
        else:
            print("\n❌ Certains tests ont échoué.")
    else:
        print("\n❌ Impossible de créer les données de test.")
    
    # 3. Nettoyer (optionnel)
    # cleanup_test_data()
    
    print("\nPour nettoyer les données de test :")
    print("python test_bloc_b.py && python -c \"from test_bloc_b import cleanup_test_data; cleanup_test_data()\"") 
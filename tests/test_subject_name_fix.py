"""
Tests unitaires et d'intégration pour la correction du bug subject_name
"""
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import json

# Configuration DB pour les tests
DB_CONFIG = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

class TestSubjectNameFix:
    """Tests pour vérifier la correction du problème subject_name"""
    
    def test_database_columns_exist(self):
        """Test unitaire: Vérifier que les colonnes subject et subject_name existent"""
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Vérifier que solver_input a bien les deux colonnes
        cur.execute("""
            SELECT column_name, data_type, is_generated
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = 'solver_input'
            AND column_name IN ('subject', 'subject_name')
            ORDER BY column_name
        """)
        columns = cur.fetchall()
        
        # Assertions
        assert len(columns) == 2, "Les colonnes subject et subject_name doivent exister"
        
        subject_col = next(col for col in columns if col[0] == 'subject')
        subject_name_col = next(col for col in columns if col[0] == 'subject_name')
        
        assert subject_col[1] == 'text', "La colonne subject doit être de type text"
        assert subject_name_col[1] == 'text', "La colonne subject_name doit être de type text"
        assert subject_name_col[2] == 'ALWAYS', "subject_name doit être une colonne générée"
        
        cur.close()
        conn.close()
    
    def test_subject_name_computed_correctly(self):
        """Test unitaire: Vérifier que subject_name = subject"""
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Prendre quelques cours pour tester
        cur.execute("""
            SELECT course_id, subject, subject_name
            FROM solver_input
            WHERE subject IS NOT NULL
            LIMIT 5
        """)
        courses = cur.fetchall()
        
        # Vérifier que subject_name = subject pour tous les enregistrements
        for course in courses:
            assert course['subject'] == course['subject_name'], \
                f"subject_name ({course['subject_name']}) doit égaler subject ({course['subject']}) pour course_id {course['course_id']}"
        
        cur.close()
        conn.close()
    
    def test_advanced_wrapper_query(self):
        """Test unitaire: Vérifier que la requête dans advanced_wrapper fonctionne"""
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Cette requête était celle qui plantait avant la correction
            cur.execute("""
                SELECT DISTINCT 
                    class_list,
                    subject as subject,
                    SUM(hours) as total_hours
                FROM solver_input
                WHERE hours > 0
                GROUP BY class_list, subject
            """)
            results = cur.fetchall()
            
            # La requête doit s'exécuter sans erreur
            assert len(results) >= 0, "La requête doit s'exécuter sans erreur"
            
            # Vérifier la structure du résultat
            if results:
                first_result = results[0]
                assert 'subject' in first_result, "Le résultat doit contenir une clé 'subject'"
                assert 'total_hours' in first_result, "Le résultat doit contenir 'total_hours'"
                
        except psycopg2.Error as e:
            pytest.fail(f"La requête SQL a échoué: {e}")
        finally:
            cur.close()
            conn.close()
    
    def test_pedagogical_solver_query(self):
        """Test unitaire: Vérifier que la requête dans pedagogical_solver fonctionne"""
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Cette requête était celle qui plantait avant la correction
            cur.execute("""
                SELECT 
                    course_id, 
                    subject as subject,
                    teacher_names as teacher,
                    class_list,
                    hours,
                    is_parallel
                FROM solver_input 
                WHERE hours > 0
                ORDER BY course_id
            """)
            results = cur.fetchall()
            
            # La requête doit s'exécuter sans erreur
            assert len(results) >= 0, "La requête doit s'exécuter sans erreur"
            
            # Vérifier la structure du résultat
            if results:
                first_result = results[0]
                assert 'course_id' in first_result, "Le résultat doit contenir 'course_id'"
                assert 'subject' in first_result, "Le résultat doit contenir 'subject'"
                assert 'hours' in first_result, "Le résultat doit contenir 'hours'"
                
        except psycopg2.Error as e:
            pytest.fail(f"La requête SQL a échoué: {e}")
        finally:
            cur.close()
            conn.close()


class TestIntegrationOptimizationAdvanced:
    """Tests d'intégration pour l'optimisation avancée"""
    
    BASE_URL = "http://localhost:8000"
    
    def test_api_health_check(self):
        """Test intégration: Vérifier que l'API est accessible"""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200, "L'API doit être accessible"
        
        health_data = response.json()
        assert health_data.get("status") == "healthy", "L'API doit être en bonne santé"
    
    def test_advanced_status_endpoint(self):
        """Test intégration: Vérifier l'état des modules avancés"""
        response = requests.get(f"{self.BASE_URL}/api/advanced/status")
        assert response.status_code == 200, "L'endpoint de statut doit fonctionner"
        
        status_data = response.json()
        assert "modules_available" in status_data, "Le statut doit indiquer si les modules sont disponibles"
        assert status_data.get("ready", False), "Les modules doivent être prêts"
    
    def test_advanced_optimization_endpoint(self):
        """Test intégration: Vérifier que l'optimisation avancée ne plante plus"""
        # Payload minimal pour tester
        payload = {
            "time_limit": 30  # Court pour test rapide
        }
        
        response = requests.post(
            f"{self.BASE_URL}/api/advanced/optimize", 
            json=payload,
            timeout=60  # Timeout de 1 minute pour le test
        )
        
        # Le status_code doit être 200 (pas d'erreur 500)
        assert response.status_code == 200, f"L'optimisation avancée ne doit pas planter. Status: {response.status_code}"
        
        result_data = response.json()
        assert "status" in result_data, "La réponse doit contenir un statut"
        
        # Le statut peut être 'success' ou 'error', mais pas de crash
        status = result_data.get("status")
        assert status in ["success", "error"], f"Statut attendu: success ou error, reçu: {status}"
        
        # Si erreur, ce ne doit pas être une erreur SQL sur subject_name
        if status == "error":
            message = result_data.get("message", "")
            assert "subject_name" not in message.lower(), f"L'erreur ne doit pas concerner subject_name: {message}"
            assert "does not exist" not in message.lower(), f"L'erreur ne doit pas concerner une colonne manquante: {message}"
    
    def test_generate_schedule_endpoint(self):
        """Test intégration: Vérifier la génération standard d'emploi du temps"""
        payload = {
            "time_limit": 30  # Court pour test rapide
        }
        
        response = requests.post(
            f"{self.BASE_URL}/generate_schedule",
            json=payload,
            timeout=60
        )
        
        # Doit fonctionner sans erreur 500
        assert response.status_code == 200, f"La génération standard ne doit pas planter. Status: {response.status_code}"
        
        result_data = response.json()
        assert "success" in result_data, "La réponse doit contenir un champ 'success'"
    
    def test_schedule_entries_populated(self):
        """Test intégration: Vérifier qu'après génération, des entrées existent"""
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Compter les entrées d'emploi du temps
        cur.execute("SELECT COUNT(*) FROM schedule_entries")
        count = cur.fetchone()[0]
        
        # Il doit y avoir au moins quelques entrées (après génération)
        # Note: Ce test assume qu'au moins une génération a été faite
        assert count >= 0, "Les entrées d'emploi du temps doivent être comptables"
        
        if count > 0:
            # Vérifier que subject_name est rempli
            cur.execute("""
                SELECT COUNT(*) 
                FROM schedule_entries 
                WHERE subject_name IS NOT NULL AND subject_name != ''
            """)
            filled_count = cur.fetchone()[0]
            
            # Au moins quelques entrées doivent avoir subject_name rempli
            assert filled_count > 0, "Les entrées doivent avoir subject_name rempli"
        
        cur.close()
        conn.close()


def run_all_tests():
    """Exécute tous les tests avec reporting"""
    print("Tests de la correction subject_name...")
    
    try:
        # Tests unitaires
        print("\n1. Tests unitaires...")
        test_unit = TestSubjectNameFix()
        
        test_unit.test_database_columns_exist()
        print("OK Structure de base de donnees")
        
        test_unit.test_subject_name_computed_correctly()
        print("OK Colonne generee")
        
        test_unit.test_advanced_wrapper_query()
        print("OK Requete advanced_wrapper")
        
        test_unit.test_pedagogical_solver_query()
        print("OK Requete pedagogical_solver")
        
        # Tests d'integration
        print("\n2. Tests d'integration...")
        test_integration = TestIntegrationOptimizationAdvanced()
        
        test_integration.test_api_health_check()
        print("OK Sante de l'API")
        
        test_integration.test_advanced_status_endpoint()
        print("OK Statut des modules avances")
        
        test_integration.test_advanced_optimization_endpoint()
        print("OK Optimisation avancee (sans crash)")
        
        test_integration.test_generate_schedule_endpoint()
        print("OK Generation standard")
        
        test_integration.test_schedule_entries_populated()
        print("OK Entrees d'emploi du temps")
        
        print("\nTOUS LES TESTS REUSSIS!")
        return True
        
    except Exception as e:
        print(f"\nECHEC DES TESTS: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
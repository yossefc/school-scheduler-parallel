#!/usr/bin/env python3
# debug_constraints.py - Script pour debugger les problèmes de contraintes

import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import sys

# Configuration
API_URL = "http://localhost:8000"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123"
}

def check_database():
    """Vérifie la connexion et l'état de la BD"""
    print("🔍 Vérification de la base de données...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier les contraintes
        cur.execute("SELECT COUNT(*) as count FROM constraints")
        count = cur.fetchone()['count']
        print(f"✅ Nombre de contraintes dans la BD: {count}")
        
        # Afficher les dernières contraintes
        cur.execute("""
            SELECT constraint_id, constraint_type, entity_name, is_active, created_at 
            FROM constraints 
            ORDER BY constraint_id DESC 
            LIMIT 5
        """)
        constraints = cur.fetchall()
        
        if constraints:
            print("\n📋 Dernières contraintes:")
            for c in constraints:
                print(f"  - ID: {c['constraint_id']}, Type: {c['constraint_type']}, "
                      f"Entity: {c['entity_name']}, Active: {c['is_active']}")
        else:
            print("⚠️  Aucune contrainte trouvée")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur BD: {e}")
        return False

def test_api_connection():
    """Teste la connexion à l'API"""
    print("\n🔍 Test de l'API...")
    try:
        response = requests.get(f"{API_URL}/")
        if response.status_code == 200:
            print("✅ API accessible")
            return True
        else:
            print(f"❌ API retourne code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erreur de connexion API: {e}")
        return False

def test_list_constraints():
    """Teste la liste des contraintes via l'API"""
    print("\n🔍 Test endpoint /constraints...")
    try:
        response = requests.get(f"{API_URL}/constraints")
        if response.status_code == 200:
            constraints = response.json()
            print(f"✅ Endpoint fonctionne, {len(constraints)} contraintes retournées")
            return constraints
        else:
            print(f"❌ Erreur: {response.status_code}")
            print(f"   Réponse: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_add_constraint():
    """Teste l'ajout d'une contrainte"""
    print("\n🔍 Test d'ajout de contrainte...")
    
    test_constraint = {
        "constraint_type": "teacher_availability",
        "entity_name": "TEST_DEBUG",
        "constraint_data": {
            "unavailable_days": [5],
            "unavailable_periods": [7, 8, 9]
        },
        "priority": 2
    }
    
    try:
        response = requests.post(
            f"{API_URL}/constraints",
            json=test_constraint,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Contrainte ajoutée avec ID: {result.get('constraint_id', 'inconnu')}")
            return result
        else:
            print(f"❌ Erreur: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout: {e}")
        return None

def test_generate_schedule():
    """Teste la génération d'emploi du temps"""
    print("\n🔍 Test de génération d'emploi du temps...")
    
    request_data = {
        "constraints": [],
        "time_limit": 30
    }
    
    try:
        response = requests.post(
            f"{API_URL}/generate_schedule",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result:
                print(f"✅ Emploi du temps généré avec {len(result.get('schedule', []))} entrées")
            else:
                print("⚠️  Réponse vide")
        else:
            print(f"❌ Erreur: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

def check_solver_data():
    """Vérifie les données nécessaires au solver"""
    print("\n🔍 Vérification des données pour le solver...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Tables à vérifier
        checks = {
            "teachers": "SELECT COUNT(*) FROM teachers",
            "classes": "SELECT COUNT(*) FROM classes",
            "time_slots": "SELECT COUNT(*) FROM time_slots",
            "teacher_load": "SELECT COUNT(*) FROM teacher_load"
        }
        
        all_ok = True
        for table, query in checks.items():
            cur.execute(query)
            count = cur.fetchone()[0]
            if count > 0:
                print(f"✅ {table}: {count} entrées")
            else:
                print(f"❌ {table}: VIDE!")
                all_ok = False
                
        conn.close()
        return all_ok
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    print("="*60)
    print("🐛 DEBUG DES CONTRAINTES ET DE LA GÉNÉRATION")
    print("="*60)
    
    # 1. Vérifier la BD
    if not check_database():
        print("\n⚠️  Problème de connexion à la BD")
        print("Vérifiez que PostgreSQL est accessible sur localhost:5432")
        return
    
    # 2. Vérifier l'API
    if not test_api_connection():
        print("\n⚠️  L'API n'est pas accessible")
        print("Vérifiez que le solver est démarré sur le port 8000")
        return
    
    # 3. Vérifier les données
    if not check_solver_data():
        print("\n⚠️  Données manquantes pour le solver")
        print("Chargez d'abord les données de base (teachers, classes, etc.)")
        return
    
    # 4. Tester la liste des contraintes
    constraints = test_list_constraints()
    
    # 5. Tester l'ajout
    new_constraint = test_add_constraint()
    
    # 6. Vérifier si la contrainte a été ajoutée
    if new_constraint:
        print("\n🔍 Vérification de l'ajout...")
        constraints_after = test_list_constraints()
        if constraints_after and len(constraints_after) > len(constraints or []):
            print("✅ La contrainte a bien été ajoutée à la liste")
        else:
            print("❌ La contrainte n'apparaît pas dans la liste")
    
    # 7. Tester la génération
    test_generate_schedule()
    
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
    print("="*60)
    
    print("\n🔧 Actions recommandées:")
    print("1. Vérifiez les logs Docker: docker-compose logs -f solver")
    print("2. Vérifiez que api_constraints.py est bien importé dans main.py")
    print("3. Vérifiez la configuration de la BD (host: 'postgres' dans Docker)")
    print("4. Testez manuellement: curl http://localhost:8000/docs")

if __name__ == "__main__":
    main()
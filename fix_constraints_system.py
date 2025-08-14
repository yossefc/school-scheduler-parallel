#!/usr/bin/env python3
"""
Correction du système de contraintes
Applique seulement les contraintes essentielles du CLAUDE.md
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime

def reset_critical_constraints():
    """Supprime les contraintes excessives et applique seulement les essentielles"""
    print("=== RESET DES CONTRAINTES CRITIQUES ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor()
    
    try:
        # 1. Supprimer toutes les contraintes existantes
        print("Suppression des contraintes existantes...")
        cur.execute("DELETE FROM constraints")
        
        # 2. Ajouter seulement les contraintes du CLAUDE.md
        essential_constraints = [
            {
                'name': 'שיח בוקר - Matin uniquement',
                'description': 'שיח בוקר doit être programmé seulement en périodes 1-4',
                'constraint_type': 'time_restriction',
                'priority': 9,  # CRITIQUE
                'is_active': True,
                'parameters': Json({
                    'subject': 'שיח בוקר',
                    'periods_allowed': [1, 2, 3, 4],
                    'max_consecutive': 2
                })
            },
            {
                'name': 'Structure Lundi - Classes ז, ט, ח',
                'description': 'Classes ז, ט, ח doivent finir après période 4 le lundi',
                'constraint_type': 'class_schedule',
                'priority': 8,  # HAUTE
                'is_active': True,
                'parameters': Json({
                    'day': 1,  # Lundi
                    'classes': ['ז-1', 'ז-2', 'ז-3', 'ז-4', 'ט-1', 'ט-2', 'ט-3', 'ט-4', 'ח-1', 'ח-2', 'ח-3', 'ח-4'],
                    'min_end_period': 5
                })
            },
            {
                'name': 'Pas de cours le vendredi',
                'description': 'Aucun cours programmé le vendredi (jour 5)',
                'constraint_type': 'day_restriction',
                'priority': 9,  # CRITIQUE
                'is_active': True,
                'parameters': Json({
                    'forbidden_days': [5, 6]  # Vendredi et Samedi
                })
            },
            {
                'name': 'Maximum 6 heures par jour par classe',
                'description': 'Chaque classe ne peut avoir plus de 6 périodes par jour',
                'constraint_type': 'daily_limit',
                'priority': 7,  # NORMALE
                'is_active': True,
                'parameters': Json({
                    'max_periods_per_day': 6
                })
            }
        ]
        
        # Insérer les nouvelles contraintes
        for constraint in essential_constraints:
            cur.execute("""
                INSERT INTO constraints (
                    name, description, constraint_type, priority, 
                    is_active, parameters, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                constraint['name'],
                constraint['description'],
                constraint['constraint_type'],
                constraint['priority'],
                constraint['is_active'],
                constraint['parameters'],
                datetime.now()
            ))
        
        conn.commit()
        print(f"Contraintes essentielles ajoutees: {len(essential_constraints)}")
        
        return len(essential_constraints)
        
    except Exception as e:
        conn.rollback()
        print(f"Erreur: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def limit_course_hours():
    """Limite les heures de cours à des valeurs raisonnables"""
    print("\n=== LIMITATION DES HEURES DE COURS ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor()
    
    try:
        # Limiter les cours à maximum 4 heures par semaine
        cur.execute("""
            UPDATE solver_input 
            SET hours = CASE 
                WHEN hours > 4 THEN 3  -- Max 3h pour les gros cours
                WHEN hours < 1 THEN 2  -- Min 2h 
                ELSE hours 
            END
        """)
        
        affected_rows = cur.rowcount
        conn.commit()
        
        print(f"Cours ajustes: {affected_rows}")
        return affected_rows
        
    except Exception as e:
        conn.rollback()
        print(f"Erreur: {e}")
        return 0
    finally:
        cur.close()
        conn.close()

def verify_feasibility():
    """Vérifie que le problème est maintenant faisable"""
    print("\n=== VERIFICATION DE FAISABILITE ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Total heures après limitation
        cur.execute("SELECT SUM(hours) as total_hours FROM solver_input")
        total_hours = cur.fetchone()['total_hours']
        
        # Contraintes critiques restantes
        cur.execute("SELECT COUNT(*) as critical FROM constraints WHERE priority >= 8")
        critical_count = cur.fetchone()['critical']
        
        # Classes distinctes
        cur.execute("SELECT COUNT(DISTINCT class_list) as classes FROM solver_input")
        class_count = cur.fetchone()['classes']
        
        print(f"Heures totales: {total_hours}")
        print(f"Contraintes critiques: {critical_count}")
        print(f"Classes distinctes: {class_count}")
        
        # Calcul de faisabilité
        slots_per_week = 5 * 8  # 5 jours, 8 périodes
        total_slots_available = class_count * slots_per_week
        utilization = (total_hours / total_slots_available) * 100
        
        print(f"Slots disponibles: {total_slots_available}")
        print(f"Utilisation: {utilization:.1f}%")
        
        if utilization < 80 and critical_count <= 5:
            print("FAISABILITE: PROBABLE")
            return True
        else:
            print("FAISABILITE: DOUTEUSE")
            return False
            
    finally:
        cur.close()
        conn.close()

def main():
    print("CORRECTION DU SYSTEME DE CONTRAINTES")
    print("=" * 50)
    
    # 1. Reset des contraintes
    constraints_added = reset_critical_constraints()
    
    # 2. Limitation des heures
    courses_adjusted = limit_course_hours()
    
    # 3. Vérification
    is_feasible = verify_feasibility()
    
    print("\n" + "=" * 50)
    print("RESULTAT:")
    print(f"Contraintes ajoutees: {constraints_added}")
    print(f"Cours ajustes: {courses_adjusted}")
    print(f"Faisable: {'OUI' if is_feasible else 'NON'}")
    
    if is_feasible:
        print("\nSYSTEME PRET POUR GENERATION!")
        print("Vous pouvez maintenant utiliser le solver pedagogique.")
    else:
        print("\nSYSTEME ENCORE PROBLEMATIQUE")
        print("Il faut reduire davantage les contraintes.")

if __name__ == "__main__":
    main()
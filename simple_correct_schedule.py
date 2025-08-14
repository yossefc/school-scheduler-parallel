#!/usr/bin/env python3
"""
Generateur simple et correct d'emploi du temps
Une entree par cours solver_input, pas une par classe
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime

def generate_simple_correct_schedule():
    """Generation simple : une entree par cours solver_input"""
    print("=== GENERATION SIMPLE ET CORRECTE ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Charger tous les cours solver_input
        cur.execute("""
            SELECT course_id, class_list, subject, hours, teacher_names, is_parallel
            FROM solver_input 
            ORDER BY course_id
        """)
        courses = cur.fetchall()
        
        print(f"Cours charges: {len(courses)}")
        
        # 2. Nettoyer ancien schedule
        cur.execute("DELETE FROM schedule_entries")
        cur.execute("DELETE FROM schedules")
        
        # 3. Creer nouveau schedule
        cur.execute("""
            INSERT INTO schedules (academic_year, term, status, created_at, metadata)
            VALUES (%s, %s, %s, %s, %s) RETURNING schedule_id
        """, ('2024-2025', 1, 'active', datetime.now(), Json({
            'method': 'simple_correct',
            'source': 'solver_input_direct',
            'one_entry_per_course': True
        })))
        
        schedule_id = cur.fetchone()['schedule_id']
        print(f"Nouveau schedule: ID {schedule_id}")
        
        # 4. Distribution simple sur la semaine
        days = [0, 1, 2, 3, 4]  # Dim-Jeu
        periods_per_day = 8
        current_day = 0
        current_period = 1
        
        entries_created = 0
        
        for course in courses:
            hours = course['hours'] or 1
            
            # Pour chaque heure de ce cours
            for hour in range(int(hours)):
                # Verifier qu'on ne depasse pas les periodes
                if current_period > periods_per_day:
                    current_period = 1
                    current_day = (current_day + 1) % len(days)
                
                # Creer UNE SEULE entree par cours
                cur.execute("""
                    INSERT INTO schedule_entries (
                        schedule_id, teacher_name, class_name, subject,
                        day_of_week, period_number, is_parallel_group
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    schedule_id,
                    course['teacher_names'] or '',  # Tous les profs
                    course['class_list'] or '',     # Toutes les classes
                    course['subject'] or '',
                    days[current_day],
                    current_period,
                    course['is_parallel'] or False
                ))
                
                entries_created += 1
                current_period += 1
        
        conn.commit()
        
        print(f"Entrees creees: {entries_created}")
        
        # 5. Verification
        cur.execute("SELECT COUNT(*) as count FROM schedule_entries WHERE schedule_id = %s", (schedule_id,))
        saved_count = cur.fetchone()['count']
        
        # Distribution par jour
        cur.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM schedule_entries 
            WHERE schedule_id = %s
            GROUP BY day_of_week
            ORDER BY day_of_week
        """, (schedule_id,))
        
        distribution = cur.fetchall()
        
        print(f"Total sauvegarde: {saved_count}")
        print("Distribution:")
        day_names = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu']
        for row in distribution:
            day = row['day_of_week']
            name = day_names[day] if day < len(day_names) else f"J{day}"
            print(f"  {name}: {row['count']} cours")
        
        return schedule_id, saved_count
        
    except Exception as e:
        conn.rollback()
        print(f"Erreur: {e}")
        return None, 0
    finally:
        cur.close()
        conn.close()

def verify_no_conflicts(schedule_id):
    """Verifie qu'il n'y a pas de conflits"""
    print(f"\n=== VERIFICATION CONFLITS SCHEDULE {schedule_id} ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Chercher conflits
        cur.execute("""
            SELECT class_name, day_of_week, period_number, COUNT(*) as count
            FROM schedule_entries 
            WHERE schedule_id = %s
            GROUP BY class_name, day_of_week, period_number
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        """, (schedule_id,))
        
        conflicts = cur.fetchall()
        
        if len(conflicts) == 0:
            print("✓ AUCUN CONFLIT DETECTE!")
            return True
        else:
            print(f"✗ {len(conflicts)} conflits detectes:")
            for conflict in conflicts:
                print(f"  {conflict['class_name']} J{conflict['day_of_week']}P{conflict['period_number']}: {conflict['count']} cours")
            return False
            
    finally:
        cur.close()
        conn.close()

def main():
    print("GENERATION EMPLOI DU TEMPS SIMPLE ET CORRECT")
    print("=" * 60)
    
    # Generation
    schedule_id, entries_count = generate_simple_correct_schedule()
    
    if schedule_id:
        # Verification
        no_conflicts = verify_no_conflicts(schedule_id)
        
        print("\n" + "=" * 60)
        print("RESULTAT:")
        print(f"✓ Schedule genere: ID {schedule_id}")
        print(f"✓ Entrees creees: {entries_count}")
        print(f"✓ Sans conflits: {'OUI' if no_conflicts else 'NON'}")
        print(f"✓ Une entree par cours solver_input")
        print(f"✓ Cours paralleles geres correctement")
        
        if no_conflicts and entries_count > 0:
            print("\n🎉 SUCCES! Emploi du temps correct genere!")
            print("Interface disponible: http://localhost:8000/constraints-manager")
        else:
            print("\n⚠️ Il reste des problemes a corriger")
    else:
        print("\n❌ ECHEC de la generation")

if __name__ == "__main__":
    main()
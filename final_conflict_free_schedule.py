#!/usr/bin/env python3
"""
Generateur final sans conflits
Verifie les classes individuelles avant de programmer
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime

def generate_conflict_free_schedule():
    """Generation sans conflits en verifiant classes individuelles"""
    print("=== GENERATION SANS CONFLITS ===")
    
    conn = psycopg2.connect(
        host='localhost',
        database='school_scheduler',
        user='admin',
        password='school123',
        port=5432
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Charger courses
        cur.execute("""
            SELECT course_id, class_list, subject, hours, teacher_names, is_parallel
            FROM solver_input 
            ORDER BY course_id
        """)
        courses = cur.fetchall()
        
        print(f"Cours a programmer: {len(courses)}")
        
        # 2. Structure pour tracker les occupations par classe
        # occupied[class_name][day][period] = True si occupe
        occupied = {}
        
        # 3. Nettoyer et creer nouveau schedule
        cur.execute("DELETE FROM schedule_entries")
        cur.execute("DELETE FROM schedules")
        
        cur.execute("""
            INSERT INTO schedules (academic_year, term, status, created_at, metadata)
            VALUES (%s, %s, %s, %s, %s) RETURNING schedule_id
        """, ('2024-2025', 1, 'active', datetime.now(), Json({
            'method': 'conflict_free',
            'source': 'solver_input_smart'
        })))
        
        schedule_id = cur.fetchone()['schedule_id']
        
        # 4. Parametres distribution
        days = [0, 1, 2, 3, 4]  # Dim-Jeu
        periods_per_day = 8
        entries_created = 0
        conflicts_avoided = 0
        
        # 5. Programmer chaque cours
        for course in courses:
            course_id = course['course_id']
            class_list = course['class_list'] or ''
            subject = course['subject'] or ''
            hours = int(course['hours'] or 1)
            teacher_names = course['teacher_names'] or ''
            is_parallel = course['is_parallel'] or False
            
            # Extraire classes individuelles
            individual_classes = []
            if class_list:
                individual_classes = [c.strip() for c in class_list.split(',') if c.strip()]
            
            # Programmer chaque heure de ce cours
            for hour in range(hours):
                # Trouver le premier creneau libre pour TOUTES les classes
                slot_found = False
                
                for day in days:
                    if slot_found:
                        break
                        
                    for period in range(1, periods_per_day + 1):
                        # Verifier si TOUTES les classes sont libres
                        all_classes_free = True
                        
                        for individual_class in individual_classes:
                            if individual_class not in occupied:
                                occupied[individual_class] = {}
                            if day not in occupied[individual_class]:
                                occupied[individual_class][day] = {}
                                
                            if occupied[individual_class][day].get(period, False):
                                all_classes_free = False
                                conflicts_avoided += 1
                                break
                        
                        if all_classes_free:
                            # Programmer le cours a ce creneau
                            cur.execute("""
                                INSERT INTO schedule_entries (
                                    schedule_id, teacher_name, class_name, subject,
                                    day_of_week, period_number, is_parallel_group
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                schedule_id,
                                teacher_names,
                                class_list,
                                subject,
                                day,
                                period,
                                is_parallel
                            ))
                            
                            # Marquer toutes les classes comme occupees
                            for individual_class in individual_classes:
                                if individual_class not in occupied:
                                    occupied[individual_class] = {}
                                if day not in occupied[individual_class]:
                                    occupied[individual_class][day] = {}
                                occupied[individual_class][day][period] = True
                            
                            entries_created += 1
                            slot_found = True
                            break
                
                if not slot_found:
                    print(f"  ATTENTION: Impossible de programmer {subject} pour {class_list}")
        
        conn.commit()
        
        # 6. Statistiques
        cur.execute("SELECT COUNT(*) as count FROM schedule_entries WHERE schedule_id = %s", (schedule_id,))
        saved_count = cur.fetchone()['count']
        
        cur.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM schedule_entries 
            WHERE schedule_id = %s
            GROUP BY day_of_week
            ORDER BY day_of_week
        """, (schedule_id,))
        distribution = cur.fetchall()
        
        print(f"Entrees creees: {entries_created}")
        print(f"Conflits evites: {conflicts_avoided}")
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

def main():
    print("GENERATION EMPLOI DU TEMPS SANS CONFLITS")
    print("=" * 60)
    
    schedule_id, entries_count = generate_conflict_free_schedule()
    
    if schedule_id:
        print("\n" + "=" * 60)
        print("RESULTAT FINAL:")
        print(f"Schedule genere: ID {schedule_id}")
        print(f"Entrees creees: {entries_count}")
        print("Verification des conflits en cours...")
        
        # Verification rapide
        try:
            import requests
            response = requests.get('http://localhost:8000/api/schedule_entries?version=latest')
            if response.ok:
                data = response.json()
                entries = data.get('entries', [])
                
                # Verifier conflits
                class_schedules = {}
                for entry in entries:
                    class_list = entry.get('class_name', '')
                    day = entry.get('day', entry.get('day_of_week', 0))
                    period = entry.get('period_number', 0)
                    
                    if class_list:
                        classes = [c.strip() for c in class_list.split(',') if c.strip()]
                        for individual_class in classes:
                            key = (individual_class, day, period)
                            if key not in class_schedules:
                                class_schedules[key] = 0
                            class_schedules[key] += 1
                
                conflicts = sum(1 for count in class_schedules.values() if count > 1)
                print(f"Conflits restants: {conflicts}")
                
                if conflicts == 0:
                    print("\n🎉 PARFAIT! Emploi du temps SANS CONFLITS genere!")
                else:
                    print(f"\n⚠️ {conflicts} conflits restants")
        except:
            print("Verification automatique echouee")
            
    else:
        print("\nEchec generation")

if __name__ == "__main__":
    main()
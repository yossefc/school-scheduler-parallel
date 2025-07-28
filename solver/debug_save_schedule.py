# debug_save_schedule.py
# Placez ce fichier dans C:\school-scheduler\solver\

import psycopg2
from ortools.sat.python import cp_model

# Test simple pour vérifier la sauvegarde
def test_save():
    conn = psycopg2.connect(
        host="localhost",
        database="school_scheduler", 
        user="admin",
        password="school123",
        port=5432
    )
    cur = conn.cursor()
    
    try:
        # Créer un schedule de test
        cur.execute("""
            INSERT INTO schedules (academic_year, term, status)
            VALUES ('2024-2025', 1, 'test')
            RETURNING schedule_id
        """)
        schedule_id = cur.fetchone()[0]
        print(f"Created schedule ID: {schedule_id}")
        
        # Insérer une entrée de test
        cur.execute("""
            INSERT INTO schedule_entries 
            (schedule_id, teacher_name, class_name, subject_name, day_of_week, period_number)
            VALUES (%s, 'Test Teacher', 'Test Class', 'Test Subject', 0, 1)
        """, (schedule_id,))
        
        conn.commit()
        print("✓ Save test successful!")
        
        # Vérifier
        cur.execute("SELECT COUNT(*) FROM schedule_entries WHERE schedule_id = %s", (schedule_id,))
        count = cur.fetchone()[0]
        print(f"Entries saved: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    test_save()
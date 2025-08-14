"""
Script pour vérifier les trous dans l'emploi du temps
"""
import psycopg2
from psycopg2.extras import RealDictCursor

db_config = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

def check_gaps():
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Récupérer le dernier schedule
    cur.execute("SELECT MAX(schedule_id) as id FROM schedules")
    schedule_id = cur.fetchone()['id']
    print(f"Analyse du schedule #{schedule_id}")
    print("="*60)
    
    # Analyser par classe
    cur.execute("""
        SELECT DISTINCT class_name 
        FROM schedule_entries 
        WHERE schedule_id = %s 
        ORDER BY class_name
    """, (schedule_id,))
    
    classes = [row['class_name'] for row in cur.fetchall()]
    
    gaps_found = False
    
    for class_name in classes[:10]:  # Analyser les 10 premières classes
        print(f"\nClasse: {class_name}")
        print("-"*40)
        
        # Récupérer l'emploi du temps de cette classe
        cur.execute("""
            SELECT day_of_week, period_number, subject_name
            FROM schedule_entries
            WHERE schedule_id = %s AND class_name = %s
            ORDER BY day_of_week, period_number
        """, (schedule_id, class_name))
        
        schedule = cur.fetchall()
        
        # Grouper par jour
        days = {}
        for entry in schedule:
            day = entry['day_of_week']
            if day not in days:
                days[day] = []
            days[day].append(entry['period_number'])
        
        # Vérifier les trous pour chaque jour
        for day, periods in days.items():
            periods.sort()
            
            # Vérifier s'il y a des trous
            gaps = []
            for i in range(len(periods) - 1):
                if periods[i+1] - periods[i] > 1:
                    gap_start = periods[i] + 1
                    gap_end = periods[i+1] - 1
                    gaps.append((gap_start, gap_end))
            
            if gaps:
                gaps_found = True
                print(f"  Jour {day}: Périodes {periods}")
                for gap_start, gap_end in gaps:
                    if gap_start == gap_end:
                        print(f"    ⚠️ TROU: Période {gap_start} vide")
                    else:
                        print(f"    ⚠️ TROU: Périodes {gap_start}-{gap_end} vides")
            else:
                print(f"  Jour {day}: ✅ Pas de trous (périodes: {periods})")
    
    print("\n" + "="*60)
    if gaps_found:
        print("DES TROUS ONT ETE DETECTES DANS L'EMPLOI DU TEMPS")
    else:
        print("AUCUN TROU DETECTE")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_gaps()
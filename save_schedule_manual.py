# save_schedule_manual.py
import json
import psycopg2
from datetime import datetime

# Connexion à la base de données
db_config = {
    "host": "postgres",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

print("📝 Sauvegarde manuelle de l'emploi du temps...")
print("-" * 50)

try:
    # 1. Lire le fichier JSON généré
    with open('schedule_generated.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    schedule = data.get('schedule', [])
    print(f"✅ {len(schedule)} créneaux trouvés dans le fichier")
    
    # 2. Connexion à la base
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    # 3. Créer un nouveau schedule
    cur.execute("""
        INSERT INTO schedules (academic_year, term, status, created_at)
        VALUES (%s, %s, %s, %s) RETURNING schedule_id
    """, ('2024-2025', 1, 'active', datetime.now()))
    
    schedule_id = cur.fetchone()[0]
    print(f"✅ Schedule créé avec ID: {schedule_id}")
    
    # 4. Insérer chaque entrée
    inserted = 0
    for entry in schedule:
        try:
            # Extraire les données
            teacher_name = entry.get('teacher_name', 'Unknown')
            class_name = entry.get('class_name', '')
            subject_name = entry.get('subject_name', entry.get('subject', 'Unknown'))
            day = entry.get('day', 0)
            period = entry.get('period', 0)
            is_parallel = entry.get('is_parallel', False)
            
            # Nettoyer class_name si nécessaire
            if ',' in class_name:
                # Si c'est plusieurs classes, les séparer
                classes = class_name.split(',')
                for single_class in classes:
                    single_class = single_class.strip().replace('-', '')
                    if single_class:
                        cur.execute("""
                            INSERT INTO schedule_entries 
                            (schedule_id, teacher_name, class_name, subject_name, 
                             day_of_week, period_number, is_parallel_group)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            schedule_id,
                            teacher_name,
                            single_class,
                            subject_name,
                            day,
                            period,
                            is_parallel
                        ))
                        inserted += 1
            else:
                # Classe unique
                class_name = class_name.strip().replace('-', '')
                if class_name:
                    cur.execute("""
                        INSERT INTO schedule_entries 
                        (schedule_id, teacher_name, class_name, subject_name, 
                         day_of_week, period_number, is_parallel_group)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        schedule_id,
                        teacher_name,
                        class_name,
                        subject_name,
                        day,
                        period,
                        is_parallel
                    ))
                    inserted += 1
                    
        except Exception as e:
            print(f"⚠️ Erreur sur une entrée: {e}")
            continue
    
    # 5. Valider les changements
    conn.commit()
    print(f"✅ {inserted} entrées sauvegardées dans la base")
    
    # 6. Vérifier le résultat
    cur.execute("""
        SELECT 
            day_of_week,
            COUNT(*) as lessons
        FROM schedule_entries
        WHERE schedule_id = %s
        GROUP BY day_of_week
        ORDER BY day_of_week
    """, (schedule_id,))
    
    print("\n📊 Répartition par jour:")
    days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
    for row in cur.fetchall():
        day_name = days[row[0]] if row[0] < 6 else f"Jour {row[0]}"
        print(f"  {day_name}: {row[1]} cours")
    
    # 7. Vérifier les classes
    cur.execute("""
        SELECT 
            class_name,
            COUNT(*) as lessons
        FROM schedule_entries
        WHERE schedule_id = %s
        GROUP BY class_name
        ORDER BY class_name
        LIMIT 10
    """, (schedule_id,))
    
    print("\n📚 Exemples de classes:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} cours")
    
    cur.close()
    conn.close()
    
    print("\n✅ TERMINÉ ! L'emploi du temps est maintenant dans la base de données.")
    
except FileNotFoundError:
    print("❌ Fichier schedule_generated.json non trouvé")
    print("Exécutez d'abord :")
    print('$response = Invoke-WebRequest -Uri "http://localhost:8000/generate_schedule" -Method POST -Headers @{"Content-Type":"application/json"} -Body \'{"time_limit": 60}\'')
    print('$response.Content | Out-File -FilePath "schedule_generated.json" -Encoding UTF8')
    
except Exception as e:
    print(f"❌ Erreur: {e}")
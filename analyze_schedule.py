#!/usr/bin/env python3
"""Script pour analyser l'emploi du temps et détecter les trous"""

import requests
import json
from collections import defaultdict

def analyze_schedule():
    # Générer un emploi du temps
    response = requests.post("http://localhost:8000/generate_schedule", 
                           headers={"Content-Type": "application/json"}, 
                           json={})
    
    if not response.ok:
        print(f"Erreur API: {response.status_code}")
        return
    
    data = response.json()
    schedule = data.get("schedule", [])
    
    # Analyser par classe
    by_class_day = defaultdict(lambda: defaultdict(list))
    
    for entry in schedule:
        class_name = entry["class_name"]
        day = entry["day_of_week"]
        period = entry["period_number"]
        subject = entry["subject_name"]
        
        by_class_day[class_name][day].append((period, subject))
    
    # Analyser les trous pour יא-1
    class_to_check = "יא-1"
    
    if class_to_check not in by_class_day:
        print(f"Classe {class_to_check} non trouvée")
        return
    
    print(f"\n=== ANALYSE EMPLOI DU TEMPS POUR {class_to_check} ===")
    
    days = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    
    for day in range(6):  # Dimanche à Vendredi
        if day not in by_class_day[class_to_check]:
            print(f"{days[day]}: Pas de cours")
            continue
            
        periods = sorted(by_class_day[class_to_check][day])
        print(f"\n{days[day]}:")
        
        if not periods:
            print("  Pas de cours")
            continue
        
        # Détecter les trous
        period_numbers = [p[0] for p in periods]
        min_period = min(period_numbers)
        max_period = max(period_numbers)
        
        has_gap = False
        for p in range(min_period, max_period + 1):
            found = any(period[0] == p for period in periods)
            if found:
                period_info = next(period for period in periods if period[0] == p)
                print(f"  Période {p}: {period_info[1]}")
            else:
                print(f"  Période {p}: *** TROU ***")
                has_gap = True
        
        if not has_gap:
            print(f"  ✓ Pas de trous ({len(periods)} cours consécutifs)")
        else:
            print(f"  ❌ Trous détectés!")

if __name__ == "__main__":
    analyze_schedule()
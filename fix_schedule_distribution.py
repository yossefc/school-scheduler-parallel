#!/usr/bin/env python3
"""
Script de correction de l'emploi du temps
Corrige la distribution des cours sur tous les jours de la semaine
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8000"

def fix_schedule():
    print("Correction de l'emploi du temps - Elimination des trous")
    print("=" * 60)
    
    # 1. Vérifier le statut actuel
    print("1. Vérification du statut actuel...")
    try:
        response = requests.get(f"{API_BASE}/api/stats")
        if response.ok:
            stats = response.json()
            print(f"   Classes: {stats['general']['total_classes']}")
            print(f"   Professeurs: {stats['general']['total_teachers']}")
            print(f"   Contraintes: {stats['general']['active_constraints']}")
            print(f"   Lecons: {stats['general']['total_lessons']}")
        else:
            print(f"   ❌ Erreur API stats: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erreur connexion: {e}")
        return False
    
    # 2. Essayer le solver pédagogique avec paramètres optimisés
    print("\n2. Génération avec solver pédagogique...")
    try:
        payload = {
            "advanced": True,
            "time_limit": 600,  # 10 minutes
            "minimize_gaps": True,
            "eliminate_gaps": True,
            "prevent_conflicts": True,
            "friday_short": True,
            "optimize_pedagogical": True,
            "quality_target": 75  # Score minimum acceptable
        }
        
        print(f"   🚀 Lancement génération (timeout: {payload['time_limit']}s)")
        response = requests.post(
            f"{API_BASE}/generate_schedule", 
            json=payload, 
            timeout=payload['time_limit'] + 30
        )
        
        if response.ok:
            result = response.json()
            print(f"   ✅ Génération réussie!")
            print(f"   📊 Statut: {result.get('status', 'N/A')}")
            if 'quality_score' in result:
                print(f"   📈 Score qualité: {result['quality_score']}/100")
            if 'schedule_id' in result:
                print(f"   🆔 Schedule ID: {result['schedule_id']}")
        else:
            print(f"   ❌ Erreur génération: {response.status_code}")
            print(f"   📝 Message: {response.text}")
            return False
            
    except requests.Timeout:
        print("   ⏰ Timeout - Génération peut-être en cours...")
        print("   ⏳ Attente 30s puis vérification...")
        time.sleep(30)
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False
    
    # 3. Vérification du résultat
    print("\n3. Vérification de la nouvelle distribution...")
    try:
        response = requests.get(f"{API_BASE}/api/schedule_entries?version=latest")
        if response.ok:
            data = response.json()
            entries = data.get('entries', [])
            
            if len(entries) == 0:
                print("   ❌ Aucune entrée trouvée")
                return False
            
            # Analyse de la distribution par jour
            day_distribution = {}
            for entry in entries:
                day = entry.get('day', 0)
                if day not in day_distribution:
                    day_distribution[day] = 0
                day_distribution[day] += 1
            
            print(f"   📅 Total entrées: {len(entries)}")
            print(f"   📊 Distribution par jour:")
            day_names = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
            
            total_distributed = 0
            for day in range(7):
                count = day_distribution.get(day, 0)
                day_name = day_names[day] if day < len(day_names) else f"J{day}"
                if count > 0:
                    print(f"      {day_name}: {count} cours")
                    total_distributed += count
            
            # Vérification des trous
            days_with_content = len([d for d in day_distribution.values() if d > 0])
            
            if days_with_content >= 5:  # Au moins 5 jours utilisés
                print(f"   ✅ Bonne distribution sur {days_with_content} jours")
                return True
            elif day_distribution.get(0, 0) == len(entries):
                print(f"   ❌ PROBLÈME: Tous les cours sont encore sur le dimanche!")
                return False
            else:
                print(f"   ⚠️  Distribution partielle sur {days_with_content} jours")
                return True
                
        else:
            print(f"   ❌ Erreur vérification: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur vérification: {e}")
        return False

def show_classes_schedule():
    """Affiche un échantillon de l'emploi du temps par classe"""
    print("\n4. Aperçu de l'emploi du temps par classe...")
    try:
        response = requests.get(f"{API_BASE}/api/classes")
        if not response.ok:
            print("   ❌ Impossible de récupérer les classes")
            return
        
        classes = response.json().get('classes', [])[:3]  # Prendre les 3 premières classes
        
        for class_name in classes:
            response = requests.get(f"{API_BASE}/api/schedule/class/{class_name}")
            if response.ok:
                schedule = response.json().get('schedule', [])
                if schedule:
                    day_count = {}
                    for lesson in schedule:
                        day = lesson.get('day_of_week', 0)
                        day_count[day] = day_count.get(day, 0) + 1
                    
                    print(f"   📚 {class_name}: {len(schedule)} cours répartis sur {len(day_count)} jours")
                else:
                    print(f"   📚 {class_name}: Aucun cours trouvé")
            else:
                print(f"   📚 {class_name}: Erreur de récupération")
                
    except Exception as e:
        print(f"   ❌ Erreur aperçu: {e}")

if __name__ == "__main__":
    print("CORRECTION DE L'EMPLOI DU TEMPS")
    print("   Objectif: Eliminer les trous et bien repartir les cours")
    print()
    
    success = fix_schedule()
    
    if success:
        show_classes_schedule()
        print("\n" + "=" * 60)
        print("✅ CORRECTION TERMINÉE AVEC SUCCÈS!")
        print()
        print("📋 Actions à effectuer maintenant:")
        print("   1. Ouvrir: http://localhost:8000/constraints-manager")
        print("   2. Sélectionner une classe dans le sélecteur")
        print("   3. Vérifier que les cours sont bien répartis sur la semaine")
        print("   4. Si satisfait, l'emploi du temps est prêt!")
        print()
    else:
        print("\n" + "=" * 60)
        print("❌ ÉCHEC DE LA CORRECTION")
        print()
        print("🔧 Actions de dépannage:")
        print("   1. Vérifier que tous les services Docker sont actifs")
        print("   2. Consulter les logs: docker-compose logs -f solver")
        print("   3. Redémarrer si nécessaire: docker-compose restart")
        print("   4. Exécuter de nouveau ce script")
        print()
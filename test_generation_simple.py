#!/usr/bin/env python3
"""
Test simple de génération d'emploi du temps
Utilise les données de solver_input directement
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8000"

def test_simple_generation():
    print("=== TEST DE GÉNÉRATION SIMPLE ===")
    
    # 1. Vérifier les données disponibles
    print("1. Vérification des données...")
    try:
        response = requests.get(f"{API_BASE}/api/stats")
        if response.ok:
            stats = response.json()
            print(f"   Classes: {stats['general']['total_classes']}")
            print(f"   Professeurs: {stats['general']['total_teachers']}")
            print(f"   Contraintes actives: {stats['general']['active_constraints']}")
        else:
            print(f"   Erreur stats: {response.status_code}")
            return False
    except Exception as e:
        print(f"   Erreur: {e}")
        return False
    
    # 2. Générer avec paramètres minimaux
    print("\n2. Test génération basique...")
    try:
        payload = {
            "time_limit": 180,  # 3 minutes seulement
            "advanced": False,  # Version simple
        }
        
        print(f"   Lancement génération (timeout: {payload['time_limit']}s)")
        response = requests.post(
            f"{API_BASE}/generate_schedule", 
            json=payload, 
            timeout=payload['time_limit'] + 30
        )
        
        print(f"   Status HTTP: {response.status_code}")
        
        if response.ok:
            result = response.json()
            print(f"   Résultat: {result}")
            return True
        else:
            print(f"   Erreur génération: {response.text}")
            return False
            
    except requests.Timeout:
        print("   Timeout - peut-être en cours...")
        return False
    except Exception as e:
        print(f"   Erreur: {e}")
        return False

def test_interface_web():
    print("\n=== TEST INTERFACE WEB ===")
    
    # Tester l'interface constraints-manager
    try:
        response = requests.get(f"{API_BASE}/constraints-manager")
        if response.ok:
            print("   ✓ Interface constraints-manager accessible")
            print(f"   URL: {API_BASE}/constraints-manager")
            return True
        else:
            print(f"   ❌ Interface non accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erreur interface: {e}")
        return False

def test_current_schedule():
    print("\n=== TEST EMPLOI DU TEMPS ACTUEL ===")
    
    # Vérifier l'emploi du temps actuel
    try:
        response = requests.get(f"{API_BASE}/api/schedule_entries?version=latest")
        if response.ok:
            data = response.json()
            entries = data.get('entries', [])
            
            if len(entries) == 0:
                print("   ⚠️ Aucun emploi du temps trouvé")
                return False
            
            # Analyser la distribution
            day_distribution = {}
            for entry in entries:
                day = entry.get('day', 0)
                if day not in day_distribution:
                    day_distribution[day] = 0
                day_distribution[day] += 1
            
            print(f"   📅 Total entrées: {len(entries)}")
            print("   📊 Distribution par jour:")
            day_names = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"]
            
            for day in range(7):
                count = day_distribution.get(day, 0)
                day_name = day_names[day] if day < len(day_names) else f"J{day}"
                if count > 0:
                    print(f"      {day_name}: {count} cours")
            
            # Vérifier le problème des trous
            days_with_content = len([d for d in day_distribution.values() if d > 0])
            
            if day_distribution.get(0, 0) == len(entries):
                print("   ❌ PROBLÈME CONFIRMÉ: Tous les cours sont sur le dimanche!")
                print("   💡 Solution: Utiliser l'interface web pour ajouter des contraintes")
                return False
            elif days_with_content >= 3:
                print(f"   ✅ Distribution correcte sur {days_with_content} jours")
                return True
            else:
                print(f"   ⚠️ Distribution partielle sur {days_with_content} jours")
                return True
                
        else:
            print(f"   ❌ Erreur récupération: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False

def main():
    print("🔍 DIAGNOSTIC COMPLET DU SYSTÈME")
    print("=" * 50)
    
    # Tests
    web_ok = test_interface_web()
    schedule_ok = test_current_schedule()
    generation_ok = test_simple_generation()
    
    print("\n" + "=" * 50)
    print("📋 RÉSULTATS DU DIAGNOSTIC")
    print(f"   Interface web: {'✅ OK' if web_ok else '❌ ERREUR'}")
    print(f"   Emploi du temps: {'✅ OK' if schedule_ok else '❌ PROBLÈME'}")
    print(f"   Génération: {'✅ OK' if generation_ok else '❌ ERREUR'}")
    
    print("\n🎯 RECOMMANDATIONS:")
    
    if web_ok and not schedule_ok:
        print("   1. ✅ Utilisez l'interface web:")
        print(f"      http://localhost:8000/constraints-manager")
        print("   2. 🤖 Cliquez sur l'agent AI (bouton 🤖)")
        print("   3. 💬 Dites: 'Il faut distribuer les cours sur toute la semaine'")
        print("   4. ⏱️ Attendez la génération automatique")
        print("   5. 🔄 Actualisez pour voir le résultat")
    
    elif not web_ok:
        print("   1. 🔄 Redémarrer les services:")
        print("      docker-compose restart")
        print("   2. ⏱️ Attendre 30 secondes")
        print("   3. 🔁 Relancer ce script")
    
    elif generation_ok and schedule_ok:
        print("   1. 🎉 Le système fonctionne parfaitement!")
        print("   2. 🌐 Vous pouvez utiliser l'interface web")
        print("   3. 🤖 L'agent AI peut optimiser automatiquement")
    
    else:
        print("   1. 📊 Vérifiez les logs Docker:")
        print("      docker-compose logs -f solver")
        print("   2. 🔧 Contactez le support technique")

if __name__ == "__main__":
    main()
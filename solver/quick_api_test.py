#!/usr/bin/env python3
"""
Quick API Test - Tests rapides de tous les APIs avec analyse basique
"""
import requests
import json
import time

def analyze_schedule_basic(schedule_data):
    """Analyse basique d'un emploi du temps"""
    schedule = schedule_data.get('schedule', [])
    if not schedule:
        return {'error': 'Pas de données'}
    
    # Compter les entrées par classe
    class_hours = {}
    for entry in schedule:
        class_name = entry.get('class_name', 'Unknown')
        if class_name not in class_hours:
            class_hours[class_name] = 0
        class_hours[class_name] += 1
    
    # Analyser les conflits basiques (même classe, même slot)
    slots = {}
    conflicts = 0
    for entry in schedule:
        slot_key = (entry.get('day', 0), entry.get('slot_index', 0))
        class_name = entry.get('class_name', 'Unknown')
        
        if slot_key not in slots:
            slots[slot_key] = {}
        if class_name not in slots[slot_key]:
            slots[slot_key][class_name] = 0
        slots[slot_key][class_name] += 1
        
        if slots[slot_key][class_name] > 1:
            conflicts += 1
    
    # Analyser les trous basiques
    gaps = 0
    for class_name in class_hours.keys():
        class_schedule = {}
        for entry in schedule:
            if entry.get('class_name') == class_name:
                day = entry.get('day', 0)
                period = entry.get('slot_index', 0)
                if day not in class_schedule:
                    class_schedule[day] = []
                class_schedule[day].append(period)
        
        # Compter les trous par jour
        for day, periods in class_schedule.items():
            if len(periods) >= 2:
                periods.sort()
                for i in range(periods[0], periods[-1]):
                    if i not in periods:
                        gaps += 1
    
    return {
        'total_entries': len(schedule),
        'classes': len(class_hours),
        'conflicts': conflicts,
        'gaps': gaps,
        'hours_per_class': class_hours
    }

def test_api(endpoint, payload, timeout=45):
    """Test d'un seul API"""
    try:
        start_time = time.time()
        response = requests.post(
            f"http://localhost:8000{endpoint}",
            json=payload,
            timeout=timeout
        )
        call_time = time.time() - start_time
        
        if response.status_code != 200:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'time': call_time
            }
        
        data = response.json()
        if not data.get('success', True):
            return {
                'success': False,
                'error': data.get('message', 'API failed'),
                'time': call_time
            }
        
        analysis = analyze_schedule_basic(data)
        return {
            'success': True,
            'time': call_time,
            'analysis': analysis
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'time': timeout
        }

def main():
    """Test tous les APIs rapidement"""
    apis = [
        ('Parallel Sync V2 NEW', '/generate_schedule_parallel_sync_v2'),
        ('Parallel Sync', '/generate_schedule_parallel_sync'),
        ('Advanced CP-SAT', '/generate_schedule_advanced_cpsat'),
        ('Ultimate Scheduler', '/generate_schedule_ultimate'),
        ('Corrected Solver', '/generate_schedule_corrected'),
        ('Pedagogical V2', '/generate_schedule_pedagogical_v2'),
        ('Integrated Solver', '/generate_schedule_integrated'),
        ('Fixed Solver', '/generate_schedule_fixed')
    ]
    
    print("=== TEST RAPIDE DES APIs ===")
    print()
    
    results = []
    for name, endpoint in apis:
        print(f"Test {name}... ", end='', flush=True)
        
        result = test_api(endpoint, {'time_limit': 30}, 45)
        results.append((name, result))
        
        if result['success']:
            a = result['analysis']
            print(f"OK - {a['total_entries']} entrees, {a['conflicts']} conflits, {a['gaps']} trous ({result['time']:.1f}s)")
        else:
            print(f"ERREUR - {result['error']} ({result['time']:.1f}s)")
    
    print()
    print("=== RESULTATS ===")
    
    # Trier par nombre d'entrees (descending)
    successful = [(name, r) for name, r in results if r['success']]
    failed = [(name, r) for name, r in results if not r['success']]
    
    successful.sort(key=lambda x: x[1]['analysis']['total_entries'], reverse=True)
    
    print(f"\nAPIs FONCTIONNELS ({len(successful)}):")
    for i, (name, result) in enumerate(successful, 1):
        a = result['analysis']
        print(f"  {i}. {name}")
        print(f"     Entrees: {a['total_entries']}, Conflits: {a['conflicts']}, Trous: {a['gaps']}")
        print(f"     Classes: {a['classes']}, Temps: {result['time']:.1f}s")
    
    if failed:
        print(f"\nAPIs EN ECHEC ({len(failed)}):")
        for i, (name, result) in enumerate(failed, 1):
            print(f"  {i}. {name} - {result['error']}")
    
    # Meilleur API
    if successful:
        best_name, best_result = successful[0]
        print(f"\nMEILLEUR API: {best_name}")
        print(f"  {best_result['analysis']['total_entries']} entrees generees")
        print(f"  {best_result['analysis']['conflicts']} conflits detectes")
        print(f"  {best_result['analysis']['gaps']} trous detectes")

if __name__ == "__main__":
    main()
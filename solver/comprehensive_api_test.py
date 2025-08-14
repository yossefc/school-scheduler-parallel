#!/usr/bin/env python3
"""
comprehensive_api_test.py - Tests complets de tous les APIs avec analyse des contraintes
"""
import requests
import json
import time
from typing import Dict, List, Any
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScheduleAnalyzer:
    """Analyseur d'emploi du temps pour vérifier les contraintes"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        
    def analyze_schedule(self, schedule_data: Dict) -> Dict[str, Any]:
        """
        Analyse complète d'un emploi du temps
        
        Args:
            schedule_data: Données de l'emploi du temps
            
        Returns:
            Dict: Rapport d'analyse complet
        """
        logger.info("Analyse de l'emploi du temps...")
        
        schedule = schedule_data.get('schedule', [])
        if not schedule:
            return {'error': 'Aucun emploi du temps à analyser'}
        
        # Analyses principales
        conflicts_analysis = self._analyze_conflicts(schedule)
        gaps_analysis = self._analyze_gaps(schedule)
        parallel_analysis = self._analyze_parallel_sync(schedule)
        israeli_constraints = self._check_israeli_constraints(schedule)
        coverage_analysis = self._analyze_coverage(schedule)
        
        # Score global
        global_score = self._calculate_global_score(
            conflicts_analysis, gaps_analysis, parallel_analysis, 
            israeli_constraints, coverage_analysis
        )
        
        analysis_report = {
            'global_score': global_score,
            'conflicts': conflicts_analysis,
            'gaps': gaps_analysis,
            'parallel_sync': parallel_analysis,
            'israeli_constraints': israeli_constraints,
            'coverage': coverage_analysis,
            'summary': self._generate_summary(global_score, conflicts_analysis, gaps_analysis)
        }
        
        return analysis_report
    
    def _analyze_conflicts(self, schedule: List[Dict]) -> Dict:
        """Analyse des conflits (classe/professeur au même moment)"""
        logger.info("  Analyse des conflits...")
        
        class_conflicts = []
        teacher_conflicts = []
        
        # Grouper par slot
        slots = {}
        for entry in schedule:
            slot_key = (entry.get('day_of_week', entry.get('day', 0)), 
                       entry.get('period_number', entry.get('slot_index', 0)))
            
            if slot_key not in slots:
                slots[slot_key] = []
            slots[slot_key].append(entry)
        
        # Vérifier les conflits par slot
        for slot_key, entries in slots.items():
            # Conflits de classe
            classes_in_slot = {}
            for entry in entries:
                class_name = entry.get('class_name', 'Unknown')
                if class_name not in classes_in_slot:
                    classes_in_slot[class_name] = []
                classes_in_slot[class_name].append(entry)
            
            for class_name, class_entries in classes_in_slot.items():
                if len(class_entries) > 1:
                    class_conflicts.append({
                        'class': class_name,
                        'slot': slot_key,
                        'subjects': [e.get('subject', e.get('subject_name', 'Unknown')) for e in class_entries],
                        'count': len(class_entries)
                    })
            
            # Conflits de professeur
            teachers_in_slot = {}
            for entry in entries:
                teacher = entry.get('teacher_name', 'Unknown')
                if teacher not in teachers_in_slot:
                    teachers_in_slot[teacher] = []
                teachers_in_slot[teacher].append(entry)
            
            for teacher, teacher_entries in teachers_in_slot.items():
                if len(teacher_entries) > 1:
                    teacher_conflicts.append({
                        'teacher': teacher,
                        'slot': slot_key,
                        'classes': [e.get('class_name', 'Unknown') for e in teacher_entries],
                        'count': len(teacher_entries)
                    })
        
        return {
            'class_conflicts': class_conflicts,
            'teacher_conflicts': teacher_conflicts,
            'total_class_conflicts': len(class_conflicts),
            'total_teacher_conflicts': len(teacher_conflicts),
            'has_conflicts': len(class_conflicts) > 0 or len(teacher_conflicts) > 0
        }
    
    def _analyze_gaps(self, schedule: List[Dict]) -> Dict:
        """Analyse des trous dans l'emploi du temps"""
        logger.info("  Analyse des trous...")
        
        # Grouper par classe et jour
        class_schedules = {}
        for entry in schedule:
            class_name = entry.get('class_name', 'Unknown')
            day = entry.get('day_of_week', entry.get('day', 0))
            period = entry.get('period_number', entry.get('slot_index', 0))
            
            if class_name not in class_schedules:
                class_schedules[class_name] = {}
            if day not in class_schedules[class_name]:
                class_schedules[class_name][day] = []
            
            class_schedules[class_name][day].append(period)
        
        # Calculer les trous
        gaps_by_class = {}
        total_gaps = 0
        
        for class_name, days in class_schedules.items():
            gaps_by_class[class_name] = {}
            
            for day, periods in days.items():
                if len(periods) >= 2:
                    periods.sort()
                    day_gaps = []
                    
                    for i in range(periods[0], periods[-1]):
                        if i not in periods:
                            day_gaps.append(i)
                    
                    if day_gaps:
                        gaps_by_class[class_name][day] = day_gaps
                        total_gaps += len(day_gaps)
        
        # Supprimer les classes sans trous
        gaps_by_class = {k: v for k, v in gaps_by_class.items() if v}
        
        return {
            'gaps_by_class': gaps_by_class,
            'total_gaps': total_gaps,
            'classes_with_gaps': len(gaps_by_class),
            'has_gaps': total_gaps > 0
        }
    
    def _analyze_parallel_sync(self, schedule: List[Dict]) -> Dict:
        """Analyse de la synchronisation des cours parallèles"""
        logger.info("  Analyse synchronisation parallèle...")
        
        # Grouper les cours parallèles
        parallel_groups = {}
        for entry in schedule:
            if entry.get('is_parallel_group') or entry.get('kind') == 'parallel':
                subject = entry.get('subject', entry.get('subject_name', 'Unknown'))
                slot_key = (entry.get('day_of_week', entry.get('day', 0)), 
                           entry.get('period_number', entry.get('slot_index', 0)))
                
                if subject not in parallel_groups:
                    parallel_groups[subject] = {}
                if slot_key not in parallel_groups[subject]:
                    parallel_groups[subject][slot_key] = []
                
                parallel_groups[subject][slot_key].append(entry['class_name'])
        
        # Analyser la synchronisation
        sync_violations = []
        well_synced = 0
        total_parallel_subjects = len(parallel_groups)
        
        for subject, slots in parallel_groups.items():
            # Toutes les classes de ce sujet
            all_classes = set()
            for classes_in_slot in slots.values():
                all_classes.update(classes_in_slot)
            
            # Vérifier que chaque slot a toutes les classes
            subject_well_synced = True
            for slot_key, classes_in_slot in slots.items():
                if set(classes_in_slot) != all_classes:
                    subject_well_synced = False
                    sync_violations.append({
                        'subject': subject,
                        'slot': slot_key,
                        'expected_classes': list(all_classes),
                        'actual_classes': classes_in_slot,
                        'missing_classes': list(all_classes - set(classes_in_slot))
                    })
            
            if subject_well_synced:
                well_synced += 1
        
        sync_rate = (well_synced / max(total_parallel_subjects, 1)) * 100
        
        return {
            'parallel_subjects': list(parallel_groups.keys()),
            'total_parallel_subjects': total_parallel_subjects,
            'well_synced_subjects': well_synced,
            'sync_violations': sync_violations,
            'sync_rate_percent': round(sync_rate, 1),
            'is_fully_synced': len(sync_violations) == 0
        }
    
    def _check_israeli_constraints(self, schedule: List[Dict]) -> Dict:
        """Vérification des contraintes israéliennes"""
        logger.info("  Vérification contraintes israéliennes...")
        
        violations = []
        
        # Contrainte: Lundi court pour ז, ח, ט (pas après période 4)
        young_grades = ['ז', 'ח', 'ט']
        monday_late_violations = []
        
        for entry in schedule:
            day = entry.get('day_of_week', entry.get('day', 0))
            period = entry.get('period_number', entry.get('slot_index', 0))
            class_name = entry.get('class_name', 'Unknown')
            
            # Extraire le niveau de la classe
            if '-' in class_name:
                grade = class_name.split('-')[0]
            else:
                grade = class_name
            
            # Lundi (day=1) et période tardive (>4) pour jeunes classes
            if day == 1 and period > 4 and grade in young_grades:
                monday_late_violations.append({
                    'class': class_name,
                    'subject': entry.get('subject', entry.get('subject_name', 'Unknown')),
                    'period': period,
                    'violation': 'Lundi tard pour classe jeune'
                })
        
        # Contrainte: Pas de vendredi (day=5)
        friday_violations = []
        for entry in schedule:
            day = entry.get('day_of_week', entry.get('day', 0))
            if day == 5:  # Vendredi
                friday_violations.append({
                    'class': entry.get('class_name', 'Unknown'),
                    'subject': entry.get('subject', entry.get('subject_name', 'Unknown')),
                    'violation': 'Cours le vendredi'
                })
        
        total_violations = len(monday_late_violations) + len(friday_violations)
        
        return {
            'monday_late_violations': monday_late_violations,
            'friday_violations': friday_violations,
            'total_violations': total_violations,
            'respects_israeli_constraints': total_violations == 0
        }
    
    def _analyze_coverage(self, schedule: List[Dict]) -> Dict:
        """Analyse de la couverture (classes, matières, périodes)"""
        logger.info("  Analyse de couverture...")
        
        classes = set()
        subjects = set()
        teachers = set()
        periods = set()
        days = set()
        
        for entry in schedule:
            classes.add(entry.get('class_name', 'Unknown'))
            subjects.add(entry.get('subject', entry.get('subject_name', 'Unknown')))
            teachers.add(entry.get('teacher_name', 'Unknown'))
            periods.add(entry.get('period_number', entry.get('slot_index', 0)))
            days.add(entry.get('day_of_week', entry.get('day', 0)))
        
        # Distribution par classe
        hours_per_class = {}
        for entry in schedule:
            class_name = entry.get('class_name', 'Unknown')
            if class_name not in hours_per_class:
                hours_per_class[class_name] = 0
            hours_per_class[class_name] += 1
        
        return {
            'total_schedule_entries': len(schedule),
            'unique_classes': len(classes),
            'unique_subjects': len(subjects),
            'unique_teachers': len(teachers),
            'periods_used': sorted(list(periods)),
            'days_used': sorted(list(days)),
            'hours_per_class': hours_per_class,
            'avg_hours_per_class': sum(hours_per_class.values()) / max(len(hours_per_class), 1)
        }
    
    def _calculate_global_score(self, conflicts, gaps, parallel, israeli, coverage) -> int:
        """Calcule un score global de qualité (0-100)"""
        score = 100
        
        # Pénalités
        score -= conflicts['total_class_conflicts'] * 20  # -20 par conflit de classe
        score -= conflicts['total_teacher_conflicts'] * 10  # -10 par conflit de prof
        score -= min(gaps['total_gaps'], 20)  # -1 par trou (max -20)
        score -= (100 - parallel['sync_rate_percent']) * 0.3  # Pénalité sync parallèle
        score -= israeli['total_violations'] * 15  # -15 par violation israélienne
        
        # Bonus
        if not conflicts['has_conflicts']:
            score += 10
        if not gaps['has_gaps']:
            score += 10
        if parallel['is_fully_synced']:
            score += 5
        if israeli['respects_israeli_constraints']:
            score += 5
        
        return max(0, min(100, round(score)))
    
    def _generate_summary(self, score, conflicts, gaps) -> str:
        """Génère un résumé de l'analyse"""
        if score >= 90:
            quality = "Excellente"
        elif score >= 75:
            quality = "Bonne"
        elif score >= 60:
            quality = "Acceptable"
        else:
            quality = "Problématique"
        
        issues = []
        if conflicts['has_conflicts']:
            issues.append(f"{conflicts['total_class_conflicts'] + conflicts['total_teacher_conflicts']} conflits")
        if gaps['has_gaps']:
            issues.append(f"{gaps['total_gaps']} trous")
        
        if issues:
            return f"Qualité {quality} (score: {score}/100) - Issues: {', '.join(issues)}"
        else:
            return f"Qualité {quality} (score: {score}/100) - Aucun problème majeur"

class ComprehensiveAPITester:
    """Testeur complet de tous les APIs"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.analyzer = ScheduleAnalyzer()
        self.results = {}
        
        # Liste des APIs à tester
        self.apis_to_test = [
            {
                'name': 'Advanced CP-SAT',
                'endpoint': '/generate_schedule_advanced_cpsat',
                'payload': {'time_limit': 30},
                'timeout': 45
            },
            {
                'name': 'Ultimate Scheduler',
                'endpoint': '/generate_schedule_ultimate',
                'payload': {'time_limit': 30, 'algorithms': ['corrected']},
                'timeout': 45
            },
            {
                'name': 'Pedagogical V2',
                'endpoint': '/generate_schedule_pedagogical_v2',
                'payload': {'time_limit': 30},
                'timeout': 45
            },
            {
                'name': 'Corrected Solver',
                'endpoint': '/generate_schedule_corrected',
                'payload': {'time_limit': 30},
                'timeout': 45
            },
            {
                'name': 'Integrated Solver',
                'endpoint': '/generate_schedule_integrated',
                'payload': {'time_limit': 30},
                'timeout': 45
            },
            {
                'name': 'Fixed Solver',
                'endpoint': '/generate_schedule_fixed',
                'payload': {'time_limit': 30},
                'timeout': 45
            }
        ]
    
    def run_comprehensive_tests(self):
        """Lance tous les tests"""
        logger.info("DÉBUT DES TESTS COMPLETS DES APIs")
        logger.info("=" * 60)
        
        for api_config in self.apis_to_test:
            logger.info(f"\nTest de l'API: {api_config['name']}")
            logger.info("-" * 40)
            
            try:
                result = self._test_single_api(api_config)
                self.results[api_config['name']] = result
                
                if result['success']:
                    logger.info(f"OK {api_config['name']}: Score {result['analysis']['global_score']}/100")
                else:
                    logger.info(f"ERREUR {api_config['name']}: {result['error']}")
                    
            except Exception as e:
                logger.error(f"Erreur critique pour {api_config['name']}: {e}")
                self.results[api_config['name']] = {
                    'success': False,
                    'error': f"Erreur critique: {str(e)}",
                    'analysis': None
                }
        
        # Générer le rapport final
        self._generate_final_report()
    
    def _test_single_api(self, api_config: Dict) -> Dict:
        """Test d'un seul API"""
        start_time = time.time()
        
        try:
            # Appel API
            response = requests.post(
                f"{self.api_base}{api_config['endpoint']}",
                json=api_config['payload'],
                timeout=api_config['timeout']
            )
            
            call_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'call_time': call_time,
                    'analysis': None
                }
            
            data = response.json()
            
            if not data.get('success', True):
                return {
                    'success': False,
                    'error': data.get('message', 'API returned success=false'),
                    'call_time': call_time,
                    'analysis': None
                }
            
            # Analyser l'emploi du temps
            analysis = self.analyzer.analyze_schedule(data)
            
            return {
                'success': True,
                'call_time': call_time,
                'raw_data': data,
                'analysis': analysis,
                'error': None
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f"Timeout après {api_config['timeout']}s",
                'call_time': api_config['timeout'],
                'analysis': None
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': "Impossible de se connecter au serveur",
                'call_time': time.time() - start_time,
                'analysis': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Erreur: {str(e)}",
                'call_time': time.time() - start_time,
                'analysis': None
            }
    
    def _generate_final_report(self):
        """Génère le rapport final"""
        logger.info("\n" + "=" * 60)
        logger.info("RAPPORT FINAL DES TESTS")
        logger.info("=" * 60)
        
        successful_tests = []
        failed_tests = []
        
        for api_name, result in self.results.items():
            if result['success']:
                successful_tests.append({
                    'name': api_name,
                    'score': result['analysis']['global_score'],
                    'time': result['call_time'],
                    'summary': result['analysis']['summary']
                })
            else:
                failed_tests.append({
                    'name': api_name,
                    'error': result['error'],
                    'time': result.get('call_time', 0)
                })
        
        # Trier par score
        successful_tests.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"\nAPIS FONCTIONNELS ({len(successful_tests)}):")
        for i, test in enumerate(successful_tests, 1):
            logger.info(f"  {i}. {test['name']} - Score: {test['score']}/100 ({test['time']:.1f}s)")
            logger.info(f"     {test['summary']}")
        
        if failed_tests:
            logger.info(f"\nAPIS EN ÉCHEC ({len(failed_tests)}):")
            for i, test in enumerate(failed_tests, 1):
                logger.info(f"  {i}. {test['name']} - {test['error']} ({test['time']:.1f}s)")
        
        # Meilleur API
        if successful_tests:
            best_api = successful_tests[0]
            logger.info(f"\nMEILLEUR API: {best_api['name']}")
            logger.info(f"   Score: {best_api['score']}/100")
            logger.info(f"   Temps: {best_api['time']:.1f}s")
            logger.info(f"   Résumé: {best_api['summary']}")
        
        logger.info("\n" + "=" * 60)

def main():
    """Fonction principale"""
    print("TESTS COMPLETS DES APIs D'EMPLOI DU TEMPS")
    print("=" * 60)
    
    tester = ComprehensiveAPITester()
    tester.run_comprehensive_tests()
    
    print("\nTests terminés!")

if __name__ == "__main__":
    main()
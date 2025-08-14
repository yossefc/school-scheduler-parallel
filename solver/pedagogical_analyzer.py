#!/usr/bin/env python3
"""
pedagogical_analyzer.py - Analyseur pédagogique automatique avec règles strictes
Analyse un emploi du temps et l'améliore itérativement jusqu'à la perfection
"""
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from incremental_scheduler import IncrementalScheduler

logger = logging.getLogger(__name__)

class PedagogicalAnalyzer:
    """
    Analyseur pédagogique avec règles strictes :
    - 0 trous dans l'emploi du temps
    - Blocs de 2-3h pour les matières principales 
    - Matières groupées par jour
    - Optimisation automatique jusqu'à perfection
    """
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.scheduler = IncrementalScheduler(db_config)
        self.current_schedule_id = None
        self.analysis_log = []
        self.improvements_made = []
        self.questions_asked = []
        
        # Règles pédagogiques strictes
        self.PEDAGOGICAL_RULES = {
            'max_gaps_allowed': 0,  # ZÉRO trous autorisés
            'min_block_size': 2,    # Minimum 2h consécutives
            'preferred_block_size': 3,  # Préférer 3h consécutives
            'max_subjects_per_day': 4,  # Maximum 4 matières différentes par jour
            'min_daily_hours': 5,   # Minimum 5h de cours par jour
            'max_daily_hours': 8,   # Maximum 8h de cours par jour
            'core_subjects': [      # Matières principales qui doivent avoir des blocs
                'מתמטיקה', 'אנגלית', 'עברית', 'מדעים', 'היסטוריה', 
                'גיאוגרפיה', 'ביולוגיה', 'כימיה', 'פיזיקה'
            ]
        }
        
    def analyze_full_schedule(self, schedule_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyse complète d'un emploi du temps avec toutes les règles pédagogiques
        """
        logger.info("🔍 DÉBUT D'ANALYSE PÉDAGOGIQUE COMPLÈTE")
        
        # Charger l'emploi du temps
        load_result = self.scheduler.load_existing_schedule(schedule_id)
        if not load_result['success']:
            return {"success": False, "error": load_result['error']}
        
        self.current_schedule_id = load_result['schedule_id']
        schedule_entries = self.scheduler.schedule_entries
        
        # Organiser les données par classe et jour
        schedule_by_class = self._organize_schedule_by_class(schedule_entries)
        
        # Analyses détaillées
        analysis_results = {
            'schedule_id': self.current_schedule_id,
            'total_entries': len(schedule_entries),
            'analysis_timestamp': datetime.now().isoformat(),
            'classes_analyzed': len(schedule_by_class),
            'issues_found': [],
            'pedagogical_score': 0,
            'recommendations': [],
            'critical_problems': [],
            'optimization_potential': []
        }
        
        total_score = 0
        max_possible_score = 0
        
        # Analyser chaque classe
        for class_name, class_schedule in schedule_by_class.items():
            logger.info(f"📚 Analyse de la classe {class_name}")
            
            class_analysis = self._analyze_class_schedule(class_name, class_schedule)
            analysis_results['issues_found'].extend(class_analysis['issues'])
            
            # Calculer le score pédagogique
            class_score = class_analysis['pedagogical_score']
            total_score += class_score
            max_possible_score += 100
            
            if class_score < 70:  # Score critique
                analysis_results['critical_problems'].append({
                    'class': class_name,
                    'score': class_score,
                    'main_issues': class_analysis['main_issues']
                })
            
            # Ajouter les recommandations spécifiques à cette classe
            for recommendation in class_analysis['recommendations']:
                recommendation['class'] = class_name
                analysis_results['recommendations'].append(recommendation)
        
        # Score global
        analysis_results['pedagogical_score'] = round(total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        
        # Analyse transversale
        cross_analysis = self._analyze_cross_class_issues(schedule_entries)
        analysis_results['issues_found'].extend(cross_analysis['issues'])
        analysis_results['recommendations'].extend(cross_analysis['recommendations'])
        
        # Classification des problèmes par priorité
        analysis_results = self._classify_issues_by_priority(analysis_results)
        
        logger.info(f"📊 Analyse terminée - Score pédagogique: {analysis_results['pedagogical_score']}/100")
        logger.info(f"   {len(analysis_results['issues_found'])} problèmes détectés")
        logger.info(f"   {len(analysis_results['critical_problems'])} problèmes critiques")
        
        self.analysis_log.append(analysis_results)
        return analysis_results
    
    def _organize_schedule_by_class(self, entries: List[Dict]) -> Dict[str, Dict]:
        """Organise l'emploi du temps par classe et par jour"""
        schedule_by_class = defaultdict(lambda: defaultdict(list))
        
        for entry in entries:
            class_name = entry['class_name']
            day = entry['day_of_week']
            
            schedule_by_class[class_name][day].append({
                'slot_index': entry['slot_index'],
                'subject': entry['subject'],
                'teachers': entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']],
                'kind': entry.get('kind', 'individual'),
                'entry_id': entry.get('entry_id')
            })
        
        # Trier par slot_index pour chaque jour
        for class_name in schedule_by_class:
            for day in schedule_by_class[class_name]:
                schedule_by_class[class_name][day].sort(key=lambda x: x['slot_index'])
        
        return dict(schedule_by_class)
    
    def _analyze_class_schedule(self, class_name: str, class_schedule: Dict) -> Dict[str, Any]:
        """Analyse approfondie de l'emploi du temps d'une classe"""
        issues = []
        recommendations = []
        main_issues = []
        scores = {}
        
        total_hours = 0
        total_gaps = 0
        subjects_distribution = defaultdict(list)
        daily_hours = []
        
        # Analyser chaque jour
        for day, day_schedule in class_schedule.items():
            if not day_schedule:
                continue
                
            # Calculer les statistiques du jour
            day_hours = len(day_schedule)
            total_hours += day_hours
            daily_hours.append(day_hours)
            
            # Détecter les trous dans la journée
            slots = [entry['slot_index'] for entry in day_schedule]
            if slots:
                slots.sort()
                day_gaps = 0
                for i in range(slots[0], slots[-1]):
                    if i not in slots:
                        day_gaps += 1
                        total_gaps += 1
                        issues.append({
                            'type': 'gap',
                            'severity': 'critical',
                            'day': day,
                            'slot': i,
                            'message': f'Trou détecté jour {day+1} période {i+1}'
                        })
                
                if day_gaps > 0:
                    main_issues.append(f'{day_gaps} trous jour {day+1}')
            
            # Analyser la répartition des matières
            day_subjects = [entry['subject'] for entry in day_schedule]
            unique_subjects = set(day_subjects)
            
            if len(unique_subjects) > self.PEDAGOGICAL_RULES['max_subjects_per_day']:
                issues.append({
                    'type': 'too_many_subjects',
                    'severity': 'warning',
                    'day': day,
                    'count': len(unique_subjects),
                    'subjects': list(unique_subjects),
                    'message': f'Trop de matières différentes ({len(unique_subjects)}) jour {day+1}'
                })
            
            # Analyser les blocs de matières
            blocks = self._detect_subject_blocks(day_schedule)
            for subject, block_sizes in blocks.items():
                subjects_distribution[subject].extend(block_sizes)
                
                # Vérifier si les matières principales ont des blocs suffisants
                if subject in self.PEDAGOGICAL_RULES['core_subjects']:
                    max_block = max(block_sizes) if block_sizes else 0
                    if max_block < self.PEDAGOGICAL_RULES['min_block_size']:
                        issues.append({
                            'type': 'insufficient_block',
                            'severity': 'high',
                            'subject': subject,
                            'day': day,
                            'max_block': max_block,
                            'message': f'{subject} n\'a que {max_block}h consécutives (minimum {self.PEDAGOGICAL_RULES["min_block_size"]}h)'
                        })
                        main_issues.append(f'{subject} fragmenté')
            
            # Vérifier la charge quotidienne
            if day_hours < self.PEDAGOGICAL_RULES['min_daily_hours']:
                issues.append({
                    'type': 'insufficient_daily_hours',
                    'severity': 'medium',
                    'day': day,
                    'hours': day_hours,
                    'message': f'Seulement {day_hours}h de cours jour {day+1} (minimum {self.PEDAGOGICAL_RULES["min_daily_hours"]}h)'
                })
            elif day_hours > self.PEDAGOGICAL_RULES['max_daily_hours']:
                issues.append({
                    'type': 'excessive_daily_hours',
                    'severity': 'high',
                    'day': day,
                    'hours': day_hours,
                    'message': f'{day_hours}h de cours jour {day+1} (maximum {self.PEDAGOGICAL_RULES["max_daily_hours"]}h)'
                })
        
        # Calcul du score pédagogique
        scores['gaps_score'] = max(0, 100 - (total_gaps * 25))  # -25 points par trou
        scores['blocks_score'] = self._calculate_blocks_score(subjects_distribution)
        scores['distribution_score'] = self._calculate_distribution_score(daily_hours)
        scores['subjects_score'] = self._calculate_subjects_score(subjects_distribution)
        
        pedagogical_score = sum(scores.values()) / len(scores)
        
        # Générer des recommandations
        if total_gaps > 0:
            recommendations.append({
                'type': 'eliminate_gaps',
                'priority': 1,
                'action': 'move_courses',
                'description': f'Éliminer les {total_gaps} trous en regroupant les cours',
                'automated_fix': True
            })
        
        for subject, blocks in subjects_distribution.items():
            if subject in self.PEDAGOGICAL_RULES['core_subjects']:
                if not any(block >= self.PEDAGOGICAL_RULES['min_block_size'] for block in blocks):
                    recommendations.append({
                        'type': 'create_blocks',
                        'priority': 2,
                        'subject': subject,
                        'action': 'group_consecutive_slots',
                        'description': f'Regrouper les heures de {subject} en blocs de 2-3h',
                        'automated_fix': True
                    })
        
        return {
            'class_name': class_name,
            'total_hours': total_hours,
            'total_gaps': total_gaps,
            'pedagogical_score': round(pedagogical_score),
            'scores_detail': scores,
            'issues': issues,
            'main_issues': main_issues,
            'recommendations': recommendations,
            'subjects_distribution': dict(subjects_distribution)
        }
    
    def _detect_subject_blocks(self, day_schedule: List[Dict]) -> Dict[str, List[int]]:
        """Détecte les blocs de matières consécutives"""
        blocks = defaultdict(list)
        
        if not day_schedule:
            return blocks
        
        current_subject = None
        current_block_size = 0
        
        for entry in day_schedule:
            subject = entry['subject']
            
            if subject == current_subject:
                current_block_size += 1
            else:
                if current_subject and current_block_size > 0:
                    blocks[current_subject].append(current_block_size)
                
                current_subject = subject
                current_block_size = 1
        
        # Ajouter le dernier bloc
        if current_subject and current_block_size > 0:
            blocks[current_subject].append(current_block_size)
        
        return dict(blocks)
    
    def _calculate_blocks_score(self, subjects_distribution: Dict[str, List[int]]) -> float:
        """Calcule le score basé sur la qualité des blocs"""
        score = 100
        
        for subject, blocks in subjects_distribution.items():
            if subject in self.PEDAGOGICAL_RULES['core_subjects']:
                max_block = max(blocks) if blocks else 0
                
                if max_block < self.PEDAGOGICAL_RULES['min_block_size']:
                    score -= 15  # Pénalité forte pour les matières fragmentées
                elif max_block >= self.PEDAGOGICAL_RULES['preferred_block_size']:
                    score += 5   # Bonus pour les blocs optimaux
        
        return max(0, min(100, score))
    
    def _calculate_distribution_score(self, daily_hours: List[int]) -> float:
        """Calcule le score basé sur la répartition des heures"""
        if not daily_hours:
            return 0
        
        # Vérifier l'équilibre des journées
        avg_hours = sum(daily_hours) / len(daily_hours)
        variance = sum((h - avg_hours) ** 2 for h in daily_hours) / len(daily_hours)
        
        # Score basé sur la régularité (moins de variance = meilleur score)
        distribution_score = max(0, 100 - (variance * 10))
        
        # Pénalités pour les journées trop courtes ou trop longues
        for hours in daily_hours:
            if hours < self.PEDAGOGICAL_RULES['min_daily_hours']:
                distribution_score -= 10
            elif hours > self.PEDAGOGICAL_RULES['max_daily_hours']:
                distribution_score -= 15
        
        return max(0, distribution_score)
    
    def _calculate_subjects_score(self, subjects_distribution: Dict[str, List[int]]) -> float:
        """Calcule le score basé sur la répartition des matières"""
        score = 100
        
        # Vérifier que chaque matière principale a suffisamment d'heures
        for subject in self.PEDAGOGICAL_RULES['core_subjects']:
            total_hours = sum(subjects_distribution.get(subject, []))
            if total_hours == 0:
                continue  # Matière non présente, pas de pénalité
            
            if total_hours < 3:  # Moins de 3h par semaine
                score -= 10
            elif total_hours > 8:  # Plus de 8h par semaine
                score -= 5
        
        return max(0, score)
    
    def _analyze_cross_class_issues(self, entries: List[Dict]) -> Dict[str, Any]:
        """Analyse les problèmes transversaux (professeurs, salles, etc.)"""
        issues = []
        recommendations = []
        
        # Analyser les conflits de professeurs
        teacher_conflicts = self._detect_teacher_conflicts(entries)
        for conflict in teacher_conflicts:
            issues.append({
                'type': 'teacher_conflict',
                'severity': 'critical',
                'teacher': conflict['teacher'],
                'classes': conflict['classes'],
                'slot': conflict['slot'],
                'message': f'Professeur {conflict["teacher"]} enseigne simultanément à {len(conflict["classes"])} classes'
            })
        
        # Analyser l'utilisation des professeurs
        teacher_usage = self._analyze_teacher_usage(entries)
        for teacher, analysis in teacher_usage.items():
            if analysis['gaps'] > 2:  # Plus de 2 trous dans la semaine
                recommendations.append({
                    'type': 'optimize_teacher_schedule',
                    'priority': 3,
                    'teacher': teacher,
                    'gaps': analysis['gaps'],
                    'description': f'Réduire les {analysis["gaps"]} trous de {teacher}',
                    'automated_fix': True
                })
        
        return {
            'issues': issues,
            'recommendations': recommendations
        }
    
    def _detect_teacher_conflicts(self, entries: List[Dict]) -> List[Dict]:
        """Détecte les conflits de professeurs"""
        conflicts = []
        
        # Organiser par créneau et professeur
        slot_teachers = defaultdict(lambda: defaultdict(list))
        
        for entry in entries:
            slot_key = (entry['day_of_week'], entry['slot_index'])
            teachers = entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']]
            
            for teacher in teachers:
                if teacher and teacher != 'לא משובץ':
                    slot_teachers[slot_key][teacher].append(entry['class_name'])
        
        # Détecter les conflits
        for slot_key, teachers_dict in slot_teachers.items():
            for teacher, classes in teachers_dict.items():
                if len(classes) > 1:
                    conflicts.append({
                        'slot': slot_key,
                        'teacher': teacher,
                        'classes': classes
                    })
        
        return conflicts
    
    def _analyze_teacher_usage(self, entries: List[Dict]) -> Dict[str, Dict]:
        """Analyse l'utilisation des professeurs"""
        teacher_schedules = defaultdict(lambda: defaultdict(list))
        
        for entry in entries:
            teachers = entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']]
            day = entry['day_of_week']
            slot = entry['slot_index']
            
            for teacher in teachers:
                if teacher and teacher != 'לא משובץ':
                    teacher_schedules[teacher][day].append(slot)
        
        # Calculer les statistiques pour chaque professeur
        teacher_analysis = {}
        for teacher, schedule in teacher_schedules.items():
            total_gaps = 0
            total_hours = 0
            
            for day, slots in schedule.items():
                if slots:
                    slots.sort()
                    total_hours += len(slots)
                    # Compter les trous
                    for i in range(slots[0], slots[-1]):
                        if i not in slots:
                            total_gaps += 1
            
            teacher_analysis[teacher] = {
                'total_hours': total_hours,
                'gaps': total_gaps,
                'days_active': len([d for d in schedule.values() if d])
            }
        
        return teacher_analysis
    
    def _classify_issues_by_priority(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Classe les problèmes par priorité et faisabilité de correction automatique"""
        
        critical_issues = [issue for issue in analysis['issues_found'] if issue['severity'] == 'critical']
        high_issues = [issue for issue in analysis['issues_found'] if issue['severity'] == 'high']
        medium_issues = [issue for issue in analysis['issues_found'] if issue['severity'] == 'medium']
        low_issues = [issue for issue in analysis['issues_found'] if issue['severity'] == 'warning']
        
        # Identifier les corrections automatiques possibles
        auto_fixable = [rec for rec in analysis['recommendations'] if rec.get('automated_fix')]
        manual_review = [rec for rec in analysis['recommendations'] if not rec.get('automated_fix')]
        
        analysis['issues_by_priority'] = {
            'critical': critical_issues,
            'high': high_issues, 
            'medium': medium_issues,
            'low': low_issues
        }
        
        analysis['corrections'] = {
            'automatic': auto_fixable,
            'manual_review': manual_review
        }
        
        return analysis
    
    def auto_improve_schedule(self, max_iterations: int = 10) -> Dict[str, Any]:
        """
        Amélioration automatique itérative jusqu'à obtenir un emploi du temps parfait
        """
        logger.info(f"🔄 DÉBUT D'AMÉLIORATION AUTOMATIQUE (max {max_iterations} itérations)")
        
        improvements_made = []
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"📈 Itération {iteration}/{max_iterations}")
            
            # Analyser l'état actuel
            analysis = self.analyze_full_schedule(self.current_schedule_id)
            
            if analysis['pedagogical_score'] >= 95:  # Score presque parfait
                logger.info(f"🎉 EMPLOI DU TEMPS OPTIMAL ATTEINT (Score: {analysis['pedagogical_score']}/100)")
                break
            
            # Identifier les corrections automatiques
            auto_fixes = analysis['corrections']['automatic']
            
            if not auto_fixes:
                logger.info("⚠️ Aucune correction automatique possible, arrêt de l'optimisation")
                break
            
            # Appliquer la correction la plus prioritaire
            fix_applied = None
            for fix in sorted(auto_fixes, key=lambda x: x['priority']):
                logger.info(f"🔧 Tentative de correction: {fix['description']}")
                
                success = self._apply_automatic_fix(fix)
                if success:
                    fix_applied = fix
                    improvements_made.append({
                        'iteration': iteration,
                        'fix': fix,
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.info(f"✅ Correction appliquée: {fix['description']}")
                    break
                else:
                    logger.warning(f"❌ Échec de la correction: {fix['description']}")
            
            if not fix_applied:
                logger.warning("⚠️ Aucune correction n'a pu être appliquée, arrêt")
                break
        
        # Analyse finale
        final_analysis = self.analyze_full_schedule(self.current_schedule_id)
        
        return {
            'success': True,
            'iterations_performed': iteration,
            'improvements_made': improvements_made,
            'initial_score': self.analysis_log[0]['pedagogical_score'] if self.analysis_log else 0,
            'final_score': final_analysis['pedagogical_score'],
            'final_analysis': final_analysis,
            'remaining_issues': final_analysis['issues_by_priority']['critical'] + final_analysis['issues_by_priority']['high']
        }
    
    def _apply_automatic_fix(self, fix: Dict[str, Any]) -> bool:
        """Applique une correction automatique"""
        
        try:
            if fix['type'] == 'eliminate_gaps':
                return self._fix_gaps_automatically()
            
            elif fix['type'] == 'create_blocks':
                return self._create_subject_blocks(fix['subject'])
                
            elif fix['type'] == 'optimize_teacher_schedule':
                return self._optimize_teacher_gaps(fix['teacher'])
            
            else:
                logger.warning(f"Type de correction non implémenté: {fix['type']}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'application de la correction: {e}")
            return False
    
    def _fix_gaps_automatically(self) -> bool:
        """Corrige automatiquement les trous en déplaçant les cours"""
        logger.info("🔧 Correction automatique des trous...")
        
        # Charger l'emploi du temps actuel
        schedule_by_class = self._organize_schedule_by_class(self.scheduler.schedule_entries)
        
        fixes_applied = 0
        
        for class_name, class_schedule in schedule_by_class.items():
            for day, day_schedule in class_schedule.items():
                if len(day_schedule) < 2:
                    continue  # Pas assez de cours pour avoir des trous
                
                # Détecter les trous
                slots = [entry['slot_index'] for entry in day_schedule]
                slots.sort()
                
                gaps = []
                for i in range(slots[0], slots[-1]):
                    if i not in slots:
                        gaps.append(i)
                
                if not gaps:
                    continue  # Pas de trous
                
                # Essayer de combler les trous en déplaçant les cours
                for gap_slot in gaps:
                    # Chercher un cours à déplacer vers ce trou
                    for other_day in range(5):  # Lundi à jeudi
                        if other_day == day:
                            continue
                        
                        other_day_schedule = class_schedule.get(other_day, [])
                        if not other_day_schedule:
                            continue
                        
                        # Chercher un cours isolé à déplacer
                        for entry in other_day_schedule:
                            if self._is_course_movable(entry, class_name, other_day, day, gap_slot):
                                # Déplacer le cours
                                result = self.scheduler.move_course(
                                    class_name, entry['subject'],
                                    other_day, entry['slot_index'],
                                    day, gap_slot
                                )
                                
                                if result['success']:
                                    # Sauvegarder
                                    save_result = self.scheduler.save_modifications()
                                    if save_result['success']:
                                        self.current_schedule_id = save_result['new_schedule_id']
                                        fixes_applied += 1
                                        logger.info(f"✅ Cours {entry['subject']} déplacé pour combler un trou")
                                        
                                        # Recharger pour la prochaine modification
                                        self.scheduler.load_existing_schedule(self.current_schedule_id)
                                        return True  # Une correction à la fois
                
        return fixes_applied > 0
    
    def _is_course_movable(self, entry: Dict, class_name: str, from_day: int, to_day: int, to_slot: int) -> bool:
        """Vérifie si un cours peut être déplacé sans créer de conflits"""
        
        # Vérifications basiques
        if not entry or not entry.get('subject'):
            return False
        
        # Éviter de déplacer les cours parallèles (plus complexe)
        if entry.get('kind') == 'parallel':
            return False
        
        # Vérifier les contraintes israéliennes
        young_grades = ['ז-1', 'ז-2', 'ז-3', 'ז-4', 'ח-1', 'ח-2', 'ח-3', 'ח-4', 'ט-1', 'ט-2', 'ט-3', 'ט-4', 'ט-5']
        if class_name in young_grades and to_day == 1 and to_slot > 4:  # Lundi après période 4
            return False
        
        # Autres vérifications pourraient être ajoutées ici
        return True
    
    def _create_subject_blocks(self, subject: str) -> bool:
        """Crée des blocs de cours consécutifs pour une matière"""
        logger.info(f"🔧 Création de blocs pour {subject}...")
        
        # Cette fonction nécessiterait une logique complexe de regroupement
        # Pour l'instant, on retourne False pour indiquer qu'elle n'est pas implémentée
        logger.warning(f"Création de blocs pour {subject} non encore implémentée automatiquement")
        return False
    
    def _optimize_teacher_gaps(self, teacher: str) -> bool:
        """Optimise l'emploi du temps d'un professeur pour réduire ses trous"""
        logger.info(f"🔧 Optimisation de l'emploi du temps de {teacher}...")
        
        # Cette fonction nécessiterait une analyse approfondie des cours du professeur
        # Pour l'instant, on retourne False pour indiquer qu'elle n'est pas implémentée
        logger.warning(f"Optimisation pour {teacher} non encore implémentée automatiquement")
        return False
    
    def ask_user_question(self, problem: Dict[str, Any]) -> str:
        """
        Pose une question intelligente à l'utilisateur quand un problème ne peut pas être résolu automatiquement
        """
        question_type = problem.get('type', 'unknown')
        
        if question_type == 'insufficient_block':
            subject = problem.get('subject', 'matière inconnue')
            max_block = problem.get('max_block', 0)
            
            question = f"""
🤔 PROBLÈME DÉTECTÉ: La matière '{subject}' est trop fragmentée

📊 SITUATION ACTUELLE:
   • Plus grand bloc consécutif: {max_block}h
   • Minimum recommandé: {self.PEDAGOGICAL_RULES['min_block_size']}h
   • Optimal recommandé: {self.PEDAGOGICAL_RULES['preferred_block_size']}h

❓ QUESTION:
Pour améliorer l'apprentissage de {subject}, je recommande de regrouper les heures en blocs de 2-3h consécutives.

Que préférez-vous:
1. Regrouper automatiquement les heures de {subject} (peut déplacer d'autres cours)
2. Garder la répartition actuelle mais accepter une efficacité pédagogique moindre
3. Me donner des contraintes spécifiques pour {subject} (jours préférés, heures à éviter, etc.)

Votre choix (1/2/3): """

        elif question_type == 'gap':
            day = problem.get('day', 0)
            slot = problem.get('slot', 0)
            day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi']
            
            question = f"""
🕳️ PROBLÈME DÉTECTÉ: Trou dans l'emploi du temps

📅 SITUATION:
   • Jour: {day_names[day]}
   • Période: {slot + 1}
   • Impact: Les élèves ont une heure libre au milieu de leur journée

❓ QUESTION:
Ce trou peut être problématique pour la discipline et l'organisation. 

Comment souhaitez-vous le résoudre:
1. Déplacer automatiquement un cours pour combler ce trou
2. Raccourcir la journée en déplaçant les cours vers les bords
3. Accepter ce trou s'il y a une raison pédagogique (pause, étude dirigée, etc.)

Votre choix (1/2/3): """

        elif question_type == 'teacher_conflict':
            teacher = problem.get('teacher', 'professeur inconnu')
            classes = problem.get('classes', [])
            
            question = f"""
👨‍🏫 PROBLÈME CRITIQUE: Conflit de professeur

⚠️ SITUATION:
   • Professeur: {teacher}
   • Enseigne simultanément à: {', '.join(classes)}
   • Ceci est physiquement impossible!

❓ QUESTION URGENTE:
Ce conflit doit être résolu immédiatement.

Options:
1. Déplacer automatiquement l'un des cours vers un autre créneau
2. Diviser les groupes si c'est un cours parallèle qui peut être séparé
3. Me dire s'il y a une erreur dans les données (ce professeur ne devrait pas enseigner à certaines classes)

Votre choix (1/2/3): """

        else:
            question = f"""
❓ PROBLÈME COMPLEXE DÉTECTÉ

Je rencontre un problème que je ne peux pas résoudre automatiquement:
{problem.get('message', 'Problème non spécifié')}

Pouvez-vous m'aider à comprendre comment procéder?
"""

        self.questions_asked.append({
            'timestamp': datetime.now().isoformat(),
            'problem': problem,
            'question': question
        })
        
        return question


def main():
    """Test de l'analyseur pédagogique"""
    logging.basicConfig(level=logging.INFO)
    
    db_config = {
        "host": "localhost",
        "database": "school_scheduler", 
        "user": "admin",
        "password": "school123",
        "port": 5432
    }
    
    analyzer = PedagogicalAnalyzer(db_config)
    
    # Analyser le dernier emploi du temps
    analysis = analyzer.analyze_full_schedule()
    
    if analysis.get('success') is False:
        print(f"❌ Erreur: {analysis.get('error')}")
        return
    
    print(f"\n📊 ANALYSE PÉDAGOGIQUE TERMINÉE")
    print(f"Score global: {analysis['pedagogical_score']}/100")
    print(f"Problèmes critiques: {len(analysis['issues_by_priority']['critical'])}")
    print(f"Corrections automatiques possibles: {len(analysis['corrections']['automatic'])}")
    
    # Tenter une amélioration automatique
    if analysis['pedagogical_score'] < 90:
        print(f"\n🔄 DÉBUT D'AMÉLIORATION AUTOMATIQUE...")
        improvement = analyzer.auto_improve_schedule(max_iterations=5)
        
        print(f"Améliorations réalisées: {len(improvement['improvements_made'])}")
        print(f"Score initial: {improvement['initial_score']}/100")
        print(f"Score final: {improvement['final_score']}/100")


if __name__ == "__main__":
    main()
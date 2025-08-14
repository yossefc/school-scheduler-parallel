"""
conflict_resolver.py - Système de détection et résolution automatique des conflits
Analyse la qualité des emplois du temps et propose des corrections automatiques
"""
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)

class IssueType(Enum):
    """Types de problèmes détectés dans un emploi du temps"""
    TROU = "gap"                    # Trou dans l'emploi du temps
    COURS_ISOLE = "isolated_hour"   # Heure isolée (non groupée)
    AMPLITUDE_EXCESSIVE = "excessive_amplitude"  # Journée trop longue
    SURCHARGE = "overload"          # Trop de cours consécutifs
    GAP_HEBDO = "weekly_gap"        # Trop de jours sans une matière
    MATIERE_DIFFICILE_TARD = "difficult_subject_late"  # Matière difficile en fin de journée

class SeverityLevel(Enum):
    """Niveaux de gravité des problèmes"""
    CRITICAL = 1    # Doit être corrigé
    HIGH = 2        # Fortement recommandé
    MEDIUM = 3      # Amélioration souhaitée
    LOW = 4         # Préférence mineure

@dataclass
class ScheduleIssue:
    """Représente un problème détecté dans l'emploi du temps"""
    type: IssueType
    severity: SeverityLevel
    entity: str  # Professeur, classe, etc.
    details: Dict
    suggestion: str
    auto_fixable: bool = False

class ConflictResolver:
    """Résolveur de conflits pour emplois du temps"""
    
    def __init__(self):
        # Configuration des seuils de détection
        self.thresholds = {
            "max_teacher_amplitude": 6,     # Max 6h d'amplitude par jour
            "max_consecutive_hours": 3,     # Max 3h consécutives
            "max_weekly_gap": 3,           # Max 3 jours sans une matière
            "late_period_start": 5,        # Période considérée comme "tard"
        }
        
        # Matières considérées comme difficiles
        self.difficult_subjects = {
            "מתמטיקה", "פיזיקה", "כימיה", "אנגלית מתקדמת"
        }
        
        # Templates d'explication en hébreu et français
        self.explanation_templates = {
            IssueType.TROU: {
                "fr": "Le professeur {teacher} a un trou de {gap_size}h le {day} entre {start_time} et {end_time}",
                "he": "למורה {teacher} יש חור של {gap_size} שעות ביום {day} בין {start_time} ל-{end_time}"
            },
            IssueType.COURS_ISOLE: {
                "fr": "La classe {class_name} a une heure isolée de {subject} le {day} à {time}",
                "he": "לכיתה {class_name} יש שעה בודדה של {subject} ביום {day} בשעה {time}"
            },
            IssueType.AMPLITUDE_EXCESSIVE: {
                "fr": "Le professeur {teacher} a une amplitude de {amplitude}h le {day} (recommandé: max {max_amplitude}h)",
                "he": "למורה {teacher} יש משרה של {amplitude} שעות ביום {day} (מומלץ: מקסימום {max_amplitude} שעות)"
            }
        }
    
    def analyze_schedule_quality(self, solution: Dict) -> Dict:
        """
        Analyse complète de la qualité d'un emploi du temps
        
        Args:
            solution: Solution générée par l'optimiseur
            
        Returns:
            Rapport d'analyse avec problèmes détectés et suggestions
        """
        logger.info("=== ANALYSE DE QUALITÉ DE L'EMPLOI DU TEMPS ===")
        
        analysis = {
            "global_score": 0,
            "issues": [],
            "stats": {},
            "fixes": {
                "automatic": [],
                "manual": []
            },
            "recommendations": []
        }
        
        # 1. Analyser les trous dans les emplois du temps
        gaps = self._detect_teacher_gaps(solution)
        analysis["issues"].extend(gaps)
        
        # 2. Détecter les cours isolés
        isolated = self._detect_isolated_hours(solution)
        analysis["issues"].extend(isolated)
        
        # 3. Analyser l'amplitude journalière
        amplitude_issues = self._detect_excessive_amplitude(solution)
        analysis["issues"].extend(amplitude_issues)
        
        # 4. Détecter la surcharge (trop de cours consécutifs)
        overload_issues = self._detect_overload(solution)
        analysis["issues"].extend(overload_issues)
        
        # 5. Analyser l'équilibre hebdomadaire
        weekly_issues = self._detect_weekly_gaps(solution)
        analysis["issues"].extend(weekly_issues)
        
        # 6. Vérifier le placement des matières difficiles
        late_difficult = self._detect_late_difficult_subjects(solution)
        analysis["issues"].extend(late_difficult)
        
        # 7. Calculer le score global
        analysis["global_score"] = self._calculate_quality_score(analysis["issues"])
        
        # 8. Générer les suggestions de correction
        analysis["fixes"] = self._generate_fixes(analysis["issues"])
        
        # 9. Compiler les statistiques
        analysis["stats"] = self._compile_statistics(solution, analysis["issues"])
        
        logger.info(f"✓ Analyse terminée - Score: {analysis['global_score']}/100")
        logger.info(f"  - {len(analysis['issues'])} problèmes détectés")
        logger.info(f"  - {len(analysis['fixes']['automatic'])} corrections automatiques possibles")
        
        return analysis
    
    def _detect_teacher_gaps(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les trous dans les emplois du temps des professeurs"""
        issues = []
        
        for teacher_name, teacher_schedule in solution.get("by_teacher", {}).items():
            # Regrouper par jour
            by_day = {}
            for entry in teacher_schedule:
                day = entry["day"]
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(entry["period"])
            
            # Analyser chaque jour
            for day, periods in by_day.items():
                if len(periods) <= 1:
                    continue
                
                periods_sorted = sorted(periods)
                gaps = []
                
                for i in range(len(periods_sorted) - 1):
                    gap_size = periods_sorted[i+1] - periods_sorted[i] - 1
                    if gap_size > 0:
                        gaps.append({
                            "start_period": periods_sorted[i],
                            "end_period": periods_sorted[i+1],
                            "size": gap_size
                        })
                
                # Créer des issues pour chaque trou
                for gap in gaps:
                    issues.append(ScheduleIssue(
                        type=IssueType.TROU,
                        severity=SeverityLevel.CRITICAL,
                        entity=teacher_name,
                        details={
                            "teacher": teacher_name,
                            "day": day,
                            "gap_start": gap["start_period"],
                            "gap_end": gap["end_period"],
                            "gap_size": gap["size"]
                        },
                        suggestion=f"Regrouper les cours de {teacher_name} le jour {day}",
                        auto_fixable=True
                    ))
        
        return issues
    
    def _detect_isolated_hours(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les heures de cours isolées (non groupées en blocs)"""
        issues = []
        
        for class_name, class_schedule in solution.get("by_class", {}).items():
            # Regrouper par matière
            by_subject = {}
            for entry in class_schedule:
                subject = entry["subject"]
                if subject not in by_subject:
                    by_subject[subject] = []
                by_subject[subject].append((entry["day"], entry["period"]))
            
            # Analyser chaque matière
            for subject, time_slots in by_subject.items():
                if len(time_slots) < 2:
                    continue
                
                # Trier par jour et période
                sorted_slots = sorted(time_slots)
                isolated_slots = []
                
                i = 0
                while i < len(sorted_slots):
                    current_day, current_period = sorted_slots[i]
                    
                    # Vérifier si fait partie d'un bloc
                    is_part_of_block = False
                    
                    # Vérifier avec le slot suivant
                    if i < len(sorted_slots) - 1:
                        next_day, next_period = sorted_slots[i + 1]
                        if current_day == next_day and next_period == current_period + 1:
                            is_part_of_block = True
                    
                    # Vérifier avec le slot précédent
                    if i > 0:
                        prev_day, prev_period = sorted_slots[i - 1]
                        if current_day == prev_day and current_period == prev_period + 1:
                            is_part_of_block = True
                    
                    if not is_part_of_block:
                        isolated_slots.append((current_day, current_period))
                    
                    i += 1
                
                # Créer des issues pour les heures isolées
                for day, period in isolated_slots:
                    issues.append(ScheduleIssue(
                        type=IssueType.COURS_ISOLE,
                        severity=SeverityLevel.HIGH,
                        entity=f"{class_name}_{subject}",
                        details={
                            "class": class_name,
                            "subject": subject,
                            "day": day,
                            "period": period
                        },
                        suggestion=f"Regrouper {subject} en blocs de 2h pour {class_name}",
                        auto_fixable=True
                    ))
        
        return issues
    
    def _detect_excessive_amplitude(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les amplitudes journalières excessives pour les professeurs"""
        issues = []
        
        for teacher_name, teacher_schedule in solution.get("by_teacher", {}).items():
            by_day = {}
            for entry in teacher_schedule:
                day = entry["day"]
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(entry["period"])
            
            for day, periods in by_day.items():
                if len(periods) <= 1:
                    continue
                
                min_period = min(periods)
                max_period = max(periods)
                amplitude = max_period - min_period + 1
                
                if amplitude > self.thresholds["max_teacher_amplitude"]:
                    issues.append(ScheduleIssue(
                        type=IssueType.AMPLITUDE_EXCESSIVE,
                        severity=SeverityLevel.MEDIUM,
                        entity=teacher_name,
                        details={
                            "teacher": teacher_name,
                            "day": day,
                            "amplitude": amplitude,
                            "first_period": min_period,
                            "last_period": max_period,
                            "max_recommended": self.thresholds["max_teacher_amplitude"]
                        },
                        suggestion=f"Réduire l'amplitude de {teacher_name} le jour {day}",
                        auto_fixable=False
                    ))
        
        return issues
    
    def _detect_overload(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les surcharges (trop d'heures consécutives)"""
        issues = []
        
        # Analyser pour les classes
        for class_name, class_schedule in solution.get("by_class", {}).items():
            by_day = {}
            for entry in class_schedule:
                day = entry["day"]
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(entry["period"])
            
            for day, periods in by_day.items():
                periods_sorted = sorted(periods)
                consecutive_count = 1
                max_consecutive = 1
                
                for i in range(1, len(periods_sorted)):
                    if periods_sorted[i] == periods_sorted[i-1] + 1:
                        consecutive_count += 1
                        max_consecutive = max(max_consecutive, consecutive_count)
                    else:
                        consecutive_count = 1
                
                if max_consecutive > self.thresholds["max_consecutive_hours"]:
                    issues.append(ScheduleIssue(
                        type=IssueType.SURCHARGE,
                        severity=SeverityLevel.MEDIUM,
                        entity=class_name,
                        details={
                            "class": class_name,
                            "day": day,
                            "consecutive_hours": max_consecutive,
                            "max_recommended": self.thresholds["max_consecutive_hours"]
                        },
                        suggestion=f"Réduire les heures consécutives pour {class_name} le jour {day}",
                        auto_fixable=False
                    ))
        
        return issues
    
    def _detect_weekly_gaps(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les gaps hebdomadaires (trop de jours sans une matière)"""
        issues = []
        
        for class_name, class_schedule in solution.get("by_class", {}).items():
            by_subject = {}
            for entry in class_schedule:
                subject = entry["subject"]
                day = entry["day"]
                if subject not in by_subject:
                    by_subject[subject] = set()
                by_subject[subject].add(day)
            
            for subject, days in by_subject.items():
                days_list = sorted(days)
                
                # Chercher des gaps de plus de X jours
                for i in range(len(days_list) - 1):
                    gap = days_list[i+1] - days_list[i] - 1
                    if gap >= self.thresholds["max_weekly_gap"]:
                        issues.append(ScheduleIssue(
                            type=IssueType.GAP_HEBDO,
                            severity=SeverityLevel.LOW,
                            entity=f"{class_name}_{subject}",
                            details={
                                "class": class_name,
                                "subject": subject,
                                "from_day": days_list[i],
                                "to_day": days_list[i+1],
                                "gap_days": gap
                            },
                            suggestion=f"Mieux répartir {subject} sur la semaine pour {class_name}",
                            auto_fixable=False
                        ))
        
        return issues
    
    def _detect_late_difficult_subjects(self, solution: Dict) -> List[ScheduleIssue]:
        """Détecte les matières difficiles placées tard dans la journée"""
        issues = []
        
        for class_name, class_schedule in solution.get("by_class", {}).items():
            for entry in class_schedule:
                subject = entry["subject"]
                period = entry["period"]
                day = entry["day"]
                
                # Vérifier si c'est une matière difficile placée tard
                if (subject in self.difficult_subjects and 
                    period >= self.thresholds["late_period_start"]):
                    
                    issues.append(ScheduleIssue(
                        type=IssueType.MATIERE_DIFFICILE_TARD,
                        severity=SeverityLevel.MEDIUM,
                        entity=f"{class_name}_{subject}",
                        details={
                            "class": class_name,
                            "subject": subject,
                            "day": day,
                            "period": period,
                            "recommended_before": self.thresholds["late_period_start"]
                        },
                        suggestion=f"Déplacer {subject} plus tôt dans la journée pour {class_name}",
                        auto_fixable=True
                    ))
        
        return issues
    
    def _calculate_quality_score(self, issues: List[ScheduleIssue]) -> int:
        """Calcule un score de qualité global (0-100)"""
        base_score = 100
        
        for issue in issues:
            if issue.severity == SeverityLevel.CRITICAL:
                base_score -= 15
            elif issue.severity == SeverityLevel.HIGH:
                base_score -= 10
            elif issue.severity == SeverityLevel.MEDIUM:
                base_score -= 5
            elif issue.severity == SeverityLevel.LOW:
                base_score -= 2
        
        return max(0, base_score)
    
    def _generate_fixes(self, issues: List[ScheduleIssue]) -> Dict:
        """Génère des suggestions de correction automatique et manuelle"""
        fixes = {
            "automatic": [],
            "manual": []
        }
        
        for issue in issues:
            fix_suggestion = {
                "issue_id": f"{issue.type.value}_{issue.entity}",
                "type": issue.type.value,
                "severity": issue.severity.value,
                "description": issue.suggestion,
                "details": issue.details,
                "estimated_impact": self._estimate_fix_impact(issue)
            }
            
            if issue.auto_fixable:
                fix_suggestion["action"] = self._generate_auto_fix_action(issue)
                fixes["automatic"].append(fix_suggestion)
            else:
                fixes["manual"].append(fix_suggestion)
        
        return fixes
    
    def _estimate_fix_impact(self, issue: ScheduleIssue) -> Dict:
        """Estime l'impact d'une correction"""
        impact = {
            "difficulty": "medium",
            "time_required": "moderate",
            "side_effects": "minimal"
        }
        
        if issue.type == IssueType.TROU:
            impact.update({
                "difficulty": "high",
                "time_required": "significant",
                "side_effects": "possible"
            })
        elif issue.type == IssueType.COURS_ISOLE:
            impact.update({
                "difficulty": "medium",
                "time_required": "moderate",
                "side_effects": "minimal"
            })
        
        return impact
    
    def _generate_auto_fix_action(self, issue: ScheduleIssue) -> Dict:
        """Génère une action de correction automatique"""
        if issue.type == IssueType.TROU:
            return {
                "type": "compact_teacher_schedule",
                "target": issue.details["teacher"],
                "day": issue.details["day"],
                "method": "move_courses_together"
            }
        
        elif issue.type == IssueType.COURS_ISOLE:
            return {
                "type": "merge_to_block",
                "target_class": issue.details["class"],
                "target_subject": issue.details["subject"],
                "method": "find_adjacent_slot"
            }
        
        elif issue.type == IssueType.MATIERE_DIFFICILE_TARD:
            return {
                "type": "move_to_morning",
                "target_class": issue.details["class"],
                "target_subject": issue.details["subject"],
                "target_period": f"<{self.thresholds['late_period_start']}"
            }
        
        return {"type": "manual_intervention_required"}
    
    def _compile_statistics(self, solution: Dict, issues: List[ScheduleIssue]) -> Dict:
        """Compile des statistiques détaillées"""
        stats = {
            "total_issues": len(issues),
            "by_severity": {
                "critical": sum(1 for i in issues if i.severity == SeverityLevel.CRITICAL),
                "high": sum(1 for i in issues if i.severity == SeverityLevel.HIGH),
                "medium": sum(1 for i in issues if i.severity == SeverityLevel.MEDIUM),
                "low": sum(1 for i in issues if i.severity == SeverityLevel.LOW)
            },
            "by_type": {},
            "teachers_affected": len(set(i.entity for i in issues if "teacher" in i.details)),
            "classes_affected": len(set(i.entity for i in issues if "class" in i.details))
        }
        
        # Statistiques par type
        for issue_type in IssueType:
            count = sum(1 for i in issues if i.type == issue_type)
            if count > 0:
                stats["by_type"][issue_type.value] = count
        
        return stats
    
    def explain_issue(self, issue: ScheduleIssue, language: str = "fr") -> str:
        """Génère une explication pédagogique d'un problème"""
        template = self.explanation_templates.get(issue.type, {}).get(language)
        
        if template:
            try:
                return template.format(**issue.details)
            except KeyError as e:
                logger.warning(f"Clé manquante dans template: {e}")
        
        # Fallback en cas de problème avec le template
        return f"Problème détecté: {issue.type.value} pour {issue.entity}"
    
    def auto_fix(self, schedule: Dict, issues: List[ScheduleIssue]) -> Dict:
        """
        Applique les corrections automatiques possibles
        
        Note: Cette méthode génère des recommandations de modifications
        L'application réelle nécessite une réexécution de l'optimiseur
        """
        logger.info("=== GÉNÉRATION DES CORRECTIONS AUTOMATIQUES ===")
        
        auto_fixes = {
            "applied_fixes": [],
            "failed_fixes": [],
            "recommendations": []
        }
        
        for issue in issues:
            if issue.auto_fixable:
                fix_result = self._attempt_auto_fix(issue)
                if fix_result["success"]:
                    auto_fixes["applied_fixes"].append(fix_result)
                else:
                    auto_fixes["failed_fixes"].append(fix_result)
            else:
                auto_fixes["recommendations"].append({
                    "issue": issue.type.value,
                    "entity": issue.entity,
                    "suggestion": issue.suggestion,
                    "manual_action_required": True
                })
        
        logger.info(f"✓ {len(auto_fixes['applied_fixes'])} corrections automatiques générées")
        logger.info(f"⚠ {len(auto_fixes['failed_fixes'])} corrections échouées")
        logger.info(f"📋 {len(auto_fixes['recommendations'])} actions manuelles recommandées")
        
        return auto_fixes
    
    def _attempt_auto_fix(self, issue: ScheduleIssue) -> Dict:
        """Tente d'appliquer une correction automatique"""
        # Pour l'instant, on génère juste des recommandations
        # L'implémentation complète nécessiterait une intégration avec l'optimiseur
        
        return {
            "success": True,
            "issue_type": issue.type.value,
            "entity": issue.entity,
            "action_taken": "constraint_added",
            "description": f"Ajout de contrainte pour corriger {issue.type.value}",
            "requires_re_optimization": True
        }
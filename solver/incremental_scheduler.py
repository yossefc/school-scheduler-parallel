#!/usr/bin/env python3
"""
incremental_scheduler.py - Système de modification incrémentale d'emploi du temps
Permet de modifier un emploi du temps existant au lieu de toujours générer from scratch
"""
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class IncrementalScheduler:
    """
    Système de modification incrémentale d'emploi du temps
    - Charge un emploi du temps existant
    - Applique des modifications ponctuelles
    - Résout seulement les conflits nécessaires
    """
    
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.current_schedule = None
        self.schedule_id = None
        self.schedule_entries = []
        self.modifications_log = []
    
    def load_existing_schedule(self, schedule_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Charge un emploi du temps existant
        Si schedule_id n'est pas fourni, charge le plus récent
        """
        logger.info("Chargement d'un emploi du temps existant...")
        
        conn = psycopg2.connect(**self.db_config)
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if schedule_id is None:
                # Charger l'emploi du temps le plus récent
                cursor.execute("""
                    SELECT schedule_id, academic_year, term, status, created_at, metadata
                    FROM schedules 
                    WHERE status = 'active'
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                schedule_info = cursor.fetchone()
                
                if not schedule_info:
                    logger.warning("Aucun emploi du temps existant trouvé")
                    return {"success": False, "error": "Aucun emploi du temps existant"}
                
                schedule_id = schedule_info['schedule_id']
            else:
                # Charger l'emploi du temps spécifique
                cursor.execute("""
                    SELECT schedule_id, academic_year, term, status, created_at, metadata
                    FROM schedules 
                    WHERE schedule_id = %s
                """, (schedule_id,))
                schedule_info = cursor.fetchone()
                
                if not schedule_info:
                    logger.error(f"Emploi du temps {schedule_id} non trouvé")
                    return {"success": False, "error": f"Emploi du temps {schedule_id} non trouvé"}
            
            # Charger toutes les entrées de l'emploi du temps
            cursor.execute("""
                SELECT entry_id, class_name, day_of_week, slot_index, subject, 
                       teacher_names, kind, slot_id
                FROM schedule_entries 
                WHERE schedule_id = %s
                ORDER BY day_of_week, slot_index, class_name
            """, (schedule_id,))
            
            entries = cursor.fetchall()
            
            self.schedule_id = schedule_id
            self.schedule_entries = [dict(entry) for entry in entries]
            self.current_schedule = {
                'schedule_id': schedule_id,
                'info': dict(schedule_info),
                'entries': self.schedule_entries
            }
            
            logger.info(f"✅ Emploi du temps {schedule_id} chargé avec {len(entries)} entrées")
            logger.info(f"   Créé le: {schedule_info['created_at']}")
            logger.info(f"   Année: {schedule_info['academic_year']}")
            logger.info(f"   Statut: {schedule_info['status']}")
            
            return {
                "success": True,
                "schedule_id": schedule_id,
                "entries_count": len(entries),
                "schedule_info": dict(schedule_info),
                "entries": self.schedule_entries
            }
            
        except Exception as e:
            logger.error(f"Erreur chargement emploi du temps: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
    
    def move_course(self, class_name: str, subject: str, old_day: int, old_slot: int, 
                   new_day: int, new_slot: int) -> Dict[str, Any]:
        """
        Déplace un cours d'un créneau à un autre
        """
        if not self.current_schedule:
            return {"success": False, "error": "Aucun emploi du temps chargé"}
        
        logger.info(f"Déplacement de {subject} pour {class_name}")
        logger.info(f"  De: Jour {old_day} période {old_slot}")
        logger.info(f"  Vers: Jour {new_day} période {new_slot}")
        
        # Trouver l'entrée à déplacer
        course_to_move = None
        for entry in self.schedule_entries:
            if (entry['class_name'] == class_name and 
                entry['subject'] == subject and
                entry['day_of_week'] == old_day and 
                entry['slot_index'] == old_slot):
                course_to_move = entry
                break
        
        if not course_to_move:
            logger.error("Cours à déplacer non trouvé")
            return {"success": False, "error": "Cours non trouvé"}
        
        # Vérifier les conflits au nouveau créneau
        conflicts = self._check_conflicts_at_slot(new_day, new_slot, class_name, course_to_move['teacher_names'])
        
        if conflicts:
            logger.warning(f"Conflits détectés: {conflicts}")
            return {
                "success": False, 
                "error": "Conflit détecté",
                "conflicts": conflicts,
                "suggestions": self._suggest_alternative_slots(class_name, subject, new_day)
            }
        
        # Appliquer le déplacement
        old_slot_id = course_to_move['slot_id']
        new_slot_id = self._get_slot_id(new_day, new_slot)
        
        course_to_move['day_of_week'] = new_day
        course_to_move['slot_index'] = new_slot
        course_to_move['slot_id'] = new_slot_id
        
        # Enregistrer la modification
        modification = {
            'type': 'move_course',
            'timestamp': datetime.now().isoformat(),
            'class_name': class_name,
            'subject': subject,
            'old_position': {'day': old_day, 'slot': old_slot},
            'new_position': {'day': new_day, 'slot': new_slot},
            'old_slot_id': old_slot_id,
            'new_slot_id': new_slot_id
        }
        self.modifications_log.append(modification)
        
        logger.info("✅ Cours déplacé avec succès")
        return {
            "success": True,
            "modification": modification,
            "updated_entry": course_to_move
        }
    
    def change_teacher(self, class_name: str, subject: str, day: int, slot: int, 
                      new_teachers: List[str]) -> Dict[str, Any]:
        """
        Change le professeur d'un cours
        """
        if not self.current_schedule:
            return {"success": False, "error": "Aucun emploi du temps chargé"}
        
        logger.info(f"Changement de professeur pour {subject} - {class_name}")
        logger.info(f"  Créneau: Jour {day} période {slot}")
        logger.info(f"  Nouveaux professeurs: {new_teachers}")
        
        # Trouver l'entrée à modifier
        course_to_modify = None
        for entry in self.schedule_entries:
            if (entry['class_name'] == class_name and 
                entry['subject'] == subject and
                entry['day_of_week'] == day and 
                entry['slot_index'] == slot):
                course_to_modify = entry
                break
        
        if not course_to_modify:
            return {"success": False, "error": "Cours non trouvé"}
        
        # Vérifier la disponibilité des nouveaux professeurs
        teacher_conflicts = self._check_teacher_availability(new_teachers, day, slot)
        if teacher_conflicts:
            return {
                "success": False,
                "error": "Conflit de professeur",
                "conflicts": teacher_conflicts
            }
        
        # Appliquer le changement
        old_teachers = course_to_modify['teacher_names'].copy() if isinstance(course_to_modify['teacher_names'], list) else [course_to_modify['teacher_names']]
        course_to_modify['teacher_names'] = new_teachers
        
        # Enregistrer la modification
        modification = {
            'type': 'change_teacher',
            'timestamp': datetime.now().isoformat(),
            'class_name': class_name,
            'subject': subject,
            'position': {'day': day, 'slot': slot},
            'old_teachers': old_teachers,
            'new_teachers': new_teachers
        }
        self.modifications_log.append(modification)
        
        logger.info("✅ Professeur changé avec succès")
        return {
            "success": True,
            "modification": modification,
            "updated_entry": course_to_modify
        }
    
    def add_course(self, class_name: str, subject: str, teachers: List[str], 
                  day: int, slot: int, hours: int = 1) -> Dict[str, Any]:
        """
        Ajoute un nouveau cours à l'emploi du temps
        """
        if not self.current_schedule:
            return {"success": False, "error": "Aucun emploi du temps chargé"}
        
        logger.info(f"Ajout d'un nouveau cours: {subject} pour {class_name}")
        logger.info(f"  Professeurs: {teachers}")
        logger.info(f"  Créneau: Jour {day} période {slot}")
        
        # Vérifier les conflits
        conflicts = self._check_conflicts_at_slot(day, slot, class_name, teachers)
        if conflicts:
            return {
                "success": False,
                "error": "Conflit détecté",
                "conflicts": conflicts
            }
        
        # Créer la nouvelle entrée
        slot_id = self._get_slot_id(day, slot)
        new_entry = {
            'entry_id': None,  # Sera assigné lors de la sauvegarde
            'class_name': class_name,
            'day_of_week': day,
            'slot_index': slot,
            'subject': subject,
            'teacher_names': teachers,
            'kind': 'individual',
            'slot_id': slot_id
        }
        
        self.schedule_entries.append(new_entry)
        
        # Enregistrer la modification
        modification = {
            'type': 'add_course',
            'timestamp': datetime.now().isoformat(),
            'class_name': class_name,
            'subject': subject,
            'teachers': teachers,
            'position': {'day': day, 'slot': slot},
            'hours': hours
        }
        self.modifications_log.append(modification)
        
        logger.info("✅ Cours ajouté avec succès")
        return {
            "success": True,
            "modification": modification,
            "new_entry": new_entry
        }
    
    def remove_course(self, class_name: str, subject: str, day: int, slot: int) -> Dict[str, Any]:
        """
        Supprime un cours de l'emploi du temps
        """
        if not self.current_schedule:
            return {"success": False, "error": "Aucun emploi du temps chargé"}
        
        logger.info(f"Suppression de {subject} pour {class_name}")
        logger.info(f"  Créneau: Jour {day} période {slot}")
        
        # Trouver l'entrée à supprimer
        course_to_remove = None
        for i, entry in enumerate(self.schedule_entries):
            if (entry['class_name'] == class_name and 
                entry['subject'] == subject and
                entry['day_of_week'] == day and 
                entry['slot_index'] == slot):
                course_to_remove = entry
                break
        
        if not course_to_remove:
            return {"success": False, "error": "Cours non trouvé"}
        
        # Supprimer l'entrée
        self.schedule_entries.remove(course_to_remove)
        
        # Enregistrer la modification
        modification = {
            'type': 'remove_course',
            'timestamp': datetime.now().isoformat(),
            'class_name': class_name,
            'subject': subject,
            'position': {'day': day, 'slot': slot},
            'removed_entry': course_to_remove
        }
        self.modifications_log.append(modification)
        
        logger.info("✅ Cours supprimé avec succès")
        return {
            "success": True,
            "modification": modification,
            "removed_entry": course_to_remove
        }
    
    def save_modifications(self) -> Dict[str, Any]:
        """
        Sauvegarde l'emploi du temps modifié en base de données
        """
        if not self.current_schedule or not self.modifications_log:
            return {"success": False, "error": "Aucune modification à sauvegarder"}
        
        logger.info("Sauvegarde des modifications...")
        
        conn = psycopg2.connect(**self.db_config)
        try:
            cursor = conn.cursor()
            
            # Créer une nouvelle version de l'emploi du temps
            cursor.execute("""
                INSERT INTO schedules (academic_year, term, status, created_at, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING schedule_id
            """, (
                self.current_schedule['info']['academic_year'],
                self.current_schedule['info']['term'],
                'active',
                datetime.now(),
                json.dumps({
                    'generation_method': 'incremental_modification',
                    'base_schedule_id': self.schedule_id,
                    'modifications': self.modifications_log,
                    'modification_count': len(self.modifications_log)
                })
            ))
            
            new_schedule_id = cursor.fetchone()[0]
            
            # Marquer l'ancien emploi du temps comme archivé
            cursor.execute("""
                UPDATE schedules 
                SET status = 'archived' 
                WHERE schedule_id = %s
            """, (self.schedule_id,))
            
            # Sauvegarder toutes les entrées modifiées
            for entry in self.schedule_entries:
                cursor.execute("""
                    INSERT INTO schedule_entries 
                    (schedule_id, class_name, day_of_week, slot_index, subject, teacher_names, kind, slot_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_schedule_id,
                    entry['class_name'],
                    entry['day_of_week'],
                    entry['slot_index'],
                    entry['subject'],
                    entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']],
                    entry['kind'],
                    entry['slot_id']
                ))
            
            conn.commit()
            
            logger.info(f"✅ Emploi du temps modifié sauvegardé: ID {new_schedule_id}")
            logger.info(f"   {len(self.modifications_log)} modifications appliquées")
            logger.info(f"   {len(self.schedule_entries)} entrées sauvegardées")
            
            return {
                "success": True,
                "new_schedule_id": new_schedule_id,
                "old_schedule_id": self.schedule_id,
                "modifications_applied": len(self.modifications_log),
                "entries_count": len(self.schedule_entries)
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur sauvegarde: {e}")
            return {"success": False, "error": str(e)}
        finally:
            conn.close()
    
    def get_schedule_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé de l'emploi du temps actuel
        """
        if not self.current_schedule:
            return {"error": "Aucun emploi du temps chargé"}
        
        # Statistiques par classe
        class_stats = {}
        for entry in self.schedule_entries:
            class_name = entry['class_name']
            if class_name not in class_stats:
                class_stats[class_name] = {'courses': 0, 'subjects': set()}
            class_stats[class_name]['courses'] += 1
            class_stats[class_name]['subjects'].add(entry['subject'])
        
        # Convertir les sets en listes pour la sérialisation JSON
        for class_name in class_stats:
            class_stats[class_name]['subjects'] = list(class_stats[class_name]['subjects'])
            class_stats[class_name]['subjects_count'] = len(class_stats[class_name]['subjects'])
        
        return {
            "schedule_id": self.schedule_id,
            "total_entries": len(self.schedule_entries),
            "classes_count": len(class_stats),
            "modifications_count": len(self.modifications_log),
            "class_statistics": class_stats,
            "last_modified": self.modifications_log[-1]['timestamp'] if self.modifications_log else None
        }
    
    def _check_conflicts_at_slot(self, day: int, slot: int, class_name: str, teachers: List[str]) -> List[Dict]:
        """Vérifie les conflits à un créneau donné"""
        conflicts = []
        
        for entry in self.schedule_entries:
            if entry['day_of_week'] == day and entry['slot_index'] == slot:
                # Conflit de classe
                if entry['class_name'] == class_name:
                    conflicts.append({
                        'type': 'class_conflict',
                        'message': f"Classe {class_name} a déjà {entry['subject']} à ce créneau"
                    })
                
                # Conflit de professeur
                existing_teachers = entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']]
                for teacher in teachers:
                    if teacher in existing_teachers:
                        conflicts.append({
                            'type': 'teacher_conflict',
                            'message': f"Professeur {teacher} enseigne déjà à {entry['class_name']} à ce créneau"
                        })
        
        return conflicts
    
    def _check_teacher_availability(self, teachers: List[str], day: int, slot: int) -> List[Dict]:
        """Vérifie la disponibilité des professeurs"""
        conflicts = []
        
        for entry in self.schedule_entries:
            if entry['day_of_week'] == day and entry['slot_index'] == slot:
                existing_teachers = entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']]
                for teacher in teachers:
                    if teacher in existing_teachers:
                        conflicts.append({
                            'teacher': teacher,
                            'conflict_with': entry['class_name'],
                            'subject': entry['subject']
                        })
        
        return conflicts
    
    def _suggest_alternative_slots(self, class_name: str, subject: str, preferred_day: int) -> List[Dict]:
        """Suggère des créneaux alternatifs"""
        suggestions = []
        
        # Chercher des créneaux libres le même jour
        for slot in range(12):  # 12 périodes par jour
            if not self._check_conflicts_at_slot(preferred_day, slot, class_name, []):
                suggestions.append({
                    'day': preferred_day,
                    'slot': slot,
                    'reason': 'Même jour, créneau libre'
                })
        
        # Si pas de place le même jour, chercher les autres jours
        if len(suggestions) < 3:
            for day in range(5):  # Lundi à jeudi
                if day != preferred_day:
                    for slot in range(12):
                        if not self._check_conflicts_at_slot(day, slot, class_name, []):
                            suggestions.append({
                                'day': day,
                                'slot': slot,
                                'reason': 'Autre jour, créneau libre'
                            })
                            if len(suggestions) >= 5:
                                break
                if len(suggestions) >= 5:
                    break
        
        return suggestions[:5]  # Limiter à 5 suggestions
    
    def _get_slot_id(self, day: int, slot: int) -> int:
        """Calcule le slot_id basé sur le jour et la période"""
        return day * 12 + slot + 1
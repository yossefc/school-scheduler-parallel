"""Utilitaires pour l'agent IA"""
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

def init_default_constraints(agent):
    """Initialise les contraintes institutionnelles par défaut"""
    logger.info("Initialisation des contraintes par défaut")
    # Les contraintes sont déjà dans agent._load_institutional_constraints()
    return True

def format_time_fr(hour: int, minute: int = 0) -> str:
    """Formate l'heure en français"""
    return f"{hour:02d}h{minute:02d}" if minute else f"{hour}h"

def format_day_fr(day_num: int) -> str:
    """Convertit le numéro du jour en nom français"""
    days = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
    return days[day_num] if 0 <= day_num <= 6 else "Inconnu"

def validate_constraint_data(constraint_type: str, data: Dict[str, Any]) -> bool:
    """Valide les données d'une contrainte"""
    required_fields = {
        "teacher_availability": ["unavailable_days"],
        "time_preference": ["preferred_periods"],
        "consecutive_hours_limit": ["max_consecutive"],
        "parallel_teaching": ["groups", "simultaneous"]
    }
    
    if constraint_type not in required_fields:
        return True  # Type non validé = accepté
    
    for field in required_fields[constraint_type]:
        if field not in data:
            return False
    
    return True

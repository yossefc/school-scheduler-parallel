# scheduler_ai/models.py - Version corrigée pour Pydantic v2
"""
Modèles Pydantic corrigés pour la validation des contraintes et données
Compatible avec Pydantic v2+ et validation stricte
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, List, Optional, Any, Literal, Union
from datetime import time, datetime
from enum import Enum, IntEnum

# ========== ENUMS CORRIGÉS ==========

class ConstraintPriority(IntEnum):
    """Niveaux de priorité des contraintes"""
    HARD = 0          # Incontournable (חובה)
    VERY_STRONG = 1   # Quasi-incompressible (חזק מאוד)
    MEDIUM = 2        # Améliore la qualité (בינוני)
    NORMAL = 3        # Standard (רגיל)
    LOW = 4           # Confort (נמוך)
    MINIMAL = 5       # Préférence mineure (מינימלי)

class ConstraintType(str, Enum):
    """Types de contraintes supportés - Système éducatif israélien"""
    TEACHER_AVAILABILITY = "teacher_availability"
    TIME_PREFERENCE = "time_preference"
    CONSECUTIVE_HOURS_LIMIT = "consecutive_hours_limit" 
    PARALLEL_TEACHING = "parallel_teaching"
    SCHOOL_HOURS = "school_hours"
    FRIDAY_EARLY_END = "friday_early_end"
    MORNING_PRAYER = "morning_prayer"
    LUNCH_BREAK = "lunch_break"
    TEACHER_MEETING = "teacher_meeting"
    ROOM_AVAILABILITY = "room_availability"
    CLASS_PREFERENCE = "class_preference"
    GENDER_SEPARATION = "gender_separation"
    HEBREW_FRENCH_BILINGUAL = "hebrew_french_bilingual"
    RELIGIOUS_STUDIES = "religious_studies"

# ========== MODÈLES DE DONNÉES CORRIGÉS ==========

class TeacherAvailabilityData(BaseModel):
    """Données pour la disponibilité d'un enseignant"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    unavailable_days: List[int] = Field(
        ..., 
        min_length=1, 
        max_length=6,
        description="Jours indisponibles (0=Dimanche, 5=Vendredi)"
    )
    unavailable_periods: Optional[List[int]] = Field(
        default_factory=list, 
        max_length=12,
        description="Périodes indisponibles (1-12)"
    )
    reason: Optional[str] = Field(
        default=None, 
        max_length=200,
        description="Raison de l'indisponibilité"
    )
    
    @field_validator('unavailable_days')
    @classmethod
    def validate_days(cls, v):
        """Valide que les jours sont dans la plage correcte"""
        for day in v:
            if not 0 <= day <= 5:  # Dimanche à Vendredi seulement
                raise ValueError(f'Jour invalide: {day}. Doit être entre 0 (dimanche) et 5 (vendredi)')
        return sorted(list(set(v)))  # Éliminer doublons et trier
    
    @field_validator('unavailable_periods')
    @classmethod
    def validate_periods(cls, v):
        """Valide les périodes"""
        if v:
            for period in v:
                if not 1 <= period <= 12:
                    raise ValueError(f'Période invalide: {period}. Doit être entre 1 et 12')
        return sorted(list(set(v))) if v else []

class ConstraintRequest(BaseModel):
    """Modèle de requête pour une contrainte avec validation complète"""
    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    type: ConstraintType = Field(..., description="Type de contrainte")
    entity: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Entité concernée (professeur, classe, etc.)"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Données spécifiques à la contrainte"
    )
    priority: ConstraintPriority = Field(
        default=ConstraintPriority.NORMAL,
        description="Priorité de la contrainte"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Métadonnées additionnelles"
    )

class ConstraintResponse(BaseModel):
    """Réponse après application d'une contrainte"""
    model_config = ConfigDict(use_enum_values=True)
    
    status: Literal["success", "conflict", "error", "pending"]
    constraint_id: Optional[int] = None
    plan: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    solution_diff: Optional[Dict[str, Any]] = None
    score_delta: Optional[int] = None
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    hebrew_explanation: Optional[str] = None

# Export des classes principales
__all__ = [
    'ConstraintRequest', 'ConstraintResponse', 
    'ConstraintType', 'ConstraintPriority',
    'TeacherAvailabilityData'
]

"""Modèles Pydantic pour validation des contraintes"""
from typing import Dict, Any, Optional, List, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ConstraintType(str, Enum):
    TEACHER_AVAILABILITY = "teacher_availability"
    CLASS_PREFERENCE = "class_preference"
    SUBJECT_LIMIT = "subject_limit"
    CONSECUTIVE_HOURS_LIMIT = "consecutive_hours_limit"
    TIME_PREFERENCE = "time_preference"
    PARALLEL_TEACHING = "parallel_teaching"
    ROOM_CONSTRAINT = "room_constraint"
    CUSTOM = "custom"


class ConstraintPriority(int, Enum):
    HARD = 0
    VERY_HIGH = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    SOFT = 5


class ConstraintInput(BaseModel):
    """Modèle d'entrée pour une contrainte avec validation avancée"""
    type: ConstraintType
    entity: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any]
    priority: ConstraintPriority = ConstraintPriority.MEDIUM
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    # Champs calculés/enrichis
    parsed_at: Optional[datetime] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    original_text: Optional[str] = None
    requires_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    
    @field_validator('entity')
    def validate_entity(cls, v: str, info) -> str:
        """Valide et normalise l'entité"""
        v = v.strip()
        
        # Normalisation basique
        if info.data.get('type') == ConstraintType.TEACHER_AVAILABILITY:
            # Capitaliser les noms de professeurs
            v = v.title()
        elif info.data.get('type') == ConstraintType.CLASS_PREFERENCE:
            # Format classes : "9A", "10B", etc
            v = v.upper()
            
        return v
    
    @model_validator(mode='after')
    def validate_constraint_data(self) -> 'ConstraintInput':
        """Validation croisée type/data + détection des clarifications nécessaires"""
        
        if self.type == ConstraintType.TEACHER_AVAILABILITY:
            if 'unavailable_days' not in self.data and 'available_days' not in self.data:
                self.requires_clarification = True
                self.clarification_questions.append(
                    f"Quels jours {self.entity} n'est-il pas disponible ?"
                )
                
        elif self.type == ConstraintType.SUBJECT_LIMIT:
            # Validation pour "pas plus de X heures de Y"
            if 'subject' not in self.data:
                self.requires_clarification = True
                self.clarification_questions.append("Quelle matière est concernée ?")
            
            if 'max_hours_per_day' not in self.data and 'max_consecutive_hours' not in self.data:
                self.requires_clarification = True
                self.clarification_questions.append(
                    "S'agit-il d'une limite par jour ou d'heures consécutives ?"
                )
                
            # Validation des valeurs numériques
            for key in ['max_hours_per_day', 'max_consecutive_hours']:
                if key in self.data:
                    try:
                        val = int(self.data[key])
                        if val < 1 or val > 8:
                            self.requires_clarification = True
                            self.clarification_questions.append(
                                f"La valeur {val} semble inhabituelle. Confirmez-vous ?"
                            )
                    except (ValueError, TypeError):
                        self.requires_clarification = True
                        self.clarification_questions.append(
                            f"La limite doit être un nombre entier"
                        )
                        
        elif self.type == ConstraintType.CONSECUTIVE_HOURS_LIMIT:
            if 'max_consecutive' not in self.data:
                self.requires_clarification = True
                self.clarification_questions.append(
                    "Combien d'heures consécutives maximum ?"
                )
                
        elif self.type == ConstraintType.TIME_PREFERENCE:
            if 'time_slots' not in self.data and 'preferred_periods' not in self.data:
                self.requires_clarification = True
                self.clarification_questions.append(
                    "À quels moments cette contrainte s'applique-t-elle ?"
                )
        
        # Enrichissement automatique
        if not self.parsed_at:
            self.parsed_at = datetime.now()
            
        return self


class ConstraintResponse(BaseModel):
    """Réponse après traitement d'une contrainte"""
    status: Literal["success", "clarification_needed", "conflict", "error"]
    constraint_id: Optional[int] = None
    constraint: Optional[ConstraintInput] = None
    message: str
    clarification_questions: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    applied_automatically: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
# scheduler_ai/models.py - Ajout de la validation Pydantic pour les contraintes

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime, time
from enum import IntEnum

class ConstraintPriority(IntEnum):
    """Niveaux de priorité des contraintes"""
    HARD = 0          # Incontournable
    VERY_STRONG = 1   # Quasi-incompressible
    MEDIUM = 2        # Améliore la qualité
    NORMAL = 3        # Standard
    LOW = 4           # Confort
    MINIMAL = 5       # Préférence mineure

class ConstraintType(str):
    """Types de contraintes supportés"""
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

# Modèles de données pour chaque type de contrainte
class TeacherAvailabilityData(BaseModel):
    """Données pour la disponibilité d'un enseignant"""
    unavailable_days: List[int] = Field(..., min_items=1, max_items=7)
    unavailable_periods: Optional[List[int]] = Field(default=[], max_items=10)
    reason: Optional[str] = Field(default=None, max_length=200)
    
    @field_validator('unavailable_days')
    def validate_days(cls, v):
        for day in v:
            if not 0 <= day <= 6:
                raise ValueError('Les jours doivent être entre 0 (dimanche) et 6 (samedi)')
        return v

class TimePreferenceData(BaseModel):
    """Données pour les préférences horaires"""
    preferred_time: Literal["morning", "afternoon", "evening"]
    preferred_periods: Optional[List[int]] = Field(default=[], max_items=10)
    avoid_periods: Optional[List[int]] = Field(default=[], max_items=10)
    is_strict: bool = Field(default=False)

class ConsecutiveHoursData(BaseModel):
    """Données pour la limitation des heures consécutives"""
    max_consecutive: int = Field(..., ge=1, le=8)
    applies_to: Literal["all", "teachers", "students"] = "all"
    exceptions: Optional[List[str]] = Field(default=[])

class ParallelTeachingData(BaseModel):
    """Données pour l'enseignement parallèle"""
    teachers: List[str] = Field(..., min_items=2, max_items=5)
    classes: List[str] = Field(..., min_items=2)
    simultaneous: bool = Field(default=True)
    subject: str = Field(..., min_length=1)

class SchoolHoursData(BaseModel):
    """Données pour les horaires d'ouverture"""
    start: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    end: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    days: Optional[List[int]] = Field(default=[0, 1, 2, 3, 4, 5])
    
    @field_validator('end')
    def validate_end_after_start(cls, v, info):
        if info.data.get('start') and v <= info.data['start']:
            raise ValueError('L\'heure de fin doit être après l\'heure de début')
        return v

class MorningPrayerData(BaseModel):
    """Données pour la prière du matin"""
    start: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    end: str = Field(..., pattern=r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    days: List[int] = Field(default=[0, 1, 2, 3, 4])
    mandatory_for: Optional[List[str]] = Field(default=["all"])

# Mapping des types vers les modèles de données
CONSTRAINT_DATA_MODELS = {
    ConstraintType.TEACHER_AVAILABILITY: TeacherAvailabilityData,
    ConstraintType.TIME_PREFERENCE: TimePreferenceData,
    ConstraintType.CONSECUTIVE_HOURS_LIMIT: ConsecutiveHoursData,
    ConstraintType.PARALLEL_TEACHING: ParallelTeachingData,
    ConstraintType.SCHOOL_HOURS: SchoolHoursData,
    ConstraintType.MORNING_PRAYER: MorningPrayerData,
}

# Modèle principal de contrainte avec validation
class ConstraintRequest(BaseModel):
    """Modèle de requête pour une contrainte avec validation complète"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: ConstraintType
    entity: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any]
    priority: ConstraintPriority = Field(default=ConstraintPriority.NORMAL)
    metadata: Optional[Dict[str, Any]] = Field(default={})
    
    @field_validator('entity')
    def validate_entity(cls, v, info):
        if 'type' in info.data:
            constraint_type = info.data['type']
            # Validation spécifique selon le type
            if constraint_type == ConstraintType.TEACHER_AVAILABILITY:
                if not v or v == "unknown":
                    raise ValueError('Le nom du professeur est requis')
            elif constraint_type == ConstraintType.CONSECUTIVE_HOURS_LIMIT:
                if v not in ["all", "teachers", "students"]:
                    raise ValueError('Entity doit être "all", "teachers" ou "students"')
        return v
    
    @field_validator('data')
    def validate_data_schema(cls, v, info):
        if 'type' not in info.data:
            return v
            
        constraint_type = info.data['type']
        if constraint_type in CONSTRAINT_DATA_MODELS:
            # Valider avec le modèle Pydantic approprié
            data_model = CONSTRAINT_DATA_MODELS[constraint_type]
            try:
                validated_data = data_model(**v)
                return validated_data.model_dump()
            except Exception as e:
                raise ValueError(f'Données invalides pour {constraint_type}: {str(e)}')
        
        return v

class ConstraintResponse(BaseModel):
    """Réponse après application d'une contrainte"""
    status: Literal["success", "conflict", "error"]
    constraint_id: Optional[int] = None
    plan: Optional[List[Dict[str, Any]]] = None
    solution_diff: Optional[Dict[str, Any]] = None
    score_delta: Optional[int] = None
    conflicts: List[Dict[str, Any]] = Field(default=[])
    suggestions: List[str] = Field(default=[])
    processing_time_ms: Optional[int] = None

# Exemple d'utilisation dans l'API
"""
# Dans scheduler_ai/api.py, modifier la route apply_constraint :

from scheduler_ai.models import ConstraintRequest, ConstraintResponse

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    try:
        # Validation automatique avec Pydantic
        constraint_request = ConstraintRequest(**request.json)
        
        # Appliquer via l'agent
        result = agent.apply_constraint(constraint_request.model_dump())
        
        # Retourner une réponse validée
        response = ConstraintResponse(**result)
        return jsonify(response.model_dump())
        
    except ValidationError as e:
        return jsonify({
            "error": "Validation failed",
            "details": e.errors()
        }), 400
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {str(e)}")
        return jsonify({"error": str(e)}), 500
"""
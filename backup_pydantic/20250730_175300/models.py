# 🔧 CORRECTION DU PROBLÈME PYDANTIC
# Le problème vient de l'utilisation d'Enum avec Pydantic 2.x

# ===== SOLUTION 1: Correction dans solver/models.py =====

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime, time
from enum import Enum

# 🔧 CORRECTION: Hériter de str et Enum correctement
class ConstraintType(str, Enum):
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

class ConstraintPriority(int, Enum):
    """Niveaux de priorité des contraintes"""
    HARD = 0
    VERY_STRONG = 1
    MEDIUM = 2
    NORMAL = 3
    LOW = 4
    MINIMAL = 5

# 🔧 CORRECTION: Configuration Pydantic appropriée
class ConstraintRequest(BaseModel):
    """Modèle de requête pour une contrainte avec validation complète"""
    model_config = ConfigDict(
        use_enum_values=True,           # Utiliser les valeurs des enums
        arbitrary_types_allowed=True,   # Permettre les types personnalisés
        str_strip_whitespace=True,      # Nettoyer les chaînes
        validate_assignment=True        # Valider lors des assignations
    )
    
    # 🔧 CORRECTION: Utiliser les types enum correctement
    type: ConstraintType
    entity: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any]
    priority: ConstraintPriority = Field(default=ConstraintPriority.NORMAL)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

# ===== SOLUTION 2: Version alternative avec Union si problème persiste =====

from typing import Union

# Si les Enums posent encore problème, utiliser des Literal
ConstraintTypeValues = Literal[
    "teacher_availability",
    "time_preference", 
    "consecutive_hours_limit",
    "parallel_teaching",
    "school_hours",
    "friday_early_end",
    "morning_prayer",
    "lunch_break",
    "teacher_meeting",
    "room_availability",
    "class_preference"
]

class ConstraintRequestAlternative(BaseModel):
    """Version alternative sans Enum si nécessaire"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    type: ConstraintTypeValues  # Utiliser Literal au lieu d'Enum
    entity: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any]
    priority: int = Field(default=3, ge=0, le=5)  # Simple int avec validation
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

# ===== SOLUTION 3: Modèles avec validation personnalisée =====

class ConstraintRequestSafe(BaseModel):
    """Version sûre qui fonctionne avec toutes les versions de Pydantic"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )
    
    type: str = Field(..., description="Type de contrainte")
    entity: str = Field(..., min_length=1, max_length=100, description="Entité concernée")
    data: Dict[str, Any] = Field(..., description="Données de la contrainte")
    priority: int = Field(default=3, ge=0, le=5, description="Priorité (0=critique, 5=optionnel)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator('type')
    @classmethod
    def validate_constraint_type(cls, v: str) -> str:
        """Valider que le type de contrainte est supporté"""
        valid_types = {
            "teacher_availability", "time_preference", "consecutive_hours_limit",
            "parallel_teaching", "school_hours", "friday_early_end",
            "morning_prayer", "lunch_break", "teacher_meeting",
            "room_availability", "class_preference"
        }
        
        if v not in valid_types:
            raise ValueError(f"Type de contrainte non supporté: {v}. Types valides: {valid_types}")
        
        return v
    
    @field_validator('priority')
    @classmethod 
    def validate_priority(cls, v: int) -> int:
        """Valider la priorité"""
        if not 0 <= v <= 5:
            raise ValueError("La priorité doit être entre 0 (critique) et 5 (optionnel)")
        return v

# ===== SOLUTION 4: Classes de données simples pour éviter Pydantic =====

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class SimpleConstraintRequest:
    """Version dataclass simple qui évite complètement Pydantic"""
    type: str
    entity: str
    data: Dict[str, Any]
    priority: int = 3
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validation post-initialisation"""
        if not self.entity:
            raise ValueError("Entity ne peut pas être vide")
        
        if not 0 <= self.priority <= 5:
            raise ValueError("Priority doit être entre 0 et 5")
        
        if self.metadata is None:
            self.metadata = {}

# ===== Autres modèles corrigés =====

class ConstraintResponse(BaseModel):
    """Réponse après application d'une contrainte - VERSION CORRIGÉE"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    status: Literal["success", "conflict", "error"]
    constraint_id: Optional[int] = None
    plan: Optional[List[Dict[str, Any]]] = None
    solution_diff: Optional[Dict[str, Any]] = None
    score_delta: Optional[int] = None
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None

class ScheduleRequest(BaseModel):
    """Requête de génération d'emploi du temps - VERSION CORRIGÉE"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    time_limit: int = Field(default=60, ge=10, le=3600)
    optimize_for: Literal["balance", "minimal_gaps", "teacher_preference"] = "balance"

# ===== TEST DE VALIDATION =====

def test_models():
    """Fonction de test pour valider les modèles"""
    
    # Test 1: ConstraintRequest basique
    try:
        request = ConstraintRequestSafe(
            type="teacher_availability",
            entity="Cohen",
            data={"unavailable_days": [5]},
            priority=2
        )
        print("✅ ConstraintRequestSafe fonctionne")
        print(f"   Type: {request.type}, Entity: {request.entity}")
    except Exception as e:
        print(f"❌ ConstraintRequestSafe échoue: {e}")
    
    # Test 2: Version dataclass
    try:
        simple_request = SimpleConstraintRequest(
            type="teacher_availability",
            entity="Cohen", 
            data={"unavailable_days": [5]},
            priority=2
        )
        print("✅ SimpleConstraintRequest fonctionne")
        print(f"   Type: {simple_request.type}, Entity: {simple_request.entity}")
    except Exception as e:
        print(f"❌ SimpleConstraintRequest échoue: {e}")
    
    # Test 3: ConstraintResponse
    try:
        response = ConstraintResponse(
            status="success",
            constraint_id=123,
            score_delta=5
        )
        print("✅ ConstraintResponse fonctionne")
        print(f"   Status: {response.status}, Score delta: {response.score_delta}")
    except Exception as e:
        print(f"❌ ConstraintResponse échoue: {e}")

if __name__ == "__main__":
    test_models()
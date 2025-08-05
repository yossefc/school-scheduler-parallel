# models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ConstraintType(str, Enum):
    TEACHER_AVAILABILITY = "teacher_availability"
    FRIDAY_EARLY_END = "friday_early_end" 
    CONSECUTIVE_HOURS_LIMIT = "consecutive_hours_limit"
    CUSTOM = "custom"

class ConstraintPriority(int, Enum):
    HARD = 0
    HIGH = 1
    MEDIUM = 2
    NORMAL = 3
    LOW = 4

class ConstraintInput(BaseModel):
    type: ConstraintType = ConstraintType.CUSTOM
    entity: Optional[str] = None
    priority: ConstraintPriority = ConstraintPriority.NORMAL
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    text: Optional[str] = None
    requires_clarification: bool = False
    clarification_questions: List[str] = Field(default_factory=list)
    parsed_at: Optional[datetime] = None

class ConstraintResponse(BaseModel):
    status: str
    constraint_id: Optional[int] = None
    constraint: Optional[ConstraintInput] = None
    message: str
    clarification_questions: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    applied_automatically: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

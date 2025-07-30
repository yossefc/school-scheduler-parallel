# models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import time

class Teacher(BaseModel):
    teacher_id: Optional[int] = None
    teacher_name: str
    total_hours: Optional[int] = None
    work_days: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class Subject(BaseModel):
    subject_id: Optional[int] = None
    subject_name: str
    subject_code: Optional[str] = None
    category: Optional[str] = None
    difficulty_level: int = 3

class Class(BaseModel):
    class_id: Optional[int] = None
    grade: int
    section: str
    class_name: str
    student_count: Optional[int] = None

class TimeSlot(BaseModel):
    slot_id: Optional[int] = None
    day_of_week: int  # 0=Sunday, 5=Friday
    period_number: int
    start_time: time
    end_time: time
    is_break: bool = False

class TeacherLoad(BaseModel):
    teacher_name: str
    subject: str
    grade: str
    class_list: str
    hours: int
    work_days: Optional[str] = None

class ParallelGroup(BaseModel):
    subject: str
    grade: str
    teachers: str
    class_lists: str

class Constraint(BaseModel):
    constraint_type: str
    priority: int = 1
    entity_type: Optional[str] = None
    entity_name: Optional[str] = None
    constraint_data: Dict[str, Any]
    is_active: bool = True

class ScheduleRequest(BaseModel):
    constraints: List[Dict[str, Any]] = []
    time_limit: int = 60
    optimize_for: str = "balance"  # balance, minimal_gaps, teacher_preference

class ConstraintRequest(BaseModel):
    type: str
    entity: str
    data: Dict[str, Any]
    priority: int = 2

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

class NaturalLanguageRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None

class ScheduleEntry(BaseModel):
    teacher_name: str
    class_name: str
    subject_name: str
    day_of_week: int
    period_number: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class ScheduleResponse(BaseModel):
    schedule_id: int
    entries: List[ScheduleEntry]
    summary: Dict[str, Any]
    conflicts: List[Dict[str, Any]] = []

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []

# Types de contraintes supportés
CONSTRAINT_TYPES = {
    "teacher_availability": {
        "description": "Disponibilité d'un professeur",
        "required_fields": ["unavailable_days", "unavailable_periods"],
        "entity_type": "teacher"
    },
    "subject_time_preference": {
        "description": "Préférence horaire pour une matière",
        "required_fields": ["preferred_periods"],
        "entity_type": "subject"
    },
    "consecutive_hours_limit": {
        "description": "Limite d'heures consécutives",
        "required_fields": ["max_consecutive"],
        "entity_type": "teacher"
    },
    "class_time_restriction": {
        "description": "Restriction horaire pour une classe",
        "required_fields": ["restricted_periods"],
        "entity_type": "class"
    },
    "parallel_teaching": {
        "description": "Enseignement en parallèle",
        "required_fields": ["groups", "simultaneous"],
        "entity_type": "subject"
    },
    "friday_early_end": {
        "description": "Fin anticipée le vendredi",
        "required_fields": ["last_period"],
        "entity_type": "school"
    },
    "morning_prayer": {
        "description": "Prière du matin",
        "required_fields": ["duration", "start_time"],
        "entity_type": "school"
    }
}

# Mapping des jours
DAYS_MAPPING = {
    "dimanche": 0, "sunday": 0, "ראשון": 0,
    "lundi": 1, "monday": 1, "שני": 1,
    "mardi": 2, "tuesday": 2, "שלישי": 2,
    "mercredi": 3, "wednesday": 3, "רביעי": 3,
    "jeudi": 4, "thursday": 4, "חמישי": 4,
    "vendredi": 5, "friday": 5, "שישי": 5
}
"""Tests pour le flux de contraintes"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from scheduler_ai.models import ConstraintInput, ConstraintResponse, ConstraintType
from scheduler_ai.parsers import extract_constraint
from scheduler_ai.agent_extensions import ClarificationMiddleware


class TestConstraintParsing:
    """Tests du parsing de contraintes"""
    
    def test_parse_subject_limit_hours_per_day(self):
        """Test parsing limite heures par jour"""
        text = "pas plus de 3 heures de math par jour"
        constraint = extract_constraint(text)
        
        assert constraint.type == ConstraintType.SUBJECT_LIMIT
        assert constraint.data['subject'] == 'math'
        assert constraint.data.get('max_hours_per_day') == 3
        assert not constraint.requires_clarification
        
    def test_parse_subject_limit_consecutive(self):
        """Test parsing limite heures consécutives"""
        text = "maximum 2 heures consécutives de français"
        constraint = extract_constraint(text)
        
        assert constraint.type == ConstraintType.SUBJECT_LIMIT
        assert constraint.data['subject'] == 'français'
        assert constraint.data.get('max_consecutive_hours') == 2
        
    def test_parse_ambiguous_limit(self):
        """Test parsing limite ambiguë"""
        text = "je voudrais qu'il n'y ait pas plus de 3 à deux heures de math dans une journée"
        constraint = extract_constraint(text)
        
        assert constraint.type == ConstraintType.SUBJECT_LIMIT
        assert constraint.data['subject'] == 'math'
        # Devrait demander clarification sur la valeur exacte
        assert constraint.requires_clarification
        
    def test_parse_teacher_availability(self):
        """Test parsing disponibilité professeur"""
        text = "le professeur Cohen ne peut pas enseigner le vendredi"
        constraint = extract_constraint(text)
        
        assert constraint.type == ConstraintType.TEACHER_AVAILABILITY
        assert constraint.entity == "Cohen"
        assert constraint.data['unavailable_days'] == [5]
        assert constraint.confidence > 0.8
        
    def test_parse_unknown_constraint(self):
        """Test parsing contrainte non reconnue"""
        text = "quelque chose de complètement aléatoire"
        constraint = extract_constraint(text)
        
        assert constraint.type == ConstraintType.CUSTOM
        assert constraint.requires_clarification


class TestClarificationMiddleware:
    """Tests du middleware de clarification"""
    
    @pytest.fixture
    def middleware(self):
        return ClarificationMiddleware(max_attempts=3)
    
    @pytest.mark.asyncio
    async def test_successful_constraint(self, middleware):
        """Test contrainte comprise du premier coup"""
        response = await middleware.process_constraint(
            "maximum 2 heures de math par jour",
            "session123"
        )
        
        assert response.status == "success"
        assert response.applied_automatically
        assert response.confidence >= 0.8
        
    @pytest.mark.asyncio
    async def test_clarification_needed(self, middleware):
        """Test demande de clarification"""
        response = await middleware.process_constraint(
            "limite pour les maths",
            "session123"
        )
        
        assert response.status == "clarification_needed"
        assert len(response.clarification_questions) > 0
        assert "combien" in response.clarification_questions[0].lower()
        
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, middleware):
        """Test échec après 3 tentatives"""
        session_id = "session123"
        
        # 3 tentatives qui échouent
        for i in range(3):
            response = await middleware.process_constraint(
                "contrainte incompréhensible xyz",
                session_id
            )
            assert response.status == "clarification_needed"
            
        # 4ème tentative = échec
        response = await middleware.process_constraint(
            "contrainte incompréhensible xyz",
            session_id
        )
        
        assert response.status == "error"
        assert "impossible de comprendre" in response.message.lower()
        assert len(response.suggestions) > 0


class TestConstraintValidation:
    """Tests de validation Pydantic"""
    
    def test_valid_constraint_input(self):
        """Test création contrainte valide"""
        constraint = ConstraintInput(
            type=ConstraintType.SUBJECT_LIMIT,
            entity="all_classes",
            data={
                "subject": "math",
                "max_hours_per_day": 3
            }
        )
        
        assert not constraint.requires_clarification
        assert constraint.parsed_at is not None
        
    def test_missing_required_data(self):
        """Test données manquantes"""
        constraint = ConstraintInput(
            type=ConstraintType.SUBJECT_LIMIT,
            entity="all_classes",
            data={}  # Manque subject et limite
        )
        
        assert constraint.requires_clarification
        assert len(constraint.clarification_questions) >= 2
        
    def test_invalid_numeric_value(self):
        """Test valeur numérique invalide"""
        constraint = ConstraintInput(
            type=ConstraintType.SUBJECT_LIMIT,
            entity="all_classes",
            data={
                "subject": "math",
                "max_hours_per_day": 15  # Trop élevé
            }
        )
        
        assert constraint.requires_clarification
        assert any("inhabituelle" in q for q in constraint.clarification_questions)
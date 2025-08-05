"""
tests/test_agent.py - Tests unitaires pour l'agent IA
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from scheduler_ai.agent import ScheduleAIAgent, ConstraintPriority
from scheduler_ai.llm_router import LLMRouter, TaskComplexity

# Fixtures
@pytest.fixture
def db_config():
    return {
        "host": "postgres",   # ✅ Pour Docker
        "database": "test_scheduler",
        "user": "test_user",
        "password": "test_pass"
    }

@pytest.fixture
def agent(db_config):
    with patch('scheduler_ai.agent.create_engine'):
        return ScheduleAIAgent(db_config)

@pytest.fixture
def llm_router():
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'ANTHROPIC_API_KEY': 'test-key'
    }):
        return LLMRouter()

# Tests ScheduleAIAgent
class TestScheduleAIAgent:
    
    def test_init(self, agent):
        """Test l'initialisation de l'agent"""
        assert agent.db_config is not None
        assert len(agent.institutional_constraints) >= 5
        assert agent.institutional_constraints[0]['priority'] == ConstraintPriority.HARD.value
    
    @pytest.mark.asyncio
    async def test_apply_constraint_success(self, agent):
        """Test l'application réussie d'une contrainte"""
        constraint = {
            "type": "teacher_availability",
            "entity": "Cohen",
            "data": {"unavailable_days": [5]},
            "priority": 2
        }
        
        # Mock des méthodes internes
        agent._analyze_constraint = Mock(return_value={
            "has_hard_conflicts": False,
            "conflicts": [],
            "soft_conflicts": [],
            "affected_entities": ["Cohen"]
        })
        
        agent._simulate_constraint_application = Mock(return_value=asyncio.coroutine(lambda: {
            "feasible": True,
            "score_delta": 5
        })())
        
        agent._apply_constraint_to_solver = Mock(return_value=asyncio.coroutine(lambda: {
            "success": True,
            "constraint_id": 123,
            "schedule_id": 456,
            "diff": {"added": 2, "removed": 1},
            "score_delta": 5
        })())
        
        agent._save_to_history = Mock()
        
        result = await agent.apply_constraint(constraint)
        
        assert result["status"] == "success"
        assert result["score_delta"] == 5
        assert "plan" in result
        agent._save_to_history.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_constraint_with_conflict(self, agent):
        """Test l'application d'une contrainte avec conflit"""
        constraint = {
            "type": "teacher_availability",
            "entity": "Cohen",
            "data": {"unavailable_days": [1, 2, 3, 4, 5]},
            "priority": 2
        }
        
        agent._analyze_constraint = Mock(return_value={
            "has_hard_conflicts": True,
            "conflicts": [{
                "type": "teacher_availability",
                "message": "Cohen doit enseigner 20h mais n'a aucun jour disponible"
            }],
            "soft_conflicts": [],
            "affected_entities": ["Cohen"]
        })
        
        agent._generate_suggestions = Mock(return_value=[
            {"action": "reduce_hours", "description": "Réduire les heures de Cohen"},
            {"action": "change_teacher", "description": "Remplacer Cohen"}
        ])
        
        result = await agent.apply_constraint(constraint)
        
        assert result["status"] == "conflict"
        assert len(result["conflicts"]) > 0
        assert len(result["suggestions"]) > 0
    
    def test_explain_conflict(self, agent):
        """Test l'explication d'un conflit"""
        agent._get_conflict_details = Mock(return_value={
            "type": "teacher_availability",
            "severity": 0.8,
            "entities": ["Cohen", "9A"],
            "params": {
                "teacher": "Cohen",
                "day": "vendredi",
                "time": "14h",
                "subject": "Math",
                "class": "9A"
            }
        })
        
        explanation = agent.explain_conflict("conflict_123")
        
        assert "natural_language" in explanation
        assert "Cohen" in explanation["natural_language"]
        assert "suggestions" in explanation
        assert explanation["severity"] == 0.8
    
    def test_calculate_schedule_score(self, agent):
        """Test le calcul du score d'un emploi du temps"""
        schedule = [
            {"teacher_name": "Cohen", "day_of_week": 1, "period_number": 1},
            {"teacher_name": "Cohen", "day_of_week": 1, "period_number": 3},  # Trou
            {"teacher_name": "Levy", "day_of_week": 1, "period_number": 8, "subject_name": "Math"}  # Math tard
        ]
        
        agent._count_teacher_gaps = Mock(return_value=1)
        agent._count_late_hard_subjects = Mock(return_value=1)
        agent._calculate_distribution_score = Mock(return_value=10)
        
        score = agent._calculate_schedule_score(schedule)
        
        assert score > 0
        assert score < 100  # Avec pénalités

# Tests LLMRouter
class TestLLMRouter:
    
    def test_choose_model_simple(self, llm_router):
        """Test le choix de modèle pour tâche simple"""
        model = llm_router.choose_model("simple_constraint", 5000)
        assert model == "openai/gpt-4o"
    
    def test_choose_model_complex(self, llm_router):
        """Test le choix de modèle pour tâche complexe"""
        model = llm_router.choose_model("deep_reasoning", 150000)
        assert model == "anthropic/claude-4-opus"
    
    def test_choose_model_hybrid(self, llm_router):
        """Test le choix hybride"""
        model = llm_router.choose_model("parallel_scheduling", 50000, TaskComplexity.HIGH)
        assert model == "hybrid"
    
    def test_detect_constraint_type(self, llm_router):
        """Test la détection du type de contrainte"""
        tests = [
            ("Le professeur Cohen ne peut pas enseigner le vendredi", "teacher_availability"),
            ("Les cours de math uniquement le matin", "time_preference"),
            ("Cohen et Levy enseignent ensemble", "parallel_teaching"),
        ]
        
        for text, expected_type in tests:
            detected = llm_router._detect_constraint_type(text)
            assert detected == expected_type
    
    @patch('scheduler_ai.llm_router.LLMRouter._call_openai')
    def test_parse_natural_language(self, mock_openai, llm_router):
        """Test le parsing du langage naturel"""
        mock_openai.return_value = MagicMock(
            content=json.dumps({
                "constraint": {
                    "type": "teacher_availability",
                    "entity": "Cohen",
                    "data": {"unavailable_days": [5]},
                    "priority": 2
                },
                "summary": "Cohen pas disponible vendredi",
                "alternatives": []
            })
        )
        
        result = llm_router.parse_natural_language(
            "Le professeur Cohen ne peut pas enseigner le vendredi"
        )
        
        assert result["constraint"]["type"] == "teacher_availability"
        assert result["constraint"]["entity"] == "Cohen"
        assert result["confidence"] > 0.5
    
    def test_calculate_confidence(self, llm_router):
        """Test le calcul de confiance"""
        parsed = {
            "constraint": {
                "type": "teacher_availability",
                "entity": "Cohen",
                "data": {"unavailable_days": [5]}
            },
            "alternatives": []
        }
        
        confidence = llm_router._calculate_confidence(
            parsed,
            "Cohen ne peut pas le vendredi"
        )
        
        assert 0 <= confidence <= 1
        assert confidence > 0.7  # Parsing complet et cohérent

# Tests d'intégration
class TestIntegration:
    
    @pytest.mark.asyncio
    async def test_full_constraint_flow(self, agent, llm_router):
        """Test le flow complet d'ajout de contrainte"""
        # 1. Parser le texte
        with patch.object(llm_router, '_call_openai') as mock_llm:
            mock_llm.return_value = MagicMock(
                content=json.dumps({
                    "constraint": {
                        "type": "teacher_availability",
                        "entity": "Cohen",
                        "data": {"unavailable_days": [5]},
                        "priority": 2
                    },
                    "summary": "Cohen pas disponible vendredi",
                    "alternatives": []
                })
            )
            
            parsed = llm_router.parse_natural_language(
                "Le professeur Cohen ne peut pas enseigner le vendredi"
            )
        
        # 2. Appliquer la contrainte
        with patch.multiple(agent,
            _analyze_constraint=Mock(return_value={
                "has_hard_conflicts": False,
                "conflicts": [],
                "soft_conflicts": [],
                "affected_entities": ["Cohen"]
            }),
            _simulate_constraint_application=Mock(return_value=asyncio.coroutine(lambda: {
                "feasible": True,
                "score_delta": 5
            })()),
            _apply_constraint_to_solver=Mock(return_value=asyncio.coroutine(lambda: {
                "success": True,
                "constraint_id": 123,
                "diff": {},
                "score_delta": 5
            })()),
            _save_to_history=Mock()
        ):
            result = await agent.apply_constraint(parsed["constraint"])
        
        assert result["status"] == "success"
        assert result["score_delta"] == 5

# Tests de performance
class TestPerformance:
    
    @pytest.mark.slow
    def test_large_schedule_analysis(self, agent):
        """Test avec un grand emploi du temps"""
        # Créer un emploi du temps de 1000 entrées
        large_schedule = [
            {
                "teacher_name": f"Teacher{i%20}",
                "class_name": f"Class{i%30}",
                "day_of_week": i % 6,
                "period_number": (i % 10) + 1
            }
            for i in range(1000)
        ]
        
        start_time = datetime.now()
        score = agent._calculate_schedule_score(large_schedule)
        duration = (datetime.now() - start_time).total_seconds()
        
        assert score >= 0
        assert duration < 1.0  # Moins d'1 seconde

# Mocks et helpers
def create_mock_schedule(size=100):
    """Crée un emploi du temps de test"""
    return [
        {
            "entry_id": i,
            "teacher_name": f"Teacher{i%10}",
            "class_name": f"Class{i%5}",
            "subject_name": f"Subject{i%8}",
            "day_of_week": i % 6,
            "period_number": (i % 10) + 1
        }
        for i in range(size)
    ]

def create_mock_constraint(constraint_type="teacher_availability"):
    """Crée une contrainte de test"""
    return {
        "type": constraint_type,
        "entity": "TestEntity",
        "data": {"test": True},
        "priority": 2
    }

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
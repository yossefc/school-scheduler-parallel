#!/usr/bin/env python3
"""Test rapide des corrections Pydantic"""

import sys
sys.path.insert(0, 'scheduler_ai')

try:
    from models import ConstraintRequest, ConstraintType
    print("✅ Import models réussi")
    
    # Test validation
    test_data = {
        "type": "teacher_availability",
        "entity": "Test",
        "data": {"unavailable_days": [1, 2]},
        "priority": 2
    }
    
    constraint = ConstraintRequest(**test_data)
    print(f"✅ Validation réussie: {constraint.type}")
    print("🎉 Corrections Pydantic fonctionnelles!")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    sys.exit(1)

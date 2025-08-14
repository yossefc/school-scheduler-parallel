#!/usr/bin/env python3
"""
Simple test for integrated solver
"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test all required imports"""
    print("=== TESTING IMPORTS ===")
    
    try:
        from integrated_solver import IntegratedScheduleSolver
        print("OK: IntegratedScheduleSolver imported")
        
        from parallel_course_handler import ParallelCourseHandler
        print("OK: ParallelCourseHandler imported")
        
        from ortools.sat.python import cp_model
        print("OK: OR-Tools CP-SAT imported")
        
        import psycopg2
        print("OK: psycopg2 imported")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_solver_creation():
    """Test solver creation"""
    print("\n=== TESTING SOLVER CREATION ===")
    
    try:
        from integrated_solver import IntegratedScheduleSolver
        
        db_config = {
            "host": "localhost",
            "database": "test_db", 
            "user": "test_user",
            "password": "test_pass",
            "port": 5432
        }
        
        solver = IntegratedScheduleSolver(db_config=db_config)
        print("OK: Solver created")
        print(f"Config: {solver.config}")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_parallel_course_logic():
    """Test parallel course logic"""
    print("\n=== TESTING PARALLEL COURSE LOGIC ===")
    
    try:
        from parallel_course_handler import ParallelCourseHandler
        
        # Test data with parallel courses
        test_courses = [
            {
                'course_id': 1,
                'subject': 'math',
                'teacher_names': 'teacher1',
                'class_list': 'class1',
                'hours': 2,
                'is_parallel': False,
                'group_id': None
            },
            {
                'course_id': 2,
                'subject': 'bible',
                'teacher_names': 'teacher2, teacher3',
                'class_list': 'class1, class2',
                'hours': 1,
                'is_parallel': True,
                'group_id': 1
            },
            {
                'course_id': 3,
                'subject': 'bible',
                'teacher_names': 'teacher4, teacher5',
                'class_list': 'class3, class4',
                'hours': 1,
                'is_parallel': True,
                'group_id': 1
            }
        ]
        
        expanded_courses, sync_groups = ParallelCourseHandler.expand_parallel_courses(test_courses)
        
        print(f"OK: Processed {len(test_courses)} courses")
        print(f"OK: Found {len(sync_groups)} parallel groups")
        
        for group_id, course_ids in sync_groups.items():
            print(f"  Group {group_id}: {len(course_ids)} courses")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_model_creation():
    """Test CP-SAT model creation"""
    print("\n=== TESTING MODEL CREATION ===")
    
    try:
        from integrated_solver import IntegratedScheduleSolver
        
        db_config = {"host": "test", "database": "test", "user": "test", "password": "test", "port": 5432}
        solver = IntegratedScheduleSolver(db_config=db_config)
        
        # Simulate data
        solver.courses = [
            {'course_id': 1, 'subject': 'math', 'teacher_names': 'teacher1', 'class_list': 'class1', 'hours': 2, 'is_parallel': False, 'group_id': None}
        ]
        
        solver.time_slots = []
        for day in range(5):  # Sunday-Thursday
            for period in range(1, 9):  # 8 periods per day
                solver.time_slots.append({
                    'slot_id': day * 8 + period,
                    'day_of_week': day,
                    'period_number': period
                })
        
        solver.classes = ['class1']
        solver.parallel_groups = {}
        
        # Test variable creation
        solver.create_variables()
        print(f"OK: Created {len(solver.schedule_vars)} schedule variables")
        
        # Test constraint addition
        solver.add_constraints()
        print("OK: Constraints added to model")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Main test runner"""
    print("Integrated Solver Test Suite")
    print("-" * 40)
    
    tests = [
        test_imports,
        test_solver_creation,
        test_parallel_course_logic,
        test_model_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print("Test failed - stopping")
            break
    
    print("-" * 40)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("SUCCESS: All tests passed!")
        print("Integrated solver is ready for deployment")
        return True
    else:
        print("FAILURE: Some tests failed")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)
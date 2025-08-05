#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_everything_no_psql.py - Correction complète sans nécessiter psql
"""
import os
import sys
import subprocess
import psycopg2
from datetime import datetime

print("="*60)
print("   CORRECTION COMPLÈTE - SCHOOL SCHEDULER")
print("="*60)
print(f"Début: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123"
}

def check_postgresql_connection():
    """Vérifie la connexion PostgreSQL"""
    print("[0/6] Vérification de PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        print("✓ PostgreSQL accessible\n")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL inaccessible: {e}")
        print("\nOptions:")
        print("1. Démarrez PostgreSQL via Services Windows")
        print("2. Ou utilisez: docker-compose up -d postgres")
        print("3. Ou installez PostgreSQL depuis postgresql.org\n")
        return False

def fix_database():
    """Corrige la base de données directement avec Python"""
    print("[1/6] Correction de la base de données...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Corrections des colonnes
        fixes = [
            ("teachers", "is_active", "BOOLEAN DEFAULT true"),
            ("classes", "is_active", "BOOLEAN DEFAULT true"),
            ("time_slots", "is_active", "BOOLEAN DEFAULT true"),
            ("rooms", "is_available", "BOOLEAN DEFAULT true")
        ]
        
        for table, column, col_type in fixes:
            try:
                cur.execute(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = '{column}'
                """)
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    print(f"  ✓ Ajouté {table}.{column}")
            except Exception as e:
                print(f"  ! Erreur {table}.{column}: {e}")
        
        cur.close()
        conn.close()
        print("✓ Base de données corrigée\n")
        return True
    except Exception as e:
        print(f"✗ Erreur DB: {e}\n")
        return False

def create_missing_modules():
    """Crée tous les modules Python manquants"""
    print("[2/6] Création des modules manquants...")
    
    modules = {
        "scheduler_ai/fuzzy_hebrew_matching.py": """# fuzzy_hebrew_matching.py
class HebrewFuzzyMatcher:
    def __init__(self):
        self.threshold = 0.8
    
    def match(self, str1, str2):
        if not str1 or not str2:
            return 0.0
        s1, s2 = str1.lower().strip(), str2.lower().strip()
        if s1 == s2:
            return 1.0
        if s1 in s2 or s2 in s1:
            return 0.8
        common = sum(1 for c in s1 if c in s2)
        return common / max(len(s1), len(s2))
""",
        
        "scheduler_ai/parsers.py": """# parsers.py
def natural_language_parser(text):
    text_lower = text.lower()
    
    # Détection du type
    constraint_type = "custom"
    if "disponible" in text_lower or "availability" in text_lower:
        constraint_type = "teacher_availability"
    elif "vendredi" in text_lower:
        constraint_type = "friday_constraint"
    elif "consecutive" in text_lower or "consécutives" in text_lower:
        constraint_type = "consecutive_hours_limit"
    
    # Extraction d'entité
    entity = None
    words = text.split()
    for i, word in enumerate(words):
        if word.lower() in ["professeur", "prof", "teacher"] and i + 1 < len(words):
            entity = words[i + 1]
            break
    
    return {
        "type": constraint_type,
        "entity": entity,
        "original_text": text
    }
""",
        
        "scheduler_ai/agent_extensions.py": """# agent_extensions.py
class ClarificationMiddleware:
    def __init__(self):
        self.pending_clarifications = {}
    
    def process(self, constraint):
        if not constraint.get("entity"):
            return {
                "needs_clarification": True,
                "question": "Pour quelle entité cette contrainte s'applique-t-elle ?"
            }
        return {"needs_clarification": False}

clarification_middleware = ClarificationMiddleware()
""",
        
        "scheduler_ai/database.py": """# database.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Constraint(Base):
    __tablename__ = 'constraints'
    
    constraint_id = Column(Integer, primary_key=True)
    constraint_type = Column(String(50))
    entity_name = Column(String(100))
    constraint_data = Column(JSON)
    priority = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

def get_db_session():
    engine = create_engine('postgresql://admin:school123@localhost/school_scheduler')
    Session = sessionmaker(bind=engine)
    return Session()

def create_tables():
    # Créer les tables si nécessaire
    pass
""",
        
        "scheduler_ai/models.py": """# models.py
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
"""
    }
    
    for filepath, content in modules.items():
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Créé: {filepath}")
        except Exception as e:
            print(f"  ✗ Erreur {filepath}: {e}")
    
    # Créer les __init__.py
    for dir_path in ["scheduler_ai", "solver", "database", "tests"]:
        if os.path.exists(dir_path):
            init_file = os.path.join(dir_path, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, 'w') as f:
                    f.write("# -*- coding: utf-8 -*-\n")
                print(f"  ✓ Créé: {init_file}")
    
    print("✓ Modules créés\n")

def fix_solver_init():
    """Corrige le constructeur du solver"""
    print("[3/6] Correction du solver...")
    
    solver_file = "solver/solver_engine.py"
    if not os.path.exists(solver_file):
        print(f"  ! {solver_file} n'existe pas")
        return
    
    try:
        with open(solver_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer la signature __init__
        if "def __init__(self):" in content:
            # Trouver la position
            init_pos = content.find("def __init__(self):")
            if init_pos != -1:
                # Trouver la fin de __init__
                next_def = content.find("\n    def ", init_pos + 1)
                if next_def == -1:
                    next_def = len(content)
                
                # Nouveau __init__
                new_init = '''def __init__(self, db_config=None):
        """Initialise le solver avec configuration optionnelle"""
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        if db_config is None:
            db_config = {
                "host": "localhost",
                "database": "school_scheduler",
                "user": "admin",
                "password": "school123"
            }
        
        self.db_config = db_config
        self.schedule_vars = {}
        self.parallel_vars = {}
        self.teachers = []
        self.classes = []
        self.subjects = []
        self.rooms = []
        self.time_slots = []
        self.teacher_load = []
        self.constraints = []
        self.parallel_groups = []
        self.parallel_details = []
        self.objective_terms = []'''
                
                # Remplacer
                content = content[:init_pos] + new_init + content[next_def:]
                
                # Sauvegarder
                with open(solver_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"  ✓ Solver corrigé")
        else:
            print("  ! Signature __init__ non trouvée")
            
    except Exception as e:
        print(f"  ✗ Erreur solver: {e}")
    
    print("✓ Solver traité\n")

def fix_encoding():
    """Corrige l'encodage des fichiers"""
    print("[4/6] Correction de l'encodage...")
    
    files = ["scheduler_ai/agent.py", "scheduler_ai/api.py", "solver/solver_engine.py"]
    
    for filepath in files:
        if os.path.exists(filepath):
            try:
                # Lire avec différents encodages
                content = None
                for enc in ['utf-8', 'cp1252', 'iso-8859-1', 'utf-16']:
                    try:
                        with open(filepath, 'r', encoding=enc) as f:
                            content = f.read()
                        break
                    except:
                        continue
                
                if content:
                    # Nettoyer
                    content = content.replace('?', 'e')
                    content = content.replace('\\x0a', '\n')
                    content = content.replace('\\x5cn', '\n')
                    
                    # Sauvegarder en UTF-8
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"  ✓ Corrigé: {filepath}")
            except Exception as e:
                print(f"  ✗ Erreur {filepath}: {e}")
    
    print("✓ Encodage traité\n")

def install_packages():
    """Installe les packages manquants"""
    print("[5/6] Installation des packages...")
    
    packages = ["psycopg2-binary", "ortools", "flask", "flask-socketio", 
                "flask-cors", "sqlalchemy", "pydantic", "chardet"]
    
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"  ✓ {pkg} déjà installé")
        except ImportError:
            print(f"  → Installation de {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
            print(f"  ✓ {pkg} installé")
    
    print("✓ Packages OK\n")

def final_test():
    """Test final rapide"""
    print("[6/6] Test final...")
    
    try:
        # Test imports
        from scheduler_ai.fuzzy_hebrew_matching import HebrewFuzzyMatcher
        from scheduler_ai.parsers import natural_language_parser
        from scheduler_ai.agent_extensions import clarification_middleware
        print("  ✓ Modules importables")
        
        # Test DB
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM teachers WHERE is_active = true")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  ✓ Base de données OK ({count} professeurs actifs)")
        
        print("✓ Tests passés\n")
        return True
    except Exception as e:
        print(f"  ✗ Erreur test: {e}\n")
        return False

def main():
    """Fonction principale"""
    # Vérifier PostgreSQL d'abord
    if not check_postgresql_connection():
        print("⚠️ PostgreSQL doit être démarré pour continuer.")
        sys.exit(1)
    
    # Exécuter toutes les corrections
    steps = [
        fix_database,
        create_missing_modules,
        fix_solver_init,
        fix_encoding,
        install_packages,
        final_test
    ]
    
    success = 0
    for step in steps:
        try:
            if step():
                success += 1
        except Exception as e:
            print(f"Erreur dans {step.__name__}: {e}\n")
    
    print("="*60)
    print(f"RÉSUMÉ: {success}/{len(steps)} étapes réussies")
    print("="*60)
    
    if success == len(steps):
        print("\n✅ Système complètement corrigé!")
        print("\nProchaine étape:")
        print("  python verify_system.py")
    else:
        print("\n⚠️ Certaines corrections ont échoué.")
        print("Relancez le script après avoir résolu les problèmes.")
    
    print(f"\nFin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
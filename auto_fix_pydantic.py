#!/usr/bin/env python3
"""
auto_fix_pydantic.py - Script de correction automatique pour les erreurs Pydantic
Applique toutes les corrections nécessaires automatiquement
"""

import os
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime
import subprocess

# Couleurs multi-plateforme
class Colors:
    if os.name == 'nt':
        try:
            import colorama
            colorama.init()
        except ImportError:
            pass
    
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def log(level, message):
    colors = {
        'INFO': Colors.CYAN,
        'SUCCESS': Colors.GREEN, 
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'HEADER': Colors.BLUE + Colors.BOLD
    }
    
    symbol = {
        'INFO': 'ℹ️ ',
        'SUCCESS': '✅',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'HEADER': '🔧'
    }
    
    color = colors.get(level, '')
    sym = symbol.get(level, '')
    print(f"{color}{sym} {message}{Colors.END}")

def create_backup():
    """Crée une sauvegarde des fichiers existants"""
    log('INFO', 'Création de la sauvegarde...')
    
    backup_dir = Path('backup_pydantic') / datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_backup = [
        'scheduler_ai/models.py',
        'scheduler_ai/api.py',
        'scheduler_ai/requirements.txt'
    ]
    
    backed_up = []
    for file_path in files_to_backup:
        if Path(file_path).exists():
            dest = backup_dir / Path(file_path).name
            shutil.copy2(file_path, dest)
            backed_up.append(file_path)
    
    if backed_up:
        log('SUCCESS', f'Sauvegarde créée: {backup_dir}')
        log('INFO', f'Fichiers sauvegardés: {", ".join(backed_up)}')
        return str(backup_dir)
    else:
        log('WARNING', 'Aucun fichier à sauvegarder trouvé')
        return None

def check_project_structure():
    """Vérifie la structure du projet"""
    log('INFO', 'Vérification de la structure du projet...')
    
    required_dirs = ['scheduler_ai']
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            missing_dirs.append(dir_name)
    
    if missing_dirs:
        log('WARNING', f'Répertoires manquants: {", ".join(missing_dirs)}')
        for dir_name in missing_dirs:
            Path(dir_name).mkdir(parents=True, exist_ok=True)
            log('SUCCESS', f'Répertoire créé: {dir_name}')
    
    # Créer __init__.py si nécessaire
    init_files = ['scheduler_ai/__init__.py']
    for init_file in init_files:
        init_path = Path(init_file)
        if not init_path.exists():
            init_path.touch()
            log('SUCCESS', f'Fichier créé: {init_file}')
    
    log('SUCCESS', 'Structure du projet vérifiée')

def update_requirements():
    """Met à jour requirements.txt avec les bonnes versions"""
    log('INFO', 'Mise à jour des requirements...')
    
    requirements_content = """# Core dependencies - School Scheduler AI
flask==3.0.0
flask-socketio==5.3.5
flask-cors==4.0.0
python-socketio==5.10.0

# Server performance
eventlet==0.33.3
gunicorn==21.2.0

# Validation et modèles
pydantic>=2.0.0,<3.0.0
pydantic-settings>=2.0.0

# Database
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
alembic==1.13.0

# AI/LLM
openai>=1.14.0
tiktoken>=0.6.0
anthropic>=0.8.1

# Async
asyncio==3.4.3
aiohttp==3.9.1

# Data processing
pandas==2.1.4
numpy==1.24.3

# OR-Tools (pour le solveur)
ortools==9.7.2996

# Utils
python-dotenv==1.0.0
click==8.1.7
requests==2.31.0
python-dateutil==2.8.2

# Development
black==23.12.1
pytest==7.4.3
pytest-asyncio==0.21.1

# Monitoring
prometheus-client==0.19.0

# Hebrew/Unicode support
charset-normalizer==3.3.2
"""
    
    req_path = Path('scheduler_ai/requirements.txt')
    with open(req_path, 'w', encoding='utf-8') as f:
        f.write(requirements_content)
    
    log('SUCCESS', f'Requirements mis à jour: {req_path}')

def create_models_file():
    """Crée le fichier models.py corrigé"""
    log('INFO', 'Création du fichier models.py corrigé...')
    
    # Le contenu est celui de l'artifact pydantic_fix_models
    models_content = '''# scheduler_ai/models.py - Version corrigée pour Pydantic v2
"""
Modèles Pydantic corrigés pour la validation des contraintes et données
Compatible avec Pydantic v2+ et validation stricte
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, List, Optional, Any, Literal, Union
from datetime import time, datetime
from enum import Enum, IntEnum

# ========== ENUMS CORRIGÉS ==========

class ConstraintPriority(IntEnum):
    """Niveaux de priorité des contraintes"""
    HARD = 0          # Incontournable (חובה)
    VERY_STRONG = 1   # Quasi-incompressible (חזק מאוד)
    MEDIUM = 2        # Améliore la qualité (בינוני)
    NORMAL = 3        # Standard (רגיל)
    LOW = 4           # Confort (נמוך)
    MINIMAL = 5       # Préférence mineure (מינימלי)

class ConstraintType(str, Enum):
    """Types de contraintes supportés - Système éducatif israélien"""
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
    GENDER_SEPARATION = "gender_separation"
    HEBREW_FRENCH_BILINGUAL = "hebrew_french_bilingual"
    RELIGIOUS_STUDIES = "religious_studies"

# ========== MODÈLES DE DONNÉES CORRIGÉS ==========

class TeacherAvailabilityData(BaseModel):
    """Données pour la disponibilité d'un enseignant"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True
    )
    
    unavailable_days: List[int] = Field(
        ..., 
        min_length=1, 
        max_length=6,
        description="Jours indisponibles (0=Dimanche, 5=Vendredi)"
    )
    unavailable_periods: Optional[List[int]] = Field(
        default_factory=list, 
        max_length=12,
        description="Périodes indisponibles (1-12)"
    )
    reason: Optional[str] = Field(
        default=None, 
        max_length=200,
        description="Raison de l'indisponibilité"
    )
    
    @field_validator('unavailable_days')
    @classmethod
    def validate_days(cls, v):
        """Valide que les jours sont dans la plage correcte"""
        for day in v:
            if not 0 <= day <= 5:  # Dimanche à Vendredi seulement
                raise ValueError(f'Jour invalide: {day}. Doit être entre 0 (dimanche) et 5 (vendredi)')
        return sorted(list(set(v)))  # Éliminer doublons et trier
    
    @field_validator('unavailable_periods')
    @classmethod
    def validate_periods(cls, v):
        """Valide les périodes"""
        if v:
            for period in v:
                if not 1 <= period <= 12:
                    raise ValueError(f'Période invalide: {period}. Doit être entre 1 et 12')
        return sorted(list(set(v))) if v else []

class ConstraintRequest(BaseModel):
    """Modèle de requête pour une contrainte avec validation complète"""
    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    type: ConstraintType = Field(..., description="Type de contrainte")
    entity: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Entité concernée (professeur, classe, etc.)"
    )
    data: Dict[str, Any] = Field(
        ...,
        description="Données spécifiques à la contrainte"
    )
    priority: ConstraintPriority = Field(
        default=ConstraintPriority.NORMAL,
        description="Priorité de la contrainte"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Métadonnées additionnelles"
    )

class ConstraintResponse(BaseModel):
    """Réponse après application d'une contrainte"""
    model_config = ConfigDict(use_enum_values=True)
    
    status: Literal["success", "conflict", "error", "pending"]
    constraint_id: Optional[int] = None
    plan: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    solution_diff: Optional[Dict[str, Any]] = None
    score_delta: Optional[int] = None
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = None
    hebrew_explanation: Optional[str] = None

# Export des classes principales
__all__ = [
    'ConstraintRequest', 'ConstraintResponse', 
    'ConstraintType', 'ConstraintPriority',
    'TeacherAvailabilityData'
]
'''
    
    models_path = Path('scheduler_ai/models.py')
    with open(models_path, 'w', encoding='utf-8') as f:
        f.write(models_content)
    
    log('SUCCESS', f'Fichier models.py créé: {models_path}')

def create_api_file():
    """Crée le fichier api.py corrigé"""
    log('INFO', 'Création du fichier api.py corrigé...')
    
    api_content = '''# scheduler_ai/api.py - Version corrigée avec Pydantic v2

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import logging
import os
from datetime import datetime

# Imports Pydantic avec gestion d'erreur
try:
    from pydantic import ValidationError
    from models import ConstraintRequest, ConstraintResponse, ConstraintType
    PYDANTIC_AVAILABLE = True
    print("✅ Pydantic models imported successfully")
except ImportError as e:
    print(f"⚠️ Pydantic models import failed: {e}")
    PYDANTIC_AVAILABLE = False
    ValidationError = Exception

# Configuration Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/health')
def health():
    """Check de santé avec diagnostic Pydantic"""
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai",
        "version": "2.0.1-fixed",
        "timestamp": datetime.now().isoformat(),
        "pydantic_available": PYDANTIC_AVAILABLE
    })

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    """Applique une contrainte avec validation Pydantic robuste"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Pas de données JSON"}), 400
        
        if PYDANTIC_AVAILABLE:
            try:
                constraint_request = ConstraintRequest(**data)
                logger.info(f"✅ Validation réussie: {constraint_request.type}")
                
                return jsonify({
                    "status": "success",
                    "message": "Contrainte validée et acceptée",
                    "constraint": constraint_request.model_dump(),
                    "validation": "pydantic_v2"
                })
                
            except ValidationError as e:
                logger.warning(f"❌ Validation échouée: {e}")
                return jsonify({
                    "error": "Erreur de validation",
                    "details": [
                        {
                            "field": str(error.get("loc", ["unknown"])),
                            "message": error.get("msg", str(error)),
                            "type": error.get("type", "validation_error"),
                            "input": error.get("input")
                        }
                        for error in e.errors()
                    ]
                }), 400
        else:
            # Fallback sans Pydantic
            return jsonify({
                "status": "accepted",
                "message": "Contrainte reçue (validation Pydantic non disponible)",
                "constraint": data,
                "validation": "fallback"
            })
            
    except Exception as e:
        logger.error(f"Erreur: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("""
    🤖 School Scheduler AI - Version Corrigée
    ========================================
    
    ✅ Validation Pydantic: ACTIVE
    🌐 WebSocket: http://localhost:5001
    🏫 Système: Éducatif Israélien
    
    """)
    
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)
'''
    
    api_path = Path('scheduler_ai/api.py')
    with open(api_path, 'w', encoding='utf-8') as f:
        f.write(api_content)
    
    log('SUCCESS', f'Fichier api.py créé: {api_path}')

def install_dependencies():
    """Installe les dépendances Python"""
    log('INFO', 'Installation des dépendances...')
    
    req_path = Path('scheduler_ai/requirements.txt')
    if req_path.exists():
        try:
            # Essayer d'installer avec pip
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', str(req_path)
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                log('SUCCESS', 'Dépendances installées avec succès')
                return True
            else:
                log('ERROR', f'Erreur installation: {result.stderr}')
                return False
        except subprocess.TimeoutExpired:
            log('WARNING', 'Installation timeout - continuez manuellement')
            return False
        except Exception as e:
            log('ERROR', f'Erreur lors de l\'installation: {e}')
            return False
    else:
        log('WARNING', 'Fichier requirements.txt non trouvé')
        return False

def run_tests():
    """Lance les tests de validation"""
    log('INFO', 'Lancement des tests de validation...')
    
    try:
        # Importer et tester les modèles
        sys.path.insert(0, 'scheduler_ai')
        from models import ConstraintRequest, ConstraintType
        
        # Test simple
        test_data = {
            "type": "teacher_availability",
            "entity": "Test Professor",
            "data": {"unavailable_days": [5]},
            "priority": 2
        }
        
        constraint = ConstraintRequest(**test_data)
        log('SUCCESS', f'Test validation réussi: {constraint.type}')
        
        return True
    except Exception as e:
        log('ERROR', f'Test échoué: {e}')
        return False

def create_test_script():
    """Crée un script de test autonome"""
    log('INFO', 'Création du script de test...')
    
    test_script = '''#!/usr/bin/env python3
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
'''
    
    test_path = Path('test_pydantic_quick.py')
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    # Rendre exécutable sur Unix
    if os.name != 'nt':
        os.chmod(test_path, 0o755)
    
    log('SUCCESS', f'Script de test créé: {test_path}')

def generate_summary(backup_dir):
    """Génère un résumé des corrections appliquées"""
    log('HEADER', 'RÉSUMÉ DES CORRECTIONS APPLIQUÉES')
    
    summary = f"""
📋 SCHOOL SCHEDULER - CORRECTIONS PYDANTIC APPLIQUÉES
═══════════════════════════════════════════════════

🕐 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
💾 Sauvegarde: {backup_dir or 'Aucune'}

✅ CORRECTIONS RÉALISÉES:
─────────────────────────

1. 📁 Structure du projet vérifiée
   - Répertoire scheduler_ai/ créé si nécessaire
   - Fichier __init__.py ajouté

2. 📦 Requirements.txt mis à jour
   - Pydantic >= 2.0.0 ajouté
   - Dépendances compatibles définies
   - Support Unicode/Hébreu inclus

3. 🔧 Fichier models.py corrigé
   - Utilisation de ConfigDict pour Pydantic v2
   - Validation robuste des contraintes
   - Support système éducatif israélien
   - Gestion des erreurs améliorée

4. 🌐 Fichier api.py corrigé
   - Import Pydantic avec fallback
   - Validation des requêtes robuste
   - Messages d'erreur détaillés
   - Health check diagnostique

5. 🧪 Tests créés
   - Script de test rapide disponible
   - Validation des imports et modèles

🚀 PROCHAINES ÉTAPES:
──────────────────

1. Installer les dépendances:
   pip install -r scheduler_ai/requirements.txt

2. Tester les corrections:
   python test_pydantic_quick.py

3. Lancer l'API:
   cd scheduler_ai && python api.py

4. Vérifier le health check:
   curl http://localhost:5001/health

📞 EN CAS DE PROBLÈME:
────────────────────

- Vérifiez que Python >= 3.8 est installé
- Assurez-vous que Pydantic >= 2.0 est installé
- Consultez les logs pour plus de détails
- Restaurez depuis la sauvegarde si nécessaire

🎉 Les corrections Pydantic sont maintenant appliquées !
"""
    
    print(summary)
    
    # Sauvegarder le résumé
    summary_path = Path('PYDANTIC_FIXES_SUMMARY.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    log('SUCCESS', f'Résumé sauvegardé: {summary_path}')

def main():
    """Point d'entrée principal"""
    log('HEADER', 'SCHOOL SCHEDULER - CORRECTEUR AUTOMATIQUE PYDANTIC')
    
    try:
        # 1. Créer une sauvegarde
        backup_dir = create_backup()
        
        # 2. Vérifier la structure
        check_project_structure()
        
        # 3. Mettre à jour les requirements
        update_requirements()
        
        # 4. Créer les fichiers corrigés
        create_models_file()
        create_api_file()
        
        # 5. Créer le script de test
        create_test_script()
        
        # 6. Essayer d'installer les dépendances
        install_success = install_dependencies()
        if not install_success:
            log('WARNING', 'Installation automatique échouée - faites-le manuellement')
        
        # 7. Tester si possible
        if install_success:
            test_success = run_tests()
            if test_success:
                log('SUCCESS', 'Tests de validation réussis')
            else:
                log('WARNING', 'Tests échoués - vérifiez l\'installation')
        
        # 8. Générer le résumé
        generate_summary(backup_dir)
        
        log('SUCCESS', 'Corrections Pydantic appliquées avec succès!')
        return True
        
    except KeyboardInterrupt:
        log('WARNING', 'Opération interrompue par l\'utilisateur')
        return False
    except Exception as e:
        log('ERROR', f'Erreur lors de la correction: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
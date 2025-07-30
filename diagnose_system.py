#!/usr/bin/env python3
"""
diagnose_system.py - Diagnostic automatique du système School Scheduler
"""
import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from datetime import datetime

class SystemDiagnostic:
    def __init__(self):
        self.issues = []
        self.fixes = []
        self.base_dir = Path.cwd()
        
    def log(self, level, message):
        symbols = {"✅": "OK", "❌": "ERROR", "⚠️": "WARNING", "📝": "INFO"}
        print(f"{symbols.get(level, level)} {message}")
    
    def check_python_version(self):
        """Vérifie la version Python"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            self.log("✅", f"Python {version.major}.{version.minor} OK")
        else:
            self.issues.append("Version Python < 3.8")
            self.fixes.append("Installer Python 3.8 ou supérieur")
    
    def check_required_files(self):
        """Vérifie la présence des fichiers essentiels"""
        required_files = [
            "solver/main.py",
            "scheduler_ai/agent.py",
            "scheduler_ai/parsers.py",
            "ai_agent_native.py"
        ]
        
        for file in required_files:
            if (self.base_dir / file).exists():
                self.log("✅", f"Fichier {file} trouvé")
            else:
                self.issues.append(f"Fichier manquant: {file}")
                self.fixes.append(f"Créer le fichier {file}")
    
    def check_solver_engine(self):
        """Vérifie solver_engine.py"""
        solver_engine_path = self.base_dir / "solver_engine.py"
        
        if not solver_engine_path.exists():
            self.issues.append("solver_engine.py manquant")
            self.fixes.append("Créer solver_engine.py (voir le code fourni)")
            
            # Créer automatiquement le fichier
            self.create_solver_engine()
        else:
            self.log("✅", "solver_engine.py existe")
    
    def create_solver_engine(self):
        """Crée le fichier solver_engine.py manquant"""
        content = '''#!/usr/bin/env python3
"""
solver_engine.py - Interface entre l'agent AI et le solver OR-Tools
Auto-généré par le diagnostic
"""
import sys
import os
from typing import Dict, List, Any

class ScheduleSolver:
    """Stub pour le solver - À remplacer par l'implémentation réelle"""
    
    def __init__(self):
        self.constraints = []
        self.schedule = []
        
    def apply_constraint(self, constraint: Dict) -> Dict:
        """Applique une contrainte"""
        self.constraints.append(constraint)
        return {
            "success": True,
            "constraint_id": len(self.constraints),
            "message": "Contrainte ajoutée (mode stub)"
        }
    
    def get_current_schedule(self) -> List[Dict]:
        """Retourne l'emploi du temps actuel"""
        # Stub - retourne un emploi du temps vide
        return self.schedule
    
    def solve(self, time_limit: int = 30) -> Dict:
        """Lance la résolution"""
        return {
            "status": "stub",
            "message": "Solver en mode stub - implémentation réelle requise",
            "schedule": []
        }
'''
        
        with open("solver_engine.py", "w", encoding="utf-8") as f:
            f.write(content)
        self.log("📝", "Créé solver_engine.py (version stub)")
    
    def check_dependencies(self):
        """Vérifie les dépendances Python"""
        required_packages = [
            "flask",
            "flask-socketio",
            "psycopg2-binary",
            "sqlalchemy",
            "ortools",
            "pandas",
            "openpyxl"
        ]
        
        missing = []
        for package in required_packages:
            spec = importlib.util.find_spec(package.replace("-", "_"))
            if spec is None:
                missing.append(package)
            else:
                self.log("✅", f"Package {package} installé")
        
        if missing:
            self.issues.append(f"Packages manquants: {', '.join(missing)}")
            self.fixes.append(f"pip install {' '.join(missing)}")
    
    def check_database(self):
        """Vérifie la connexion à la base de données"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="school_scheduler",
                user="postgres",
                password="postgres",
                connect_timeout=5
            )
            conn.close()
            self.log("✅", "Connexion PostgreSQL OK")
        except ImportError:
            self.issues.append("psycopg2 non installé")
            self.fixes.append("pip install psycopg2-binary")
        except Exception as e:
            self.issues.append(f"Erreur base de données: {str(e)}")
            self.fixes.append("Vérifier que PostgreSQL est lancé et que la base 'school_scheduler' existe")
    
    def check_ports(self):
        """Vérifie les ports utilisés"""
        ports = {
            5001: "Agent AI",
            8000: "Solver API",
            3000: "Frontend",
            5432: "PostgreSQL"
        }
        
        for port, service in ports.items():
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    self.log("✅", f"Port {port} ({service}) accessible")
                else:
                    self.log("⚠️", f"Port {port} ({service}) non accessible")
            except:
                self.log("❌", f"Erreur test port {port}")
    
    def check_parsers_module(self):
        """Vérifie et crée le module parsers si nécessaire"""
        parsers_path = self.base_dir / "scheduler_ai" / "parsers.py"
        
        if not parsers_path.exists():
            self.issues.append("scheduler_ai/parsers.py manquant")
            self.create_parsers_module()
        else:
            self.log("✅", "Module parsers.py existe")
    
    def create_parsers_module(self):
        """Crée le module parsers.py"""
        os.makedirs("scheduler_ai", exist_ok=True)
        
        content = '''#!/usr/bin/env python3
"""
parsers.py - Parseur de langage naturel pour les contraintes
Auto-généré par le diagnostic
"""
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class NaturalLanguageParser:
    """Parse les contraintes en langage naturel"""
    
    def __init__(self):
        self.days_map = {
            "lundi": 1, "mardi": 2, "mercredi": 3, 
            "jeudi": 4, "vendredi": 5, "dimanche": 0,
            "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "sunday": 0
        }
    
    def parse(self, text: str, language: str = "fr") -> Dict:
        """Parse une contrainte en langage naturel"""
        text = text.lower().strip()
        
        # Détection du type de contrainte
        if "ne peut pas" in text or "unavailable" in text:
            return self._parse_availability_constraint(text)
        elif "préfère" in text or "prefers" in text:
            return self._parse_preference_constraint(text)
        elif "maximum" in text or "pas plus de" in text:
            return self._parse_limit_constraint(text)
        else:
            return {
                "success": False,
                "error": "Type de contrainte non reconnu",
                "original_text": text
            }
    
    def _parse_availability_constraint(self, text: str) -> Dict:
        """Parse une contrainte de disponibilité"""
        # Extraction du professeur
        teacher_match = re.search(r"professeur\\s+(\\w+)", text)
        teacher = teacher_match.group(1) if teacher_match else None
        
        # Extraction du jour
        day = None
        for day_name, day_num in self.days_map.items():
            if day_name in text:
                day = day_num
                break
        
        if teacher and day is not None:
            return {
                "success": True,
                "parsed_constraint": {
                    "type": "teacher_availability",
                    "constraint": {
                        "teacher": teacher.capitalize(),
                        "day": day,
                        "available": False
                    }
                },
                "confidence": 0.9
            }
        
        return {
            "success": False,
            "error": "Impossible d'extraire les informations",
            "original_text": text
        }
    
    def _parse_preference_constraint(self, text: str) -> Dict:
        """Parse une contrainte de préférence"""
        # Stub - à implémenter
        return {
            "success": False,
            "error": "Parsing des préférences non implémenté",
            "original_text": text
        }
    
    def _parse_limit_constraint(self, text: str) -> Dict:
        """Parse une contrainte de limite"""
        # Stub - à implémenter
        return {
            "success": False,
            "error": "Parsing des limites non implémenté",
            "original_text": text
        }
'''
        
        with open("scheduler_ai/parsers.py", "w", encoding="utf-8") as f:
            f.write(content)
        
        # Créer __init__.py
        with open("scheduler_ai/__init__.py", "w") as f:
            f.write("")
        
        self.log("📝", "Créé scheduler_ai/parsers.py (version de base)")
    
    def generate_report(self):
        """Génère le rapport de diagnostic"""
        print("\n" + "="*60)
        print("📊 RAPPORT DE DIAGNOSTIC")
        print("="*60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Répertoire: {self.base_dir}")
        
        if not self.issues:
            print("\n✅ Aucun problème détecté!")
        else:
            print(f"\n❌ {len(self.issues)} problèmes trouvés:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
            
            print(f"\n🔧 Solutions proposées:")
            for i, fix in enumerate(self.fixes, 1):
                print(f"  {i}. {fix}")
        
        # Script de correction automatique
        if self.fixes:
            self.create_fix_script()
    
    def create_fix_script(self):
        """Crée un script pour appliquer les corrections"""
        script_content = """#!/bin/bash
# Script de correction automatique généré
echo "🔧 Application des corrections..."

"""
        
        for fix in self.fixes:
            if fix.startswith("pip install"):
                script_content += f"{fix}\n"
            elif fix.startswith("Créer"):
                script_content += f"# TODO: {fix}\n"
            else:
                script_content += f"echo 'Action manuelle requise: {fix}'\n"
        
        with open("apply_fixes.sh", "w") as f:
            f.write(script_content)
        os.chmod("apply_fixes.sh", 0o755)
        
        print("\n📝 Script de correction créé: ./apply_fixes.sh")
    
    def run(self):
        """Lance le diagnostic complet"""
        print("🔍 Diagnostic du système School Scheduler\n")
        
        self.check_python_version()
        self.check_required_files()
        self.check_solver_engine()
        self.check_parsers_module()
        self.check_dependencies()
        self.check_database()
        self.check_ports()
        
        self.generate_report()

if __name__ == "__main__":
    diagnostic = SystemDiagnostic()
    diagnostic.run()
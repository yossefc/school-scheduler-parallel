#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de verification du systeme School Scheduler
Version securisee sans caracteres speciaux
"""
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging
from datetime import datetime
import asyncio
from typing import Dict, List, Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration de la base de donnees
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "school_scheduler"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "school123")
}

class SchedulerVerifier:
    """Classe pour verifier l'etat du systeme"""
    
    def __init__(self):
        self.results = {
            "encodage": None,
            "database": None,
            "solver": None,
            "agent": None,
            "constraints": None,
            "api": None
        }
        self.errors = []
        
    def check_encoding(self) -> bool:
        """Verifie l'encodage des fichiers Python"""
        logger.info("[ENCODAGE] Verification de l'encodage...")
        
        problematic_files = []
        files_to_check = [
            "solver/solver_engine.py",
            "scheduler_ai/agent.py",
            "scheduler_ai/api.py"
        ]
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Chercher les caracteres problematiques
                        bad_chars = ['?', '\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
                        for char in bad_chars:
                            if char in content:
                                problematic_files.append(file_path)
                                break
                except Exception as e:
                    self.errors.append(f"Erreur lecture {file_path}: {e}")
                    problematic_files.append(file_path)
        
        if problematic_files:
            self.results["encodage"] = "[X] Problemes d'encodage detectes"
            self.errors.append(f"Fichiers avec encodage incorrect: {problematic_files}")
            return False
        else:
            self.results["encodage"] = "[OK] Encodage correct"
            return True
    
    def check_database(self) -> bool:
        """Verifie la connexion et la structure de la base de donnees"""
        logger.info("[DATABASE] Verification de la base de donnees...")
        
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            # Verifier les tables essentielles
            tables = ['teachers', 'classes', 'subjects', 'time_slots', 'constraints']
            missing_tables = []
            
            for table in tables:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table,))
                
                if not cur.fetchone()[0]:
                    missing_tables.append(table)
            
            # Verifier quelques donnees
            cur.execute("SELECT COUNT(*) FROM teachers WHERE is_active = true")
            teacher_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM classes WHERE is_active = true")
            class_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM time_slots WHERE is_active = true")
            slot_count = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            if missing_tables:
                self.results["database"] = "[X] Tables manquantes"
                self.errors.append(f"Tables manquantes: {missing_tables}")
                return False
            elif teacher_count == 0 or class_count == 0 or slot_count == 0:
                self.results["database"] = "[!] Base de donnees vide"
                self.errors.append(f"Donnees: {teacher_count} profs, {class_count} classes, {slot_count} creneaux")
                return False
            else:
                self.results["database"] = f"[OK] DB OK ({teacher_count} profs, {class_count} classes)"
                return True
                
        except Exception as e:
            self.results["database"] = "[X] Erreur de connexion"
            self.errors.append(f"Erreur DB: {str(e)}")
            return False
    
    def check_solver(self) -> bool:
        """Verifie que le solver fonctionne"""
        logger.info("[SOLVER] Verification du solver...")
        
        try:
            # Import dynamique pour eviter les erreurs si le module n'existe pas
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from solver.solver_engine import ScheduleSolver
            
            # Test basique
            solver = ScheduleSolver(DB_CONFIG)
            solver.load_data_from_db()
            
            # Verifier que les donnees sont chargees
            if not solver.teachers or not solver.classes:
                self.results["solver"] = "[!] Solver sans donnees"
                return False
            
            # Test rapide de resolution (5 secondes max)
            logger.info("Test de resolution rapide...")
            solution = solver.solve(time_limit=5)
            
            if solution:
                self.results["solver"] = f"[OK] Solver OK ({len(solution)} assignations)"
                return True
            else:
                self.results["solver"] = "[!] Pas de solution trouvee"
                return False
                
        except ImportError as e:
            self.results["solver"] = "[X] Module solver introuvable"
            self.errors.append(f"Import error: {e}")
            return False
        except Exception as e:
            self.results["solver"] = "[X] Erreur solver"
            self.errors.append(f"Erreur solver: {str(e)}")
            return False
    
    def check_agent(self) -> bool:
        """Verifie que l'agent AI fonctionne"""
        logger.info("[AGENT] Verification de l'agent AI...")
        
        try:
            from scheduler_ai.agent import ScheduleAIAgent
            
            agent = ScheduleAIAgent(DB_CONFIG)
            
            # Verifier les contraintes institutionnelles
            if not agent.institutional_constraints:
                self.results["agent"] = "[!] Pas de contraintes institutionnelles"
                return False
            
            # Test de resolution de nom
            result = agent._resolve_teacher_name("test")
            
            if "error" in result or "success" in result:
                self.results["agent"] = f"[OK] Agent OK ({len(agent.institutional_constraints)} contraintes)"
                return True
            else:
                self.results["agent"] = "[!] Agent comportement inattendu"
                return False
                
        except ImportError as e:
            self.results["agent"] = "[X] Module agent introuvable"
            self.errors.append(f"Import error: {e}")
            return False
        except Exception as e:
            self.results["agent"] = "[X] Erreur agent"
            self.errors.append(f"Erreur agent: {str(e)}")
            return False
    
    async def check_constraints_async(self) -> bool:
        """Verifie l'application des contraintes (async)"""
        logger.info("[CONTRAINTES] Verification des contraintes...")
        
        try:
            from scheduler_ai.agent import ScheduleAIAgent
            
            agent = ScheduleAIAgent(DB_CONFIG)
            
            # Test avec une contrainte simple
            test_constraint = {
                "type": "teacher_availability",
                "entity": "Test Teacher",
                "data": {"unavailable_days": [5]},
                "priority": 3
            }
            
            # Simulation seulement (pas d'application reelle)
            analysis = await agent._analyze_constraint(test_constraint)
            
            if isinstance(analysis, dict):
                self.results["constraints"] = "[OK] Systeme de contraintes OK"
                return True
            else:
                self.results["constraints"] = "[!] Analyse contraintes incorrecte"
                return False
                
        except Exception as e:
            self.results["constraints"] = "[X] Erreur contraintes"
            self.errors.append(f"Erreur contraintes: {str(e)}")
            return False
    
    def check_api(self) -> bool:
        """Verifie que l'API Flask est importable"""
        logger.info("[API] Verification de l'API...")
        
        try:
            from scheduler_ai.api import app
            
            # Verifier les routes principales
            routes = [rule.rule for rule in app.url_map.iter_rules()]
            essential_routes = ['/health', '/api/ai/constraints']
            
            missing_routes = [r for r in essential_routes if r not in routes]
            
            if missing_routes:
                self.results["api"] = "[!] Routes manquantes"
                self.errors.append(f"Routes manquantes: {missing_routes}")
                return False
            else:
                self.results["api"] = f"[OK] API OK ({len(routes)} routes)"
                return True
                
        except ImportError as e:
            self.results["api"] = "[X] Module API introuvable"
            self.errors.append(f"Import error: {e}")
            return False
        except Exception as e:
            self.results["api"] = "[X] Erreur API"
            self.errors.append(f"Erreur API: {str(e)}")
            return False
    
    def generate_report(self) -> str:
        """Genere un rapport de verification"""
        report = """
================================================================
           RAPPORT DE VERIFICATION - SCHOOL SCHEDULER
================================================================

Date: {}

Resultats des verifications:
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        for component, status in self.results.items():
            if status:
                report += f"\n  * {component.upper()}: {status}"
        
        if self.errors:
            report += "\n\n[X] Erreurs detectees:\n"
            for i, error in enumerate(self.errors, 1):
                report += f"\n  {i}. {error}"
        
        # Score global
        success_count = sum(1 for v in self.results.values() if v and "[OK]" in v)
        total_count = len(self.results)
        score = (success_count / total_count) * 100
        
        report += f"\n\nScore global: {score:.0f}% ({success_count}/{total_count} composants OK)"
        
        if score == 100:
            report += "\n\n==> Systeme completement operationnel!"
        elif score >= 80:
            report += "\n\n==> Systeme fonctionnel avec quelques avertissements"
        elif score >= 50:
            report += "\n\n==> Systeme partiellement fonctionnel"
        else:
            report += "\n\n==> Systeme necessite des corrections importantes"
        
        report += "\n\n" + "="*60 + "\n"
        
        return report

async def main():
    """Fonction principale"""
    verifier = SchedulerVerifier()
    
    # Executer les verifications
    logger.info("Demarrage de la verification du systeme...")
    
    verifier.check_encoding()
    verifier.check_database()
    verifier.check_solver()
    verifier.check_agent()
    await verifier.check_constraints_async()
    verifier.check_api()
    
    # Generer et afficher le rapport
    report = verifier.generate_report()
    print(report)
    
    # Sauvegarder le rapport
    report_file = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"Rapport sauvegarde dans: {report_file}")
    
    # Code de sortie base sur le score
    success_count = sum(1 for v in verifier.results.values() if v and "[OK]" in v)
    if success_count == len(verifier.results):
        sys.exit(0)  # Tout est OK
    elif success_count >= 4:
        sys.exit(1)  # Quelques problemes mineurs
    else:
        sys.exit(2)  # Problemes majeurs

if __name__ == "__main__":
    asyncio.run(main())
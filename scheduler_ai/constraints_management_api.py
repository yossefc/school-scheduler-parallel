"""
API Flask pour la gestion des contraintes avec interface web
À ajouter dans scheduler_ai/api.py ou créer un fichier séparé
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# Configuration DB (ajustez selon votre config)
DB_CONFIG = {
    "host": "localhost",
    "database": "school_scheduler", 
    "user": "admin",
    "password": "school123"
}

class ConstraintsManager:
    def __init__(self, db_config):
        self.db_config = db_config
    
    def get_all_constraints(self):
        """Récupère toutes les contraintes avec leurs détails"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Contraintes institutionnelles
            cur.execute("""
                SELECT 
                    id,
                    name,
                    type,
                    priority,
                    entity,
                    data,
                    description,
                    is_active,
                    applicable_days
                FROM institutional_constraints
                ORDER BY priority ASC, name ASC
            """)
            institutional = [dict(row) for row in cur.fetchall()]
            
            # Contraintes utilisateur
            cur.execute("""
                SELECT 
                    constraint_id,
                    constraint_type,
                    priority,
                    entity_type,
                    entity_name,
                    constraint_data,
                    is_active,
                    created_at,
                    updated_at
                FROM constraints
                ORDER BY priority ASC, created_at DESC
            """)
            user_constraints = [dict(row) for row in cur.fetchall()]
            
            # Statistiques
            total_active = len([c for c in institutional if c['is_active']]) + \
                          len([c for c in user_constraints if c['is_active']])
                          
            return {
                "institutional": institutional,
                "user": user_constraints,
                "total_active": total_active,
                "stats": {
                    "total_institutional": len(institutional),
                    "total_user": len(user_constraints),
                    "hard_constraints": len([c for c in institutional + user_constraints 
                                           if c.get('priority', 0) == 0 and c.get('is_active', False)])
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur get_all_constraints: {e}")
            return {"institutional": [], "user": [], "total_active": 0, "stats": {}}
        finally:
            cur.close()
            conn.close()
    
    def toggle_constraint(self, constraint_type, constraint_id, active):
        """Active/désactive une contrainte"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            if constraint_type == "institutional":
                cur.execute("""
                    UPDATE institutional_constraints 
                    SET is_active = %s, updated_at = NOW()
                    WHERE id = %s
                """, (active, constraint_id))
            else:  # user constraint
                cur.execute("""
                    UPDATE constraints 
                    SET is_active = %s, updated_at = NOW()
                    WHERE constraint_id = %s
                """, (active, constraint_id))
            
            conn.commit()
            
            # Log l'action
            logger.info(f"Contrainte {constraint_type}:{constraint_id} {'activée' if active else 'désactivée'}")
            
            return {"success": True}
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur toggle_constraint: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cur.close()
            conn.close()
    
    def delete_constraint(self, constraint_type, constraint_id):
        """Supprime une contrainte (sauf les critiques)"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            if constraint_type == "institutional":
                # Vérifier que ce n'est pas une contrainte critique
                cur.execute("SELECT priority FROM institutional_constraints WHERE id = %s", (constraint_id,))
                result = cur.fetchone()
                if result and result[0] == 0:
                    return {"success": False, "error": "Impossible de supprimer une contrainte critique"}
                
                cur.execute("DELETE FROM institutional_constraints WHERE id = %s", (constraint_id,))
            else:
                cur.execute("DELETE FROM constraints WHERE constraint_id = %s", (constraint_id,))
            
            conn.commit()
            logger.info(f"Contrainte {constraint_type}:{constraint_id} supprimée")
            
            return {"success": True}
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur delete_constraint: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cur.close()
            conn.close()
    
    def reset_all_constraints(self):
        """Reset toutes les contraintes (garde seulement les critiques)"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Backup d'abord
            cur.execute("""
                CREATE TABLE IF NOT EXISTS constraints_backup_""" + str(int(time.time())) + """ AS 
                SELECT *, NOW() as backup_date FROM constraints WHERE is_active = true
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS institutional_constraints_backup_""" + str(int(time.time())) + """ AS 
                SELECT *, NOW() as backup_date FROM institutional_constraints WHERE is_active = true
            """)
            
            # Désactiver toutes les contraintes non-critiques
            cur.execute("UPDATE constraints SET is_active = false")
            cur.execute("UPDATE institutional_constraints SET is_active = false WHERE priority > 0")
            
            # Garder seulement les contraintes système critiques
            cur.execute("""
                INSERT INTO institutional_constraints 
                (name, type, priority, entity, data, description, is_active, applicable_days) 
                VALUES 
                ('Horaires d''ouverture école', 'school_hours', 0, 'school',
                 '{"start": "08:00", "end": "18:00", "mandatory": true}',
                 'École ouverte de 8h à 18h - NON MODIFIABLE', true, ARRAY[0,1,2,3,4,5]),
                ('Vendredi écourté', 'friday_short', 0, 'all',
                 '{"end_time": "13:00", "last_period": 6}',
                 'Vendredi se termine à 13h - NON MODIFIABLE', true, ARRAY[5])
                ON CONFLICT (name) DO UPDATE SET is_active = true
            """)
            
            conn.commit()
            logger.info("Reset des contraintes effectué")
            
            return {"success": True, "message": "Contraintes réinitialisées avec succès"}
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur reset_all_constraints: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cur.close()
            conn.close()
    
    def disable_soft_constraints(self):
        """Désactive toutes les contraintes non-critiques (priorité > 0)"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            cur.execute("UPDATE institutional_constraints SET is_active = false WHERE priority > 0")
            cur.execute("UPDATE constraints SET is_active = false WHERE priority > 0")
            
            conn.commit()
            logger.info("Contraintes non-critiques désactivées")
            
            return {"success": True, "message": "Contraintes non-critiques désactivées"}
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur disable_soft_constraints: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cur.close()
            conn.close()
    
    def add_constraint(self, constraint_data):
        """Ajoute une nouvelle contrainte utilisateur"""
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        try:
            # Parsing simple du texte en contrainte structurée
            parsed = self._parse_natural_language(constraint_data)
            
            cur.execute("""
                INSERT INTO constraints 
                (constraint_type, priority, entity_type, entity_name, constraint_data, 
                 is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING constraint_id
            """, (
                parsed["type"],
                parsed["priority"], 
                parsed["entity_type"],
                parsed["entity_name"],
                json.dumps(parsed["data"]),
                True
            ))
            
            constraint_id = cur.fetchone()[0]
            conn.commit()
            
            logger.info(f"Nouvelle contrainte ajoutée: {constraint_id}")
            
            return {
                "success": True, 
                "constraint_id": constraint_id,
                "parsed": parsed
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur add_constraint: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cur.close()
            conn.close()
    
    def _parse_natural_language(self, constraint_data):
        """Parsing simple du langage naturel (version basique)"""
        text = constraint_data.get("text", "").lower()
        
        # Détection du type
        if "disponible" in text or "indisponible" in text:
            constraint_type = "teacher_availability"
            entity_type = "teacher"
        elif "classe" in text:
            constraint_type = "class_constraint"
            entity_type = "class"
        elif "matière" in text or "cours" in text:
            constraint_type = "subject_timing"  
            entity_type = "subject"
        else:
            constraint_type = constraint_data.get("type", "custom")
            entity_type = "custom"
        
        # Extraction de l'entité
        entity_name = constraint_data.get("entity", "").strip()
        if not entity_name:
            # Tentative d'extraction automatique (très basique)
            words = text.split()
            for i, word in enumerate(words):
                if word in ["professeur", "prof", "enseignant"] and i + 1 < len(words):
                    entity_name = words[i + 1]
                    break
                elif word in ["classe"] and i + 1 < len(words):
                    entity_name = words[i + 1]
                    break
        
        # Données spécifiques selon le type
        data = {"original_text": text}
        
        if "vendredi" in text:
            data["day"] = 5
            data["restriction"] = "unavailable" if "pas" in text or "indisponible" in text else "limited"
        
        if "matin" in text:
            data["time_preference"] = "morning"
        elif "après-midi" in text:
            data["time_preference"] = "afternoon"
        
        return {
            "type": constraint_type,
            "entity_type": entity_type,
            "entity_name": entity_name or "unknown",
            "priority": constraint_data.get("priority", 2),
            "data": data
        }
    
    def test_solver(self):
        """Test rapide du solver avec les contraintes actuelles"""
        try:
            # Import du solver
            from solver_engine import ScheduleSolver
            
            solver = ScheduleSolver()
            start_time = time.time()
            
            # Test avec limite de temps courte
            result = solver.solve(time_limit=10)
            
            end_time = time.time()
            
            if result:
                return {
                    "success": True,
                    "time": round(end_time - start_time, 2),
                    "message": "Solution trouvée!"
                }
            else:
                return {
                    "success": False,
                    "time": round(end_time - start_time, 2),
                    "error": "Aucune solution trouvée - contraintes incompatibles"
                }
                
        except Exception as e:
            logger.error(f"Erreur test_solver: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Instance globale
constraints_manager = ConstraintsManager(DB_CONFIG)

# Routes Flask (à ajouter dans votre api.py existante)
def add_constraints_routes(app):
    """Ajoute les routes de gestion des contraintes à l'app Flask"""
    
    @app.route('/constraints-manager')
    def constraints_interface():
        """Sert l'interface de gestion des contraintes"""
        with open('constraints_manager.html', 'r', encoding='utf-8') as f:
            return f.read()
    
    @app.route('/api/constraints/list', methods=['GET'])
    def list_constraints():
        """Liste toutes les contraintes"""
        result = constraints_manager.get_all_constraints()
        return jsonify(result)
    
    @app.route('/api/constraints/toggle', methods=['POST'])
    def toggle_constraint():
        """Active/désactive une contrainte"""
        data = request.get_json()
        result = constraints_manager.toggle_constraint(
            data['type'], 
            data['id'], 
            data['active']
        )
        return jsonify(result)
    
    @app.route('/api/constraints/delete', methods=['DELETE'])  
    def delete_constraint():
        """Supprime une contrainte"""
        data = request.get_json()
        result = constraints_manager.delete_constraint(
            data['type'],
            data['id']
        )
        return jsonify(result)
    
    @app.route('/api/constraints/reset', methods=['POST'])
    def reset_constraints():
        """Reset toutes les contraintes"""
        result = constraints_manager.reset_all_constraints()
        return jsonify(result)
    
    @app.route('/api/constraints/disable-soft', methods=['POST'])
    def disable_soft_constraints():
        """Désactive les contraintes non-critiques"""
        result = constraints_manager.disable_soft_constraints()
        return jsonify(result)
    
    @app.route('/api/constraints/add', methods=['POST'])
    def add_constraint():
        """Ajoute une nouvelle contrainte"""
        data = request.get_json()
        result = constraints_manager.add_constraint(data)
        return jsonify(result)
    
    @app.route('/api/solver/test', methods=['POST'])
    def test_solver():
        """Test le solver avec les contraintes actuelles"""
        result = constraints_manager.test_solver()
        return jsonify(result)

# Si exécuté directement (pour test)
if __name__ == '__main__':
    app = Flask(__name__)
    CORS(app)
    
    add_constraints_routes(app)
    
    print("🎯 Gestionnaire de contraintes démarré!")
    print("Interface: http://localhost:5001/constraints-manager")
    print("API: http://localhost:5001/api/constraints/list")
    
    app.run(host='0.0.0.0', port=5002, debug=True)
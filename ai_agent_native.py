"""
Agent IA School Scheduler - Version Python Native
Compatible avec toutes les fonctionnalités du système
"""
import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration DB
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "school_scheduler"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "school123"),
    "port": os.environ.get("DB_PORT", "5432")
}

# Sessions actives
active_sessions = {}

# ==== PARSEUR DE CONTRAINTES ====

class ConstraintParser:
    def __init__(self):
        self.patterns = {
            "teacher_availability": [
                r"(?:le\s+)?professeur\s+(\w+)\s+(?:ne\s+peut\s+pas|n'est\s+pas\s+disponible|pas\s+disponible)\s+(?:le\s+)?(\w+)",
                r"(\w+)\s+(?:ne\s+peut\s+pas|pas\s+disponible)\s+(?:le\s+)?(\w+)",
            ],
            "time_preference": [
                r"(?:les\s+cours\s+de\s+)?(\w+)\s+(?:doivent\s+être|uniquement|seulement)\s+(?:le\s+)?(\w+)",
                r"(\w+)\s+(?:en\s+)?(\w+)\s+(?:seulement|uniquement)",
            ],
            "consecutive_limit": [
                r"(?:maximum|max)\s+(\d+)\s+heures?\s+(?:consécutives|de\s+suite)",
                r"pas\s+plus\s+de\s+(\d+)\s+heures?\s+(?:d'affilée|consécutives)",
            ]
        }
        
        self.days_map = {
            "lundi": 1, "mardi": 2, "mercredi": 3, 
            "jeudi": 4, "vendredi": 5, "dimanche": 0,
            "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "sunday": 0
        }
        
        self.time_map = {
            "matin": "morning", "après-midi": "afternoon", 
            "midi": "noon", "soir": "evening"
        }
    
    def parse(self, text: str, language: str = "fr") -> Dict[str, Any]:
        text_lower = text.lower().strip()
        
        # Détecter le type de contrainte
        for constraint_type, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return self._extract_constraint(constraint_type, match, text_lower)
        
        # Fallback: analyse par mots-clés
        return self._fallback_parse(text_lower)
    
    def _extract_constraint(self, constraint_type: str, match, text: str) -> Dict[str, Any]:
        groups = match.groups()
        
        if constraint_type == "teacher_availability":
            teacher = groups[0].title()
            day_str = groups[1] if len(groups) > 1 else ""
            
            unavailable_days = []
            for day_name, day_num in self.days_map.items():
                if day_name in day_str:
                    unavailable_days.append(day_num)
            
            return {
                "constraint": {
                    "type": "teacher_availability",
                    "entity": teacher,
                    "data": {
                        "unavailable_days": unavailable_days,
                        "reason": f"Extrait de: {text}"
                    },
                    "priority": 2
                },
                "confidence": 0.9,
                "summary": f"{teacher} n'est pas disponible {day_str}"
            }
        
        elif constraint_type == "time_preference":
            subject = groups[0].title()
            time_str = groups[1] if len(groups) > 1 else ""
            
            preferred_periods = []
            if "matin" in time_str:
                preferred_periods = [1, 2, 3, 4]
            elif "après-midi" in time_str or "apres-midi" in time_str:
                preferred_periods = [5, 6, 7, 8]
            
            return {
                "constraint": {
                    "type": "subject_time_preference", 
                    "entity": subject,
                    "data": {
                        "preferred_periods": preferred_periods,
                        "time_preference": time_str
                    },
                    "priority": 3
                },
                "confidence": 0.8,
                "summary": f"Cours de {subject} préférés {time_str}"
            }
        
        elif constraint_type == "consecutive_limit":
            max_hours = int(groups[0])
            
            return {
                "constraint": {
                    "type": "consecutive_hours_limit",
                    "entity": "all_classes",
                    "data": {
                        "max_consecutive": max_hours
                    },
                    "priority": 2
                },
                "confidence": 0.85,
                "summary": f"Maximum {max_hours} heures consécutives"
            }
        
        return self._fallback_parse(text)
    
    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        return {
            "constraint": {
                "type": "general",
                "entity": "unknown",
                "data": {"original_text": text},
                "priority": 3
            },
            "confidence": 0.3,
            "summary": "Contrainte non reconnue - analyse manuelle requise",
            "alternatives": [
                "Reformulez avec 'Le professeur X ne peut pas le Y'",
                "Ou 'Les cours de X doivent être le matin/après-midi'"
            ]
        }

# Instance du parseur
parser = ConstraintParser()

# ==== ROUTES API ====

@app.route('/health')
def health():
    try:
        # Test de connexion DB
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return jsonify({
        "status": "ok",
        "message": "Agent IA School Scheduler - Python Native",
        "version": "2.0-native",
        "database": db_status,
        "features": [
            "constraint_parsing",
            "natural_language", 
            "websocket_support",
            "database_integration"
        ],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/ai/constraints/natural', methods=['POST'])
def parse_natural_constraint():
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'fr')
        
        if not text:
            return jsonify({"error": "Texte manquant"}), 400
        
        # Parser la contrainte
        result = parser.parse(text, language)
        
        return jsonify({
            "original_text": text,
            "parsed_constraint": result,
            "confidence": result.get("confidence", 0.5),
            "summary": result.get("summary", ""),
            "alternatives": result.get("alternatives", []),
            "model_used": "native_parser",
            "processing_time_ms": 50  # Temps simulé
        })
        
    except Exception as e:
        logger.error(f"Erreur parsing: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    try:
        data = request.json
        constraint = data.get('constraint', {})
        
        # Validation de base
        if not all(k in constraint for k in ['type', 'entity', 'data']):
            return jsonify({"error": "Contrainte incomplète"}), 400
        
        # Simuler l'application (en mode développement)
        return jsonify({
            "status": "simulated",
            "message": "Contrainte analysée - Mode développement",
            "constraint_applied": constraint,
            "impact_analysis": {
                "affected_teachers": 1 if constraint.get('type') == 'teacher_availability' else 0,
                "affected_classes": 2,
                "complexity": "medium"
            },
            "suggestions": [
                "En mode production, cette contrainte serait transmise au solver OR-Tools",
                "Ajoutez vos clés API pour les fonctionnalités IA avancées"
            ]
        })
        
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/suggestions', methods=['GET'])
def get_suggestions():
    return jsonify({
        "suggestions": [
            {
                "type": "constraint_examples",
                "title": "Exemples de contraintes",
                "items": [
                    "Le professeur Cohen ne peut pas enseigner le vendredi",
                    "Les cours de mathématiques doivent être le matin",
                    "Maximum 3 heures consécutives de sport"
                ]
            },
            {
                "type": "optimization",
                "title": "Optimisations possibles",
                "items": [
                    "Réduire les trous dans l'emploi du temps",
                    "Éviter les matières difficiles en fin de journée",
                    "Équilibrer la charge des professeurs"
                ]
            }
        ]
    })

# ==== WEBSOCKET ====

@socketio.on('connect')
def handle_connect():
    session_id = request.sid
    active_sessions[session_id] = {
        "connected_at": datetime.now(),
        "context": {}
    }
    
    emit('connected', {
        "session_id": session_id,
        "message": "Connexion établie avec l'Agent IA (Python Native)",
        "capabilities": [
            "parsing_constraints",
            "natural_language_fr",
            "suggestions",
            "basic_analysis"
        ]
    })
    
    logger.info(f"Client connecté: {session_id}")

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    logger.info(f"Client déconnecté: {session_id}")

@socketio.on('message')
def handle_message(data):
    session_id = request.sid
    
    try:
        text = data.get('text', '')
        message_type = data.get('type', 'question')
        
        if message_type == 'constraint':
            # Parser et analyser
            result = parser.parse(text)
            
            if result.get('confidence', 0) > 0.7:
                response = {
                    "type": "plan",
                    "thoughts": f"J'ai analysé votre contrainte: {result['summary']}",
                    "plan": [
                        {
                            "step": "action/parse",
                            "description": "Analyse du texte en langage naturel",
                            "status": "completed",
                            "confidence": result['confidence']
                        },
                        {
                            "step": "action/validate",
                            "description": "Validation de la contrainte",
                            "status": "ready"
                        },
                        {
                            "step": "action/apply",
                            "description": "Application au solver (simulé)",
                            "status": "pending"
                        }
                    ],
                    "ask_user": "Souhaitez-vous simuler l'application de cette contrainte?",
                    "constraint_data": result['constraint']
                }
            else:
                response = {
                    "type": "clarification",
                    "message": f"Je ne suis pas sûr d'avoir bien compris (confiance: {result['confidence']:.1%})",
                    "suggestions": result.get('alternatives', []),
                    "examples": [
                        "Le professeur [Nom] ne peut pas [jour]",
                        "Les cours de [matière] doivent être le [moment]"
                    ]
                }
        else:
            # Question générale
            response = {
                "type": "answer",
                "message": f"Vous avez dit: '{text}'. Je peux vous aider avec les contraintes d'emploi du temps.",
                "suggestions": [
                    "Essayez de décrire une contrainte de disponibilité",
                    "Ou demandez des suggestions d'optimisation"
                ]
            }
        
        emit('ai_response', response)
        
    except Exception as e:
        logger.error(f"Erreur handle_message: {e}")
        emit('error', {"message": str(e)})

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════════════════╗
║        🤖 AGENT IA SCHOOL SCHEDULER                      ║
║                Version Python Native                     ║
╚══════════════════════════════════════════════════════════╝

🚀 Démarrage sur http://localhost:5001
🔧 Version: Développement (sans Docker)
📊 Base de données: {db_config['host']}:{db_config['port']}/{db_config['database']}

✨ Fonctionnalités disponibles:
  • Parsing de contraintes en français
  • API REST et WebSocket
  • Interface de test intégrée
  • Analyse et suggestions

🧪 Tests:
  • Health: curl http://localhost:5001/health
  • Parse: curl -X POST http://localhost:5001/api/ai/constraints/natural \\
           -H 'Content-Type: application/json' \\
           -d '{{"text":"Le professeur Cohen ne peut pas le vendredi","language":"fr"}}'

⏸️  Ctrl+C pour arrêter
""")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        print("\\n👋 Agent IA arrêté")
    except Exception as e:
        print(f"\\n❌ Erreur: {e}")

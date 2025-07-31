# scheduler_ai/api.py - Version corrigée avec Pydantic

"""
API Flask et WebSocket pour l'agent IA avec validation Pydantic
"""
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import asyncio
from typing import Dict, Any
import logging
import os
from datetime import datetime

# IMPORTANT : Importer Pydantic et les modèles
from pydantic import ValidationError
from models import ConstraintRequestSafe as ConstraintRequest, ConstraintResponse

# Importer l'agent et le router
from agent import ScheduleAIAgent
from llm_router import LLMRouter

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
db_config = {
    "host": os.environ.get("DB_HOST", "localhost"),  # Changé de "postgres" à "localhost"
    "database": os.environ.get("DB_NAME", "school_scheduler"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "school123")
}

# Instances
agent = ScheduleAIAgent(db_config)
llm_router = LLMRouter()

# Sessions actives
active_sessions = {}

@app.route('/health')
def health():
    """Check de santé de l'API"""
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    """
    Applique une nouvelle contrainte via l'agent IA avec validation Pydantic
    """
    try:
        # NOUVEAU : Validation automatique avec Pydantic
        constraint_request = ConstraintRequest(**request.json)
        
        logger.info(f"Constraint validated: {constraint_request.type} for {constraint_request.entity}")
        
        # Convertir en dict pour l'agent
        constraint_dict = constraint_request.dict()
        
        # Appliquer via l'agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.apply_constraint(constraint_dict))
        
        return jsonify(result)
        
    except ValidationError as e:
        # NOUVEAU : Retourner les erreurs de validation détaillées
        logger.warning(f"Validation failed: {e.errors()}")
        return jsonify({
            "error": "Validation failed",
            "details": e.errors()
        }), 400
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/explain/<conflict_id>', methods=['GET'])
def explain_conflict(conflict_id):
    """Explique un conflit spécifique"""
    try:
        explanation = agent.explain_conflict(conflict_id)
        return jsonify(explanation)
    except Exception as e:
        logger.error(f"Erreur explain_conflict: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/constraints/natural', methods=['POST'])
def parse_natural_constraint():
    """
    Parse une contrainte en langage naturel
    """
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'fr')
        
        # Utiliser le LLM pour parser
        parsed = llm_router.parse_natural_language(text, language)
        
        return jsonify({
            "original_text": text,
            "parsed_constraint": parsed,
            "confidence": parsed.get('confidence', 0.0)
        })
        
    except Exception as e:
        logger.error(f"Erreur parse_natural: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/suggestions', methods=['GET'])
def get_suggestions():
    """Obtient des suggestions d'amélioration pour l'emploi du temps actuel"""
    try:
        suggestions = agent.generate_improvement_suggestions()
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        logger.error(f"Erreur get_suggestions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai/history', methods=['GET'])
def get_constraint_history():
    """Récupère l'historique des contraintes appliquées"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        history = agent.get_constraint_history(limit, offset)
        return jsonify({
            "history": history,
            "total": len(history)
        })
    except Exception as e:
        logger.error(f"Erreur get_history: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ===== WEBSOCKET HANDLERS =====

@socketio.on('connect')
def handle_connect():
    """Gère la connexion d'un client"""
    session_id = request.sid
    active_sessions[session_id] = {
        "connected_at": datetime.now(),
        "context": {}
    }
    emit('connected', {
        "session_id": session_id,
        "message": "Connexion établie avec l'agent IA"
    })
    logger.info(f"Client connecté: {session_id}")

@socketio.on('disconnect')
def handle_disconnect():
    """Gère la déconnexion d'un client"""
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    logger.info(f"Client déconnecté: {session_id}")

@socketio.on('message')
def handle_message(data):
    """Gère les messages du chat"""
    session_id = request.sid
    
    try:
        text = data.get('text', '')
        message_type = data.get('type', 'question')
        context = data.get('context', {})
        
        logger.info(f"Message reçu de {session_id}: {text[:50]}...")
        
        # Router selon le type de message
        if message_type == 'constraint':
            response = handle_constraint_message(text, context)
        else:
            response = handle_question_message(text, context)
        
        emit('ai_response', response)
        
    except Exception as e:
        logger.error(f"Erreur handle_message: {str(e)}")
        emit('error', {"message": str(e)})

def handle_constraint_message(text: str, context: Dict) -> Dict[str, Any]:
    """Traite un message de type contrainte"""
    parsed = llm_router.parse_natural_language(text)
    
    if parsed.get('confidence', 0) > 0.7:
        return {
            "type": "plan",
            "message": f"J'ai compris : {parsed['summary']}",
            "constraint": parsed['constraint'],
            "thoughts": "Je vais analyser l'impact de cette contrainte sur l'emploi du temps.",
            "plan": [
                {"action": "Analyser la contrainte", "step": "action/analyze"},
                {"action": "Vérifier les conflits", "step": "action/check_conflicts"},
                {"action": "Proposer une solution", "step": "action/propose"}
            ],
            "ask_user": "Voulez-vous que j'applique cette contrainte ?"
        }
    else:
        return {
            "type": "clarification",
            "message": "Je ne suis pas sûr de comprendre. Pouvez-vous reformuler ?\n\nExemples valides :\n- Le professeur X ne peut pas le vendredi\n- Les cours de math doivent être le matin"
        }

def handle_question_message(text: str, context: Dict) -> Dict[str, Any]:
    """Traite une question générale"""
    # Utiliser le LLM pour répondre
    response = llm_router.answer_question(text, context)
    
    return {
        "type": "answer",
        "message": response['answer'],
        "references": response.get('references', [])
    }

@socketio.on('apply_plan')
def handle_apply_plan(data):
    """Applique un plan approuvé"""
    session_id = request.sid
    
    try:
        plan_id = data.get('plan_id')
        constraint = data.get('constraint')
        
        # Appliquer via l'agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.apply_constraint(constraint))
        
        # Notifier tous les clients connectés
        socketio.emit('schedule_updated', {
            "updater": session_id,
            "result": result
        }, room='schedule_viewers')
        
        emit('plan_applied', result)
        
    except Exception as e:
        logger.error(f"Erreur apply_plan: {str(e)}")
        emit('error', {"message": str(e)})

@socketio.on('join_schedule_view')
def handle_join_schedule_view():
    """Rejoint la room pour recevoir les mises à jour"""
    join_room('schedule_viewers')
    emit('joined_room', {"room": "schedule_viewers"})

if __name__ == '__main__':
    print("""
    🤖 Agent IA School Scheduler
    ============================
    
    ✅ Validation Pydantic activée
    📊 Base de données : localhost:5432
    🌐 WebSocket : http://localhost:5001
    
    Routes disponibles :
    - GET  /health
    - POST /api/ai/constraint (avec validation)
    - POST /api/ai/constraints/natural
    - GET  /api/ai/suggestions
    
    """)
    
    # Configuration serveur selon l'environnement
    is_development = os.getenv('FLASK_ENV') == 'development'
    
    if is_development:
        # Mode développement : permet Werkzeug avec allow_unsafe_werkzeug
        socketio.run(app, host="0.0.0.0", port=5001,
             debug=True, allow_unsafe_werkzeug=True)

    else:
        # Mode production : utilise eventlet pour la performance
        try:
            import eventlet
            socketio.run(app, debug=False, port=5001, host='0.0.0.0')
        except ImportError:
            logger.warning("eventlet non installé, utilisation de Werkzeug en mode unsafe")
            socketio.run(app, debug=False, port=5001, host='0.0.0.0', 
                        allow_unsafe_werkzeug=True)
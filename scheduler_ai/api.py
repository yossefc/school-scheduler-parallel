"""
scheduler_ai/api.py - API Flask et WebSocket pour l'agent IA
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

from scheduler_ai.agent import ScheduleAIAgent, ConstraintPriority
from scheduler_ai.llm_router import LLMRouter

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
db_config = {
    "host": os.environ.get("DB_HOST", "postgres"),
    "database": os.environ.get("DB_NAME", "school_scheduler"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "school123")
}

# Instances
agent = ScheduleAIAgent(db_config)
llm_router = LLMRouter()

# Sessions actives
active_sessions = {}

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    """
    Applique une nouvelle contrainte via l'agent IA
    
    Body: {
        "constraint": {
            "type": str,
            "entity": str,
            "data": dict,
            "priority": int
        }
    }
    """
    try:
        data = request.json
        constraint = data.get('constraint')
        
        if not constraint:
            return jsonify({"error": "Contrainte manquante"}), 400
        
        # Validation basique
        if not all(k in constraint for k in ['type', 'entity', 'data']):
            return jsonify({"error": "Contrainte incomplète"}), 400
        
        # Appliquer via l'agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.apply_constraint(constraint))
        
        return jsonify(result)
        
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
    
    Body: {
        "text": str,
        "language": "fr" | "he"
    }
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
    """
    Gère les messages du chat
    
    Data: {
        "text": str,
        "type": "question" | "constraint" | "feedback",
        "context": dict
    }
    """
    session_id = request.sid
    
    try:
        message_type = data.get('type', 'question')
        text = data.get('text', '')
        context = data.get('context', {})
        
        # Mettre à jour le contexte de session
        if session_id in active_sessions:
            active_sessions[session_id]['context'].update(context)
        
        # Router selon le type
        if message_type == 'constraint':
            # Parser et appliquer la contrainte
            response = handle_constraint_message(text, context)
        elif message_type == 'feedback':
            # Traiter le feedback
            response = handle_feedback_message(text, context)
        else:
            # Question générale
            response = handle_question_message(text, context)
        
        # Émettre la réponse
        emit('ai_response', response)
        
    except Exception as e:
        logger.error(f"Erreur handle_message: {str(e)}")
        emit('error', {"message": str(e)})

def handle_constraint_message(text: str, context: Dict) -> Dict[str, Any]:
    """Traite un message contenant une contrainte"""
    # Parser la contrainte
    parsed = llm_router.parse_natural_language(text, context.get('language', 'fr'))
    
    if parsed.get('confidence', 0) < 0.7:
        # Demander clarification
        return {
            "type": "clarification",
            "message": "Je ne suis pas sûr d'avoir bien compris. Voulez-vous dire :",
            "suggestions": parsed.get('alternatives', []),
            "original_parse": parsed
        }
    
    # Créer le plan
    constraint = parsed['constraint']
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    analysis = loop.run_until_complete(agent._analyze_constraint(constraint))
    
    plan = agent._create_modification_plan(constraint, analysis)
    
    return {
        "type": "plan",
        "thoughts": f"J'ai compris que vous voulez {parsed['summary']}",
        "plan": plan,
        "ask_user": "Souhaitez-vous appliquer ce plan ? (Répondre 'OK' ou préciser des ajustements)"
    }

def handle_feedback_message(text: str, context: Dict) -> Dict[str, Any]:
    """Traite un message de feedback"""
    if text.upper() == 'OK' and context.get('pending_plan'):
        # Appliquer le plan en attente
        plan = context['pending_plan']
        constraint = plan['constraint']
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(agent.apply_constraint(constraint))
        
        if result['status'] == 'success':
            return {
                "type": "success",
                "message": "✅ Plan appliqué avec succès !",
                "details": {
                    "score_delta": result['score_delta'],
                    "changes": result['solution_diff']
                }
            }
        else:
            return {
                "type": "error",
                "message": "❌ Impossible d'appliquer le plan",
                "details": result
            }
    else:
        # Traiter comme ajustement
        return {
            "type": "adjustment",
            "message": "Je comprends vos ajustements. Que souhaitez-vous modifier ?"
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

# ===== HELPERS =====

def format_response_for_ui(response: Dict) -> Dict:
    """Formate la réponse pour l'UI"""
    if response['type'] == 'plan':
        # Ajouter des métadonnées visuelles
        for step in response['plan']:
            step['icon'] = get_icon_for_action(step['step'])
            step['color'] = get_color_for_priority(step.get('priority', 3))
    
    return response

def get_icon_for_action(action: str) -> str:
    """Retourne l'icône appropriée pour une action"""
    icons = {
        "action/add_constraint": "➕",
        "action/modify_constraint": "✏️",
        "action/solve": "🔄",
        "action/report": "📊",
        "action/relax_constraint": "🔧"
    }
    return icons.get(action, "▶️")

def get_color_for_priority(priority: int) -> str:
    """Retourne la couleur pour un niveau de priorité"""
    colors = {
        0: "red",      # HARD
        1: "orange",   # VERY_STRONG  
        2: "yellow",   # MEDIUM
        3: "blue",     # NORMAL
        4: "green",    # LOW
        5: "gray"      # MINIMAL
    }
    return colors.get(priority, "blue")

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
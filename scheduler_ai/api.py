"""API Flask avec support complet des contraintes et clarifications"""
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any
from parsers import natural_language_parser
from agent_extensions import clarification_middleware

from pydantic import ValidationError

# Imports directs (structure plate)
from models import ConstraintInput, ConstraintResponse
from agent_extensions import clarification_middleware
from agent import ScheduleAIAgent
from models import ConstraintInput, ConstraintResponse
from database import Constraint, get_db_session, create_tables
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialisation des tables SQLAlchemy
create_tables()
agent = ScheduleAIAgent({
    "host": os.environ.get("DB_HOST", "postgres"),  # postgres not localhost dans Docker
    "database": os.environ.get("DB_NAME", "school_scheduler"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASSWORD", "school123")
})

# Sessions actives
active_sessions: Dict[str, Dict] = {}


@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai-advanced",
        "version": "3.0",
        "features": ["nlp_parsing", "clarifications", "auto_apply"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/ai/validate_teacher', methods=['POST'])
def validate_teacher():
    """Valide et propose des corrections pour les noms de professeurs"""
    data = request.get_json()
    input_name = data.get('teacher_name', '')
    
    result = agent._resolve_teacher_name(input_name)
    
    if result["success"] == "confirmation_needed":
        return jsonify({
            "status": "confirmation_needed",
            "message": result["question"],
            "suggested_teacher": result["teacher"]["teacher_name"],
            "confidence": result["confidence"]
        })
    
    return jsonify(result)
@app.route('/api/ai/constraints', methods=['POST'])
def apply_constraint():
    """Applique une contrainte avec validation Pydantic"""
    try:
        # Validation avec Pydantic
        constraint_input = ConstraintInput(**request.json)
        
        # Si clarification nécessaire
        if constraint_input.requires_clarification:
            return jsonify(ConstraintResponse(
                status="clarification_needed",
                constraint=constraint_input,
                message="Clarification nécessaire",
                clarification_questions=constraint_input.clarification_questions
            ).model_dump())
        
        # Appliquer la contrainte
        result = asyncio.run(agent.apply_constraint(constraint_input.model_dump()))
        
        # Persister si succès
        if result.get("status") == "success":
            # Préparer les données enrichies
            enriched_data = constraint_input.data.copy() if constraint_input.data else {}
            enriched_data.update({
                'metadata': constraint_input.metadata,
                'created_by': 'api'
            })
            
            new_constraint = Constraint(
                constraint_type=constraint_input.type.value,
                entity_name=constraint_input.entity,
                constraint_data=enriched_data,
                priority=constraint_input.priority.value,
                is_active=True
            )
            session = get_db_session()
            try:
                session.add(new_constraint)
                session.commit()
                session.refresh(new_constraint)
                result["constraint_id"] = new_constraint.id
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
        
        return jsonify(result)
        
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": "Validation échouée",
            "errors": e.errors()
        }), 400
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@socketio.on('connect')
def handle_connect():
    session_id = request.sid
    active_sessions[session_id] = {
        "connected_at": datetime.now(),
        "clarification_count": 0
    }
    emit('connected', {
        "message": "Agent IA connecté - Support complet des contraintes",
        "session_id": session_id
    })


@socketio.on('message')
def handle_message(data):
    """Traite un message de l'utilisateur"""
    session_id = request.sid
    text = data.get('text', '')
    
    # DEBUG
    print(f"🔍 Message reçu: {text}")
    
    async def process_message_async():
        try:
            # Utiliser le middleware
            response = await clarification_middleware.process_constraint(
                text,
                session_id,
                context=data.get('context', {})
            )
            
            # IMPORTANT: Toujours envoyer les détails complets
            emit_data = {
                'status': response.status,
                'message': response.message,
                'confidence': response.confidence
            }
            
            # AJOUTER LES DÉTAILS DE LA CONTRAINTE
            if response.constraint:
                emit_data['constraint'] = {
                    'type': response.constraint.type.value if hasattr(response.constraint.type, 'value') else str(response.constraint.type),
                    'entity': response.constraint.entity,
                    'data': response.constraint.data,
                    'confidence': response.constraint.confidence or 0.8
                }
            
            # Si questions de clarification
            if response.clarification_questions:
                emit_data['clarification_questions'] = response.clarification_questions
            
            print(f"📤 Envoi réponse: {emit_data}")
            emit('ai_response', emit_data)
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            emit('ai_response', {
                'status': 'error',
                'message': f'Erreur: {str(e)}'
            })
    
    asyncio.run(process_message_async())

@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    clarification_middleware.clear_history(session_id)


@app.route('/api/ai/constraints', methods=['GET'])
def list_constraints():
    """Liste toutes les contraintes actives"""
    session = get_db_session()
    try:
        constraints = session.query(Constraint).filter_by(is_active=True).all()
        return jsonify({
            "constraints": [c.to_dict() for c in constraints],
            "total": len(constraints)
        })
    finally:
        session.close()


if __name__ == '__main__':
    create_tables()
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
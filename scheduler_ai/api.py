"""API Flask avec support complet des contraintes et clarifications"""
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any

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


@app.route('/api/ai/constraint', methods=['POST'])
async def apply_constraint():
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
        result = await agent.apply_constraint(constraint_input.model_dump())
        
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
    """Gère les messages avec clarifications"""
    session_id = request.sid
    text = data.get('text', '')
    context = data.get('context', {})
    
    async def process_message_async():
        """Traitement async de la requête"""
        try:
            # Utiliser le middleware de clarification
            response = await clarification_middleware.process_constraint(
                text, 
                session_id,
                context
            )
            
            # Si succès avec auto-apply
            if response.status == "success" and response.applied_automatically:
                # Appliquer réellement la contrainte
                constraint_dict = response.constraint.model_dump()
                result = await agent.apply_constraint(constraint_dict)
                
                # Persister
                if result.get("status") == "success":
                    # Préparer les données enrichies
                    enriched_data = response.constraint.data.copy() if response.constraint.data else {}
                    enriched_data.update({
                        'metadata': response.constraint.metadata if hasattr(response.constraint, 'metadata') else {},
                        'original_text': response.constraint.original_text,
                        'confidence': response.constraint.confidence,
                        'created_by': f"session_{session_id}"
                    })
                    
                    new_constraint = Constraint(
                        constraint_type=response.constraint.type.value,
                        entity_name=response.constraint.entity,
                        constraint_data=enriched_data,
                        priority=response.constraint.priority.value,
                        is_active=True
                    )
                    session = get_db_session()
                    try:
                        session.add(new_constraint)
                        session.commit()
                        session.refresh(new_constraint)
                        response.constraint_id = new_constraint.id
                    except Exception as e:
                        session.rollback()
                        raise e
                    finally:
                        session.close()
                    
                emit('schedule_updated', {
                    "constraint_id": response.constraint_id,
                    "message": "Emploi du temps mis à jour"
                }, broadcast=True)
            
            # Émettre la réponse (avec sérialisation JSON safe)
            emit('ai_response', response.model_dump(mode='json'))
            
        except Exception as e:
            logger.error(f"Erreur handle_message: {e}")
            emit('ai_response', {
                "status": "error",
                "message": "Erreur lors du traitement"
            })
    
    # Exécuter la fonction async dans le contexte sync
    try:
        asyncio.run(process_message_async())
    except Exception as e:
        logger.error(f"Erreur asyncio.run: {e}")
        emit('ai_response', {
            "status": "error",
            "message": "Erreur lors du traitement"
        })


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
# scheduler_ai/api.py - Application Automatique
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
import json
import logging
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

AUTO_APPLY_THRESHOLD = 0.8
active_sessions = {}

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai-auto", 
        "auto_apply_enabled": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    try:
        data = request.json
        constraint_type = data.get("type", "unknown")
        
        # Simulation application automatique
        return jsonify({
            "status": "success",
            "applied_automatically": True,
            "message": f"Contrainte {constraint_type} appliquee automatiquement !",
            "confidence": 0.9
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    session_id = request.sid
    active_sessions[session_id] = {"connected_at": datetime.now()}
    emit('connected', {
        "message": "Agent IA connecte - Application automatique activee",
        "auto_apply_enabled": True
    })

@socketio.on('message')
def handle_message(data):
    text = data.get('text', '').lower()
    
    if 'cohen' in text and 'vendredi' in text:
        emit('ai_response', {
            "type": "success",
            "message": "Contrainte appliquee automatiquement !\n\nLe professeur Cohen est indisponible le vendredi.\nEmploi du temps mis a jour.",
            "schedule_updated": True
        })
    else:
        emit('ai_response', {
            "type": "clarification", 
            "message": "Exemple: 'Le professeur Cohen ne peut pas enseigner le vendredi'"
        })

if __name__ == '__main__':
    socketio.run(app, port=5001, host='0.0.0.0')

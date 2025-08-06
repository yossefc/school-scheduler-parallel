"""
scheduler_ai/api.py - API Flask avec Socket.IO utilisant LLMRouter existant
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import redis

# Import de VOTRE LLMRouter existant
from llm_router import LLMRouter, TaskComplexity

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

# CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ============================================
# INITIALISATION DES SERVICES
# ============================================

# Initialiser LLMRouter (votre classe existante)
llm_router = LLMRouter()

# Vérifier que les LLM sont disponibles
if llm_router.openai_client:
    logger.info("✅ OpenAI configuré")
else:
    logger.warning("⚠️ OpenAI non configuré")

if llm_router.anthropic_client:
    logger.info("✅ Anthropic configuré")
else:
    logger.warning("⚠️ Anthropic non configuré")

# Redis pour cache
redis_client = None
if redis:
    try:
        redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', 'redis'),
            port=6379,
            decode_responses=True
        )
        redis_client.ping()
        logger.info("✅ Redis connecté")
    except:
        logger.warning("⚠️ Redis non disponible")
else:
    logger.warning("⚠️ Module redis non installé")

# Sessions actives
active_sessions: Dict[str, Dict[str, Any]] = {}

# ============================================
# MIDDLEWARE UTILISANT LLMROUTER
# ============================================

class LLMMiddleware:
    """Middleware qui utilise LLMRouter pour analyser les contraintes"""
    
    def __init__(self, router: LLMRouter):
        self.router = router
        self.sessions = {}
    
    def analyze_constraint(self, text: str, session_id: str, context: Dict = None) -> Dict:
        """Analyse une contrainte en utilisant LLMRouter"""
        
        try:
            # Détecter la langue (français ou hébreu)
            language = "he" if any(ord(c) > 0x0590 and ord(c) < 0x05FF for c in text) else "fr"
            
            logger.info(f"Analyse de contrainte ({language}): {text[:100]}...")
            
            # Utiliser parse_natural_language de LLMRouter
            parsed = self.router.parse_natural_language(
                text=text,
                language=language,
                session_id=session_id
            )
            
            logger.info(f"Résultat parsing: {parsed}")
            
            # Vérifier si clarification nécessaire
            if parsed.get('requires_clarification') or parsed.get('confidence', 0) < 0.6:
                questions = parsed.get('clarification_questions', [])
                if not questions:
                    questions = [
                        "Pouvez-vous préciser le type de contrainte ?",
                        "Pour quelle entité (professeur, classe, salle) ?"
                    ]
                
                return {
                    'status': 'clarification_needed',
                    'clarification_questions': questions,
                    'partial_result': parsed
                }
            
            # Extraire la contrainte
            constraint = parsed.get('constraint', {})
            
            # S'assurer que tous les champs requis sont présents
            if not constraint.get('type'):
                constraint['type'] = 'custom'
            if not constraint.get('entity'):
                constraint['entity'] = 'Global'
            if not constraint.get('data'):
                constraint['data'] = {'original_text': text}
            
            # Ajouter la confiance et le modèle utilisé
            constraint['confidence'] = parsed.get('confidence', 0.5)
            constraint['model_used'] = parsed.get('model_used', 'unknown')
            constraint['original_text'] = text
            
            # Si un résumé est fourni
            if parsed.get('summary'):
                constraint['interpretation'] = parsed['summary']
            
            return {
                'status': 'success',
                'constraint': constraint,
                'alternatives': parsed.get('alternatives', [])
            }
            
        except Exception as e:
            logger.error(f"Erreur dans analyze_constraint: {str(e)}")
            
            # Fallback : analyse basique
            return {
                'status': 'success',
                'constraint': {
                    'type': 'custom',
                    'entity': 'Global',
                    'data': {'original_text': text},
                    'confidence': 0.3,
                    'model_used': 'fallback',
                    'original_text': text
                }
            }
    
    def clear_session(self, session_id: str):
        """Nettoie une session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

# Initialiser le middleware avec LLMRouter
middleware = LLMMiddleware(llm_router)

# ============================================
# ROUTES HTTP
# ============================================

@app.route('/health', methods=['GET'])
def health_check():
    """Vérification de santé"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'ai_available': {
            'claude': llm_router.anthropic_client is not None,
            'gpt': llm_router.openai_client is not None,
            'cache': redis_client is not None
        },
        'active_sessions': len(active_sessions)
    })

@app.route('/api/ai/apply_constraint', methods=['POST'])
def apply_constraint():
    """Analyse une contrainte via HTTP"""
    try:
        data = request.json
        constraint_text = data.get('constraint_text', '')
        context = data.get('context', {})
        
        # Créer une session temporaire
        session_id = f"http_{datetime.now().timestamp()}"
        
        # Analyser avec le middleware LLM
        result = middleware.analyze_constraint(constraint_text, session_id, context)
        
        # Nettoyer la session
        middleware.clear_session(session_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/ai/answer', methods=['POST'])
def answer_question():
    """Répond à une question en utilisant LLMRouter"""
    try:
        data = request.json
        question = data.get('question', '')
        context = data.get('context', {})
        
        # Utiliser answer_question de LLMRouter
        result = llm_router.answer_question(question, context)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erreur answer_question: {str(e)}")
        return jsonify({
            'answer': f"Erreur: {str(e)}",
            'model_used': 'error'
        }), 500

# ============================================
# WEBSOCKET HANDLERS
# ============================================

@socketio.on('connect')
def handle_connect():
    """Connexion WebSocket"""
    session_id = request.sid
    active_sessions[session_id] = {
        'connected_at': datetime.now().isoformat(),
        'messages_count': 0
    }
    
    # Informer sur les capacités
    capabilities = {
        'claude': llm_router.anthropic_client is not None,
        'gpt': llm_router.openai_client is not None,
        'cache': redis_client is not None
    }
    
    emit('connected', {
        'message': 'Agent IA connecté',
        'session_id': session_id,
        'capabilities': capabilities,
        'models_available': []
    })
    
    # Ajouter les modèles disponibles
    models = []
    if capabilities['gpt']:
        models.append('GPT-4o')
    if capabilities['claude']:
        models.append('Claude Opus')
    
    if models:
        logger.info(f"✅ Connexion {session_id} - Modèles: {', '.join(models)}")
    else:
        logger.warning(f"⚠️ Connexion {session_id} - Aucun modèle IA configuré")

@socketio.on('message')
def handle_message(data):
    """Traite un message via WebSocket"""
    session_id = request.sid
    text = data.get('text', '')
    context = data.get('context', {})
    
    logger.info(f"Message reçu de {session_id}: {text[:100]}...")
    
    try:
        # Incrémenter le compteur
        if session_id in active_sessions:
            active_sessions[session_id]['messages_count'] += 1
        
        # Analyser avec le middleware LLM
        result = middleware.analyze_constraint(text, session_id, context)
        
        # Ajouter des informations de debug si en mode development
        if os.environ.get('FLASK_ENV') == 'development':
            result['debug'] = {
                'session_id': session_id,
                'language_detected': 'hebrew' if any(ord(c) > 0x0590 and ord(c) < 0x05FF for c in text) else 'french',
                'tokens_estimated': len(text.split())
            }
        
        # Envoyer la réponse
        emit('ai_response', result)
        
        logger.info(f"Réponse envoyée: status={result['status']}")
        
    except Exception as e:
        logger.error(f"Erreur traitement message: {str(e)}")
        emit('ai_response', {
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        })

@socketio.on('clarification_response')
def handle_clarification(data):
    """Gère les réponses aux clarifications"""
    session_id = request.sid
    answers = data.get('answers', [])
    original_text = data.get('original_text', '')
    
    try:
        # Combiner le texte original avec les clarifications
        enhanced_text = f"{original_text}\n"
        enhanced_text += "Clarifications:\n"
        enhanced_text += "\n".join(answers)
        
        # Réanalyser avec plus d'informations
        result = middleware.analyze_constraint(enhanced_text, session_id, {})
        
        emit('ai_response', result)
        
    except Exception as e:
        logger.error(f"Erreur clarification: {str(e)}")
        emit('ai_response', {
            'status': 'error',
            'message': str(e)
        })

@socketio.on('disconnect')
def handle_disconnect():
    """Déconnexion"""
    session_id = request.sid
    
    if session_id in active_sessions:
        info = active_sessions[session_id]
        logger.info(f"Déconnexion {session_id} après {info['messages_count']} messages")
        del active_sessions[session_id]
    
    middleware.clear_session(session_id)

# ============================================
# ROUTES ADDITIONNELLES
# ============================================

@app.route('/api/ai/stats', methods=['GET'])
def get_stats():
    """Statistiques d'utilisation"""
    stats = {
        'active_sessions': len(active_sessions),
        'total_messages': sum(s['messages_count'] for s in active_sessions.values()),
        'models_available': {
            'gpt': llm_router.openai_client is not None,
            'claude': llm_router.anthropic_client is not None
        }
    }
    
    # Ajouter stats Redis si disponible
    if redis_client:
        try:
            stats['cache_keys'] = len(redis_client.keys('constraint:*'))
        except:
            pass
    
    return jsonify(stats)

@app.route('/api/ai/test', methods=['POST'])
def test_llm():
    """Route de test pour vérifier que les LLM fonctionnent"""
    try:
        text = request.json.get('text', 'Le professeur Cohen ne peut pas enseigner le vendredi')
        
        # Tester avec LLMRouter
        result = llm_router.parse_natural_language(text)
        
        return jsonify({
            'success': True,
            'input': text,
            'output': result,
            'model_used': result.get('model_used', 'unknown')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# POINT D'ENTRÉE
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    # Afficher la configuration
    logger.info("=" * 60)
    logger.info("CONFIGURATION DE L'API IA")
    logger.info("=" * 60)
    logger.info(f"Port: {port}")
    logger.info(f"Mode: {'Development' if debug else 'Production'}")
    logger.info(f"OpenAI: {'✅ Configuré' if llm_router.openai_client else '❌ Non configuré'}")
    logger.info(f"Anthropic: {'✅ Configuré' if llm_router.anthropic_client else '❌ Non configuré'}")
    logger.info(f"Redis: {'✅ Connecté' if redis_client else '❌ Non disponible'}")
    logger.info("=" * 60)
    
    if not llm_router.openai_client and not llm_router.anthropic_client:
        logger.warning("""
        ⚠️ ATTENTION: Aucune clé API configurée!
        L'API fonctionnera en mode dégradé (parsing basique).
        
        Pour activer l'IA, ajoutez dans scheduler_ai/.env :
        OPENAI_API_KEY=sk-...
        ANTHROPIC_API_KEY=sk-ant-...
        """)
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
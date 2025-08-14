# advisor_api.py - API Flask pour l'agent conseiller
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging
from schedule_advisor_agent import ScheduleAdvisorAgent, create_advisor_agent
import os
from datetime import datetime
import json

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['JSON_AS_ASCII'] = False  # Support UTF-8 pour hébreu

# Configuration CORS pour permettre l'accès depuis le port 8000
CORS(app, origins=["http://localhost:8000", "http://127.0.0.1:8000"])

socketio = SocketIO(app, cors_allowed_origins=["http://localhost:8000", "http://127.0.0.1:8000", "*"])

# Configuration DB
db_config = {
    "host": os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "school_scheduler"),
    "user": os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", "school123")
}

# Instance globale de l'agent conseiller
advisor_agent = create_advisor_agent(db_config)

@app.route('/api/advisor/chat', methods=['POST'])
def chat_with_advisor():
    """Endpoint principal pour discuter avec l'agent conseiller"""
    try:
        # Gestion explicite de l'encodage UTF-8 pour hébreu
        data = request.get_json(force=True)
        if not data:
            # Fallback si JSON malformé
            raw_data = request.get_data(as_text=True)
            logger.warning(f"JSON malformé, données brutes: {raw_data[:100]}")
            return jsonify({
                "error": "Format JSON invalide",
                "success": False
            }), 400
            
        user_input = data.get('message', '')
        user_context = data.get('context', {})
        
        # Vérifier que le message n'est pas vide ou corrompu
        if not user_input or len(user_input.strip()) == 0:
            return jsonify({
                "error": "Message vide ou invalide",
                "success": False
            }), 400
        
        logger.info(f"Demande utilisateur: {user_input}")
        
        # Traiter la demande avec l'agent
        response = advisor_agent.process_user_request(user_input, user_context)
        
        # Émettre la réponse via WebSocket si nécessaire
        socketio.emit('advisor_response', response, room=user_context.get('session_id'))
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erreur chat advisor: {e}")
        return jsonify({
            "error": str(e),
            "message": "Désolé, j'ai rencontré un problème. Pouvez-vous reformuler votre demande ?",
            "success": False
        }), 500

@app.route('/api/advisor/confirm', methods=['POST'])
def confirm_changes():
    """Confirme ou rejette les changements proposés"""
    try:
        data = request.get_json()
        change_ids = data.get('change_ids', [])
        confirmation = data.get('confirmation', 'yes')
        user_context = data.get('context', {})
        
        logger.info(f"Confirmation changements: {change_ids}, decision: {confirmation}")
        
        response = advisor_agent.confirm_changes(change_ids, confirmation)
        
        # Émettre la confirmation via WebSocket
        socketio.emit('changes_applied', response, room=user_context.get('session_id'))
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erreur confirmation: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/api/advisor/preferences', methods=['GET'])
def get_user_preferences():
    """Récupère les préférences/revendications utilisateur"""
    try:
        preferences = advisor_agent.get_user_preferences_summary()
        return jsonify({
            "preferences": preferences,
            "success": True
        })
    except Exception as e:
        logger.error(f"Erreur récupération préférences: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/api/advisor/conversation', methods=['GET'])
def get_conversation_history():
    """Récupère l'historique de conversation"""
    try:
        return jsonify({
            "conversation": advisor_agent.conversation_history,
            "success": True
        })
    except Exception as e:
        logger.error(f"Erreur récupération conversation: {e}")
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/api/advisor/status', methods=['GET'])
def get_advisor_status():
    """État de l'agent conseiller"""
    try:
        return jsonify({
            "status": "active",
            "pending_changes": len(advisor_agent.pending_changes),
            "user_preferences": len(advisor_agent.user_preferences),
            "conversation_length": len(advisor_agent.conversation_history),
            "success": True
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

@app.route('/api/advisor/examples', methods=['GET'])
def get_usage_examples():
    """Retourne des exemples d'utilisation pour guider l'utilisateur (français + hébreu)"""
    examples = {
        "simple_requests_french": [
            "Peux-tu éliminer les trous dans l'emploi du temps de ז-1 ?",
            "Je voudrais déplacer le cours de maths de יא-2 plus tôt dans la journée",
            "Comment équilibrer mieux la charge entre les classes ?",
            "Y a-t-il trop d'heures pour certains professeurs ?",
        ],
        "simple_requests_hebrew": [
            "תוכל למלא את החורים במערכת השעות של ז-1?",
            "אני רוצה להזיז את המתמטיקה של יא-2 יותר מוקדם ביום",
            "איך לאזן טוב יותר את העומס בין הכיתות?",
            "האם יש יותר מדי שעות למורים מסוימים?",
        ],
        "preferences_french": [
            "Pour moi, il est important que les cours de maths soient toujours le matin",
            "J'évite toujours les cours après 15h pour les petites classes",
            "Les professeurs de sciences préfèrent avoir leurs cours groupés",
            "Règle importante: pas plus de 6h par jour pour chaque classe"
        ],
        "preferences_hebrew": [
            "חשוב לי שהמתמטיקה תמיד תהיה בבוקר",
            "אני תמיד נמנע משיעורים אחרי 15:00 לכיתות הקטנות",
            "המורים למדעים מעדיפים שיעורים מקובצים",
            "כלל חשוב: לא יותר מ-6 שעות ביום לכל כיתה"
        ],
        "complex_requests_french": [
            "Peux-tu optimiser l'emploi du temps en gardant mes préférences sur les horaires ?",
            "Je veux réorganiser la semaine de ח-1 en évitant les conflits avec les cours parallèles",
            "Comment faire pour que tous les cours commencent à 8h et se terminent avant 16h ?"
        ],
        "complex_requests_hebrew": [
            "תוכל לייעל את מערכת השעות תוך שמירה על ההעדפות שלי לגבי הזמנים?",
            "אני רוצה לארגן מחדש את השבוע של ח-1 תוך הימנעות מקונפליקטים עם שיעורים מקבילים",
            "איך לגרום לכל השיעורים להתחיל ב-8 ולהסתיים לפני 16:00?"
        ]
    }
    
    return jsonify({
        "examples": examples,
        "tips_french": [
            "Soyez spécifique sur ce que vous voulez modifier",
            "Mentionnez vos préférences, l'agent s'en souviendra",
            "Vous pouvez demander 'plus de détails' avant de confirmer",
            "L'agent apprend de vos demandes pour mieux vous conseiller"
        ],
        "tips_hebrew": [
            "היו ספציפיים לגבי מה שאתם רוצים לשנות",
            "ציינו את ההעדפות שלכם, הסוכן יזכור אותן",
            "תוכלו לבקש 'פרטים נוספים' לפני האישור",
            "הסוכן לומד מהבקשות שלכם כדי לייעץ טוב יותר"
        ],
        "languages_supported": ["hebrew", "french"],
        "success": True
    })

# WebSocket events pour communication en temps réel
@socketio.on('connect')
def handle_connect():
    logger.info('Client connecté à l\'agent conseiller')
    emit('advisor_ready', {
        "message": "Bonjour ! Je suis votre agent conseiller pour l'emploi du temps. Comment puis-je vous aider ?",
        "timestamp": datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client déconnecté de l\'agent conseiller')

@socketio.on('user_message')
def handle_user_message(data):
    """Traite les messages utilisateur en temps réel"""
    try:
        user_input = data.get('message', '')
        user_context = data.get('context', {})
        user_context['session_id'] = request.sid
        
        # Traiter avec l'agent
        response = advisor_agent.process_user_request(user_input, user_context)
        
        # Émettre la réponse
        emit('advisor_response', response)
        
    except Exception as e:
        emit('advisor_error', {
            "error": str(e),
            "message": "Désolé, une erreur s'est produite. Pouvez-vous réessayer ?"
        })

@socketio.on('confirm_changes')
def handle_confirm_changes(data):
    """Traite les confirmations de changements en temps réel"""
    try:
        change_ids = data.get('change_ids', [])
        confirmation = data.get('confirmation', 'yes')
        
        response = advisor_agent.confirm_changes(change_ids, confirmation)
        emit('changes_result', response)
        
    except Exception as e:
        emit('advisor_error', {
            "error": str(e)
        })

@app.route('/api/advisor/optimize', methods=['POST'])
def optimize_schedule():
    """Optimise l'emploi du temps avec les algorithmes avancés"""
    try:
        data = request.get_json() or {}
        algorithm = data.get('algorithm', 'hybrid')
        objectives = data.get('objectives', None)
        
        logger.info(f"🚀 Demande d'optimisation avec algorithme: {algorithm}")
        
        # Initialiser le moteur d'optimisation si nécessaire
        if not advisor_agent.optimization_engine:
            success = advisor_agent.initialize_optimization_engine()
            if not success:
                return jsonify({
                    "error": "Impossible d'initialiser le moteur d'optimisation",
                    "success": False
                }), 500
        
        # Effectuer l'optimisation
        result = advisor_agent.optimize_schedule_with_advanced_algorithms(
            algorithm=algorithm,
            objectives=objectives
        )
        
        if "error" in result:
            return jsonify({
                "error": result["error"],
                "success": False
            }), 500
        
        return jsonify({
            "success": True,
            "algorithm": algorithm,
            "optimization_result": result,
            "quality_score": result.get("quality", {}).get("total_score", 0),
            "recommendations": result.get("recommendations", []),
            "algorithm_info": result.get("algorithm_info", {})
        })
        
    except Exception as e:
        logger.error(f"Erreur optimisation: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur d'optimisation: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/recommend-algorithm', methods=['GET'])
def recommend_algorithm():
    """Recommande le meilleur algorithme pour le contexte actuel"""
    try:
        # Initialiser le moteur d'optimisation si nécessaire
        if not advisor_agent.optimization_engine:
            success = advisor_agent.initialize_optimization_engine()
            if not success:
                return jsonify({
                    "error": "Impossible d'analyser le contexte",
                    "success": False
                }), 500
        
        # Obtenir la recommandation
        recommendation = advisor_agent.recommend_best_algorithm()
        
        if "error" in recommendation:
            return jsonify({
                "error": recommendation["error"],
                "success": False
            }), 500
        
        return jsonify({
            "success": True,
            "recommendation": recommendation
        })
        
    except Exception as e:
        logger.error(f"Erreur recommandation algorithme: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur de recommandation: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/analyze-quality', methods=['GET'])
def analyze_schedule_quality():
    """Analyse la qualité de l'emploi du temps actuel"""
    try:
        # Initialiser le moteur d'optimisation si nécessaire
        if not advisor_agent.optimization_engine:
            success = advisor_agent.initialize_optimization_engine()
            if not success:
                return jsonify({
                    "error": "Impossible d'analyser la qualité",
                    "success": False
                }), 500
        
        # Récupérer les données d'emploi du temps
        schedule_data = advisor_agent._get_current_schedule_data()
        if not schedule_data:
            return jsonify({
                "error": "Impossible de récupérer les données d'emploi du temps",
                "success": False
            }), 500
        
        # Analyser la qualité
        quality_analysis = advisor_agent.optimization_engine.analyze_schedule_quality(schedule_data)
        
        return jsonify({
            "success": True,
            "quality_analysis": quality_analysis,
            "schedule_metadata": schedule_data.get("metadata", {}),
            "improvement_suggestions": advisor_agent._generate_optimization_recommendations({
                "quality": quality_analysis
            })
        })
        
    except Exception as e:
        logger.error(f"Erreur analyse qualité: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur d'analyse: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/algorithms-info', methods=['GET'])
def get_algorithms_info():
    """Retourne des informations sur tous les algorithmes disponibles"""
    try:
        algorithms_info = {
            "simulated_annealing": advisor_agent._get_algorithm_info("simulated_annealing"),
            "tabu_search": advisor_agent._get_algorithm_info("tabu_search"),
            "hybrid": advisor_agent._get_algorithm_info("hybrid"),
            "multi_objective": advisor_agent._get_algorithm_info("multi_objective")
        }
        
        return jsonify({
            "success": True,
            "algorithms": algorithms_info,
            "description": "Algorithmes d'optimisation avancés basés sur l'analyse comparative des méthodes NP-difficiles"
        })
        
    except Exception as e:
        logger.error(f"Erreur infos algorithmes: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/train', methods=['POST'])
def train_agent():
    """Entraîne l'agent AI sur tous les scénarios"""
    try:
        logger.info("🎓 Demande d'entraînement de l'agent AI")
        
        # Lancer l'entraînement
        training_results = advisor_agent.train_agent_on_all_scenarios()
        
        return jsonify({
            "success": True,
            "training_results": training_results,
            "message": f"Agent entraîné avec {training_results['success_rate']:.1%} de succès"
        })
        
    except Exception as e:
        logger.error(f"Erreur entraînement: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur d'entraînement: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/optimize-intelligent', methods=['POST'])
def optimize_intelligent():
    """Optimisation intelligente avec apprentissage automatique"""
    try:
        logger.info("🧠 Demande d'optimisation intelligente")
        
        # Utiliser l'optimisation avec apprentissage
        result = advisor_agent.optimize_with_intelligent_learning()
        
        if "error" in result:
            return jsonify({
                "error": result["error"],
                "success": False
            }), 500
        
        return jsonify({
            "success": True,
            "optimization_result": result,
            "learning_info": result.get("learning_info", {}),
            "message": "Optimisation intelligente terminée"
        })
        
    except Exception as e:
        logger.error(f"Erreur optimisation intelligente: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur: {str(e)}",
            "success": False
        }), 500

@app.route('/api/advisor/learning-status', methods=['GET'])
def get_learning_status():
    """Obtient le statut d'apprentissage de l'agent"""
    try:
        # Obtenir les statistiques d'apprentissage
        training_system = advisor_agent.training_system
        
        # Calculer les statistiques
        total_cases = len(training_system.learning_history)
        successful_cases = sum(1 for o in training_system.learning_history if o.success)
        
        # Rankings des algorithmes
        rankings = training_system.rank_algorithms()
        
        # Insights
        insights = training_system.extract_key_insights()
        
        return jsonify({
            "success": True,
            "learning_status": {
                "total_training_cases": total_cases,
                "successful_cases": successful_cases,
                "success_rate": successful_cases / total_cases if total_cases > 0 else 0,
                "algorithm_rankings": rankings,
                "key_insights": insights,
                "algorithm_performance": training_system.algorithm_performance
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur status apprentissage: {e}", exc_info=True)
        return jsonify({
            "error": f"Erreur: {str(e)}",
            "success": False
        }), 500

if __name__ == '__main__':
    logger.info("🤖 Démarrage de l'Agent Conseiller d'Emploi du Temps")
    logger.info("Endpoints disponibles:")
    logger.info("  POST /api/advisor/chat - Chat avec l'agent")
    logger.info("  POST /api/advisor/confirm - Confirmer des changements") 
    logger.info("  GET  /api/advisor/preferences - Voir les préférences")
    logger.info("  GET  /api/advisor/conversation - Historique")
    logger.info("  GET  /api/advisor/examples - Exemples d'usage")
    logger.info("  🧠 NOUVEAUX ALGORITHMES AVANCÉS:")
    logger.info("  POST /api/advisor/optimize - Optimisation avec algorithmes avancés")
    logger.info("  GET  /api/advisor/recommend-algorithm - Recommandation d'algorithme")
    logger.info("  GET  /api/advisor/analyze-quality - Analyse qualité emploi du temps")
    logger.info("  GET  /api/advisor/algorithms-info - Infos algorithmes disponibles")
    logger.info("  WebSocket sur / pour communication temps réel")
    
    socketio.run(app, host='0.0.0.0', port=5002, debug=True)
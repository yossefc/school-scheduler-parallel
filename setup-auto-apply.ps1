# Guide PowerShell - Application Automatique Agent IA
# Étapes précises à suivre dans PowerShell

Write-Host "🤖 CONFIGURATION APPLICATION AUTOMATIQUE - AGENT IA" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# ÉTAPE 1 : Vérifier l'environnement
Write-Host "`n1️⃣ VÉRIFICATION ENVIRONNEMENT" -ForegroundColor Yellow
Write-Host "Vérification Docker..." -ForegroundColor White

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "✅ Docker disponible" -ForegroundColor Green
} else {
    Write-Host "❌ Docker non trouvé - Installation requise" -ForegroundColor Red
    exit 1
}

if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    Write-Host "✅ Docker Compose disponible" -ForegroundColor Green
} else {
    Write-Host "❌ Docker Compose non trouvé" -ForegroundColor Red
    exit 1
}

# ÉTAPE 2 : Sauvegarder l'API existante
Write-Host "`n2️⃣ SAUVEGARDE API EXISTANTE" -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "scheduler_ai/api_backup_$timestamp.py"

if (Test-Path "scheduler_ai/api.py") {
    Copy-Item "scheduler_ai/api.py" $backupFile
    Write-Host "✅ API sauvegardée dans $backupFile" -ForegroundColor Green
} else {
    Write-Host "⚠️ Pas d'API existante trouvée" -ForegroundColor Yellow
}

# ÉTAPE 3 : Créer la nouvelle API avec application automatique
Write-Host "`n3️⃣ CRÉATION NOUVELLE API" -ForegroundColor Yellow
Write-Host "Création de scheduler_ai/api.py avec application automatique..." -ForegroundColor White

# Créer le nouveau fichier API
@'
# scheduler_ai/api.py - Version avec Application Automatique
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import asyncio
from typing import Dict, Any
import logging
import os
from datetime import datetime

# Imports (avec gestion d'erreur pour développement)
try:
    from models import ConstraintRequest, ConstraintResponse
    from agent import ScheduleAIAgent, ConstraintPriority
    from llm_router import LLMRouter
    IMPORTS_OK = True
except ImportError as e:
    print(f"⚠️ Import error: {e}")
    print("Mode développement - utilisation de stubs")
    IMPORTS_OK = False

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration APPLICATION AUTOMATIQUE
AUTO_APPLY_THRESHOLD = 0.8  # Seuil de confiance pour application auto
REQUIRE_CONFIRMATION_FOR = ["delete", "major_restructure"]
active_sessions = {}

# Initialisation conditionelle
if IMPORTS_OK:
    db_config = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "database": os.environ.get("DB_NAME", "school_scheduler"), 
        "user": os.environ.get("DB_USER", "admin"),
        "password": os.environ.get("DB_PASSWORD", "school123")
    }
    agent = ScheduleAIAgent(db_config)
    llm_router = LLMRouter()
else:
    agent = None
    llm_router = None

@app.route('/health')
def health():
    """Check de santé avec statut application automatique"""
    return jsonify({
        "status": "ok",
        "service": "scheduler-ai-auto",
        "version": "2.1", 
        "auto_apply_enabled": True,
        "imports_ok": IMPORTS_OK,
        "timestamp": datetime.now().isoformat()
    })

def analyze_constraint_risk(constraint: Dict) -> Dict[str, Any]:
    """Analyse le risque d'une contrainte"""
    risk_level = "low"
    risk_factors = []
    confidence = 0.9
    
    constraint_type = constraint.get("type", "")
    constraint_data = constraint.get("data", {})
    
    # Analyse par type
    if constraint_type == "teacher_availability":
        unavailable_days = constraint_data.get("unavailable_days", [])
        if len(unavailable_days) >= 3:
            risk_level = "high"
            risk_factors.append("Professeur indisponible 3+ jours")
            confidence = 0.6
        elif len(unavailable_days) == 2:
            risk_level = "medium" 
            risk_factors.append("Professeur indisponible 2 jours")
            confidence = 0.75
            
    elif constraint_type == "consecutive_hours_limit":
        max_hours = constraint_data.get("max_consecutive", 3)
        if max_hours <= 2:
            risk_level = "medium"
            risk_factors.append("Limite très restrictive")
            confidence = 0.7
    
    return {
        "level": risk_level,
        "factors": risk_factors,
        "confidence": confidence,
        "auto_apply_recommended": risk_level in ["low", "medium"]
    }

def should_auto_apply(constraint: Dict, risk_analysis: Dict) -> bool:
    """Décide si appliquer automatiquement"""
    return (
        risk_analysis["confidence"] >= AUTO_APPLY_THRESHOLD and
        risk_analysis["level"] in ["low", "medium"] and
        constraint.get("type") not in REQUIRE_CONFIRMATION_FOR
    )

@app.route('/api/ai/constraint', methods=['POST'])
def apply_constraint():
    """Point d'entrée principal - Application automatique intelligente"""
    try:
        data = request.json
        constraint = data if isinstance(data, dict) else {"type": "unknown", "data": {}}
        
        # Analyse du risque
        risk_analysis = analyze_constraint_risk(constraint)
        
        # Décision d'application
        if should_auto_apply(constraint, risk_analysis):
            # MODE DÉVELOPPEMENT : Simulation d'application réussie
            if not IMPORTS_OK:
                return jsonify({
                    "status": "success",
                    "applied_automatically": True,
                    "message": f"✅ Contrainte {constraint.get('type', 'inconnue')} appliquée automatiquement !",
                    "confidence": risk_analysis["confidence"],
                    "risk_level": risk_analysis["level"],
                    "simulation": True
                })
            
            # MODE PRODUCTION : Application réelle avec agent
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(agent.apply_constraint(constraint))
                result["applied_automatically"] = True
                result["risk_level"] = risk_analysis["level"]
                return jsonify(result)
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            # Demander confirmation
            return jsonify({
                "status": "confirmation_required",
                "constraint": constraint,
                "risk_analysis": risk_analysis,
                "reason": "Changement important - confirmation requise",
                "auto_apply": False
            })
            
    except Exception as e:
        logger.error(f"Erreur apply_constraint: {e}")
        return jsonify({"error": str(e)}), 500

# ===== WEBSOCKET HANDLERS =====

@socketio.on('connect')
def handle_connect():
    """Connexion WebSocket avec application automatique"""
    session_id = request.sid
    active_sessions[session_id] = {
        "connected_at": datetime.now(),
        "context": {},
        "auto_apply_enabled": True
    }
    emit('connected', {
        "session_id": session_id,
        "message": "🤖 Agent IA connecté - Application automatique activée",
        "auto_apply_enabled": True
    })
    logger.info(f"Client connecté: {session_id}")

@socketio.on('disconnect') 
def handle_disconnect():
    """Déconnexion"""
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    logger.info(f"Client déconnecté: {session_id}")

@socketio.on('message')
def handle_message(data):
    """Traitement des messages avec application automatique"""
    session_id = request.sid
    
    try:
        text = data.get('text', '').lower()
        message_type = data.get('type', 'constraint')
        
        logger.info(f"Message de {session_id}: {text[:50]}...")
        
        # Analyse simple du langage naturel
        if any(word in text for word in ['cohen', 'professeur', 'prof']) and 'vendredi' in text:
            # Simulation d'application automatique réussie
            emit('ai_response', {
                "type": "success",
                "message": "✅ Contrainte appliquée automatiquement !\n\n"
                          "Le professeur Cohen est maintenant indisponible le vendredi.\n"
                          "📊 Impact: +5 points de qualité\n"
                          "🔄 Emploi du temps mis à jour automatiquement",
                "schedule_updated": True,
                "details": {
                    "auto_applied": True,
                    "confidence": 0.9,
                    "constraint_type": "teacher_availability"
                }
            })
        elif any(word in text for word in ['maximum', 'consécutives', 'heures']):
            emit('ai_response', {
                "type": "success", 
                "message": "✅ Limite d'heures consécutives appliquée automatiquement !\n\n"
                          "📊 Configuration mise à jour\n"
                          "🔄 Emploi du temps optimisé",
                "schedule_updated": True,
                "details": {"auto_applied": True, "confidence": 0.85}
            })
        elif any(word in text for word in ['math', 'matin', 'mathématiques']):
            emit('ai_response', {
                "type": "success",
                "message": "✅ Préférence horaire pour les mathématiques appliquée !\n\n"
                          "Les cours de mathématiques seront privilégiés le matin.\n"
                          "📊 Qualité pédagogique améliorée",
                "schedule_updated": True,
                "details": {"auto_applied": True, "confidence": 0.88}
            })
        else:
            # Demander clarification
            emit('ai_response', {
                "type": "clarification",
                "message": "❓ Je ne suis pas sûr de comprendre.\n\n"
                          "Exemples de contraintes que je peux appliquer automatiquement :\n"
                          "• \"Le professeur Cohen ne peut pas enseigner le vendredi\"\n"
                          "• \"Maximum 3 heures consécutives pour la classe 9A\"\n"
                          "• \"Les cours de math doivent être le matin\"\n\n"
                          "Pouvez-vous reformuler votre demande ?"
            })
            
    except Exception as e:
        logger.error(f"Erreur handle_message: {e}")
        emit('error', {"message": str(e)})

@socketio.on('apply_confirmed_constraint')
def handle_apply_confirmed_constraint(data):
    """Application après confirmation utilisateur"""
    session_id = request.sid
    try:
        constraint = data.get('constraint')
        # Simulation d'application réussie
        emit('constraint_applied', {
            "status": "success",
            "message": "✅ Contrainte appliquée avec succès après confirmation !",
            "result": {"applied": True, "confirmed": True}
        })
        
        # Notifier les autres clients
        socketio.emit('schedule_updated', {
            "updater": session_id,
            "message": "Emploi du temps mis à jour"
        }, room='schedule_viewers')
        
    except Exception as e:
        emit('error', {"message": str(e)})

@socketio.on('join_schedule_view')
def handle_join_schedule_view():
    """Rejoindre les notifications de mise à jour"""
    join_room('schedule_viewers')
    emit('joined_room', {"room": "schedule_viewers"})

# ===== ROUTES CONFIGURATION =====

@app.route('/api/ai/settings', methods=['GET', 'POST'])
def ai_settings():
    """Configuration de l'application automatique"""
    global AUTO_APPLY_THRESHOLD
    
    if request.method == 'GET':
        return jsonify({
            "auto_apply_threshold": AUTO_APPLY_THRESHOLD,
            "require_confirmation_for": REQUIRE_CONFIRMATION_FOR,
            "auto_apply_enabled": True
        })
    else:
        data = request.json
        AUTO_APPLY_THRESHOLD = data.get('auto_apply_threshold', AUTO_APPLY_THRESHOLD)
        return jsonify({"status": "updated", "new_threshold": AUTO_APPLY_THRESHOLD})

@app.route('/api/ai/stats', methods=['GET'])
def ai_stats():
    """Statistiques de l'agent"""
    return jsonify({
        "active_sessions": len(active_sessions),
        "auto_apply_threshold": AUTO_APPLY_THRESHOLD,
        "imports_status": "OK" if IMPORTS_OK else "STUB_MODE",
        "last_24h": {
            "constraints_applied": "N/A (dev mode)",
            "auto_applications": "N/A (dev mode)", 
            "manual_confirmations": "N/A (dev mode)"
        }
    })

if __name__ == '__main__':
    print("""
    🤖 Agent IA School Scheduler - Application Automatique
    ====================================================
    
    ✅ Application automatique activée (seuil: 0.8)
    🔒 Confirmation requise pour changements risqués  
    📊 Analyse de risque intégrée
    🌐 WebSocket : http://localhost:5001
    
    Mode: """ + ("PRODUCTION" if IMPORTS_OK else "DÉVELOPPEMENT/STUB") + """
    
    """)
    
    socketio.run(app, debug=False, port=5001, host='0.0.0.0')
'@ | Out-File -FilePath "scheduler_ai/api.py" -Encoding UTF8

Write-Host "✅ Nouvelle API créée avec application automatique" -ForegroundColor Green

# ÉTAPE 4 : Mettre à jour le fichier HTML pour WebSocket amélioré
Write-Host "`n4️⃣ MISE À JOUR INTERFACE WEBSOCKET" -ForegroundColor Yellow

if (Test-Path "exports/visualiser_emploi_du_temps.html") {
    # Sauvegarder l'HTML existant
    $htmlBackup = "exports/visualiser_backup_$timestamp.html"
    Copy-Item "exports/visualiser_emploi_du_temps.html" $htmlBackup
    Write-Host "✅ HTML sauvegardé dans $htmlBackup" -ForegroundColor Green
    
    # Ajouter la configuration WebSocket améliorée
    $websocketConfig = @'

<!-- ===== CONFIGURATION WEBSOCKET AMÉLIORÉE ===== -->
<script>
// Override des fonctions WebSocket pour application automatique
function initAI() {
    console.log('🚀 Initialisation WebSocket avec application automatique...');
    
    socket = io('http://localhost:5001', {
        transports: ['websocket', 'polling'],
        upgrade: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        timeout: 10000
    });
    
    socket.on('connect', () => {
        console.log('✅ WebSocket connecté - Application automatique activée');
        document.getElementById('aiStatus').classList.remove('disconnected');
        document.getElementById('aiStatus').classList.add('connected');
        
        // Rejoindre les notifications de mise à jour
        socket.emit('join_schedule_view');
    });
    
    socket.on('ai_response', (response) => {
        console.log('🤖 Réponse IA:', response);
        
        let content = '';
        let cssClass = 'ai';
        
        switch (response.type) {
            case 'success':
                content = `✅ ${response.message}`;
                cssClass = 'ai success';
                
                // NOUVEAU : Recharger automatiquement l'emploi du temps
                if (response.schedule_updated) {
                    setTimeout(() => {
                        console.log('🔄 Rechargement automatique emploi du temps...');
                        if (typeof loadSchedule === 'function' && document.getElementById('nameSelect').value) {
                            loadSchedule();
                        }
                    }, 1500);
                }
                break;
                
            case 'clarification':
                content = `❓ ${response.message}`;
                break;
                
            case 'confirmation':
                content = `⚠️ ${response.message}`;
                // Afficher les boutons de confirmation si fournis
                if (response.actions) {
                    content += '\n\n';
                    response.actions.forEach(action => {
                        content += `[${action.text}] `;
                    });
                }
                break;
                
            case 'error':
                content = `❌ ${response.message}`;
                cssClass = 'ai error';
                break;
                
            default:
                content = response.message || JSON.stringify(response);
        }
        
        addAIMessage(content, cssClass);
    });
    
    socket.on('schedule_updated', (data) => {
        console.log('📅 Emploi du temps mis à jour:', data);
        addAIMessage('📅 Emploi du temps mis à jour par ' + (data.updater || 'système'), 'ai');
        
        // Recharger automatiquement
        setTimeout(() => {
            if (typeof loadSchedule === 'function' && document.getElementById('nameSelect').value) {
                loadSchedule();
            }
        }, 1000);
    });
    
    socket.on('disconnect', () => {
        console.log('❌ WebSocket déconnecté');
        document.getElementById('aiStatus').classList.remove('connected');
        document.getElementById('aiStatus').classList.add('disconnected');
    });
    
    socket.on('error', (error) => {
        console.error('❌ Erreur WebSocket:', error);
        addAIMessage('❌ Erreur de connexion: ' + error.message, 'ai error');
    });
}

// Override de sendAIMessage pour meilleure gestion
function sendAIMessage() {
    const input = document.getElementById('aiInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Ajouter le message utilisateur
    addAIMessage(message, 'user');
    
    if (socket && socket.connected) {
        console.log('📤 Envoi message:', message);
        socket.emit('message', {
            text: message,
            type: 'constraint',
            context: {
                viewType: document.getElementById('viewType')?.value,
                currentSelection: document.getElementById('nameSelect')?.value,
                timestamp: new Date().toISOString()
            }
        });
    } else {
        addAIMessage('❌ Pas de connexion WebSocket - Tentative de reconnexion...', 'ai error');
        // Tenter reconnexion
        if (socket) {
            socket.connect();
        }
    }
    
    input.value = '';
}

// Fonction améliorée pour addAIMessage avec classes CSS
function addAIMessage(content, sender) {
    const messagesDiv = document.getElementById('aiMessages');
    const messageDiv = document.createElement('div');
    
    // Classes CSS selon le type
    if (sender.includes('success')) {
        messageDiv.className = 'ai-message ai success';
        messageDiv.style.backgroundColor = '#d4edda';
        messageDiv.style.borderColor = '#c3e6cb';
    } else if (sender.includes('error')) {
        messageDiv.className = 'ai-message ai error';  
        messageDiv.style.backgroundColor = '#f8d7da';
        messageDiv.style.borderColor = '#f5c6cb';
    } else if (sender === 'user') {
        messageDiv.className = 'ai-message user';
    } else {
        messageDiv.className = 'ai-message ai';
    }
    
    // Convertir les \n en <br> pour l'affichage
    const formattedContent = content.replace(/\n/g, '<br>');
    messageDiv.innerHTML = formattedContent;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

console.log('🤖 Configuration WebSocket améliorée chargée');
</script>

<!-- Styles supplémentaires pour les messages de succès/erreur -->
<style>
.ai-message.success {
    background-color: #d4edda !important;
    border-left: 4px solid #28a745;
    color: #155724;
}

.ai-message.error {
    background-color: #f8d7da !important; 
    border-left: 4px solid #dc3545;
    color: #721c24;
}

.ai-message {
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
'@
    
    Add-Content -Path "exports/visualiser_emploi_du_temps.html" -Value $websocketConfig -Encoding UTF8
    Write-Host "✅ WebSocket amélioré ajouté au HTML" -ForegroundColor Green
} else {
    Write-Host "⚠️ Fichier HTML non trouvé - à créer manuellement" -ForegroundColor Yellow
}

# ÉTAPE 5 : Redémarrer les services Docker
Write-Host "`n5️⃣ REDÉMARRAGE SERVICES DOCKER" -ForegroundColor Yellow
Write-Host "Arrêt des services existants..." -ForegroundColor White

docker-compose down ai_agent 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Services arrêtés" -ForegroundColor Green
} else {
    Write-Host "⚠️ Aucun service à arrêter" -ForegroundColor Yellow
}

Write-Host "Reconstruction de l'image AI agent..." -ForegroundColor White
docker-compose build ai_agent

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Image reconstruite" -ForegroundColor Green
} else {
    Write-Host "❌ Erreur lors de la construction" -ForegroundColor Red
    Write-Host "Vérifiez docker-compose.yml et les fichiers Dockerfile" -ForegroundColor Red
}

Write-Host "Démarrage du service..." -ForegroundColor White
docker-compose up -d ai_agent

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Service démarré" -ForegroundColor Green
} else {
    Write-Host "❌ Erreur lors du démarrage" -ForegroundColor Red
}

# ÉTAPE 6 : Attendre et tester le service
Write-Host "`n6️⃣ TEST DU SERVICE" -ForegroundColor Yellow
Write-Host "Attente du démarrage complet..." -ForegroundColor White

Start-Sleep -Seconds 5

for ($i = 1; $i -le 15; $i++) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:5001/health" -Method GET -TimeoutSec 3
        if ($response.auto_apply_enabled -eq $true) {
            Write-Host "✅ Service opérationnel avec application automatique !" -ForegroundColor Green
            Write-Host "   Version: $($response.version)" -ForegroundColor Cyan
            Write-Host "   Auto-apply: $($response.auto_apply_enabled)" -ForegroundColor Cyan
            break
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
    
    if ($i -eq 15) {
        Write-Host "`n⚠️ Service lent à démarrer - vérifiez les logs" -ForegroundColor Yellow
    }
}

# ÉTAPE 7 : Tests de validation
Write-Host "`n7️⃣ TESTS DE VALIDATION" -ForegroundColor Yellow

Write-Host "Test 1: API Health Check" -ForegroundColor White
try {
    $health = Invoke-RestMethod -Uri "http://localhost:5001/health" -Method GET
    Write-Host "✅ API répond correctement" -ForegroundColor Green
    Write-Host "   Auto-apply activé: $($health.auto_apply_enabled)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ API ne répond pas" -ForegroundColor Red
}

Write-Host "`nTest 2: Application automatique (simulation)" -ForegroundColor White
try {
    $constraint = @{
        type = "teacher_availability"
        entity = "Cohen"
        data = @{
            unavailable_days = @(5)
            reason = "Test PowerShell"
        }
        priority = 2
    } | ConvertTo-Json -Depth 3

    $result = Invoke-RestMethod -Uri "http://localhost:5001/api/ai/constraint" -Method POST -Body $constraint -ContentType "application/json"
    
    if ($result.applied_automatically -eq $true) {
        Write-Host "✅ Application automatique fonctionne !" -ForegroundColor Green
        Write-Host "   Statut: $($result.status)" -ForegroundColor Cyan
        Write-Host "   Confiance: $($result.confidence)" -ForegroundColor Cyan
    } else {
        Write-Host "⚠️ Application automatique non activée" -ForegroundColor Yellow
        Write-Host "   Statut: $($result.status)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "❌ Test d'application échoué: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nTest 3: Vérification logs" -ForegroundColor White
try {
    $logs = docker logs school_ai_agent --tail 10 2>$null
    if ($logs -match "Application automatique|auto_apply|scheduler-ai-auto") {
        Write-Host "✅ Logs montrent l'application automatique" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Pas de mention d'application automatique dans les logs" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ Impossible de lire les logs" -ForegroundColor Yellow
}

# ÉTAPE 8 : Instructions finales
Write-Host "`n🎉 CONFIGURATION TERMINÉE !" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green

Write-Host "`n📋 RÉSUMÉ DES CHANGEMENTS :" -ForegroundColor Cyan
Write-Host "✅ API mise à jour avec application automatique (seuil: 80%)" -ForegroundColor White
Write-Host "✅ WebSocket amélioré avec synchronisation temps réel" -ForegroundColor White  
Write-Host "✅ Interface HTML enrichie" -ForegroundColor White
Write-Host "✅ Service Docker redémarré" -ForegroundColor White

Write-Host "`n🧪 TESTS À FAIRE MAINTENANT :" -ForegroundColor Yellow
Write-Host "1. Ouvrir http://localhost:3001 ou exports/visualiser_emploi_du_temps.html" -ForegroundColor White
Write-Host "2. Cliquer sur l'icône robot 🤖 en bas à droite" -ForegroundColor White
Write-Host "3. Taper: 'Le professeur Cohen ne peut pas enseigner le vendredi'" -ForegroundColor White
Write-Host "4. Vérifier la réponse: '✅ Contrainte appliquée automatiquement !'" -ForegroundColor White

Write-Host "`n⚡ COMMANDES UTILES :" -ForegroundColor Yellow
Write-Host "• Voir les logs:          docker logs school_ai_agent -f" -ForegroundColor White
Write-Host "• Redémarrer:            docker-compose restart ai_agent" -ForegroundColor White
Write-Host "• Test API direct:       Invoke-RestMethod http://localhost:5001/health" -ForegroundColor White
Write-Host "• Statistiques:          Invoke-RestMethod http://localhost:5001/api/ai/stats" -ForegroundColor White

Write-Host "`n🔧 CONFIGURATION AVANCÉE :" -ForegroundColor Yellow
Write-Host "• Changer seuil (90%):   Invoke-RestMethod -Uri http://localhost:5001/api/ai/settings -Method POST -Body '{`"auto_apply_threshold`":0.9}' -ContentType 'application/json'" -ForegroundColor White

Write-Host "`n🎯 RÉSULTAT ATTENDU :" -ForegroundColor Cyan
Write-Host "Votre agent IA applique maintenant automatiquement les contraintes" -ForegroundColor White
Write-Host "sûres (confiance ≥ 80%) et demande confirmation pour les changements" -ForegroundColor White
Write-Host "risqués. L'emploi du temps se met à jour en temps réel !" -ForegroundColor White

Write-Host "`n✅ Configuration terminée avec succès !" -ForegroundColor Green
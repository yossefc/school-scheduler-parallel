// ScheduleAdvisor.js - Interface React pour l'agent conseiller
import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './ScheduleAdvisor.css';

const ScheduleAdvisor = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [socket, setSocket] = useState(null);
  const [pendingChanges, setPendingChanges] = useState([]);
  const [userPreferences, setUserPreferences] = useState([]);
  const [showExamples, setShowExamples] = useState(false);
  const [examples, setExamples] = useState(null);
  const messagesEndRef = useRef(null);

  // Connexion WebSocket
  useEffect(() => {
    const newSocket = io('http://localhost:5002');
    setSocket(newSocket);

    // Événements WebSocket
    newSocket.on('advisor_ready', (data) => {
      addMessage('assistant', data.message, 'ready');
    });

    newSocket.on('advisor_response', (response) => {
      addMessage('assistant', response.message, 'response');
      
      if (response.proposals && response.proposals.length > 0) {
        setPendingChanges(response.proposals);
      }
      
      setIsLoading(false);
    });

    newSocket.on('changes_result', (result) => {
      addMessage('assistant', result.message, 'confirmation');
      setPendingChanges([]);
      setIsLoading(false);
    });

    newSocket.on('advisor_error', (error) => {
      addMessage('assistant', `Erreur: ${error.message || error.error}`, 'error');
      setIsLoading(false);
    });

    return () => newSocket.close();
  }, []);

  // Auto-scroll vers le bas
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Charger les préférences utilisateur au démarrage
  useEffect(() => {
    loadUserPreferences();
    loadExamples();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const addMessage = (role, content, type = 'default') => {
    const newMessage = {
      id: Date.now(),
      role,
      content,
      type,
      timestamp: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setIsLoading(true);

    // Ajouter le message utilisateur
    addMessage('user', userMessage, 'user');

    // Envoyer via WebSocket si connecté
    if (socket) {
      socket.emit('user_message', {
        message: userMessage,
        context: {
          timestamp: new Date().toISOString(),
          user_name: "User" // Vous pouvez récupérer le nom utilisateur
        }
      });
    } else {
      // Fallback HTTP si WebSocket non disponible
      try {
        const response = await fetch('http://localhost:5002/api/advisor/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMessage,
            context: { timestamp: new Date().toISOString() }
          })
        });

        const data = await response.json();
        
        if (data.success) {
          addMessage('assistant', data.message, 'response');
          if (data.proposals && data.proposals.length > 0) {
            setPendingChanges(data.proposals);
          }
        } else {
          addMessage('assistant', data.message || 'Erreur de communication', 'error');
        }
      } catch (error) {
        addMessage('assistant', 'Erreur de connexion avec l\'agent conseiller', 'error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const confirmChanges = async (changeIds, confirmation = 'yes') => {
    setIsLoading(true);

    if (socket) {
      socket.emit('confirm_changes', {
        change_ids: changeIds,
        confirmation: confirmation
      });
    } else {
      // Fallback HTTP
      try {
        const response = await fetch('http://localhost:5002/api/advisor/confirm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            change_ids: changeIds,
            confirmation: confirmation
          })
        });

        const data = await response.json();
        addMessage('assistant', data.message, 'confirmation');
        setPendingChanges([]);
      } catch (error) {
        addMessage('assistant', 'Erreur lors de la confirmation', 'error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const loadUserPreferences = async () => {
    try {
      const response = await fetch('http://localhost:5002/api/advisor/preferences');
      const data = await response.json();
      if (data.success) {
        setUserPreferences(data.preferences);
      }
    } catch (error) {
      console.error('Erreur chargement préférences:', error);
    }
  };

  const loadExamples = async () => {
    try {
      const response = await fetch('http://localhost:5002/api/advisor/examples');
      const data = await response.json();
      if (data.success) {
        setExamples(data.examples);
      }
    } catch (error) {
      console.error('Erreur chargement exemples:', error);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const useExample = (exampleText) => {
    setInputMessage(exampleText);
    setShowExamples(false);
  };

  return (
    <div className="schedule-advisor">
      <div className="advisor-header">
        <h2>🤖 Agent Conseiller d'Emploi du Temps</h2>
        <div className="advisor-status">
          <span className={`status-dot ${socket ? 'connected' : 'disconnected'}`}></span>
          {socket ? 'Connecté' : 'Déconnecté'}
        </div>
      </div>

      <div className="advisor-main">
        {/* Zone de chat */}
        <div className="chat-container">
          <div className="messages">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.role} ${message.type}`}>
                <div className="message-content">
                  <div className="message-text">
                    {message.content.split('\n').map((line, i) => (
                      <div key={i}>
                        {line.startsWith('**') && line.endsWith('**') ? (
                          <strong>{line.slice(2, -2)}</strong>
                        ) : line.startsWith('*') && line.endsWith('*') ? (
                          <em>{line.slice(1, -1)}</em>
                        ) : (
                          line
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="message-time">{message.timestamp}</div>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="message assistant loading">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Changements en attente */}
          {pendingChanges.length > 0 && (
            <div className="pending-changes">
              <h3>🔄 Modifications Proposées</h3>
              {pendingChanges.map((change, index) => (
                <div key={index} className="change-proposal">
                  <div className="change-description">
                    <strong>{change.description}</strong>
                  </div>
                  <div className="change-details">
                    <div>Confiance: {Math.round(change.confidence_score * 100)}%</div>
                    <div>Classes: {change.affected_classes.join(', ')}</div>
                    <div>Professeurs: {change.affected_teachers.length}</div>
                  </div>
                </div>
              ))}
              
              <div className="change-actions">
                <button 
                  className="btn confirm"
                  onClick={() => confirmChanges(pendingChanges.map(c => c.change_id), 'yes')}
                  disabled={isLoading}
                >
                  ✅ Confirmer les modifications
                </button>
                <button 
                  className="btn cancel"
                  onClick={() => confirmChanges(pendingChanges.map(c => c.change_id), 'no')}
                  disabled={isLoading}
                >
                  ❌ Annuler
                </button>
                <button 
                  className="btn details"
                  onClick={() => setInputMessage('plus de détails sur ces modifications')}
                >
                  📋 Plus de détails
                </button>
              </div>
            </div>
          )}

          {/* Zone de saisie */}
          <div className="input-container">
            <div className="input-actions">
              <button 
                className="btn-icon examples"
                onClick={() => setShowExamples(!showExamples)}
                title="Voir des exemples"
              >
                💡
              </button>
            </div>
            
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tapez votre demande ici... (ex: 'peux-tu éliminer les trous dans l'emploi du temps de ז-1 ?')"
              rows="2"
              disabled={isLoading}
            />
            
            <button 
              className="btn send"
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading}
            >
              Envoyer
            </button>
          </div>
        </div>

        {/* Panneau latéral */}
        <div className="sidebar">
          {/* Exemples */}
          {showExamples && examples && (
            <div className="examples-panel">
              <h3>💡 Exemples d'utilisation</h3>
              
              <div className="example-category">
                <h4>Demandes simples</h4>
                {examples.simple_requests.map((example, i) => (
                  <div key={i} className="example-item" onClick={() => useExample(example)}>
                    "{example}"
                  </div>
                ))}
              </div>

              <div className="example-category">
                <h4>Préférences</h4>
                {examples.preferences.map((example, i) => (
                  <div key={i} className="example-item" onClick={() => useExample(example)}>
                    "{example}"
                  </div>
                ))}
              </div>

              <div className="example-category">
                <h4>Demandes complexes</h4>
                {examples.complex_requests.map((example, i) => (
                  <div key={i} className="example-item" onClick={() => useExample(example)}>
                    "{example}"
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Préférences utilisateur */}
          <div className="user-preferences">
            <h3>📝 Mes Préférences</h3>
            {userPreferences.total_preferences ? (
              <div>
                <div className="pref-summary">
                  Total: {userPreferences.total_preferences} règles actives
                </div>
                {Object.entries(userPreferences.categories || {}).map(([category, prefs]) => (
                  <div key={category} className="pref-category">
                    <strong>{category}</strong>
                    {prefs.slice(0, 3).map((pref, i) => (
                      <div key={i} className="pref-item">
                        {pref.rule.substring(0, 60)}...
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <p>Aucune préférence enregistrée. Mentionnez vos règles dans la conversation !</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScheduleAdvisor;
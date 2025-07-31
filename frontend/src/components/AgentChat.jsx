import React, { useState, useEffect, useRef } from 'react';

const AgentChat = ({ socket, connected }) => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [pendingPlan, setPendingPlan] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (!socket) return;

    socket.on('ai_response', (response) => {
      setIsTyping(false);
      handleAIResponse(response);
    });

    socket.on('schedule_updated', (data) => {
      addSystemMessage('📋 Emploi du temps mis à jour !');
    });

    return () => {
      if (socket) {
        socket.off('ai_response');
        socket.off('schedule_updated');
      }
    };
  }, [socket]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleAIResponse = (response) => {
    const aiMessage = {
      id: Date.now(),
      type: 'ai',
      content: response.message,
      timestamp: new Date(),
      metadata: response
    };

    setMessages(prev => [...prev, aiMessage]);

    // Si l'IA propose un plan d'action
    if (response.plan) {
      setPendingPlan({
        id: response.plan_id,
        constraint: response.constraint,
        actions: response.plan
      });
    }

    // Si mise à jour automatique
    if (response.applied_automatically) {
      addSystemMessage(`✅ Contrainte appliquée automatiquement (confiance: ${response.confidence})`);
    }
  };

  const addSystemMessage = (text) => {
    setMessages(prev => [...prev, {
      id: Date.now(),
      type: 'system',
      content: text,
      timestamp: new Date()
    }]);
  };

  const sendMessage = () => {
    if (!inputText.trim() || !connected || !socket) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    socket.emit('message', {
      text: inputText,
      context: {}
    });

    setInputText('');
  };

  const applyPlan = () => {
    if (!pendingPlan || !socket) return;

    socket.emit('apply_plan', {
      plan_id: pendingPlan.id,
      constraint: pendingPlan.constraint
    });

    setPendingPlan(null);
    addSystemMessage('📋 Application du plan en cours...');
  };

  const renderMessage = (message) => {
    const isAI = message.type === 'ai';
    const isSystem = message.type === 'system';

    return (
      <div key={message.id} style={{ 
        display: 'flex', 
        gap: '12px', 
        justifyContent: isAI ? 'flex-start' : isSystem ? 'center' : 'flex-end',
        marginBottom: '16px'
      }}>
        {isAI && (
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: '#e3f2fd',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            🤖
          </div>
        )}
        
        <div style={{ maxWidth: isSystem ? '100%' : '70%' }}>
          <div style={{
            borderRadius: '12px',
            padding: '12px 16px',
            backgroundColor: isAI ? '#f5f5f5' : isSystem ? '#e3f2fd' : '#2196f3',
            color: isAI ? '#333' : isSystem ? '#1976d2' : 'white',
            fontSize: isSystem ? '14px' : '16px',
            fontStyle: isSystem ? 'italic' : 'normal'
          }}>
            <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{message.content}</p>
            
            {/* Badges de modèle */}
            {message.metadata?.model_used && (
              <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                {message.metadata.model_used.includes('gpt-4o') && (
                  <span style={{
                    fontSize: '12px',
                    backgroundColor: '#e8f5e8',
                    color: '#2e7d32',
                    padding: '4px 8px',
                    borderRadius: '12px'
                  }}>
                    ⚡ GPT-4o
                  </span>
                )}
                {message.metadata.model_used.includes('claude') && (
                  <span style={{
                    fontSize: '12px',
                    backgroundColor: '#f3e5f5',
                    color: '#7b1fa2',
                    padding: '4px 8px',
                    borderRadius: '12px'
                  }}>
                    🧠 Claude
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>

        {!isAI && !isSystem && (
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: '#2196f3',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            👤
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
      overflow: 'hidden'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #e0e0e0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: '#f8f9fa'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '20px' }}>🤖</span>
          <h3 style={{ margin: 0, fontWeight: 'bold' }}>Assistant IA</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: connected ? '#4CAF50' : '#f44336'
          }} />
          <span style={{ fontSize: '14px', color: '#666' }}>
            {connected ? 'Connecté' : 'Déconnecté'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px',
        backgroundColor: '#fafafa'
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#666', marginTop: '32px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🤖</div>
            <p>Bonjour ! Je suis votre assistant pour la gestion des emplois du temps.</p>
            <p style={{ fontSize: '14px', marginTop: '8px', color: '#999' }}>
              Essayez : "Le professeur Cohen ne peut pas enseigner le vendredi"
            </p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {isTyping && (
          <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              backgroundColor: '#e3f2fd',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              🤖
            </div>
            <div style={{
              backgroundColor: '#f5f5f5',
              borderRadius: '12px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center'
            }}>
              <span>💭 En train d'écrire...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Plan d'action en attente */}
      {pendingPlan && (
        <div style={{
          margin: '0 16px 12px',
          padding: '12px',
          backgroundColor: '#fff3cd',
          border: '1px solid #ffeaa7',
          borderRadius: '8px'
        }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span style={{ fontSize: '20px' }}>⚠️</span>
            <div style={{ flex: 1 }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: 'bold', color: '#856404' }}>
                Plan d'action proposé :
              </p>
              <ul style={{ margin: '0 0 12px 0', padding: '0 0 0 20px', color: '#856404' }}>
                {pendingPlan.actions.map((action, idx) => (
                  <li key={idx}>{action.action}</li>
                ))}
              </ul>
              <button
                onClick={applyPlan}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#ffc107',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Appliquer le plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{ padding: '16px', borderTop: '1px solid #e0e0e0' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Décrivez votre contrainte..."
            style={{
              flex: 1,
              padding: '12px',
              border: '1px solid #ddd',
              borderRadius: '8px',
              fontSize: '16px',
              outline: 'none'
            }}
            disabled={!connected}
          />
          <button
            onClick={sendMessage}
            disabled={!connected || !inputText.trim()}
            style={{
              padding: '12px 16px',
              backgroundColor: connected && inputText.trim() ? '#2196f3' : '#ccc',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: connected && inputText.trim() ? 'pointer' : 'not-allowed',
              fontSize: '16px'
            }}
          >
            📤
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgentChat;
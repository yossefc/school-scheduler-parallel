import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Loader, Check, AlertCircle } from 'lucide-react';
import io from 'socket.io-client';

const AgentChat = ({ scheduleId, onScheduleUpdate }) => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [pendingPlan, setPendingPlan] = useState(null);
  const messagesEndRef = useRef(null);
  const socketRef = useRef(null);

  useEffect(() => {
    // Connexion WebSocket
    socketRef.current = io('http://localhost:5001', {
      transports: ['websocket', 'polling']
    });

    socketRef.current.on('connect', () => {
      setIsConnected(true);
      console.log('Connecté à l\'agent IA');
    });

    socketRef.current.on('disconnect', () => {
      setIsConnected(false);
    });

    socketRef.current.on('ai_response', (response) => {
      setIsTyping(false);
      handleAIResponse(response);
    });

    socketRef.current.on('schedule_updated', (data) => {
      if (onScheduleUpdate) {
        onScheduleUpdate(data.result);
      }
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

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
    if (!inputText.trim() || !isConnected) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputText,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    socketRef.current.emit('message', {
      text: inputText,
      context: { scheduleId }
    });

    setInputText('');
  };

  const applyPlan = () => {
    if (!pendingPlan) return;

    socketRef.current.emit('apply_plan', {
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
      <div
        key={message.id}
        className={`flex gap-3 ${isAI ? '' : 'justify-end'} ${isSystem ? 'justify-center' : ''}`}
      >
        {isAI && (
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-blue-600" />
          </div>
        )}
        
        <div className={`max-w-[70%] ${isSystem ? 'max-w-full' : ''}`}>
          <div
            className={`rounded-lg px-4 py-2 ${
              isAI ? 'bg-gray-100 text-gray-800' :
              isSystem ? 'bg-blue-50 text-blue-700 text-sm italic' :
              'bg-blue-600 text-white'
            }`}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
            
            {/* Badges de modèle */}
            {message.metadata?.model_used && (
              <div className="mt-2 flex gap-2">
                {message.metadata.model_used.includes('gpt-4o') && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
                    ⚡ Rapide
                  </span>
                )}
                {message.metadata.model_used.includes('claude') && (
                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">
                    🔍 Analyse profonde
                  </span>
                )}
              </div>
            )}
          </div>
          
          <div className="text-xs text-gray-500 mt-1">
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>

        {!isAI && !isSystem && (
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
            <User className="w-5 h-5 text-white" />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold">Assistant IA</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {isConnected ? 'Connecté' : 'Déconnecté'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <Bot className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>Bonjour ! Je suis votre assistant pour la gestion des emplois du temps.</p>
            <p className="text-sm mt-2">Essayez : "Le professeur Cohen ne peut pas enseigner le vendredi"</p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {isTyping && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
              <Bot className="w-5 h-5 text-blue-600" />
            </div>
            <div className="bg-gray-100 rounded-lg px-4 py-2">
              <Loader className="w-4 h-4 animate-spin text-gray-600" />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Plan d'action en attente */}
      {pendingPlan && (
        <div className="mx-4 mb-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-800">Plan d'action proposé :</p>
              <ul className="text-sm text-yellow-700 mt-1 space-y-1">
                {pendingPlan.actions.map((action, idx) => (
                  <li key={idx}>• {action.action}</li>
                ))}
              </ul>
              <button
                onClick={applyPlan}
                className="mt-2 px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 transition-colors"
              >
                Appliquer le plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Décrivez votre contrainte..."
            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={!isConnected}
          />
          <button
            onClick={sendMessage}
            disabled={!isConnected || !inputText.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgentChat;
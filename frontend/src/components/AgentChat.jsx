import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, AlertCircle, Check, Clock, Zap, Search } from 'lucide-react';
import { useScheduleAI } from '../hooks/useScheduleAI';

const AgentChat = ({ scheduleId, onScheduleUpdate }) => {
  const [message, setMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  
  const {
    messages,
    isConnected,
    sendMessage,
    sendConstraint,
    applyPlan,
    currentPlan
  } = useScheduleAI(scheduleId);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = () => {
    if (!message.trim()) return;
    
    // Détecter le type de message
    const messageType = detectMessageType(message);
    sendMessage(message, messageType);
    setMessage('');
  };

  const detectMessageType = (text) => {
    const constraintKeywords = ['peut pas', 'disponible', 'préfère', 'éviter', 'לא יכול', 'עדיף'];
    const hasConstraintKeyword = constraintKeywords.some(kw => 
      text.toLowerCase().includes(kw)
    );
    
    return hasConstraintKeyword ? 'constraint' : 'question';
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderMessage = (msg) => {
    const isAI = msg.sender === 'ai';
    
    return (
      <div
        key={msg.id}
        className={`flex ${isAI ? 'justify-start' : 'justify-end'} mb-4`}
      >
        <div className={`flex max-w-3xl ${isAI ? '' : 'flex-row-reverse'}`}>
          <div className={`flex-shrink-0 ${isAI ? 'mr-3' : 'ml-3'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              isAI ? 'bg-indigo-500' : 'bg-gray-400'
            }`}>
              {isAI ? <Bot size={18} className="text-white" /> : <User size={18} className="text-white" />}
            </div>
          </div>
          
          <div className={`flex flex-col ${isAI ? '' : 'items-end'}`}>
            <div className={`rounded-lg px-4 py-2 ${
              isAI ? 'bg-gray-100 text-gray-800' : 'bg-indigo-500 text-white'
            }`}>
              {msg.type === 'plan' ? (
                <PlanDisplay plan={msg.content} onApply={() => applyPlan(msg.content)} />
              ) : msg.type === 'error' ? (
                <ErrorDisplay error={msg.content} />
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
            </div>
            
            <div className="text-xs text-gray-500 mt-1">
              {formatTime(msg.timestamp)}
              {msg.model && (
                <span className="ml-2">
                  {msg.model.includes('gpt') ? '⚡' : '🔍'} {msg.model}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">Assistant IA</h3>
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`} />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connecté' : 'Déconnecté'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <Bot size={48} className="mx-auto mb-4 text-gray-400" />
            <p className="text-lg mb-2">Bonjour ! Je suis votre assistant IA.</p>
            <p className="text-sm">
              Je peux vous aider à gérer les contraintes d'emploi du temps.
              Essayez : "Le professeur Cohen ne peut pas enseigner le vendredi"
            </p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-2">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-200">
        <div className="flex space-x-4">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Tapez votre message..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            disabled={!isConnected}
          />
          <button
            onClick={handleSend}
            disabled={!isConnected || !message.trim()}
            className="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
        
        <div className="mt-2 flex flex-wrap gap-2">
          {quickActions.map((action) => (
            <button
              key={action.id}
              onClick={() => setMessage(action.text)}
              className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

// Composant pour afficher un plan
const PlanDisplay = ({ plan, onApply }) => {
  const [expanded, setExpanded] = useState(true);
  
  return (
    <div className="space-y-3">
      <div className="font-medium mb-2">{plan.thoughts}</div>
      
      <div className="space-y-2">
        {plan.steps.map((step, index) => (
          <div key={index} className="flex items-start space-x-2">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
              getPriorityColor(step.priority)
            }`}>
              {index + 1}
            </div>
            <div className="flex-1">
              <div className="text-sm font-medium">{step.description}</div>
              {step.affected_entities && (
                <div className="text-xs text-gray-600 mt-1">
                  Affecte : {step.affected_entities.join(', ')}
                </div>
              )}
              {step.priority_impact && (
                <div className="text-xs text-gray-600">
                  Impact : {step.priority_impact}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
        <p className="text-sm text-blue-800 mb-3">{plan.ask_user}</p>
        <div className="flex space-x-2">
          <button
            onClick={onApply}
            className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 text-sm"
          >
            <Check size={16} className="inline mr-1" />
            Appliquer
          </button>
          <button
            onClick={() => {}}
            className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 text-sm"
          >
            Modifier
          </button>
        </div>
      </div>
    </div>
  );
};

// Composant pour afficher une erreur
const ErrorDisplay = ({ error }) => (
  <div className="flex items-start space-x-2 text-red-700">
    <AlertCircle size={20} className="flex-shrink-0 mt-0.5" />
    <div>
      <div className="font-medium">Erreur</div>
      <div className="text-sm mt-1">{error.message || error}</div>
    </div>
  </div>
);

// Helpers
const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('fr-FR', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });
};

const getPriorityColor = (priority) => {
  const colors = {
    0: 'bg-red-500 text-white',      // HARD
    1: 'bg-orange-500 text-white',   // VERY_STRONG
    2: 'bg-yellow-500 text-white',   // MEDIUM
    3: 'bg-blue-500 text-white',     // NORMAL
    4: 'bg-green-500 text-white',    // LOW
    5: 'bg-gray-400 text-white'      // MINIMAL
  };
  return colors[priority] || colors[3];
};

const quickActions = [
  { id: 1, label: "Disponibilité prof", text: "Le professeur " },
  { id: 2, label: "Préférence horaire", text: "Je préférerais que les cours de " },
  { id: 3, label: "Éviter fin de journée", text: "Éviter de placer " },
  { id: 4, label: "Cours consécutifs", text: "Maximum 2 heures consécutives de " }
];

export default AgentChat;
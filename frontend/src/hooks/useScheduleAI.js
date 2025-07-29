import { useState, useEffect, useCallback, useRef } from 'react';
import io from 'socket.io-client';

const SOCKET_URL = process.env.REACT_APP_AI_SOCKET_URL || 'http://localhost:5001';

export const useScheduleAI = (scheduleId) => {
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  const socketRef = useRef(null);
  const messageIdCounter = useRef(0);

  useEffect(() => {
    // Initialiser la connexion Socket.IO
    socketRef.current = io(SOCKET_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    const socket = socketRef.current;

    // Event handlers
    socket.on('connect', () => {
      console.log('Connected to AI agent');
      setIsConnected(true);
      
      // Rejoindre la room des viewers
      socket.emit('join_schedule_view');
      
      // Envoyer le contexte initial
      socket.emit('context', {
        scheduleId,
        language: 'fr'
      });
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from AI agent');
      setIsConnected(false);
    });

    socket.on('ai_response', (response) => {
      handleAIResponse(response);
      setIsProcessing(false);
    });

    socket.on('error', (error) => {
      addMessage({
        type: 'error',
        content: error,
        sender: 'ai'
      });
      setIsProcessing(false);
    });

    socket.on('schedule_updated', (update) => {
      if (update.updater !== socket.id) {
        addMessage({
          type: 'notification',
          content: 'L\'emploi du temps a été mis à jour par un autre utilisateur.',
          sender: 'system'
        });
      }
    });

    // Cleanup
    return () => {
      socket.disconnect();
    };
  }, [scheduleId]);

  const addMessage = useCallback((message) => {
    const newMessage = {
      id: ++messageIdCounter.current,
      timestamp: new Date().toISOString(),
      ...message
    };
    
    setMessages(prev => [...prev, newMessage]);
    return newMessage;
  }, []);

  const handleAIResponse = useCallback((response) => {
    const { type, message, thoughts, plan, ask_user, details, model } = response;
    
    let content;
    switch (type) {
      case 'plan':
        content = {
          thoughts,
          steps: plan,
          ask_user
        };
        setCurrentPlan(content);
        break;
        
      case 'clarification':
        content = message;
        break;
        
      case 'success':
        content = `${message}\n${details ? JSON.stringify(details, null, 2) : ''}`;
        break;
        
      case 'answer':
        content = message;
        break;
        
      default:
        content = response;
    }
    
    addMessage({
      type,
      content,
      sender: 'ai',
      model: model || 'unknown'
    });
  }, [addMessage]);

  const sendMessage = useCallback((text, messageType = 'question') => {
    if (!socketRef.current || !isConnected) {
      console.error('Socket not connected');
      return;
    }
    
    // Ajouter le message de l'utilisateur
    addMessage({
      type: 'user',
      content: text,
      sender: 'user'
    });
    
    setIsProcessing(true);
    
    // Envoyer au serveur
    socketRef.current.emit('message', {
      text,
      type: messageType,
      context: {
        scheduleId,
        pending_plan: currentPlan,
        language: 'fr'
      }
    });
  }, [isConnected, currentPlan, scheduleId, addMessage]);

  const sendConstraint = useCallback(async (constraint) => {
    if (!isConnected) {
      throw new Error('Not connected to AI agent');
    }
    
    setIsProcessing(true);
    
    try {
      const response = await fetch(`${SOCKET_URL}/api/ai/constraint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ constraint })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      // Ajouter le résultat comme message
      addMessage({
        type: result.status === 'success' ? 'success' : 'error',
        content: result,
        sender: 'ai'
      });
      
      return result;
      
    } catch (error) {
      addMessage({
        type: 'error',
        content: { message: error.message },
        sender: 'ai'
      });
      throw error;
    } finally {
      setIsProcessing(false);
    }
  }, [isConnected, addMessage]);

  const applyPlan = useCallback((plan) => {
    if (!socketRef.current || !isConnected) {
      console.error('Socket not connected');
      return;
    }
    
    setIsProcessing(true);
    
    socketRef.current.emit('apply_plan', {
      plan_id: plan.id,
      constraint: plan.constraint
    });
  }, [isConnected]);

  const parseNaturalConstraint = useCallback(async (text, language = 'fr') => {
    try {
      const response = await fetch(`${SOCKET_URL}/api/ai/constraints/natural`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text, language })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('Error parsing natural constraint:', error);
      throw error;
    }
  }, []);

  const getConstraintHistory = useCallback(async (limit = 50, offset = 0) => {
    try {
      const response = await fetch(
        `${SOCKET_URL}/api/ai/history?limit=${limit}&offset=${offset}`
      );
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
      
    } catch (error) {
      console.error('Error fetching history:', error);
      throw error;
    }
  }, []);

  const explainConflict = useCallback(async (conflictId) => {
    try {
      const response = await fetch(`${SOCKET_URL}/api/ai/explain/${conflictId}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const explanation = await response.json();
      
      // Ajouter l'explication comme message
      addMessage({
        type: 'explanation',
        content: explanation,
        sender: 'ai'
      });
      
      return explanation;
      
    } catch (error) {
      console.error('Error explaining conflict:', error);
      throw error;
    }
  }, [addMessage]);

  const getSuggestions = useCallback(async () => {
    try {
      const response = await fetch(`${SOCKET_URL}/api/ai/suggestions`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      return data.suggestions;
      
    } catch (error) {
      console.error('Error getting suggestions:', error);
      throw error;
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    messageIdCounter.current = 0;
  }, []);

  const exportChat = useCallback(() => {
    const chatData = {
      scheduleId,
      exportedAt: new Date().toISOString(),
      messages: messages.map(msg => ({
        ...msg,
        // Nettoyer les données sensibles si nécessaire
      }))
    };
    
    const blob = new Blob([JSON.stringify(chatData, null, 2)], {
      type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-export-${scheduleId}-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [messages, scheduleId]);

  return {
    // État
    messages,
    isConnected,
    currentPlan,
    isProcessing,
    
    // Actions principales
    sendMessage,
    sendConstraint,
    applyPlan,
    
    // Actions utilitaires
    parseNaturalConstraint,
    getConstraintHistory,
    explainConflict,
    getSuggestions,
    
    // Gestion des messages
    clearMessages,
    exportChat,
    
    // Socket direct (pour cas avancés)
    socket: socketRef.current
  };
}
import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import axios from 'axios';
import AgentChat from './components/AgentChat';

const API_URL = 'http://localhost:8000/api';
const AI_SOCKET_URL = 'http://localhost:5001';

// Configuration des jours et périodes
const DAYS = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי'];
const PERIODS = 10;
const PERIOD_TIMES = {
  1: '08:00-08:45',
  2: '08:50-09:35',
  3: '09:40-10:25',
  4: '10:30-10:45',
  5: '10:45-11:30',
  6: '11:35-12:20',
  7: '12:25-13:10',
  8: '13:15-14:00',
  9: '14:05-14:50',
  10: '14:55-15:40'
};

function App() {
  // États pour l'emploi du temps
  const [currentSchedule, setCurrentSchedule] = useState([]);
  const [allClasses, setAllClasses] = useState([]);
  const [allTeachers, setAllTeachers] = useState([]);
  const [viewType, setViewType] = useState('class');
  const [selectedName, setSelectedName] = useState('');
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // États pour l'agent IA
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [aiPanelVisible, setAiPanelVisible] = useState(false);

  // Initialisation
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      // Charger les statistiques
      const statsResponse = await axios.get(`${API_URL}/stats`);
      setStats(statsResponse.data);

      // Charger les listes
      const classesResponse = await axios.get(`${API_URL}/classes`);
      setAllClasses(classesResponse.data.classes || []);

      const teachersResponse = await axios.get(`${API_URL}/teachers`);
      setAllTeachers(teachersResponse.data.teachers || []);

      // Initialiser l'agent IA
      initializeAI();

    } catch (error) {
      console.error('Erreur lors du chargement:', error);
      setError('Erreur de connexion au serveur');
    }
  };

  const initializeAI = () => {
    const newSocket = io(AI_SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    newSocket.on('connect', () => {
      setConnected(true);
      // Envoyer le contexte initial
      newSocket.emit('context', {
        scheduleId: 'current',
        language: 'he',
        classes: allClasses,
        teachers: allTeachers
      });
    });

    newSocket.on('disconnect', () => {
      setConnected(false);
    });

    newSocket.on('schedule_updated', () => {
      showNotification('✅ המערכת עודכנה בהצלחה!', 'success');
      if (currentSchedule.length > 0) {
        setTimeout(() => loadSchedule(), 1000);
      }
    });

    setSocket(newSocket);

    return () => newSocket.close();
  };

  const loadSchedule = async () => {
    if (!selectedName) {
      alert('אנא בחר כיתה או מורה');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.get(`${API_URL}/schedule/${viewType}/${encodeURIComponent(selectedName)}`);
      setCurrentSchedule(response.data.schedule || []);
    } catch (error) {
      setError('שגיאה בטעינת הנתונים');
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportToExcel = () => {
    if (currentSchedule.length === 0) {
      alert('אין נתונים לייצוא');
      return;
    }

    let csv = '\ufeff'; // BOM pour UTF-8
    csv += 'יום,שעה,מקצוע,';
    csv += viewType === 'class' ? 'מורה\n' : 'כיתה\n';

    currentSchedule.forEach(lesson => {
      const day = DAYS[lesson.day_of_week];
      const data = viewType === 'class' ? lesson.teacher_name : lesson.class_name;
      csv += `${day},${lesson.period_number},${lesson.subject_name},${data}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `מערכת_${selectedName}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  const refreshData = () => {
    showNotification('🔄 מרענן נתונים...', 'success');
    initializeApp();
  };

  const showNotification = (message, type) => {
    // Implémentation simple de notification
    console.log(`${type}: ${message}`);
  };

  const renderScheduleTable = () => {
    if (loading) {
      return <div style={styles.loading}>טוען מערכת שעות...</div>;
    }

    if (error) {
      return <div style={styles.error}>שגיאה: {error}</div>;
    }

    if (currentSchedule.length === 0) {
      return <div style={styles.loading}>בחר כיתה או מורה לצפייה במערכת השעות</div>;
    }

    return (
      <div>
        <h2 style={styles.scheduleTitle}>מערכת שעות - {selectedName}</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>שעה</th>
              {DAYS.map(day => (
                <th key={day} style={styles.th}>{day}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({length: PERIODS}, (_, period) => (
              <tr key={period + 1}>
                <td style={{...styles.td, ...styles.periodHeader}}>
                  <strong>{period + 1}</strong>
                  <div style={styles.periodTime}>{PERIOD_TIMES[period + 1] || ''}</div>
                </td>
                {DAYS.map((_, day) => {
                  const lesson = currentSchedule.find(l => 
                    l.day_of_week === day && l.period_number === period + 1
                  );
                  
                  if (lesson) {
                    return (
                      <td key={day} style={styles.td}>
                        <div style={styles.subject}>{lesson.subject_name}</div>
                        <div style={styles.teacher}>
                          {viewType === 'class' ? lesson.teacher_name : lesson.class_name}
                        </div>
                      </td>
                    );
                  } else if (period + 1 === 4) {
                    return <td key={day} style={{...styles.td, ...styles.breakCell}}>הפסקה</td>;
                  } else {
                    return <td key={day} style={{...styles.td, ...styles.emptySlot}}>-</td>;
                  }
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={styles.container} dir="rtl">
      <div style={styles.mainContent}>
        <h1 style={styles.title}>מערכת שעות בית ספרית - עם עוזר AI</h1>
        
        {/* Statistiques */}
        <div style={styles.stats}>
          {stats ? (
            <>
              <span>כיתות: {stats.general?.total_classes || 0}</span>
              <span>מורים: {stats.general?.total_teachers || 0}</span>
              <span>שיעורים: {stats.general?.total_lessons || 0}</span>
              <span>מקצועות: {stats.general?.total_subjects || 0}</span>
            </>
          ) : (
            <span>טוען נתונים...</span>
          )}
        </div>

        {/* Contrôles */}
        <div style={styles.controls}>
          <select 
            value={viewType} 
            onChange={(e) => setViewType(e.target.value)}
            style={styles.select}
          >
            <option value="class">תצוגה לפי כיתה</option>
            <option value="teacher">תצוגה לפי מורה</option>
          </select>
          
          <select 
            value={selectedName} 
            onChange={(e) => setSelectedName(e.target.value)}
            style={styles.select}
          >
            <option value="">בחר...</option>
            {(viewType === 'class' ? allClasses : allTeachers).map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          
          <button onClick={loadSchedule} style={styles.button}>הצג מערכת</button>
          <button onClick={exportToExcel} style={styles.button}>ייצא לאקסל</button>
          <button onClick={() => window.print()} style={styles.button}>הדפס</button>
          <button onClick={refreshData} style={styles.button}>רענן נתונים</button>
        </div>

        {/* Tableau des emplois du temps */}
        <div style={styles.scheduleContainer}>
          {renderScheduleTable()}
        </div>
      </div>

      {/* Bouton AI Toggle */}
      {!aiPanelVisible && (
        <div style={styles.aiToggle} onClick={() => setAiPanelVisible(true)}>
          🤖
        </div>
      )}

      {/* Panel AI */}
      {aiPanelVisible && (
        <div style={styles.aiPanel}>
          <div style={styles.aiHeader} onClick={() => setAiPanelVisible(false)}>
            <h3 style={styles.aiHeaderTitle}>
              🤖 עוזר AI לתכנון
            </h3>
            <div style={{
              ...styles.aiStatus,
              backgroundColor: connected ? '#4CAF50' : '#f44336'
            }}></div>
          </div>
          <AgentChat socket={socket} connected={connected} />
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    fontFamily: 'Arial, sans-serif',
    margin: '20px',
    backgroundColor: '#f5f5f5',
    minHeight: '100vh',
  },
  mainContent: {
    maxWidth: '1400px',
    margin: '0 auto',
    background: 'white',
    padding: '20px',
    borderRadius: '10px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
  },
  title: {
    color: '#333',
    textAlign: 'center',
    marginBottom: '30px',
    fontSize: '2.5em',
  },
  stats: {
    background: '#e3f2fd',
    padding: '15px',
    borderRadius: '8px',
    marginBottom: '20px',
    textAlign: 'center',
  },
  controls: {
    marginBottom: '20px',
    textAlign: 'center',
    background: '#f5f5f5',
    padding: '15px',
    borderRadius: '8px',
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  select: {
    padding: '12px',
    fontSize: '16px',
    border: '2px solid #ddd',
    borderRadius: '5px',
    background: 'white',
    minWidth: '200px',
  },
  button: {
    padding: '12px 24px',
    fontSize: '16px',
    backgroundColor: '#4CAF50',
    color: 'white',
    border: 'none',
    borderRadius: '5px',
    cursor: 'pointer',
    transition: 'all 0.3s',
  },
  scheduleContainer: {
    marginTop: '20px',
  },
  scheduleTitle: {
    textAlign: 'center',
    marginBottom: '20px',
    color: '#333',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '14px',
  },
  th: {
    border: '1px solid #ddd',
    padding: '10px',
    textAlign: 'center',
    backgroundColor: '#2196F3',
    color: 'white',
    fontWeight: 'bold',
  },
  td: {
    border: '1px solid #ddd',
    padding: '10px',
    textAlign: 'center',
    backgroundColor: '#fff',
    minHeight: '60px',
  },
  periodHeader: {
    backgroundColor: '#f5f5f5',
    fontWeight: 'bold',
  },
  periodTime: {
    fontSize: '11px',
    color: '#666',
  },
  subject: {
    fontWeight: 'bold',
    color: '#1976d2',
    fontSize: '16px',
    marginBottom: '5px',
  },
  teacher: {
    fontSize: '13px',
    color: '#666',
  },
  breakCell: {
    backgroundColor: '#ffe0b2',
    color: '#e65100',
    fontStyle: 'italic',
  },
  emptySlot: {
    backgroundColor: '#fafafa',
    color: '#ccc',
  },
  loading: {
    textAlign: 'center',
    padding: '50px',
    fontSize: '18px',
    color: '#666',
  },
  error: {
    backgroundColor: '#ffebee',
    color: '#c62828',
    padding: '15px',
    borderRadius: '5px',
    textAlign: 'center',
  },
  aiToggle: {
    position: 'fixed',
    bottom: '20px',
    left: '20px',
    width: '60px',
    height: '60px',
    backgroundColor: '#2196F3',
    color: 'white',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: '0 3px 15px rgba(33,150,243,0.4)',
    fontSize: '24px',
    zIndex: 999,
  },
  aiPanel: {
    position: 'fixed',
    bottom: '20px',
    left: '20px',
    width: '400px',
    height: '600px',
    backgroundColor: 'white',
    borderRadius: '15px',
    boxShadow: '0 5px 25px rgba(0,0,0,0.3)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1000,
  },
  aiHeader: {
    background: 'linear-gradient(135deg, #2196F3, #1976d2)',
    color: 'white',
    padding: '15px 20px',
    borderRadius: '15px 15px 0 0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
  },
  aiHeaderTitle: {
    margin: 0,
    fontSize: '18px',
  },
  aiStatus: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    marginLeft: '10px',
  },
};

export default App; 
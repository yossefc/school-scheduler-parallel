import React from 'react';
import AgentChat from './components/AgentChat';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>🎓 School Scheduler AI</h1>
      </header>
      <main>
        <div className="container">
          <div className="schedule-view">
            {/* Ici sera l'emploi du temps */}
            <h2>Emploi du temps</h2>
            <p>L'interface d'emploi du temps sera ici</p>
          </div>
          <div className="ai-chat">
            <AgentChat scheduleId={1} onScheduleUpdate={() => console.log('Updated')} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

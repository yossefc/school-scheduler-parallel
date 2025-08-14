# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Table of Contents
- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Development Commands](#development-commands)
- [Testing](#testing)
- [Important Implementation Details](#important-implementation-details)
- [Environment Configuration](#environment-configuration)
- [Common Tasks](#common-tasks)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [User-Specific Constraints](#contraintes-spécifiques-utilisateur)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)

## Project Overview

School Scheduler AI - An AI-powered school timetable generator with Hebrew language support. The system uses constraint programming (Google OR-Tools CP-SAT) combined with LLM agents (GPT-4/Claude) for natural language constraint processing.

## Architecture

### Services & Ports
- **PostgreSQL Database**: 5432
- **Redis Cache**: 6379
- **Solver API (FastAPI)**: 8000
- **AI Agent (Flask/Socket.IO)**: 5001
- **AI Advisor Agent (Flask/Socket.IO)**: 5002
- **Frontend (React)**: 3001
- **n8n Automation**: 5678
- **Prometheus**: 9090
- **Grafana**: 3002

### Key Components
1. **solver/**: CP-SAT optimization engine for schedule generation
2. **scheduler_ai/**: AI agent for natural language constraint parsing (Hebrew/English)
3. **frontend/**: React UI with real-time updates via Socket.IO
4. **database/**: PostgreSQL schema and migrations

## Development Commands

### Running the System
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service_name]

# Stop services
docker-compose down
```

### Frontend Development
```bash
cd frontend
npm install
npm start              # Development server on port 3001
npm run build         # Production build
npm test              # Run tests
```

### Backend Development

#### Solver Service
```bash
cd solver
pip install -r requirements.txt
python main.py        # Runs on port 8000
```

#### AI Agent Service
```bash
cd scheduler_ai
pip install -r requirements.txt
python api.py         # Runs on port 5001
pytest               # Run tests
```

#### AI Advisor Agent Service
```bash
cd scheduler_ai
pip install -r requirements.txt
python advisor_api.py  # Runs on port 5002
# Test Hebrew support:
python test_hebrew_agent.py
```

### Database Operations
```bash
# Connect to database
psql -h localhost -U admin -d school_scheduler -p 5432
# Password: school123

# Run migrations
cd database
alembic upgrade head
```

## Testing
```bash
# AI Agent tests
cd scheduler_ai && pytest

# Frontend tests
cd frontend && npm test

# Solver tests
cd solver && pytest
```

## Important Implementation Details

### Pedagogical Optimization Engine
- **NEW**: `solver/pedagogical_solver.py` - Advanced pedagogical logic solver
- Prioritizes 2-hour consecutive blocks for better learning flow
- Minimizes gaps between courses for the same class
- Groups courses by day to reduce fragmentation
- Respects Israeli educational constraints (prayer times, Friday scheduling)
- Quality scoring system (0-100) based on pedagogical principles

### Advanced Scheduling Pipeline
- **Enhanced**: `solver/advanced_wrapper.py` - Integrated advanced optimization
- Primary solver: Pedagogical logic with course grouping
- Fallback: Original constraint-based solver
- Time limit increased from 60s to 600s for better results
- Real-time quality metrics and block counting

### Hebrew Language Support
- The system is Hebrew-first with specialized parsing in `scheduler_ai/hebrew_parser.py`
- Frontend UI includes RTL support
- Natural language constraints can be entered in Hebrew or English

### Constraint Types
The system handles multiple constraint types defined in `database/schema.sql`:
- Teacher availability
- Class requirements
- Room assignments
- Parallel teaching groups
- Time preferences
- Maximum daily hours
- **NEW**: Religious constraints (prayer times, Shabbat preparation)
- **NEW**: Pedagogical constraints (course grouping, block scheduling)

### AI Model Routing
`scheduler_ai/llm_router.py` automatically selects between GPT-4 and Claude based on:
- Task complexity
- Language (Hebrew vs English)
- Constraint type
- Context length

### Real-time Updates
- Frontend connects to AI Agent via Socket.IO for live updates
- Constraint changes trigger automatic re-solving
- Progress indicators show solving status
- **Enhanced**: Advanced optimization status and quality scores

### Logging System
- **Standardized Logging**: Uses Python's built-in `logging` library throughout all modules
- Structured log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Module-specific loggers for better tracing
- Console handlers only (no file handlers to avoid permission issues in Docker)
- Log levels: DEBUG, INFO, WARNING, ERROR for different component states
- **Note**: File logging removed from `advanced_main.py` to prevent `/logs` directory access errors

### AI Advisor Agent (NEW)
- **Multilingual Support**: Automatic Hebrew/French language detection
- **Natural Language Processing**: `hebrew_language_processor.py` handles Hebrew school terminology
- **User Preference Memory**: Stores and recalls user preferences across sessions
- **Real-time Chat**: WebSocket communication on port 5002
- **Integrated UI**: Available in constraints manager (`/constraints-manager`) via floating button
- **Smart Suggestions**: Proposes schedule optimizations with confidence scores
- **Database Integration**: Stores preferences in `user_preferences` table

### Schedule Optimization Improvements
- **Fixed Extraction Method**: `fixed_extraction.py` prevents duplicate entries and conflicts
- **Gap Elimination**: New constraints to minimize gaps between classes
- **Parallel Course Handling**: Enhanced synchronization for multi-class courses
- **Global Optimization**: Treats all classes together instead of sequential processing

## Environment Configuration

Key environment variables (set in `config.env` or docker-compose):
- `OPENAI_API_KEY`: Required for GPT-4
- `ANTHROPIC_API_KEY`: Required for Claude
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_URL`: Redis cache connection
- `ENABLE_PARALLEL_TEACHING`: Feature flag
- `ENABLE_MONITORING`: Prometheus/Grafana

## Common Tasks

### Adding a New Constraint Type
1. Update `database/schema.sql` with new constraint table/columns
2. Modify `solver/solver_engine_with_constraints.py` to handle constraint
3. Update `scheduler_ai/agent.py` to parse natural language
4. Add UI components in `frontend/src/components/`

### Debugging Schedule Generation
1. Check solver logs: `docker-compose logs -f solver`
2. Verify constraints in database: `SELECT * FROM constraints;`
3. Test pedagogical solver: `POST http://localhost:8000/api/advanced/optimize`
4. Test standard solver: `POST http://localhost:8000/generate_schedule`
5. Test fixed solver (no gaps/conflicts): `POST http://localhost:8000/generate_schedule_fixed`
6. Monitor via Grafana: http://localhost:3002
7. **NEW**: Access dashboard: http://localhost:8000/ for system status
8. **NEW**: Use constraints manager: http://localhost:8000/constraints-manager
9. **NEW**: Chat with AI Advisor: Click 🤖 button on constraints manager page

### Updating Dependencies
```bash
# Backend
cd scheduler_ai && pip freeze > requirements.txt

# Frontend
cd frontend && npm update
```

## API Reference

### Solver API Endpoints (Port 8000)
```http
POST /generate_schedule
Content-Type: application/json
{
  "classes": [...],
  "constraints": [...]
}
Response: { "schedule": [...], "status": "success" }

POST /api/advanced/optimize
Content-Type: application/json
{
  "optimization_level": "pedagogical",
  "quality_target": 85
}
Response: { "schedule": [...], "quality_score": 87.5 }

POST /generate_schedule_fixed
Content-Type: application/json
{
  "eliminate_gaps": true,
  "prevent_conflicts": true
}
Response: { "schedule": [...], "conflicts": [] }

GET /constraints-manager
Response: HTML interface for constraint management

GET /
Response: System dashboard with status metrics
```

### AI Agent API (Port 5001)
```http
POST /parse_constraints
Content-Type: application/json
{
  "text": "שיח בוקר צריך להיות רק בבוקר",
  "language": "hebrew"
}
Response: { "constraints": [...], "confidence": 0.95 }

WebSocket /socket.io
Events: constraint_update, solving_progress, schedule_ready
```

### AI Advisor API (Port 5002)
```http
POST /chat
Content-Type: application/json
{
  "message": "איך לשפר את המערכת?",
  "user_id": "user123"
}
Response: { "response": "...", "suggestions": [...] }

WebSocket /socket.io
Events: chat_message, optimization_suggestion, preference_update
```

## Troubleshooting

### Common Issues

#### Schedule Generation Fails
**Symptoms**: API returns 500 error, no schedule generated
**Solutions**:
1. Check constraint conflicts: `SELECT * FROM constraints WHERE priority = 'CRITICAL'`
2. Verify solver logs: `docker-compose logs -f solver`
3. Test with reduced constraints: Remove non-essential constraints temporarily
4. Increase solver timeout: Modify `time_limit` in solver config

#### Hebrew Text Not Parsing
**Symptoms**: AI agent doesn't recognize Hebrew constraints
**Solutions**:
1. Verify language detection: Check `hebrew_language_processor.py` logs
2. Test Hebrew parser directly: `python test_hebrew_agent.py`
3. Check encoding: Ensure UTF-8 in all text inputs
4. Validate terminology: Use school-specific Hebrew terms

#### Database Connection Issues
**Symptoms**: Services can't connect to PostgreSQL
**Solutions**:
1. Check container status: `docker-compose ps`
2. Verify credentials: `psql -h localhost -U admin -d school_scheduler -p 5432`
3. Reset database: `docker-compose down -v && docker-compose up -d`
4. Check port conflicts: `netstat -tulpn | grep 5432`

#### Frontend Not Loading
**Symptoms**: React app shows blank page or connection errors
**Solutions**:
1. Check console for errors: Open browser dev tools
2. Verify API endpoints: Test `http://localhost:8000/` directly
3. Clear cache: Hard refresh (Ctrl+Shift+R)
4. Check Socket.IO connection: Look for WebSocket errors in network tab

#### Poor Schedule Quality
**Symptoms**: Generated schedules have gaps, conflicts, or low quality scores
**Solutions**:
1. Use pedagogical solver: `POST /api/advanced/optimize`
2. Adjust quality target: Set `quality_target` to 80-85
3. Review constraint priorities: Ensure critical constraints are marked properly
4. Enable gap elimination: Use `/generate_schedule_fixed` endpoint

### Log Analysis

#### Solver Logs
```bash
# View real-time solver activity
docker-compose logs -f solver

# Filter for errors only
docker-compose logs solver 2>&1 | grep ERROR

# Check optimization progress
docker-compose logs solver | grep "Quality score"
```

#### AI Agent Logs
```bash
# Monitor constraint parsing
docker-compose logs -f scheduler_ai

# Hebrew processing logs
docker-compose logs scheduler_ai | grep "hebrew"

# LLM routing decisions
docker-compose logs scheduler_ai | grep "router"
```

## Database Schema

Core tables:
- `teachers`: Teaching staff with specializations
- `subjects`: Course definitions
- `classes`: Student groups
- `time_slots`: Available time periods
- `constraints`: All scheduling rules
- `schedules`: Generated timetables
- `parallel_groups`: Multi-class teaching arrangements
- **NEW**: `solver_input`: Formalized input data for the solver (courses, hours, teachers)
- **Enhanced**: `schedule_entries`: Now includes pedagogical quality metrics

## Security Notes
- API keys are environment-based (never commit)
- CORS configured for local development
- Database credentials in docker-compose (change for production)
- Redis used for session management
- Add to memory

## Dependencies

### Core Technologies & Versions

#### Backend Dependencies
- **Python**: 3.9+
- **FastAPI**: 0.100.0+ (Solver API)
- **Flask**: 2.3.0+ (AI Agents)
- **Google OR-Tools**: 9.7+ (CP-SAT solver)
- **PostgreSQL**: 13+ (Database)
- **Redis**: 6.2+ (Cache & Sessions)
- **Socket.IO**: 5.0+ (Real-time updates)

#### AI/ML Dependencies  
- **OpenAI**: 1.0+ (GPT-4 integration)
- **Anthropic**: 0.25+ (Claude integration)
- **Transformers**: 4.30+ (Language processing)
- **spaCy**: 3.6+ (Hebrew NLP)

#### Frontend Dependencies
- **React**: 18.2+
- **Socket.IO Client**: 4.7+
- **Material-UI**: 5.14+ (UI components)
- **Axios**: 1.5+ (HTTP client)

#### Development & Deployment
- **Docker**: 20.10+
- **Docker Compose**: 2.20+
- **pytest**: 7.4+ (Testing)
- **Alembic**: 1.12+ (Database migrations)

#### Monitoring & Observability
- **Prometheus**: 2.45+
- **Grafana**: 10.0+
- **n8n**: 1.0+ (Workflow automation)

### Package Installation Commands
```bash
# Backend solver service
cd solver
pip install fastapi uvicorn ortools psycopg2-binary redis

# AI agent services  
cd scheduler_ai
pip install flask socketio openai anthropic transformers spacy

# Hebrew language model
python -m spacy download he_core_news_sm

# Frontend
cd frontend  
npm install react socket.io-client @mui/material axios

# Development tools
pip install pytest black flake8 alembic
npm install --save-dev jest @testing-library/react
```

### Version Compatibility Notes
- **Python 3.9+** required for advanced type hints used throughout
- **OR-Tools 9.7+** needed for latest CP-SAT improvements 
- **PostgreSQL 13+** for advanced JSON operations in constraints
- **Redis 6.2+** for improved memory management with large datasets
- **Node.js 18+** recommended for frontend development

## Contraintes Spécifiques Utilisateur

### Contraintes École Hébraïque Religieuse
L'agent AI a été entraîné avec les contraintes spécifiques suivantes :

1. **שיח בוקר (Conversation Hébreu)**
   - MATIN UNIQUEMENT (périodes 1-4)
   - Maximum 2h consécutives (pas 3h de suite)
   - Priorité: CRITIQUE

2. **Structure Lundi**
   - Classes ז, ט, ח doivent finir APRÈS période 4
   - Majorité des professeurs présents (80% minimum)
   - Professeurs שיח בוקר et חינוך OBLIGATOIRES
   - Priorité: HAUTE

3. **Optimisation Spécialisée**
   - Algorithme préféré: Constraint Programming
   - Objectif qualité pédagogique: 85%+
   - Respect contraintes religieuses: 100%

### Utilisation
Ces contraintes sont automatiquement appliquées lors de l'optimisation via :
- Interface web: http://localhost:8000/constraints-manager
- Section "Optimisation Pédagogique Avancée"
- L'agent AI respectera toutes ces règles automatiquement

### Fichiers de Configuration
- `user_constraints_permanent.json`: Contraintes détaillées
- `ai_agent_user_config.json`: Configuration agent AI

- Add to memory
- "Please update CLAUDE.md to note that we now use library X for logging"
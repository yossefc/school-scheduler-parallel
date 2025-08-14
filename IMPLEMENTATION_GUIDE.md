# 🎓 School Scheduler - Implementation & User Guide

## 📋 Table of Contents
- [System Overview](#system-overview)
- [Architecture](#architecture)
- [How to View Schedules](#how-to-view-schedules)
- [Interface Guide](#interface-guide)
- [Israeli School Features](#israeli-school-features)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)

## 🏗️ System Overview

School Scheduler is an AI-powered timetable generation system specifically designed for Israeli schools, featuring:
- Hebrew/French language support
- Religious constraints (prayer times, short Friday)
- Parallel teaching groups
- Advanced optimization pipeline
- Real-time constraint management

### Current Status
- **133 courses** loaded in database
- **403 total hours** to schedule
- **All advanced modules** integrated and operational

## 🔧 Architecture

```
┌─────────────────────────────────────┐
│     Frontend (Port 3001)            │
│         React + Socket.IO           │
└──────────────┬──────────────────────┘
               │
     ┌─────────┴──────────┐
     ▼                    ▼
┌──────────┐       ┌──────────────┐
│ Solver   │       │   AI Agent   │
│ Port 8000│       │  Port 5001   │
│ FastAPI  │       │Flask/Socket  │
└────┬─────┘       └──────┬───────┘
     │                    │
     └──────┬─────────────┘
            ▼
    ┌──────────────┐
    │  PostgreSQL  │
    │  Port 5432   │
    │              │
    │ Tables:      │
    │ - teachers   │
    │ - subjects   │
    │ - solver_input│
    │ - constraints│
    │ - schedules  │
    └──────────────┘
```

### Services & Ports
- **PostgreSQL Database**: 5432
- **Redis Cache**: 6379
- **Solver API (FastAPI)**: 8000
- **AI Agent (Flask/Socket.IO)**: 5001
- **Frontend (React)**: 3001
- **n8n Automation**: 5678
- **Prometheus**: 9090
- **Grafana**: 3002

## 📍 How to View Schedules

### Quick Access Points

1. **Main Dashboard**: http://localhost:8000/
   - System status overview
   - Quick actions
   - Statistics

2. **Constraints Manager**: http://localhost:8000/constraints-manager
   - Add/manage constraints
   - Generate schedules
   - **VIEW GENERATED SCHEDULES**

3. **React Frontend**: http://localhost:3001
   - Full interactive interface
   - Real-time updates

### Step-by-Step Schedule Generation

1. **Access the Constraints Manager**
   ```
   http://localhost:8000/constraints-manager
   ```

2. **Add Constraints** (optional)
   - Type in natural language (Hebrew or French)
   - Examples:
     - "Le professeur Cohen n'est pas disponible le vendredi"
     - "תפילה צריכה להיות בשעה ראשונה"

3. **Generate Schedule**
   - Click the **"🚀 Générer l'emploi du temps"** button
   - Wait for processing (usually 10-30 seconds)

4. **View Results**
   - Schedule automatically appears at bottom of page
   - Switch between classes using tabs
   - Each class has its own weekly view

## 📊 Interface Guide

### Main Dashboard Components

#### 1️⃣ **Header Section**
```
🎓 School Scheduler
System status indicators:
- 🟢 Backend Connected (Solver API)
- 🟣 AI Connected (Natural language processing)
```

#### 2️⃣ **Statistics Cards**
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  📚 X       │  👨‍🏫 Y      │  🎯 Z       │  ✅ N%      │
│ Constraints │ Teachers    │ Classes     │Success Rate │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

#### 3️⃣ **Constraint Input**
- Natural language text area
- Priority selector (0-5)
- AI analysis feedback

#### 4️⃣ **Active Constraints List**
Each constraint shows:
- **Type Icon**: 🚫 Unavailable, 🙏 Prayer, 📅 Friday, etc.
- **Priority**: 🔴 Critical, 🟠 High, 🟡 Medium, 🔵 Normal, 🟢 Low
- **Actions**: Toggle active/inactive, Delete

#### 5️⃣ **Generated Schedule Display**

##### Statistics Panel
```
📊 Generation Statistics
• Total slots: 403
• Classes: 15
• Periods per day: 8
• Status: ✓ Successfully generated
```

##### Class Tabs
```
[📚 א1] [📚 א2] [📚 ב1] [📚 ב2] [📚 ג1] ...
```
Click any tab to view that class's schedule

##### Weekly Schedule Table
```
┌────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Period │  Sunday  │  Monday  │ Tuesday  │Wednesday │ Thursday │  Friday  │
├────────┼──────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│   1    │  Prayer  │  Prayer  │  Prayer  │  Prayer  │  Prayer  │  Prayer  │
│   2    │   Math   │  Hebrew  │ English  │   Math   │  Talmud  │  Torah   │
│   3    │  Hebrew  │   Math   │   Math   │ History  │  Hebrew  │ English  │
│   4    │ Science  │  [FREE]  │  Sports  │ Science  │   Art    │ Science  │
│   5    │ English  │  [FREE]  │Geography │ English  │   Math   │ ████████ │
│   6    │ History  │ Science  │  Torah   │  Sports  │ Science  │ ████████ │
│   7    │  Talmud  │   Art    │ Science  │  Talmud  │ History  │ ████████ │
│   8    │  Sports  │Geography │   Art    │  Torah   │  Sports  │ ████████ │
└────────┴──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### Color Coding

- 🟦 **Blue**: Mathematics, Sciences
- 🟩 **Green**: Languages (Hebrew, English)
- 🟨 **Orange**: Religious studies (Torah, Prayer, Talmud)
- 🟪 **Purple**: History, Geography
- 🟦 **Cyan**: Sports
- 🟡 **Yellow**: Arts
- ⬛ **Dark Gray**: Friday afternoon (school closed)
- ⬜ **White**: Free periods

## 🇮🇱 Israeli School Features

### Religious Constraints
- **Morning Prayer (תפילה)**: Always scheduled in period 1
- **Torah/Talmud Studies**: Preferably morning slots
- **Friday Schedule**: Short day (4 periods maximum)

### Special Time Blocks
- **Monday 12:00-13:30**: Free for grades ז, ח, ט (middle school)
- **Friday Afternoon**: Blocked (Shabbat preparation)

### Parallel Teaching
- Multiple teachers for same subject/time
- Automatic group splitting
- Synchronized scheduling

### Hebrew Support
- Full Hebrew language constraint input
- Hebrew day names (א-ו for Sunday-Friday)
- RTL interface support

## 🚀 API Endpoints

### Core Endpoints

#### Schedule Generation
```http
POST /generate_schedule
{
  "time_limit": 300
}
```

#### Constraints Management
```http
GET /api/constraints          # List all constraints
POST /api/constraints         # Add new constraint
PUT /api/constraints/{id}     # Update constraint
DELETE /api/constraints/{id}  # Delete constraint
```

#### Advanced Optimization
```http
POST /api/advanced/optimize           # Full optimization pipeline
POST /api/advanced/smart-distribute   # Smart course distribution
GET /api/advanced/analyze-conflicts   # Conflict analysis
GET /api/advanced/status             # Module status check
```

#### Statistics
```http
GET /api/stats    # System statistics
GET /health       # Health check
```

### Using Advanced Features

#### 1. Run Full Optimization
```bash
curl -X POST http://localhost:8000/api/advanced/optimize \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### 2. Smart Distribution for a Course
```bash
curl -X POST http://localhost:8000/api/advanced/smart-distribute \
  -H "Content-Type: application/json" \
  -d '{
    "class_name": "א1",
    "subject": "מתמטיקה",
    "hours": 5
  }'
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Schedule Not Displaying
- Check if generation completed: Look for "✓ Successfully generated"
- Verify data exists: Check statistics panel
- Try refreshing the page

#### 2. Constraints Not Applied
- Ensure constraints are marked as "Active"
- Check priority levels (0 = highest)
- Verify constraint format is correct

#### 3. Services Not Connected
- Check Docker containers: `docker-compose ps`
- Restart services: `docker-compose restart`
- Check logs: `docker-compose logs [service_name]`

### Quick Fixes

#### Reset Database
```bash
docker exec school_db psql -U admin -d school_scheduler -c "TRUNCATE schedules CASCADE;"
```

#### Reload Constraints
```bash
curl -X GET http://localhost:8000/api/constraints
```

#### Force Regeneration
```bash
curl -X POST http://localhost:8000/generate_schedule \
  -H "Content-Type: application/json" \
  -d '{"time_limit": 600}'
```

## 📈 Performance Tips

1. **Optimal Time Limits**
   - Quick generation: 60-120 seconds
   - Standard: 300 seconds
   - High quality: 600+ seconds

2. **Constraint Priority**
   - Use priority 0-1 for hard constraints
   - Use priority 2-3 for preferences
   - Use priority 4-5 for nice-to-have

3. **Batch Operations**
   - Add all constraints before generating
   - Use advanced optimization for better results
   - Generate during off-peak hours

## 🔐 Security Notes

- API keys are environment-based (never commit)
- Default credentials for development only
- Change passwords before production deployment
- Enable CORS restrictions for production

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Metrics Dashboard**: http://localhost:3002 (Grafana)
- **Automation Workflows**: http://localhost:5678 (n8n)
- **Database Admin**: Connect with pgAdmin to port 5432

## 🆘 Support

For issues or questions:
1. Check logs: `docker-compose logs -f [service_name]`
2. Review constraints in database
3. Verify all services are running
4. Check network connectivity between services

---

*School Scheduler v2.0 - Optimized for Israeli Educational Institutions*
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from solver_engine import ScheduleSolver  # Solver corrigֳ©
from models import ScheduleRequest, ConstraintRequest
from constraints_handler import ConstraintsManager
import json
import logging
from prometheus_fastapi_instrumentator import Instrumentator
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="School Schedule Solver - Parallel Teaching Edition")
# Instrumentation Prometheus (/metrics)
Instrumentator().instrument(app).expose(app, include_in_schema=False)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instances
constraints_manager = ConstraintsManager()

# Configuration DB  
db_config = {
    "host": "host.docker.internal",  # Utiliser host.docker.internal comme ai_agent
    "database": "school_scheduler",
    "user": "admin", 
    "password": "school123"
}

@app.get("/")
async def root():
    return {
        "message": "School Schedule Solver API - Parallel Teaching Edition",
        "version": "2.0",
        "features": ["parallel_teaching", "automatic_detection", "synchronized_scheduling"]
    }

@app.post("/generate_schedule")
async def generate_schedule(request: ScheduleRequest):
    """Gֳ©nֳ¨re un emploi du temps avec support des cours parallֳ¨les"""
    try:
        # Utiliser le solver corrigֳ©
        solver = ScheduleSolver()
        
        # Charger les donnֳ©es
        solver.load_data_from_db()
        
        # Appliquer les contraintes additionnelles
        for constraint in request.constraints:
            solver.add_constraint(constraint)
        
        # Rֳ©soudre
        schedule = solver.solve(time_limit=request.time_limit)
        
        if schedule:
            # Sauvegarder
            schedule_id = solver.save_schedule(schedule)
            return {
                "status": "success",
                "schedule_id": schedule_id,
                "summary": solver.get_schedule_summary(schedule),
                "message": "Emploi du temps gֳ©nֳ©rֳ© avec succֳ¨s (cours parallֳ¨les inclus)"
            }
        else:
            return {
                "status": "failed",
                "reason": "Aucune solution trouvֳ©e",
                "suggestion": "Vֳ©rifiez les contraintes parallֳ¨les avec /api/parallel/check"
            }
            
    except Exception as e:
        logger.error(f"Erreur gֳ©nֳ©ration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# NOUVEAUX ENDPOINTS POUR LES COURS PARALLֳˆLES
# ============================================

@app.get("/api/parallel/groups")
async def get_parallel_groups():
    """Retourne tous les groupes d'enseignement parallֳ¨le"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                pg.group_id,
                pg.subject,
                pg.grade,
                pg.teachers,
                COUNT(DISTINCT ptd.teacher_name) as teacher_count,
                MAX(ptd.hours_per_teacher) as hours,
                STRING_AGG(DISTINCT ptd.classes_covered, ', ') as all_classes
            FROM parallel_groups pg
            LEFT JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
            GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
            ORDER BY pg.grade, pg.subject
        """)
        
        groups = cur.fetchall()
        return {"parallel_groups": groups, "total": len(groups)}
        
    finally:
        cur.close()
        conn.close()

@app.get("/api/parallel/check")
async def check_parallel_consistency():
    """Vֳ©rifie la cohֳ©rence des cours parallֳ¨les"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT * FROM check_parallel_consistency()")
        issues = cur.fetchall()
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "message": "Aucun problֳ¨me dֳ©tectֳ©" if len(issues) == 0 else f"{len(issues)} problֳ¨mes dֳ©tectֳ©s"
        }
        
    finally:
        cur.close()
        conn.close()

@app.get("/api/parallel/teacher/{teacher_name}")
async def get_teacher_parallel_courses(teacher_name: str):
    """Retourne les cours parallֳ¨les d'un professeur"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                pg.group_id,
                pg.subject,
                pg.grade,
                pg.teachers,
                ptd.hours_per_teacher as hours,
                ptd.classes_covered
            FROM parallel_groups pg
            JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
            WHERE ptd.teacher_name = %s
            ORDER BY pg.grade, pg.subject
        """, (teacher_name,))
        
        courses = cur.fetchall()
        
        # Aussi obtenir les cours individuels
        cur.execute("""
            SELECT 
                subject,
                grade,
                class_list,
                hours
            FROM teacher_load
            WHERE teacher_name = %s
            AND (is_parallel = FALSE OR is_parallel IS NULL)
            ORDER BY grade, subject
        """, (teacher_name,))
        
        individual = cur.fetchall()
        
        return {
            "teacher": teacher_name,
            "parallel_courses": courses,
            "individual_courses": individual,
            "total_parallel_hours": sum(c["hours"] for c in courses),
            "total_individual_hours": sum(c["hours"] for c in individual)
        }
        
    finally:
        cur.close()
        conn.close()

@app.post("/api/parallel/analyze")
async def analyze_for_parallel(data: dict):
    """Analyse des donnֳ©es pour identifier les cours parallֳ¨les potentiels"""
    try:
        teacher_loads = data.get("teacher_loads", [])
        
        # Grouper par matiֳ¨re et niveau
        candidates = {}
        for load in teacher_loads:
            if "," in load.get("class_list", ""):
                key = f"{load['subject']}_{load['grade']}"
                if key not in candidates:
                    candidates[key] = []
                candidates[key].append(load)
        
        # Identifier les vrais groupes parallֳ¨les
        parallel_groups = []
        for key, group in candidates.items():
            if len(group) > 1:
                subject, grade = key.split("_")
                parallel_groups.append({
                    "subject": subject,
                    "grade": grade,
                    "teachers": [g["teacher_name"] for g in group],
                    "teacher_count": len(group),
                    "hours": group[0]["hours"],
                    "is_valid": all(g["hours"] == group[0]["hours"] for g in group)
                })
        
        return {
            "potential_parallel_groups": parallel_groups,
            "total_found": len(parallel_groups),
            "recommendation": "Ces groupes devraient ֳ×tre configurֳ©s comme cours parallֳ¨les"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================
# ENDPOINTS DE VISUALISATION AMֳ‰LIORֳ‰S
# ============================================

@app.get("/api/schedule/{view_type}/{name}")
async def get_schedule_enhanced(view_type: str, name: str):
    """Version simplifiée qui fonctionne sans erreurs SQL"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer le dernier schedule_id actif
        cur.execute("SELECT MAX(schedule_id) as latest_id FROM schedules WHERE status = 'active'")
        result = cur.fetchone()
        
        if not result or not result['latest_id']:
            return {"schedule": [], "view_type": view_type, "name": name, "message": "Aucun emploi du temps actif"}
        
        schedule_id = result['latest_id']
        
        if view_type == "class":
            # Pour une classe, récupérer toutes les entrées
            cur.execute("""
                SELECT 
                    entry_id,
                    teacher_name,
                    class_name,
                    subject_name,
                    day_of_week,
                    period_number,
                    is_parallel_group,
                    group_id
                FROM schedule_entries
                WHERE schedule_id = %s AND class_name = %s
                ORDER BY day_of_week, period_number
            """, (schedule_id, name))
            
        elif view_type == "teacher":
            # Pour un professeur
            cur.execute("""
                SELECT 
                    entry_id,
                    teacher_name,
                    class_name,
                    subject_name,
                    day_of_week,
                    period_number,
                    is_parallel_group,
                    group_id
                FROM schedule_entries
                WHERE schedule_id = %s AND teacher_name LIKE %s
                ORDER BY day_of_week, period_number
            """, (schedule_id, f"%{name}%"))
        else:
            return {"error": "Type de vue non supporté. Utilisez 'class' ou 'teacher'"}
        
        schedule = cur.fetchall()
        
        # Enrichir les données
        for entry in schedule:
            if entry.get("is_parallel_group") and entry.get("group_id"):
                entry["display_type"] = "parallel"
                entry["display_info"] = f"Cours parallèle - Groupe {entry['group_id']}"
            else:
                entry["display_type"] = "individual"
                entry["display_info"] = "Cours individuel"
        
        return {
            "schedule": schedule, 
            "view_type": view_type, 
            "name": name,
            "total_lessons": len(schedule),
            "schedule_id": schedule_id
        }
        
    except Exception as e:
        logger.error(f"Erreur get_schedule_enhanced: {str(e)}")
        return {"error": str(e), "schedule": []}
    finally:
        cur.close()
        conn.close()

@app.get("/api/stats/parallel")
async def get_parallel_statistics():
    """Statistiques spֳ©cifiques aux cours parallֳ¨les"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT * FROM v_parallel_statistics")
        stats = {row["metric"]: row["value"] for row in cur.fetchall()}
        
        # Ajouter des stats dֳ©taillֳ©es
        cur.execute("""
            SELECT 
                subject,
                COUNT(DISTINCT group_id) as group_count,
                COUNT(DISTINCT teacher_name) as teacher_count,
                SUM(hours_per_teacher) as total_hours
            FROM parallel_teaching_details
            GROUP BY subject
            ORDER BY group_count DESC
        """)
        
        by_subject = cur.fetchall()
        
        return {
            "general": stats,
            "by_subject": by_subject,
            "summary": f"{stats.get('Total groupes parallֳ¨les', 0)} groupes avec {stats.get('Total professeurs en parallֳ¨le', 0)} professeurs"
        }
        
    finally:
        cur.close()
        conn.close()


# ============================================
# ENDPOINTS POUR L'INTERFACE WEB
# ============================================

@app.get("/api/classes")
async def get_classes():
    """Retourne la liste de toutes les classes"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT DISTINCT class_name FROM classes ORDER BY class_name")
        classes = [row['class_name'] for row in cur.fetchall()]
        return {"classes": classes}
    finally:
        cur.close()
        conn.close()

@app.get("/api/teachers")
async def get_teachers():
    """Retourne la liste de tous les professeurs"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT DISTINCT teacher_name FROM teachers ORDER BY teacher_name")
        teachers = [row['teacher_name'] for row in cur.fetchall()]
        return {"teachers": teachers}
    finally:
        cur.close()
        conn.close()

@app.get("/api/stats")
async def get_general_stats():
    """Retourne les statistiques générales"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        stats = {}
        
        # Compter les contraintes (table existante)
        try:
            cur.execute("SELECT COUNT(*) as count FROM constraints")
            stats['total_constraints'] = cur.fetchone()['count']
        except:
            stats['total_constraints'] = 0
        
        # Compter les contraintes institutionnelles (table existante)
        try:
            cur.execute("SELECT COUNT(*) as count FROM institutional_constraints")
            stats['total_institutional_constraints'] = cur.fetchone()['count']
        except:
            stats['total_institutional_constraints'] = 0
        
        # Compter les contraintes actives
        try:
            cur.execute("SELECT COUNT(*) as count FROM constraints WHERE is_active = true")
            stats['active_constraints'] = cur.fetchone()['count']
        except:
            stats['active_constraints'] = 0
        
        # Données par défaut pour les tables manquantes
        stats['total_classes'] = 0  # Table classes n'existe pas encore
        stats['total_teachers'] = 0  # Table teachers n'existe pas encore
        stats['total_lessons'] = 0  # Table schedule_entries n'existe pas encore
        stats['total_subjects'] = 0  # Table teacher_load n'existe pas encore
        
        return {"general": stats, "note": "Statistiques basées sur les tables existantes"}
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


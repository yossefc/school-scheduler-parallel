from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from solver_engine import ParallelScheduleSolver  # Nouveau solver
from models import ScheduleRequest, ConstraintRequest
from constraints_handler import ConstraintsManager
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="School Schedule Solver - Parallel Teaching Edition")

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
    "host": "postgres",
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
    """Génère un emploi du temps avec support des cours parallèles"""
    try:
        # Utiliser le nouveau solver
        solver = ParallelScheduleSolver()
        
        # Charger les données
        solver.load_data_from_db()
        
        # Appliquer les contraintes additionnelles
        for constraint in request.constraints:
            solver.add_constraint(constraint)
        
        # Résoudre
        schedule = solver.solve(time_limit=request.time_limit)
        
        if schedule:
            # Sauvegarder
            schedule_id = solver.save_schedule(schedule)
            return {
                "status": "success",
                "schedule_id": schedule_id,
                "summary": solver.get_schedule_summary(schedule),
                "message": "Emploi du temps généré avec succès (cours parallèles inclus)"
            }
        else:
            return {
                "status": "failed",
                "reason": "Aucune solution trouvée",
                "suggestion": "Vérifiez les contraintes parallèles avec /api/parallel/check"
            }
            
    except Exception as e:
        logger.error(f"Erreur génération: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# NOUVEAUX ENDPOINTS POUR LES COURS PARALLÈLES
# ============================================

@app.get("/api/parallel/groups")
async def get_parallel_groups():
    """Retourne tous les groupes d'enseignement parallèle"""
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
    """Vérifie la cohérence des cours parallèles"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT * FROM check_parallel_consistency()")
        issues = cur.fetchall()
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "message": "Aucun problème détecté" if len(issues) == 0 else f"{len(issues)} problèmes détectés"
        }
        
    finally:
        cur.close()
        conn.close()

@app.get("/api/parallel/teacher/{teacher_name}")
async def get_teacher_parallel_courses(teacher_name: str):
    """Retourne les cours parallèles d'un professeur"""
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
    """Analyse des données pour identifier les cours parallèles potentiels"""
    try:
        teacher_loads = data.get("teacher_loads", [])
        
        # Grouper par matière et niveau
        candidates = {}
        for load in teacher_loads:
            if "," in load.get("class_list", ""):
                key = f"{load['subject']}_{load['grade']}"
                if key not in candidates:
                    candidates[key] = []
                candidates[key].append(load)
        
        # Identifier les vrais groupes parallèles
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
            "recommendation": "Ces groupes devraient être configurés comme cours parallèles"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================
# ENDPOINTS DE VISUALISATION AMÉLIORÉS
# ============================================

@app.get("/api/schedule/{view_type}/{name}")
async def get_schedule_enhanced(view_type: str, name: str):
    """Version améliorée qui affiche correctement les cours parallèles"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if view_type == "class":
            # Pour une classe, montrer tous les profs en parallèle
            cur.execute("""
                WITH parallel_entries AS (
                    SELECT 
                        se.schedule_id,
                        se.day_of_week,
                        se.period_number,
                        se.subject_name,
                        se.class_name,
                        se.group_id,
                        STRING_AGG(DISTINCT se.teacher_name, ' + ' ORDER BY se.teacher_name) as teachers
                    FROM schedule_entries se
                    WHERE se.class_name = %s
                    AND se.group_id IS NOT NULL
                    GROUP BY se.schedule_id, se.day_of_week, se.period_number, 
                             se.subject_name, se.class_name, se.group_id
                ),
                regular_entries AS (
                    SELECT 
                        schedule_id,
                        day_of_week,
                        period_number,
                        subject_name,
                        teacher_name as teachers,
                        class_name,
                        NULL as group_id
                    FROM schedule_entries
                    WHERE class_name = %s
                    AND (group_id IS NULL OR is_parallel_group = FALSE)
                )
                SELECT * FROM parallel_entries
                UNION ALL
                SELECT * FROM regular_entries
                ORDER BY day_of_week, period_number
            """, (name, name))
            
        elif view_type == "teacher":
            cur.execute("""
                SELECT 
                    entry_id,
                    schedule_id,
                    day_of_week,
                    period_number,
                    subject_name,
                    teacher_name,
                    class_name,
                    is_parallel_group,
                    group_id
                FROM schedule_entries
                WHERE teacher_name = %s
                ORDER BY day_of_week, period_number
            """, (name,))
        
        schedule = cur.fetchall()
        
        # Marquer les entrées parallèles
        for entry in schedule:
            if entry.get("group_id"):
                entry["display_type"] = "parallel"
                entry["display_info"] = f"Groupe parallèle #{entry['group_id']}"
        
        return {"schedule": schedule, "view_type": view_type, "name": name}
        
    finally:
        cur.close()
        conn.close()

@app.get("/api/stats/parallel")
async def get_parallel_statistics():
    """Statistiques spécifiques aux cours parallèles"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT * FROM v_parallel_statistics")
        stats = {row["metric"]: row["value"] for row in cur.fetchall()}
        
        # Ajouter des stats détaillées
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
            "summary": f"{stats.get('Total groupes parallèles', 0)} groupes avec {stats.get('Total professeurs en parallèle', 0)} professeurs"
        }
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# Ajouter ces lignes au début de votre main.py dans ./solver/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from solver_engine_with_constraints import ScheduleSolverWithConstraints as ScheduleSolver
from constraints_handler import ConstraintsManager
from ortools.sat.python import cp_model
import json
import logging
from datetime import datetime
from prometheus_fastapi_instrumentator import Instrumentator
import psycopg2
from psycopg2.extras import RealDictCursor
from api_constraints import register_constraint_routes  # Import du module
from pydantic import BaseModel
import os
from typing import Optional, List, Any

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="School Schedule Solver - Docker Edition")

# CORS - Très important pour Docker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permet toutes les origines en dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
# Instances
constraints_manager = ConstraintsManager()

# IMPORTANT: Enregistrer les routes des contraintes
register_constraint_routes(app)

# Configuration DB pour Docker
db_config = {
    "host": "postgres",  # Nom du service Docker, pas localhost !
    "database": "school_scheduler",
    "user": "admin", 
    "password": "school123"
}
class GenerateScheduleRequest(BaseModel):
    constraints: Optional[List[Any]] = None  # réservée pour usage futur
    time_limit: int = 300
# Route pour servir l'interface HTML
@app.get("/constraints-manager")
async def constraints_interface():
    """Sert l'interface de gestion des contraintes"""
    try:
        # Chemin du fichier HTML dans le container
        html_path = '/app/constraints_manager.html'
        
        # Si le fichier n'existe pas dans /app, essayer le dossier courant
        if not os.path.exists(html_path):
            html_path = 'constraints_manager.html'
        
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        logger.error(f"Fichier constraints_manager.html non trouvé")
        return HTMLResponse(content="""
            <h1>Erreur: Interface non trouvée</h1>
            <p>Le fichier constraints_manager.html n'est pas présent dans le container.</p>
            <p>Vérifiez que le fichier est bien dans le dossier ./solver/</p>
        """, status_code=404)

@app.get("/")
async def root():
    return {
        "message": "School Schedule Solver API - Docker Version",
        "version": "2.0",
        "features": ["parallel_teaching", "automatic_detection", "synchronized_scheduling"],
        "endpoints": {
            "interface": "http://localhost:8000/constraints-manager",
            "api_constraints": "http://localhost:8000/api/constraints",
            "api_stats": "http://localhost:8000/api/stats"
        }
    }

# Route de santé pour Docker
@app.get("/health")
async def health_check():
    """Health check endpoint pour Docker"""
    try:
        # Test de connexion à la DB
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


    

# Remplacez la fonction generate_schedule dans main.py par cette version corrigée
@app.post("/parse")
async def parse_excel(file: UploadFile = File(...)):
    """Parse un fichier Excel et extrait les données pour l'emploi du temps"""
    try:
        logger.info(f"Réception du fichier: {file.filename}")
        
        # Vérifier l'extension du fichier
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Le fichier doit être un Excel (.xlsx ou .xls)")
        
        # Lire le fichier Excel
        contents = await file.read()
        
        # Traiter les différents onglets
        df_teachers = pd.read_excel(contents, sheet_name='Teachers', engine='openpyxl')
        df_subjects = pd.read_excel(contents, sheet_name='Teacher_Subjects', engine='openpyxl')
        df_parallel = pd.read_excel(contents, sheet_name='Parallel_Groups', engine='openpyxl')
        df_constraints = pd.read_excel(contents, sheet_name='Constraints', engine='openpyxl')
        
        # Nettoyer et formater les données des professeurs
        teachers = []
        for _, row in df_teachers.iterrows():
            teacher = {
                "teacher_name": str(row['Teacher Name']).strip(),
                "total_hours": int(row['Total Hours']) if pd.notna(row['Total Hours']) else None,
                "work_days": str(row['Work Days']) if pd.notna(row['Work Days']) else None,
                "grades": str(row['Grades']) if pd.notna(row['Grades']) else None,
                "email": str(row['Email']) if pd.notna(row['Email']) else None,
                "phone": str(row['Phone']) if pd.notna(row['Phone']) else None
            }
            teachers.append(teacher)
        
        # Nettoyer et formater les charges d'enseignement
        teacher_subjects = []
        for _, row in df_subjects.iterrows():
            subject = {
                "teacher_name": str(row['Teacher Name']).strip(),
                "subject": str(row['Subject']).strip(),
                "grade": str(row['Grade']),
                "class_list": str(row['Class List']) if pd.notna(row['Class List']) else "",
                "hours": int(row['Hours']) if pd.notna(row['Hours']) else 0,
                "work_days": str(row['Work Days']) if pd.notna(row['Work Days']) else None
            }
            teacher_subjects.append(subject)
        
        # Nettoyer et formater les groupes parallèles
        parallel_groups = []
        for _, row in df_parallel.iterrows():
            group = {
                "subject": str(row['Subject']).strip(),
                "grade": str(row['Grade']),
                "teachers": str(row['Teachers']).split(',') if pd.notna(row['Teachers']) else [],
                "class_lists": str(row['Class Lists']).split(',') if pd.notna(row['Class Lists']) else []
            }
            # Nettoyer les espaces dans les listes
            group["teachers"] = [t.strip() for t in group["teachers"]]
            group["class_lists"] = [c.strip() for c in group["class_lists"]]
            parallel_groups.append(group)
        
        # Nettoyer et formater les contraintes
        constraints = []
        for _, row in df_constraints.iterrows():
            constraint = {
                "type": str(row['Type']).strip() if pd.notna(row['Type']) else "custom",
                "weight": int(row['Weight']) if pd.notna(row['Weight']) else 1,
                "details": json.dumps({
                    "description": str(row['Description']) if pd.notna(row['Description']) else "",
                    "entity_type": str(row['Entity Type']) if pd.notna(row['Entity Type']) else "",
                    "entity_name": str(row['Entity Name']) if pd.notna(row['Entity Name']) else "",
                    "day": str(row['Day']) if pd.notna(row['Day']) else None,
                    "period": str(row['Period']) if pd.notna(row['Period']) else None,
                    "room": str(row['Room']) if pd.notna(row['Room']) else None
                })
            }
            constraints.append(constraint)
        
        # Préparer la réponse
        result = {
            "teachers": teachers,
            "teacher_subjects": teacher_subjects,
            "parallel_groups": parallel_groups,
            "constraints": constraints,
            "metadata": {
                "filename": file.filename,
                "imported_at": datetime.now().isoformat(),
                "counts": {
                    "teachers": len(teachers),
                    "teacher_subjects": len(teacher_subjects),
                    "parallel_groups": len(parallel_groups),
                    "constraints": len(constraints)
                }
            }
        }
        
        logger.info(f"Parsing réussi: {result['metadata']['counts']}")
        return JSONResponse(content=result)
        
    except pd.errors.EmptyDataError:
        logging.error("Trace solver :", exc_info=e)        
        raise HTTPException(status_code=400, detail="Le fichier Excel est vide ou mal formaté")
    except KeyError as e:
        logging.error("Trace solver :", exc_info=e)        # <-- ajoute ceci
        raise HTTPException(status_code=400, detail=f"Colonne manquante dans le fichier Excel: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors du parsing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du fichier: {str(e)}")


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
        logging.error("Trace solver :", exc_info=e)        # <-- ajoute ceci
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
        # Utiliser des requêtes directes au lieu de la vue qui peut ne pas exister
        stats = {}
        
        # Compter les groupes parallèles
        cur.execute("SELECT COUNT(*) as count FROM parallel_groups")
        stats['Total groupes parallèles'] = cur.fetchone()['count']
        
        # Compter les professeurs en parallèle
        cur.execute("SELECT COUNT(DISTINCT teacher_name) as count FROM parallel_teaching_details")
        stats['Total professeurs en parallèle'] = cur.fetchone()['count']
        
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
        
        # Compter les données réelles
        try:
            cur.execute("SELECT COUNT(*) as count FROM classes")
            stats['total_classes'] = cur.fetchone()['count']
        except:
            stats['total_classes'] = 0
            
        try:
            cur.execute("SELECT COUNT(*) as count FROM teachers")
            stats['total_teachers'] = cur.fetchone()['count']
        except:
            stats['total_teachers'] = 0
            
        try:
            cur.execute("SELECT COUNT(*) as count FROM schedule_entries")
            stats['total_lessons'] = cur.fetchone()['count']
        except:
            stats['total_lessons'] = 0
            
        try:
            cur.execute("SELECT COUNT(*) as count FROM subjects")
            stats['total_subjects'] = cur.fetchone()['count']
        except:
            stats['total_subjects'] = 0
        
        return {"general": stats, "note": "Statistiques basées sur les tables existantes"}
    finally:
        cur.close()
        conn.close()


# ============================================================
# GÉNÉRATION D'EMPLOI DU TEMPS (API)
# ============================================================
from typing import Optional, List, Any



# Dans main.py, remplacez la fonction generate_schedule_endpoint par :

@app.post("/generate_schedule")
async def generate_schedule_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps complet avec gestion améliorée"""
    try:
        logger.info("=== DÉBUT GÉNÉRATION EMPLOI DU TEMPS ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Créer le solver avec la config Docker
        solver = ScheduleSolver(db_config)
        
        # Charger les données
        logger.info("Chargement des données...")
        solver.load_data_from_db()
        
        # IMPORTANT: Utiliser un temps suffisant vu le taux d'utilisation de 95%
        time_limit = max(payload.time_limit, 600)  # Minimum 10 minutes
        logger.info(f"Génération avec time_limit={time_limit}s")
        
        # Résoudre
        schedule = solver.solve(time_limit=time_limit)
        
        if schedule is None:
            logger.error("Aucune solution trouvée")
            
            # Essayer avec des paramètres plus permissifs
            logger.info("Tentative avec paramètres assouplis...")
            solver.solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
            solver.solver.parameters.linearization_level = 2
            solver.solver.parameters.cp_model_presolve = True
            
            schedule = solver.solve(time_limit=time_limit * 2)  # Doubler le temps
            
            if schedule is None:
                raise HTTPException(
                    status_code=500, 
                    detail="Impossible de générer un emploi du temps. Vérifiez les contraintes."
                )
        
        # Sauvegarder systématiquement si une solution existe
        schedule_id = None
        try:
            schedule_id = solver.save_schedule(schedule)
            logger.info(f"Schedule sauvegardé avec ID: {schedule_id}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde schedule: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Erreur de sauvegarde: {e}")
        
        # Générer le résumé
        summary = solver.get_schedule_summary(schedule)
        
        logger.info("=== GÉNÉRATION TERMINÉE ===")
        logger.info(f"Résultat: {len(schedule)} créneaux générés")
        logger.info(f"Jours utilisés: {summary.get('days_used', [])}")
        logger.info(f"Classes couvertes: {summary.get('classes_covered', 0)}")
        
        return {
            "success": True,
            "schedule": schedule,
            "summary": summary,
            "schedule_id": schedule_id,
            "message": f"Emploi du temps généré: {len(schedule)} créneaux"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la génération: {str(e)}"
        )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


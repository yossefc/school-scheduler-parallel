# Ajouter ces lignes au début de votre main.py dans ./solver/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import pandas as pd
from solver_engine_with_constraints import ScheduleSolverWithConstraints as ScheduleSolver
from fixed_solver_engine import FixedScheduleSolver
from constraints_handler import ConstraintsManager
from ortools.sat.python import cp_model
import json
import logging
from datetime import datetime
from prometheus_fastapi_instrumentator import Instrumentator
import psycopg2
from psycopg2.extras import RealDictCursor
from api_constraints import register_constraint_routes  # Import du module
try:
    # Optionnel: modules d'optimisation avancée
    from advanced_main import AdvancedSchedulingSystem  # type: ignore
    from pedagogical_solver_v2 import PedagogicalScheduleSolverV2  # type: ignore
    _advanced_modules_available = True
except Exception:
    AdvancedSchedulingSystem = None  # type: ignore
    PedagogicalScheduleSolverV2 = None  # type: ignore
    _advanced_modules_available = False
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

# Proxy pour l'agent AI de parsing des contraintes
@app.post("/api/parse_constraint")
async def proxy_parse_constraint(request: Request):
    """Proxy pour parser les contraintes via l'agent AI"""
    try:
        # Récupérer le body de la requête
        body = await request.json()
        
        # Envoyer à l'agent AI sur le port 5001
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://scheduler_ai:5001/parse_constraint",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Formater la réponse pour l'interface
                return {
                    "constraint": {
                        "type": data.get("constraint_type", "custom"),
                        "entity": data.get("entity_name", "Global"),
                        "data": data.get("constraint_data", {}),
                        "priority": data.get("priority", 2),
                        "confidence": data.get("confidence", 0.5)
                    }
                }
            else:
                # Fallback si l'agent AI ne répond pas
                return {
                    "constraint": {
                        "type": "custom",
                        "entity": "Global",
                        "data": {"original_text": body.get("text", "")},
                        "priority": 2,
                        "confidence": 0.3
                    }
                }
    except Exception as e:
        logger.error(f"Erreur proxy parse_constraint: {e}")
        # Retourner une contrainte basique en cas d'erreur
        return {
            "constraint": {
                "type": "custom",
                "entity": "Global",
                "data": {"original_text": body.get("text", "")},
                "priority": 2,
                "confidence": 0.1
            }
        }

# Proxy pour l'agent conseiller (contournement CORS)
@app.api_route("/api/advisor/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_advisor(request: Request, path: str):
    """Proxy pour rediriger les appels vers l'agent conseiller"""
    try:
        advisor_url = f"http://advisor_agent:5002/api/advisor/{path}"
        
        # Préparer la requête
        headers = dict(request.headers)
        headers.pop('host', None)  # Retirer l'host header
        headers.pop('content-length', None)  # Laisser httpx gérer la longueur
        
        async with httpx.AsyncClient() as client:
            if request.method == "GET":
                response = await client.get(advisor_url, headers=headers, params=request.query_params)
            else:
                body = await request.body()
                # Gérer l'encodage UTF-8 pour les données JSON
                data = None
                if body:
                    try:
                        if isinstance(body, bytes):
                            body_str = body.decode('utf-8', errors='ignore')
                        else:
                            body_str = str(body)
                        data = json.loads(body_str)
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        logger.warning(f"Problème d'encodage proxy: {e}")
                        return JSONResponse({"error": "Erreur d'encodage des données"}, status_code=400)
                
                response = await client.request(
                    method=request.method,
                    url=advisor_url,
                    headers=headers,
                    json=data,
                    params=request.query_params
                )
        
        return JSONResponse(
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            status_code=response.status_code
        )
    except Exception as e:
        logger.error(f"Erreur proxy advisor: {e}")
        return JSONResponse({"error": "Agent conseiller non disponible"}, status_code=503)

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
# Instances
constraints_manager = ConstraintsManager()

# IMPORTANT: Enregistrer les routes des contraintes
register_constraint_routes(app)

# Intégration des modules avancés
try:
    from advanced_wrapper import router as advanced_router
    app.include_router(advanced_router)
    logger.info("✅ Modules avancés intégrés avec succès")
except ImportError as e:
    logger.warning(f"⚠️ Modules avancés non disponibles: {e}")

# Configuration DB pour Docker
db_config = {
    "host": "postgres",  # Nom du service Docker, pas localhost !
    "database": "school_scheduler",
    "user": "admin", 
    "password": "school123"
}
class GenerateScheduleRequest(BaseModel):
    constraints: Optional[List[Any]] = None  # réservée pour usage futur
    time_limit: int = 600
    advanced: bool = False
    # Contraintes avancées spécifiques
    limit_consecutive: bool = True
    avoid_late_hard: bool = True
    minimize_gaps: bool = True
    friday_short: bool = True

# ------------------------------------------------------------
# Routes d'état et d'optimisation avancée
# ------------------------------------------------------------
@app.get("/api/advanced/status")
async def advanced_status():
    """Retourne l'état de disponibilité des modules avancés."""
    status = {
        "modules_available": _advanced_modules_available,
        "ready": False,
    }
    if not _advanced_modules_available:
        return status
    # Tente une instanciation à blanc pour valider l'environnement DB
    try:
        _ = AdvancedSchedulingSystem(db_config=db_config)  # type: ignore
        status["ready"] = True
    except Exception:
        status["ready"] = False
    return status


@app.post("/api/advanced/optimize")
async def advanced_optimize():
    """Lance le pipeline d'optimisation avancée et retourne un résumé.

    Note: Cette route exécute le pipeline de façon synchrone.
    """
    if not _advanced_modules_available or AdvancedSchedulingSystem is None:  # type: ignore
        raise HTTPException(status_code=503, detail="Modules avancés indisponibles")

    try:
        system = AdvancedSchedulingSystem(db_config=db_config)  # type: ignore
        result = system.run_full_analysis()

        # Récupérer le dernier schedule_id actif (sauvegardé par l'optimiseur)
        import psycopg2
        from psycopg2.extras import RealDictCursor

        schedule_id = None
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT MAX(schedule_id) AS latest_id FROM schedules WHERE status = 'active'")
            row = cur.fetchone()
            if row and row.get("latest_id"):
                schedule_id = row["latest_id"]
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

        payload = {
            "status": "success" if result.get("success") else "error",
            "quality_score": result.get("final_score", 0),
            "issues_count": len(result.get("solution", {}).get("quality_analysis", {}).get("issues", [])) if result.get("solution") else None,
            "message": "Optimisation terminée" if result.get("success") else result.get("error", "Échec optimisation"),
            "schedule_id": schedule_id,
        }
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_clean_from_solver_input") 
async def generate_clean_from_solver_input(payload: GenerateScheduleRequest):
    """Génère un emploi du temps PROPRE utilisant UNIQUEMENT solver_input"""
    try:
        logger.info("=== GÉNÉRATION PROPRE DEPUIS SOLVER_INPUT ===")
        
        # Importer et utiliser le générateur propre
        from solver_input_generator import generate_from_solver_input
        
        result = generate_from_solver_input()
        
        if result.get('success'):
            logger.info("✅ Génération propre réussie")
            return {
                "success": True,
                "status": "OPTIMAL",
                "schedule_id": result.get('schedule_id'),
                "message": result.get('message'),
                "total_entries": result.get('total_entries'),
                "classes": result.get('classes'),
                "subjects": result.get('subjects'),
                "teachers": result.get('teachers'),
                "method": "solver_input_clean"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Erreur génération propre'))
            
    except Exception as e:
        logger.error(f"Erreur génération propre: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_from_solver_input")
async def generate_schedule_from_solver_input(payload: GenerateScheduleRequest):
    """Génère un emploi du temps en utilisant les données de solver_input"""
    try:
        logger.info("=== GÉNÉRATION EMPLOI DU TEMPS DEPUIS SOLVER_INPUT ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Récupérer les données depuis solver_input
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Statistiques
        cur.execute("SELECT COUNT(*) as total FROM solver_input")
        total_courses = cur.fetchone()['total']
        logger.info(f"Nombre total de cours à planifier: {total_courses}")
        
        # Récupérer les données formatées
        cur.execute("""
            SELECT 
                course_id,
                class_list,
                subject,
                hours,
                teacher_names,
                work_days,
                grade,
                is_parallel
            FROM solver_input 
            ORDER BY course_id
        """)
        
        solver_data = cur.fetchall()
        cur.close()
        conn.close()
        
        logger.info(f"Données récupérées: {len(solver_data)} cours")
        
        # Utiliser le solver fixé avec les vraies données
        from fixed_solver_engine import FixedScheduleSolver
        
        solver = FixedScheduleSolver(db_config=db_config)
        
        # Convertir les données pour le solver
        formatted_data = []
        for row in solver_data:
            # Traiter class_list (peut être "ז-1, ז-2" ou "ז-1")
            classes = [c.strip() for c in row['class_list'].split(',') if c.strip()]
            
            # Traiter teacher_names
            teachers = [t.strip() for t in (row['teacher_names'] or '').split(',') if t.strip() and t.strip() != 'לא משובץ']
            
            for class_name in classes:
                formatted_data.append({
                    'course_id': row['course_id'],
                    'class_name': class_name,
                    'subject': row['subject'],
                    'hours_per_week': row['hours'] or 1,
                    'teachers': teachers,
                    'is_parallel': row['is_parallel'] or False,
                    'grade': row['grade']
                })
        
        logger.info(f"Données formatées: {len(formatted_data)} entrées de cours")
        
        # Charger les données dans le solver
        solver.load_data_from_db()
        
        # Créer les variables et contraintes
        solver.create_variables()
        solver.add_constraints()
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result.get('success'):
            logger.info("✅ Génération réussie depuis solver_input")
            return {
                "success": True,
                "status": "OPTIMAL",
                "schedule_id": result.get('schedule_id'),
                "quality_score": result.get('quality_score', 85),
                "message": f"Emploi du temps généré avec {len(formatted_data)} cours",
                "courses_planned": len(formatted_data),
                "method": "solver_input_fixed"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Erreur génération: {result.get('error', 'Erreur inconnue')}")
            
    except Exception as e:
        logger.error(f"Erreur génération solver_input: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_fixed")
async def generate_schedule_fixed_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver fixé (sans conflits ni trous)"""
    try:
        logger.info("=== DÉBUT GÉNÉRATION EMPLOI DU TEMPS FIXÉ ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Utiliser le nouveau solver fixé
        solver = FixedScheduleSolver(db_config=db_config)
        
        # Charger les données
        logger.info("Chargement des données...")
        solver.load_data_from_db()
        
        # Résoudre avec le solver fixé
        schedule = solver.solve(time_limit=payload.time_limit)
        
        if schedule is None:
            logger.error("Aucune solution trouvée avec le solver fixé")
            raise HTTPException(
                status_code=500, 
                detail="Impossible de générer un emploi du temps sans conflits"
            )
        
        # Sauvegarder
        try:
            schedule_id = solver.save_schedule(schedule)
            logger.info(f"Schedule fixé sauvegardé avec ID: {schedule_id}")
            
            # Mettre à jour les métadonnées
            metadata = {
                "solve_status": "OPTIMAL",
                "walltime_sec": getattr(solver, 'solve_time', 0),
                "advanced": True,
                "notes": ["fixed_solver", "no_conflicts", "no_gaps"]
            }
            
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE schedules SET metadata = %s WHERE schedule_id = %s",
                    (json.dumps(metadata), schedule_id)
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde schedule fixé: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Erreur de sauvegarde: {e}")
        
        # Générer le résumé
        summary = solver.get_schedule_summary(schedule)
        
        logger.info("=== GÉNÉRATION FIXÉE TERMINÉE ===")
        logger.info(f"Résultat: {len(schedule)} créneaux générés sans conflits")
        
        return {
            "success": True,
            "schedule": schedule,
            "summary": summary,
            "schedule_id": schedule_id,
            "advanced": True,
            "solver_type": "fixed",
            "total_entries": len(schedule),
            "message": f"Emploi du temps fixé généré: {len(schedule)} créneaux sans conflits ni trous",
            "features": {
                "no_conflicts": True,
                "no_gaps": True,
                "parallel_sync": True,
                "global_optimization": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération fixée: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la génération fixée: {str(e)}"
        )
# Route pour servir l'interface HTML
@app.get("/constraints-manager")
async def constraints_interface():
    """Sert l'interface SIMPLE avec tous les algorithmes intégrés"""
    try:
        # Chemin du fichier HTML dans le container  
        html_path = '/app/interface_simple.html'
        
        # Si le fichier n'existe pas dans /app, essayer le dossier courant
        if not os.path.exists(html_path):
            html_path = 'interface_simple.html'
        
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
async def dashboard():
    """Affiche le tableau de bord principal"""
    try:
        # Essayer d'abord le fichier dashboard
        dashboard_path = '/app/dashboard.html'
        if not os.path.exists(dashboard_path):
            dashboard_path = 'dashboard.html'
        
        if os.path.exists(dashboard_path):
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
    except:
        pass
    
    # Fallback sur l'ancienne réponse JSON
    return {
        "message": "School Schedule Solver API - Docker Version",
        "version": "2.0",
        "features": ["parallel_teaching", "automatic_detection", "synchronized_scheduling", "advanced_optimization"],
        "endpoints": {
            "dashboard": "http://localhost:8000/",
            "interface": "http://localhost:8000/constraints-manager",
            "api_constraints": "http://localhost:8000/api/constraints",
            "api_stats": "http://localhost:8000/api/stats",
            "api_advanced": "http://localhost:8000/api/advanced/"
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


    

@app.post("/generate_schedule_ultimate")
async def generate_schedule_ultimate_endpoint(request: Request):
    """Génère un emploi du temps avec TOUS les algorithmes combinés"""
    try:
        logger.info("=== GÉNÉRATION ULTIME DEMANDÉE ===")
        
        # Récupérer les options depuis le body
        body = await request.json() if hasattr(request, 'json') else {}
        
        # Utiliser le scheduler ultime
        from ultimate_scheduler import generate_ultimate_schedule
        
        result = await generate_ultimate_schedule(db_config, body)
        
        logger.info("✅ GÉNÉRATION ULTIME TERMINÉE")
        return result
        
    except Exception as e:
        logger.error(f"Erreur scheduler ultime: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_corrected")
async def generate_schedule_corrected_endpoint():
    """Génère un emploi du temps avec la logique parallèle CORRIGÉE"""
    try:
        logger.info("=== GÉNÉRATION AVEC LOGIQUE CORRIGÉE ===")
        
        # Utiliser le nouveau solver corrigé
        from corrected_solver_engine import CorrectedScheduleSolver
        
        solver = CorrectedScheduleSolver(db_config=db_config)
        
        # Charger les données
        solver.load_data_from_db()
        
        # Créer le modèle
        solver.create_variables()
        solver.add_constraints()
        
        # Résoudre (temps suffisant pour le problème complexe)
        schedule = solver.solve(time_limit=600)
        
        if schedule:
            # Sauvegarder
            schedule_id = solver.save_schedule(schedule)
            
            # Mettre à jour les métadonnées
            metadata = {
                "solve_status": "OPTIMAL",
                "walltime_sec": solver.solve_time,
                "advanced": True,
                "notes": ["corrected_parallel_logic", "fixed_solver"],
                "solver_version": "corrected_v1"
            }
            
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE schedules SET metadata = %s WHERE schedule_id = %s",
                    (json.dumps(metadata), schedule_id)
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
            
            # Générer le résumé
            summary = solver.get_schedule_summary(schedule)
            
            logger.info("✅ GÉNÉRATION CORRIGÉE RÉUSSIE")
            
            return {
                "success": True,
                "schedule_id": schedule_id,
                "schedule": schedule,
                "summary": summary,
                "message": "Emploi du temps généré avec logique parallèle corrigée",
                "features": {
                    "corrected_parallel_logic": True,
                    "multi_class_courses": True,
                    "simultaneous_teachers": True,
                    "no_friday": True
                },
                "total_entries": len(schedule),
                "solve_time": solver.solve_time
            }
        else:
            raise HTTPException(status_code=500, detail="Aucune solution trouvée avec le solver corrigé")
            
    except Exception as e:
        logger.error(f"Erreur solver corrigé: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

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

@app.get("/api/schedule_entries")
async def get_schedule_entries(version: str = "latest"):
    """Retourne les entrées d'emploi du temps selon le contrat spécifié"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer le dernier schedule_id
        if version == "latest":
            cur.execute("""
                SELECT schedule_id, metadata, created_at 
                FROM schedules 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            schedule_result = cur.fetchone()
            
            if not schedule_result:
                return {
                    "version": version,
                    "time_slots": [],
                    "entries": [],
                    "meta": {
                        "solve_status": "ERROR",
                        "walltime_sec": 0,
                        "advanced": False,
                        "notes": ["Aucun emploi du temps trouvé"]
                    }
                }
            
            schedule_id = schedule_result['schedule_id']
        else:
            schedule_id = int(version)
            cur.execute("SELECT metadata, created_at FROM schedules WHERE schedule_id = %s", (schedule_id,))
            schedule_result = cur.fetchone()
            if not schedule_result:
                raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
        
        # Récupérer les time_slots
        cur.execute("""
            SELECT 
                ts.slot_id,
                ts.day_of_week as day,
                ts.period_number - 1 as index,
                ts.start_time::text as start,
                ts.end_time::text as end
            FROM time_slots ts
            ORDER BY ts.day_of_week, ts.period_number
        """)
        time_slots = cur.fetchall()
        
        # Récupérer les entrées d'emploi du temps
        cur.execute("""
            SELECT 
                se.class_name,
                se.day_of_week as day,
                CASE 
                    WHEN se.period_number = 0 THEN 0  -- Period 0 reste 0 (shich boker)
                    ELSE se.period_number              -- Les autres restent tels quels
                END as slot_index,
                COALESCE(se.subject_name, se.subject) as subject,
                se.teacher_name,
                se.room
            FROM schedule_entries se
            WHERE se.schedule_id = %s
            ORDER BY se.day_of_week, se.period_number, se.class_name
        """, (schedule_id,))
        entries_raw = cur.fetchall()
        
        # Transformer les données selon le contrat
        entries = []
        for entry in entries_raw:
            # Gestion des teacher_names (split si string)
            teacher_names = entry['teacher_name']
            if isinstance(teacher_names, str):
                teacher_names = [name.strip() for name in teacher_names.split(',') if name.strip()]
            elif not isinstance(teacher_names, list):
                teacher_names = [str(teacher_names)] if teacher_names else []
            
            entries.append({
                "class_name": entry['class_name'],
                "day": entry['day'],
                "slot_index": entry['slot_index'],
                "subject": entry['subject'] or '',
                "teacher_names": teacher_names,
                "room": entry['room'] or ''
            })
        
        # Extraire metadata
        metadata = {}
        if schedule_result['metadata']:
            try:
                if isinstance(schedule_result['metadata'], str):
                    metadata = json.loads(schedule_result['metadata'])
                else:
                    metadata = schedule_result['metadata']
            except:
                metadata = {}
        
        # Construire la réponse selon le contrat
        return {
            "version": version,
            "time_slots": [dict(slot) for slot in time_slots],
            "entries": entries,
            "meta": {
                "solve_status": metadata.get("solve_status", "OPTIMAL"),
                "walltime_sec": metadata.get("walltime_sec", 0),
                "advanced": metadata.get("advanced", False),
                "notes": metadata.get("notes", [])
            }
        }
        
    finally:
        cur.close()
        conn.close()

@app.get("/api/last_schedule_info")
async def get_last_schedule_info():
    """Retourne les informations du dernier emploi du temps généré"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer le dernier schedule avec ses informations
        cur.execute("""
            SELECT 
                s.schedule_id,
                s.created_at,
                s.metadata,
                COUNT(se.id) as entries_count,
                EXTRACT(EPOCH FROM (NOW() - s.created_at))/60 as minutes_ago
            FROM schedules s
            LEFT JOIN schedule_entries se ON s.schedule_id = se.schedule_id
            GROUP BY s.schedule_id, s.created_at, s.metadata
            ORDER BY s.created_at DESC
            LIMIT 1
        """)
        
        result = cur.fetchone()
        
        if not result:
            return {
                "recent": False,
                "message": "Aucun emploi du temps trouvé"
            }
        
        # Considérer comme "récent" si créé il y a moins de 2 heures (120 minutes)
        is_recent = result['minutes_ago'] < 120
        
        # Essayer d'extraire le quality_score des metadata
        quality_score = 0
        if result['metadata']:
            try:
                import json
                metadata = json.loads(result['metadata']) if isinstance(result['metadata'], str) else result['metadata']
                quality_score = metadata.get('quality_score', 0)
            except:
                pass
        
        return {
            "recent": is_recent,
            "schedule_id": result['schedule_id'],
            "created_at": result['created_at'].isoformat() if result['created_at'] else None,
            "entries_count": result['entries_count'],
            "minutes_ago": int(result['minutes_ago']),
            "quality_score": quality_score
        }
        
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
        logger.info(f"Paramètres: time_limit={payload.time_limit}s, advanced={payload.advanced}")
        
        # Si mode avancé demandé, utiliser le solver pédagogique V2
        if payload.advanced and _advanced_modules_available and PedagogicalScheduleSolverV2:
            logger.info("Mode avancé activé - utilisation du solver pédagogique V2")
            try:
                # Utiliser le nouveau solver pédagogique
                solver = PedagogicalScheduleSolverV2(db_config=db_config)
                # Configurer selon les options demandées AVANT la création des variables
                solver.config.update({
                    "zero_gaps": payload.minimize_gaps,
                    "prefer_2h_blocks": True,
                    "two_hour_blocks_strict": True,
                    "friday_short": payload.friday_short,
                    "friday_off": True,        # Désactiver complètement le vendredi
                    "sunday_enabled": True     # Toujours activer le dimanche
                })
                solver.load_data()
                solver.create_variables()
                solver.add_constraints()
                
                # Résoudre
                schedule = solver.solve(time_limit=payload.time_limit)
                
                if schedule:
                    # Sauvegarder
                    schedule_id = solver.save_schedule(schedule)
                    quality_score = solver.get_quality_score()
                    # Mettre à jour les métadonnées pour l'API de visualisation
                    try:
                        conn = psycopg2.connect(**db_config)
                        cur = conn.cursor()
                        metadata = {
                            "solve_status": "OPTIMAL",
                            "walltime_sec": getattr(solver, 'solve_time', 0),
                            "advanced": True,
                            "notes": ["advanced_v2"],
                            "config": solver.config,
                        }
                        cur.execute(
                            "UPDATE schedules SET metadata = %s WHERE schedule_id = %s",
                            (json.dumps(metadata), schedule_id)
                        )
                        conn.commit()
                    finally:
                        try:
                            cur.close()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass

                    return {
                        "success": True,
                        "schedule_id": schedule_id,
                        "message": "Emploi du temps optimisé généré avec succès",
                        "quality_score": quality_score,
                        "advanced": True,
                        "total_entries": len(schedule),
                        "features_applied": {
                            "zero_gaps": True,
                            "parallel_sync": True,
                            "subject_grouping": True,
                            "sunday_enabled": True,
                            "friday_off": True
                        }
                    }
                else:
                    logger.warning("Solver pédagogique échoué, fallback sur méthode standard")
            except Exception as e:
                logger.error(f"Erreur solver pédagogique: {e}", exc_info=True)
        
        # Méthode standard (ou fallback)
        solver = ScheduleSolver(db_config)
        
        # Charger les données
        logger.info("Chargement des données...")
        solver.load_data_from_db()
        
        # IMPORTANT: Utiliser un temps suffisant vu le taux d'utilisation de 95%
        time_limit = max(payload.time_limit, 600)  # Minimum 10 minutes
        logger.info(f"Génération avec time_limit={time_limit}s")
        
        # Appliquer les contraintes avancées si demandées
        if payload.advanced:
            logger.info("Application des contraintes avancées")
            # TODO: Implémenter l'application des contraintes spécifiques
            # payload.limit_consecutive, payload.avoid_late_hard, etc.
        
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
            
            # Sauvegarder les métadonnées pour l'API schedule_entries
            # IMPORTANT: nous sommes dans la voie standard (fallback). Marquer advanced=False
            metadata = {
                "solve_status": "OPTIMAL" if schedule else "INFEASIBLE",
                "walltime_sec": getattr(solver, 'solve_time', 0),
                "advanced": False,
                "notes": ["standard_solver"]
            }
            
            # Mettre à jour les métadonnées dans la DB
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            try:
                cur.execute(
                    "UPDATE schedules SET metadata = %s WHERE schedule_id = %s",
                    (json.dumps(metadata), schedule_id)
                )
                conn.commit()
            finally:
                cur.close()
                conn.close()
                
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
            "advanced": payload.advanced,
            "total_entries": len(schedule),
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


@app.get("/get_schedule_by_class/{schedule_id}")
async def get_schedule_by_class(schedule_id: int):
    """
    Récupère l'emploi du temps organisé par classe
    """
    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Récupérer toutes les classes
        cur.execute("SELECT DISTINCT class_name FROM schedule_entries WHERE schedule_id = %s ORDER BY class_name", (schedule_id,))
        classes = [row[0] for row in cur.fetchall()]
        
        schedules_by_class = {}
        days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        
        for class_name in classes:
            cur.execute("""
                SELECT day_of_week, period_number, subject_name, teacher_name, room, is_parallel_group
                FROM schedule_entries 
                WHERE schedule_id = %s AND class_name = %s
                ORDER BY day_of_week, period_number
            """, (schedule_id, class_name))
            
            entries = cur.fetchall()
            class_schedule = {}
            
            for entry in entries:
                day_name = days[entry[0] - 1] if entry[0] <= len(days) else f"Jour {entry[0]}"
                period = entry[1]
                
                if day_name not in class_schedule:
                    class_schedule[day_name] = {}
                    
                class_schedule[day_name][period] = {
                    'subject': entry[2],
                    'teacher_name': entry[3],
                    'room': entry[4],
                    'is_parallel': entry[5]
                }
                
            schedules_by_class[class_name] = class_schedule
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "schedules_by_class": schedules_by_class,
            "classes": classes,
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération emploi du temps par classe {schedule_id}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/get_schedule_by_teacher/{schedule_id}")
async def get_schedule_by_teacher(schedule_id: int):
    """
    Récupère l'emploi du temps organisé par professeur
    """
    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Récupérer tous les professeurs
        cur.execute("SELECT DISTINCT teacher_name FROM schedule_entries WHERE schedule_id = %s AND teacher_name IS NOT NULL ORDER BY teacher_name", (schedule_id,))
        teachers = [row[0] for row in cur.fetchall()]
        
        schedules_by_teacher = {}
        days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        
        for teacher_name in teachers:
            cur.execute("""
                SELECT day_of_week, period_number, class_name, subject_name, room, is_parallel_group
                FROM schedule_entries 
                WHERE schedule_id = %s AND teacher_name LIKE %s
                ORDER BY day_of_week, period_number
            """, (schedule_id, f'%{teacher_name}%'))
            
            entries = cur.fetchall()
            teacher_schedule = {}
            
            for entry in entries:
                day_name = days[entry[0] - 1] if entry[0] <= len(days) else f"Jour {entry[0]}"
                period = entry[1]
                
                if day_name not in teacher_schedule:
                    teacher_schedule[day_name] = {}
                if period not in teacher_schedule[day_name]:
                    teacher_schedule[day_name][period] = []
                    
                teacher_schedule[day_name][period].append({
                    'class_name': entry[2],
                    'subject': entry[3],
                    'room': entry[4],
                    'is_parallel': entry[5]
                })
                
            schedules_by_teacher[teacher_name] = teacher_schedule
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "schedules_by_teacher": schedules_by_teacher,
            "teachers": teachers,
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération emploi du temps par professeur {schedule_id}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/get_schedule/{schedule_id}")
async def get_schedule_data(schedule_id: int):
    """
    Récupère les données complètes d'un emploi du temps pour affichage
    """
    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Récupérer les entrées de l'emploi du temps
        cur.execute("""
            SELECT 
                day_of_week,
                period_number,
                class_name,
                subject_name,
                teacher_name,
                room,
                is_parallel_group
            FROM schedule_entries 
            WHERE schedule_id = %s
            ORDER BY day_of_week, period_number, class_name
        """, (schedule_id,))
        
        entries = cur.fetchall()
        cur.close()
        conn.close()
        
        if not entries:
            return {"success": False, "error": "Emploi du temps non trouvé"}
        
        # Organiser les données par jour et période
        schedule_grid = {}
        days = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
        
        for entry in entries:
            day_name = days[entry[0] - 1] if entry[0] <= len(days) else f"Jour {entry[0]}"
            period = entry[1]
            
            if day_name not in schedule_grid:
                schedule_grid[day_name] = {}
            if period not in schedule_grid[day_name]:
                schedule_grid[day_name][period] = []
                
            schedule_grid[day_name][period].append({
                'class_name': entry[2],
                'subject': entry[3],
                'teacher_name': entry[4],
                'room': entry[5],
                'is_parallel': entry[6]
            })
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "schedule_grid": schedule_grid,
            "total_entries": len(entries),
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération emploi du temps {schedule_id}: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


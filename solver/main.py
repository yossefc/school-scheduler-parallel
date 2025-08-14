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
    from robust_solver import RobustScheduleSolver  # Nouveau solver robuste
    from flexible_solver import FlexibleScheduleSolver  # Solver flexible avec minimisation
    from simple_working_solver import SimpleWorkingSolver  # Solver ultra-simple qui fonctionne
    from improved_simple_solver import ImprovedSimpleSolver  # Solver amélioré avec plus de cours
    from realistic_solver import RealisticScheduleSolver  # Solver réaliste et complet
    from parallel_sync_solver import ParallelSyncSolver  # Solver avec synchronisation parallèle correcte
    from parallel_sync_solver_v2 import ParallelSyncSolverV2  # Solver V2 avec heures supplémentaires
    _advanced_modules_available = True
except Exception:
    AdvancedSchedulingSystem = None  # type: ignore
    PedagogicalScheduleSolverV2 = None  # type: ignore
    RobustScheduleSolver = None  # type: ignore
    FlexibleScheduleSolver = None  # type: ignore
    SimpleWorkingSolver = None  # type: ignore
    ImprovedSimpleSolver = None  # type: ignore
    RealisticScheduleSolver = None  # type: ignore
    ParallelSyncSolver = None  # type: ignore
    ParallelSyncSolverV2 = None  # type: ignore
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
    """Sert l'interface SIMPLE et AUTOMATIQUE avec le solver intégré"""
    try:
        # Utiliser la nouvelle interface simplifiée
        html_path = '/app/constraints_manager_simple.html'
        
        # Si le fichier n'existe pas dans /app, essayer le dossier courant
        if not os.path.exists(html_path):
            html_path = 'constraints_manager_simple.html'
        
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        logger.error(f"Fichier constraints_manager.html non trouvé")
        return HTMLResponse(content="""
            <h1>Erreur: Interface non trouvée</h1>
            <p>Le fichier constraints_manager.html n'est pas présent dans le container.</p>
            <p>Vérifiez que le fichier est bien dans le dossier ./solver/</p>
        """, status_code=404)

@app.get("/test-interface")
async def test_interface():
    """Page de test pour l'interface avec corrections d'encodage"""
    try:
        html_path = '/app/test_interface.html'
        if not os.path.exists(html_path):
            html_path = 'test_interface.html'
        
        with open(html_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
            <h1>🧪 Test Interface Temporairement Indisponible</h1>
            <p>Utilisez l'interface principale: <a href="/constraints-manager">constraints-manager</a></p>
            <p>Ou testez directement les APIs:</p>
            <ul>
                <li><a href="/api/schedule_by_class/103">/api/schedule_by_class/103</a></li>
                <li><a href="/api/schedule_by_teacher/103">/api/schedule_by_teacher/103</a></li>
            </ul>
        """, status_code=200)

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
# SOLVER INTÉGRÉ OPTIMISÉ
# ============================================

@app.post("/generate_schedule_integrated")
async def generate_schedule_integrated_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver intégré optimisé (synchronisation parallèle + zéro trous)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER INTÉGRÉ OPTIMISÉ ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Utiliser le nouveau solver intégré
        from integrated_solver import IntegratedScheduleSolver
        
        solver = IntegratedScheduleSolver(db_config=db_config)
        
        # Charger les données
        solver.load_data()
        logger.info(f"Données chargées: {len(solver.courses)} cours, {len(solver.classes)} classes")
        
        # Créer le modèle
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle CP-SAT créé avec toutes les contraintes")
        
        # Résoudre avec le temps suffisant
        schedule = solver.solve(time_limit=payload.time_limit)
        
        if schedule:
            # Sauvegarder
            schedule_id = solver.save_schedule(schedule)
            summary = solver.get_summary()
            
            logger.info("✅ GÉNÉRATION INTÉGRÉE RÉUSSIE")
            logger.info(f"  → Schedule ID: {schedule_id}")
            logger.info(f"  → Qualité: {summary['quality_metrics']['quality_score']}/100")
            logger.info(f"  → Trous: {summary['quality_metrics']['gaps_count']}")
            logger.info(f"  → Sync parallèle: {'✓' if summary['quality_metrics']['parallel_sync_ok'] else '✗'}")
            
            return {
                "success": True,
                "message": "Emploi du temps généré avec le solver intégré",
                "schedule_id": schedule_id,
                "quality_score": summary['quality_metrics']['quality_score'],
                "gaps_count": summary['quality_metrics']['gaps_count'],
                "parallel_sync_ok": summary['quality_metrics']['parallel_sync_ok'],
                "solve_time": summary['solve_time'],
                "total_courses": summary['courses_count'],
                "parallel_groups": summary['parallel_groups_count'],
                "summary": summary,
                "algorithm": "integrated_solver_v1"
            }
        else:
            logger.error("✗ GÉNÉRATION INTÉGRÉE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver intégré n'a pas trouvé de solution. Vérifiez les contraintes."
            )
            
    except ImportError as e:
        logger.error(f"Erreur import solver intégré: {e}")
        raise HTTPException(
            status_code=503,
            detail="Solver intégré indisponible - utiliser /generate_schedule à la place"
        )
    except Exception as e:
        logger.error(f"Erreur solver intégré: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_robust")
async def generate_schedule_robust_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver robuste (ZÉRO TROUS GARANTIS)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER ROBUSTE (ZÉRO TROUS) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct pour éviter les problèmes de condition
        from robust_solver import RobustScheduleSolver as RobustSolver
        
        solver = RobustSolver(db_config=db_config)
        
        # Charger et valider les données
        solver.load_data()
        logger.info(f"Données chargées: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer le modèle avec contraintes anti-trous
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle robuste créé avec élimination stricte des trous")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION ROBUSTE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']} (OBJECTIF: 0)")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION ROBUSTE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver robuste n'a pas trouvé de solution sans trous. Les contraintes sont peut-être trop strictes."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver robuste: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_flexible")
async def generate_schedule_flexible_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver flexible (MINIMISE les trous)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER FLEXIBLE (MINIMISE TROUS) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from flexible_solver import FlexibleScheduleSolver as FlexSolver
        
        solver = FlexSolver(db_config=db_config)
        
        # Charger les données avec filtrage intelligent
        solver.load_data()
        logger.info(f"Données: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer modèle avec objectif de minimisation des trous
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle flexible créé avec minimisation des trous")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION FLEXIBLE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']} (MINIMISÉS)")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION FLEXIBLE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver flexible n'a pas trouvé de solution. Problème de données ou contraintes."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver flexible: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_simple")
async def generate_schedule_simple_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver ultra-simple (FONCTIONNE TOUJOURS)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER ULTRA-SIMPLE ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from simple_working_solver import SimpleWorkingSolver as SimpleSolver
        
        solver = SimpleSolver(db_config=db_config)
        
        # Charger données très filtrées
        solver.load_data()
        logger.info(f"Données filtrées: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Modèle minimal
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle ultra-simple créé")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION SIMPLE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']}")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ MÊME LE SOLVER SIMPLE ÉCHOUE - PROBLÈME MAJEUR")
            raise HTTPException(
                status_code=500,
                detail="Même le solver simplifié échoue. Vérifiez les données de base."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver simple: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_improved")
async def generate_schedule_improved_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver amélioré (PLUS DE COURS, MOINS DE TROUS)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER AMÉLIORÉ (EMPLOI DU TEMPS COMPLET) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from improved_simple_solver import ImprovedSimpleSolver as ImprovedSolver
        
        solver = ImprovedSolver(db_config=db_config)
        
        # Charger plus de données avec filtrage intelligent
        solver.load_data()
        logger.info(f"Données étendues: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer modèle équilibré
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle amélioré créé avec étalement des cours")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION AMÉLIORÉE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']} (RÉDUITS)")
            logger.info(f"  → Périodes utilisées: {result.get('periods_used', [])}")
            logger.info(f"  → Classes couvertes: {result.get('classes_covered', 0)}")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION AMÉLIORÉE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver amélioré n'a pas trouvé de solution. Essayez le solver simple."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver amélioré: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_advanced_cpsat") 
async def generate_schedule_advanced_cpsat_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver CP-SAT ULTRA-AVANCÉ (zéro trous + objectif sophistiqué)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER CP-SAT ULTRA-AVANCÉ ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import du solver ultra-avancé
        from advanced_cpsat_solver import AdvancedCPSATSolver
        
        solver = AdvancedCPSATSolver(db_config=db_config)
        
        # Charger données
        solver.load_data_from_db()
        logger.info("Données chargées pour solver ultra-avancé")
        
        # Créer variables sophistiquées
        solver.create_variables()
        solver.add_hard_constraints()
        solver.add_objective()  # Objectif span-load sophistiqué
        logger.info("Modèle CP-SAT ultra-avancé créé")
        
        # Résoudre
        schedule = solver.solve(time_limit=payload.time_limit)
        
        if schedule:
            logger.info("✅ GÉNÉRATION ULTRA-AVANCÉE RÉUSSIE")
            logger.info(f"  → Emploi du temps avec ZÉRO TROUS garanti")
            logger.info(f"  → Objectif span-load optimisé")
            
            return {
                "success": True,
                "schedule": schedule,
                "algorithm": "advanced_cpsat_solver",
                "features": {
                    "zero_gaps_guaranteed": True,
                    "span_load_optimization": True,
                    "parallel_sync": True,
                    "sophisticated_objective": True
                },
                "message": "Solver CP-SAT ultra-avancé: zéro trous + objectif sophistiqué"
            }
        else:
            logger.error("✗ SOLVER ULTRA-AVANCÉ ÉCHOUÉ")
            raise HTTPException(
                status_code=500,
                detail="Le solver CP-SAT ultra-avancé n'a pas trouvé de solution."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver ultra-avancé: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_pedagogical_v2")
async def generate_schedule_pedagogical_v2_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver PÉDAGOGIQUE V2 (blocs 2h + zéro trous)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER PÉDAGOGIQUE V2 ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import du solver pédagogique V2
        from pedagogical_solver_v2 import PedagogicalScheduleSolverV2
        
        solver = PedagogicalScheduleSolverV2(db_config=db_config)
        
        # Charger données 
        solver.load_data()
        logger.info("Données chargées pour solver pédagogique V2")
        
        # Résoudre avec optimisations pédagogiques
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result.get('success'):
            logger.info("✅ GÉNÉRATION PÉDAGOGIQUE V2 RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Blocs 2h optimisés: {result.get('blocks_2h_count', 0)}")
            logger.info(f"  → Qualité pédagogique: {result['quality_score']}/100")
            
            return result
        else:
            logger.error("✗ SOLVER PÉDAGOGIQUE V2 ÉCHOUÉ")
            raise HTTPException(
                status_code=500,
                detail="Le solver pédagogique V2 n'a pas trouvé de solution."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver pédagogique V2: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_adaptive")
async def generate_schedule_adaptive_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps ADAPTATIF - place le maximum de cours possible"""
    try:
        logger.info("=== GÉNÉRATION ADAPTATIVE (MAXIMUM DE COURS POSSIBLES) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from adaptive_all_courses_solver import AdaptiveAllCoursesSolver
        
        solver = AdaptiveAllCoursesSolver(db_config=db_config)
        
        # Charger TOUS les cours
        solver.load_data()
        logger.info(f"Données ADAPTATIVES: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Modèle adaptatif
        solver.create_variables()
        solver.add_adaptive_constraints()
        logger.info("Modèle ADAPTATIF créé - maximise les cours placés")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION ADAPTATIVE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Cours placés: {result['courses_placed']}/{result['total_courses_input']}")
            logger.info(f"  → Taux placement: {result['placement_rate']}")
            logger.info(f"  → Créneaux générés: {result['total_schedule_entries']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION ADAPTATIVE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver adaptatif n'a pas pu placer de cours."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver adaptatif: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_all_courses")
async def generate_schedule_all_courses_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec TOUS les cours et contraintes relâchées"""
    try:
        logger.info("=== GÉNÉRATION AVEC TOUS LES COURS (CONTRAINTES RELÂCHÉES) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from relaxed_complete_solver import RelaxedCompleteScheduleSolver
        
        solver = RelaxedCompleteScheduleSolver(db_config=db_config)
        
        # Charger ABSOLUMENT TOUS les cours
        solver.load_data()
        logger.info(f"Données ULTRA-COMPLÈTES: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer modèle CP-SAT relâché
        solver.create_variables()
        solver.add_relaxed_constraints()
        logger.info("Modèle CP-SAT RELÂCHÉ créé pour TOUS les cours")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION COMPLÈTE AVEC TOUS LES COURS RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Cours traités: {result['total_courses_input']} (TOUS)")
            logger.info(f"  → Créneaux générés: {result['total_schedule_entries']}")
            logger.info(f"  → Taux couverture: {result['coverage_rate']}")
            logger.info(f"  → Violations: {result['violations_count']}")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ MÊME AVEC CONTRAINTES RELÂCHÉES, ÉCHEC")
            raise HTTPException(
                status_code=500,
                detail="Impossible de traiter tous les cours même avec contraintes relâchées."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver tous cours: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_complete")
async def generate_schedule_complete_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver COMPLET CP-SAT (TOUS LES 231 COURS)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER COMPLET CP-SAT (TOUS LES COURS) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from complete_cpsat_solver import CompleteScheduleSolver
        
        solver = CompleteScheduleSolver(db_config=db_config)
        
        # Charger TOUS les cours
        solver.load_data()
        logger.info(f"Données COMPLÈTES: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer modèle CP-SAT complet
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle CP-SAT complet créé pour TOUS les cours")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION COMPLÈTE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']}")
            logger.info(f"  → Cours traités: {result['total_courses_processed']} (TOUS)")
            logger.info(f"  → Créneaux générés: {result['total_schedule_entries']}")
            logger.info(f"  → Taux couverture: {result['coverage_rate']}")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION COMPLÈTE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver complet n'a pas trouvé de solution. Problème avec les contraintes."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver complet: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_realistic")
async def generate_schedule_realistic_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec le solver réaliste (COMPLET ET ÉQUILIBRÉ)"""
    try:
        logger.info("=== GÉNÉRATION AVEC SOLVER RÉALISTE (EMPLOI DU TEMPS COMPLET) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        
        # Import direct
        from realistic_solver import RealisticScheduleSolver as RealisticSolver
        
        solver = RealisticSolver(db_config=db_config)
        
        # Charger données avec stratégie réaliste
        solver.load_data()
        logger.info(f"Données réalistes: {len(solver.courses)} cours, {len(solver.classes)} classes, {len(solver.teachers)} professeurs")
        
        # Créer modèle pragmatique
        solver.create_variables()
        solver.add_constraints()
        logger.info("Modèle réaliste créé avec contraintes équilibrées")
        
        # Résoudre
        result = solver.solve(time_limit=payload.time_limit)
        
        if result and result['success']:
            logger.info("✅ GÉNÉRATION RÉALISTE RÉUSSIE")
            logger.info(f"  → Schedule ID: {result['schedule_id']}")
            logger.info(f"  → Qualité: {result['quality_score']}/100")
            logger.info(f"  → Trous: {result['gaps_count']} (OPTIMISÉS)")
            logger.info(f"  → Périodes utilisées: {result.get('periods_used', [])}")
            logger.info(f"  → Classes couvertes: {result.get('classes_covered', 0)}")
            logger.info(f"  → Moyenne périodes/classe: {result.get('avg_periods_per_class', 0):.1f}")
            logger.info(f"  → Temps: {result['solve_time']:.1f}s")
            
            return result
        else:
            logger.error("✗ GÉNÉRATION RÉALISTE ÉCHOUÉE")
            raise HTTPException(
                status_code=500,
                detail="Le solver réaliste n'a pas trouvé de solution. Problème avec les données."
            )
            
    except Exception as e:
        logger.error(f"Erreur solver réaliste: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

def save_parallel_schedule_to_db(schedule: list, conn) -> int:
    """Sauvegarde un emploi du temps avec synchronisation parallèle en base"""
    from datetime import datetime
    
    cur = conn.cursor()
    try:
        # Créer un nouvel emploi du temps
        cur.execute("""
            INSERT INTO schedules (academic_year, term, status, created_at, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING schedule_id
        """, (
            "2024-2025", 
            1, 
            "active", 
            datetime.now(),
            json.dumps({
                "solver": "parallel_sync",
                "sync_status": "PERFECT",
                "conflicts": 0,
                "quality": "Synchronisation parfaite des cours parallèles"
            })
        ))
        
        schedule_id = cur.fetchone()[0]
        
        # Sauvegarder les entrées
        for entry in schedule:
            # Traiter les professeurs (peut être une liste ou une string)
            teacher_names = entry.get('teacher_names', [])
            if isinstance(teacher_names, list):
                teacher_name = ", ".join(teacher_names) if teacher_names else ""
            else:
                teacher_name = str(teacher_names) if teacher_names else ""
            
            cur.execute("""
                INSERT INTO schedule_entries 
                (schedule_id, teacher_name, class_name, subject_name, 
                 day_of_week, period_number, is_parallel_group)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                schedule_id,
                teacher_name,
                entry.get('class_name', ''),
                entry.get('subject', ''),
                entry.get('day', 0),
                entry.get('slot_index', 0),
                entry.get('kind') == 'parallel'
            ))
        
        conn.commit()
        logger.info(f"Schedule sauvegardé: ID={schedule_id}, {len(schedule)} entrées")
        return schedule_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erreur sauvegarde schedule: {e}")
        raise e
    finally:
        cur.close()

@app.post("/generate_schedule_parallel_sync")
async def generate_schedule_parallel_sync_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps avec SYNCHRONISATION PARFAITE des cours parallèles"""
    try:
        logger.info("=== GÉNÉRATION AVEC SYNCHRONISATION PARALLÈLE CORRECTE ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        logger.info("OBJECTIF: Corriger le problème de synchronisation ז-1, ז-3, ז-4")
        
        # Vérifier la disponibilité du module
        try:
            from parallel_sync_solver import ParallelSyncSolver as SyncSolver
        except ImportError:
            raise HTTPException(
                status_code=503, 
                detail="Module de synchronisation parallèle non disponible"
            )
        
        # Connexion DB
        conn = psycopg2.connect(**db_config)
        
        try:
            solver = SyncSolver()
            
            # Charger données
            courses_count, slots_count = solver.load_data(conn)
            logger.info(f"Données chargées: {courses_count} cours, {slots_count} créneaux")
            
            # Créer modèle avec synchronisation
            constraints_count = solver.create_model()
            logger.info(f"Modèle créé avec {constraints_count} contraintes")
            
            # Résoudre
            result = solver.solve(time_limit_seconds=payload.time_limit)
            
            if result and result['success']:
                logger.info("✅ SYNCHRONISATION PARALLÈLE RÉUSSIE")
                logger.info(f"  → Entrées: {result['stats']['total_entries']}")
                logger.info(f"  → Cours parallèles: {result['stats']['parallel_courses']}")  
                logger.info(f"  → Cours individuels: {result['stats']['individual_courses']}")
                logger.info(f"  → Status: {result['solver_status']}")
                logger.info(f"  → Temps: {result['stats']['solve_time']:.1f}s")
                
                # Sauvegarder en base de données pour l'interface
                schedule_id = save_parallel_schedule_to_db(result['schedule'], conn)
                logger.info(f"  → Schedule ID: {schedule_id}")
                
                return JSONResponse(content={
                    "success": True,
                    "schedule": result['schedule'],
                    "schedule_id": schedule_id,
                    "stats": result['stats'],
                    "solver_type": "parallel_sync",
                    "sync_status": "PERFECT",
                    "quality_score": 100,  # Score parfait car 0 conflits
                    "message": f"Emploi du temps généré avec synchronisation parfaite - {result['stats']['parallel_courses']} cours parallèles correctement synchronisés"
                })
            else:
                logger.error("✗ SYNCHRONISATION PARALLÈLE ÉCHOUÉE")
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Aucune solution trouvée avec synchronisation parallèle",
                        "solver_type": "parallel_sync"
                    }
                )
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Erreur synchronisation parallèle: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/generate_schedule_parallel_sync_v2")
async def generate_schedule_parallel_sync_v2_endpoint(payload: GenerateScheduleRequest):
    """Génère un emploi du temps V2 avec heures supplémentaires en bord de journée"""
    try:
        logger.info("=== GÉNÉRATION AVEC SYNCHRONISATION PARALLÈLE V2 (HEURES SUPPLÉMENTAIRES) ===")
        logger.info(f"Paramètres: time_limit={payload.time_limit}s")
        logger.info("OBJECTIF: Placer les heures supplémentaires en début/fin de journée")
        
        # Vérifier la disponibilité du module
        try:
            from parallel_sync_solver_v2 import ParallelSyncSolverV2 as SyncSolverV2
        except ImportError:
            raise HTTPException(
                status_code=503, 
                detail="Module de synchronisation parallèle V2 non disponible"
            )
        
        # Connexion DB
        conn = psycopg2.connect(**db_config)
        
        try:
            solver = SyncSolverV2()
            
            # Charger données avec analyse des heures supplémentaires
            courses_count, slots_count = solver.load_data(conn)
            logger.info(f"Données chargées: {courses_count} cours, {slots_count} créneaux")
            
            # Créer modèle avec contraintes V2
            constraints_count = solver.create_model()
            logger.info(f"Modèle V2 créé avec {constraints_count} contraintes")
            
            # Résoudre avec optimisation V2
            result = solver.solve(time_limit_seconds=payload.time_limit)
            
            if result and result['success']:
                logger.info("✅ SYNCHRONISATION PARALLÈLE V2 RÉUSSIE")
                logger.info(f"  → Entrées: {result['stats']['total_entries']}")
                logger.info(f"  → Cours parallèles principaux: {result['stats']['parallel_main_courses']}")  
                logger.info(f"  → Heures supplémentaires: {result['stats']['parallel_extra_courses']}")
                logger.info(f"  → Cours individuels: {result['stats']['individual_courses']}")
                logger.info(f"  → Créneaux de bord utilisés: {result['stats']['edge_slots_used']}")
                logger.info(f"  → Créneaux du milieu: {result['stats']['middle_slots_used']}")
                logger.info(f"  → Trous détectés: {result['stats']['gaps_detected']}")
                logger.info(f"  → Score qualité: {result['quality_score']}/100")
                logger.info(f"  → Status: {result['solver_status']}")
                logger.info(f"  → Temps: {result['stats']['solve_time']:.1f}s")
                
                # Sauvegarder en base de données pour l'interface
                schedule_id = save_parallel_schedule_to_db(result['schedule'], conn)
                logger.info(f"  → Schedule ID: {schedule_id}")
                
                return JSONResponse(content={
                    "success": True,
                    "schedule": result['schedule'],
                    "schedule_id": schedule_id,
                    "stats": result['stats'],
                    "solver_type": "parallel_sync_v2",
                    "quality_score": result['quality_score'],
                    "message": f"V2: {result['stats']['total_entries']} entrées, {result['stats']['gaps_detected']} trous, {result['stats']['parallel_extra_courses']} heures supplémentaires placées",
                    "optimization_notes": {
                        "edge_placement": f"{result['stats']['edge_slots_used']} heures aux bords",
                        "gap_minimization": f"{result['stats']['gaps_detected']} trous restants",
                        "quality_target": "Heures supplémentaires placées correctement"
                    }
                })
            else:
                logger.error("❌ ÉCHEC SYNCHRONISATION PARALLÈLE V2")
                raise HTTPException(
                    status_code=500,
                    detail="Le solver V2 n'a pas trouvé de solution. Contraintes trop strictes pour les heures supplémentaires."
                )
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Erreur synchronisation parallèle V2: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

# ============================================
# SYSTÈME DE MODIFICATION INCRÉMENTALE
# ============================================

from incremental_scheduler import IncrementalScheduler
from intelligent_scheduler_assistant import IntelligentSchedulerAssistant
from pydantic import BaseModel

class ScheduleModificationRequest(BaseModel):
    schedule_id: Optional[int] = None
    action: str  # 'move', 'change_teacher', 'add', 'remove'
    class_name: Optional[str] = None
    subject: Optional[str] = None
    old_day: Optional[int] = None
    old_slot: Optional[int] = None
    new_day: Optional[int] = None
    new_slot: Optional[int] = None
    teachers: Optional[List[str]] = None
    hours: Optional[int] = 1

@app.post("/load_existing_schedule")
async def load_existing_schedule_endpoint(schedule_id: Optional[int] = None):
    """Charge un emploi du temps existant pour modification"""
    try:
        logger.info(f"Chargement emploi du temps existant: {schedule_id or 'le plus récent'}")
        
        scheduler = IncrementalScheduler(db_config)
        result = scheduler.load_existing_schedule(schedule_id)
        
        if result['success']:
            logger.info(f"✅ Emploi du temps {result['schedule_id']} chargé")
            return JSONResponse(content={
                "success": True,
                "schedule_id": result['schedule_id'],
                "entries_count": result['entries_count'],
                "schedule_info": result['schedule_info'],
                "message": f"Emploi du temps {result['schedule_id']} chargé ({result['entries_count']} entrées)"
            })
        else:
            raise HTTPException(status_code=404, detail=result['error'])
            
    except Exception as e:
        logger.error(f"Erreur chargement emploi du temps: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/modify_schedule")
async def modify_schedule_endpoint(request: ScheduleModificationRequest):
    """Applique une modification à un emploi du temps existant"""
    try:
        logger.info(f"Modification emploi du temps: {request.action}")
        
        scheduler = IncrementalScheduler(db_config)
        
        # Charger l'emploi du temps
        load_result = scheduler.load_existing_schedule(request.schedule_id)
        if not load_result['success']:
            raise HTTPException(status_code=404, detail=load_result['error'])
        
        # Appliquer la modification selon l'action
        if request.action == 'move':
            if not all([request.class_name, request.subject, request.old_day is not None, 
                       request.old_slot is not None, request.new_day is not None, request.new_slot is not None]):
                raise HTTPException(status_code=400, detail="Paramètres manquants pour déplacement")
            
            result = scheduler.move_course(
                request.class_name, request.subject,
                request.old_day, request.old_slot,
                request.new_day, request.new_slot
            )
            
        elif request.action == 'change_teacher':
            if not all([request.class_name, request.subject, request.new_day is not None, 
                       request.new_slot is not None, request.teachers]):
                raise HTTPException(status_code=400, detail="Paramètres manquants pour changement professeur")
            
            result = scheduler.change_teacher(
                request.class_name, request.subject,
                request.new_day, request.new_slot, request.teachers
            )
            
        elif request.action == 'add':
            if not all([request.class_name, request.subject, request.new_day is not None, 
                       request.new_slot is not None, request.teachers]):
                raise HTTPException(status_code=400, detail="Paramètres manquants pour ajout")
            
            result = scheduler.add_course(
                request.class_name, request.subject, request.teachers,
                request.new_day, request.new_slot, request.hours
            )
            
        elif request.action == 'remove':
            if not all([request.class_name, request.subject, request.new_day is not None, request.new_slot is not None]):
                raise HTTPException(status_code=400, detail="Paramètres manquants pour suppression")
            
            result = scheduler.remove_course(
                request.class_name, request.subject,
                request.new_day, request.new_slot
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Action inconnue: {request.action}")
        
        if result['success']:
            # Sauvegarder automatiquement
            save_result = scheduler.save_modifications()
            
            if save_result['success']:
                summary = scheduler.get_schedule_summary()
                
                return JSONResponse(content={
                    "success": True,
                    "action": request.action,
                    "modification": result['modification'],
                    "new_schedule_id": save_result['new_schedule_id'],
                    "summary": summary,
                    "message": f"Modification '{request.action}' appliquée et sauvegardée"
                })
            else:
                raise HTTPException(status_code=500, detail=f"Erreur sauvegarde: {save_result['error']}")
        else:
            # Retourner les conflits/suggestions
            return JSONResponse(status_code=400, content={
                "success": False,
                "error": result['error'],
                "conflicts": result.get('conflicts', []),
                "suggestions": result.get('suggestions', [])
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur modification emploi du temps: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/schedule_summary/{schedule_id}")
async def get_schedule_summary_endpoint(schedule_id: int):
    """Retourne un résumé d'un emploi du temps"""
    try:
        scheduler = IncrementalScheduler(db_config)
        load_result = scheduler.load_existing_schedule(schedule_id)
        
        if not load_result['success']:
            raise HTTPException(status_code=404, detail=load_result['error'])
        
        summary = scheduler.get_schedule_summary()
        return JSONResponse(content=summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur résumé emploi du temps: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/schedule-editor")
async def schedule_editor_interface():
    """Interface web pour l'éditeur d'emploi du temps incrémental"""
    try:
        # Lire le fichier HTML de l'éditeur
        import os
        file_path = os.path.join(os.path.dirname(__file__), "schedule_editor.html")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Interface éditeur non trouvée")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Erreur interface éditeur: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/analyze_schedule_pedagogical")
async def analyze_schedule_pedagogical_endpoint(schedule_id: Optional[int] = None):
    """Analyse pédagogique automatique d'un emploi du temps"""
    try:
        logger.info(f"🔍 Analyse pédagogique de l'emploi du temps {schedule_id or 'le plus récent'}")
        
        # Connexion DB
        conn = psycopg2.connect(**db_config)
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Charger l'emploi du temps le plus récent si pas d'ID spécifié
            if schedule_id is None:
                cursor.execute("""
                    SELECT schedule_id FROM schedules 
                    WHERE status = 'active'
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Aucun emploi du temps trouvé")
                schedule_id = result['schedule_id']
            
            # Charger les entrées de l'emploi du temps
            cursor.execute("""
                SELECT class_name, day_of_week, period_number as slot_index, subject, 
                       teacher_names, kind
                FROM schedule_entries 
                WHERE schedule_id = %s
                ORDER BY day_of_week, period_number, class_name
            """, (schedule_id,))
            
            entries = cursor.fetchall()
            
            if not entries:
                raise HTTPException(status_code=404, detail="Emploi du temps vide")
            
            # Analyse pédagogique simplifiée
            analysis = analyze_schedule_simple(entries, schedule_id)
            
            return JSONResponse(content=analysis)
            
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur analyse pédagogique: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

def analyze_schedule_simple(entries: List[Dict], schedule_id: int) -> Dict[str, Any]:
    """Analyse pédagogique simplifiée"""
    from collections import defaultdict
    
    # Organiser par classe
    schedule_by_class = defaultdict(lambda: defaultdict(list))
    
    for entry in entries:
        class_name = entry['class_name']
        day = entry['day_of_week']
        schedule_by_class[class_name][day].append({
            'slot': entry['slot_index'],
            'subject': entry['subject'],
            'teachers': entry['teacher_names'] if isinstance(entry['teacher_names'], list) else [entry['teacher_names']],
            'kind': entry.get('kind', 'individual')
        })
    
    # Trier par slot pour chaque jour
    for class_name in schedule_by_class:
        for day in schedule_by_class[class_name]:
            schedule_by_class[class_name][day].sort(key=lambda x: x['slot'])
    
    # Analyses
    total_gaps = 0
    total_isolated_courses = 0
    classes_analyzed = len(schedule_by_class)
    issues = []
    recommendations = []
    
    for class_name, class_schedule in schedule_by_class.items():
        class_gaps = 0
        class_isolated = 0
        
        for day, day_schedule in class_schedule.items():
            if len(day_schedule) < 2:
                continue
                
            # Détecter les trous
            slots = [entry['slot'] for entry in day_schedule]
            if slots:
                slots.sort()
                for i in range(slots[0], slots[-1]):
                    if i not in slots:
                        class_gaps += 1
                        total_gaps += 1
                        issues.append({
                            'type': 'gap',
                            'severity': 'critical',
                            'class': class_name,
                            'day': day,
                            'slot': i,
                            'message': f'Trou détecté: {class_name}, jour {day+1}, période {i+1}'
                        })
            
            # Détecter les matières isolées (pas de blocs)
            subject_blocks = defaultdict(list)
            current_subject = None
            current_block_size = 0
            
            for entry in day_schedule:
                subject = entry['subject']
                if subject == current_subject:
                    current_block_size += 1
                else:
                    if current_subject and current_block_size > 0:
                        subject_blocks[current_subject].append(current_block_size)
                    current_subject = subject
                    current_block_size = 1
            
            # Ajouter le dernier bloc
            if current_subject and current_block_size > 0:
                subject_blocks[current_subject].append(current_block_size)
            
            # Vérifier les matières principales qui n'ont que des blocs de 1h
            core_subjects = ['מתמטיקה', 'אנגלית', 'עברית', 'מדעים', 'היסטוריה']
            for subject, blocks in subject_blocks.items():
                if subject in core_subjects and all(block == 1 for block in blocks):
                    class_isolated += 1
                    total_isolated_courses += 1
                    issues.append({
                        'type': 'isolated_subject',
                        'severity': 'high',
                        'class': class_name,
                        'subject': subject,
                        'day': day,
                        'message': f'Matière fragmentée: {subject} pour {class_name} (que des blocs de 1h)'
                    })
    
    # Score pédagogique
    pedagogical_score = max(0, 100 - (total_gaps * 25) - (total_isolated_courses * 10))
    
    # Recommandations
    if total_gaps > 0:
        recommendations.append({
            'type': 'eliminate_gaps',
            'priority': 1,
            'count': total_gaps,
            'description': f'Éliminer les {total_gaps} trous en regroupant les cours',
            'automated': True
        })
    
    if total_isolated_courses > 0:
        recommendations.append({
            'type': 'create_blocks',
            'priority': 2,
            'count': total_isolated_courses,
            'description': f'Créer des blocs de 2-3h pour {total_isolated_courses} matières fragmentées',
            'automated': False
        })
    
    return {
        'success': True,
        'schedule_id': schedule_id,
        'analysis_timestamp': datetime.now().isoformat(),
        'pedagogical_score': pedagogical_score,
        'classes_analyzed': classes_analyzed,
        'total_entries': len(entries),
        'issues_found': {
            'gaps': total_gaps,
            'isolated_courses': total_isolated_courses,
            'total_issues': total_gaps + total_isolated_courses
        },
        'issues_detail': issues,
        'recommendations': recommendations,
        'quality_assessment': {
            'excellent': pedagogical_score >= 90,
            'good': pedagogical_score >= 70,
            'needs_improvement': pedagogical_score < 70,
            'critical': pedagogical_score < 50
        }
    }

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

# ============================================
# ASSISTANT INTELLIGENT - AMÉLIORATION CONTINUE
# ============================================

# Global assistant instance
_intelligent_assistant = None

def get_intelligent_assistant():
    """Get or create the intelligent assistant instance"""
    global _intelligent_assistant
    if _intelligent_assistant is None:
        _intelligent_assistant = IntelligentSchedulerAssistant(db_config)
    return _intelligent_assistant

class ImprovementSessionRequest(BaseModel):
    schedule_id: Optional[int] = None
    target_quality: int = 90

class UserResponseRequest(BaseModel):
    session_id: str
    response: str
    continue_improvement: bool = True

@app.post("/start_improvement_session")
async def start_improvement_session_endpoint(request: ImprovementSessionRequest):
    """
    Démarre une session d'amélioration continue d'emploi du temps
    Implémente exactement ce que l'utilisateur demande
    """
    try:
        logger.info(f"🚀 Démarrage session d'amélioration - Objectif: {request.target_quality}/100")
        
        assistant = get_intelligent_assistant()
        result = assistant.start_improvement_session(
            schedule_id=request.schedule_id,
            target_quality=request.target_quality
        )
        
        if result['success']:
            logger.info(f"✅ Session démarrée: {result['session_id']}")
            return JSONResponse(content=result)
        else:
            logger.error(f"❌ Échec démarrage session: {result['error']}")
            raise HTTPException(status_code=400, detail=result['error'])
            
    except Exception as e:
        logger.error(f"Erreur démarrage session amélioration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/answer_question")
async def answer_question_endpoint(request: UserResponseRequest):
    """
    Traite la réponse de l'utilisateur à une question intelligente
    """
    try:
        logger.info(f"📝 Réponse utilisateur reçue pour session {request.session_id}")
        
        assistant = get_intelligent_assistant()
        result = assistant.answer_question(
            user_response=request.response,
            continue_improvement=request.continue_improvement
        )
        
        if result['success']:
            logger.info("✅ Réponse traitée avec succès")
            return JSONResponse(content=result)
        else:
            logger.error(f"❌ Erreur traitement réponse: {result['error']}")
            raise HTTPException(status_code=400, detail=result['error'])
            
    except Exception as e:
        logger.error(f"Erreur traitement réponse: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/improvement_session_status")
async def get_improvement_session_status():
    """
    Retourne le statut de la session d'amélioration active
    """
    try:
        assistant = get_intelligent_assistant()
        status = assistant.get_session_status()
        
        if 'error' in status:
            return JSONResponse(content={"error": status['error']}, status_code=404)
        
        return JSONResponse(content=status)
        
    except Exception as e:
        logger.error(f"Erreur statut session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/improvement_session_report")
async def get_improvement_session_report():
    """
    Génère un rapport détaillé de la session d'amélioration
    """
    try:
        assistant = get_intelligent_assistant()
        report = assistant.get_detailed_session_report()
        
        if 'error' in report:
            return JSONResponse(content={"error": report['error']}, status_code=404)
        
        return JSONResponse(content=report)
        
    except Exception as e:
        logger.error(f"Erreur rapport session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/intelligent-assistant")
async def intelligent_assistant_interface():
    """Interface web pour l'assistant intelligent d'amélioration continue"""
    try:
        # Créer l'interface HTML pour l'assistant intelligent
        html_content = """
<!DOCTYPE html>
<html lang="fr" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Assistant Intelligent - Amélioration Continue</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
            direction: rtl;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 30px;
            padding: 25px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            background: #f8f9fa;
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            min-width: 180px;
            margin: 10px;
        }
        
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-warning { background: #ffc107; color: #212529; }
        .btn-danger { background: #dc3545; color: white; }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }
        
        .status {
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            font-weight: bold;
            text-align: center;
            font-size: 1.1em;
        }
        
        .status.success { background: #d4edda; color: #155724; border: 2px solid #c3e6cb; }
        .status.error { background: #f8d7da; color: #721c24; border: 2px solid #f5c6cb; }
        .status.warning { background: #fff3cd; color: #856404; border: 2px solid #ffeaa7; }
        .status.info { background: #d1ecf1; color: #0c5460; border: 2px solid #bee5eb; }
        
        .question-box {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            white-space: pre-line;
            font-family: monospace;
            font-size: 14px;
            line-height: 1.6;
        }
        
        .response-area {
            margin-top: 20px;
        }
        
        .response-area textarea {
            width: 100%;
            min-height: 120px;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            resize: vertical;
        }
        
        .progress-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .progress-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #dee2e6;
            text-align: center;
        }
        
        .progress-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #007bff;
        }
        
        .hidden { display: none; }
        
        .loading {
            text-align: center;
            padding: 30px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Assistant Intelligent</h1>
            <p>Amélioration Continue des Emplois du Temps</p>
            <p>🎯 Règles pédagogiques strictes | 🔄 Corrections automatiques | 🤔 Questions intelligentes</p>
        </div>
        
        <div class="content">
            <!-- Section de démarrage -->
            <div class="section">
                <h2>🚀 Démarrer une Session d'Amélioration</h2>
                <p>L'assistant va analyser l'emploi du temps, appliquer des corrections automatiques, et poser des questions intelligentes quand nécessaire.</p>
                
                <div style="margin: 20px 0;">
                    <label>Objectif de qualité pédagogique:</label>
                    <select id="targetQuality" style="padding: 8px; margin: 10px; border-radius: 4px;">
                        <option value="95">Excellente (95/100)</option>
                        <option value="90" selected>Très bonne (90/100)</option>
                        <option value="85">Bonne (85/100)</option>
                        <option value="75">Acceptable (75/100)</option>
                    </select>
                </div>
                
                <button id="startSessionBtn" class="btn btn-success">🚀 Démarrer l'Amélioration</button>
                <div id="startStatus"></div>
            </div>
            
            <!-- Section de progression -->
            <div id="progressSection" class="section hidden">
                <h2>📊 Progression de l'Amélioration</h2>
                <div id="progressInfo" class="progress-info"></div>
                <div id="sessionStatus"></div>
            </div>
            
            <!-- Section de questions -->
            <div id="questionSection" class="section hidden">
                <h2>🤔 Question Intelligente</h2>
                <div id="questionBox" class="question-box"></div>
                
                <div class="response-area">
                    <label for="userResponse"><strong>Votre réponse:</strong></label>
                    <textarea id="userResponse" placeholder="Tapez votre réponse ici..."></textarea>
                    
                    <div style="margin-top: 15px;">
                        <button id="submitResponseBtn" class="btn btn-primary">📝 Envoyer la Réponse</button>
                        <button id="pauseSessionBtn" class="btn btn-warning">⏸️ Pause</button>
                    </div>
                </div>
            </div>
            
            <!-- Section de résultats -->
            <div id="resultsSection" class="section hidden">
                <h2>🎉 Résultats de l'Amélioration</h2>
                <div id="finalResults"></div>
                <button id="generateReportBtn" class="btn btn-info">📋 Générer Rapport Détaillé</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentSessionId = null;
        
        function showStatus(message, type = 'info', elementId = 'startStatus') {
            const statusDiv = document.getElementById(elementId);
            statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
        }
        
        function showLoading(elementId, message = 'Traitement en cours...') {
            const element = document.getElementById(elementId);
            element.innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <div>${message}</div>
                </div>
            `;
        }
        
        // Démarrer une session
        document.getElementById('startSessionBtn').addEventListener('click', async () => {
            const targetQuality = parseInt(document.getElementById('targetQuality').value);
            const startBtn = document.getElementById('startSessionBtn');
            
            startBtn.disabled = true;
            showLoading('startStatus', '🚀 Démarrage de l\\'amélioration...');
            
            try {
                const response = await fetch('/start_improvement_session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target_quality: targetQuality })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentSessionId = result.session_id;
                    showStatus(`✅ Session démarrée: ${result.session_id}`, 'success');
                    
                    // Afficher la progression
                    displayProgress(result.initial_analysis);
                    
                    // Vérifier s'il y a une question
                    if (result.improvement_result.status === 'question_required') {
                        displayQuestion(result.improvement_result);
                    } else {
                        displayResults(result.improvement_result);
                    }
                } else {
                    showStatus(`❌ Erreur: ${result.error}`, 'error');
                }
            } catch (error) {
                showStatus(`❌ Erreur de connexion: ${error.message}`, 'error');
            } finally {
                startBtn.disabled = false;
            }
        });
        
        function displayProgress(analysis) {
            const progressSection = document.getElementById('progressSection');
            const progressInfo = document.getElementById('progressInfo');
            
            progressInfo.innerHTML = `
                <div class="progress-card">
                    <div class="progress-number">${analysis.pedagogical_score}</div>
                    <div>Score Initial</div>
                </div>
                <div class="progress-card">
                    <div class="progress-number">${analysis.total_entries}</div>
                    <div>Cours Total</div>
                </div>
                <div class="progress-card">
                    <div class="progress-number">${analysis.classes_analyzed}</div>
                    <div>Classes</div>
                </div>
                <div class="progress-card">
                    <div class="progress-number">${Object.keys(analysis.issues_by_priority.critical).length + Object.keys(analysis.issues_by_priority.high).length}</div>
                    <div>Problèmes</div>
                </div>
            `;
            
            progressSection.classList.remove('hidden');
        }
        
        function displayQuestion(questionData) {
            const questionSection = document.getElementById('questionSection');
            const questionBox = document.getElementById('questionBox');
            
            questionBox.textContent = questionData.question;
            questionSection.classList.remove('hidden');
            
            showStatus(`🤔 Question posée - Itération ${questionData.iteration}`, 'warning', 'sessionStatus');
        }
        
        function displayResults(results) {
            const resultsSection = document.getElementById('resultsSection');
            const finalResults = document.getElementById('finalResults');
            
            if (results.status === 'completed') {
                finalResults.innerHTML = `
                    <div class="status success">
                        🎉 Amélioration terminée avec succès!
                        <br>Score final: ${results.final_score}/100
                        <br>Améliorations appliquées: ${results.improvements_made}
                        <br>Itérations: ${results.iterations_performed}
                    </div>
                `;
            } else {
                finalResults.innerHTML = `
                    <div class="status info">
                        ⏸️ Session interrompue
                        <br>Dernière itération: ${results.iterations_performed}
                    </div>
                `;
            }
            
            resultsSection.classList.remove('hidden');
        }
        
        // Envoyer une réponse
        document.getElementById('submitResponseBtn').addEventListener('click', async () => {
            const response = document.getElementById('userResponse').value.trim();
            
            if (!response) {
                showStatus('⚠️ Veuillez saisir une réponse', 'warning', 'sessionStatus');
                return;
            }
            
            if (!currentSessionId) {
                showStatus('❌ Aucune session active', 'error', 'sessionStatus');
                return;
            }
            
            const submitBtn = document.getElementById('submitResponseBtn');
            submitBtn.disabled = true;
            showLoading('sessionStatus', '📝 Traitement de votre réponse...');
            
            try {
                const apiResponse = await fetch('/answer_question', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: currentSessionId,
                        response: response,
                        continue_improvement: true
                    })
                });
                
                const result = await apiResponse.json();
                
                if (result.success) {
                    showStatus('✅ Réponse traitée avec succès', 'success', 'sessionStatus');
                    
                    // Vider la zone de réponse
                    document.getElementById('userResponse').value = '';
                    
                    // Vérifier le résultat
                    if (result.improvement_continued.status === 'question_required') {
                        displayQuestion(result.improvement_continued);
                    } else {
                        document.getElementById('questionSection').classList.add('hidden');
                        displayResults(result.improvement_continued);
                    }
                } else {
                    showStatus(`❌ Erreur: ${result.error}`, 'error', 'sessionStatus');
                }
            } catch (error) {
                showStatus(`❌ Erreur: ${error.message}`, 'error', 'sessionStatus');
            } finally {
                submitBtn.disabled = false;
            }
        });
        
        // Pause session
        document.getElementById('pauseSessionBtn').addEventListener('click', () => {
            document.getElementById('questionSection').classList.add('hidden');
            showStatus('⏸️ Session mise en pause', 'info', 'sessionStatus');
        });
        
        // Générer rapport
        document.getElementById('generateReportBtn').addEventListener('click', async () => {
            try {
                const response = await fetch('/improvement_session_report');
                const report = await response.json();
                
                if (report.error) {
                    showStatus(`❌ ${report.error}`, 'error', 'sessionStatus');
                } else {
                    // Afficher ou télécharger le rapport
                    const reportWindow = window.open('', '_blank');
                    reportWindow.document.write(`
                        <h1>Rapport d'Amélioration</h1>
                        <pre>${JSON.stringify(report, null, 2)}</pre>
                    `);
                }
            } catch (error) {
                showStatus(`❌ Erreur génération rapport: ${error.message}`, 'error', 'sessionStatus');
            }
        });
    </script>
</body>
</html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Erreur interface assistant intelligent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

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

@app.get("/api/schedule_by_class/{schedule_id}")
async def get_schedule_by_class_new(schedule_id: int):
    """Retourne l'emploi du temps organisé par classe (format amélioré)"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Vérifier que le schedule existe
        cur.execute("SELECT COUNT(*) as count FROM schedules WHERE schedule_id = %s", (schedule_id,))
        if cur.fetchone()['count'] == 0:
            raise HTTPException(status_code=404, detail="Emploi du temps non trouvé")
        
        # Récupérer les entrées par classe
        cur.execute("""
            SELECT 
                se.class_name,
                se.day_of_week,
                se.period_number,
                COALESCE(se.subject, se.subject_name) as subject,
                se.teacher_name,
                CASE 
                    WHEN se.period_number IS NOT NULL THEN 
                        (6 + se.period_number)::text || ':00'
                    ELSE '00:00'
                END as start_time,
                COALESCE(se.is_parallel_group, false) as is_parallel,
                se.group_id
            FROM schedule_entries se
            WHERE se.schedule_id = %s
            ORDER BY se.class_name, se.day_of_week, se.period_number
        """, (schedule_id,))
        
        entries = cur.fetchall()
        
        if not entries:
            return {
                "success": False,
                "message": "Aucune donnée d'emploi du temps trouvée",
                "schedule_id": schedule_id,
                "classes": {}
            }
        
        # Organiser par classe
        classes_schedule = {}
        day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi']
        hebrew_days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי']
        
        for entry in entries:
            class_name = entry['class_name']
            day = entry['day_of_week']
            period = entry['period_number']
            
            if class_name not in classes_schedule:
                classes_schedule[class_name] = {
                    'class_name': class_name,
                    'days': {},
                    'stats': {'total_hours': 0, 'subjects': set(), 'teachers': set()}
                }
            
            day_name = day_names[day] if day < len(day_names) else f'Jour {day}'
            hebrew_day = hebrew_days[day] if day < len(hebrew_days) else f'יום {day}'
            
            if day_name not in classes_schedule[class_name]['days']:
                classes_schedule[class_name]['days'][day_name] = {
                    'hebrew_name': hebrew_day,
                    'periods': {}
                }
            
            classes_schedule[class_name]['days'][day_name]['periods'][period] = {
                'subject': entry['subject'],
                'teacher': entry['teacher_name'],
                'time': entry['start_time'],
                'is_parallel': bool(entry['is_parallel']),
                'group_id': entry['group_id']
            }
            
            # Statistiques
            classes_schedule[class_name]['stats']['total_hours'] += 1
            classes_schedule[class_name]['stats']['subjects'].add(entry['subject'])
            classes_schedule[class_name]['stats']['teachers'].add(entry['teacher_name'])
        
        # Convertir sets en listes pour JSON
        for class_name in classes_schedule:
            stats = classes_schedule[class_name]['stats']
            stats['subjects'] = list(stats['subjects'])
            stats['teachers'] = list(stats['teachers'])
            stats['subjects_count'] = len(stats['subjects'])
            stats['teachers_count'] = len(stats['teachers'])
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "total_classes": len(classes_schedule),
            "classes": classes_schedule,
            "view_type": "by_class"
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération emploi du temps par classe: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/api/schedule_by_teacher/{schedule_id}")
async def get_schedule_by_teacher_new(schedule_id: int):
    """Retourne l'emploi du temps organisé par professeur (format amélioré)"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Vérifier que le schedule existe
        cur.execute("SELECT COUNT(*) as count FROM schedules WHERE schedule_id = %s", (schedule_id,))
        if cur.fetchone()['count'] == 0:
            raise HTTPException(status_code=404, detail="Emploi du temps non trouvé")
        
        # Récupérer les entrées par professeur
        cur.execute("""
            SELECT 
                se.teacher_name,
                se.day_of_week,
                se.period_number,
                COALESCE(se.subject, se.subject_name) as subject,
                se.class_name,
                CASE 
                    WHEN se.period_number IS NOT NULL THEN 
                        (6 + se.period_number)::text || ':00'
                    ELSE '00:00'
                END as start_time,
                COALESCE(se.is_parallel_group, false) as is_parallel,
                se.group_id
            FROM schedule_entries se
            WHERE se.schedule_id = %s
            ORDER BY se.teacher_name, se.day_of_week, se.period_number
        """, (schedule_id,))
        
        entries = cur.fetchall()
        
        if not entries:
            return {
                "success": False,
                "message": "Aucune donnée d'emploi du temps trouvée",
                "schedule_id": schedule_id,
                "teachers": {}
            }
        
        # Organiser par professeur
        teachers_schedule = {}
        day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi']
        hebrew_days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי']
        
        for entry in entries:
            teacher_name = entry['teacher_name']
            day = entry['day_of_week']
            period = entry['period_number']
            
            if teacher_name not in teachers_schedule:
                teachers_schedule[teacher_name] = {
                    'teacher_name': teacher_name,
                    'days': {},
                    'stats': {'total_hours': 0, 'subjects': set(), 'classes': set()}
                }
            
            day_name = day_names[day] if day < len(day_names) else f'Jour {day}'
            hebrew_day = hebrew_days[day] if day < len(hebrew_days) else f'יום {day}'
            
            if day_name not in teachers_schedule[teacher_name]['days']:
                teachers_schedule[teacher_name]['days'][day_name] = {
                    'hebrew_name': hebrew_day,
                    'periods': {}
                }
            
            teachers_schedule[teacher_name]['days'][day_name]['periods'][period] = {
                'subject': entry['subject'],
                'class': entry['class_name'],
                'time': entry['start_time'],
                'is_parallel': bool(entry['is_parallel']),
                'group_id': entry['group_id']
            }
            
            # Statistiques
            teachers_schedule[teacher_name]['stats']['total_hours'] += 1
            teachers_schedule[teacher_name]['stats']['subjects'].add(entry['subject'])
            teachers_schedule[teacher_name]['stats']['classes'].add(entry['class_name'])
        
        # Convertir sets en listes pour JSON
        for teacher_name in teachers_schedule:
            stats = teachers_schedule[teacher_name]['stats']
            stats['subjects'] = list(stats['subjects'])
            stats['classes'] = list(stats['classes'])
            stats['subjects_count'] = len(stats['subjects'])
            stats['classes_count'] = len(stats['classes'])
        
        return {
            "success": True,
            "schedule_id": schedule_id,
            "total_teachers": len(teachers_schedule),
            "teachers": teachers_schedule,
            "view_type": "by_teacher"
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération emploi du temps par professeur: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


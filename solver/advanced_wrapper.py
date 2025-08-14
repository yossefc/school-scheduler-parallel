"""
advanced_wrapper.py - Wrapper pour intégrer les modules d'optimisation avancés
Ce module expose les fonctionnalités avancées via l'API FastAPI
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration du logger
logger = logging.getLogger(__name__)

# Tentative d'import des modules avancés
try:
    from advanced_main import AdvancedSchedulingSystem
    from smart_scheduler import SmartScheduler
    from conflict_resolver import ConflictResolver
    from pedagogical_solver import solve_with_pedagogical_logic
    MODULES_AVAILABLE = True
    logger.info("✅ Modules avancés chargés avec succès")
except ImportError as e:
    MODULES_AVAILABLE = False
    logger.warning(f"⚠️ Modules avancés non disponibles: {e}")
    # Fallback : au moins le solver pédagogique
    try:
        from pedagogical_solver import solve_with_pedagogical_logic
        PEDAGOGICAL_AVAILABLE = True
        logger.info("✅ Solver pédagogique disponible")
    except ImportError:
        PEDAGOGICAL_AVAILABLE = False

# Création du router pour l'API
router = APIRouter(prefix="/api/advanced", tags=["advanced"])

# Configuration DB
db_config = {
    "host": "postgres",
    "database": "school_scheduler",
    "user": "admin", 
    "password": "school123"
}

# Instance globale du système avancé
advanced_system = None

def get_db_connection():
    """Obtenir une connexion à la base de données"""
    return psycopg2.connect(**db_config)

@router.post("/optimize")
async def optimize_schedule(request: Dict[str, Any] = {}):
    """
    Lance l'optimisation avancée avec logique pédagogique
    Utilise le solveur pédagogique pour créer des emplois du temps logiques
    """
    try:
        time_limit = request.get("time_limit", 600)
        
        # Essayer d'abord le solver pédagogique (toujours disponible)
        logger.info("Démarrage de l'optimisation pédagogique...")
        result = solve_with_pedagogical_logic(db_config, time_limit)
        
        if result.get("success"):
            pedagogical_score = result.get("stats", {}).get("pedagogical_score", 0)
            blocks_count = result.get("stats", {}).get("blocks_2h", 0)
            
            return {
                "status": "success",
                "message": f"Emploi du temps pédagogique généré avec {blocks_count} blocs de 2h",
                "quality_score": pedagogical_score,
                "pedagogical_features": {
                    "blocks_2h": blocks_count,
                    "coverage": result.get("stats", {}).get("coverage", "N/A"),
                    "grouped_courses": True,
                    "morning_priority": True
                },
                "result": result
            }
        
        # Si échec du solver pédagogique ET modules avancés disponibles
        if MODULES_AVAILABLE:
            logger.info("Fallback vers système avancé complet...")
            global advanced_system
            
            if not advanced_system:
                advanced_system = AdvancedSchedulingSystem(db_config)
                logger.info("Système avancé initialisé")
            
            advanced_result = advanced_system.generate_optimal_schedule()
            quality_score = advanced_result.get("quality_analysis", {}).get("global_score", 0)
            issues = advanced_result.get("quality_analysis", {}).get("issues", [])
            
            return {
                "status": "success",
                "message": f"Optimisation avancée terminée avec score {quality_score}/100",
                "quality_score": quality_score,
                "issues_count": len(issues),
                "result": advanced_result
            }
        
        # Aucune solution n'a marché
        return {
            "status": "error",
            "message": result.get("message", "Échec de la génération pédagogique")
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'optimisation: {e}")
        return {
            "status": "error", 
            "message": str(e)
        }

@router.post("/smart-distribute")
async def smart_distribution(data: Dict[str, Any]):
    """
    Utilise le SmartScheduler pour distribuer intelligemment les cours
    Optimise la répartition avec priorité aux blocs de 2h et respect des contraintes israéliennes
    """
    if not MODULES_AVAILABLE:
        return {
            "status": "error",
            "message": "Module SmartScheduler non disponible"
        }
        
    try:
        scheduler = SmartScheduler()
        
        # Extraire les paramètres
        class_name = data.get("class_name", "")
        subject = data.get("subject", "")
        hours = data.get("hours", 0)
        
        if not class_name or not subject or hours <= 0:
            raise ValueError("Paramètres manquants: class_name, subject et hours sont requis")
        
        # Distribuer les cours
        logger.info(f"Distribution de {hours}h de {subject} pour {class_name}")
        distribution = scheduler.distribute_courses(class_name, subject, hours)
        
        return {
            "status": "success",
            "message": f"Distribution optimale calculée pour {subject}",
            "distribution": {
                "subject": distribution.subject,
                "total_hours": distribution.total_hours,
                "blocks": distribution.blocks
            }
        }
    except Exception as e:
        logger.error(f"Erreur lors de la distribution: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.get("/analyze-conflicts")
async def analyze_conflicts():
    """
    Analyse les conflits dans l'emploi du temps actuel
    Identifie les problèmes et propose des solutions
    """
    if not MODULES_AVAILABLE:
        return {
            "status": "error",
            "message": "Module ConflictResolver non disponible"
        }
        
    try:
        resolver = ConflictResolver()
        
        # Charger le dernier emploi du temps depuis la DB
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer le dernier schedule_id
        cur.execute("SELECT MAX(schedule_id) as latest_id FROM schedules")
        result = cur.fetchone()
        
        if not result or not result['latest_id']:
            return {
                "status": "warning",
                "message": "Aucun emploi du temps trouvé dans la base de données"
            }
        
        schedule_id = result['latest_id']
        
        # Charger les entrées du schedule
        cur.execute("""
            SELECT 
                se.*,
                t.slot_id,
                t.day_of_week,
                t.period_number,
                t.start_time,
                t.end_time
            FROM schedule_entries se
            JOIN time_slots t ON se.time_slot_id = t.slot_id
            WHERE se.schedule_id = %s
            ORDER BY t.day_of_week, t.period_number
        """, (schedule_id,))
        
        schedule_entries = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convertir en format attendu par le resolver
        schedule = {
            "schedule_id": schedule_id,
            "entries": schedule_entries,
            "total_entries": len(schedule_entries)
        }
        
        # Analyser la qualité
        logger.info(f"Analyse de l'emploi du temps #{schedule_id} avec {len(schedule_entries)} entrées")
        analysis = resolver.analyze_schedule_quality(schedule)
        
        return {
            "status": "success",
            "schedule_id": schedule_id,
            "entries_count": len(schedule_entries),
            "analysis": analysis,
            "global_score": analysis.get("global_score", 0),
            "issues": analysis.get("issues", [])
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des conflits: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.get("/status")
async def check_advanced_status():
    """Vérifier l'état des modules avancés"""
    modules = {
        "advanced_main": False,
        "smart_scheduler": False,
        "conflict_resolver": False,
        "optimizer_advanced": False
    }
    
    try:
        import advanced_main
        modules["advanced_main"] = True
    except:
        pass
        
    try:
        import smart_scheduler
        modules["smart_scheduler"] = True
    except:
        pass
        
    try:
        import conflict_resolver
        modules["conflict_resolver"] = True
    except:
        pass
        
    try:
        import optimizer_advanced
        modules["optimizer_advanced"] = True
    except:
        pass
    
    return {
        "modules_available": MODULES_AVAILABLE,
        "modules_detail": modules,
        "ready": all(modules.values())
    }

@router.post("/apply-smart-distribution")
async def apply_smart_distribution_to_all():
    """
    Applique la distribution intelligente à tous les cours de la base
    Utilise SmartScheduler pour optimiser la répartition de tous les cours
    """
    if not MODULES_AVAILABLE:
        return {
            "status": "error",
            "message": "Modules avancés non disponibles"
        }
    
    try:
        scheduler = SmartScheduler()
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer tous les cours depuis solver_input
        cur.execute("""
            SELECT DISTINCT 
                class_list,
                subject as subject,
                SUM(hours) as total_hours
            FROM solver_input
            WHERE hours > 0
            GROUP BY class_list, subject
        """)
        
        courses = cur.fetchall()
        cur.close()
        conn.close()
        
        distributions = []
        for course in courses:
            if course['class_list'] and course['subject']:
                # Pour chaque classe dans la liste
                classes = course['class_list'].split(',')
                for class_name in classes:
                    dist = scheduler.distribute_courses(
                        class_name.strip(),
                        course['subject'],
                        int(course['total_hours'])
                    )
                    distributions.append({
                        "class": class_name.strip(),
                        "subject": course['subject'],
                        "hours": course['total_hours'],
                        "blocks": dist.blocks
                    })
        
        return {
            "status": "success",
            "message": f"Distribution appliquée à {len(distributions)} cours",
            "distributions": distributions
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'application de la distribution: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
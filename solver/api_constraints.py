# api_constraints.py - Endpoints pour gérer les contraintes
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
import logging
import httpx
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# Modèles Pydantic adaptés pour l'interface
class ConstraintCreate(BaseModel):
    type: str = Field(alias="constraint_type", default="time_preference")
    entity: str = Field(alias="entity_name", default="Global")
    data: Dict[str, Any] = Field(alias="constraint_data", default_factory=dict)
    priority: int = 2
    is_active: bool = True
    original_text: Optional[str] = None
    ai_confidence: Optional[float] = None
    
    class Config:
        populate_by_name = True  # Accepte les deux formats

class ConstraintToggle(BaseModel):
    is_active: bool

# Router pour les contraintes - SANS préfixe car on va gérer les deux routes
router = APIRouter(tags=["constraints"])

# Configuration DB - Docker
db_config = {
    "host": "postgres",  # Nom du service Docker
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123"
}

# Alternative si utilisation d'une URL de connexion
import os
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://admin:school123@postgres:5432/school_scheduler')

def format_constraint_for_frontend(constraint):
    """Formate une contrainte pour l'interface frontend"""
    import json
    
    # IMPORTANT : Parser le JSON si c'est une string
    constraint_data = constraint.get('constraint_data', {})
    if isinstance(constraint_data, str):
        try:
            # Parser le JSON string
            constraint_data = json.loads(constraint_data)
        except:
            constraint_data = {"raw": constraint_data}
    
    # Extraire entity_name depuis les données
    entity_name = constraint.get('entity_name')
    if not entity_name or entity_name == 'Global':
        if isinstance(constraint_data, dict):
            entity_name = constraint_data.get('entity_name', 
                         constraint_data.get('description', 'Global'))
    
    return {
        "constraint_id": constraint.get('constraint_id'),
        "type": constraint.get('constraint_type', 'custom'),
        "entity": entity_name,  # Utiliser le nom extrait
        "priority": constraint.get('priority', 2),
        "data": constraint_data,  # Données parsées, pas string
        "is_active": constraint.get('is_active', True),
        "created_at": str(constraint.get('created_at', '')) if constraint.get('created_at') else None,
        "constraint_type": constraint.get('constraint_type'),
        "entity_name": entity_name,
        "constraint_data": constraint_data
    }

@router.get("/constraints")
@router.get("/api/constraints")
async def list_constraints():
    """Liste toutes les contraintes"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier que la table existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'constraints'
            );
        """)
        
        if not cur.fetchone()['exists']:
            logger.warning("Table 'constraints' n'existe pas, création...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS constraints (
                    constraint_id SERIAL PRIMARY KEY,
                    constraint_type VARCHAR(50) NOT NULL,
                    priority INTEGER DEFAULT 2,
                    entity_type VARCHAR(50) DEFAULT 'global',
                    entity_name VARCHAR(100) DEFAULT 'Global',
                    constraint_data JSONB DEFAULT '{}',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            return []
        
        # Récupérer les contraintes
        cur.execute("""
            SELECT 
                constraint_id,
                constraint_type,
                priority,
                entity_type,
                entity_name,
                constraint_data,
                is_active,
                created_at,
                updated_at
            FROM constraints 
            ORDER BY priority ASC, constraint_id DESC
        """)
        
        constraints = cur.fetchall()
        
        # Formater pour l'interface
        formatted_constraints = [format_constraint_for_frontend(c) for c in constraints]
        
        logger.info(f"Retour de {len(formatted_constraints)} contraintes")
        return formatted_constraints
        
    except Exception as e:
        logger.error(f"Erreur list_constraints: {str(e)}")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@router.post("/constraints")
@router.post("/api/constraints")
async def create_constraint(constraint: ConstraintCreate = Body(...)):
    """Crée une nouvelle contrainte"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # S'assurer que la table existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS constraints (
                constraint_id SERIAL PRIMARY KEY,
                constraint_type VARCHAR(50) NOT NULL,
                priority INTEGER DEFAULT 2,
                entity_type VARCHAR(50) DEFAULT 'global',
                entity_name VARCHAR(100) DEFAULT 'Global',
                constraint_data JSONB DEFAULT '{}',
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Déterminer le type d'entité
        constraint_type = constraint.type if hasattr(constraint, 'type') else constraint.constraint_type
        entity_name = constraint.entity if hasattr(constraint, 'entity') else constraint.entity_name
        constraint_data = constraint.data if hasattr(constraint, 'data') else constraint.constraint_data
        
        entity_type = "teacher"  # Par défaut
        if constraint_type in ["school_hours", "friday_early_end", "morning_prayer", "lunch_break"]:
            entity_type = "global"
        elif "class" in entity_name.lower():
            entity_type = "class"
        
        # Ajouter le texte original aux données si présent
        if hasattr(constraint, 'original_text') and constraint.original_text:
            constraint_data['original_text'] = constraint.original_text
        
        cur.execute("""
            INSERT INTO constraints 
            (constraint_type, priority, entity_type, entity_name, constraint_data, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            constraint_type,
            constraint.priority,
            entity_type,
            entity_name,
            Json(constraint_data),
            constraint.is_active
        ))
        
        new_constraint = cur.fetchone()
        conn.commit()
        
        logger.info(f"Contrainte créée: ID={new_constraint['constraint_id']}")
        
        # Formater la réponse
        formatted = format_constraint_for_frontend(new_constraint)
        formatted['id'] = new_constraint['constraint_id']  # Ajouter l'ID pour la réponse
        
        # NOUVEAU: Déclencher la régénération automatique pour les contraintes critiques
        should_regenerate = await _should_trigger_regeneration(constraint_type, constraint.priority, constraint_data)
        if should_regenerate:
            logger.info(f"Déclenchement de la régénération automatique pour contrainte critique: {constraint_type}")
            regeneration_result = await _trigger_schedule_regeneration()
            formatted['auto_regenerated'] = regeneration_result
            formatted['message'] = "Contrainte ajoutée et emploi du temps automatiquement régénéré"
        else:
            formatted['auto_regenerated'] = False
            formatted['message'] = "Contrainte ajoutée (régénération manuelle requise)"
        
        return formatted
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erreur create_constraint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@router.post("/constraints/{constraint_id}/toggle")
@router.put("/api/constraints/{constraint_id}/toggle")
@router.post("/api/constraints/{constraint_id}/toggle")
async def toggle_constraint(constraint_id: int, toggle: ConstraintToggle = Body(...)):
    """Active/désactive une contrainte"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE constraints 
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE constraint_id = %s
            RETURNING constraint_id
        """, (toggle.is_active, constraint_id))
        
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Contrainte non trouvée")
        
        conn.commit()
        logger.info(f"Contrainte {constraint_id} mise à jour: is_active={toggle.is_active}")
        
        # NOUVEAU: Déclencher la régénération si on active une contrainte critique
        if toggle.is_active:
            # Récupérer les détails de la contrainte pour vérifier si elle est critique
            cur.execute("SELECT constraint_type, priority, constraint_data FROM constraints WHERE constraint_id = %s", (constraint_id,))
            constraint_info = cur.fetchone()
            if constraint_info:
                constraint_type, priority, constraint_data_raw = constraint_info
                constraint_data = constraint_data_raw if isinstance(constraint_data_raw, dict) else json.loads(constraint_data_raw) if constraint_data_raw else {}
                
                should_regenerate = await _should_trigger_regeneration(constraint_type, priority, constraint_data)
                if should_regenerate:
                    logger.info(f"Déclenchement de la régénération automatique pour contrainte critique activée: {constraint_id}")
                    regeneration_result = await _trigger_schedule_regeneration()
                    return {
                        "success": True, 
                        "is_active": toggle.is_active,
                        "auto_regenerated": regeneration_result,
                        "message": "Contrainte activée et emploi du temps automatiquement régénéré"
                    }
        
        return {"success": True, "is_active": toggle.is_active}
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erreur toggle_constraint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@router.delete("/constraints/{constraint_id}")
@router.delete("/api/constraints/{constraint_id}")
async def delete_constraint(constraint_id: int):
    """Supprime une contrainte"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Vérifier que ce n'est pas une contrainte système
        cur.execute("""
            SELECT priority FROM constraints 
            WHERE constraint_id = %s
        """, (constraint_id,))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Contrainte non trouvée")
        
        if result[0] == 0:  # Priorité critique
            raise HTTPException(status_code=403, detail="Impossible de supprimer une contrainte critique")
        
        # Supprimer
        cur.execute("""
            DELETE FROM constraints 
            WHERE constraint_id = %s
        """, (constraint_id,))
        
        conn.commit()
        logger.info(f"Contrainte {constraint_id} supprimée")
        
        return {"success": True, "deleted_id": constraint_id}
        
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erreur delete_constraint: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@router.get("/constraints/validate")
@router.get("/api/constraints/validate")
async def validate_constraints():
    """Valide la cohérence des contraintes"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer toutes les contraintes actives
        cur.execute("""
            SELECT * FROM constraints 
            WHERE is_active = true
        """)
        constraints = cur.fetchall()
        
        # Récupérer les enseignants
        try:
            cur.execute("SELECT teacher_name FROM teachers")
            teachers = [t['teacher_name'] for t in cur.fetchall()]
        except:
            teachers = []
        
        # Validation
        conflicts = []
        warnings = []
        
        # Vérifier les contraintes de disponibilité par professeur
        teacher_constraints = {}
        for c in constraints:
            if c['constraint_type'] == 'teacher_availability' and c.get('entity_name'):
                if c['entity_name'] not in teacher_constraints:
                    teacher_constraints[c['entity_name']] = []
                teacher_constraints[c['entity_name']].append(c)
        
        # Détecter les conflits
        for teacher, cs in teacher_constraints.items():
            if teachers and teacher not in teachers:
                warnings.append(f"Professeur '{teacher}' non trouvé dans la base de données")
            
            # Compter les jours non disponibles
            unavailable_days = set()
            for c in cs:
                data = c['constraint_data']
                if isinstance(data, str):
                    data = json.loads(data)
                if 'unavailable_days' in data:
                    unavailable_days.update(data['unavailable_days'])
            
            if len(unavailable_days) >= 5:
                conflicts.append(f"{teacher} n'a presque aucun jour disponible ({len(unavailable_days)}/6 jours bloqués)")
        
        return {
            "is_valid": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings,
            "total_constraints": len(constraints),
            "constraints_by_type": _count_by_type(constraints)
        }
        
    except Exception as e:
        logger.error(f"Erreur validate_constraints: {str(e)}")
        return {
            "is_valid": True,
            "conflicts": [],
            "warnings": [],
            "total_constraints": 0,
            "constraints_by_type": {}
        }
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@router.post("/api/constraints/seed")
async def seed_constraints():
    """Ajoute des contraintes de test"""
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Contraintes de test
        test_constraints = [
            {
                "type": "friday_early_end",
                "entity": "Global",
                "priority": 0,
                "data": {"end_time": "13:00", "applies_to": ["all"]}
            },
            {
                "type": "morning_prayer",
                "entity": "Global", 
                "priority": 0,
                "data": {"time_slot": "08:00-08:30", "mandatory_for": ["all"]}
            },
            {
                "type": "lunch_break",
                "entity": "Global",
                "priority": 1,
                "data": {"time_slot": "12:15-12:45", "mandatory_for": ["all"]}
            },
            {
                "type": "teacher_availability",
                "entity": "Cohen David",
                "priority": 2,
                "data": {"unavailable_days": [5], "reason": "Formation externe"}
            }
        ]
        
        inserted = 0
        for c in test_constraints:
            try:
                cur.execute("""
                    INSERT INTO constraints 
                    (constraint_type, entity_name, priority, constraint_data, is_active, entity_type)
                    VALUES (%s, %s, %s, %s, true, %s)
                """, (
                    c["type"], 
                    c["entity"], 
                    c["priority"], 
                    Json(c["data"]),
                    "global" if c["type"] in ["friday_early_end", "morning_prayer", "lunch_break"] else "teacher"
                ))
                inserted += 1
            except:
                pass  # Ignorer les doublons
        
        conn.commit()
        
        return {"success": True, "message": f"Ajout de {inserted} contraintes de test"}
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Erreur seed_constraints: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def _count_by_type(constraints):
    """Compte les contraintes par type"""
    counts = {}
    for c in constraints:
        ctype = c['constraint_type']
        counts[ctype] = counts.get(ctype, 0) + 1
    return counts

# ============================================
# FONCTIONS DE RÉGÉNÉRATION AUTOMATIQUE
# ============================================

async def _should_trigger_regeneration(constraint_type: str, priority: int, constraint_data: dict) -> bool:
    """Détermine si une contrainte doit déclencher la régénération automatique"""
    
    # Contraintes critiques qui nécessitent une régénération immédiate
    critical_types = [
        'teacher_availability',    # Disponibilité des professeurs
        'class_schedule',         # Horaires de classe
        'parallel_teaching',      # Enseignement parallèle
        'room_assignment',        # Affectation de salles
        'time_preference',        # Préférences horaires importantes
        'friday_short',           # Contraintes de vendredi écourté
        'morning_prayer',         # Contraintes de prière matinale
        'lunch_break',           # Pauses déjeuner
        'subject_timing'         # Horaires de matières spécifiques
    ]
    
    # Vérifier le type de contrainte
    if constraint_type in critical_types:
        logger.info(f"Contrainte critique détectée: {constraint_type}")
        return True
    
    # Vérifier la priorité (0 = critique, 1 = importante)
    if priority <= 1:
        logger.info(f"Contrainte haute priorité détectée: {priority}")
        return True
    
    # Vérifier certains mots-clés dans les données qui indiquent une contrainte critique
    if constraint_data and isinstance(constraint_data, dict):
        original_text = constraint_data.get('original_text', '').lower()
        critical_keywords = [
            'indisponible', 'pas disponible', 'trop de trous', 'trou', 'gap', 'conflit',
            'parallèle', 'simultané', 'même temps', 'overlap', 'collision',
            'urgent', 'obligatoire', 'critique', 'nécessaire', 'beaucoup de trous'
        ]
        
        # Mots-clés hébreux
        hebrew_critical = [
            'לא זמין', 'לא פנוי', 'חובה', 'דחוף', 'חשוב', 'נדרש'
        ]
        
        for keyword in critical_keywords + hebrew_critical:
            if keyword in original_text:
                logger.info(f"Mot-clé critique détecté dans le texte: {keyword}")
                return True
    
    logger.info(f"Contrainte non critique: {constraint_type}, priorité: {priority}")
    return False

async def _trigger_schedule_regeneration() -> dict:
    """Déclenche la régénération automatique de l'emploi du temps"""
    
    try:
        logger.info("Début de la régénération automatique de l'emploi du temps...")
        
        # Essayer d'abord le solver avancé/pédagogique
        regeneration_payload = {
            "time_limit": 300,  # 5 minutes max pour la régénération auto
            "advanced": True,
            "minimize_gaps": True,
            "friday_short": True
        }
        
        # Appeler l'endpoint de génération avancée en local
        async with httpx.AsyncClient() as client:
            try:
                # Essayer d'abord l'optimisation avancée
                response = await client.post(
                    "http://localhost:8000/api/advanced/optimize",
                    timeout=310.0  # Un peu plus que time_limit
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Régénération avancée réussie: score {result.get('quality_score', 0)}")
                    return {
                        "success": True,
                        "method": "advanced",
                        "quality_score": result.get('quality_score', 0),
                        "schedule_id": result.get('schedule_id'),
                        "message": "Emploi du temps régénéré avec optimisation avancée"
                    }
                else:
                    logger.warning(f"Optimisation avancée échouée: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Erreur optimisation avancée: {e}")
            
            # Fallback sur la génération standard
            try:
                response = await client.post(
                    "http://localhost:8000/generate_schedule",
                    json=regeneration_payload,
                    timeout=310.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        logger.info("Régénération standard réussie")
                        return {
                            "success": True,
                            "method": "standard",
                            "schedule_id": result.get('schedule_id'),
                            "total_entries": result.get('total_entries', 0),
                            "message": "Emploi du temps régénéré avec méthode standard"
                        }
                    else:
                        logger.error(f"Régénération standard échouée: {result}")
                        return {
                            "success": False,
                            "error": "Génération standard échouée",
                            "details": result
                        }
                else:
                    logger.error(f"Erreur HTTP régénération: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"Erreur HTTP: {response.status_code}"
                    }
                    
            except Exception as e:
                logger.error(f"Erreur lors de la régénération standard: {e}")
                return {
                    "success": False,
                    "error": f"Erreur technique: {str(e)}"
                }
                
    except Exception as e:
        logger.error(f"Erreur générale lors de la régénération: {e}")
        return {
            "success": False,
            "error": f"Erreur système: {str(e)}"
        }

# ============================================
# FONCTION D'INTÉGRATION
# ============================================

# Fonction pour intégrer dans main.py
def register_constraint_routes(app):
    """Ajoute les routes de contraintes à l'application FastAPI"""
    # Important: ne pas utiliser de préfixe car on gère les deux formats d'URL
    app.include_router(router)
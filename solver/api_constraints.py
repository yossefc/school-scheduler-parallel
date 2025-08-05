# api_constraints.py - Endpoints pour gérer les contraintes
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
import logging

logger = logging.getLogger(__name__)

# Modèles Pydantic
class ConstraintCreate(BaseModel):
    constraint_type: str
    entity_name: Optional[str] = ""
    constraint_data: Dict[str, Any]
    priority: int = 2

class ConstraintToggle(BaseModel):
    is_active: bool

# Router pour les contraintes
router = APIRouter(prefix="/constraints", tags=["constraints"])

# Configuration DB
db_config = {
    "host": "postgres",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123"
}

@router.get("/")
async def list_constraints():
    """Liste toutes les contraintes"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM constraints 
            ORDER BY priority ASC, constraint_id DESC
        """)
        constraints = cur.fetchall()
        
        # Parser les JSON strings si nécessaire
        for constraint in constraints:
            if isinstance(constraint['constraint_data'], str):
                try:
                    constraint['constraint_data'] = json.loads(constraint['constraint_data'])
                except:
                    pass
        
        return constraints
        
    finally:
        cur.close()
        conn.close()

@router.post("/")
async def create_constraint(constraint: ConstraintCreate):
    """Crée une nouvelle contrainte"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Déterminer le type d'entité
        entity_type = "teacher"  # Par défaut
        if constraint.constraint_type in ["school_hours", "friday_early_end", "morning_prayer"]:
            entity_type = "global"
        elif "class" in constraint.entity_name.lower():
            entity_type = "class"
        
        cur.execute("""
            INSERT INTO constraints 
            (constraint_type, priority, entity_type, entity_name, constraint_data, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            constraint.constraint_type,
            constraint.priority,
            entity_type,
            constraint.entity_name,
            Json(constraint.constraint_data),
            True
        ))
        
        new_constraint = cur.fetchone()
        conn.commit()
        
        logger.info(f"Created constraint: {new_constraint['constraint_id']}")
        
        # Parser le JSON pour la réponse
        if isinstance(new_constraint['constraint_data'], str):
            new_constraint['constraint_data'] = json.loads(new_constraint['constraint_data'])
        
        return new_constraint
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating constraint: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/{constraint_id}/toggle")
async def toggle_constraint(constraint_id: int, toggle: ConstraintToggle):
    """Active/désactive une contrainte"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE constraints 
            SET is_active = %s
            WHERE constraint_id = %s
            RETURNING constraint_id
        """, (toggle.is_active, constraint_id))
        
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Contrainte non trouvée")
        
        conn.commit()
        return {"success": True, "is_active": toggle.is_active}
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error toggling constraint: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/{constraint_id}")
async def delete_constraint(constraint_id: int):
    """Supprime une contrainte"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    try:
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
        return {"success": True, "deleted_id": constraint_id}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting constraint: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.get("/validate")
async def validate_constraints():
    """Valide la cohérence des contraintes"""
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Récupérer toutes les contraintes actives
        cur.execute("""
            SELECT * FROM constraints 
            WHERE is_active = true
        """)
        constraints = cur.fetchall()
        
        # Récupérer les enseignants
        cur.execute("SELECT teacher_name FROM teachers")
        teachers = [t['teacher_name'] for t in cur.fetchall()]
        
        # Validation
        conflicts = []
        warnings = []
        
        # Vérifier les contraintes de disponibilité par professeur
        teacher_constraints = {}
        for c in constraints:
            if c['constraint_type'] == 'teacher_availability' and c['entity_name']:
                if c['entity_name'] not in teacher_constraints:
                    teacher_constraints[c['entity_name']] = []
                teacher_constraints[c['entity_name']].append(c)
        
        # Détecter les conflits
        for teacher, cs in teacher_constraints.items():
            if teacher not in teachers:
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
        
    finally:
        cur.close()
        conn.close()

def _count_by_type(constraints):
    """Compte les contraintes par type"""
    counts = {}
    for c in constraints:
        ctype = c['constraint_type']
        counts[ctype] = counts.get(ctype, 0) + 1
    return counts

# Fonction pour intégrer dans main.py
def register_constraint_routes(app):
    """Ajoute les routes de contraintes à l'application FastAPI"""
    app.include_router(router)
    
# Ajout dans main.py:
# from api_constraints import register_constraint_routes
# register_constraint_routes(app)
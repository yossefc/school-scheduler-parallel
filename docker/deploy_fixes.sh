#!/bin/bash
# deploy_fixes.sh - Déploiement automatique des corrections

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-school_scheduler}"
DB_USER="${DB_USER:-admin}"
DB_PASS="${DB_PASS:-school123}"
DB_PORT="${DB_PORT:-5432}"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         DÉPLOIEMENT DES CORRECTIONS DU SOLVER            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Sauvegarder le solver actuel
echo -e "${YELLOW}1. Sauvegarde du solver actuel...${NC}"
if [ -f "solver/solver_engine.py" ]; then
    cp solver/solver_engine.py solver/solver_engine_backup_$(date +%Y%m%d_%H%M%S).py
    echo -e "${GREEN}✓ Sauvegarde créée${NC}"
else
    echo -e "${RED}✗ Fichier solver_engine.py non trouvé${NC}"
    exit 1
fi

# 2. Copier le nouveau solver
echo -e "${YELLOW}2. Installation du solver corrigé...${NC}"
# Ici, vous devez copier le contenu de solver_engine_fixed.py vers solver_engine.py
# Pour ce script, on assume que vous avez créé solver_engine_fixed.py
if [ -f "solver_engine_fixed.py" ]; then
    cp solver_engine_fixed.py solver/solver_engine.py
    echo -e "${GREEN}✓ Nouveau solver installé${NC}"
else
    echo -e "${YELLOW}⚠ Créez d'abord solver_engine_fixed.py avec le code fourni${NC}"
fi

# 3. Appliquer les corrections SQL
echo -e "${YELLOW}3. Application des corrections de données...${NC}"
PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
-- Début transaction
BEGIN;

-- Corriger les valeurs is_parallel NULL
UPDATE teacher_load
SET is_parallel = FALSE
WHERE is_parallel IS NULL
  AND (class_list IS NULL OR class_list NOT LIKE '%,%');

UPDATE teacher_load
SET is_parallel = TRUE
WHERE class_list LIKE '%,%'
  AND (is_parallel = FALSE OR is_parallel IS NULL);

-- Marquer les cours dans parallel_teaching_details
UPDATE teacher_load tl
SET is_parallel = TRUE
FROM parallel_teaching_details ptd
WHERE tl.teacher_name = ptd.teacher_name
  AND tl.subject = ptd.subject
  AND tl.grade = ptd.grade;

-- Ajouter la contrainte du vendredi si elle n'existe pas
INSERT INTO constraints (constraint_type, priority, entity_type, entity_name, constraint_data)
SELECT 
    'friday_early_end',
    1,
    'school',
    'global',
    '{"last_period": 6, "description": "Vendredi se termine à 13h"}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM constraints 
    WHERE constraint_type = 'friday_early_end'
);

COMMIT;

-- Afficher les statistiques
SELECT 
    'Statistiques après correction' as title,
    COUNT(*) FILTER (WHERE is_parallel = TRUE) as parallel_courses,
    COUNT(*) FILTER (WHERE is_parallel IS DISTINCT FROM TRUE) as individual_courses,
    COUNT(*) FILTER (WHERE is_parallel IS NULL) as null_values
FROM teacher_load;
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Corrections SQL appliquées${NC}"
else
    echo -e "${RED}✗ Erreur lors de l'application des corrections SQL${NC}"
    exit 1
fi

# 4. Vérifier la faisabilité
echo -e "${YELLOW}4. Vérification de la faisabilité...${NC}"
RESULT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
WITH needs AS (
    SELECT SUM(hours) as individual
    FROM teacher_load
    WHERE is_parallel IS DISTINCT FROM TRUE
), parallel AS (
    SELECT SUM(hours_per_teacher) as parallel
    FROM (
        SELECT DISTINCT ON (group_id) group_id, hours_per_teacher
        FROM parallel_teaching_details
    ) x
), available AS (
    SELECT COUNT(DISTINCT c.class_name) * COUNT(DISTINCT t.slot_id) as slots
    FROM classes c, time_slots t
    WHERE t.is_break = FALSE
)
SELECT 
    ROUND((COALESCE(n.individual, 0) + COALESCE(p.parallel, 0))::numeric / a.slots, 2)
FROM needs n, parallel p, available a;
")

echo -e "Ratio d'utilisation : ${BLUE}${RESULT}${NC}"

if (( $(echo "$RESULT > 1.0" | bc -l) )); then
    echo -e "${RED}⚠ ATTENTION : Plus d'heures requises que de créneaux disponibles !${NC}"
    echo -e "${YELLOW}Solutions possibles :${NC}"
    echo "  - Réduire les charges d'enseignement"
    echo "  - Augmenter le nombre de classes/salles"
    echo "  - Optimiser les groupes parallèles"
elif (( $(echo "$RESULT > 0.9" | bc -l) )); then
    echo -e "${YELLOW}⚠ Utilisation élevée (>90%). La génération peut être difficile.${NC}"
else
    echo -e "${GREEN}✓ Faisabilité OK (${RESULT})${NC}"
fi

# 5. Redémarrer le service
echo -e "${YELLOW}5. Redémarrage du service...${NC}"
if command -v docker-compose &> /dev/null; then
    docker-compose restart solver
    echo -e "${GREEN}✓ Service solver redémarré${NC}"
else
    echo -e "${YELLOW}⚠ Docker-compose non trouvé. Redémarrez manuellement le solver.${NC}"
fi

# 6. Test rapide
echo -e "${YELLOW}6. Test de l'API...${NC}"
sleep 5  # Attendre que le service démarre

# Test simple de l'API
if curl -s -f http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API accessible${NC}"
    
    # Afficher la version
    VERSION=$(curl -s http://localhost:8000/ | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    echo -e "Version de l'API : ${BLUE}${VERSION}${NC}"
else
    echo -e "${RED}✗ API non accessible${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ DÉPLOIEMENT TERMINÉ !${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Prochaines étapes :${NC}"
echo "1. Tester la génération : curl -X POST http://localhost:8000/generate_schedule -d '{\"time_limit\": 60}'"
echo "2. Vérifier les logs : docker logs school_solver"
echo "3. Si problème : restaurer avec solver_engine_backup_*.py"
echo ""
echo -e "${BLUE}Bonne chance ! 🚀${NC}"
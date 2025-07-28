#!/bin/bash
# post_install_check.sh - Vérification complète après installation des cours parallèles

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_HOST="localhost"
DB_NAME="school_scheduler"
DB_USER="admin"
DB_PASS="school123"
API_URL="http://localhost:8000"

echo -e "${YELLOW}================================================${NC}"
echo -e "${YELLOW} Vérification Post-Installation - Cours Parallèles${NC}"
echo -e "${YELLOW}================================================${NC}\n"

# Fonction pour afficher le résultat
check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        exit 1
    fi
}

# 1. Vérifier la connexion à la base de données
echo "1. Vérification de la base de données..."
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1
check_result $? "Connexion à PostgreSQL"

# 2. Vérifier les tables
echo -e "\n2. Vérification des tables..."
for table in "parallel_groups" "parallel_teaching_details"; do
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT COUNT(*) FROM $table" > /dev/null 2>&1
    check_result $? "Table $table existe"
done

# 3. Vérifier la colonne is_parallel
echo -e "\n3. Vérification des colonnes..."
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT is_parallel FROM teacher_load LIMIT 1" > /dev/null 2>&1
check_result $? "Colonne is_parallel dans teacher_load"

PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT group_id FROM schedule_entries LIMIT 1" > /dev/null 2>&1
check_result $? "Colonne group_id dans schedule_entries"

# 4. Vérifier les vues
echo -e "\n4. Vérification des vues..."
for view in "v_parallel_teaching" "v_parallel_schedule" "v_teacher_workload"; do
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT * FROM $view LIMIT 1" > /dev/null 2>&1
    check_result $? "Vue $view fonctionne"
done

# 5. Vérifier l'API
echo -e "\n5. Vérification de l'API..."
curl -s -f $API_URL > /dev/null 2>&1
check_result $? "API accessible"

# Vérifier la version
VERSION=$(curl -s $API_URL | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
if [[ "$VERSION" == "2.0" ]]; then
    echo -e "${GREEN}✓ Version correcte de l'API: $VERSION${NC}"
else
    echo -e "${RED}✗ Version incorrecte: $VERSION (attendu: 2.0)${NC}"
fi

# 6. Vérifier les endpoints parallèles
echo -e "\n6. Vérification des endpoints spécifiques..."
endpoints=(
    "/api/parallel/groups"
    "/api/parallel/check"
    "/api/stats/parallel"
)

for endpoint in "${endpoints[@]}"; do
    curl -s -f "$API_URL$endpoint" > /dev/null 2>&1
    check_result $? "Endpoint $endpoint"
done

# 7. Statistiques de la base
echo -e "\n7. Statistiques actuelles..."
echo -e "${YELLOW}Base de données:${NC}"

# Compter les groupes parallèles
PG_COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM parallel_groups")
echo "  - Groupes parallèles: $PG_COUNT"

# Compter les détails
PTD_COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM parallel_teaching_details")
echo "  - Détails de cours: $PTD_COUNT"

# Compter les cours marqués parallèles
MARKED_COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM teacher_load WHERE is_parallel = TRUE")
echo "  - Cours marqués parallèles: $MARKED_COUNT"

# 8. Test de cohérence
echo -e "\n8. Test de cohérence..."
ISSUES=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM check_parallel_consistency()")
if [ "$ISSUES" -eq "0" ]; then
    echo -e "${GREEN}✓ Aucun problème de cohérence détecté${NC}"
else
    echo -e "${YELLOW}⚠ $ISSUES problèmes de cohérence détectés${NC}"
    echo "  Exécutez: SELECT * FROM check_parallel_consistency();"
fi

# 9. Test de génération d'emploi du temps
echo -e "\n9. Test rapide de génération..."
response=$(curl -s -X POST $API_URL/generate_schedule \
    -H "Content-Type: application/json" \
    -d '{"time_limit": 10}')

if echo "$response" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✓ Génération d'emploi du temps fonctionnelle${NC}"
else
    echo -e "${YELLOW}⚠ Génération échouée ou timeout${NC}"
fi

# 10. Résumé final
echo -e "\n${YELLOW}================================================${NC}"
echo -e "${YELLOW} Résumé de l'Installation${NC}"
echo -e "${YELLOW}================================================${NC}"

if [ $PG_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ Système de cours parallèles opérationnel${NC}"
    echo -e "${GREEN}  $PG_COUNT groupes parallèles configurés${NC}"
else
    echo -e "${YELLOW}⚠ Aucun groupe parallèle configuré${NC}"
    echo "  Importez vos données Excel pour commencer"
fi

echo -e "\n${YELLOW}Prochaines étapes:${NC}"
echo "1. Importez vos données via n8n: http://localhost:5678"
echo "2. Vérifiez les groupes: curl $API_URL/api/parallel/groups"
echo "3. Générez un emploi du temps: curl -X POST $API_URL/generate_schedule"
echo "4. Visualisez: Ouvrez visualiser_emploi_du_temps.html"

echo -e "\n${GREEN}✓ Vérification terminée avec succès!${NC}"
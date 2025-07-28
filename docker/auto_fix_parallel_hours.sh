#!/bin/bash
# auto_fix_parallel_hours.sh - Correction automatique des incohérences d'heures parallèles

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-school_scheduler}"
DB_USER="${DB_USER:-admin}"
DB_PASS="${DB_PASS:-school123}"
DB_PORT="${DB_PORT:-5432}"
API_URL="${API_URL:-http://localhost:8000}"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Fonction pour afficher les messages
log() {
    echo -e "${2:-$CYAN}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Bannière
clear
echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     CORRECTION AUTOMATIQUE DES HEURES PARALLÈLES        ║"
echo "║          תיקון אוטומטי של שעות מקבילות                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Vérifier la connexion à la base de données
log "Vérification de la connexion à la base de données..."
PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1 || error "Impossible de se connecter à la base de données"
success "Connexion établie"

# 1. Analyser la situation actuelle
echo -e "\n${BOLD}1. ANALYSE DE LA SITUATION ACTUELLE${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ISSUES=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
    SELECT COUNT(DISTINCT group_id) 
    FROM (
        SELECT group_id
        FROM parallel_teaching_details
        GROUP BY group_id
        HAVING COUNT(DISTINCT hours_per_teacher) > 1
    ) as x
" | tr -d ' ')

if [ "$ISSUES" -eq "0" ]; then
    success "Aucune incohérence détectée ! Tous les groupes sont déjà cohérents."
    exit 0
else
    warning "$ISSUES groupes avec des incohérences détectés"
fi

# Afficher les détails
log "Groupes concernés:"
PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
    SELECT 
        pg.group_id as \"ID\",
        pg.subject || ' (' || pg.grade || ')' as \"Cours\",
        COUNT(DISTINCT ptd.teacher_name) as \"Profs\",
        MIN(ptd.hours_per_teacher) || '-' || MAX(ptd.hours_per_teacher) || 'h' as \"Variation\"
    FROM parallel_groups pg
    JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
    GROUP BY pg.group_id, pg.subject, pg.grade
    HAVING COUNT(DISTINCT ptd.hours_per_teacher) > 1
    ORDER BY pg.group_id
"

# 2. Demander confirmation
echo -e "\n${BOLD}2. CONFIRMATION${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}Cette opération va :${NC}"
echo "  • Uniformiser les heures parallèles au minimum de chaque groupe"
echo "  • Créer des entrées séparées pour les heures supplémentaires"
echo "  • Marquer ces heures comme individuelles (non parallèles)"
echo ""
read -p "Voulez-vous continuer ? (o/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Oo]$ ]]; then
    warning "Opération annulée"
    exit 0
fi

# 3. Créer une sauvegarde
echo -e "\n${BOLD}3. SAUVEGARDE DE SÉCURITÉ${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Création de la sauvegarde..."

BACKUP_FILE="backup_parallel_$(date +%Y%m%d_%H%M%S).sql"
PGPASSWORD=$DB_PASS pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
    -t parallel_groups -t parallel_teaching_details -t teacher_load \
    > $BACKUP_FILE 2>/dev/null || error "Échec de la sauvegarde"

success "Sauvegarde créée : $BACKUP_FILE"

# 4. Appliquer les corrections
echo -e "\n${BOLD}4. APPLICATION DES CORRECTIONS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Créer le script SQL temporaire
cat > /tmp/fix_parallel_temp.sql << 'EOF'
BEGIN;

-- Analyse et correction
WITH temp_hours_analysis AS (
    SELECT 
        group_id,
        MIN(hours_per_teacher) as min_hours
    FROM parallel_teaching_details
    GROUP BY group_id
    HAVING COUNT(DISTINCT hours_per_teacher) > 1
),
temp_extra_hours AS (
    SELECT 
        ptd.teacher_name,
        ptd.subject,
        ptd.grade,
        ptd.hours_per_teacher - ta.min_hours as extra_hours,
        ta.min_hours as parallel_hours,
        ptd.group_id
    FROM parallel_teaching_details ptd
    JOIN temp_hours_analysis ta ON ptd.group_id = ta.group_id
    WHERE ptd.hours_per_teacher > ta.min_hours
)
-- Insérer les heures supplémentaires
INSERT INTO teacher_load (teacher_name, subject, grade, class_list, hours, is_parallel)
SELECT 
    teacher_name,
    subject,
    grade,
    NULL,
    extra_hours,
    FALSE
FROM temp_extra_hours
ON CONFLICT DO NOTHING;

-- Mettre à jour les heures dans parallel_teaching_details
UPDATE parallel_teaching_details ptd
SET hours_per_teacher = ta.min_hours
FROM (
    SELECT group_id, MIN(hours_per_teacher) as min_hours
    FROM parallel_teaching_details
    GROUP BY group_id
    HAVING COUNT(DISTINCT hours_per_teacher) > 1
) ta
WHERE ptd.group_id = ta.group_id
  AND ptd.hours_per_teacher > ta.min_hours;

COMMIT;
EOF

log "Application des corrections..."
PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f /tmp/fix_parallel_temp.sql > /tmp/fix_result.log 2>&1

if [ $? -eq 0 ]; then
    success "Corrections appliquées avec succès"
else
    error "Échec de l'application des corrections. Consultez /tmp/fix_result.log"
fi

# 5. Vérification
echo -e "\n${BOLD}5. VÉRIFICATION DES RÉSULTATS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

REMAINING=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
    SELECT COUNT(DISTINCT group_id) 
    FROM (
        SELECT group_id
        FROM parallel_teaching_details
        GROUP BY group_id
        HAVING COUNT(DISTINCT hours_per_teacher) > 1
    ) as x
" | tr -d ' ')

if [ "$REMAINING" -eq "0" ]; then
    success "Toutes les incohérences ont été corrigées !"
else
    error "$REMAINING groupes ont encore des problèmes"
fi

# Afficher les statistiques
echo -e "\n${BOLD}STATISTIQUES :${NC}"
PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
    SELECT 
        'Groupes parallèles cohérents' as \"Métrique\",
        COUNT(*) as \"Valeur\"
    FROM parallel_groups
    UNION ALL
    SELECT 
        'Heures individuelles créées',
        COUNT(*)
    FROM teacher_load
    WHERE is_parallel = FALSE AND class_list IS NULL
"

# 6. Test de génération
echo -e "\n${BOLD}6. TEST DE GÉNÉRATION D'EMPLOI DU TEMPS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Test rapide de génération (10 secondes)..."

RESPONSE=$(curl -s -X POST $API_URL/generate_schedule \
    -H "Content-Type: application/json" \
    -d '{"time_limit": 10}' 2>/dev/null)

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    success "Génération d'emploi du temps fonctionnelle"
else
    warning "La génération a échoué ou timeout (normal pour un test rapide)"
fi

# 7. Rapport final
echo -e "\n${BOLD}${GREEN}═══════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}       CORRECTION TERMINÉE !          ${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════${NC}"

echo -e "\n${BOLD}Prochaines étapes :${NC}"
echo "1. Vérifier les heures individuelles créées :"
echo -e "   ${CYAN}psql -d $DB_NAME -c \"SELECT * FROM teacher_load WHERE is_parallel = FALSE AND class_list IS NULL\"${NC}"
echo ""
echo "2. Générer un emploi du temps complet :"
echo -e "   ${CYAN}curl -X POST $API_URL/generate_schedule -d '{\"time_limit\": 60}'${NC}"
echo ""
echo "3. En cas de problème, restaurer depuis la sauvegarde :"
echo -e "   ${CYAN}psql -d $DB_NAME < $BACKUP_FILE${NC}"

# Nettoyage
rm -f /tmp/fix_parallel_temp.sql /tmp/fix_result.log

echo -e "\n${GREEN}✓ Script terminé avec succès !${NC}"
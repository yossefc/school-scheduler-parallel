#!/bin/bash
# Script de diagnostic et correction à exécuter DANS le conteneur solver

echo "=== DIAGNOSTIC DU SOLVEUR D'EMPLOI DU TEMPS ==="
echo ""

# Configuration
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="school_scheduler"
DB_USER="admin"
PGPASSWORD="school123"
export PGPASSWORD

echo "1. ANALYSE DE FAISABILITÉ"
echo "========================="

# Requête de diagnostic complète
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
WITH stats AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures
)
SELECT 
    nb_classes,
    creneaux,
    heures,
    (nb_classes * creneaux) AS capacite,
    ROUND(heures::numeric/(nb_classes*creneaux)*100,1) AS taux_utilisation_pct
FROM stats;
EOF

echo ""
echo "2. ANALYSE DES GROUPES PARALLÈLES"
echo "================================="

psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
-- Classes avec le plus d'heures
SELECT class_list, COUNT(*) AS lignes, SUM(hours) AS heures_totales
FROM solver_input
WHERE class_list IS NOT NULL AND class_list != ''
GROUP BY class_list
ORDER BY heures_totales DESC
LIMIT 10;
EOF

echo ""
echo "3. DÉTECTION DES DOUBLONS"
echo "========================"

psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
-- Doublons exacts
SELECT teacher_name, subject, grade, class_list, hours, COUNT(*) AS occurrences
FROM solver_input
GROUP BY teacher_name, subject, grade, class_list, hours
HAVING COUNT(*) > 1
ORDER BY occurrences DESC
LIMIT 5;
EOF

echo ""
echo "4. RÉPARTITION DES CRÉNEAUX PAR JOUR"
echo "===================================="

psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
SELECT 
    day_of_week,
    CASE day_of_week
        WHEN 0 THEN 'Dimanche'
        WHEN 1 THEN 'Lundi'
        WHEN 2 THEN 'Mardi'
        WHEN 3 THEN 'Mercredi'
        WHEN 4 THEN 'Jeudi'
        WHEN 5 THEN 'Vendredi'
    END AS jour,
    COUNT(*) AS creneaux_disponibles
FROM time_slots
WHERE is_break = FALSE
GROUP BY day_of_week
ORDER BY day_of_week;
EOF

echo ""
echo "5. RECOMMANDATIONS"
echo "=================="

# Calcul du taux pour afficher des recommandations
TAUX=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
WITH s AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures
)
SELECT ROUND(heures::numeric/(nb_classes*creneaux)*100,1)
FROM s;" | tr -d ' ')

echo "Taux d'utilisation actuel: ${TAUX}%"
echo ""

if (( $(echo "$TAUX > 100" | bc -l) )); then
    echo "❌ IMPOSSIBLE - Le taux est supérieur à 100%"
    echo "   Actions requises:"
    echo "   1. Réduire le nombre d'heures de cours"
    echo "   2. Augmenter le nombre de créneaux disponibles"
    echo "   3. Vérifier les doublons dans solver_input"
    echo ""
    echo "   Pour nettoyer les doublons, exécutez:"
    echo "   ./clean_solver_input.sh"
elif (( $(echo "$TAUX > 85" | bc -l) )); then
    echo "⚠️  DIFFICILE - Le taux est entre 85% et 100%"
    echo "   Actions recommandées:"
    echo "   1. Augmenter time_limit à 1200 secondes"
    echo "   2. Simplifier certaines contraintes"
    echo "   3. Considérer l'ajout de créneaux"
else
    echo "✅ FAISABLE - Le taux est inférieur à 85%"
    echo "   La génération devrait fonctionner normalement."
fi

echo ""
echo "Pour lancer la génération avec un time_limit augmenté:"
echo "curl -X POST 'http://localhost:8000/generate_schedule' -H 'Content-Type: application/json' -d '{\"time_limit\": 1200}'"

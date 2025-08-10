#!/bin/bash
# Script principal pour corriger automatiquement les problèmes du solveur

echo "╔════════════════════════════════════════════════════════╗"
echo "║     CORRECTION AUTOMATIQUE DU SOLVEUR D'EMPLOI DU TEMPS ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Configuration
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="school_scheduler"
DB_USER="admin"
PGPASSWORD="school123"
export PGPASSWORD

# Fonction pour afficher une barre de progression
show_progress() {
    echo -n "$1... "
}

# Fonction pour marquer une étape comme terminée
done_step() {
    echo "✓"
}

# 1. Diagnostic initial
show_progress "Diagnostic initial"
TAUX_INITIAL=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
WITH s AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures
)
SELECT ROUND(heures::numeric/(nb_classes*creneaux)*100,1)
FROM s;" | tr -d ' ')
done_step

echo "  → Taux d'utilisation initial: ${TAUX_INITIAL}%"
echo ""

# 2. Sauvegarde
show_progress "Sauvegarde des données actuelles"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -q -c "
DROP TABLE IF EXISTS solver_input_auto_backup;
CREATE TABLE solver_input_auto_backup AS SELECT * FROM solver_input;" 2>/dev/null
done_step

# 3. Nettoyage des doublons
show_progress "Suppression des doublons"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -q << EOF 2>/dev/null
BEGIN;
TRUNCATE solver_input;
INSERT INTO solver_input (course_type, teacher_name, subject, grade, class_list, hours, is_parallel, group_id)
SELECT DISTINCT
  'regular' AS course_type,
  teacher_name,
  subject,
  grade,
  class_list,
  hours,
  COALESCE(is_parallel, FALSE),
  load_id
FROM teacher_load
WHERE hours > 0
  AND teacher_name IS NOT NULL
  AND teacher_name <> 'לא משובץ'
  AND subject IS NOT NULL
  AND class_list IS NOT NULL;
COMMIT;
EOF
done_step

# 4. Consolidation des groupes parallèles
show_progress "Consolidation des groupes parallèles"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -q << EOF 2>/dev/null
BEGIN;
-- Identifier et marquer les vrais groupes parallèles
UPDATE solver_input
SET is_parallel = TRUE
WHERE class_list LIKE '%,%'
  AND (class_list, subject, grade) IN (
    SELECT class_list, subject, grade
    FROM solver_input
    WHERE class_list LIKE '%,%'
    GROUP BY class_list, subject, grade
    HAVING COUNT(DISTINCT teacher_name) > 1
  );
COMMIT;
EOF
done_step

# 5. Nouveau diagnostic
show_progress "Calcul du nouveau taux"
TAUX_FINAL=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "
WITH s AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures
)
SELECT ROUND(heures::numeric/(nb_classes*creneaux)*100,1)
FROM s;" | tr -d ' ')
done_step

echo "  → Taux d'utilisation après correction: ${TAUX_FINAL}%"
echo ""

# 6. Résumé et recommandations
echo "╔════════════════════════════════════════════════════════╗"
echo "║                       RÉSUMÉ                           ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
WITH stats AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures,
    (SELECT COUNT(*) FROM solver_input) AS nb_cours
)
SELECT 
    nb_cours || ' cours' as "Cours à planifier",
    heures || ' heures' as "Heures totales",
    nb_classes || ' classes' as "Nombre de classes",
    creneaux || ' créneaux' as "Créneaux/semaine",
    (nb_classes * creneaux) || ' h' as "Capacité totale"
FROM stats;
EOF

echo ""
echo "Taux d'utilisation: $TAUX_INITIAL% → $TAUX_FINAL%"
echo ""

# Recommandations finales
if (( $(echo "$TAUX_FINAL > 100" | bc -l) )); then
    echo "❌ TOUJOURS INFAISABLE (> 100%)"
    echo ""
    echo "Options:"
    echo "1. Tester sur un seul niveau:"
    echo "   ./test_single_grade.sh ט"
    echo ""
    echo "2. Réduire la charge en excluant certains cours:"
    echo "   psql> DELETE FROM solver_input WHERE subject = 'חינוך' AND hours = 1;"
    echo ""
    echo "3. Augmenter les créneaux disponibles"
elif (( $(echo "$TAUX_FINAL > 85" | bc -l) )); then
    echo "⚠️  DIFFICILE MAIS POSSIBLE (85-100%)"
    echo ""
    echo "Lancer avec un time_limit élevé:"
    echo "curl -X POST 'http://localhost:8000/generate_schedule' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"time_limit\": 1800}'"
else
    echo "✅ FAISABLE (< 85%)"
    echo ""
    echo "Lancer la génération:"
    echo "curl -X POST 'http://localhost:8000/generate_schedule' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"time_limit\": 600}'"
fi

echo ""
echo "Pour annuler les modifications:"
echo "psql> TRUNCATE solver_input; INSERT INTO solver_input SELECT * FROM solver_input_auto_backup;"

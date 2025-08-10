#!/bin/bash
# Script de nettoyage de solver_input à exécuter DANS le conteneur solver

echo "=== NETTOYAGE DE SOLVER_INPUT ==="
echo ""

# Configuration
DB_HOST="postgres"
DB_PORT="5432"
DB_NAME="school_scheduler"
DB_USER="admin"
PGPASSWORD="school123"
export PGPASSWORD

echo "1. État actuel de solver_input:"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
SELECT COUNT(*) as nb_lignes, COALESCE(SUM(hours), 0) as heures_totales 
FROM solver_input;"

echo ""
echo "2. Sauvegarde de solver_input actuel..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
CREATE TABLE IF NOT EXISTS solver_input_backup AS 
SELECT * FROM solver_input;"

echo ""
echo "3. Reconstruction de solver_input SANS doublons..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
BEGIN;

-- Vider la table
TRUNCATE solver_input;

-- Reconstruire depuis teacher_load en éliminant les doublons
INSERT INTO solver_input (course_type, teacher_name, subject, grade, class_list, hours, is_parallel, group_id)
SELECT DISTINCT
  'regular' AS course_type,
  tl.teacher_name,
  tl.subject,
  tl.grade,
  tl.class_list,
  tl.hours,
  COALESCE(tl.is_parallel, FALSE),
  tl.load_id
FROM teacher_load tl
WHERE tl.hours > 0
  AND tl.teacher_name IS NOT NULL
  AND tl.teacher_name <> 'לא משובץ'
  AND tl.subject IS NOT NULL
  AND tl.class_list IS NOT NULL;

COMMIT;
EOF

echo ""
echo "4. Nouvel état de solver_input:"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
SELECT COUNT(*) as nb_lignes, COALESCE(SUM(hours), 0) as heures_totales 
FROM solver_input;"

echo ""
echo "5. Nouvelle analyse de faisabilité:"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << EOF
WITH stats AS (
  SELECT
    (SELECT COUNT(*) FROM classes) AS nb_classes,
    (SELECT COUNT(*) FROM time_slots WHERE is_break = FALSE) AS creneaux,
    (SELECT COALESCE(SUM(hours),0) FROM solver_input) AS heures
)
SELECT 
    nb_classes || ' classes' as classes,
    creneaux || ' créneaux/semaine' as creneaux,
    heures || ' heures' as heures_a_planifier,
    (nb_classes * creneaux) || ' heures-créneaux' as capacite_totale,
    ROUND(heures::numeric/(nb_classes*creneaux)*100,1) || '%' AS taux_utilisation
FROM stats;
EOF

echo ""
echo "✓ Nettoyage terminé!"
echo ""
echo "Pour restaurer l'ancienne version:"
echo "psql -h postgres -U admin -d school_scheduler -c 'TRUNCATE solver_input; INSERT INTO solver_input SELECT * FROM solver_input_backup;'"

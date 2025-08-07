-- ================================================================
-- 001_fix_teacher_load_duplicates.sql
-- Supprime les doublons dans teacher_load et ajoute une contrainte UNIQUE
-- ================================================================

BEGIN;

-- 1) Supprimer les doublons exacts (même professeur, matière, grade, classes, heures)
WITH duplicates AS (
    SELECT load_id,
           ROW_NUMBER() OVER (PARTITION BY
                                teacher_name,
                                subject,
                                COALESCE(grade, ''),
                                COALESCE(class_list, ''),
                                COALESCE(hours, 0)
                             ORDER BY load_id) AS rn
    FROM teacher_load
)
DELETE FROM teacher_load tl
USING duplicates d
WHERE tl.load_id = d.load_id
  AND d.rn > 1;

-- 2) Ajouter un indice UNIQUE pour empêcher les prochaines insertions dupliquées
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   pg_indexes
        WHERE  schemaname = 'public'
          AND  indexname  = 'idx_teacher_load_unique'
    ) THEN
        EXECUTE 'CREATE UNIQUE INDEX idx_teacher_load_unique
                 ON teacher_load (
                     teacher_name,
                     subject,
                     COALESCE(grade, ''),
                     COALESCE(class_list, ''),
                     COALESCE(hours, 0)
                 );';
    END IF;
END$$;

COMMIT;


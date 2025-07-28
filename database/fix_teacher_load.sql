/* ------------------------------------------------------------------
   fix_teacher_load.sql  –  Nettoyage sans éclatement des classes
------------------------------------------------------------------*/
BEGIN;

------------------------------------------------------------------
-- 0. Sauvegarde de la table d’origine
------------------------------------------------------------------
DROP TABLE IF EXISTS teacher_load_bak;
CREATE TABLE teacher_load_bak AS TABLE teacher_load;

------------------------------------------------------------------
-- 1. Colonne is_parallel si elle n’existe pas déjà
------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
     SELECT 1
     FROM   information_schema.columns
     WHERE  table_name = 'teacher_load'
       AND  column_name = 'is_parallel'
  ) THEN
     ALTER TABLE teacher_load
       ADD COLUMN is_parallel BOOLEAN DEFAULT FALSE;
  END IF;
END$$;

------------------------------------------------------------------
-- 2. Normalisation de class_list
------------------------------------------------------------------
/* 2.1  Remplace les ellipses (…) ou “...” par des virgules */
UPDATE teacher_load
SET    class_list = regexp_replace(class_list, '\s*(…|\.{3})\s*', ',', 'g')
WHERE  class_list ~ '…|\.{3}';

/* 2.2  Remplace les séparateurs exotiques (maqaf, virgule hébraïque, etc.)
         par une virgule ASCII, puis supprime les espaces superflus       */
UPDATE teacher_load
SET    class_list =
       trim(both ','
            FROM regexp_replace(
                   regexp_replace(class_list,
                                   '\s*[,\u05BE\uFF0C\u060C]\s*', ',', 'g'),
                   '\s+', ' ', 'g'))
WHERE  class_list IS NOT NULL;

------------------------------------------------------------------
-- 3. Marque les lignes parallèles (>= 2 classes)
------------------------------------------------------------------
UPDATE teacher_load
SET    is_parallel = TRUE
WHERE  class_list LIKE '%,%';

------------------------------------------------------------------
-- 4. Supprime les surveillances שהייה*
------------------------------------------------------------------
DELETE FROM teacher_load
WHERE  subject ILIKE 'שהייה%';

COMMIT;

------------------------------------------------------------------
-- 5. Statistiques rapides
------------------------------------------------------------------
SELECT
  'after cleanup'                                   AS info,
  COUNT(*)                                          AS total_rows,
  COUNT(*) FILTER (WHERE is_parallel)               AS parallel_rows,
  COUNT(*) FILTER (WHERE class_list IS NULL)        AS meeting_rows,
  COUNT(DISTINCT teacher_name)                      AS teachers,
  COUNT(DISTINCT subject)                           AS subjects
FROM teacher_load;

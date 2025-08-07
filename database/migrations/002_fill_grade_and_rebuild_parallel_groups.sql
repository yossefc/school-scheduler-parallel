-- ================================================================
-- 002_fill_grade_and_rebuild_parallel_groups.sql
-- Renseigne la colonne grade manquante dans teacher_load puis
-- reconstruit complètement les groupes parallèles pour avoir
-- un groupement correct par sujet ET par שכבה (grade).
-- ================================================================

BEGIN;

-- ------------------------------------------------
-- 1) Compléter la colonne grade si elle est nulle
-- ------------------------------------------------
-- Tentative #1 : utiliser la table classes si disponible
WITH classes_map AS (
    SELECT class_name, grade
    FROM classes
)
UPDATE teacher_load tl
SET grade = COALESCE(tl.grade, cls.grade::varchar)
FROM (
    SELECT tl.load_id, MIN(c.grade) AS grade
    FROM teacher_load tl
    JOIN LATERAL unnest(string_to_array(COALESCE(tl.class_list, ''), ',')) AS cls_name(raw)
        ON TRUE
    JOIN classes c ON c.class_name = trim(cls_name.raw)
    GROUP BY tl.load_id
) AS cls
WHERE tl.load_id = cls.load_id
  AND (tl.grade IS NULL OR tl.grade = '');

-- ------------------------------------------------
-- 2) Reconstruire entièrement les tables parallèles
-- ------------------------------------------------

-- Nettoyer les anciennes données
TRUNCATE TABLE parallel_groups CASCADE;
TRUNCATE TABLE parallel_teaching_details CASCADE;

-- Supprimer les anciennes contraintes parallèles
DELETE FROM constraints WHERE constraint_type = 'parallel_teaching';

-- (Ré)identifier les groupes parallèles
WITH parallel_candidates AS (
    SELECT subject,
           grade,
           COUNT(DISTINCT teacher_name)            AS teacher_count,
           STRING_AGG(DISTINCT teacher_name, ', ' ORDER BY teacher_name) AS teachers,
           STRING_AGG(DISTINCT class_list, ' | ' ORDER BY class_list)    AS all_classes,
           SUM(hours)                              AS total_hours,
           MAX(hours)                              AS max_hours_per_teacher
    FROM teacher_load
    WHERE class_list IS NOT NULL
      AND class_list LIKE '%,%'
    GROUP BY subject, grade
    HAVING COUNT(DISTINCT teacher_name) > 1
)
INSERT INTO parallel_groups (subject, grade, teachers, class_lists)
SELECT subject, grade, teachers, all_classes
FROM parallel_candidates;

-- Détails
WITH parallel_info AS (
    SELECT pg.group_id,
           pg.subject,
           pg.grade,
           unnest(string_to_array(pg.teachers, ', ')) AS teacher_name
    FROM parallel_groups pg
)
INSERT INTO parallel_teaching_details (group_id, teacher_name, subject, grade, hours_per_teacher, classes_covered)
SELECT pi.group_id,
       pi.teacher_name,
       pi.subject,
       pi.grade,
       tl.hours,
       tl.class_list
FROM parallel_info pi
JOIN teacher_load tl ON tl.teacher_name = pi.teacher_name
                     AND tl.subject      = pi.subject
                     AND tl.grade        = pi.grade
WHERE tl.class_list LIKE '%,%';

-- Mettre à jour l'indicateur is_parallel
UPDATE teacher_load tl
SET is_parallel = TRUE
FROM parallel_teaching_details ptd
WHERE tl.teacher_name = ptd.teacher_name
  AND tl.subject      = ptd.subject
  AND tl.grade        = ptd.grade
  AND tl.class_list LIKE '%,%';

-- Ajouter les contraintes parallèles
INSERT INTO constraints (
    constraint_type,
    priority,
    entity_type,
    entity_name,
    constraint_data
)
SELECT 'parallel_teaching',
       1,
       'group',
       'parallel_group_' || group_id,
       jsonb_build_object(
           'group_id',  group_id,
           'subject',   subject,
           'grade',     grade,
           'teachers',  string_to_array(teachers, ', '),
           'hours',     max_hours_per_teacher,
           'simultaneous', true
       )
FROM parallel_groups pg
JOIN (
    SELECT group_id, MAX(hours_per_teacher) AS max_hours_per_teacher
    FROM parallel_teaching_details
    GROUP BY group_id
) h USING (group_id);

COMMIT;


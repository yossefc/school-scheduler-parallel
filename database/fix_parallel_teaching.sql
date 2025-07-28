-- ================================================================
-- fix_parallel_teaching.sql - Gestion correcte des cours parallèles
-- ================================================================

BEGIN;

-- 1. Créer une table temporaire pour analyser les patterns
DROP TABLE IF EXISTS temp_load_analysis;
CREATE TEMP TABLE temp_load_analysis AS
SELECT 
    load_id,
    teacher_name,
    subject,
    grade,
    class_list,
    hours,
    -- Compter le nombre de classes
    array_length(string_to_array(class_list, ','), 1) as class_count,
    -- Vérifier si c'est potentiellement parallèle
    CASE 
        WHEN class_list LIKE '%,%' THEN TRUE
        ELSE FALSE
    END as is_multi_class
FROM teacher_load
WHERE class_list IS NOT NULL;

-- 2. Identifier les groupes de professeurs enseignant la même matière au même niveau
DROP TABLE IF EXISTS temp_parallel_candidates;
CREATE TEMP TABLE temp_parallel_candidates AS
SELECT 
    subject,
    grade,
    COUNT(DISTINCT teacher_name) as teacher_count,
    STRING_AGG(DISTINCT teacher_name, ', ' ORDER BY teacher_name) as teachers,
    STRING_AGG(DISTINCT class_list, ' | ' ORDER BY class_list) as all_classes,
    SUM(hours) as total_hours,
    MAX(hours) as max_hours_per_teacher
FROM teacher_load
WHERE class_list IS NOT NULL
  AND class_list LIKE '%,%'  -- Multi-classes seulement
GROUP BY subject, grade
HAVING COUNT(DISTINCT teacher_name) > 1;  -- Au moins 2 profs

-- 3. Vider la table parallel_groups existante
TRUNCATE TABLE parallel_groups CASCADE;

-- 4. Insérer les vrais groupes parallèles identifiés
INSERT INTO parallel_groups (subject, grade, teachers, class_lists)
SELECT 
    subject,
    grade,
    teachers,
    all_classes
FROM temp_parallel_candidates;

-- 5. Créer une nouvelle table pour les cours parallèles détaillés
DROP TABLE IF EXISTS parallel_teaching_details CASCADE;
CREATE TABLE parallel_teaching_details (
    detail_id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES parallel_groups(group_id),
    teacher_name VARCHAR(100),
    subject VARCHAR(100),
    grade VARCHAR(10),
    hours_per_teacher INTEGER,
    classes_covered TEXT,  -- Les classes que ce groupe couvre
    simultaneous_slots INTEGER,  -- Nombre de créneaux simultanés
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Remplir les détails des cours parallèles
WITH parallel_info AS (
    SELECT 
        pg.group_id,
        pg.subject,
        pg.grade,
        unnest(string_to_array(pg.teachers, ', ')) as teacher_name
    FROM parallel_groups pg
)
INSERT INTO parallel_teaching_details (
    group_id, teacher_name, subject, grade, hours_per_teacher, classes_covered
)
SELECT 
    pi.group_id,
    pi.teacher_name,
    pi.subject,
    pi.grade,
    tl.hours,
    tl.class_list
FROM parallel_info pi
JOIN teacher_load tl ON 
    tl.teacher_name = pi.teacher_name 
    AND tl.subject = pi.subject 
    AND tl.grade = pi.grade
WHERE tl.class_list LIKE '%,%';

-- 7. Marquer dans teacher_load les cours qui sont parallèles
UPDATE teacher_load tl
SET is_parallel = TRUE
FROM parallel_teaching_details ptd
WHERE tl.teacher_name = ptd.teacher_name
  AND tl.subject = ptd.subject
  AND tl.grade = ptd.grade
  AND tl.class_list LIKE '%,%';

-- 8. Créer une vue pour faciliter l'utilisation
DROP VIEW IF EXISTS v_parallel_teaching;
CREATE VIEW v_parallel_teaching AS
SELECT 
    pg.group_id,
    pg.subject,
    pg.grade,
    pg.teachers,
    ptd.hours_per_teacher as hours,
    COUNT(DISTINCT ptd.teacher_name) as teacher_count,
    STRING_AGG(DISTINCT 
        REPLACE(REPLACE(ptd.classes_covered, ' ', ''), ',', '|'), 
        ', '
    ) as all_classes
FROM parallel_groups pg
JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers, ptd.hours_per_teacher;

-- 9. Ajouter des contraintes pour l'enseignement parallèle
INSERT INTO constraints (
    constraint_type, 
    priority, 
    entity_type, 
    entity_name, 
    constraint_data
)
SELECT 
    'parallel_teaching',
    1,  -- Priorité maximale
    'group',
    'parallel_group_' || group_id,
    jsonb_build_object(
        'group_id', group_id,
        'subject', subject,
        'grade', grade,
        'teachers', string_to_array(teachers, ', '),
        'hours', hours,
        'simultaneous', true,
        'description', 'Cours parallèle: ' || teachers || ' enseignent ' || subject || ' niveau ' || grade
    )
FROM v_parallel_teaching;

-- 10. Rapport de migration
SELECT 'Migration Report' as info;

SELECT 
    'Groupes parallèles créés' as metric,
    COUNT(*) as value
FROM parallel_groups;

SELECT 
    'Détails de cours parallèles' as metric,
    COUNT(*) as value
FROM parallel_teaching_details;

SELECT 
    'Contraintes parallèles ajoutées' as metric,
    COUNT(*) as value
FROM constraints
WHERE constraint_type = 'parallel_teaching';

-- Afficher les groupes parallèles créés
SELECT 
    '=== GROUPES PARALLÈLES ===' as section,
    subject,
    grade,
    teachers,
    hours as hours_per_teacher,
    teacher_count,
    all_classes
FROM v_parallel_teaching
ORDER BY grade, subject;

COMMIT;
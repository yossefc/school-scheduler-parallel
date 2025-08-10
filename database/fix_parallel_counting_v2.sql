-- fix_parallel_counting_v2.sql
-- Version corrigée sans UNNEST dans STRING_AGG

BEGIN;

-- 1. Vider solver_input
TRUNCATE TABLE solver_input CASCADE;

-- 2. Insérer les cours INDIVIDUELS (classe unique)
INSERT INTO solver_input (
    course_type, teacher_name, subject, grade, 
    class_list, hours, is_parallel, teacher_count
)
SELECT 
    'individual',
    teacher_name,
    subject,
    COALESCE(grade, '0'),
    class_list,
    hours,
    FALSE,
    1
FROM teacher_load
WHERE (is_parallel = FALSE OR is_parallel IS NULL)
   AND (class_list NOT LIKE '%,%' OR class_list IS NULL);

-- 3. Créer les GROUPES PARALLÈLES
-- D'abord, normaliser les classes dans une table temporaire
CREATE TEMP TABLE normalized_classes AS
WITH class_expansions AS (
    SELECT 
        teacher_name,
        subject,
        COALESCE(grade, '0') as grade,
        hours,
        TRIM(UNNEST(string_to_array(class_list, ','))) as single_class
    FROM teacher_load
    WHERE class_list LIKE '%,%' OR is_parallel = TRUE
)
SELECT DISTINCT
    subject,
    grade,
    single_class
FROM class_expansions;

-- Maintenant créer les groupes parallèles
WITH parallel_groups AS (
    SELECT 
        t.subject,
        t.grade,
        STRING_AGG(DISTINCT t.teacher_name, ', ' ORDER BY t.teacher_name) as teachers,
        STRING_AGG(DISTINCT nc.single_class, ',' ORDER BY nc.single_class) as all_classes,
        MIN(t.hours) as group_hours,
        COUNT(DISTINCT t.teacher_name) as teacher_count
    FROM (
        SELECT DISTINCT
            teacher_name,
            subject,
            COALESCE(grade, '0') as grade,
            hours
        FROM teacher_load
        WHERE class_list LIKE '%,%' OR is_parallel = TRUE
    ) t
    JOIN normalized_classes nc 
        ON nc.subject = t.subject 
        AND nc.grade = t.grade
    GROUP BY t.subject, t.grade
    HAVING COUNT(DISTINCT t.teacher_name) > 1
)
INSERT INTO solver_input (
    course_type, teacher_name, subject, grade,
    class_list, hours, is_parallel, teacher_count
)
SELECT 
    'parallel_group',
    teachers,
    subject,
    grade,
    all_classes,
    group_hours,
    TRUE,
    teacher_count
FROM parallel_groups;

-- 4. Gérer les cours "parallèles" avec un seul prof
INSERT INTO solver_input (
    course_type, teacher_name, subject, grade,
    class_list, hours, is_parallel, teacher_count
)
SELECT 
    'individual',
    teacher_name,
    subject,
    COALESCE(grade, '0'),
    class_list,
    hours,
    FALSE,
    1
FROM teacher_load t1
WHERE (is_parallel = TRUE OR class_list LIKE '%,%')
  AND NOT EXISTS (
    SELECT 1 
    FROM teacher_load t2 
    WHERE t2.subject = t1.subject 
      AND COALESCE(t2.grade, '0') = COALESCE(t1.grade, '0')
      AND t2.teacher_name != t1.teacher_name
      AND (t2.is_parallel = TRUE OR t2.class_list LIKE '%,%')
  );

-- 5. Nettoyer
DROP TABLE normalized_classes;

-- 6. Analyser les résultats
DO $$
DECLARE
    hours_before INTEGER;
    hours_after INTEGER;
    courses_before INTEGER;
    courses_after INTEGER;
BEGIN
    SELECT SUM(hours), COUNT(*) INTO hours_before, courses_before FROM teacher_load;
    SELECT SUM(hours), COUNT(*) INTO hours_after, courses_after FROM solver_input;
    
    RAISE NOTICE '';
    RAISE NOTICE '=== CORRECTION DU TRIPLE COMPTAGE ===';
    RAISE NOTICE '';
    RAISE NOTICE 'AVANT (teacher_load): % lignes, % heures', courses_before, hours_before;
    RAISE NOTICE 'APRÈS (solver_input): % cours, % heures', courses_after, hours_after;
    
    IF hours_before > hours_after THEN
        RAISE NOTICE 'Réduction: % heures (-%)', 
            hours_before - hours_after, 
            ROUND(((hours_before - hours_after)::NUMERIC / hours_before) * 100) || '%';
    END IF;
    
    -- Faisabilité
    DECLARE
        total_slots INTEGER := 22 * 54;  -- 22 classes × 54 créneaux
        utilization NUMERIC;
    BEGIN
        utilization := (hours_after::NUMERIC / total_slots) * 100;
        
        RAISE NOTICE '';
        RAISE NOTICE '=== FAISABILITÉ ===';
        RAISE NOTICE 'Créneaux disponibles: %', total_slots;
        RAISE NOTICE 'Taux d''utilisation: %', ROUND(utilization, 1) || '%';
        
        IF utilization > 100 THEN
            RAISE WARNING '❌ IMPOSSIBLE: Trop d''heures!';
        ELSIF utilization > 85 THEN
            RAISE NOTICE '⚠️  DIFFICILE: Utilisez time_limit=600';
        ELSE
            RAISE NOTICE '✅ FAISABLE!';
        END IF;
    END;
END $$;

-- 7. Afficher les statistiques
SELECT 'Résumé final:' as info;

SELECT 
    course_type,
    COUNT(*) as nombre,
    SUM(hours) as heures_totales
FROM solver_input
GROUP BY course_type

UNION ALL

SELECT 
    'TOTAL' as course_type,
    COUNT(*),
    SUM(hours)
FROM solver_input
ORDER BY course_type;

-- 8. Exemples de groupes parallèles
SELECT 'Exemples de groupes parallèles:' as info;

SELECT 
    subject as matière,
    grade as niveau,
    teacher_count || ' professeurs' as nb_profs,
    hours || ' heures' as heures
FROM solver_input
WHERE course_type = 'parallel_group'
ORDER BY teacher_count DESC
LIMIT 5;

COMMIT;





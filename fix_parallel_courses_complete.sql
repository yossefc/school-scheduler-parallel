-- ================================================================
-- CORRECTION COMPLÈTE DES COURS PARALLÈLES
-- ================================================================
-- Ce script corrige les données pour bien gérer les groupes parallèles

BEGIN;

-- 1. Sauvegarder l'état actuel
DROP TABLE IF EXISTS solver_input_backup_before_fix;
CREATE TABLE solver_input_backup_before_fix AS 
SELECT * FROM solver_input;

-- 2. Analyser les cours qui devraient être parallèles
DROP TABLE IF EXISTS parallel_analysis;
CREATE TEMP TABLE parallel_analysis AS
WITH potential_parallel AS (
    -- Identifier les cours avec les mêmes matière/niveau/classes
    SELECT 
        subject,
        grade,
        class_list,
        COUNT(DISTINCT teacher_name) as teacher_count,
        STRING_AGG(DISTINCT teacher_name, ', ' ORDER BY teacher_name) as all_teachers,
        MIN(hours) as min_hours,
        MAX(hours) as max_hours,
        AVG(hours) as avg_hours
    FROM solver_input
    WHERE class_list LIKE '%,%'  -- Multi-classes uniquement
       OR course_type = 'parallel'
    GROUP BY subject, grade, class_list
)
SELECT * FROM potential_parallel 
WHERE teacher_count > 1;

-- Afficher l'analyse
SELECT 
    '🔍 Groupes parallèles détectés:' as info,
    COUNT(*) as nombre_groupes,
    SUM(teacher_count) as total_profs
FROM parallel_analysis;

-- 3. Vider solver_input pour reconstruction
TRUNCATE TABLE solver_input CASCADE;

-- 4. Ajouter la colonne teacher_names si elle n'existe pas
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'solver_input' 
        AND column_name = 'teacher_names'
    ) THEN
        ALTER TABLE solver_input ADD COLUMN teacher_names TEXT;
    END IF;
END $$;

-- 5. Reconstruire solver_input avec les groupes parallèles corrects
-- 5a. D'abord, insérer les cours vraiment parallèles
INSERT INTO solver_input (
    course_type, 
    subject, 
    grade, 
    class_list, 
    hours, 
    is_parallel,
    teacher_names,  -- Liste des profs
    teacher_count,
    group_id
)
SELECT 
    'parallel' as course_type,
    pa.subject,
    pa.grade,
    pa.class_list,
    pa.min_hours as hours,  -- Prendre le minimum d'heures communes
    TRUE as is_parallel,
    pa.all_teachers as teacher_names,  -- Tous les profs séparés par virgules
    pa.teacher_count,
    -- Générer un group_id unique basé sur subject+grade+classes
    abs(hashtext(pa.subject || '_' || COALESCE(pa.grade, '0') || '_' || pa.class_list)) % 10000 as group_id
FROM parallel_analysis pa;

-- 5b. Ajouter les heures supplémentaires individuelles si nécessaire
-- (Si un prof a plus d'heures que le minimum du groupe)
INSERT INTO solver_input (
    course_type,
    teacher_name,
    subject,
    grade,
    class_list,
    hours,
    is_parallel,
    teacher_names,
    group_id
)
SELECT 
    'individual' as course_type,
    si_orig.teacher_name,
    si_orig.subject,
    si_orig.grade,
    si_orig.class_list,
    (si_orig.hours - pa.min_hours) as hours,  -- Différence avec le minimum
    FALSE as is_parallel,
    si_orig.teacher_name as teacher_names,
    NULL as group_id
FROM solver_input_backup_before_fix si_orig
JOIN parallel_analysis pa 
    ON pa.subject = si_orig.subject 
    AND COALESCE(pa.grade, '') = COALESCE(si_orig.grade, '')
    AND pa.class_list = si_orig.class_list
WHERE si_orig.hours > pa.min_hours;

-- 5c. Insérer tous les cours individuels (non parallèles)
INSERT INTO solver_input (
    course_type,
    teacher_name,
    subject,
    grade,
    class_list,
    hours,
    is_parallel,
    teacher_names
)
SELECT 
    'individual',
    teacher_name,
    subject,
    grade,
    class_list,
    hours,
    FALSE,
    teacher_name  -- Un seul prof
FROM solver_input_backup_before_fix
WHERE NOT EXISTS (
    -- Exclure les cours déjà traités comme parallèles
    SELECT 1 FROM parallel_analysis pa
    WHERE pa.subject = solver_input_backup_before_fix.subject
    AND COALESCE(pa.grade, '') = COALESCE(solver_input_backup_before_fix.grade, '')
    AND pa.class_list = solver_input_backup_before_fix.class_list
)
AND hours > 0;

-- 6. Vérifier le résultat
SELECT 
    '✅ Résultat après correction:' as status,
    COUNT(*) FILTER (WHERE is_parallel = TRUE) as cours_paralleles,
    COUNT(*) FILTER (WHERE is_parallel = FALSE) as cours_individuels,
    COUNT(DISTINCT teacher_names) FILTER (WHERE is_parallel = TRUE) as groupes_avec_multi_profs,
    SUM(hours) as total_heures
FROM solver_input;

-- 7. Afficher un échantillon des cours parallèles créés
SELECT 
    course_id,
    course_type,
    subject,
    grade,
    class_list,
    teacher_names,
    hours,
    is_parallel,
    group_id
FROM solver_input
WHERE is_parallel = TRUE
LIMIT 5;

-- 8. Analyse de faisabilité finale
WITH stats AS (
    SELECT 
        (SELECT COUNT(*) FROM classes) as nb_classes,
        (SELECT COUNT(*) FROM time_slots WHERE day_of_week < 5) as slots_disponibles,  -- Exclure vendredi
        (SELECT SUM(hours) FROM solver_input) as total_heures
)
SELECT 
    nb_classes || ' classes' as classes,
    slots_disponibles || ' créneaux (dim-jeu)' as creneaux,
    total_heures || ' heures à planifier' as heures,
    ROUND(100.0 * total_heures / (nb_classes * slots_disponibles), 1) || '%' as taux_utilisation,
    CASE 
        WHEN total_heures > nb_classes * slots_disponibles THEN '❌ IMPOSSIBLE - Trop d''heures!'
        WHEN total_heures > nb_classes * slots_disponibles * 0.9 THEN '⚠️ TRÈS DIFFICILE'
        WHEN total_heures > nb_classes * slots_disponibles * 0.8 THEN '🟡 DIFFICILE'
        ELSE '✅ FAISABLE'
    END as faisabilite
FROM stats;

COMMIT;

-- Message final
SELECT '
========================================
📋 CORRECTION TERMINÉE
========================================
Les cours parallèles ont été correctement configurés.
La colonne teacher_names contient maintenant la liste des profs.

⚠️ IMPORTANT : Relancez maintenant la génération d''emploi du temps !
========================================
' as message;
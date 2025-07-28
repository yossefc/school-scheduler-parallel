-- ================================================================
-- debug_queries_parallel.sql - Requêtes utiles pour le debugging
-- et la maintenance du système de cours parallèles
-- ================================================================

-- 1. VUE D'ENSEMBLE DES COURS PARALLÈLES
-- Affiche tous les groupes avec leurs détails
SELECT 
    pg.group_id,
    pg.subject AS "Matière",
    pg.grade AS "Niveau",
    pg.teachers AS "Professeurs",
    COUNT(DISTINCT ptd.teacher_name) AS "Nb Profs",
    MAX(ptd.hours_per_teacher) AS "Heures/Prof",
    STRING_AGG(DISTINCT ptd.classes_covered, ' | ' ORDER BY ptd.classes_covered) AS "Classes"
FROM parallel_groups pg
LEFT JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
ORDER BY pg.grade, pg.subject;

-- 2. VÉRIFIER LES INCOHÉRENCES D'HEURES
-- Trouve les groupes où les profs n'ont pas le même nombre d'heures
WITH hour_check AS (
    SELECT 
        group_id,
        COUNT(DISTINCT hours_per_teacher) as different_hours,
        STRING_AGG(teacher_name || ': ' || hours_per_teacher || 'h', ', ' ORDER BY teacher_name) as details
    FROM parallel_teaching_details
    GROUP BY group_id
    HAVING COUNT(DISTINCT hours_per_teacher) > 1
)
SELECT 
    pg.subject,
    pg.grade,
    hc.details AS "Détail des heures"
FROM hour_check hc
JOIN parallel_groups pg ON hc.group_id = pg.group_id;

-- 3. PROFESSEURS AVEC COURS PARALLÈLES ET INDIVIDUELS
-- Montre les profs qui ont les deux types de cours
WITH teacher_summary AS (
    SELECT 
        teacher_name,
        SUM(CASE WHEN is_parallel THEN hours ELSE 0 END) as parallel_hours,
        SUM(CASE WHEN NOT is_parallel OR is_parallel IS NULL THEN hours ELSE 0 END) as individual_hours,
        COUNT(DISTINCT CASE WHEN is_parallel THEN subject || '_' || grade END) as parallel_subjects,
        COUNT(DISTINCT CASE WHEN NOT is_parallel OR is_parallel IS NULL THEN subject || '_' || grade END) as individual_subjects
    FROM teacher_load
    GROUP BY teacher_name
)
SELECT 
    teacher_name AS "Professeur",
    parallel_hours AS "Heures Parallèles",
    individual_hours AS "Heures Individuelles",
    parallel_hours + individual_hours AS "Total",
    parallel_subjects AS "Matières Parallèles",
    individual_subjects AS "Matières Individuelles"
FROM teacher_summary
WHERE parallel_hours > 0
ORDER BY parallel_hours DESC;

-- 4. CLASSES AVEC LE PLUS DE COURS PARALLÈLES
-- Identifie les classes qui ont beaucoup de cours en parallèle
WITH class_parallel AS (
    SELECT 
        unnest(string_to_array(replace(classes_covered, ' ', ''), ',')) as class_name,
        subject,
        hours_per_teacher as hours
    FROM parallel_teaching_details
)
SELECT 
    class_name AS "Classe",
    COUNT(DISTINCT subject) AS "Nb Matières Parallèles",
    SUM(hours) AS "Total Heures Parallèles",
    STRING_AGG(DISTINCT subject, ', ' ORDER BY subject) AS "Matières"
FROM class_parallel
GROUP BY class_name
ORDER BY COUNT(DISTINCT subject) DESC;

-- 5. DIAGNOSTIC D'UN GROUPE SPÉCIFIQUE
-- Remplacez {group_id} par l'ID du groupe à analyser
/*
SELECT 
    'Groupe Info' as section,
    pg.*
FROM parallel_groups pg
WHERE group_id = {group_id}
UNION ALL
SELECT 
    'Détails Profs' as section,
    ptd.*::text
FROM parallel_teaching_details ptd
WHERE group_id = {group_id}
UNION ALL
SELECT 
    'Contraintes' as section,
    c.*::text
FROM constraints c
WHERE entity_name = 'parallel_group_{group_id}';
*/

-- 6. CONFLITS POTENTIELS DANS L'EMPLOI DU TEMPS
-- Trouve les créneaux où trop de cours parallèles sont programmés
WITH parallel_slots AS (
    SELECT 
        day_of_week,
        period_number,
        COUNT(DISTINCT group_id) as parallel_groups_count,
        COUNT(DISTINCT teacher_name) as teachers_count,
        STRING_AGG(DISTINCT subject_name, ', ') as subjects
    FROM schedule_entries
    WHERE is_parallel_group = TRUE
    GROUP BY day_of_week, period_number
)
SELECT 
    CASE day_of_week
        WHEN 0 THEN 'Dimanche'
        WHEN 1 THEN 'Lundi'
        WHEN 2 THEN 'Mardi'
        WHEN 3 THEN 'Mercredi'
        WHEN 4 THEN 'Jeudi'
        WHEN 5 THEN 'Vendredi'
    END AS "Jour",
    period_number AS "Période",
    parallel_groups_count AS "Groupes Parallèles",
    teachers_count AS "Nb Profs",
    subjects AS "Matières"
FROM parallel_slots
WHERE parallel_groups_count > 2  -- Ajustez selon vos besoins
ORDER BY parallel_groups_count DESC;

-- 7. STATISTIQUES GLOBALES
SELECT 
    'Statistiques Cours Parallèles' as title,
    jsonb_build_object(
        'total_groupes', (SELECT COUNT(*) FROM parallel_groups),
        'total_profs_paralleles', (SELECT COUNT(DISTINCT teacher_name) FROM parallel_teaching_details),
        'total_heures_paralleles', (SELECT SUM(hours_per_teacher) FROM parallel_teaching_details),
        'matieres_paralleles', (SELECT COUNT(DISTINCT subject) FROM parallel_groups),
        'classes_avec_parallele', (
            SELECT COUNT(DISTINCT unnest(string_to_array(replace(classes_covered, ' ', ''), ',')))
            FROM parallel_teaching_details
        )
    ) as stats;

-- 8. TROUVER LES COURS QUI DEVRAIENT ÊTRE PARALLÈLES
-- Identifie les patterns similaires qui ne sont pas encore groupés
WITH potential_parallel AS (
    SELECT 
        subject,
        grade,
        COUNT(DISTINCT teacher_name) as teacher_count,
        STRING_AGG(DISTINCT teacher_name, ', ' ORDER BY teacher_name) as teachers,
        STRING_AGG(DISTINCT class_list, ' | ' ORDER BY class_list) as all_classes,
        ARRAY_AGG(DISTINCT hours ORDER BY hours) as hours_array
    FROM teacher_load
    WHERE class_list LIKE '%,%'
      AND (is_parallel = FALSE OR is_parallel IS NULL)
    GROUP BY subject, grade
    HAVING COUNT(DISTINCT teacher_name) > 1
)
SELECT 
    subject AS "Matière",
    grade AS "Niveau", 
    teacher_count AS "Nb Profs",
    teachers AS "Professeurs",
    hours_array AS "Heures",
    all_classes AS "Classes"
FROM potential_parallel
ORDER BY teacher_count DESC;

-- 9. AUDIT DES MODIFICATIONS
-- Montre les dernières modifications sur les tables parallèles
SELECT 
    'parallel_groups' as table_name,
    group_id as id,
    subject || ' ' || grade as description,
    'N/A' as created_at  -- Ajoutez created_at à vos tables si nécessaire
FROM parallel_groups
ORDER BY group_id DESC
LIMIT 5;

-- 10. RAPPORT COMPLET POUR UN PROFESSEUR
-- Remplacez 'NOM_PROF' par le nom du professeur
/*
WITH prof_data AS (
    SELECT 'NOM_PROF' as prof_name
)
SELECT 
    'Cours Parallèles' as type,
    pg.subject,
    pg.grade,
    ptd.hours_per_teacher as hours,
    pg.teachers as with_teachers
FROM prof_data pd
JOIN parallel_teaching_details ptd ON ptd.teacher_name = pd.prof_name
JOIN parallel_groups pg ON pg.group_id = ptd.group_id
UNION ALL
SELECT 
    'Cours Individuels' as type,
    subject,
    grade,
    hours,
    'Solo' as with_teachers
FROM prof_data pd
JOIN teacher_load tl ON tl.teacher_name = pd.prof_name
WHERE is_parallel = FALSE OR is_parallel IS NULL
ORDER BY type, grade, subject;
*/

-- 11. VALIDATION AVANT GÉNÉRATION D'EMPLOI DU TEMPS
-- Vérifie que tout est prêt pour la génération
WITH validation_checks AS (
    SELECT 'Groupes sans détails' as check_name,
           COUNT(*) as issues
    FROM parallel_groups pg
    WHERE NOT EXISTS (
        SELECT 1 FROM parallel_teaching_details ptd 
        WHERE ptd.group_id = pg.group_id
    )
    
    UNION ALL
    
    SELECT 'Profs inexistants dans les groupes',
           COUNT(DISTINCT ptd.teacher_name)
    FROM parallel_teaching_details ptd
    WHERE NOT EXISTS (
        SELECT 1 FROM teachers t 
        WHERE t.teacher_name = ptd.teacher_name
    )
    
    UNION ALL
    
    SELECT 'Contraintes manquantes pour groupes',
           COUNT(*)
    FROM parallel_groups pg
    WHERE NOT EXISTS (
        SELECT 1 FROM constraints c 
        WHERE c.entity_name = 'parallel_group_' || pg.group_id
    )
)
SELECT * FROM validation_checks
WHERE issues > 0;

-- 12. EXPORT POUR DOCUMENTATION
-- Génère un rapport formaté des groupes parallèles
SELECT 
    '### ' || pg.subject || ' - Niveau ' || pg.grade AS markdown_title,
    E'\n**Professeurs:** ' || pg.teachers ||
    E'\n**Heures:** ' || MAX(ptd.hours_per_teacher) || 'h par professeur' ||
    E'\n**Classes:** ' || STRING_AGG(DISTINCT ptd.classes_covered, ', ') ||
    E'\n' AS details
FROM parallel_groups pg
JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers
ORDER BY pg.grade, pg.subject;
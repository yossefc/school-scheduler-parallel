-- fix_parallel_data.sql - Correction des données pour résoudre les problèmes identifiés
-- Exécuter ce script AVANT de lancer le solver

BEGIN;

-- ================================================================
-- 1. VÉRIFICATION ET CORRECTION DES VALEURS is_parallel
-- ================================================================

-- Afficher les statistiques actuelles
SELECT 
    'Avant correction' as phase,
    COUNT(*) as total_loads,
    COUNT(*) FILTER (WHERE is_parallel = TRUE) as parallel_true,
    COUNT(*) FILTER (WHERE is_parallel = FALSE) as parallel_false,
    COUNT(*) FILTER (WHERE is_parallel IS NULL) as parallel_null
FROM teacher_load;

-- Corriger les NULL en FALSE pour les cours individuels
UPDATE teacher_load
SET is_parallel = FALSE
WHERE is_parallel IS NULL
  AND (class_list IS NULL OR class_list NOT LIKE '%,%');

-- S'assurer que tous les cours multi-classes sont marqués parallèles
UPDATE teacher_load
SET is_parallel = TRUE
WHERE class_list LIKE '%,%'
  AND (is_parallel = FALSE OR is_parallel IS NULL);

-- Marquer comme parallèles tous les cours référencés dans parallel_teaching_details
UPDATE teacher_load tl
SET is_parallel = TRUE
FROM parallel_teaching_details ptd
WHERE tl.teacher_name = ptd.teacher_name
  AND tl.subject = ptd.subject
  AND tl.grade = ptd.grade;

-- Afficher les statistiques après correction
SELECT 
    'Après correction' as phase,
    COUNT(*) as total_loads,
    COUNT(*) FILTER (WHERE is_parallel = TRUE) as parallel_true,
    COUNT(*) FILTER (WHERE is_parallel = FALSE) as parallel_false,
    COUNT(*) FILTER (WHERE is_parallel IS NULL) as parallel_null
FROM teacher_load;

-- ================================================================
-- 2. ANALYSE DE FAISABILITÉ
-- ================================================================

-- Calculer les besoins réels en créneaux
WITH schedule_needs AS (
    -- Heures individuelles (non parallèles)
    SELECT 
        'Individual' as type,
        SUM(hours) as total_hours
    FROM teacher_load
    WHERE is_parallel IS DISTINCT FROM TRUE
    
    UNION ALL
    
    -- Heures parallèles (compter une seule fois par groupe)
    SELECT 
        'Parallel' as type,
        SUM(hours_per_teacher) as total_hours
    FROM (
        SELECT DISTINCT ON (group_id) 
            group_id,
            hours_per_teacher
        FROM parallel_teaching_details
    ) as unique_groups
),
available_resources AS (
    SELECT 
        COUNT(DISTINCT class_name) as num_classes,
        COUNT(*) as num_slots
    FROM classes, time_slots
    WHERE time_slots.is_break = FALSE
)
SELECT 
    'ANALYSE DE FAISABILITÉ' as title,
    (SELECT SUM(total_hours) FROM schedule_needs) as total_hours_needed,
    (SELECT num_classes * num_slots FROM available_resources) as total_slots_available,
    ROUND((SELECT SUM(total_hours) FROM schedule_needs)::numeric / 
          (SELECT num_classes * num_slots FROM available_resources)::numeric, 2) as utilization_ratio,
    CASE 
        WHEN (SELECT SUM(total_hours) FROM schedule_needs) > 
             (SELECT num_classes * num_slots FROM available_resources)
        THEN 'IMPOSSIBLE - Trop d''heures pour les créneaux disponibles'
        WHEN (SELECT SUM(total_hours) FROM schedule_needs)::numeric / 
             (SELECT num_classes * num_slots FROM available_resources)::numeric > 0.9
        THEN 'DIFFICILE - Utilisation > 90%'
        ELSE 'FAISABLE'
    END as feasibility;

-- Détail par type
SELECT * FROM (
    SELECT 
        'Heures individuelles' as category,
        SUM(hours) as hours
    FROM teacher_load
    WHERE is_parallel IS DISTINCT FROM TRUE
    
    UNION ALL
    
    SELECT 
        'Créneaux parallèles' as category,
        SUM(hours_per_teacher) as hours
    FROM (
        SELECT DISTINCT ON (group_id) group_id, hours_per_teacher
        FROM parallel_teaching_details
    ) as x
    
    UNION ALL
    
    SELECT 
        'Créneaux disponibles' as category,
        COUNT(DISTINCT c.class_name) * COUNT(DISTINCT t.slot_id) as hours
    FROM classes c, time_slots t
    WHERE t.is_break = FALSE
) as summary
ORDER BY category;

-- ================================================================
-- 3. IDENTIFICATION DES PROBLÈMES POTENTIELS
-- ================================================================

-- Classes surchargées (plus de 40h/semaine)
WITH class_load AS (
    SELECT 
        unnest(string_to_array(class_list, ',')) as class_name,
        SUM(hours) as total_hours
    FROM teacher_load
    WHERE class_list IS NOT NULL
      AND is_parallel IS DISTINCT FROM TRUE
    GROUP BY 1
)
SELECT 
    'Classes surchargées (>40h)' as issue,
    class_name,
    total_hours
FROM class_load
WHERE total_hours > 40
ORDER BY total_hours DESC;

-- Professeurs surchargés
SELECT 
    'Professeurs surchargés (>25h)' as issue,
    teacher_name,
    SUM(hours) as total_hours
FROM teacher_load
WHERE is_parallel IS DISTINCT FROM TRUE
GROUP BY teacher_name
HAVING SUM(hours) > 25
ORDER BY total_hours DESC;

-- ================================================================
-- 4. OPTIMISATIONS SUGGÉRÉES
-- ================================================================

-- Identifier les opportunités de cours parallèles non exploitées
WITH parallel_opportunities AS (
    SELECT 
        subject,
        grade,
        COUNT(DISTINCT teacher_name) as teacher_count,
        STRING_AGG(DISTINCT teacher_name, ', ') as teachers,
        SUM(hours) as total_hours,
        COUNT(DISTINCT class_list) as unique_class_lists
    FROM teacher_load
    WHERE is_parallel IS DISTINCT FROM TRUE
      AND class_list IS NOT NULL
    GROUP BY subject, grade
    HAVING COUNT(DISTINCT teacher_name) > 1
       AND COUNT(DISTINCT class_list) >= COUNT(DISTINCT teacher_name)
)
SELECT 
    'Opportunité parallèle' as suggestion,
    subject || ' ' || grade as course,
    teacher_count || ' profs: ' || teachers as details,
    'Économie potentielle: ' || (total_hours - MAX(total_hours/teacher_count)) || ' créneaux' as benefit
FROM parallel_opportunities
ORDER BY (total_hours - MAX(total_hours/teacher_count)) DESC;

-- ================================================================
-- 5. CORRECTIONS AUTOMATIQUES (OPTIONNEL)
-- ================================================================

-- Supprimer les doublons dans teacher_load si nécessaire
-- (Décommenter si vous voulez exécuter)
/*
DELETE FROM teacher_load a
USING teacher_load b
WHERE a.load_id > b.load_id
  AND a.teacher_name = b.teacher_name
  AND a.subject = b.subject
  AND a.grade = b.grade
  AND a.class_list = b.class_list;
*/

-- Créer les contraintes manquantes pour le vendredi court
INSERT INTO constraints (constraint_type, priority, entity_type, entity_name, constraint_data)
SELECT 
    'friday_early_end',
    1,
    'school',
    'global',
    '{"last_period": 6, "description": "Vendredi se termine à 13h"}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM constraints 
    WHERE constraint_type = 'friday_early_end'
);

COMMIT;

-- ================================================================
-- RÉSUMÉ FINAL
-- ================================================================
SELECT 
    'RÉSUMÉ POST-CORRECTION' as title,
    jsonb_build_object(
        'total_professeurs', (SELECT COUNT(DISTINCT teacher_name) FROM teachers),
        'total_classes', (SELECT COUNT(*) FROM classes),
        'total_charges', (SELECT COUNT(*) FROM teacher_load),
        'charges_paralleles', (SELECT COUNT(*) FROM teacher_load WHERE is_parallel = TRUE),
        'charges_individuelles', (SELECT COUNT(*) FROM teacher_load WHERE is_parallel IS DISTINCT FROM TRUE),
        'groupes_paralleles', (SELECT COUNT(*) FROM parallel_groups),
        'heures_totales_individuelles', (SELECT SUM(hours) FROM teacher_load WHERE is_parallel IS DISTINCT FROM TRUE),
        'creneaux_paralleles', (SELECT SUM(hours_per_teacher) FROM (SELECT DISTINCT ON (group_id) group_id, hours_per_teacher FROM parallel_teaching_details) x),
        'creneaux_disponibles', (SELECT COUNT(DISTINCT c.class_name) * COUNT(DISTINCT t.slot_id) FROM classes c, time_slots t WHERE t.is_break = FALSE)
    ) as stats;
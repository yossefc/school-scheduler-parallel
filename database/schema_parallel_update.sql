-- ================================================================
-- schema_parallel_update.sql - Mise à jour pour gérer correctement
-- l'enseignement parallèle dans le système scolaire israélien
-- ================================================================

BEGIN;

-- 1. Ajouter la colonne group_id à schedule_entries si elle n'existe pas
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'schedule_entries' 
        AND column_name = 'group_id'
    ) THEN
        ALTER TABLE schedule_entries 
        ADD COLUMN group_id INTEGER;
    END IF;
END$$;

-- 2. Créer la table parallel_teaching_details si elle n'existe pas
CREATE TABLE IF NOT EXISTS parallel_teaching_details (
    detail_id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES parallel_groups(group_id),
    teacher_name VARCHAR(100),
    subject VARCHAR(100),
    grade VARCHAR(10),
    hours_per_teacher INTEGER,
    classes_covered TEXT,
    simultaneous_slots INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_teacher_load_parallel 
ON teacher_load(is_parallel) 
WHERE is_parallel = TRUE;

CREATE INDEX IF NOT EXISTS idx_parallel_details_group 
ON parallel_teaching_details(group_id);

CREATE INDEX IF NOT EXISTS idx_schedule_entries_group 
ON schedule_entries(group_id) 
WHERE group_id IS NOT NULL;

-- 4. Vue pour visualiser facilement les cours parallèles
CREATE OR REPLACE VIEW v_parallel_schedule AS
SELECT 
    se.schedule_id,
    se.day_of_week,
    se.period_number,
    se.group_id,
    se.subject_name,
    STRING_AGG(DISTINCT se.teacher_name, ' + ' ORDER BY se.teacher_name) as teachers,
    STRING_AGG(DISTINCT se.class_name, ', ' ORDER BY se.class_name) as classes,
    COUNT(DISTINCT se.class_name) as class_count,
    bool_or(se.is_parallel_group) as is_parallel
FROM schedule_entries se
WHERE se.group_id IS NOT NULL
GROUP BY 
    se.schedule_id,
    se.day_of_week,
    se.period_number,
    se.group_id,
    se.subject_name
ORDER BY 
    se.day_of_week,
    se.period_number;

-- 5. Vue pour analyser la charge des professeurs incluant les cours parallèles
CREATE OR REPLACE VIEW v_teacher_workload AS
WITH regular_hours AS (
    -- Heures des cours individuels
    SELECT 
        teacher_name,
        COUNT(*) as teaching_hours,
        0 as parallel_hours
    FROM schedule_entries
    WHERE is_parallel_group = FALSE OR is_parallel_group IS NULL
    GROUP BY teacher_name
),
parallel_hours AS (
    -- Heures des cours parallèles
    SELECT 
        teacher_name,
        0 as teaching_hours,
        COUNT(DISTINCT (day_of_week, period_number, group_id)) as parallel_hours
    FROM schedule_entries
    WHERE is_parallel_group = TRUE
    GROUP BY teacher_name
)
SELECT 
    COALESCE(r.teacher_name, p.teacher_name) as teacher_name,
    COALESCE(r.teaching_hours, 0) as regular_hours,
    COALESCE(p.parallel_hours, 0) as parallel_hours,
    COALESCE(r.teaching_hours, 0) + COALESCE(p.parallel_hours, 0) as total_hours
FROM regular_hours r
FULL OUTER JOIN parallel_hours p ON r.teacher_name = p.teacher_name
ORDER BY total_hours DESC;

-- 6. Fonction pour vérifier la cohérence des cours parallèles
CREATE OR REPLACE FUNCTION check_parallel_consistency()
RETURNS TABLE (
    issue_type TEXT,
    details TEXT
) AS $$
BEGIN
    -- Vérifier que tous les profs d'un groupe parallèle ont le même nombre d'heures
    RETURN QUERY
    SELECT 
        'Incohérence heures parallèles'::TEXT,
        'Groupe ' || group_id || ': ' || 
        STRING_AGG(teacher_name || ' (' || hours_per_teacher || 'h)', ', ')::TEXT
    FROM parallel_teaching_details
    GROUP BY group_id
    HAVING COUNT(DISTINCT hours_per_teacher) > 1;
    
    -- Vérifier que les classes ne sont pas assignées à plusieurs groupes parallèles pour la même matière
    RETURN QUERY
    WITH class_conflicts AS (
        SELECT 
            unnest(string_to_array(classes_covered, ',')) as class_name,
            subject,
            grade,
            COUNT(DISTINCT group_id) as group_count
        FROM parallel_teaching_details
        GROUP BY 1, 2, 3
        HAVING COUNT(DISTINCT group_id) > 1
    )
    SELECT 
        'Classe dans plusieurs groupes'::TEXT,
        class_name || ' apparaît dans ' || group_count || 
        ' groupes pour ' || subject || ' niveau ' || grade::TEXT
    FROM class_conflicts;
END;
$$ LANGUAGE plpgsql;

-- 7. Trigger pour valider l'insertion dans parallel_teaching_details
CREATE OR REPLACE FUNCTION validate_parallel_teaching()
RETURNS TRIGGER AS $$
BEGIN
    -- Vérifier que le professeur existe
    IF NOT EXISTS (
        SELECT 1 FROM teachers 
        WHERE teacher_name = NEW.teacher_name
    ) THEN
        RAISE EXCEPTION 'Professeur % non trouvé dans la table teachers', NEW.teacher_name;
    END IF;
    
    -- Vérifier que les heures sont positives
    IF NEW.hours_per_teacher <= 0 THEN
        RAISE EXCEPTION 'Le nombre d''heures doit être positif';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_parallel_teaching ON parallel_teaching_details;
CREATE TRIGGER trg_validate_parallel_teaching
BEFORE INSERT OR UPDATE ON parallel_teaching_details
FOR EACH ROW
EXECUTE FUNCTION validate_parallel_teaching();

-- 8. Statistiques utiles
CREATE OR REPLACE VIEW v_parallel_statistics AS
SELECT 
    'Total groupes parallèles' as metric,
    COUNT(DISTINCT group_id)::TEXT as value
FROM parallel_groups
UNION ALL
SELECT 
    'Total professeurs en parallèle',
    COUNT(DISTINCT teacher_name)::TEXT
FROM parallel_teaching_details
UNION ALL
SELECT 
    'Total heures parallèles planifiées',
    SUM(hours_per_teacher)::TEXT
FROM parallel_teaching_details
UNION ALL
SELECT 
    'Classes avec cours parallèles',
    (SELECT COUNT(DISTINCT class_name) 
     FROM (SELECT unnest(string_to_array(classes_covered, ',')) as class_name 
           FROM parallel_teaching_details) as classes)::TEXT;

COMMIT;
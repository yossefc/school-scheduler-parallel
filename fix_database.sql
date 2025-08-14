-- fix_database.sql - Corrections des problèmes de données

-- 1. CORRIGER LE DOUBLON (jour 0, période 1)
DELETE FROM time_slots 
WHERE slot_id IN (
    SELECT slot_id FROM (
        SELECT slot_id,
               ROW_NUMBER() OVER (PARTITION BY day_of_week, period_number 
                                 ORDER BY slot_id) AS rn
        FROM time_slots
        WHERE day_of_week = 0 AND period_number = 1
    ) t
    WHERE rn > 1
);

-- 2. MARQUER LE VENDREDI APRÈS-MIDI COMME NON DISPONIBLE
UPDATE time_slots 
SET is_active = FALSE,
    is_break = TRUE
WHERE day_of_week = 5 
  AND period_number >= 5;  -- Après 13h (périodes 5-11)

-- 3. VÉRIFIER LA STRUCTURE DE solver_input
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'solver_input'
ORDER BY ordinal_position;

-- 4. AJOUTER work_days SI MANQUANT
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'solver_input' AND column_name = 'work_days'
    ) THEN
        ALTER TABLE solver_input 
        ADD COLUMN work_days VARCHAR(50) DEFAULT '0,1,2,3,4,5';
    END IF;
END $$;

-- 5. CRÉER UNE VUE CORRIGÉE DES CRÉNEAUX DISPONIBLES
DROP VIEW IF EXISTS v_available_slots CASCADE;
CREATE VIEW v_available_slots AS
SELECT 
    slot_id,
    day_of_week,
    period_number,
    start_time,
    end_time,
    CASE 
        WHEN day_of_week = 5 AND period_number >= 5 THEN FALSE  -- Vendredi PM
        WHEN day_of_week = 1 AND period_number BETWEEN 4 AND 7 THEN FALSE  -- Lundi réunions
        ELSE TRUE
    END AS available_for_teaching
FROM time_slots
WHERE is_active = TRUE 
  AND is_break = FALSE;

-- 6. STATISTIQUES APRÈS CORRECTION
SELECT 
    'Total slots' AS metric,
    COUNT(*) AS value
FROM v_available_slots
WHERE available_for_teaching
UNION ALL
SELECT 
    'Friday morning slots',
    COUNT(*)
FROM v_available_slots
WHERE day_of_week = 5 AND available_for_teaching
UNION ALL
SELECT 
    'Monday available',
    COUNT(*)
FROM v_available_slots
WHERE day_of_week = 1 AND available_for_teaching;

-- 7. VÉRIFIER L'ÉQUILIBRE PAR JOUR
SELECT 
    day_of_week,
    COUNT(*) AS available_periods,
    STRING_AGG(period_number::text, ',' ORDER BY period_number) AS periods
FROM v_available_slots
WHERE available_for_teaching
GROUP BY day_of_week
ORDER
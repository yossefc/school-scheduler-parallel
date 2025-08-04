-- ================================================================
-- SCRIPT DE NETTOYAGE COMPLET DES CONTRAINTES
-- ================================================================

BEGIN;

-- 1. BACKUP avant suppression (optionnel)
CREATE TABLE IF NOT EXISTS constraints_backup AS 
SELECT *, NOW() as backup_date FROM constraints WHERE is_active = true;

CREATE TABLE IF NOT EXISTS institutional_constraints_backup AS 
SELECT *, NOW() as backup_date FROM institutional_constraints WHERE is_active = true;

-- 2. DÉSACTIVER toutes les contraintes (plus sûr que supprimer)
UPDATE constraints SET is_active = false;
UPDATE institutional_constraints SET is_active = false;

-- 3. Optionnel: SUPPRIMER complètement (décommenter si souhaité)
/*
DELETE FROM constraints;
DELETE FROM institutional_constraint_entities;
DELETE FROM institutional_constraints;
*/

-- 4. GARDER seulement les contraintes système critiques
INSERT INTO institutional_constraints 
(name, type, priority, entity, data, description, is_active, applicable_days) 
VALUES 
(
    'Horaires d''ouverture école',
    'school_hours',
    0,
    'school',
    '{"start": "08:00", "end": "18:00", "mandatory": true}',
    'École ouverte de 8h à 18h - NON MODIFIABLE',
    true,
    ARRAY[0,1,2,3,4,5]
),
(
    'Vendredi écourté',
    'friday_short',
    0,
    'all',
    '{"end_time": "13:00", "last_period": 6}',
    'Vendredi se termine à 13h - NON MODIFIABLE',
    true,
    ARRAY[5]
)
ON CONFLICT (name) DO UPDATE SET
    is_active = true,
    data = EXCLUDED.data;

-- 5. STATISTIQUES finales
SELECT 
    'CONTRAINTES ACTIVES APRÈS NETTOYAGE' as info,
    COUNT(*) as total_institutional
FROM institutional_constraints WHERE is_active = true;

SELECT 
    'CONTRAINTES UTILISATEUR ACTIVES' as info,
    COUNT(*) as total_user
FROM constraints WHERE is_active = true;

COMMIT;

-- Afficher le résumé
SELECT '=== NETTOYAGE TERMINÉ ===' as status;
SELECT 
    'Contraintes institutionnelles actives: ' || COUNT(*) as result
FROM institutional_constraints WHERE is_active = true;

SELECT 
    'Contraintes utilisateur actives: ' || COUNT(*) as result  
FROM constraints WHERE is_active = true;
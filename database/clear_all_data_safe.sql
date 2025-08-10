-- ================================================================
-- SCRIPT DE NETTOYAGE SÉCURISÉ DES DONNÉES
-- ================================================================
-- Ce script vide toutes les tables existantes de manière sécurisée

-- Désactiver temporairement les contraintes de clés étrangères
SET session_replication_role = replica;

-- Vider les tables principales (seulement si elles existent)
DO $$
DECLARE
    table_name text;
    sql_command text;
BEGIN
    -- Liste des tables à vider
    FOR table_name IN 
        SELECT t.table_name 
        FROM information_schema.tables t
        WHERE t.table_schema = 'public' 
          AND t.table_type = 'BASE TABLE'
          AND t.table_name NOT LIKE '%backup%'
          AND t.table_name NOT IN ('alembic_version', 'migration_history')
    LOOP
        sql_command := 'TRUNCATE TABLE ' || table_name || ' CASCADE';
        EXECUTE sql_command;
        RAISE NOTICE 'Table % vidée', table_name;
    END LOOP;
END $$;

-- Réactiver les contraintes de clés étrangères
SET session_replication_role = DEFAULT;

-- Remettre à zéro les séquences qui existent
DO $$
DECLARE
    seq_name text;
    sql_command text;
BEGIN
    -- Remettre à zéro toutes les séquences
    FOR seq_name IN 
        SELECT sequence_name 
        FROM information_schema.sequences 
        WHERE sequence_schema = 'public'
    LOOP
        sql_command := 'ALTER SEQUENCE ' || seq_name || ' RESTART WITH 1';
        EXECUTE sql_command;
        RAISE NOTICE 'Séquence % réinitialisée', seq_name;
    END LOOP;
END $$;

-- Vérifier le résultat
SELECT 
    table_name,
    (
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_name = t.table_name 
        AND table_schema = 'public'
    ) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
  AND table_name NOT LIKE '%backup%'
ORDER BY table_name;

SELECT '=== NETTOYAGE SÉCURISÉ TERMINÉ ===' as message;
SELECT 'Toutes les tables principales ont été vidées' as status;
SELECT 'Les séquences ont été réinitialisées' as info;

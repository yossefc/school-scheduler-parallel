-- ================================================================
-- SCRIPT DE NETTOYAGE COMPLET DES DONNÉES
-- ================================================================
-- Ce script vide toutes les tables tout en conservant la structure

BEGIN;

-- Désactiver temporairement les contraintes de clés étrangères
SET session_replication_role = replica;

-- Vider toutes les tables principales (dans l'ordre pour éviter les conflits de FK)
TRUNCATE TABLE schedule_entries CASCADE;
TRUNCATE TABLE schedules CASCADE;
TRUNCATE TABLE schedule_generations CASCADE;
TRUNCATE TABLE parallel_teaching_details CASCADE;
TRUNCATE TABLE parallel_groups CASCADE;
TRUNCATE TABLE constraints CASCADE;
TRUNCATE TABLE solver_input CASCADE;
TRUNCATE TABLE teacher_load CASCADE;
TRUNCATE TABLE time_slots CASCADE;
TRUNCATE TABLE classes CASCADE;
TRUNCATE TABLE subjects CASCADE;
TRUNCATE TABLE teachers CASCADE;

-- Réactiver les contraintes de clés étrangères
SET session_replication_role = DEFAULT;

-- Remettre à zéro les séquences auto-increment
ALTER SEQUENCE teachers_teacher_id_seq RESTART WITH 1;
ALTER SEQUENCE subjects_subject_id_seq RESTART WITH 1;
ALTER SEQUENCE classes_class_id_seq RESTART WITH 1;
ALTER SEQUENCE time_slots_slot_id_seq RESTART WITH 1;
ALTER SEQUENCE teacher_load_load_id_seq RESTART WITH 1;
ALTER SEQUENCE constraints_constraint_id_seq RESTART WITH 1;
ALTER SEQUENCE parallel_groups_group_id_seq RESTART WITH 1;
ALTER SEQUENCE parallel_teaching_details_detail_id_seq RESTART WITH 1;
ALTER SEQUENCE solver_input_course_id_seq RESTART WITH 1;
ALTER SEQUENCE schedules_schedule_id_seq RESTART WITH 1;
ALTER SEQUENCE schedule_entries_entry_id_seq RESTART WITH 1;
ALTER SEQUENCE schedule_generations_id_seq RESTART WITH 1;

COMMIT;

-- Afficher le résultat
SELECT 
    'Table' as type,
    schemaname as schema,
    tablename as name,
    n_tup_ins as insertions,
    n_tup_upd as updates,
    n_tup_del as deletions
FROM pg_stat_user_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

-- Vérifier que toutes les tables sont vides
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.tables t2 WHERE t2.table_name = t.table_name) as row_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT '=== NETTOYAGE TERMINÉ ===' as message;
SELECT 'Toutes les données ont été supprimées' as status;
SELECT 'Les tables et séquences ont été réinitialisées' as info;

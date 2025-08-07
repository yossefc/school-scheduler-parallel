-- ================================================================
-- FIX_CONSTRAINT_DUPLICATION.SQL
-- Correction définitive du problème de duplication des contraintes
-- ================================================================

BEGIN;

-- ================================================================
-- PARTIE 1 : NETTOYAGE DES DOUBLONS EXISTANTS
-- ================================================================

-- 1.1 Créer une sauvegarde avant nettoyage
CREATE TABLE IF NOT EXISTS constraints_backup_before_cleanup AS 
SELECT *, NOW() as backup_date 
FROM constraints;

-- 1.2 Identifier et supprimer les doublons de contraintes
WITH duplicates AS (
    SELECT 
        constraint_id,
        ROW_NUMBER() OVER (
            PARTITION BY 
                constraint_type, 
                entity_type, 
                entity_name, 
                constraint_data::text
            ORDER BY constraint_id ASC
        ) as rn
    FROM constraints
)
DELETE FROM constraints 
WHERE constraint_id IN (
    SELECT constraint_id 
    FROM duplicates 
    WHERE rn > 1
);

-- 1.3 Afficher le résultat du nettoyage
DO $$
DECLARE
    deleted_count INTEGER;
    remaining_count INTEGER;
BEGIN
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    SELECT COUNT(*) INTO remaining_count FROM constraints;
    RAISE NOTICE 'Contraintes supprimées: %, Contraintes restantes: %', deleted_count, remaining_count;
END $$;

-- ================================================================
-- PARTIE 2 : AJOUT DE CONTRAINTES UNIQUES
-- ================================================================

-- 2.1 Créer un index unique pour éviter les doublons futurs
-- (On ne peut pas faire une contrainte unique sur JSONB, donc on utilise un index)
CREATE UNIQUE INDEX IF NOT EXISTS idx_constraints_unique 
ON constraints (
    constraint_type, 
    entity_type, 
    entity_name, 
    MD5(constraint_data::text)
);

-- ================================================================
-- PARTIE 3 : MODIFIER LES SCRIPTS D'INSERTION
-- ================================================================

-- 3.1 Créer une fonction pour insérer les contraintes de manière sécurisée
CREATE OR REPLACE FUNCTION safe_insert_constraint(
    p_constraint_type VARCHAR,
    p_priority INTEGER,
    p_entity_type VARCHAR,
    p_entity_name VARCHAR,
    p_constraint_data JSONB,
    p_is_active BOOLEAN DEFAULT TRUE
) RETURNS INTEGER AS $$
DECLARE
    v_constraint_id INTEGER;
BEGIN
    -- Vérifier si la contrainte existe déjà
    SELECT constraint_id INTO v_constraint_id
    FROM constraints
    WHERE constraint_type = p_constraint_type
      AND entity_type = p_entity_type
      AND entity_name = p_entity_name
      AND MD5(constraint_data::text) = MD5(p_constraint_data::text);
    
    -- Si elle n'existe pas, l'insérer
    IF v_constraint_id IS NULL THEN
        INSERT INTO constraints (
            constraint_type, priority, entity_type, 
            entity_name, constraint_data, is_active
        ) VALUES (
            p_constraint_type, p_priority, p_entity_type,
            p_entity_name, p_constraint_data, p_is_active
        ) RETURNING constraint_id INTO v_constraint_id;
        
        RAISE NOTICE 'Nouvelle contrainte créée: ID %', v_constraint_id;
    ELSE
        RAISE NOTICE 'Contrainte existante trouvée: ID %', v_constraint_id;
    END IF;
    
    RETURN v_constraint_id;
END;
$$ LANGUAGE plpgsql;

-- 3.2 Recréer les contraintes de cours parallèles avec protection
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT 
            'parallel_teaching' as ctype,
            1 as priority,
            'group' as etype,
            'parallel_group_' || group_id as ename,
            jsonb_build_object(
                'group_id', group_id,
                'subject', subject,
                'grade', grade,
                'teachers', string_to_array(teachers, ', '),
                'hours', hours,
                'simultaneous', true,
                'description', 'Cours parallèle: ' || teachers || ' enseignent ' || subject || ' niveau ' || grade
            ) as cdata
        FROM v_parallel_teaching
    ) LOOP
        PERFORM safe_insert_constraint(
            r.ctype, r.priority, r.etype, 
            r.ename, r.cdata
        );
    END LOOP;
END $$;

-- ================================================================
-- PARTIE 4 : CORRIGER LE SCRIPT fix_parallel_teaching.sql
-- ================================================================

-- 4.1 Créer une version corrigée du script
CREATE OR REPLACE FUNCTION fix_parallel_teaching_safe() RETURNS VOID AS $$
BEGIN
    -- Vider et reconstruire parallel_groups
    TRUNCATE TABLE parallel_groups CASCADE;
    
    -- Réinsérer les groupes parallèles
    INSERT INTO parallel_groups (subject, grade, teachers, class_lists)
    SELECT 
        subject,
        grade,
        STRING_AGG(DISTINCT teacher_name, ', ' ORDER BY teacher_name),
        STRING_AGG(DISTINCT class_list, ' | ' ORDER BY class_list)
    FROM teacher_load
    WHERE class_list IS NOT NULL
      AND class_list LIKE '%,%'
    GROUP BY subject, grade
    HAVING COUNT(DISTINCT teacher_name) > 1;
    
    -- Remplir parallel_teaching_details
    DELETE FROM parallel_teaching_details;
    
    WITH parallel_info AS (
        SELECT 
            pg.group_id,
            pg.subject,
            pg.grade,
            unnest(string_to_array(pg.teachers, ', ')) as teacher_name
        FROM parallel_groups pg
    )
    INSERT INTO parallel_teaching_details (
        group_id, teacher_name, subject, grade, 
        hours_per_teacher, classes_covered
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
    WHERE tl.class_list LIKE '%,%'
    ON CONFLICT DO NOTHING;  -- Protection contre les doublons
    
    RAISE NOTICE 'Parallel teaching fixed safely without duplicates';
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- PARTIE 5 : AJOUTER DES TRIGGERS POUR PRÉVENIR LES DOUBLONS
-- ================================================================

-- 5.1 Trigger pour vérifier avant insertion
CREATE OR REPLACE FUNCTION check_constraint_duplicate() 
RETURNS TRIGGER AS $$
DECLARE
    existing_count INTEGER;
BEGIN
    -- Vérifier si une contrainte identique existe déjà
    SELECT COUNT(*) INTO existing_count
    FROM constraints
    WHERE constraint_type = NEW.constraint_type
      AND entity_type = NEW.entity_type
      AND entity_name = NEW.entity_name
      AND MD5(constraint_data::text) = MD5(NEW.constraint_data::text)
      AND constraint_id != COALESCE(NEW.constraint_id, -1);
    
    IF existing_count > 0 THEN
        RAISE WARNING 'Contrainte en double détectée et bloquée: % - % - %', 
            NEW.constraint_type, NEW.entity_type, NEW.entity_name;
        RETURN NULL;  -- Empêcher l'insertion
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_constraint_duplicates ON constraints;
CREATE TRIGGER trg_prevent_constraint_duplicates
BEFORE INSERT ON constraints
FOR EACH ROW
EXECUTE FUNCTION check_constraint_duplicate();

-- ================================================================
-- PARTIE 6 : STATISTIQUES ET VÉRIFICATION
-- ================================================================

-- 6.1 Rapport de synthèse
SELECT 'RAPPORT DE NETTOYAGE' as section;

SELECT 
    constraint_type,
    COUNT(*) as nombre,
    COUNT(DISTINCT entity_name) as entites_distinctes
FROM constraints
GROUP BY constraint_type
ORDER BY nombre DESC;

-- 6.2 Vérifier les doublons restants
SELECT 
    'DOUBLONS RESTANTS' as section,
    constraint_type,
    entity_type,
    entity_name,
    COUNT(*) as occurrences
FROM constraints
GROUP BY constraint_type, entity_type, entity_name, MD5(constraint_data::text)
HAVING COUNT(*) > 1;

-- ================================================================
-- PARTIE 7 : SCRIPT DE DÉMARRAGE DOCKER SÉCURISÉ
-- ================================================================

-- Créer une table de contrôle des migrations
CREATE TABLE IF NOT EXISTS migration_history (
    migration_id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(32)
);

-- Fonction pour exécuter les migrations une seule fois
CREATE OR REPLACE FUNCTION run_migration_once(
    p_migration_name VARCHAR,
    p_migration_sql TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_checksum VARCHAR(32);
    v_exists BOOLEAN;
BEGIN
    -- Calculer le checksum du SQL
    v_checksum := MD5(p_migration_sql);
    
    -- Vérifier si la migration a déjà été exécutée
    SELECT EXISTS(
        SELECT 1 FROM migration_history 
        WHERE migration_name = p_migration_name
    ) INTO v_exists;
    
    IF NOT v_exists THEN
        -- Exécuter la migration
        EXECUTE p_migration_sql;
        
        -- Enregistrer dans l'historique
        INSERT INTO migration_history (migration_name, checksum)
        VALUES (p_migration_name, v_checksum);
        
        RAISE NOTICE 'Migration % exécutée avec succès', p_migration_name;
        RETURN TRUE;
    ELSE
        RAISE NOTICE 'Migration % déjà exécutée, ignorée', p_migration_name;
        RETURN FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ================================================================
-- RÉSUMÉ FINAL
-- ================================================================
SELECT 
    '✅ NETTOYAGE TERMINÉ' as status,
    (SELECT COUNT(*) FROM constraints) as total_contraintes,
    (SELECT COUNT(DISTINCT constraint_type) FROM constraints) as types_distincts,
    (SELECT COUNT(*) FROM migration_history) as migrations_executees;
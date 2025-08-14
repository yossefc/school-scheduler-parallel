-- Migration ROLLBACK: Remove subject_name compatibility
-- This script undoes the changes made by fix_subject_name_compatibility.sql

DO $rollback$
BEGIN
    -- Remove subject_name computed column if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = 'solver_input' 
        AND column_name = 'subject_name'
        AND is_generated = 'ALWAYS'  -- Only remove if it's a generated column
    ) THEN
        ALTER TABLE public.solver_input DROP COLUMN subject_name;
        RAISE NOTICE 'Removed subject_name generated column from solver_input';
    END IF;
    
    -- Remove compatibility view if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.views
        WHERE table_schema = 'public' 
        AND table_name = 'v_solver_input_compat'
    ) THEN
        DROP VIEW public.v_solver_input_compat;
        RAISE NOTICE 'Removed v_solver_input_compat view';
    END IF;
    
    RAISE NOTICE 'Rollback completed. Note: subject_name column in schedule_entries was preserved to avoid data loss.';
    
END $rollback$;
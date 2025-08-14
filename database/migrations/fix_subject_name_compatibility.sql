-- Migration: Fix subject_name compatibility issue
-- Issue: Code expects 'subject_name' column but table has 'subject'
-- Solution: Add computed column for backward compatibility

-- Migration UP
DO $migration$
BEGIN
    -- Check if subject_name column already exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = 'solver_input' 
        AND column_name = 'subject_name'
    ) THEN
        -- Add subject_name as computed column (PostgreSQL 12+)
        BEGIN
            ALTER TABLE public.solver_input
            ADD COLUMN subject_name text GENERATED ALWAYS AS (subject) STORED;
            
            RAISE NOTICE 'Added subject_name computed column to solver_input';
            
        EXCEPTION WHEN feature_not_supported THEN
            -- Fallback for older PostgreSQL versions: create view
            RAISE NOTICE 'PostgreSQL version does not support GENERATED columns, creating compatibility view';
            
            CREATE OR REPLACE VIEW public.v_solver_input_compat AS
            SELECT 
                course_id,
                class_list,
                subject,
                subject AS subject_name,  -- Compatibility alias
                hours,
                is_parallel,
                teacher_count,
                course_type,
                grade,
                group_id,
                teacher_names,
                work_days
            FROM public.solver_input;
            
            -- Grant permissions
            GRANT SELECT ON public.v_solver_input_compat TO public;
        END;
    ELSE
        RAISE NOTICE 'subject_name column already exists in solver_input';
    END IF;
    
    -- Ensure schedule_entries has subject_name column (expected by frontend)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = 'schedule_entries' 
        AND column_name = 'subject_name'
    ) THEN
        -- schedule_entries should have subject_name (it's in schema.sql)
        ALTER TABLE public.schedule_entries
        ADD COLUMN IF NOT EXISTS subject_name VARCHAR(100);
        
        RAISE NOTICE 'Added subject_name column to schedule_entries';
    END IF;
    
    -- Update any existing records where subject_name might be null
    -- Note: schedule_entries doesn't have 'subject' column, using a default value
    UPDATE public.schedule_entries 
    SET subject_name = COALESCE(subject_name, 'Unknown')
    WHERE subject_name IS NULL;
    
END $migration$;
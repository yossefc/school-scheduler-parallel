-- Supprimer les tables si elles existent
DROP TABLE IF EXISTS schedule_entries CASCADE;
DROP TABLE IF EXISTS schedules CASCADE;
DROP TABLE IF EXISTS constraints CASCADE;
DROP TABLE IF EXISTS teacher_load CASCADE;
DROP TABLE IF EXISTS parallel_groups CASCADE;
DROP TABLE IF EXISTS time_slots CASCADE;
DROP TABLE IF EXISTS classes CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;

-- Table des professeurs
CREATE TABLE teachers (
    teacher_id SERIAL PRIMARY KEY,
    teacher_name VARCHAR(100) UNIQUE NOT NULL,
    total_hours INTEGER,
    work_days VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des matières
CREATE TABLE subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    subject_code VARCHAR(20) UNIQUE,
    category VARCHAR(50), -- 'general', 'kodesh', 'languages'
    difficulty_level INTEGER DEFAULT 3
);

-- Table des classes
CREATE TABLE classes (
    class_id SERIAL PRIMARY KEY,
    grade INTEGER NOT NULL,
    section VARCHAR(10) NOT NULL,
    class_name VARCHAR(50) UNIQUE NOT NULL,
    student_count INTEGER
);

-- Table des créneaux horaires
CREATE TABLE time_slots (
    slot_id SERIAL PRIMARY KEY,
    day_of_week INTEGER, -- 0=Dimanche, 5=Vendredi
    period_number INTEGER,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_break BOOLEAN DEFAULT FALSE
);

-- Table des charges d'enseignement
CREATE TABLE teacher_load (
    load_id SERIAL PRIMARY KEY,
    teacher_name VARCHAR(100) REFERENCES teachers(teacher_name),
    subject VARCHAR(100),
    grade VARCHAR(10),
    class_list VARCHAR(255),
    hours INTEGER,
    work_days VARCHAR(50)
);

-- Table des groupes parallèles
CREATE TABLE parallel_groups (
    group_id SERIAL PRIMARY KEY,
    subject VARCHAR(100),
    grade VARCHAR(10),
    teachers TEXT,
    class_lists TEXT
);

-- Table des contraintes
CREATE TABLE constraints (
    constraint_id SERIAL PRIMARY KEY,
    constraint_type VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 1,
    entity_type VARCHAR(50),
    entity_name VARCHAR(100),
    constraint_data JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des emplois du temps
CREATE TABLE schedules (
    schedule_id SERIAL PRIMARY KEY,
    academic_year VARCHAR(20),
    term INTEGER,
    version INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des entrées d'emploi du temps
CREATE TABLE schedule_entries (
    entry_id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES schedules(schedule_id),
    teacher_name VARCHAR(100),
    class_name VARCHAR(50),
    subject_name VARCHAR(100),
    day_of_week INTEGER,
    period_number INTEGER,
    is_parallel_group BOOLEAN DEFAULT FALSE,
    group_id INTEGER
);

-- Insérer les créneaux horaires de base
INSERT INTO time_slots (day_of_week, period_number, start_time, end_time, is_break) VALUES
-- Dimanche à Jeudi
(0, 1, '08:00', '08:45', FALSE),
(0, 2, '08:45', '09:30', FALSE),
(0, 3, '09:30', '09:45', TRUE), -- Pause
(0, 4, '09:45', '10:30', FALSE),
(0, 5, '10:30', '11:15', FALSE),
(0, 6, '11:15', '12:00', FALSE),
(0, 7, '12:00', '12:45', TRUE), -- Déjeuner
(0, 8, '12:45', '13:30', FALSE),
(0, 9, '13:30', '14:15', FALSE),
(0, 10, '14:15', '15:00', FALSE),
-- Répéter pour les autres jours
(1, 1, '08:00', '08:45', FALSE),
(1, 2, '08:45', '09:30', FALSE),
-- ... (continuez pour tous les jours)
-- Vendredi (journée courte)
(5, 1, '08:00', '08:45', FALSE),
(5, 2, '08:45', '09:30', FALSE),
(5, 3, '09:30', '09:45', TRUE),
(5, 4, '09:45', '10:30', FALSE),
(5, 5, '10:30', '11:15', FALSE),
(5, 6, '11:15', '12:00', FALSE),
(5, 7, '12:00', '12:45', FALSE);
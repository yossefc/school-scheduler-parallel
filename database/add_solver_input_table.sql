-- Ajout de la table solver_input manquante
-- Cette table est cruciale pour le système mais n'était pas définie dans le schéma

CREATE TABLE IF NOT EXISTS solver_input (
    course_id SERIAL PRIMARY KEY,
    course_type VARCHAR(50) DEFAULT 'regular',
    teacher_name VARCHAR(255),
    teacher_names VARCHAR(500),
    subject VARCHAR(255),
    subject_name VARCHAR(255),
    grade VARCHAR(50),
    class_list VARCHAR(500),
    hours INTEGER NOT NULL,
    is_parallel BOOLEAN DEFAULT FALSE,
    group_id INTEGER,
    subject_id INTEGER REFERENCES subjects(subject_id),
    teacher_count INTEGER DEFAULT 1,
    work_days VARCHAR(50) DEFAULT '0,1,2,3,4,5',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour optimisation des requêtes
CREATE INDEX IF NOT EXISTS idx_solver_input_teacher ON solver_input(teacher_name);
CREATE INDEX IF NOT EXISTS idx_solver_input_subject ON solver_input(subject);
CREATE INDEX IF NOT EXISTS idx_solver_input_parallel ON solver_input(is_parallel);
CREATE INDEX IF NOT EXISTS idx_solver_input_grade ON solver_input(grade);
CREATE INDEX IF NOT EXISTS idx_solver_input_course_type ON solver_input(course_type);

-- Commentaires pour documentation
COMMENT ON TABLE solver_input IS 'Table principale pour les données d''entrée du solveur d''emploi du temps';
COMMENT ON COLUMN solver_input.course_type IS 'Type de cours: regular, individual, parallel_group';
COMMENT ON COLUMN solver_input.teacher_names IS 'Noms des professeurs (séparés par virgules pour groupes parallèles)';
COMMENT ON COLUMN solver_input.class_list IS 'Liste des classes concernées (séparées par virgules)';
COMMENT ON COLUMN solver_input.hours IS 'Nombre d''heures hebdomadaires pour ce cours';
COMMENT ON COLUMN solver_input.is_parallel IS 'Indique si c''est un cours en groupe parallèle';
COMMENT ON COLUMN solver_input.work_days IS 'Jours de travail disponibles (0=Dimanche, 5=Vendredi)';
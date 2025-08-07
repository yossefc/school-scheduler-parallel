#!/bin/bash
# ================================================================
# DOCKER-ENTRYPOINT-FIXED.SH
# Script de démarrage Docker corrigé pour éviter les duplications
# ================================================================

set -e

echo "🚀 Starting Solver Service with duplication protection..."

# Variables d'environnement
DB_HOST=${DB_HOST:-postgres}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-school_scheduler}
DB_USER=${DB_USER:-admin}
DB_PASS=${DB_PASS:-school123}

# Fonction pour exécuter SQL de manière sécurisée
run_sql() {
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "$1" 2>/dev/null
}

run_sql_file() {
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$1" 2>/dev/null
}

# Attendre que PostgreSQL soit prêt
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER > /dev/null 2>&1; do
    echo "   PostgreSQL not ready, waiting..."
    sleep 2
done
echo "✅ PostgreSQL is ready!"

# ================================================================
# ÉTAPE 1 : Créer la table de contrôle des migrations
# ================================================================
echo "📋 Setting up migration control..."

run_sql "
CREATE TABLE IF NOT EXISTS migration_history (
    migration_id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(32)
);"

# ================================================================
# ÉTAPE 2 : Fonction pour exécuter les migrations une seule fois
# ================================================================
check_and_run_migration() {
    local migration_name=$1
    local migration_file=$2
    
    echo "🔍 Checking migration: $migration_name"
    
    # Vérifier si la migration a déjà été exécutée
    result=$(run_sql "SELECT COUNT(*) FROM migration_history WHERE migration_name = '$migration_name';")
    count=$(echo $result | grep -oE '[0-9]+' | tail -1)
    
    if [ "$count" = "0" ]; then
        echo "   ▶️  Running migration: $migration_name"
        
        # Exécuter le fichier SQL
        if run_sql_file "$migration_file"; then
            # Calculer le checksum du fichier
            checksum=$(md5sum "$migration_file" | cut -d' ' -f1)
            
            # Enregistrer dans l'historique
            run_sql "INSERT INTO migration_history (migration_name, checksum) 
                     VALUES ('$migration_name', '$checksum');"
            
            echo "   ✅ Migration completed: $migration_name"
        else
            echo "   ❌ Migration failed: $migration_name"
            exit 1
        fi
    else
        echo "   ⏭️  Migration already executed: $migration_name"
    fi
}

# ================================================================
# ÉTAPE 3 : Appliquer le fix de duplication (une seule fois)
# ================================================================
echo "🔧 Applying duplication fix..."

# Créer le script de fix temporaire
cat > /tmp/fix_duplication.sql << 'EOF'
BEGIN;

-- Supprimer les doublons existants
WITH duplicates AS (
    SELECT 
        constraint_id,
        ROW_NUMBER() OVER (
            PARTITION BY 
                constraint_type, 
                entity_type, 
                entity_name, 
                MD5(constraint_data::text)
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

-- Créer un index unique pour prévenir les futurs doublons
CREATE UNIQUE INDEX IF NOT EXISTS idx_constraints_unique 
ON constraints (
    constraint_type, 
    entity_type, 
    entity_name, 
    MD5(constraint_data::text)
);

COMMIT;
EOF

check_and_run_migration "fix_constraint_duplication_v1" "/tmp/fix_duplication.sql"

# ================================================================
# ÉTAPE 4 : Migrations des contraintes parallèles (avec protection)
# ================================================================
if [ -f "/app/database/fix_parallel_teaching.sql" ]; then
    echo "📚 Processing parallel teaching constraints..."
    
    # Créer une version sécurisée du script
    cat > /tmp/safe_parallel_teaching.sql << 'EOF'
BEGIN;

-- Reconstruire les groupes parallèles
TRUNCATE TABLE parallel_groups CASCADE;

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

-- Remplir les détails (avec protection ON CONFLICT)
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
WHERE tl.class_list LIKE '%,%';

-- Ajouter les contraintes SANS DUPLICATION
DO $$
DECLARE
    r RECORD;
    existing_id INTEGER;
BEGIN
    FOR r IN (
        SELECT 
            pg.group_id,
            pg.subject,
            pg.grade,
            pg.teachers,
            ptd.hours_per_teacher as hours
        FROM parallel_groups pg
        JOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id
        GROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers, ptd.hours_per_teacher
    ) LOOP
        -- Vérifier si la contrainte existe déjà
        SELECT constraint_id INTO existing_id
        FROM constraints
        WHERE constraint_type = 'parallel_teaching'
          AND entity_type = 'group'
          AND entity_name = 'parallel_group_' || r.group_id;
        
        -- Insérer seulement si elle n'existe pas
        IF existing_id IS NULL THEN
            INSERT INTO constraints (
                constraint_type, priority, entity_type, 
                entity_name, constraint_data
            ) VALUES (
                'parallel_teaching',
                1,
                'group',
                'parallel_group_' || r.group_id,
                jsonb_build_object(
                    'group_id', r.group_id,
                    'subject', r.subject,
                    'grade', r.grade,
                    'teachers', string_to_array(r.teachers, ', '),
                    'hours', r.hours,
                    'simultaneous', true
                )
            );
        END IF;
    END LOOP;
END $$;

COMMIT;
EOF
    
    check_and_run_migration "parallel_teaching_constraints_v2" "/tmp/safe_parallel_teaching.sql"
fi

# ================================================================
# ÉTAPE 5 : Autres migrations (si nécessaire)
# ================================================================
for migration_file in /app/database/migrations/*.sql; do
    if [ -f "$migration_file" ]; then
        migration_name=$(basename "$migration_file" .sql)
        check_and_run_migration "$migration_name" "$migration_file"
    fi
done

# ================================================================
# ÉTAPE 6 : Rapport de statut
# ================================================================
echo "📊 Database status report:"

constraint_count=$(run_sql "SELECT COUNT(*) FROM constraints WHERE is_active = true;" | grep -oE '[0-9]+' | tail -1)
parallel_count=$(run_sql "SELECT COUNT(*) FROM constraints WHERE constraint_type = 'parallel_teaching';" | grep -oE '[0-9]+' | tail -1)
migration_count=$(run_sql "SELECT COUNT(*) FROM migration_history;" | grep -oE '[0-9]+' | tail -1)

echo "   📌 Active constraints: $constraint_count"
echo "   🎯 Parallel teaching constraints: $parallel_count"
echo "   ✅ Migrations executed: $migration_count"

# ================================================================
# ÉTAPE 7 : Démarrer l'application
# ================================================================
echo "🚀 Starting Scheduler AI application..."

cd /app

# Déterminer dynamiquement le module à lancer
if [ -f "/app/scheduler_ai/api.py" ]; then
    echo "📦 Using package structure (scheduler_ai.api:app)"
    APP_MODULE="scheduler_ai.api:app"
elif [ -f "/app/api.py" ]; then
    echo "📦 Using flat structure (api:app)"
    APP_MODULE="api:app"
else
    echo "❌ Aucun module API trouvé (ni scheduler_ai/api.py, ni /app/api.py)"
    ls -la /app
    exit 1
fi

exec gunicorn -k eventlet -w 1 "$APP_MODULE" -b 0.0.0.0:${PORT:-5001} --log-level info
#!/bin/bash
set -e

echo "🤖 Starting School Scheduler AI Agent..."

# Attendre que PostgreSQL soit prêt
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h ${DB_HOST:-postgres} -p ${DB_PORT:-5432} -U ${DB_USER:-admin}; do
    sleep 1
done
echo "✅ PostgreSQL is ready!"

# Attendre que Redis soit prêt (si configuré)
if [ ! -z "$REDIS_URL" ]; then
    echo "⏳ Waiting for Redis..."
    REDIS_HOST=$(echo $REDIS_URL | sed -e 's/redis:\/\///' -e 's/:.*$//')
    REDIS_PORT=$(echo $REDIS_URL | sed -e 's/.*://' -e 's/\/.*//')
    while ! nc -z ${REDIS_HOST} ${REDIS_PORT:-6379}; do
        sleep 1
    done
    echo "✅ Redis is ready!"
fi

# Appliquer les migrations Alembic
echo "🔄 Skipping database migrations for now..."
# TODO: Fix alembic configuration
# if [ -f "alembic.ini" ]; then
#     alembic upgrade head
# else
#     echo "⚠️  No alembic.ini found, skipping migrations..."
# fi

# Initialiser les données de base si nécessaire
if [ "$INIT_DATA" = "true" ]; then
    echo "📦 Initializing default data..."
    python -c "
from scheduler_ai.agent import ScheduleAIAgent
from scheduler_ai.utils import init_default_constraints
agent = ScheduleAIAgent({'host': '$DB_HOST', 'database': '$DB_NAME', 'user': '$DB_USER', 'password': '$DB_PASSWORD'})
init_default_constraints(agent)
print('✅ Default constraints initialized')
"
fi

# Vérifier les clés API
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set. GPT-4o features will be disabled."
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set. Claude features will be disabled."
fi

# Créer les répertoires de logs
mkdir -p /logs

# Afficher la configuration
echo "
📋 Configuration:
  - Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}
  - WebSocket Port: 5001
  - Log Level: ${LOG_LEVEL:-INFO}
  - Redis: ${REDIS_URL:-disabled}
  - AI Routing: ${SCHEDULE_AI_ROUTING:-gpt4o_first,claude_fallback}
"

# Démarrer l'application
echo "🚀 Starting Flask SocketIO server..."
exec "$@"
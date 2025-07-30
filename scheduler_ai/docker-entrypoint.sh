#!/bin/bash
set -e

echo "🤖 Starting School Scheduler AI Agent..."

# Attendre PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h ${DB_HOST:-postgres} -p ${DB_PORT:-5432} -U ${DB_USER:-admin}; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready!"

# Attendre Redis si configuré
if [ ! -z "$REDIS_URL" ]; then
    echo "⏳ Waiting for Redis..."
    REDIS_HOST=$(echo $REDIS_URL | sed -e 's|redis://||' -e 's|:.*$||')
    REDIS_PORT=$(echo $REDIS_URL | sed -e 's|.*:||' -e 's|/.*$||')
    while ! nc -z ${REDIS_HOST} ${REDIS_PORT:-6379} 2>/dev/null; do
        echo "Waiting for Redis..."
        sleep 2
    done
    echo "✅ Redis is ready!"
fi

# Créer __init__.py si nécessaire (pour les deux structures)
touch /app/__init__.py 2>/dev/null || true
touch /app/scheduler_ai/__init__.py 2>/dev/null || true

# Afficher la structure pour debug
echo "📁 App structure:"
ls -la /app/
if [ -d "/app/scheduler_ai/" ]; then
    echo "📁 scheduler_ai content:"
    ls -la /app/scheduler_ai/
else
    echo "📁 Files are directly in /app (simplified structure)"
fi

# Vérifier quelle structure on utilise et adapter la commande
if [ -f "/app/scheduler_ai/api.py" ]; then
    echo "📦 Using package structure (scheduler_ai.api:app)"
    APP_MODULE="scheduler_ai.api:app"
elif [ -f "/app/api.py" ]; then
    echo "📦 Using flat structure (api:app)"
    APP_MODULE="api:app"
else
    echo "❌ No api.py found!"
    exit 1
fi

# Skip migrations pour l'instant
echo "⚠️ Skipping migrations (tables already exist)"

# Démarrer avec le bon module détecté
echo "🚀 Starting application with module: $APP_MODULE"
exec gunicorn -k eventlet -w 1 "$APP_MODULE" -b 0.0.0.0:5001 --log-level info
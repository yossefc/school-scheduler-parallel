# 🐳 Guide de Dépannage Docker - Scheduler AI

## 🚨 Problèmes Courants et Solutions

### 1. **Erreur : `dos2unix: not found`**

**Symptôme :**
```bash
/bin/sh: 1: dos2unix: not found
```

**Cause :** L'image `python:3.11-slim` n'inclut pas `dos2unix` par défaut.

**✅ Solution :**
```dockerfile
# Installer dos2unix dans les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl postgresql-client netcat-openbsd dos2unix \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# OU supprimer dos2unix et utiliser sed à la place
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh
```

### 2. **Erreur : `COPY scheduler_ai/requirements.txt ./: not found`**

**Symptôme :**
```bash
COPY failed: file not found in build context
```

**Cause :** Le contexte de build Docker est la racine du projet, pas `scheduler_ai/`.

**✅ Solution :**
```dockerfile
# ✅ Correct - depuis la racine du projet
COPY scheduler_ai/requirements.txt ./

# ❌ Incorrect
COPY requirements.txt ./
```

**Build context :**
```bash
# Depuis la racine du projet
docker build -f scheduler_ai/Dockerfile .
```

### 3. **Erreur : `ModuleNotFoundError: No module named 'scheduler_ai'`**

**Symptôme :**
```bash
ModuleNotFoundError: No module named 'scheduler_ai'
```

**Cause :** Structure Python incorrecte dans le conteneur.

**✅ Solutions :**

#### Option A : Structure Package (Dockerfile principal)
```dockerfile
# Garder l'arborescence package
COPY scheduler_ai/ ./scheduler_ai/
ENV PYTHONPATH=/app
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "scheduler_ai.api:app", "-b", "0.0.0.0:5001"]
```

#### Option B : Structure Plate (Dockerfile.simple)
```dockerfile
# Copier directement dans /app
COPY scheduler_ai/ ./
ENV PYTHONPATH=/app
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "api:app", "-b", "0.0.0.0:5001"]
```

### 4. **Erreur : `chmod: cannot access 'docker-entrypoint.sh': No such file`**

**Symptôme :**
```bash
chmod: cannot access 'docker-entrypoint.sh': No such file or directory
```

**Cause :** Le script est copié après la tentative de modification.

**✅ Solution :**
```dockerfile
# ✅ Correct - copier d'abord, puis modifier
COPY scheduler_ai/docker-entrypoint.sh ./
RUN dos2unix docker-entrypoint.sh && chmod +x docker-entrypoint.sh

# ❌ Incorrect - modifier avant de copier
RUN dos2unix docker-entrypoint.sh && chmod +x docker-entrypoint.sh
COPY scheduler_ai/docker-entrypoint.sh ./
```

## 🔧 Dockerfiles Disponibles

### 1. **Dockerfile** (Structure Package)
```bash
# Build avec structure package complète
docker build -f scheduler_ai/Dockerfile -t scheduler-ai:package .
```

**Avantages :**
- Structure Python propre
- Imports absolus fonctionnent
- Séparation claire du code

### 2. **Dockerfile.simple** (Structure Plate)
```bash
# Build avec structure simplifiée
docker build -f scheduler_ai/Dockerfile.simple -t scheduler-ai:simple .
```

**Avantages :**
- Plus simple à déboguer
- Évite les problèmes d'imports
- Image plus légère

## 🐛 Debug Docker

### Vérifier la Structure du Conteneur
```bash
# Démarrer un conteneur pour inspection
docker run -it scheduler-ai:latest bash

# Vérifier la structure
ls -la /app/
ls -la /app/scheduler_ai/ 2>/dev/null || echo "Structure plate"

# Tester les imports Python
python -c "import api; print('✅ api module OK')"
python -c "import scheduler_ai.api; print('✅ scheduler_ai.api module OK')"
```

### Logs de Démarrage
```bash
# Voir les logs détaillés
docker logs scheduler-ai-container

# Suivre les logs en temps réel
docker logs -f scheduler-ai-container
```

### Variables d'Environnement de Debug
```bash
docker run -e PYTHONPATH=/app -e FLASK_ENV=development scheduler-ai:latest
```

## 🚀 Build & Run Rapide

### Version Package
```bash
cd /path/to/school-scheduler
docker build -f scheduler_ai/Dockerfile -t scheduler-ai:package .
docker run -p 5001:5001 scheduler-ai:package
```

### Version Simple
```bash
cd /path/to/school-scheduler
docker build -f scheduler_ai/Dockerfile.simple -t scheduler-ai:simple .
docker run -p 5001:5001 scheduler-ai:simple
```

### Avec Docker Compose
```bash
# Utiliser le Dockerfile principal
docker-compose up scheduler-ai

# Forcer le rebuild
docker-compose up --build scheduler-ai
```

## 📋 Checklist de Validation

- [ ] Build context = racine du projet
- [ ] `requirements.txt` accessible via `scheduler_ai/requirements.txt`
- [ ] `docker-entrypoint.sh` copié avant `chmod`
- [ ] Structure Python cohérente (package OU plate)
- [ ] `PYTHONPATH` correctement défini
- [ ] CMD utilise le bon module (`scheduler_ai.api:app` OU `api:app`)
- [ ] Ports exposés (5001)
- [ ] Variables d'environnement définies

## 🔗 Ressources

- **Dockerfile principal :** `scheduler_ai/Dockerfile`
- **Dockerfile simplifié :** `scheduler_ai/Dockerfile.simple`
- **Script d'entrée :** `scheduler_ai/docker-entrypoint.sh`
- **Requirements :** `scheduler_ai/requirements.txt` 
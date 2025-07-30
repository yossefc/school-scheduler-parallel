######################## 1 ─ Base image & build args ########################
# - Possibilité de passer le proxy (build) : --build-arg HTTPS_PROXY=http://proxy:3128
# - Eventlet installé pour Socket.IO
############################################################################

ARG PYTHON_VERSION=3.11-slim
FROM python:${PYTHON_VERSION} AS base

# ---------- Crée un utilisateur non-root (meilleure sécurité) --------------
ENV USER=aiuser
RUN useradd -ms /bin/bash ${USER}

# ---------- Build args optionnels (proxy) ----------------------------------
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY}

######################## 2 ─ Dépendances système ###########################
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl postgresql-client netcat-openbsd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

######################## 3 ─ Dépendances Python ############################
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        eventlet                 \
        gunicorn                 \
        psycopg2-binary          \
    && pip cache purge

######################## 4 ─ Code de l’application #########################
COPY . .

# ---------- Droits & format LF pour le script d’entrée --------------------
RUN dos2unix docker-entrypoint.sh || true          \
 && chmod +x docker-entrypoint.sh

######################## 5 ─ Fichiers & permissions ------------------------
RUN mkdir -p /logs /app/data \
 && chown -R ${USER}:${USER} /app /logs /app/data

######################## 6 ─ Variables d’environnement par défaut ##########
ENV FLASK_APP=scheduler_ai/api.py \
    FLASK_ENV=production          \
    PYTHONUNBUFFERED=1            \
    LOG_FILE=/logs/scheduler_ai.log \
    PORT=5001

######################## 7 ─ Exposition du port WebSocket ##################
EXPOSE ${PORT}

######################## 8 ─ Healthcheck ###################################
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

######################## 9 ─ Passage à l’utilisateur non-root ##############
USER ${USER}

########################10 ─ Entrypoint & CMD ###############################
# ENTRYPOINT pointe sur le shell de bootstrap (création DB, wait-for-it, etc.)
ENTRYPOINT ["bash", "/app/docker-entrypoint.sh"]

# CMD : production = gunicorn + eventlet ; développement = flask (géré via script)
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "scheduler_ai.api:app", "-b", "0.0.0.0:5001", "--log-level", "info"]


FROM node:18-alpine

WORKDIR /app

# Copier package.json
COPY package.json ./

# Installer les dépendances
RUN npm install

# Copier le code source
COPY . .

# Exposer le port
EXPOSE 3000

# Variables d'environnement par défaut
ENV REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_AI_SOCKET_URL=http://localhost:5001
ENV WDS_SOCKET_HOST=localhost
ENV WDS_SOCKET_PORT=3001
ENV WDS_SOCKET_PATH=/ws

# Démarrer l'application
CMD ["npm", "start"] 
# frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Copier les fichiers de dépendances
COPY package*.json ./

# Installer les dépendances
RUN npm ci

# Copier le code source
COPY . .

# Build de production
RUN npm run build

# Stage de production
FROM node:18-alpine

WORKDIR /app

# Installer serve globalement
RUN npm install -g serve

# Copier le build depuis le stage builder
COPY --from=builder /app/build ./build

EXPOSE 3000

# Servir l'application
CMD ["serve", "-s", "build", "-l", "3000"]
# 🚀 Guide de Démarrage Rapide - Agent IA

Ce guide vous permet de démarrer l'agent IA en 5 minutes.

## 📋 Prérequis

- Docker Desktop installé et lancé
- Clés API (OpenAI et/ou Anthropic)
- 4GB de RAM disponible

## 🎯 Démarrage en 3 étapes

### 1️⃣ Configuration (1 minute)

```bash
# Cloner le projet
git clone https://github.com/votre-repo/school-scheduler.git
cd school-scheduler

# Copier la configuration
cp .env.example .env

# Éditer .env et ajouter vos clés API
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=claude-...
```

### 2️⃣ Lancement (2 minutes)

**Windows (PowerShell):**
```powershell
.\start-ai-agent.ps1 -Build -Init -Detached
```

**Linux/Mac:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.ai.yml up -d
```

### 3️⃣ Test (2 minutes)

Ouvrez votre navigateur à : http://localhost:3001

Testez avec ces exemples :
- "Le professeur Cohen ne peut pas enseigner le vendredi"
- "Les cours de math doivent être le matin"
- "Maximum 3 heures consécutives pour la classe 9A"

## 🔍 Vérification

```bash
# Vérifier que tout fonctionne
docker ps | grep school

# Voir les logs
docker logs school_ai_agent -f
```

## 🆘 Problèmes courants

### ❌ "Connection refused"
```bash
# Redémarrer les services
docker-compose -f docker-compose.yml -f docker-compose.ai.yml restart
```

### ❌ "Invalid API key"
```bash
# Vérifier votre .env
cat .env | grep API_KEY
```

### ❌ "Out of memory"
Augmentez la mémoire Docker dans Docker Desktop Settings → Resources

## 📚 Prochaines étapes

1. **Lisez la doc complète** : [README_AI_AGENT.md](README_AI_AGENT.md)
2. **Explorez les exemples** : [examples/use_ai_agent.py](examples/use_ai_agent.py)
3. **Personnalisez** : Modifiez les contraintes institutionnelles dans `agent.py`

## 💬 Support

- **Discord** : [Rejoindre le serveur](https://discord.gg/school-scheduler)
- **Issues GitHub** : [Créer une issue](https://github.com/votre-repo/issues)
- **Email** : support@school-scheduler.ai

---

**Bon scheduling ! 🎓**
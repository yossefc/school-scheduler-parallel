# 🤖 Guide de Démarrage Rapide - Agent Conseiller Multilingue

## 🚀 Démarrage en 3 étapes

### 1. Lancer l'Agent
```bash
# Option A: Avec Docker (recommandé)
docker-compose up advisor_agent -d

# Option B: Directement avec Python
cd scheduler_ai
python advisor_api.py
```

### 2. Vérifier que l'Agent fonctionne
```bash
# Test rapide de l'API
curl http://localhost:5002/api/advisor/status

# Ou ouvrir dans le navigateur
http://localhost:5002/api/advisor/examples
```

### 3. Utiliser l'Agent dans l'Interface
- Aller sur **http://localhost:8000/constraints-manager**
- Cliquer sur le bouton **🤖** en bas à droite
- Commencer à taper en hébreu ou français !

---

## 🧪 Tester l'Agent

### Test Automatique Complet
```bash
python test_agent_multilingue.py
```

### Tests Rapides Manuels

#### En Hébreu:
```
תוכל למלא את החורים במערכת השעות של ז-1?
אני רוצה להזיז את המתמטיקה של יא-2 יותר מוקדם ביום
חשוב לי שהמתמטיקה תמיד תהיה בבוקר
```

#### En Français:
```
Peux-tu éliminer les trous dans l'emploi du temps de ז-1 ?
Je voudrais équilibrer la charge des professeurs
Pour moi, les cours de maths doivent toujours être le matin
```

---

## 🔧 Résolution de Problèmes

### L'agent ne répond pas
```bash
# Vérifier si l'agent est démarré
docker-compose ps advisor_agent

# Voir les logs
docker-compose logs -f advisor_agent

# Redémarrer si nécessaire
docker-compose restart advisor_agent
```

### L'agent n'apparaît pas dans constraints-manager
1. Vérifier que l'agent tourne sur le port 5002
2. Rafraîchir la page constraints-manager
3. Vérifier la console JavaScript pour des erreurs

### Base de données non accessible
```bash
# Vérifier PostgreSQL
docker-compose ps postgres

# Tester la connexion
psql -h localhost -U admin -d school_scheduler -p 5432
```

---

## 📖 Exemples d'Usage

### Corrections d'Emploi du Temps
- **Hébreu**: `תוכל לתקן את הקונפליקטים בין השיעורים?`
- **Français**: `Peux-tu corriger les conflits dans l'emploi du temps ?`

### Déplacements de Cours
- **Hébreu**: `אני רוצה להזיז את האנגלית של ח-1 ליום רביעי`
- **Français**: `Je veux déplacer l'anglais de ח-1 au mercredi`

### Préférences Personnelles
- **Hébreu**: `עדיף לי שהמדעים יהיו מקובצים`
- **Français**: `Je préfère que les sciences soient groupées`

### Optimisations Générales
- **Hébreu**: `איך לייעל טוב יותר את מערכת השעות?`
- **Français**: `Comment mieux optimiser l'emploi du temps ?`

---

## 🎯 Fonctionnalités Clés

✅ **Détection automatique de langue** (Hébreu/Français)  
✅ **Extraction d'entités hébraïques** (classes, matières, professeurs)  
✅ **Réponses intelligentes** dans la langue de votre choix  
✅ **Mémorisation des préférences** multilingues  
✅ **Propositions de modifications** avec niveaux de confiance  
✅ **Interface chat intégrée** dans constraints-manager  

---

## 🆘 Support

Si vous rencontrez des problèmes:

1. **Vérifiez les logs**: `docker-compose logs -f advisor_agent`
2. **Testez l'API**: Utilisez le script `test_agent_multilingue.py`
3. **Consultez la documentation**: `AGENT_MULTILINGUE_GUIDE.md`
4. **Vérifiez les services**: Tous les containers doivent être actifs

---

**L'agent est prêt à vous aider en hébreu et en français ! 🇮🇱🇫🇷**
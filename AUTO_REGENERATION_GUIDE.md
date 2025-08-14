# Guide : Régénération Automatique des Contraintes

## 🎯 Vue d'ensemble

Le système de régénération automatique des contraintes permet aux utilisateurs de voir immédiatement les changements dans l'emploi du temps lorsqu'ils ajoutent des contraintes critiques. Fini le besoin de régénérer manuellement !

## ✨ Fonctionnalités

### 1. Détection Automatique des Contraintes Critiques

Le système identifie automatiquement les contraintes qui nécessitent une régénération immédiate :

**Types de contraintes critiques :**
- `teacher_availability` - Disponibilité des professeurs
- `class_schedule` - Horaires de classe
- `parallel_teaching` - Enseignement parallèle
- `room_assignment` - Affectation de salles
- `time_preference` - Préférences horaires importantes
- `friday_short` - Contraintes de vendredi écourté
- `morning_prayer` - Contraintes de prière matinale
- `lunch_break` - Pauses déjeuner
- `subject_timing` - Horaires de matières spécifiques

**Priorités critiques :**
- Priorité 0 : CRITIQUE (régénération automatique)
- Priorité 1 : IMPORTANTE (régénération automatique)
- Priorité 2+ : NORMALE (suggestion de régénération)

**Mots-clés critiques :**
- Français : "indisponible", "trop de trous", "conflit", "parallèle", "urgent", "obligatoire"
- Hébreu : "לא זמין", "לא פנוי", "חובה", "דחוף", "חשוב"

### 2. Processus de Régénération

Lorsqu'une contrainte critique est détectée :

1. **Tentative d'optimisation avancée** (5 min max)
   - Utilise le solver pédagogique
   - Optimise la qualité de l'emploi du temps
   - Retourne un score de qualité

2. **Fallback vers génération standard**
   - Si l'optimisation avancée échoue
   - Génère un emploi du temps basique
   - Plus rapide mais moins optimisé

### 3. Feedback Utilisateur en Temps Réel

**Notifications pour régénération réussie :**
- 📅 Notification verte en haut à droite
- Affiche la méthode utilisée (avancée/standard)
- Score de qualité si disponible
- Bouton pour voir le nouvel emploi du temps

**Suggestions pour contraintes non critiques :**
- 💡 Notification orange en bas à droite
- Bouton "Régénérer maintenant"
- Option "Plus tard" pour ignorer

**Messages d'état détaillés :**
- ✅ Succès avec détails de régénération
- ⚠️ Avertissement si régénération échoue
- 🔄 Indicateur de progression

## 📖 Guide d'utilisation

### Interface Web (Recommandé)

1. **Ouvrir le gestionnaire** : http://localhost:8000/constraints-manager
2. **Ajouter une contrainte critique** :
   - Type : "Disponibilité Prof" ou "Horaire Matière"
   - Priorité : "🔴 HARD - Critique" ou "🟠 Très Forte"
   - Texte : "Le professeur Cohen n'est pas disponible le vendredi"
3. **Observer la régénération automatique** :
   - Message de statut mis à jour
   - Notification de succès
   - Option pour voir le nouvel emploi du temps

### API REST

```bash
# Ajouter une contrainte critique
curl -X POST http://localhost:8000/api/constraints \
  -H "Content-Type: application/json" \
  -d '{
    "constraint_type": "teacher_availability",
    "entity_name": "Cohen David",
    "constraint_data": {
      "unavailable_days": [5],
      "original_text": "Cohen indisponible vendredi"
    },
    "priority": 1,
    "is_active": true
  }'

# Réponse avec régénération automatique
{
  "success": true,
  "constraint_id": 123,
  "auto_regenerated": true,
  "regeneration_details": {
    "success": true,
    "method": "advanced",
    "quality_score": 87.5,
    "schedule_id": 456
  },
  "message": "Contrainte ajoutée et emploi du temps automatiquement régénéré"
}
```

## 🔧 Configuration

### Endpoints concernés

- `POST /api/constraints` - Création avec auto-régénération
- `POST /api/constraints/{id}/toggle` - Activation avec auto-régénération
- `POST /api/advanced/optimize` - Optimisation avancée
- `POST /generate_schedule` - Génération standard

### Paramètres de régénération

```python
regeneration_payload = {
    "time_limit": 300,      # 5 minutes max
    "advanced": True,       # Essayer d'abord l'optimisation avancée
    "minimize_gaps": True,  # Minimiser les trous
    "friday_short": True    # Respecter vendredi écourté
}
```

## 📊 Surveillance et Logs

### Logs importantes

```
INFO - Contrainte critique détectée: teacher_availability
INFO - Déclenchement de la régénération automatique pour contrainte: 123
INFO - Régénération avancée réussie: score 87.5
```

### Métriques

- Taux de réussite de régénération automatique
- Temps moyen de régénération
- Distribution des scores de qualité
- Types de contraintes les plus fréquents

## 🚀 Exemples de Test

### Test complet

```bash
# Exécuter le script de test
python test_auto_constraint_regeneration.py
```

### Tests manuels

1. **Contrainte critique** : "Le professeur Cohen a trop de trous dans son emploi du temps"
2. **Contrainte normale** : "Préférence pour les cours le matin"
3. **Contrainte hébreu** : "המורה לא זמין ביום שישי"

## 🔍 Dépannage

### Régénération n'a pas lieu

**Vérifier :**
- Type de contrainte dans la liste critique ?
- Priorité 0 ou 1 ?
- Mots-clés critiques présents ?
- Serveur solver accessible (port 8000) ?

**Solutions :**
- Ajuster le type de contrainte
- Diminuer la priorité
- Utiliser des mots-clés critiques
- Vérifier les logs du serveur

### Régénération échoue

**Causes possibles :**
- Contraintes incompatibles
- Timeout (>5 minutes)
- Erreur du solver
- Problème de base de données

**Solutions :**
- Simplifier les contraintes
- Utiliser la génération manuelle
- Vérifier les logs d'erreur
- Tester avec le mode debug

### Interface non mise à jour

**Vérifier :**
- JavaScript activé ?
- Console d'erreurs navigateur ?
- Réponse API correcte ?

**Solutions :**
- Actualiser la page
- Vider le cache navigateur
- Vérifier la console développeur

## 📈 Évolutions futures

- **WebSocket en temps réel** pour les notifications
- **Historique des régénérations** automatiques
- **Paramètres utilisateur** pour personnaliser les seuils
- **Prévisualisation** avant régénération
- **Rollback automatique** si qualité dégradée

---

*Guide mis à jour le : 2025-08-13*  
*Version : 1.0*
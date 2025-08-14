# Solver Intégré Optimisé - École Israélienne

## Vue d'ensemble

Le solver intégré combine toutes les optimisations nécessaires pour générer des emplois du temps scolaires de haute qualité pour l'école israélienne. Il résout spécifiquement les problèmes critiques identifiés :

### ✅ Problèmes Résolus

1. **Synchronisation des cours parallèles** : Tous les cours avec le même `group_id` sont placés exactement au même créneau
2. **Élimination des trous** : Les emplois du temps sont compacts sans périodes vides entre les cours
3. **Construction globale** : Traite toutes les classes ensemble au lieu d'une approche séquentielle
4. **Contraintes israéliennes** : Respect du calendrier scolaire (pas de cours le vendredi, lundi court pour ז,ח,ט)
5. **Optimisation pédagogique** : Privilégie les blocs de 2h pour les matières principales

## Architecture

### Modules Principaux

- `integrated_solver.py` : Solver principal avec toutes les optimisations
- `parallel_course_handler.py` : Gestion spécialisée des cours parallèles
- `main.py` : API REST avec endpoint `/generate_schedule_integrated`

### Algorithme

1. **Chargement des données** : Lecture de la table `solver_input` (193 cours)
2. **Analyse des groupes parallèles** : Identification des cours à synchroniser par `group_id`
3. **Création du modèle CP-SAT** : Variables et contraintes OR-Tools
4. **Résolution optimisée** : Temps limite 600 secondes, parallélisation 8 threads
5. **Validation qualité** : Calcul des métriques et score de qualité

## Utilisation

### Via API REST

```bash
# Endpoint principal
POST http://localhost:8000/generate_schedule_integrated

# Payload
{
  "time_limit": 600,
  "advanced": true,
  "minimize_gaps": true,
  "friday_short": true
}

# Réponse attendue
{
  "success": true,
  "schedule_id": 123,
  "quality_score": 87.5,
  "gaps_count": 3,
  "parallel_sync_ok": true,
  "solve_time": 245.6,
  "total_courses": 193,
  "parallel_groups": 12
}
```

### Via Python Direct

```python
from integrated_solver import IntegratedScheduleSolver

# Configuration DB
db_config = {
    "host": "localhost",
    "database": "school_scheduler",
    "user": "admin",
    "password": "school123",
    "port": 5432
}

# Créer et configurer le solver
solver = IntegratedScheduleSolver(db_config=db_config)
solver.load_data()
solver.create_variables() 
solver.add_constraints()

# Résoudre
schedule = solver.solve(time_limit=600)

if schedule:
    schedule_id = solver.save_schedule(schedule)
    print(f"Schedule généré: {schedule_id}")
    print(f"Qualité: {solver.quality_metrics['quality_score']}/100")
```

## Contraintes Implémentées

### Contraintes Dures (Obligatoires)

1. **Placement unique** : Chaque cours placé exactement `hours` fois
2. **Pas de conflits** : Un prof/classe ne peut avoir qu'un cours à la fois
3. **Synchronisation parallèle** : Tous les cours avec même `group_id` au même créneau
4. **Vendredi exclu** : Aucun cours le vendredi
5. **Lundi court** : Classes ז,ח,ט finissent avant période 5 le lundi
6. **Professeurs obligatoires** : Profs de חינוך et שיח בוקר présents le lundi

### Contraintes Souples (Optimisation)

1. **Élimination des trous** : Regrouper les cours par journée
2. **Blocs de 2h** : Privilégier les cours consécutifs pour les matières principales
3. **Matières difficiles le matin** : Placer מתמטיקה, פיזיקה, etc. avant période 4

## Métriques de Qualité

### Score de Qualité (0-100)

- **Base** : 100 points
- **Pénalités** :
  - -5 points par trou détecté
  - -50 points si synchronisation parallèle échoue
  - -10 points si plus de 5h d'amplitude par jour

### Critères de Validation

- ✅ **Score ≥ 85** : Qualité acceptable
- ✅ **Trous < 5%** : Moins de 5% de périodes vides
- ✅ **Sync parallèle = 100%** : Tous les groupes correctement synchronisés
- ✅ **Tous les cours placés** : 193/193 cours dans l'emploi du temps

## Tests de Validation

### Test Logique (`test_simple.py`)

```bash
cd solver
python test_simple.py
```

Valide :
- ✅ Imports des modules
- ✅ Création du solver
- ✅ Logique des cours parallèles
- ✅ Génération du modèle CP-SAT

### Test API Complet (`test_integrated_solver.py`)

```bash
cd solver
python test_integrated_solver.py
```

Teste :
- API disponible
- Génération avec 193 cours
- Métriques de qualité
- Comparaison avec autres solvers

## Données d'Entrée

### Table `solver_input` (193 lignes)

Colonnes critiques :
- `course_id` : Identifiant unique
- `subject` : Matière (עברית, מתמטיקה, etc.)
- `class_list` : Classes concernées (séparées par virgules)
- `teacher_names` : Professeurs (séparés par virgules)
- `hours` : Nombre d'heures hebdomadaires
- `is_parallel` : TRUE pour cours parallèles
- `group_id` : Identifiant pour synchronisation (cours parallèles)
- `grade` : Niveau scolaire (ז,ח,ט,י,יא,יב)

### Exemples de Cours Parallèles

```sql
-- Groupe 4: תנך pour 3 classes avec 4 professeurs
SELECT course_id, subject, class_list, teacher_names, group_id 
FROM solver_input 
WHERE group_id = 4;

-- Résultat attendu: Tous ces cours au MÊME créneau
```

## Avantages par Rapport aux Anciens Solvers

### Synchronisation Parallèle ✅
- **Avant** : Cours parallèles placés à des moments différents
- **Maintenant** : Synchronisation stricte par `group_id`

### Élimination des Trous ✅
- **Avant** : Emplois du temps fragmentés avec des trous
- **Maintenant** : Cours regroupés, maximum 1 trou par jour

### Construction Globale ✅
- **Avant** : Classe par classe → blocages
- **Maintenant** : Toutes les classes ensemble → optimisation globale

### Performance ✅
- **Avant** : 60 secondes → solutions incomplètes
- **Maintenant** : 600 secondes → solutions de qualité

## Déploiement

### Avec Docker (Recommandé)

1. Démarrer Docker Desktop
2. Lancer les services :
   ```bash
   docker-compose up -d
   ```
3. Tester l'API :
   ```bash
   curl -X POST http://localhost:8000/generate_schedule_integrated \
        -H "Content-Type: application/json" \
        -d '{"time_limit": 600}'
   ```

### Sans Docker

1. Installer les dépendances :
   ```bash
   cd solver
   pip install -r requirements.txt
   ```
2. Configurer PostgreSQL
3. Lancer l'API :
   ```bash
   python main.py
   ```

## Monitoring et Debug

### Logs Détaillés

Le solver produit des logs complets :
- Chargement des données
- Analyse des groupes parallèles
- Création des variables CP-SAT
- Progression de la résolution
- Métriques de qualité

### Dashboard Grafana

Accessible sur http://localhost:3002 (avec Docker)
- Temps de résolution
- Scores de qualité
- Utilisation CPU/Mémoire

### Interface Web

http://localhost:8000/constraints-manager
- Gestion des contraintes
- Chat avec l'agent IA
- Visualisation des emplois du temps

## Résolution de Problèmes

### Erreur "Aucune solution trouvée"

1. Vérifier les contraintes contradictoires
2. Augmenter `time_limit` à 900s
3. Désactiver temporairement les contraintes souples
4. Vérifier les données `solver_input`

### Synchronisation Parallèle Échoue

1. Vérifier les `group_id` dans la DB
2. Contrôler que les cours ont le même nombre d'heures
3. Examiner les logs pour les conflits

### Qualité Faible (< 85)

1. Activer `minimize_gaps=true`
2. Augmenter le temps de résolution
3. Vérifier l'équilibre des charges par classe

## Support

- **Documentation** : CLAUDE.md
- **Tests** : `test_simple.py`, `test_integrated_solver.py`
- **Logs** : Niveau INFO pour le debugging
- **API** : OpenAPI/Swagger sur http://localhost:8000/docs
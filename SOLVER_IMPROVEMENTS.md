# Améliorations du Solver d'Emploi du Temps

## Vue d'ensemble

Ce document décrit les améliorations majeures apportées au système de génération d'emploi du temps pour résoudre les problèmes identifiés.

## Problèmes Résolus

### 1. ❌ Cours Parallèles Non Synchronisés

**Problème** : Les cours devant être enseignés en parallèle (plusieurs professeurs, mêmes élèves) n'étaient pas planifiés au même créneau.

**Solution** :
- Ajout de `_add_parallel_sync_constraints()` dans `solver_engine_with_constraints.py`
- Nouvelle classe `PedagogicalScheduleSolverV2` avec synchronisation native
- Contraintes fortes : tous les cours d'un groupe parallèle DOIVENT être au même créneau

```python
# Exemple de contrainte ajoutée
for i in range(1, len(group_vars)):
    self.model.Add(group_vars[0] == group_vars[i])
```

### 2. ❌ Trous dans l'Emploi du Temps

**Problème** : Les élèves avaient des "trous" (périodes libres) entre leurs cours.

**Solution** :
- Contrainte dure "zéro trou" dans `_add_zero_gap_constraints()`
- Si une classe a cours en période 1 et 5, les périodes 2-4 DOIVENT être remplies
- Utilisation de variables auxiliaires pour détecter première/dernière période

### 3. ❌ Matières Éparpillées

**Problème** : Une même matière était dispersée sur tous les jours de la semaine.

**Solution** :
- `_add_subject_grouping_constraints()` limite à 2-3 jours maximum par matière
- Pénalités pour éparpillement dans la fonction objectif
- Favorise les blocs de 2h consécutives

### 4. ❌ Dimanche Sans Cours

**Problème** : Le dimanche (jour 0) n'avait aucun cours assigné.

**Solution** :
- Correction des boucles : `for day in range(6)` au lieu de `range(5)`
- Modification du chargement des time_slots : `WHERE day_of_week >= 0 AND day_of_week <= 5`
- Ajout de pénalités si le dimanche est sous-utilisé

### 5. ❌ Modules Avancés Non Utilisés

**Problème** : Les fichiers d'optimisation avancée n'étaient jamais appelés.

**Solution** :
- Intégration dans `main.py` avec vérification de disponibilité
- Nouveau solver `PedagogicalScheduleSolverV2` utilisé si `advanced=true`
- Fallback automatique sur solver standard en cas d'échec

## Architecture Améliorée

### Solver Standard (`solver_engine_with_constraints.py`)
- Contraintes de base renforcées
- Support dimanche-vendredi
- Synchronisation parallèle ajoutée
- Meilleure distribution quotidienne

### Solver Pédagogique V2 (`pedagogical_solver_v2.py`)
Nouveau solver complet avec :
- ✅ Synchronisation native des cours parallèles
- ✅ Zéro trou garanti (contrainte dure)
- ✅ Regroupement intelligent des matières
- ✅ Support complet dimanche-vendredi
- ✅ Blocs de 2h privilégiés
- ✅ Analyse de qualité intégrée

### API Améliorée (`main.py`)
```python
POST /generate_schedule
{
    "time_limit": 300,
    "advanced": true,         # Active le solver pédagogique V2
    "minimize_gaps": true,    # Force zéro trou
    "friday_short": true,     # Vendredi écourté
    "limit_consecutive": true,
    "avoid_late_hard": true
}
```

Nouvelles routes :
- `GET /api/advanced/status` : Vérifie la disponibilité des modules avancés
- `POST /api/advanced/optimize` : Lance l'optimisation avancée
- `GET /api/schedule_entries` : Récupère l'emploi du temps avec métadonnées

## Configuration des Jours

Convention israélienne standard :
- 0 = Dimanche (ראשון)
- 1 = Lundi (שני)
- 2 = Mardi (שלישי)
- 3 = Mercredi (רביעי)
- 4 = Jeudi (חמישי)
- 5 = Vendredi (שישי) - matin uniquement

## Utilisation

### 1. Via l'Interface Web

Ouvrir `http://localhost:8000/constraints-manager` :
- Onglet "Emploi du temps"
- Bouton "Optimisation avancée" pour utiliser le solver V2
- Visualisation par classe ou professeur

### 2. Via l'API

```bash
# Génération standard
curl -X POST http://localhost:8000/generate_schedule \
  -H "Content-Type: application/json" \
  -d '{"time_limit": 300}'

# Génération avancée
curl -X POST http://localhost:8000/generate_schedule \
  -H "Content-Type: application/json" \
  -d '{"time_limit": 300, "advanced": true, "minimize_gaps": true}'
```

### 3. Script de Test

```powershell
# Tester le nouveau solver
.\test_advanced_solver.ps1
```

## Qualité de la Solution

Le solver V2 calcule un score de qualité (0-100) basé sur :
- Nombre de trous détectés (-5 points par trou)
- Utilisation du dimanche (objectif : >20 cours)
- Regroupement des matières (% sur 2 jours max)
- Synchronisation des cours parallèles

## Performances

- Solver standard : ~30-60 secondes
- Solver pédagogique V2 : ~60-180 secondes (plus de contraintes)
- Utilisation de 8 workers parallèles
- Limite configurable (par défaut 600s)

## Problèmes Connus et Solutions

1. **Si dimanche reste vide** :
   - Vérifier que les time_slots incluent le dimanche
   - Augmenter la pénalité pour sous-utilisation du dimanche
   - Forcer une distribution minimale par jour

2. **Si synchronisation parallèle échoue** :
   - Vérifier les données dans `parallel_groups`
   - S'assurer que `is_parallel = true` dans `solver_input`
   - Vérifier les logs pour les groupes détectés

3. **Si trous persistent** :
   - Augmenter le time_limit
   - Vérifier la faisabilité (trop de contraintes ?)
   - Utiliser le solver V2 avec `minimize_gaps=true`

## Prochaines Étapes

1. Optimisation des performances du solver V2
2. Interface de configuration des poids d'objectifs
3. Rapport détaillé de qualité post-génération
4. Support des contraintes de salles
5. Préférences individuelles des professeurs





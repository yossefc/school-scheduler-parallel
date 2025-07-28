# School Scheduler - Planificateur d'Emploi du Temps

Ce projet est un système de planification d'emploi du temps scolaire avec interface web de visualisation.

## ⚡ Démarrage rapide

```powershell
# Pipeline complet en une commande
.\run-full-pipeline.ps1 -ShowProgress

# Validation seule (sans modification)
.\run-full-pipeline.ps1 -ValidateOnly

# Générer un planning réel
python solver/main.py
```

**Support multilingue** : Hébreu, Arabe, caractères Unicode  
**Optimisation OR-Tools** : Contraintes complexes, groupes parallèles  
**Interface moderne** : Visualisation bilingue, export Excel

## Structure du Projet

- `/solver/` - Moteur de résolution des emplois du temps (Python)
- `/database/` - Schéma de base de données
- `/exports/` - Fichiers Excel et visualisateur HTML
- `/docker/` - Configuration Docker

## Fonctionnalités

- ✅ Génération automatique d'emplois du temps
- ✅ Interface web de visualisation bilingue (hébreu/français)
- ✅ Export Excel des plannings
- ✅ Support des contraintes d'enseignants et de classes
- ✅ Interface responsive pour impression

## Installation et Utilisation

### Prérequis
- Python 3.8+
- Docker (optionnel)
- PowerShell (pour les scripts Windows)

### Installation avec Docker

```bash
docker-compose up -d
```

### Installation manuelle

1. Installer les dépendances Python :
```bash
cd solver
pip install -r requirements.txt
```

2. Configurer la base de données :
```bash
# Exécuter le schéma SQL dans votre base de données
```

3. Lancer le solveur :
```bash
cd solver
python main.py
```

### Scripts PowerShell disponibles

- **`run-full-pipeline.ps1`** - 🚀 **Pipeline complet** (Unicode → Bloc A → Bloc B)
- **`prepare-github-release.ps1`** - 📋 **Préparation GitHub** (validation + publication)
- `export-schedule.ps1` - Export des emplois du temps
- `voir-emploi-temps.ps1` - Visualisation des plannings
- `fix-data.ps1` - Correction des données
- `create_test_excel.ps1` - Création de fichiers de test
- `run-normalize-classes.ps1` - **Normalisation Unicode avancée** des listes de classes
- `run-fix-teacher-load.ps1` - Nettoyage et traitement des charges d'enseignants (Bloc A)
- `test-bloc-b.ps1` - Test des groupes parallèles et réunions professeurs (Bloc B)

## Processus de traitement des données

### Étape 0 : Normalisation Unicode avancée (Optionnel)

Pour les données contenant des caractères hébreux, arabes ou des séparateurs non-standard :

```powershell
# Validation des données sans modification
.\run-normalize-classes.ps1 -ValidateOnly -ShowProgress

# Normalisation complète avec exemples
.\run-normalize-classes.ps1 -ShowProgress -ShowExamples
```

**Caractères supportés** :
- **Ellipses** : `...` et `…` → `,`
- **Virgules Unicode** : `,` (ASCII), `،` (Arabe), `，` (Pleine largeur), `ֺ` (Hébreu)
- **Nettoyage** : Espaces multiples, virgules consécutives, début/fin de chaîne

**Transformations** :
```
ט-1...ט-3  →  ט-1,ט-2,ט-3
א-1،א-2   →  א-1,א-2  
ב-1 ， ב-2  →  ב-1,ב-2
ג-1,,ג-2   →  ג-1,ג-2
```

### Bloc A : Nettoyage des données teacher_load

Après la normalisation Unicode, nettoyez les données :

```powershell
# Nettoyage des données avec affichage des étapes
.\run-fix-teacher-load.ps1 -ShowProgress

# Ou avec une base de données personnalisée
.\run-fix-teacher-load.ps1 -DatabasePath "path/to/your/database.db"
```

Ce script effectue :
- **Éclatement des plages** : `ט-1...ט-3` devient `ט-1`, `ט-2`, `ט-3` séparément
- **Marquage des cours parallèles** : Les cours éclatés sont marqués comme parallèles
- **Suppression des surveillances** : Retire les cours de type `שהייה`
- **Préservation des réunions** : Garde les `ישיבה`/`פגישה` pour traitement spécial

### Bloc B : Améliorations du solveur Python

Le moteur de résolution a été amélioré pour supporter :

#### 🔄 Groupes parallèles
- **Cours simultanés** : Un professeur peut enseigner à plusieurs classes en même temps
- **Contraintes de synchronisation** : Les cours parallèles sont automatiquement planifiés au même créneau
- **Support natif** : Intégration dans les contraintes OR-Tools

#### 👥 Réunions professeurs  
- **Réunions sans classe** : `ישיבה`/`פגישה` bloquent le professeur mais n'occupent aucune salle
- **Classe virtuelle** : Utilisation de `_MEETING` comme identifiant interne
- **Planification flexible** : Les réunions peuvent être placées n'importe quand selon les disponibilités

#### 🧪 Tests et validation

```powershell
# Test complet (Windows PowerShell)
.\test-bloc-b.ps1 -FullCycle

# Tests manuels (Python)
cd solver
python test_bloc_b.py

# Lancer le solveur avec les améliorations
python main.py
```

**Validation automatique** :
- ✅ Chargement des groupes parallèles depuis la base
- ✅ Création de variables `_MEETING` pour les réunions
- ✅ Application des contraintes de simultanéité
- ✅ Génération d'un planning cohérent

## Visualisateur Web

Ouvrez `exports/visualiser_emploi_du_temps.html` dans votre navigateur pour :
- Consulter les emplois du temps par classe ou professeur
- Imprimer les plannings
- Interface bilingue hébreu/français

## Technologies Utilisées

- **Backend**: Python, OR-Tools (optimisation)
- **Base de données**: SQL
- **Frontend**: HTML, CSS, JavaScript
- **Déploiement**: Docker
- **Export**: Excel (openpyxl)

## 🚀 Publication sur GitHub

Pour préparer et publier le projet sur GitHub :

```powershell
# Validation complète avant publication
.\prepare-github-release.ps1 -DryRun

# Préparation pour GitHub (si validation OK)
.\prepare-github-release.ps1
```

**Puis suivez les instructions affichées pour :**
1. Créer le dépôt sur GitHub.com
2. Configurer le remote origin
3. Pousser le code initial

## Contribuer

1. Fork le projet
2. Créez votre branche (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commitez vos changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Ouvrez une Pull Request

## Licence

Ce projet est sous licence [choisir une licence appropriée]. 
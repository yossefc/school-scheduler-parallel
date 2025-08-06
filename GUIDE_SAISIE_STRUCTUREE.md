# 🎯 Guide de la Saisie Structurée des Contraintes

## Vue d'ensemble

L'interface de gestion des contraintes dispose maintenant de **deux modes de saisie** :

1. **Mode texte libre** (original) : Décrivez vos contraintes en langage naturel
2. **Mode structuré** (nouveau) : Utilisez des champs guidés pour créer vos contraintes

## Comment basculer entre les modes

Cliquez sur le bouton **🔄 Basculer mode saisie** pour passer d'un mode à l'autre.

- **Mode texte libre** : Bouton bleu "🔄 Basculer mode saisie"
- **Mode structuré** : Bouton vert "📝 Mode texte libre"

## Mode Structuré - Champs disponibles

### 🏢 Type d'entité
- **Professeur** : Pour les contraintes liées à un enseignant
- **Classe** : Pour les contraintes spécifiques à une classe
- **Salle** : Pour les contraintes de localisation
- **Global (école)** : Pour les contraintes qui s'appliquent à toute l'école

### 🔧 Types de contraintes disponibles

| Type | Description | Exemple d'usage |
|------|-------------|-----------------|
| **Disponibilité** | Indisponibilités d'un professeur | "Cohen pas disponible vendredi" |
| **Horaire matière** | Contraintes temporelles | "Maths en première heure" |
| **Attribution salle** | Assignation de salles | "Sciences en laboratoire" |
| **Cours parallèle** | Enseignement synchronisé | "Maths ט en parallèle" |
| **Vendredi court** | Journée écourtée | "Fin à 14h le vendredi" |
| **Prière matinale** | Temps religieux | "Première période réservée" |
| **Personnalisé** | Autres contraintes | Contraintes spécifiques |

### 🎚️ Niveaux de priorité

| Priorité | Couleur | Description |
|----------|---------|-------------|
| **🔴 Critique (1)** | Rouge | Contrainte absolue - ne peut pas être violée |
| **🟠 Importante (2)** | Orange | Contrainte très importante |
| **🟡 Normale (3)** | Jaune | Contrainte standard (par défaut) |
| **🟢 Faible (4)** | Vert | Contrainte préférentielle |

### ✅ État de la contrainte
- **✅ Active** : La contrainte est appliquée
- **❌ Inactive** : La contrainte est ignorée

## Exemples pratiques

### Exemple 1 : Professeur indisponible
```
Type d'entité: Professeur
Nom: Cohen
Type de contrainte: Disponibilité
Priorité: Importante (2)
```
→ Génère : "Le professeur Cohen n'est pas disponible"

### Exemple 2 : Cours parallèles
```
Type d'entité: Global (école)
Nom: מתמטיקה ט
Type de contrainte: Cours parallèle
Priorité: Critique (1)
```
→ Génère : "Les cours de מתמטיקה ט doivent être en parallèle"

### Exemple 3 : Vendredi court
```
Type d'entité: Global (école)
Nom: École
Type de contrainte: Vendredi court
Priorité: Critique (1)
```
→ Génère : "Les cours se terminent plus tôt le vendredi"

## Avantages du mode structuré

✅ **Guidage** : Les champs vous guident dans la création de contraintes valides  
✅ **Cohérence** : Format standardisé pour toutes les contraintes  
✅ **Priorités claires** : Système de priorités visuellement identifiable  
✅ **Types prédéfinis** : Templates pour les contraintes courantes  
✅ **Génération automatique** : Le texte se crée automatiquement  
✅ **Validation** : Réduction des erreurs de saisie  

## Mode texte libre

Le mode texte libre reste disponible pour :
- Les contraintes complexes non couvertes par les templates
- Les utilisateurs préférant la saisie naturelle
- Les contraintes nécessitant des descriptions détaillées

## Tips et astuces

1. **Commencez par le mode structuré** pour les contraintes courantes
2. **Basculez en mode texte libre** pour affiner la description si nécessaire
3. **Utilisez des noms cohérents** (ex: toujours "Cohen" et pas "Prof Cohen")
4. **Ajustez les priorités** selon l'importance réelle de la contrainte
5. **Testez avec l'état "Inactive"** avant d'activer définitivement

## Support et aide

- L'interface génère automatiquement le texte de contrainte
- Vous pouvez modifier le texte généré avant de valider
- Les contraintes structurées sont marquées avec `created_via: 'structured_input'`
- En cas de problème, revenez au mode texte libre

---

*Cette fonctionnalité améliore significativement l'expérience utilisateur en proposant une saisie guidée tout en conservant la flexibilité du mode texte libre.*
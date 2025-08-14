# Checklist de Tests - Interface Contraintes & Génération

## 🎯 Acceptance Criteria à valider

### ✅ Navigation et Interface
- [ ] Interface accessible via http://localhost:8000/constraints-manager
- [ ] Layout split : gauche (35%) contraintes, droite (65%) résultats
- [ ] Thème sombre avec couleurs #0b1220, #0f1629, etc.
- [ ] Responsive design fonctionne sur différentes tailles d'écran

### ✅ Panneau Contraintes (Gauche)
- [ ] Contraintes dures : Limiter heures consécutives, Éviter matières dures, Vendredi écourté
- [ ] Contraintes souples : Minimiser trous profs, Priorité matin, Équilibrer charge
- [ ] Toutes les checkboxes sont cochées par défaut
- [ ] Bouton "🚀 Génération avancée" présent et stylé
- [ ] Statut affiché : "Prêt" au démarrage
- [ ] Barre de progression apparaît pendant génération
- [ ] Métadonnées affichées après génération (statut, temps, mode)

### ✅ Panneau Résultats (Droite)
- [ ] Onglets "📚 Classes" et "👥 Professeurs"
- [ ] Sélecteur pour choisir classe/professeur
- [ ] Filtre par matière "Toutes matières"
- [ ] Boutons : "📊 Exporter CSV", "🖨️ Imprimer", "🔄 Reset filtres"
- [ ] État vide initial avec message d'aide
- [ ] Grille emploi du temps avec jours en colonnes, créneaux en lignes

### ✅ Fonctionnalité Génération
- [ ] Cliquer "Génération avancée" → statut passe à "Initialisation…"
- [ ] Barre de progression s'affiche et se remplit
- [ ] Statut évolue : "Lancement…" → "Optimisation…" → "Optimal ✅"
- [ ] Toast de succès : "Planning généré avec succès! 🎉"
- [ ] Métadonnées s'affichent automatiquement
- [ ] Grille se remplit avec l'emploi du temps généré

### ✅ Visualisation Emploi du Temps
- [ ] Auto-sélection de la première classe/professeur disponible
- [ ] Grille correctement structurée (créneaux + horaires en lignes, jours en colonnes)
- [ ] Cellules affichent : Badge matière + info prof/classe + salle (si dispo)
- [ ] Passage d'un onglet à l'autre (Classes ↔ Professeurs) fonctionne
- [ ] Filtre par matière opérationnel
- [ ] Affichage cohérent selon le mode (vue classe vs vue professeur)

### ✅ Fonctionnalités Export & Actions
- [ ] Export CSV télécharge fichier avec bon format
- [ ] CSV contient : Vue, Nom, Jour, Créneau, Heure, Classe, Matière, Professeurs, Salle
- [ ] Nom fichier CSV : emploi_temps_[classes|teachers]_[nom].csv
- [ ] Impression (Ctrl+P) affiche correctement l'emploi du temps
- [ ] Reset filtres remet filtre matière à "Toutes matières"

### ✅ Gestion Erreurs & États
- [ ] Si génération échoue : statut "Infaisable ❌" ou "Erreur ❌"
- [ ] Toast d'erreur avec message approprié
- [ ] Si timeout : message "Timeout sans résultat..."
- [ ] Si aucune classe/prof sélectionné pour export : toast d'erreur
- [ ] Si pas de planning à exporter : toast "Aucun planning à exporter"

### ✅ Persistance & Préférences
- [ ] Contraintes cochées sauvegardées dans localStorage
- [ ] Onglet actif (Classes/Professeurs) restauré au rechargement
- [ ] Préférences rechargées automatiquement à l'ouverture

### ✅ Support RTL (Bonus)
- [ ] Attribut data-locale="he" change direction (dir="rtl")
- [ ] Titre change en hébreu : "ניהול אילוצים ויצירה"
- [ ] Layout adapté pour lecture droite-à-gauche

### ✅ APIs Backend
- [ ] GET /api/schedule_entries?version=latest retourne contrat JSON correct
- [ ] POST /generate_schedule avec advanced=true fonctionne
- [ ] Métadonnées (solve_status, walltime_sec, advanced) correctement sauvegardées
- [ ] Compatibilité subject vs subject_name assurée

## 🔧 Tests Techniques

### Test API schedule_entries
```bash
curl "http://localhost:8000/api/schedule_entries?version=latest"
```
Doit retourner :
```json
{
  "version": "latest",
  "time_slots": [...],
  "entries": [...],
  "meta": {
    "solve_status": "OPTIMAL|FEASIBLE|INFEASIBLE|ERROR",
    "walltime_sec": 3.32,
    "advanced": true,
    "notes": []
  }
}
```

### Test génération avancée
```bash
curl -X POST "http://localhost:8000/generate_schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "advanced": true,
    "limit_consecutive": true,
    "avoid_late_hard": true,
    "minimize_gaps": true,
    "friday_short": true
  }'
```

## 📝 Logs à surveiller
- Console navigateur : pas d'erreurs JavaScript
- Logs serveur : génération sans erreurs critiques
- Réseau : appels API retournent 200 OK
- Base de données : schedule_entries créées avec bonnes colonnes

## ✅ Validation finale
- [ ] Interface fonctionne end-to-end sans dépendance au dashboard
- [ ] Génération + visualisation + export complet en une interface
- [ ] Performance acceptable (génération < 10 minutes)
- [ ] UX fluide et intuitive
- [ ] Messages d'erreur utiles et clairs

---
**Statut global** : [ ] ✅ Tous les critères validés
# 🤖 Guide de l'Agent Conseiller Multilingue (Hébreu + Français)

## 🌟 Comment ça fonctionne ?

Votre Agent Conseiller AI peut maintenant **comprendre et répondre en hébreu** ! Voici comment il vous comprend :

### 1. 🔍 **Détection Automatique de Langue**

L'agent analyse automatiquement votre message et détermine si vous écrivez en hébreu ou en français :

```
Votre message: "תוכל למלא את החורים במערכת השעות של ז-1?"
Agent détecte: "Hébreu (85% de caractères hébreux)"
Réponse en: Hébreu
```

### 2. 🧠 **Processeur de Langue Hébraïque Spécialisé**

L'agent utilise un processeur NLP spécialement conçu pour l'hébreu dans le contexte scolaire :

#### **Actions en Hébreu Comprises:**
- `להזיז` (déplacer) → "move"
- `לתקן` (réparer) → "fix"  
- `לאזן` (équilibrer) → "balance"
- `להוסיף` (ajouter) → "add"
- `לבטל` (annuler) → "cancel"

#### **Entités Scolaires Détectées:**
- **Classes**: `ז-1`, `ח-2`, `יא-3` automatiquement reconnues
- **Matières**: `מתמטיקה`, `אנגלית`, `תנך`, `מדעים`, `היסטוריה`
- **Jours**: `יום ראשון`, `יום שני`, `רביעי`
- **Temps**: `בבוקר`, `אחר הצהריים`, `ב-8`, `בשעה 9`

#### **Problèmes Identifiés:**
- `חור` / `חורים` → "gaps" (trous dans l'emploi du temps)
- `התנגשות` / `קונפליקט` → "conflict" (conflits d'horaires)
- `עומס` → "overload" (surcharge)

#### **Préférences Personnelles:**
- `חשוב לי` → "important to me"
- `אני מעדיף` → "I prefer"
- `תמיד` → "always"
- `לעולם לא` → "never"
- `כדאי` → "it's better"

### 3. 💬 **Exemples de Conversations**

#### **Demande Simple en Hébreu:**
```
👤 Vous: "תוכל למלא את החורים במערכת השעות של ז-1?"

🤖 Agent: "שלום! ניתחתי את הבקשה שלך ואני מציע 2 שינויים לשיפור מערכת השעות:

🟢 הצעה 1 (ביטחון: 85%)
   למלא את החור של 4 שעות ביום חמישי בין פריודות 2-5
   למה: להזיז שיעורים לזמנים פנויים כדי ליצור בלוק רציף
   השפעה: 1 כיתות, 3 מורים

האם אתה רוצה שאיישם את השינויים האלה?"
```

#### **Préférence Personnelle:**
```
👤 Vous: "חשוב לי שהמתמטיקה תמיד תהיה בבוקר"

🤖 Agent: "שלום! 📝 רשמתי את ההעדפה החדשה שלך שאשמור בזיכרון לאופטימיזציות הבאות.

אני מבין שמתמטיקה צריכה להיות תמיד בבוקר. זה ייקח בחשבון בכל השיפורים הבאים שלי למערכת השעות."
```

#### **Conversation Mixte:**
```
👤 Vous: "תוכל לעזור לי?"
🤖 Agent: "שלום! בוודאי אוכל לעזור. מה תרצה לשנות במערכת השעות?"

👤 Vous: "Je veux équilibrer la charge des professeurs"  
🤖 Agent: "Bonjour ! Je peux analyser la charge des professeurs..."
```

### 4. 🔧 **Architecture Technique**

```
Votre Message en Hébreu
         ↓
[Détection de Langue] → "hebrew" détecté
         ↓
[Processeur Hébreu] → Analyse NLP spécialisée
         ↓
[Extraction d'Entités] → Classes, matières, actions, préférences
         ↓
[Génération de Réponses] → Réponse en hébreu
```

#### **Composants Clés:**

1. **`HebrewLanguageProcessor`** - Processeur NLP hébreu
   - Normalisation du texte (suppression nikud)
   - Extraction d'entités scolaires
   - Analyse d'intentions
   - Évaluation d'urgence et politesse

2. **`ScheduleAdvisorAgent`** - Agent principal multilingue
   - Détection automatique de langue
   - Routage vers le bon processeur
   - Génération de réponses adaptées
   - Mémorisation des préférences

3. **Base de Données** - Stockage multilingue
   - Préférences en hébreu et français
   - Historique conversationnel
   - Métadonnées linguistiques

### 5. 📚 **Vocabulaire Scolaire Supporté**

#### **Matières (עברית ← → Français):**
- `מתמטיקה` ↔ Mathématiques
- `אנגלית` ↔ Anglais  
- `תנ"ך` ↔ Bible
- `מדעים` ↔ Sciences
- `היסטוריה` ↔ Histoire
- `אזרחות` ↔ Éducation civique
- `הבעה` ↔ Expression
- `ספורט` ↔ Sport

#### **Classes Reconnues:**
- `ז-1, ז-2, ז-3` (7ème année)
- `ח-1, ח-2, ח-3` (8ème année) 
- `ט-1, ט-2, ט-3` (9ème année)
- `י-1, יא-1, יב-1` (10ème, 11ème, 12ème année)

#### **Expressions Temporelles:**
- `בבוקר` (le matin)
- `אחר הצהריים` (l'après-midi)
- `יום ראשון` (dimanche)
- `בשעה 8` (à 8h00)

### 6. 🎯 **Niveaux de Confiance**

L'agent calcule un score de confiance pour chaque analyse :

- **🟢 85-100%** - Très confiant (action claire, entités bien identifiées)
- **🟡 60-84%** - Moyennement confiant (demande un peu ambiguë)
- **🟠 30-59%** - Peu confiant (demande plus de clarifications)

### 7. 🚀 **Comment Commencer**

#### **Démarrer l'Agent:**
```bash
# Lancer le service agent conseiller
docker-compose up advisor_agent -d

# Vérifier qu'il est actif
curl http://localhost:5002/api/advisor/status
```

#### **Ouvrir l'Interface:**
1. Aller sur votre interface web principale
2. Cliquer sur "🤖 Agent Conseiller"  
3. Commencer à taper en hébreu ou français !

#### **Exemples pour Tester:**

**Demandes en Hébreu:**
```
תוכל למלא את החורים במערכת השעות של ז-1?
אני רוצה להזיז את המתמטיקה של יא-2 יותר מוקדם ביום
איך לאזן טוב יותר את העומס בין הכיתות?
חשוב לי שהמתמטיקה תמיד תהיה בבוקר
```

**Demandes en Français:**
```
Peux-tu éliminer les trous dans l'emploi du temps de ז-1 ?
Je voudrais équilibrer la charge des professeurs
Pour moi, les cours de sciences doivent être groupés
```

### 8. 🔧 **Fonctionnalités Avancées**

#### **Mémoire Contextuelle:**
- L'agent se souvient de vos préférences dans les deux langues
- Historique de conversation multilingue
- Apprentissage de vos habitudes linguistiques

#### **Analyse Intelligente:**
- Détection d'urgence (`דחוף`, "urgent")
- Évaluation de politesse (`בבקשה`, "s'il vous plaît")
- Reconnaissance d'entités complexes

#### **Propositions Contextuelles:**
- Solutions adaptées au contexte hébraïque/français
- Respect des conventions scolaires israéliennes
- Optimisations pédagogiques intelligentes

---

## 🎉 **Résultat Final**

Votre Agent Conseiller peut maintenant :

✅ **Comprendre** vos demandes en hébreu et français  
✅ **Analyser** intelligemment les entités scolaires hébraïques  
✅ **Répondre** dans la langue de votre choix  
✅ **Mémoriser** vos préférences multilingues  
✅ **Proposer** des modifications adaptées  
✅ **Apprendre** de vos interactions  

**Il suffit de lui parler naturellement dans la langue de votre choix !** 🗣️
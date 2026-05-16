# 🩺 Veille médicale automatique — Guide d'installation

Système 100% automatique qui :
- Envoie chaque matin à 7h un email récapitulatif technique des publications médicales
- Publie le mardi et le vendredi un épisode podcast de ~20 min, accessible via Pocket Casts / AntennaPod sur Android
- Tourne dans le cloud GitHub, **sans aucun ordinateur à laisser allumé**
- Coût : **0 €**

---

## ⏱️ Temps d'installation total : ~30 minutes (une seule fois)

## 📋 Vue d'ensemble des comptes à créer

| Service | Pour quoi | Lien |
|---|---|---|
| **GitHub** | Héberger et exécuter le script | https://github.com/signup |
| **Groq** | Générer les résumés IA (gratuit, illimité) | https://console.groq.com |
| **Gmail** | Envoyer les emails (utilisez votre Gmail existant) | — |

---

## 1️⃣ Créer un compte GitHub (5 min)

1. Allez sur https://github.com/signup
2. Créez un compte avec votre email — choisissez un nom d'utilisateur (ex: `dr-martin`)
3. Validez votre email

---

## 2️⃣ Créer un compte Groq pour l'IA (3 min)

1. Allez sur https://console.groq.com
2. Cliquez sur **"Sign in"** puis **"Continue with Google"** (le plus simple)
3. Une fois connecté, allez dans **"API Keys"** dans le menu de gauche
4. Cliquez sur **"Create API Key"**, donnez-lui un nom (ex: "veille-medicale")
5. **Copiez la clé** (elle commence par `gsk_...`) — gardez-la dans un bloc-notes, on s'en servira dans 5 minutes

> Groq est **gratuit** pour un usage personnel : largement assez pour notre 2 résumés/jour.

---

## 3️⃣ Créer un mot de passe d'application Gmail (5 min)

> ⚠️ Si votre compte Google n'a pas la **double authentification** activée, activez-la d'abord ici : https://myaccount.google.com/security

1. Allez sur https://myaccount.google.com/apppasswords
2. Tapez un nom comme **"Veille médicale"** et cliquez sur **"Créer"**
3. Google affiche un **mot de passe de 16 caractères** (ex: `abcd efgh ijkl mnop`)
4. **Copiez-le sans les espaces** (ex: `abcdefghijklmnop`) et gardez-le pour l'étape 5

---

## 4️⃣ Importer le code dans votre GitHub (5 min)

### Option A — Via l'interface web GitHub (plus simple)

1. Téléchargez le ZIP de ce projet (lien fourni par l'assistant)
2. Connectez-vous sur https://github.com
3. Cliquez sur le **"+" en haut à droite** → **"New repository"**
4. Nom : `veille-medicale-cloud`
5. ⚠️ **Cochez "Public"** (obligatoire pour que le flux podcast soit accessible — sinon votre app podcast ne pourra pas télécharger les MP3)
6. Cliquez sur **"Create repository"**
7. Sur la page du dépôt vide, cliquez sur **"uploading an existing file"**
8. **Glissez-déposez tout le contenu du ZIP** (les dossiers `.github`, `scripts`, `podcast`, et les fichiers `index.html`, `README.md`, `.gitignore`)
9. Tout en bas, cliquez sur **"Commit changes"**

---

## 5️⃣ Configurer les 4 secrets dans GitHub (5 min)

1. Sur la page de votre dépôt, cliquez sur **"Settings"** (onglet en haut)
2. Menu de gauche : **"Secrets and variables" → "Actions"**
3. Cliquez sur **"New repository secret"** pour chacun des 4 secrets ci-dessous :

| Nom du secret | Valeur |
|---|---|
| `GROQ_API_KEY` | La clé `gsk_...` copiée à l'étape 2 |
| `SMTP_USER` | Votre adresse Gmail (ex: `votre.nom@gmail.com`) |
| `SMTP_PASSWORD` | Le mot de passe 16 caractères de l'étape 3 |
| `MAIL_TO` | L'adresse où vous voulez recevoir les emails (peut être la même que SMTP_USER) |

---

## 6️⃣ Activer GitHub Pages pour le podcast (2 min)

1. Toujours dans **"Settings"** → menu de gauche **"Pages"**
2. Sous **"Branch"**, sélectionnez **"main"** et **"/ (root)"**
3. Cliquez sur **"Save"**
4. Patientez 1-2 min. Une fois actif, votre site sera accessible à `https://VOTRE-USERNAME.github.io/veille-medicale-cloud/`

---

## 7️⃣ Donner les permissions au workflow (2 min)

1. **"Settings"** → menu de gauche **"Actions" → "General"**
2. Tout en bas, section **"Workflow permissions"** :
   - Sélectionnez **"Read and write permissions"**
   - Cliquez sur **"Save"**

Sans ça, le workflow ne pourra pas pousser les nouveaux MP3 dans le dépôt.

---

## 8️⃣ Premier test manuel (3 min)

1. Sur votre dépôt, cliquez sur l'onglet **"Actions"** en haut
2. À gauche, cliquez sur **"Veille médicale quotidienne"**
3. À droite, bouton **"Run workflow"** → choisissez le mode :
   - `email` pour tester juste l'email
   - `audio` pour tester aussi la génération MP3 + publication podcast
   - `auto` pour le comportement normal (email + audio si mardi/vendredi)
4. Cliquez sur le bouton vert **"Run workflow"**
5. Patientez 2-3 minutes. Vous devriez voir :
   - Un email arriver dans votre boîte
   - Si mode audio : un MP3 publié dans le dossier `podcast/episodes/` du dépôt

> ⚠️ Si vous voyez une croix rouge, cliquez dessus pour voir l'erreur. C'est presque toujours un secret mal copié.

---

## 9️⃣ Ajouter le podcast sur Android (2 min)

1. Installez **AntennaPod** (gratuit, open source) ou **Pocket Casts** depuis le Play Store
2. Ouvrez l'app, allez dans **"Ajouter un podcast"** → **"Par URL"**
3. Collez : `https://VOTRE-USERNAME.github.io/veille-medicale-cloud/podcast/feed.xml`
4. Le podcast apparaît avec votre premier épisode
5. Dans les paramètres du podcast, activez **"Téléchargement automatique"**

À chaque nouvelle publication (mardi/vendredi 7h), l'app téléchargera automatiquement l'épisode en Wi-Fi.

---

## ✅ C'est terminé

À partir de maintenant, chaque matin à 7h :
- **Tous les jours** : email avec les nouveautés
- **Mardi et vendredi** : épisode podcast de ~20 min disponible dans votre app

Tout est automatique. Vous n'avez **plus jamais besoin de toucher quoi que ce soit**.

---

## 🛠️ Personnalisation après installation

Ouvrez `scripts/veille.py` directement sur GitHub (cliquez sur le crayon pour éditer) et modifiez en haut du fichier :

```python
JOURS_RECULS = 2            # fenêtre de recherche en jours
ARTICLES_PAR_THEME = 7      # nombre max d'articles par thème
```

Ou changez les requêtes PubMed dans le dictionnaire `PUBMED_QUERIES` pour cibler d'autres spécialités.

Pour changer l'heure d'envoi, modifiez le cron dans `.github/workflows/veille.yml`.

---

## ❓ Dépannage rapide

| Problème | Solution |
|---|---|
| Pas d'email reçu | Vérifiez les 4 secrets, surtout le mot de passe d'application Gmail (16 caractères sans espaces) |
| Erreur "401" sur Groq | Clé Groq mal copiée, recommencez l'étape 2 |
| Podcast inaccessible | Le dépôt doit être **public** et GitHub Pages doit être activé |
| Workflow ne se lance pas seul | Normal le 1er jour : GitHub désactive les workflows automatiques pendant 60 jours après le dernier commit. Faites un commit manuel pour réactiver. |
| Pas d'épisode mardi/vendredi | Vérifiez les permissions "Read and write" à l'étape 7 |

---

## 💰 Coût

**0 €** :
- GitHub Actions : 2000 min/mois gratuites, on en utilise ~30/mois
- GitHub Pages : gratuit pour les dépôts publics
- Groq API : gratuit pour usage personnel (largement sous les limites)
- Edge TTS : gratuit, illimité
- Gmail : gratuit

---

## 🔒 Confidentialité

- Vos secrets (clés, mots de passe) sont chiffrés par GitHub, **invisibles** dans le code
- Le dépôt est public mais ne contient **aucune information personnelle**
- Le podcast est public mais à URL non devinable (votre username + `/veille-medicale-cloud`). Si vous voulez le rendre vraiment privé, il faut un hébergement payant.

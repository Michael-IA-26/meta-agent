# 👋 Bienvenue chez JM Partners — Guide de démarrage

> Ce guide est fait pour vous. Pas de code, pas de jargon technique — juste ce que vous devez savoir pour profiter pleinement de votre assistant comptable automatisé.

---

## 1. 🎯 Ce qu'on va faire ensemble

Votre cabinet vient de se doter d'un **assistant automatisé** qui travaille pour vous 24h/24, 7j/7.

Concrètement, il va :

- **Lire vos emails entrants** et identifier automatiquement les demandes de vos clients (documents manquants, questions TVA, relances…)
- **Surveiller vos échéances** fiscales et comptables (TVA, IS, bilans) et vous alerter avant qu'il soit trop tard
- **Relancer vos clients** par email quand des pièces manquent à un dossier — de façon professionnelle et personnalisée
- **Vous envoyer un rapport quotidien** chaque matin avec l'état de vos dossiers

Vous n'avez **rien à faire au quotidien**. L'assistant tourne tout seul. Ce guide vous explique comment il fonctionne et comment vérifier que tout va bien.

---

## 2. 🤖 Qu'est-ce que les agents ?

Votre assistant est composé de **10 agents spécialisés**, chacun ayant un rôle précis. Voici ce qu'ils font en langage métier :

---

### 📬 Agent Emails (`mail_handler`)
**Ce qu'il fait :** Il lit votre boîte email professionnelle toutes les 15 minutes et classe automatiquement chaque message reçu.

**Exemple :** Un client vous envoie « Je vous transmets mon grand livre comme demandé ». L'agent détecte que c'est un envoi de document, identifie le client dans votre base, et note que le grand livre a été reçu.

**Ce que vous recevez :** Rien directement — il travaille en silence. Vous pouvez voir le résultat dans le dashboard.

---

### 📋 Agent Vérification Dossiers (`document_checker`)
**Ce qu'il fait :** Pour chaque dossier client, il vérifie quelles pièces ont été reçues et lesquelles manquent encore, en fonction du type de mission (bilan, TVA, IS, paie, création).

**Exemple :** Pour un dossier bilan, il vérifie si vous avez reçu : Grand Livre, Balance, Factures Achats, Factures Ventes, Relevés Bancaires. S'il manque la Balance et les Relevés, il le signale.

**Ce que vous recevez :** Une liste précise des manquants, avec le niveau d'urgence selon la deadline.

---

### ✉️ Agent Relances (`relance_handler`)
**Ce qu'il fait :** Quand des pièces manquent dans un dossier, il rédige et envoie automatiquement un email de relance à votre client — adapté au niveau d'urgence.

**Exemple :**
- Deadline dans 15 jours → email cordial : *« Bonjour, nous n'avons pas encore reçu votre Grand Livre… »*
- Deadline dans 3 jours → email ferme : *« Bonjour, afin de respecter votre deadline du 15 juin, nous avons besoin en urgence de… »*

**Ce que vous recevez :** Un email est envoyé depuis votre adresse à votre client. Vous êtes en copie si vous le souhaitez.

> 💡 L'agent ne relance jamais deux fois en moins de 48h le même client pour le même dossier.

---

### 📊 Agent TVA (`tva_agent`)
**Ce qu'il fait :** Il surveille toutes vos déclarations TVA à venir et vérifie que les pièces nécessaires sont disponibles (CA mensuel, factures, relevés bancaires).

**Exemple :** La TVA d'avril est à déposer le 20 mai. Le 5 mai (J-15), l'agent détecte que le CA mensuel n'est pas encore reçu → alerte Telegram + vérification automatique des pièces.

**Ce que vous recevez :** Une alerte Telegram à J-15, J-7 et J-3 si des pièces manquent.

---

### 📅 Agent Échéances (`echeance_agent`)
**Ce qu'il fait :** Chaque matin, il génère un rapport complet de toutes vos échéances TVA et IS des 30 prochains jours, avec un code couleur.

**Exemple de rapport reçu :**
```
🔴 URGENT (≤3j) : TVA avril — échéance 20/05
🟠 ATTENTION (≤7j) : Acompte IS T2 — échéance 15/06
🟡 À SURVEILLER (≤15j) : TVA mai — échéance 20/06
```

**Ce que vous recevez :** Un email + un message Telegram chaque matin en semaine.

---

### 🗂️ Agent Clôture (`cloture_handler`)
**Ce qu'il fait :** Le dernier jour ouvré de chaque mois, il identifie tous les dossiers en cours et déclenche la procédure de clôture comptable mensuelle.

**Exemple :** Le 30 juin, il liste tous les dossiers actifs, les passe en statut « clôture envoyée » et vous notifie sur Telegram.

**Ce que vous recevez :** Une notification Telegram en fin de mois.

---

### 💰 Agent Acomptes IS (`acompte_is_agent`)
**Ce qu'il fait :** Il surveille les échéances de paiement des acomptes d'Impôt sur les Sociétés (15 mars, 15 juin, 15 septembre, 15 décembre) pour chacun de vos clients.

**Exemple :** Le 1er juin, il détecte que l'acompte IS T2 de votre client Dupont SARL arrive à échéance le 15 juin → alerte J-15, J-7, J-3.

**Ce que vous recevez :** Un email + alerte Telegram par client concerné.

---

### 📈 Agent Bilans (`bilan_agent`)
**Ce qu'il fait :** Il surveille les deadlines de dépôt des bilans comptables pour vos clients et vous alerte quand la date approche.

**Exemple :** Le bilan 2025 de Martin & Associés est à déposer le 30 septembre. À J-30, J-15 et J-7, vous recevez une alerte avec l'état des pièces reçues.

**Ce que vous recevez :** Un email + alerte Telegram à J-30, J-15 et J-7.

---

### 📝 Agent Déclarations IS (`declaration_is_agent`)
**Ce qu'il fait :** Il surveille les échéances de dépôt des déclarations IS (2065) et vous alerte si la date approche sans que la liasse fiscale soit disponible.

**Exemple :** La déclaration IS de Lemaire SAS est à déposer le 15 mai. À J-15, il vérifie que la liasse fiscale est disponible — si non, alerte.

**Ce que vous recevez :** Un email + alerte Telegram à J-30, J-15 et J-7.

---

### 🔔 Agent Notifications (`notification_agent`)
**Ce qu'il fait :** C'est le hub centralisé de toutes les notifications. Il s'assure que vous ne recevez pas deux fois la même alerte dans la même journée (déduplication automatique).

**Exemple :** Si deux agents détectent simultanément le même problème sur un dossier, vous ne recevez qu'une seule notification.

**Ce que vous recevez :** Rien de plus — il travaille en arrière-plan.

---

## 3. 🗓️ Le calendrier quotidien

Voici exactement ce qui se passe chaque jour :

### Lundi au vendredi

| Heure | Ce qui se passe | Ce que vous recevez |
|-------|----------------|---------------------|
| **07h00** | Cycle complet : emails → relances → TVA → échéances → clôture → IS → bilans | Email rapport échéances + alertes Telegram |
| **Toutes les 15 min** | Lecture de votre boîte email | (rien si boîte vide) |
| **En continu** | Surveillance des nouvelles pièces reçues | Telegram si document urgent reçu |

### Week-end et jours fériés

L'assistant est en veille. Il reprend automatiquement le lundi matin.

> 📌 **Astuce :** Si une deadline tombe un lundi, l'alerte du vendredi précédent sera marquée J-3 (week-end non compté). Prévoyez d'agir le vendredi.

---

## 4. 📩 Les résultats attendus

### 4.1 Rapport d'échéances quotidien (email)

Chaque matin en semaine, vous recevez un email comme celui-ci :

```
Objet : Rapport échéances JM Partners — Mardi 11 juin 2026

🔴 URGENT — 1 échéance dans ≤3 jours
  • TVA avril 2026 — deadline 13/06 — Dupont SARL

🟠 ATTENTION — 2 échéances dans ≤7 jours
  • Acompte IS T2 — deadline 15/06 — Martin & Associés
  • Acompte IS T2 — deadline 15/06 — Lemaire SAS

🟡 À SURVEILLER — 1 échéance dans ≤15 jours
  • TVA mai 2026 — deadline 20/06 — Petit Négoce

Total : 4 échéances actives
```

---

### 4.2 Alerte Telegram (agent en erreur)

Si un problème technique survient sur un agent :

```
[JM Partners] Agent tva_agent en erreur :
Connection timeout after 30s
```

→ Vous pouvez l'ignorer si c'est ponctuel (l'agent réessaiera au prochain cycle). Si c'est répété, contactez le support.

---

### 4.3 Email de relance client (envoyé automatiquement)

Exemple d'email que votre client reçoit :

```
De : contact@jmpartners.fr
À : client@dupont-sarl.fr
Objet : Relance : documents manquants — Dossier Bilan 2025

Bonjour,

Nous n'avons pas encore reçu les documents suivants nécessaires
à l'établissement de votre bilan 2025 :
- Grand Livre
- Balance comptable

Merci de nous les transmettre dans les meilleurs délais.

Cordialement,
Le cabinet JM Partners
```

> 💡 La tonalité est automatiquement adaptée : cordiale à J-15, ferme à J-7, urgente à J-3.

---

### 4.4 Dashboard web

Accessible à l'adresse de votre service, le dashboard affiche en temps réel :

- **Vue Kanban** : vos dossiers classés en "Documents manquants" / "En attente" / "Complet"
- **Calendrier** : les 30 prochaines échéances TVA et IS avec code couleur
- **KPIs** : nombre de dossiers actifs, alertes J-7, urgences J-3

---

## 5. ⚙️ Configuration initiale — 18 éléments à remplir

Lors de la mise en place, votre prestataire technique va vous demander 18 informations. Voici ce que c'est et où les trouver.

### Supabase (base de données — 2 éléments)
> Votre prestataire crée ces accès pour vous.

| Élément | Description |
|---------|-------------|
| `URL de la base` | L'adresse de votre base de données (ex: `https://xxxx.supabase.co`) |
| `Clé d'accès service` | Un mot de passe long qui donne accès à la base |

---

### Email sortant — SMTP (4 éléments)
> Ce sont les paramètres de votre boîte email professionnelle.

| Élément | Ce que c'est | Où le trouver |
|---------|-------------|---------------|
| `Serveur SMTP` | Le serveur d'envoi de votre messagerie | Pour Gmail : `smtp.gmail.com` |
| `Port SMTP` | Le numéro de connexion | Pour Gmail : `587` |
| `Adresse email` | L'adresse depuis laquelle les emails seront envoyés | Ex: `contact@jmpartners.fr` |
| `Mot de passe SMTP` | **Attention :** Pour Gmail, c'est un *mot de passe d'application* (pas votre mot de passe habituel). À créer dans les paramètres de sécurité Google. | Compte Google → Sécurité → Mots de passe des applications |

---

### Email entrant — IMAP (4 éléments)
> Pour que l'assistant lise vos emails reçus.

| Élément | Ce que c'est | Valeur typique |
|---------|-------------|----------------|
| `Serveur IMAP` | Le serveur de réception | Pour Gmail : `imap.gmail.com` |
| `Adresse email` | La boîte à surveiller | Même adresse que SMTP |
| `Mot de passe IMAP` | Même mot de passe d'application que SMTP | Identique |
| `Intervalle de lecture` | Fréquence de lecture des emails (en minutes) | `15` (recommandé) |

---

### Intelligence artificielle (1 élément)
> Pour la rédaction des emails de relance et la classification des emails reçus.

| Élément | Ce que c'est | Où le trouver |
|---------|-------------|---------------|
| `Clé API Anthropic` | La clé d'accès à Claude (IA) | Sur console.anthropic.com — votre prestataire peut la fournir |

---

### Notifications Telegram (2 éléments)
> Pour recevoir les alertes sur votre téléphone.

| Élément | Ce que c'est | Comment faire |
|---------|-------------|---------------|
| `Token du bot` | L'identifiant de votre bot Telegram | Créer un bot via @BotFather sur Telegram, il vous donnera un token |
| `ID du canal` | Le numéro de votre groupe ou canal Telegram | Créer un groupe, y ajouter le bot, récupérer l'ID avec votre prestataire |

---

### Rapports et configuration (5 éléments)

| Élément | Ce que c'est | Exemple |
|---------|-------------|---------|
| `Email rapports` | Votre email pour recevoir les rapports quotidiens | `michael@jmpartners.fr` |
| `Email destinataire rapports` | Identique au précédent (double configuration) | `michael@jmpartners.fr` |
| `ID cabinet` | Le nom court de votre cabinet | `jmpartners` |
| `Scheduler activé` | Est-ce que le cron doit tourner ? | `true` |
| `Heure du cycle` | À quelle heure tourne le cycle principal | `0 7 * * 1-5` = 07h00 lun-ven |

---

## 6. ✅ Premiers jours — vérifier que ça marche

Voici les 5 vérifications à faire dans les 3 premiers jours.

### Jour 1 — L'assistant démarre

**Ce que vous devez voir :**

☐ **Telegram** : un message d'alerte ou de test de votre bot Telegram (si configuré)

☐ **Dashboard** : rendez-vous sur l'adresse de votre service → vous voyez vos dossiers dans le Kanban

☐ **Rapport du lendemain matin** : vous recevez un email avec les échéances du jour

**Si rien ne se passe :** Contactez le support (voir section 7).

---

### Jour 2 — Le premier rapport

**Ce que vous devez voir :**

☐ **Email reçu à 07h00** avec le rapport d'échéances (même s'il est vide)

☐ **Table journaux** (si vous avez accès Supabase) : une ligne `orchestrator_run` avec `statut = ok`

☐ **GET /health** répond `"statut": "ok"` et `"dernier_run"` n'est pas vide

---

### Jour 3 — Test de relance

**Test à faire vous-même :**

1. Dans le dashboard, cliquez sur **"Relancer"** sur un dossier avec des documents manquants
2. Vérifiez que votre client (ou vous-même si vous avez mis votre email en test) reçoit l'email

**Si l'email n'arrive pas :**
- Vérifier les SPAM
- Vérifier que SMTP_PASSWORD est correct
- Contacter le support

---

### Tableau de bord de santé rapide

```
✅ Rapport email reçu à 07h00          → Scheduler OK
✅ Alerte Telegram reçue               → Telegram OK
✅ GET /health → statut: ok            → Service UP
✅ dernier_run.agents_ko = 0           → Tous les agents OK
✅ Email de relance test reçu          → SMTP OK
```

---

## 7. 🆘 Support — Qui contacter si problème

### Problème urgent (service arrêté, aucun rapport depuis 24h)

**Contacter votre prestataire technique directement.**

Avant d'appeler, notez :
- L'heure approximative du dernier rapport reçu
- Un exemple de message Telegram d'erreur si vous en avez reçu un
- Le résultat de : `https://votre-service.railway.app/health`

---

### Problème non urgent (une alerte manquante, un email mal formaté)

Envoyer un email au support avec :
1. La date et l'heure du problème
2. Le nom du client ou dossier concerné
3. Ce que vous attendiez vs ce que vous avez reçu

---

### Questions fréquentes

**Q : L'assistant peut-il envoyer un email à la place de mon adresse ?**
R : Oui, il utilise votre adresse email configurée dans SMTP_USER. Les clients verront votre adresse comme expéditeur.

**Q : Puis-je modifier le texte des emails de relance ?**
R : Le texte est généré automatiquement par l'IA (Claude). Il peut être personnalisé par votre prestataire si vous souhaitez un style particulier.

**Q : Que se passe-t-il si l'IA (Claude) est indisponible ?**
R : Un texte de relance standard prédéfini est utilisé automatiquement. L'email est quand même envoyé.

**Q : L'assistant peut-il rater une échéance ?**
R : Il alerte aux jours exacts J-15, J-7 et J-3. Si le service est arrêté un de ces jours précis, l'alerte ne sera pas envoyée ce jour-là mais reprendra au prochain cycle. Pour les deadlines critiques, vérifiez aussi votre calendrier manuellement.

**Q : Comment ajouter un nouveau client dans le système ?**
R : Le client doit être créé dans la table `contacts` de votre base Supabase avec son email. Votre prestataire peut le faire ou vous montrer comment.

**Q : Mes données sont-elles sécurisées ?**
R : Les données sont stockées dans votre propre instance Supabase (vous en êtes propriétaire). Les emails de relance passent par votre propre serveur SMTP. L'IA ne reçoit que le sujet et le corps des emails entrants pour les classifier.

---

*Document préparé par votre prestataire technique — Cabinet JM Partners 2026*

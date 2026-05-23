# META-AGENT — Boussole Stratégique

> Version Mai 2026 · Confidentiel

---

## Navigation rapide

- [Partie 1 — Vision & Positioning](#partie-1--vision--positioning)
- [Partie 2 — Catalogue Agents](#partie-2--catalogue-agents)
  - [Email Agent](#email-agent)
  - [LeadCommercial Agent](#leadcommercial-agent)
  - [JM Partners Agent](#jm-partners-agent-cabinet-comptable)
- [Partie 3 — Grille Tarifaire](#partie-3--grille-tarifaire-globale)
- [Partie 4 — Playbook Commercial](#partie-4--playbook-commercial)
- [Partie 5 — Onboarding Client](#partie-5--onboarding-client-type)
- [Partie 6 — Métriques de Succès](#partie-6--métriques-de-succès-par-client)
- [Partie 7 — Risques & Garanties](#partie-7--risques--garanties)

---

## PARTIE 1 — VISION & POSITIONING

### 💡 Proposition de valeur

> **"On automatise les tâches répétitives à haute valeur de vos équipes grâce à des agents IA spécialisés, déployés en 2 semaines, mesurables dès le premier mois."**

Ce n'est pas un chatbot. Ce n'est pas une "solution no-code". Ce sont des agents autonomes qui s'intègrent dans vos workflows existants (Gmail, Supabase, IMAP, APIs fiscales) et produisent des résultats concrets : leads qualifiés, relances envoyées, rapports générés — sans intervention humaine.

### 🎯 Cibles prioritaires

| Cible | Douleur principale | Agent le plus adapté |
|---|---|---|
| Cabinet expertise comptable (10-50 collab.) | Oublis déclarations, relances manuelles, dossiers en retard | JM Partners Agent |
| Cabinet d'assurance / CGPI | Emails entrants non triés, perte de prospects chauds | Email Agent |
| PME avec équipe commerciale B2B | Prospection manuelle, leads IDF non détectés | LeadCommercial Agent |
| Cabinet de recrutement | Emails candidats non classés, suivi manuel | Email Agent |

### 💰 Modèle économique

```
Setup fee (unique)     → intégration technique + configuration ICP/templates
Abonnement mensuel     → SaaS par agent actif en production
Maintenance incluse    → corrections bugs, mises à jour APIs, monitoring
Options                → formations, dashboards custom, intégrations sur mesure
```

### 🏆 Avantages concurrentiels

- ✅ **Temps réel** : résultats mesurables dès la première semaine
- ✅ **Pas de lock-in** : code sur GitHub, client peut reprendre la main
- ✅ **Zéro donnée utilisée pour entraîner des modèles** (Anthropic API, pas fine-tuning)
- ✅ **308 tests automatisés** : fiabilité prouvée avant déploiement
- ✅ **Déploiement Railway** : zéro infra à gérer côté client
- ✅ **RGPD EU** : données hébergées en Europe, accès nominatif, logs auditables

---

## PARTIE 2 — CATALOGUE AGENTS

---

## EMAIL AGENT

*Nom commercial : **Mika Email Intelligence***

---

<details>
<summary><strong>📥 gmail_fetcher</strong> — Collecte automatique des emails Gmail</summary>

### gmail_fetcher

**Rôle en 1 phrase**
Se connecte à Gmail via OAuth2 et récupère les emails non lus, normalisés et prêts à être analysés.

**Problème client résolu**
Le client passe 30-45 minutes chaque matin à trier manuellement sa boîte mail, en cherchant les messages importants parmi les newsletters, les relances fournisseurs et les prospects. Certains emails critiques sont lus trop tard.

**Ce que fait l'agent concrètement**
- 🔗 Se connecte à Gmail via OAuth2 (aucun mot de passe transmis)
- 📥 Récupère les N derniers emails non lus (configurable)
- 🧹 Normalise chaque email en dict structuré (expéditeur, sujet, corps, date)
- 🔑 Identifie chaque email par un `message_id` unique (anti-doublon)
- ⚡ S'exécute en quelques secondes, sans interaction humaine

**Inputs requis**
- Accès Gmail via OAuth2 (token configuré 1 fois)
- Variable `GMAIL_TOKEN_B64` dans Doppler

**Outputs livrés**
- Liste d'emails structurés prête pour analyse Claude
- Logs détaillés de chaque exécution

**KPIs de succès mesurables**
- Temps de collecte : < 10 secondes pour 20 emails
- Taux de doublons : 0% (dédup par message_id)
- Disponibilité : 100% (testé 7j/7)

**Temps d'onboarding client**
2 heures (configuration OAuth2 + test)

**Checklist onboarding**
- [ ] Créer un projet Google Cloud avec Gmail API activée
- [ ] Générer les credentials OAuth2 (client_id, client_secret)
- [ ] Effectuer le premier consentement OAuth (flux navigateur, 1 fois)
- [ ] Encoder le token en base64 et l'ajouter dans Doppler
- [ ] Tester avec `--once --dry-run`

**Valorisation interne**
- Dev : 3j (inclus dans le setup Email Agent)
- Infra : inclus dans Railway (< 2€/mois)
- API Gmail : gratuit

**Prix de vente** → inclus dans l'offre Email Agent packagée

</details>

---

<details>
<summary><strong>🧠 email_analyzer</strong> — Classification IA des emails par Claude</summary>

### email_analyzer

**Rôle en 1 phrase**
Envoie chaque email à Claude Sonnet 4 avec le profil client ICP et classifie l'intent (prospect chaud, froid, hors-cible, question technique).

**Problème client résolu**
Sans IA, le client doit lire chaque email pour décider si c'est un prospect chaud ou une perte de temps. Avec 50+ emails/jour, c'est 45 min de travail intellectuel à faible valeur.

**Ce que fait l'agent concrètement**
- 🤖 Envoie chaque email à Claude Sonnet 4 avec contexte ICP
- 🏷️ Classifie : prospect chaud / froid / hors-cible / question technique / autre
- 📝 Extrait : priorité, résumé en 2 phrases, action recommandée, brouillon de réponse
- 🧠 Adapte l'analyse selon le profil client configuré (secteur, cibles, critères)
- ⚡ Traite un email en < 3 secondes

**Inputs requis**
- `ANTHROPIC_API_KEY` dans Doppler
- Fichier ICP client (configuré une fois lors de l'onboarding)

**Outputs livrés**
- Chaque email classifié avec : intent, priorité, résumé, action, brouillon réponse
- Données structurées pour le rapport HTML

**KPIs de succès mesurables**
- Précision classification : > 90% (validé sur 50 emails réels)
- Temps d'analyse : < 3 sec/email
- Économie estimée : 30-45 min/jour/utilisateur

**Temps d'onboarding client**
3 heures (rédaction profil ICP + calibration sur 20 emails test)

**Checklist onboarding**
- [ ] Rédiger le profil ICP avec le client (cibles, secteurs, critères prospect chaud)
- [ ] Tester sur 20 emails réels → valider la classification
- [ ] Ajuster le prompt ICP si précision < 85%
- [ ] Valider avec le client sur 1 semaine réelle

**Valorisation interne**
- Dev : inclus dans Email Agent
- API Claude : ~0,50-2€/mois selon volume (Claude Sonnet 4, haiku en fallback)

**Prix de vente** → inclus dans l'offre Email Agent packagée

</details>

---

<details>
<summary><strong>💾 supabase_writer</strong> — Persistance et KPIs en base</summary>

### supabase_writer

**Rôle en 1 phrase**
Sauvegarde chaque email analysé dans Supabase et calcule les KPIs hebdomadaires (temps économisé, valeur générée).

**Problème client résolu**
Sans persistance, les analyses disparaissent. Le client ne peut pas mesurer le ROI de l'outil ni suivre les tendances (quel % de prospects chauds ce mois vs le mois dernier).

**Ce que fait l'agent concrètement**
- 💾 Persiste chaque email analysé dans la table `emails`
- 🔑 Gère les doublons par `message_id` (idempotent)
- 📊 Calcule les KPIs de session (nb emails, % prospects, temps économisé, valeur estimée)
- 📈 Sauvegarde les KPIs dans la table `email_kpis` pour le suivi mensuel

**Inputs requis**
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` dans Doppler
- Tables `emails` et `email_kpis` créées (script SQL fourni)

**Outputs livrés**
- Historique complet des emails analysés en base
- KPIs exportables (CSV, dashboard)

**Valorisation interne** → inclus dans Email Agent

**Prix de vente** → inclus dans l'offre Email Agent packagée

</details>

---

<details>
<summary><strong>📝 reporter</strong> — Génération du rapport HTML</summary>

### reporter

**Rôle en 1 phrase**
Génère un rapport HTML responsive, organisé par priorité, avec statistiques et tableau des emails de la session.

**Problème client résolu**
Le client veut recevoir une synthèse lisible chaque matin, sans ouvrir un dashboard ou une interface complexe — directement dans sa boîte mail, sur mobile comme sur desktop.

**Ce que fait l'agent concrètement**
- 📝 Agrège tous les emails analysés de la session
- 📊 Calcule les statistiques : nb total, % par catégorie, temps économisé
- 🎨 Génère un HTML responsive (compatible webmail, mobile, desktop)
- 📋 Organise par priorité décroissante (urgent → normal → info)
- ⚡ Aucun appel réseau — logique pure, < 1 seconde

**Inputs requis**
- Liste des emails analysés (sortie de `email_analyzer`)

**Outputs livrés**
- Fichier HTML complet prêt à envoyer par email

</details>

---

<details>
<summary><strong>📤 sender</strong> — Envoi du rapport par email SMTP</summary>

### sender

**Rôle en 1 phrase**
Envoie le rapport HTML généré par email SMTP à l'adresse configurée, sans jamais bloquer le pipeline.

**Inputs requis**
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` dans Doppler
- `RAPPORT_EMAIL` (destinataire)

**Outputs livrés**
- Email HTML reçu chaque matin avec le rapport
- Log de confirmation d'envoi

</details>

---

<details>
<summary><strong>💬 telegram_sender</strong> — Alerte Telegram avec KPIs</summary>

### telegram_sender

**Rôle en 1 phrase**
Envoie une alerte Telegram concise avec les KPIs clés de la session : nb emails traités, % prospects chauds, action recommandée.

**Inputs requis**
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` dans Doppler

**Outputs livrés**
- Message Telegram formaté Markdown avec les KPIs
- Notification mobile instantanée

</details>

---

<details>
<summary><strong>🎛️ Orchestrateur Email Agent</strong> — Coordinateur du pipeline</summary>

### Orchestrateur Email Agent

**Rôle en 1 phrase**
Coordonne les 6 agents en séquence, gère les erreurs et les retries, loggue chaque étape.

**Ce que fait l'agent concrètement**
- ⏰ Planifie l'exécution à 08h45 via APScheduler (ou `--once`)
- 🔄 Coordonne : fetch → analyze (boucle) → persist → build → send → kpis → telegram
- 🛡️ Erreurs non-bloquantes : si `supabase_writer` échoue, le rapport est quand même envoyé
- 📋 Loggue chaque étape avec timing et statut
- 🚩 Flag `--dry-run` disponible pour tester sans envoi réel

</details>

---

### 📦 Offre packagée : Mika Email Intelligence

| Élément | Détail |
|---|---|
| **Nom commercial** | Mika Email Intelligence |
| **Agents inclus** | 6 (gmail_fetcher, email_analyzer, supabase_writer, reporter, sender, telegram_sender) |
| **Setup fee** | **1 500 € HT** |
| **Abonnement mensuel** | **290 € HT/mois** |
| **ROI client estimé** | 1 200-2 000 €/mois (30-45 min/jour × taux horaire) |
| **Délai déploiement** | 2 semaines |
| **Cible idéale** | Cabinet avec +50 emails/jour, une personne qui trie manuellement |

**Pitch 30 secondes :**
> "Chaque matin à 8h45, votre boîte mail est analysée automatiquement par une IA. Vous recevez un rapport HTML classé par priorité — prospect chaud, question technique, info — avec un brouillon de réponse pour chaque email important. Résultat : vous gagnez 30-45 minutes par jour, zéro email important raté, et un dashboard qui mesure votre ROI chaque semaine."

**Cas d'usage démo :**
> Montrer un vrai rapport HTML reçu ce matin. Cliquer sur un "prospect chaud" identifié par Claude. Montrer le brouillon de réponse généré. Ouvrir Telegram pour montrer l'alerte KPIs reçue à 08h46. Puis ouvrir Supabase : 47 emails en base, 12% prospects chauds cette semaine vs 8% la semaine dernière. Durée : 8 minutes.

---

## LEADCOMMERCIAL AGENT

*Nom commercial : **Mika Lead Hunter***

---

<details>
<summary><strong>🏢 sirene_fetcher</strong> — Collecte des nouvelles entreprises IDF</summary>

### sirene_fetcher

**Rôle en 1 phrase**
Interroge l'API INSEE Sirene chaque nuit pour récupérer toutes les nouvelles immatriculations d'Île-de-France du jour.

**Problème client résolu**
Une nouvelle entreprise SAS créée hier à Paris a besoin d'un comptable, d'un assureur, d'un logiciel de gestion — aujourd'hui. Mais personne ne la détecte avant qu'elle aille chercher elle-même sur Google. Cet agent détecte ces entreprises le lendemain de leur création.

**Ce que fait l'agent concrètement**
- 🌙 S'exécute chaque nuit à 02h00
- 🏛️ Interroge l'API INSEE Sirene pour les départements 75, 77, 78, 91, 92, 93, 94, 95
- 🔍 Filtre par forme juridique (SAS, SARL, EURL, SA...) et code NAF
- 📋 Normalise chaque entreprise : siren, siret, denomination, naf, dept, commune, date immatriculation

**Inputs requis**
- `SIRENE_API_TOKEN` dans Doppler
- Date de recherche (défaut : hier)

**Outputs livrés**
- Liste d'entreprises nouvellement créées, structurées et filtrées

**KPIs de succès mesurables**
- Nb entreprises détectées/nuit : 50-200 selon la configuration
- Temps d'exécution : < 2 minutes
- Taux d'erreur API Sirene : < 1%

**Checklist onboarding**
- [ ] Obtenir un token API INSEE Sirene (gratuit, formulaire en ligne)
- [ ] Configurer les codes NAF cibles (secteurs d'intérêt du client)
- [ ] Configurer les formes juridiques cibles
- [ ] Définir le seuil de score ICP (défaut : 50)
- [ ] Test dry-run sur 1 semaine de données historiques

</details>

---

<details>
<summary><strong>🔎 pappers_enricher</strong> — Enrichissement données dirigeant et financier</summary>

### pappers_enricher

**Rôle en 1 phrase**
Enrichit chaque lead avec les données Pappers : dirigeant, capital social, date de création, score santé financière.

**Problème client résolu**
Le commercial sait qu'une entreprise vient d'être créée, mais il ne sait pas qui appeler, quel est le capital, si la société est solide. Appeler à l'aveugle perd du temps et nuit à l'image.

**Ce que fait l'agent concrètement**
- 📊 Interroge l'API Pappers pour chaque lead qualifié
- 👤 Récupère : nom/prénom dirigeant, email si disponible
- 💶 Capital social, date création exacte
- 📈 Score santé financière (0-100)
- 🌐 Site web si disponible
- 🛡️ Dégradation gracieuse : si Pappers absent, le lead passe quand même

**Inputs requis**
- `PAPPERS_API_KEY` dans Doppler (optionnel mais recommandé)

**Outputs livrés**
- Lead enrichi avec données dirigeant et financières

</details>

---

<details>
<summary><strong>⚖️ icp_scorer</strong> — Scoring 0-100 selon critères ICP</summary>

### icp_scorer

**Rôle en 1 phrase**
Note chaque lead de 0 à 100 selon les critères ICP configurés et explique le score en langage naturel.

**Problème client résolu**
Pas tous les leads se valent. Sans scoring, le commercial appelle dans l'ordre alphabétique ou chronologique — et perd du temps sur des prospects hors-cible.

**Ce que fait l'agent concrètement**
- ⚖️ Calcule un score 0-100 basé sur des règles métier
- 🎯 Critères pondérés : secteur NAF (+30), zone géographique (+25), forme juridique (+20), capital (+15), signal timing (+10)
- 📝 Génère une explication du score : "Score 82/100 — SAS en zone Paris 75, secteur technologie, créée hier : signal chaud maximal"
- 🚦 Flag `qualified: bool` (score > seuil configuré)

**Inputs requis**
- Configuration ICP client (défini lors de l'onboarding)
- `LEAD_SCORE_THRESHOLD` (défaut : 50)

**Outputs livrés**
- Score 0-100 + explication + flag qualified

**KPIs de succès mesurables**
- 76% des leads IDF qualifiés en moyenne (données test réelles)
- 11 alertes Telegram envoyées sur vraies entreprises en test

</details>

---

<details>
<summary><strong>🔒 supabase_storage</strong> — Persistance avec verrou anti-doublon</summary>

### supabase_storage

**Rôle en 1 phrase**
Sauvegarde les leads scorés dans Supabase avec gestion des doublons par SIREN et verrou multi-cabinets.

**Problème client résolu**
Si deux cabinets utilisent le même outil, ils ne doivent pas contacter la même entreprise. Le verrou `lead_locks` garantit l'exclusivité du lead.

**Ce que fait l'agent concrètement**
- 🔒 Vérifie le verrou anti-doublon par SIREN dans `lead_locks`
- 💾 Insère le lead dans la table `leads` si non verrouillé
- 🔄 Met à jour le statut des leads existants
- 🚫 Retourne `False` si SIREN déjà pris par un autre cabinet

**Tables Supabase**
- `leads` : tous les champs enrichis + score + statut
- `lead_locks` : verrou SIREN → cabinet_id

</details>

---

<details>
<summary><strong>📲 telegram_notifier</strong> — Alerte Telegram pour les leads qualifiés</summary>

### telegram_notifier

**Rôle en 1 phrase**
Envoie une alerte Telegram instantanée pour chaque lead score > 70, avec nom, SIREN, secteur, score et lien Pappers.

**Problème client résolu**
Le commercial est en déplacement. Il ne va pas vérifier un dashboard. Il a besoin d'être alerté sur son téléphone, immédiatement, quand un lead chaud vient d'être créé.

**Ce que fait l'agent concrètement**
- 📲 Envoie un message Telegram Markdown formaté
- 🏢 Contenu : nom entreprise, SIREN, secteur NAF, score, ville, lien Pappers
- 🔔 Notification mobile instantanée (< 1 seconde après la persistance)
- 🔇 Silent si `TELEGRAM_BOT_TOKEN` absent (no crash)

**Message type :**
```
🎯 Nouveau lead qualifié — Score 87/100

🏢 TECH SOLUTIONS SAS
📍 Paris 8e (75)
🔢 SIREN: 123 456 789
🏭 Secteur: 6201Z — Programmation informatique
💶 Capital: 10 000 €
👤 Dirigeant: Jean Dupont
📅 Créée hier

🔗 Voir sur Pappers →
```

</details>

---

<details>
<summary><strong>🎛️ Orchestrateur LeadCommercial</strong> — Pipeline nocturne automatisé</summary>

### Orchestrateur LeadCommercial

**Rôle en 1 phrase**
APScheduler lance le pipeline chaque nuit à 02h00 lun-ven. Gère les locks, les retries, et les logs de stats.

**Ce que fait l'agent concrètement**
- ⏰ Cron 02h00 Europe/Paris, lun-ven
- 📋 Charge l'ICP depuis Supabase (si `CABINET_ID` configuré)
- 🔄 Coordonne : fetch → enrich → score → persist → notify
- 📊 Log des stats finales : X leads scrapés, Y qualifiés, Z alertes envoyées
- 🚩 Flags : `--date YYYY-MM-DD` (historique), `--dry-run` (test sans écriture)

</details>

---

### 📦 Offre packagée : Mika Lead Hunter

| Élément | Détail |
|---|---|
| **Nom commercial** | Mika Lead Hunter |
| **Agents inclus** | 5 (sirene_fetcher, pappers_enricher, icp_scorer, supabase_storage, telegram_notifier) |
| **Setup fee** | **1 800 € HT** |
| **Abonnement mensuel** | **390 € HT/mois** |
| **ROI client estimé** | 2 000-5 000 €/mois (valeur 1 client signé = X × abonnement mensuel) |
| **Délai déploiement** | 2 semaines |
| **Cible idéale** | PME avec commercial terrain, cabinet qui prospecte de nouveaux clients en IDF |

**Pitch 30 secondes :**
> "Chaque nuit, pendant que vous dormez, une IA scrute toutes les nouvelles entreprises créées en Île-de-France — Paris, banlieue — et vous envoie une alerte Telegram pour chaque prospect qui correspond exactement à vos critères. Vous vous réveillez avec une liste de leads chauds, enrichis avec le nom du dirigeant, le capital, le secteur. Résultat : vos commerciaux n'appellent plus dans le vide — ils appellent les bonnes personnes, au bon moment."

**Cas d'usage démo :**
> Ouvrir Telegram : montrer les 3 alertes reçues cette nuit. Cliquer sur le premier lead — lien Pappers. Ouvrir Supabase : 47 leads scrapés cette nuit, 11 qualifiés score > 70. Montrer le dashboard LeadCommercial avec les filtres ICP. Durée : 10 minutes.

---

## JM PARTNERS AGENT (Cabinet Comptable)

*Nom commercial : **Mika Compta Pilot***

---

<details>
<summary><strong>📬 mail_handler</strong> — Traitement des emails entrants cabinet</summary>

### mail_handler

**Rôle en 1 phrase**
Lit les emails entrants IMAP du cabinet, identifie le client, classifie la demande et retourne une réponse structurée à l'orchestrateur.

**Problème client résolu**
Le gestionnaire reçoit 20-30 emails/jour de clients. Il doit lire chacun, identifier de quel client et dossier il s'agit, classer la demande (document manquant, question TVA, relance de client, urgence). C'est 1-2h de travail administratif pur par jour.

**Ce que fait l'agent concrètement**
- 📬 Lit les emails IMAP non lus du cabinet
- 👤 Identifie le client par matching email/nom dans la table `contacts`
- 🏷️ Classifie la demande : document_manquant / question_tva / relance / autre
- 📋 Résout le dossier associé dans `dossiers`
- ↩️ Retourne une réponse structurée à l'orchestrateur

**Inputs requis**
- `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD` dans Doppler
- Tables `contacts` et `dossiers` renseignées

**Outputs livrés**
- Type de demande classifié
- contact_id + dossier_id résolus
- Prêt pour `relance_handler` ou `document_checker`

**Tables Supabase** : `contacts`, `dossiers`

**Checklist onboarding**
- [ ] Configurer l'accès IMAP du cabinet (ou Gmail API)
- [ ] Importer les contacts clients dans `contacts`
- [ ] Importer la liste des dossiers actifs dans `dossiers`
- [ ] Tester sur 10 emails réels du cabinet

</details>

---

<details>
<summary><strong>📋 document_checker</strong> — Vérification pièces manquantes par dossier</summary>

### document_checker

**Rôle en 1 phrase**
Interroge Supabase pour lister les pièces manquantes par dossier et calcule les niveaux d'urgence (J-15, J-7, J-3, J-0).

**Problème client résolu**
Le gestionnaire doit se souvenir, pour chaque dossier, quelles pièces il a reçues et lesquelles manquent. Sans outil, des dossiers entiers attendent en silence — jusqu'au jour J où il est trop tard.

**Ce que fait l'agent concrètement**
- 📋 Compare les documents reçus (table `documents`) avec la liste attendue
- ⏰ Calcule la deadline selon le type de dossier (bilan, TVA mensuelle, TVA trimestrielle, IS)
- 🚦 Attribue un niveau d'urgence : J-15 / J-7 / J-3 / J-0
- 📝 Retourne la liste précise des pièces manquantes avec leur statut

**Tables Supabase** : `documents`, `dossiers`

</details>

---

<details>
<summary><strong>✉️ relance_handler</strong> — Relances clients automatiques personnalisées</summary>

### relance_handler

**Rôle en 1 phrase**
Compose et envoie automatiquement un email de relance personnalisé au client pour les pièces manquantes, en évitant les doublons (48h entre deux relances).

**Problème client résolu**
Rédiger une relance client prend 5-10 minutes : trouver le bon ton, personnaliser avec le prénom, lister les pièces manquantes, ne pas être trop agressif. Multiplié par 10 dossiers/semaine, c'est 1h de travail. Et souvent, on oublie de relancer.

**Ce que fait l'agent concrètement**
- 🤖 Génère le corps de l'email via Claude API (ton professionnel, personnalisé)
- 📋 Inclut la liste précise des documents manquants
- 📅 Inclut la deadline et le niveau d'urgence
- 🔕 Anti-doublon : pas 2 relances au même client dans les 48h
- 📨 Envoie via SMTP et log dans `relances`

**Tables Supabase** : `relances`
**API** : Claude Sonnet 4 (génération email), SMTP (envoi)

**KPIs de succès mesurables**
- Taux de réponse aux relances automatiques : mesuré mensuellement
- Nb relances envoyées/semaine : objectif 100% des dossiers en retard
- Temps économisé : 1h/semaine par gestionnaire

</details>

---

<details>
<summary><strong>🧾 tva_agent</strong> — Surveillance déclarations TVA</summary>

### tva_agent

**Rôle en 1 phrase**
Surveille les déclarations TVA à venir et alerte le comptable J-15/J-7/J-3 par email + Telegram.

**Problème client résolu**
Un oubli de déclaration TVA = pénalités DGFiP. Le comptable jongle entre les régimes mensuel, trimestriel et réel simplifié. Sans surveillance automatique, le risque d'oubli est réel.

**Ce que fait l'agent concrètement**
- 📅 Scanne `declarations_tva` pour les échéances dans les 30 prochains jours
- 🔍 Vérifie si les pièces nécessaires sont disponibles
- 📧 Alerte email J-15 (digest), J-7 (direct), J-3 (urgent)
- 💬 Alerte Telegram J-3 et J-0

**Tables Supabase** : `declarations_tva`

</details>

---

<details>
<summary><strong>📅 echeance_agent</strong> — Tableau de bord échéances 30 jours</summary>

### echeance_agent

**Rôle en 1 phrase**
Scanne toutes les tables d'échéances, priorise par urgence (🔴🟠🟢) et génère un rapport quotidien.

**Ce que fait l'agent concrètement**
- 🔍 Scanne : `acomptes_is`, `declarations_tva`, `dossiers` (dates clôture)
- 🚦 Priorise : J-0/J-3 🔴, J-7 🟠, J-15 🟢
- 📊 Génère un rapport HTML quotidien avec calendrier des 30 prochains jours
- 📧 Envoie par email chaque matin
- 💬 Résumé Telegram avec les urgences du jour

**Tables Supabase** : `acomptes_is`, `declarations_tva`

</details>

---

<details>
<summary><strong>🔐 cloture_handler</strong> — Détection et procédure de clôture mensuelle</summary>

### cloture_handler

**Rôle en 1 phrase**
Détecte les dossiers en fin de mois et déclenche la procédure de clôture comptable, avec alerte au comptable responsable.

**Ce que fait l'agent concrètement**
- 📅 Détecte le dernier jour ouvré du mois
- 🔍 Identifie les dossiers arrivant en clôture dans `dossiers`
- ✅ Vérifie la disponibilité des pièces de clôture dans `documents`
- 📧 Notifie le comptable responsable par email + Telegram
- 📝 Log dans `journaux` (action="cloture_check")

**Tables Supabase** : `dossiers`, `documents`, `journaux`

</details>

---

<details>
<summary><strong>💶 acompte_is_agent</strong> — Surveillance acomptes Impôt sur les Sociétés</summary>

### acompte_is_agent

**Rôle en 1 phrase**
Surveille les acomptes IS et alerte J-15/J-7/J-3 avec le montant précis et la deadline.

**Ce que fait l'agent concrètement**
- 💶 Scanne `acomptes_is` pour les échéances à venir (4 acomptes/an)
- 💰 Rappelle le montant estimé et la date limite
- 📧 Alerte email + Telegram selon l'urgence
- ✅ Marque comme envoyé pour éviter les doublons

**Tables Supabase** : `acomptes_is`

</details>

---

<details>
<summary><strong>📊 bilan_agent</strong> — Suivi préparation des bilans annuels</summary>

### bilan_agent

**Rôle en 1 phrase**
Détecte les dossiers bilan à préparer et alerte J-30/J-15/J-7 selon la disponibilité des pièces.

**Ce que fait l'agent concrètement**
- 📅 Identifie les dossiers dont la date de clôture d'exercice approche
- 📋 Vérifie la disponibilité des pièces (documents, relevés, factures)
- 📊 Calcule le taux de complétude (X/Y pièces reçues)
- 📧 Alerte J-30 (anticipation), J-15 (relance), J-7 (urgence)

**Tables Supabase** : `dossiers`, `documents`

</details>

---

<details>
<summary><strong>📑 declaration_is_agent</strong> — Surveillance déclarations IS annuelles</summary>

### declaration_is_agent

**Rôle en 1 phrase**
Surveille les déclarations IS annuelles et prépare un résumé des éléments disponibles.

**Ce que fait l'agent concrètement**
- 📑 Scanne `declarations_is` pour les échéances annuelles
- 📋 Liste les éléments disponibles vs manquants
- 📊 Calcule les montants prévisionnels IS
- 📧 Alerte J-30/J-15/J-7 avant la deadline DGFiP

**Tables Supabase** : `declarations_is`, `dossiers`

</details>

---

<details>
<summary><strong>🔔 notification_agent</strong> — Hub central de toutes les alertes</summary>

### notification_agent

**Rôle en 1 phrase**
Hub central : reçoit les alertes de tous les agents, choisit le bon canal selon l'urgence, déduplique sur 24h.

**Problème client résolu**
Sans hub, chaque agent envoie ses propres notifications → le comptable reçoit 15 Telegram/jour et arrête de les lire. Le hub consolide, priorise et déduplique.

**Ce que fait l'agent concrètement**
- 🔔 Reçoit les alertes de tous les agents (tva, echeance, bilan, is, cloture...)
- 🧠 Choisit le canal : J-3 → Telegram immédiat / J-7 → email direct / J-15 → email digest
- 🔕 Déduplique : pas 2 notifications identiques dans les 24h (table `notification_log`)
- 📊 Log toutes les notifications envoyées pour audit

**Tables Supabase** : `notification_log`

</details>

---

<details>
<summary><strong>🎛️ Orchestrateur JM Partners</strong> — Coordinateur multi-agents</summary>

### Orchestrateur JM Partners

**Rôle en 1 phrase**
APScheduler exécute un cycle complet toutes les 30 minutes. Coordonne les 9 agents sans logique métier propre.

**Ce que fait l'orchestrateur**
- ⏰ APScheduler : cycle toutes les 30 minutes en production
- 📬 Flux email : mail_handler → document_checker → relance_handler → notification_agent
- 📅 Flux planifié : tva_agent + echeance_agent + cloture_handler + acompte_is_agent + bilan_agent + declaration_is_agent → notification_agent
- 🛡️ Erreurs isolées par agent (un agent en erreur ne bloque pas les autres)
- 📋 Log de chaque cycle avec stats (nb relances, nb alertes, nb erreurs)
- 🚩 Flag `--dry-run` : test complet sans envoi ni écriture

</details>

---

### 📦 Offre packagée : Mika Compta Pilot

| Élément | Détail |
|---|---|
| **Nom commercial** | Mika Compta Pilot |
| **Agents inclus** | 9 + orchestrateur (mail_handler, document_checker, relance_handler, tva_agent, echeance_agent, cloture_handler, acompte_is_agent, bilan_agent, declaration_is_agent, notification_agent) |
| **Dashboard inclus** | Kanban dossiers + calendrier échéances + bouton dry-run |
| **Setup fee** | **3 500 € HT** |
| **Abonnement mensuel** | **590 € HT/mois** |
| **ROI client estimé** | 3 000-6 000 €/mois (2-3h/jour × taux horaire gestionnaire) |
| **Délai déploiement** | 4 semaines |
| **Cible idéale** | Cabinet 10-30 collaborateurs, 200-500 dossiers actifs |

**Pitch 30 secondes :**
> "Imaginez que chaque dossier de votre cabinet soit surveillé 24h/24 par une IA : dès qu'un document manque, le client reçoit automatiquement une relance personnalisée. Dès qu'une échéance TVA ou IS approche, vous êtes alerté sur Telegram avant qu'il soit trop tard. Votre dashboard vous montre en temps réel quels dossiers sont en retard, lesquels sont complets, et ce qui doit être traité en priorité ce matin. Résultat : zéro oubli, 2-3h de travail administratif par jour en moins par gestionnaire."

**Cas d'usage démo :**
> Ouvrir le dashboard FastAPI. Montrer le kanban : 3 dossiers en rouge (documents manquants urgents), 7 en orange (relances à envoyer), 12 en vert (complets). Cliquer sur un dossier rouge → voir la liste des pièces manquantes + la relance déjà envoyée automatiquement il y a 2h. Ouvrir Telegram → montrer les alertes reçues ce matin pour les échéances TVA J-7. Simuler un dry-run. Durée : 15 minutes.

---

## PARTIE 3 — GRILLE TARIFAIRE GLOBALE

### Offres unitaires

| Offre | Agents inclus | Setup fee | Abonnement/mois | ROI client estimé | Déploiement | Cible idéale |
|---|---|---|---|---|---|---|
| **Mika Email Intelligence** | 6 agents email | 1 500 € | 290 € | 1 200-2 000 €/mois | 2 semaines | Cabinet +50 emails/jour |
| **Mika Lead Hunter** | 5 agents lead | 1 800 € | 390 € | 2 000-5 000 €/mois | 2 semaines | PME prospection B2B IDF |
| **Mika Compta Pilot** | 9 agents compta | 3 500 € | 590 € | 3 000-6 000 €/mois | 4 semaines | Cabinet 200-500 dossiers |

### 🎁 Bundles

| Bundle | Contenu | Setup fee | Abonnement/mois | Remise |
|---|---|---|---|---|
| **Starter** | 1 agent au choix | Prix unitaire | Prix unitaire | — |
| **Growth** | 2 agents (Email + Lead ou Email + Compta) | 2 800 € (-15%) | 560 € (-15%) | -15% |
| **Scale** | 3 agents (Email + Lead + Compta) | 5 200 € (-25%) | 970 € (-25%) | -25% |
| **Enterprise** | Agents sur mesure + SLA garanti + formation équipe | Sur devis | Sur devis | Sur devis |

### 💡 Retour sur investissement type

```
Cabinet comptable — 15 collaborateurs — 300 dossiers actifs

Avant Mika Compta Pilot :
  - 2h/jour de relances manuelles × 2 gestionnaires = 4h
  - Taux horaire gestionnaire : 45 €/h
  - Coût mensuel : 4h × 22j × 45€ = 3 960 €

Après Mika Compta Pilot :
  - 0h relances manuelles (100% automatisé)
  - 30 min/j de supervision dashboard
  - Coût mensuel abonnement : 590 €
  - ROI mensuel net : 3 960 € - 590 € = 3 370 €/mois
  - Payback setup : 3 500 € / 3 370 € = 1,04 mois
```

---

## PARTIE 4 — PLAYBOOK COMMERCIAL

### 🔄 Cycle de vente type

```
J0   → Premier contact (cold email / réseau / recommandation)
J3   → Appel découverte 30 min (qualifier le pain, le budget)
J7   → Démo 45 min (live avec données réelles)
J14  → POC gratuit 1 semaine (dry-run sur données client)
J21  → Présentation des résultats POC + proposition commerciale
J28  → Signature + onboarding
J56  → Rapport de premier mois + renouvellement confirmé
```

### 🎬 La démo idéale (45 min)

**Structure recommandée**

| Temps | Contenu | Qui |
|---|---|---|
| 0-5 min | Rappel des douleurs identifiées en découverte | Commercial |
| 5-15 min | Démo Email Agent : rapport HTML reçu ce matin, Telegram KPIs | Commercial en live |
| 15-25 min | Démo LeadCommercial : leads reçus cette nuit, dashboard | Commercial en live |
| 25-38 min | Démo JM Partners : kanban dossiers, relance envoyée, alerte TVA | Commercial en live |
| 38-42 min | Architecture & sécurité (RGPD, hébergement EU, zéro lock-in) | Commercial |
| 42-45 min | Q&A + prochaine étape (POC ou signature directe) | Commercial |

**Règle d'or :** montrer des données réelles (vrais emails, vrais leads), jamais des maquettes.

### 🔍 Les 5 questions de découverte

1. **"Combien de temps par jour votre équipe passe-t-elle sur des tâches répétitives — trier des emails, relancer des clients, chercher des leads ?"**
   → Quantifie le pain et le ROI potentiel

2. **"Est-ce qu'il vous est arrivé de rater une échéance fiscale ou de répondre trop tard à un prospect à cause du volume ?"**
   → Crée l'urgence émotionnelle

3. **"Si je vous offrais 2h de travail automatisé par jour dès la semaine prochaine, qu'en feriez-vous ?"**
   → Projette le client dans le futur, teste son ambition

4. **"Vous avez déjà essayé des outils d'automatisation ? Qu'est-ce qui n'a pas marché ?"**
   → Comprend les objections passées, positionne par rapport aux alternatives

5. **"Qui dans votre équipe serait le plus impacté positivement ? Et qui pourrait freiner le projet ?"**
   → Identifie le sponsor et les résistances internes

### 📡 Signaux d'achat à repérer

- ✅ "On a justement une réunion sur ce sujet vendredi"
- ✅ "Mon associé a le même problème, il faudrait qu'il soit dans la démo"
- ✅ "C'est combien exactement ?" (demande le prix sans qu'on l'ait mentionné)
- ✅ "On peut commencer quand ?"
- ✅ Pose des questions techniques (signe d'engagement mental)
- ✅ Partage des données / accès pendant la démo sans qu'on le demande

### 🛡️ Gestion des objections

<details>
<summary><strong>"On a déjà un prestataire"</strong></summary>

**Réponse :**
> "C'est très bien. Notre outil ne remplace pas votre prestataire actuel — il automatise les tâches que personne ne veut faire : trier les emails, envoyer des relances, surveiller les échéances. Votre prestataire peut se concentrer sur la valeur ajoutée. Est-ce qu'on peut regarder ensemble ce que fait votre prestataire actuel vs ce qu'on ferait ?"

**Objectif :** repositionner comme complémentaire, pas concurrent.

</details>

<details>
<summary><strong>"C'est trop cher"</strong></summary>

**Réponse :**
> "Je comprends. Faisons le calcul ensemble. Combien d'heures par semaine votre équipe passe sur [la tâche identifiée en découverte] ? Et quel est le coût horaire approximatif de cette personne ? ... [Calcul en direct] ... Donc on parle de X€/mois de coût actuel pour Z€/mois d'abonnement. Le ROI est à [X] semaines. Est-ce que le problème avec le prix, c'est le montant ou c'est la confiance dans le résultat ?"

**Objectif :** quantifier le coût du statu quo, puis tester si l'objection est le prix ou la confiance.

</details>

<details>
<summary><strong>"On n'est pas prêt"</strong></summary>

**Réponse :**
> "Pas de problème. Qu'est-ce qui doit se passer pour que vous soyez prêts ? Je pose la question parce que [la douleur identifiée] ne va pas se résoudre toute seule — et chaque mois sans outil, c'est [X€] de travail qui disparaît. On peut commencer par un POC d'une semaine, sans engagement, pour que vous voyiez les résultats avant de décider."

**Objectif :** comprendre le vrai blocage, proposer un POC à faible risque.

</details>

---

## PARTIE 5 — ONBOARDING CLIENT TYPE

### Semaine 1 — Discovery

- **Appel découverte 1h** : cartographie des processus actuels, identification des douleurs prioritaires
- **Accès aux systèmes** : Gmail OAuth2, base de données existante, outils en place
- **Définition de l'ICP** (pour LeadCommercial) ou mapping dossiers (pour Compta)
- **Livrable** : Document de cadrage signé + périmètre des agents déployés

### Semaine 2 — Setup

- **Configuration Supabase** : création des tables, import données existantes, activation RLS
- **Connexion des APIs** : Gmail OAuth2, Telegram bot, INSEE Sirene si LeadCommercial
- **Configuration Doppler** : tous les secrets sécurisés, zéro variable en dur
- **Déploiement Railway** : environnement de staging, Dockerfile validé
- **Livrable** : Environnement staging fonctionnel + dry-run complet réussi

### Semaine 3 — Tests & Validation

- **Dry-run complet** avec données réelles du client (1 semaine de données)
- **Ajustement** : paramètres ICP / templates relance / fréquences alertes
- **Formation utilisateur** : 1h max, interface dashboard, interprétation des rapports
- **Livrable** : Validation client sur staging + formulaire de recette signé

### Semaine 4 — Go Live

- **Passage en production** : Railway production, Doppler production, monitoring Sentry activé
- **Monitoring** : J+1 (vérification premiers résultats), J+3 (ajustements), J+7 (bilan)
- **Rapport de première semaine** automatique envoyé au client
- **Livrable** : Client autonome + rapport hebdo automatique actif + accès dashboard

### ✅ Checklist go-live universelle

- [ ] Tous les secrets dans Doppler (0 secret dans le code)
- [ ] Tests pytest ≥ 90% coverage sur les agents déployés
- [ ] Dry-run validé sur données réelles du client
- [ ] Sentry DSN configuré (monitoring erreurs)
- [ ] Langfuse configuré (monitoring LLM)
- [ ] Première exécution planifiée testée manuellement (`--once`)
- [ ] Client a accès au dashboard
- [ ] Contact d'urgence défini (Telegram direct)

---

## PARTIE 6 — MÉTRIQUES DE SUCCÈS PAR CLIENT

*Rapportées automatiquement chaque mois dans le rapport mensuel client.*

### 📧 Email Agent

| Métrique | Source | Fréquence |
|---|---|---|
| Nb emails traités / semaine | Table `emails` | Hebdomadaire |
| % prospects chauds identifiés | Table `emails` (intent=chaud) | Hebdomadaire |
| Temps économisé estimé | nb emails × 3 min | Mensuel |
| Taux d'ouverture rapports HTML | Tracking email | Mensuel |

### 🎯 LeadCommercial

| Métrique | Source | Fréquence |
|---|---|---|
| Nb leads scrapés / semaine | Table `leads` | Hebdomadaire |
| Nb leads qualifiés (score > 70) | Table `leads` (score > 70) | Hebdomadaire |
| Nb alertes Telegram envoyées | Logs Telegram | Hebdomadaire |
| Taux de conversion leads → contacts | Mise à jour manuelle statut | Mensuel |

### 🏢 JM Partners

| Métrique | Source | Fréquence |
|---|---|---|
| Nb relances automatiques envoyées | Table `relances` | Hebdomadaire |
| Taux de réponse aux relances | Table `relances` (statut répondu) | Mensuel |
| Nb dossiers clôturés à temps | Table `dossiers` | Mensuel |
| Nb alertes TVA/IS avant deadline | Table `notification_log` | Mensuel |
| Temps économisé estimé | Nb relances × 7 min | Mensuel |

---

## PARTIE 7 — RISQUES & GARANTIES

### ✅ Ce qu'on garantit

| Garantie | Détail |
|---|---|
| **Déploiement en 4 semaines** | Ou remboursement du setup fee |
| **SLA 99% uptime** | Railway + Supabase (SLA contractuels des providers) |
| **Zéro donnée utilisée pour l'entraînement** | API Anthropic (pas de fine-tuning) |
| **Conformité RGPD** | Données hébergées EU, accès nominatif, logs auditables |
| **Zéro secret hardcodé** | Tous les secrets dans Doppler, auditables à tout moment |
| **Tests automatisés** | ≥ 90% coverage avant mise en production |

### ❌ Ce qu'on ne garantit pas

| Limitation | Raison |
|---|---|
| Les résultats commerciaux | On livre l'outil, pas les ventes |
| La qualité des données INSEE Sirene | Source externe, qualité variable |
| La délivrabilité des emails | Dépend du domaine et de la réputation du client |
| Les performances Claude API | Dépend de la disponibilité Anthropic |

### 📄 Clauses contractuelles recommandées

**Clause de résiliation**
> Résiliation possible à tout moment avec préavis de 30 jours. Export des données client sous 15 jours après résiliation. Aucun frais de sortie.

**Clause de propriété du code**
> Le code est hébergé sur GitHub. En cas de résiliation, le client peut récupérer l'intégralité du code et le faire opérer par un tiers. Pas de lock-in technique.

**Clause de confidentialité**
> Toutes les données client (emails, leads, dossiers) restent propriété exclusive du client. Elles ne sont jamais utilisées pour entraîner des modèles, partagées avec des tiers, ou utilisées à des fins commerciales.

**Clause de sous-traitance IA**
> L'agent utilise l'API Anthropic Claude pour l'analyse de contenu. Anthropic s'engage contractuellement à ne pas utiliser les données API pour l'entraînement des modèles (voir [politique Anthropic](https://www.anthropic.com/privacy)).

**Clause de SLA**
> En cas d'indisponibilité > 24h non planifiée, un crédit d'un mois d'abonnement est appliqué automatiquement.

---

*Document confidentiel — META-AGENT · michael@jmpartners.fr · Mai 2026*

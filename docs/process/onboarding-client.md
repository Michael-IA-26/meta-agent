# Onboarding Client — Agent Email IA

> Guide d'intégration d'un nouveau client sur l'agent email IA.
> Public cible : commercial / chef de projet (non-développeur).
> Durée totale : 1h en présence du client.

| Version | Date | Auteur |
|---|---|---|
| v0.1 | 03/05/2026 | Jeffrey |

---

## Vue d'ensemble du parcours

L'onboarding d'un nouveau client se déroule en **4 étapes successives**, sur **environ 1 heure** :

1. **Questions ICP** (15 min) — Comprendre le métier et le ton du client
2. **Setup technique** (30 min) — Connexion Gmail, configuration, premier test
3. **Grille de validation** (15 min) — 5 critères pour valider la mise en service
4. **Suivi semaine 1** — Plan d'accompagnement les 7 premiers jours

> 💡 **Avant le rendez-vous** : envoyer au client le questionnaire d'audit `docs/process/audit-questionnaire-v0.md` pour qu'il prépare ses réponses Cat. 1 (Identité), Cat. 5 (Décisions), Cat. 6 (Risques).

---

## 1. Questions ICP (15 min)

> Objectif : préciser les détails opérationnels avant de configurer l'agent.
> Pré-requis : le questionnaire d'audit (Cat. 1 à 6) a déjà été rempli.

### 1.1 Le quotidien email du client

**Question** : *"Combien de temps passes-tu à trier tes emails chaque jour ? Et quel pourcentage de ces emails nécessitent vraiment une action de ta part ?"*

| Élément à recueillir | Valeur cible |
|---|---|
| Temps quotidien email actuel | ___ min/jour |
| Volume d'emails reçus par jour | ___ emails |
| Part nécessitant une action | ___ % |
| Heure de pic (matin/midi/soir) | ___ |

> 💡 **Pourquoi** : c'est ta **baseline**. Sans ce chiffre, impossible de mesurer le gain de temps livré.

---

### 1.2 Les emails toujours prioritaires

**Question** : *"Quels emails sont systématiquement prioritaires pour toi, peu importe le contexte ? Donne-moi 3 exemples concrets."*

Exemples typiques par secteur :
- **Cabinet comptable** : déclarations fiscales urgentes, relances Trésor Public, SOS client
- **Agence conseil** : demande de devis, validation livrable, deadline contractuelle
- **Cabinet RH** : candidat shortlisté, signature contrat, alerte légale

| Type d'email | Mots-clés à détecter | Action attendue |
|---|---|---|
| _____ | _____ | _____ |
| _____ | _____ | _____ |
| _____ | _____ | _____ |

> 💡 **Pourquoi** : ces 3 exemples vont alimenter la section "Emails HAUTE priorité" de l'ICP du client.

---

### 1.3 Les emails à ignorer ou archiver d'office

**Question** : *"À l'inverse, quels emails t'agacent ou te font perdre du temps inutilement ?"*

Exemples typiques :
- Newsletters non sollicitées
- Notifications LinkedIn / réseaux sociaux
- Relances commerciales de prestataires
- Alertes système peu critiques

| Type d'email | Domaines / expéditeurs typiques | Action attendue |
|---|---|---|
| _____ | _____ | Marquer "inutile" |
| _____ | _____ | Marquer "inutile" |

> 💡 **Pourquoi** : ces patterns alimentent la section "Emails BASSE priorité" de l'ICP.

---

### 1.4 Le ton préféré dans les réponses suggérées

**Question** : *"Quand tu réponds à un email pro, c'est plutôt formel ou plutôt direct ? Tutoiement ou vouvoiement ? Long ou court ?"*

| Critère | Choix client |
|---|---|
| Adresse | ☐ Tutoiement / ☐ Vouvoiement / ☐ Adapté au contexte |
| Registre | ☐ Très formel / ☐ Pro accessible / ☐ Décontracté |
| Longueur cible | ☐ 1-3 phrases / ☐ Un paragraphe / ☐ Long et structuré |
| Signature type | ___________________________ |

> 💡 **Pourquoi** : sans ce calibrage, l'agent va générer des réponses génériques qui ne ressemblent pas au client.

---

### 1.5 Les sujets / engagements interdits

**Question** : *"Y a-t-il des sujets ou des engagements que l'agent ne doit JAMAIS aborder ou promettre en ton nom ?"*

À creuser systématiquement :
- Engagements de prix / délais / remises
- Conseils juridiques, médicaux, fiscaux personnalisés
- Comparaisons avec la concurrence
- Données confidentielles d'autres clients

| Sujet interdit | Raison | Action de l'agent |
|---|---|---|
| _____ | _____ | Escalader vers humain |
| _____ | _____ | Escalader vers humain |

> 💡 **Pourquoi** : c'est le **garde-fou juridique et commercial**. Sans cette section, le client est exposé.

---

## 2. Setup Technique (30 min)

> Objectif : connecter l'agent email à la boîte Gmail du client et lancer un premier test.
> Pré-requis : compte Gmail actif du client + accès admin à l'agence côté Doppler.

### 2.1 Pré-requis à vérifier avant le rendez-vous

À faire **côté agence** la veille du rendez-vous :

- [ ] Le client a un **compte Gmail Workspace** (pas Outlook, pas une boîte @free.fr)
- [ ] Le projet **Google Cloud** dédié au client est créé (par Mika)
- [ ] Les **identifiants OAuth Gmail** sont générés (`credentials.json` disponible)
- [ ] Le **secret Doppler** `<CLIENT_ID>_GMAIL_OAUTH` est configuré
- [ ] Le **prompt système** intégrant l'ICP du client est en base Supabase

> ⚠️ Si l'un de ces 5 points manque, **reporter le rendez-vous**. Ne pas commencer l'onboarding sans.

À faire **côté client** la veille :

- [ ] Le client a accepté de donner accès à sa boîte Gmail (consentement écrit)
- [ ] Le client a confirmé les **5 emails représentatifs** envoyés en pièce jointe (pour le test final)

---

### 2.2 Étape 1 — Connexion Gmail OAuth (10 min)

**Action** : autoriser l'agent à lire/analyser les emails du client.

1. Sur l'écran de l'agent, ouvrir le **portail d'onboarding** : `https://onboarding.meta-agent.fr/<client_id>`
2. Cliquer sur **"Connecter Gmail"**
3. Le client est redirigé vers la **page de consentement Google**
4. Le client se connecte avec **son compte Gmail pro**
5. Le client coche les permissions demandées :
   - ☐ Lire les emails
   - ☐ Modifier les libellés (mais **pas** envoyer ni supprimer)
6. Cliquer **"Autoriser"**
7. Vérifier sur l'écran agent que le statut affiche **"✅ Gmail connecté"**

> ⚠️ Si le client refuse certaines permissions, l'agent ne pourra pas fonctionner. Re-expliquer le pourquoi de chaque permission. **Ne jamais demander la permission "envoyer en mon nom" sans validation explicite par contrat.**

---

### 2.3 Étape 2 — Configuration Doppler (5 min)

**Action côté agence uniquement** (pas devant le client) :

1. Ouvrir le projet Doppler `meta-agent`
2. Sélectionner l'environnement `client_<client_id>`
3. Vérifier que les secrets suivants sont présents :
   - `ANTHROPIC_API_KEY`
   - `<CLIENT_ID>_GMAIL_OAUTH`
   - `<CLIENT_ID>_SUPABASE_URL`
   - `<CLIENT_ID>_SUPABASE_KEY`
4. Tester avec : `doppler run --config client_<client_id> -- python apps/email_agent/sender.py --dry-run`
5. Vérifier que le terminal affiche **"✅ Configuration valide"**

> 💡 **Pourquoi Doppler** : les secrets ne sont **jamais** dans le code ni dans des fichiers `.env` partagés. Chaque client a son environnement Doppler isolé.

---

### 2.4 Étape 3 — Premier test sur 5 emails réels (10 min)

**Action devant le client** : lancer l'agent sur ses 5 derniers emails et lire les analyses ensemble.

1. Sur l'écran agent, cliquer **"Lancer un test sur 5 emails"**
2. Attendre 30-60 secondes (l'agent lit, analyse, classe)
3. Le rapport s'affiche avec pour chaque email :
   - **Priorité** : haute / moyenne / basse
   - **Catégorie** : action_requise / reponse_requise / information / inutile
   - **Résumé** en une phrase
   - **Action suggérée** (ou `null`)
   - **Réponse suggérée** (ou `null`)
4. **Avec le client**, valider chaque analyse :
   - "L'agent a-t-il bien classé cet email ?"
   - "La priorité est-elle juste à tes yeux ?"
   - "Le résumé reflète-t-il l'enjeu ?"
   - "L'action suggérée correspond-elle à ce que tu aurais fait ?"

> 💡 **Si plus de 2 erreurs sur 5** : l'ICP n'est pas calibré. Reprendre la Section 1.5 (sujets interdits) et ajuster le prompt système avant de continuer.

---

### 2.5 Étape 4 — Activation de la routine quotidienne (5 min)

**Action côté agence** : activer le scheduler pour que l'agent tourne automatiquement chaque matin.

1. Dans Doppler, vérifier que `<CLIENT_ID>_SCHEDULE` est défini (ex: `0 8 * * *` pour 8h)
2. Lancer : `doppler run --config client_<client_id> -- python apps/email_agent/scheduler.py --enable`
3. Vérifier sur Sentry que l'agent s'enregistre comme **actif**
4. Le client recevra son **premier rapport demain matin** sur :
   - 📧 Email à `<adresse_client>`
   - 📱 Telegram à `<chat_id_client>`

> ✅ **Validation** : le client a vu l'agent tourner sur ses propres emails, et il sait à quelle heure il recevra son rapport demain.

---

## 3. Grille de validation (15 min)

> Objectif : valider avec le client que l'agent est utilisable **en autonomie** dès demain.
> Si moins de 5/5 critères validés → ne pas activer la routine quotidienne et planifier une session d'ajustement.

---

### 3.1 Les 5 critères de validation

À tester avec le client, en moins de 2 minutes par critère.

| # | Critère | Question au client | OUI = | NON = |
|---|---|---|---|---|
| 1 | **Le rapport est compréhensible** | "Peux-tu lire le rapport sans formation préalable ?" | Le client lit le rapport et comprend chaque ligne en moins de 30 sec | Le client demande "ça veut dire quoi ce truc ?" sur au moins 1 ligne |
| 2 | **Les emails prioritaires sont bien identifiés** | "Sur ces 5 emails, l'agent a-t-il mis en HAUTE ce qui était vraiment urgent ?" | Au moins 4/5 priorités correctes | Plus d'1 email mal classé en priorité |
| 3 | **Les suggestions de réponse sont utilisables** | "Pourrais-tu envoyer cette suggestion de réponse telle quelle, sans réécrire ?" | Au moins 3 réponses sur 4 sont copy-paste OK (le ton est juste) | Plus d'1 réponse à réécrire entièrement |
| 4 | **Le rapport se lit en moins de 5 min** | "Combien de temps tu mettrais pour lire ce rapport quotidiennement ?" | Le client estime < 5 min/jour | Le client estime > 5 min/jour |
| 5 | **Tu recommanderais cet outil à un confrère** | "Si un confrère cabinet te demandait, tu lui parlerais de cet outil ?" | Oui, sans hésiter | Réponse hésitante ou négative |

---

### 3.2 Comment réagir selon le score

| Score | Action immédiate |
|---|---|
| **5/5** | ✅ Activer la routine quotidienne (Section 2.5). Programmer le check semaine 1 (Section 4). |
| **4/5** | 🟡 Identifier le critère NON. Si critère 2 ou 3 → ajuster l'ICP avant activation. Si critère 1 ou 4 → reformater le rapport. |
| **3/5 ou moins** | 🔴 **Ne pas activer**. Reprendre Sections 1.2-1.5 (questions ICP métier). Replanifier l'onboarding sous 3 jours. |

> 💡 **Pourquoi pas de "score moyen"** : un agent qui marche à 60% va générer plus de friction que de valeur. Le client sera mécontent et la confiance sera perdue. Mieux vaut reporter.

---

### 3.3 Documenter les frictions identifiées

Pendant l'évaluation, **noter chaque friction** observée pour la transformer en issue GitHub.

| Critère | Friction observée | Issue GitHub à ouvrir |
|---|---|---|
| _____ | _____ | `feat(email_agent): améliorer ___` |
| _____ | _____ | `fix(email_agent): corriger ___` |

> 💡 **Pourquoi** : sans ce traçage, les retours client se perdent. Chaque friction = 1 issue GitHub assignée à Mika ou Jeffrey.

---

## 4. Suivi semaine 1

> Objectif : sécuriser les 7 premiers jours d'usage et ajuster l'agent si nécessaire.
> Pré-requis : l'agent a été validé 5/5 à la grille (Section 3) et activé en routine.

---

### 4.1 Côté client — ce qu'il a à faire

**Concrètement, le client n'a presque rien à faire.** C'est là toute la valeur de l'agent.

| Jour | Action attendue | Temps |
|---|---|---|
| **J+1** | Lire le rapport quotidien à 8h45 | < 5 min |
| **J+2 à J+7** | Idem chaque matin | < 5 min/jour |
| **J+7 (rendez-vous)** | Point de bilan avec l'agence (visio 30 min) | 30 min |

> 💡 **Important** : le client n'a **pas** à corriger les analyses, ni à former l'agent. Si quelque chose cloche, c'est l'agence qui ajuste côté ICP.

---

### 4.2 Côté agence — ce que nous faisons

**Vérifications quotidiennes en J+1 à J+7** (par Jeffrey, ~10 min/jour) :

- [ ] L'agent a bien tourné (vérification Sentry → aucune erreur)
- [ ] Le rapport a bien été envoyé sur les 2 canaux (email + Telegram)
- [ ] Le coût LLM est dans la cible (< 0,50 € / jour selon ICP)
- [ ] Aucune classification visiblement aberrante (lecture rapide du rapport)

**Vérifications hebdomadaires en J+7** :

- [ ] Score de validité sur 5 emails aléatoires (objectif ≥ 80%)
- [ ] Temps gagné estimé (vs baseline Section 1.1)
- [ ] Coût total semaine vs valeur estimée (TJM × temps gagné)

> 💡 **Pourquoi cette double vigilance** : la première semaine est critique. Un client mécontent en J+3 = client perdu en J+30. Mieux vaut sur-investir le suivi initial.

---

### 4.3 Le rendez-vous bilan J+7

**Format** : visio 30 min avec le client.

**Agenda** :

| Temps | Sujet | Outil |
|---|---|---|
| 5 min | Ressenti général du client | Question ouverte |
| 10 min | Lecture commune d'un rapport au choix | Partage d'écran |
| 5 min | Identifier les 2-3 points d'ajustement prioritaires | Liste écrite |
| 5 min | Annoncer les ajustements et délai | Calendrier |
| 5 min | Question Q4 grille ("Tu recommandrais ?") | Échelle 0-10 (NPS) |

**Livrables agence post-rendez-vous** :

- [ ] Compte-rendu de 5 lignes envoyé au client sous 24h
- [ ] Issues GitHub ouvertes pour chaque ajustement
- [ ] Score NPS reporté dans `docs/clients/<client_id>/suivi.md`

> 🎯 **Critère de succès** : le client passe en mode "autonomie sereine" après J+7. Si non → planifier J+14 supplémentaire.

---

### 4.4 Quand escalader vers Mika

L'agence (côté Jeffrey ou commercial) peut gérer la plupart des ajustements seule. **Mais il faut escalader vers Mika** dans 4 cas :

| Situation | Pourquoi |
|---|---|
| Bug technique de l'agent (crash, timeout, erreur Sentry répétée) | Code à corriger |
| Demande d'évolution majeure (nouveau canal, nouveau type d'analyse) | Architecture impactée |
| Score NPS < 6 à J+7 | Risque de churn — Mika veut être au courant |
| Question juridique (RGPD, AI Act, secret professionnel) | Pas de réponse improvisée |

> 📞 **Canal d'escalade** : message Telegram dans `#meta-agent-clients` avec le tag `@mika` et la mention `[CLIENT-ID]`.

---

## Annexes

### A.1 Liens utiles

- Questionnaire d'audit : `docs/process/audit-questionnaire-v0.md`
- ICPs disponibles : `packages/prompts/icps/`
- Repo agent email : `apps/email_agent/`
- Dashboard Supabase : [à compléter par Mika]

### A.2 Contacts internes

| Rôle | Personne | Contact |
|---|---|---|
| Lead technique | Mika | michael@jmpartners.fr |
| Dev / qualité | Jeffrey | jeffrey@jmpartners.fr |

### A.3 Ressources de formation client

- Guide utilisateur agent email (PDF 1 page) : [à créer en S2]
- Vidéo de prise en main (3 min) : [à créer en S2]
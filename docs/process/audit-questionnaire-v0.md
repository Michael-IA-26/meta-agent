# Meta-Agent — Questionnaire d'audit client v0.1

> **Document interne — Usage confidentiel**
> Outil de cadrage commercial & technique

| Version | Date | Auteur / Reviewer | Statut |
|---|---|---|---|
| v0.1 — Brouillon Jeffrey | 26/04/2026 | Jeffrey · Michael | En cours |

---

## Objectif du questionnaire

Recueillir les informations indispensables auprès d'un prospect pour générer automatiquement la configuration d'un agent IA adapté à son métier.

**Mode d'emploi**

- Passé en visio ou en présentiel (45–60 min)
- L'auditeur prend des notes structurées
- Les réponses alimentent un brief JSON traité par le meta-agent
- Toutes les questions ne sont pas obligatoires : à adapter selon le contexte

---

## 1. Identité & Contexte

> Comprendre qui est le client, son contexte business, et le déclencheur qui motive le projet aujourd'hui.

### Q1.1 — L'entreprise

Quelle est l'activité principale de votre entreprise, et depuis combien de temps existe-t-elle ?

### Q1.2 — La taille

Combien de personnes travaillent dans l'entreprise au total, et combien sont concernées par le projet d'agent IA ?

### Q1.3 — L'interlocuteur

Quel est votre rôle dans l'entreprise, et qui sera le décideur final pour ce projet ?

### Q1.4 — Le déclencheur

Qu'est-ce qui vous amène à envisager un agent IA aujourd'hui plutôt qu'il y a 6 mois ou dans 6 mois ?

---

## 2. Volume & Récurrence

> Quantifier la tâche ciblée pour évaluer le ROI. Sans volume suffisant ni répétition, pas de projet IA pertinent.

### Q2.1 — Le processus à automatiser

Quelle tâche ou quel processus précis voulez-vous automatiser en priorité ? Décrivez les étapes typiques.

### Q2.2 — Le volume

Combien de fois par jour ou par semaine cette tâche est-elle réalisée actuellement ? Y a-t-il des pics (saisonniers, fin de mois...) ?

### Q2.3 — Le temps actuel

Combien de temps passe une personne sur cette tâche en moyenne ? (par occurrence, et au total par semaine)

---

## 3. Outils & Infrastructure

> Cartographier l'écosystème technique du client pour identifier les connecteurs nécessaires et les contraintes d'intégration.

### Q3.1 — Les outils principaux

Pour la tâche ciblée, quels logiciels/outils utilisez-vous au quotidien ? Merci de préciser le **nom exact** (pas juste la catégorie) pour chaque type :

- **Communication client** : Outlook, Gmail, WhatsApp Business, Slack, Teams, Zendesk...
- **CRM ou base de contacts** : HubSpot, Salesforce, Pipedrive, fichier Excel partagé, base interne...
- **Outil métier principal** : logiciel comptable, ERP, plateforme e-commerce, logiciel sectoriel...
- **Suite bureautique** : Google Workspace, Microsoft 365, LibreOffice...
- **Stockage de documents** : Google Drive, SharePoint, Dropbox, serveur local NAS...
- **Autres outils utilisés régulièrement** : (à compléter)

> **Relance entretien** : Lesquels sont en cloud, lesquels sont installés en local ?

### Q3.2 — Le canal de communication

Par quel(s) canal(canaux) vos clients/contacts vous contactent-ils principalement ? (email, téléphone, chat web, WhatsApp, formulaire...)

### Q3.3 — Les compétences techniques internes

Avez-vous une équipe ou une personne en charge de l'IT/des outils numériques en interne ? Sinon, qui s'occupe des questions techniques ?

### Q3.4 — Les contraintes existantes

Y a-t-il des outils que vous voulez absolument garder, ou au contraire des outils que vous cherchez à remplacer ?

---

## 4. Données & Connaissances

> Identifier tout ce qui peut nourrir l'agent (FAQ, procédures, historique, modèles) et qualifier la maturité documentaire du client. Sans données solides, pas d'agent pertinent.

### Q4.1 — La documentation existante

Avez-vous déjà des documents de référence pour cette tâche ? (FAQ, procédures internes, guides utilisateur, manuel produit, base de connaissance, wiki interne...)

### Q4.2 — Les exemples concrets (échantillons)

Pouvez-vous nous fournir 10 à 20 exemples réels de cas que l'agent devrait traiter ? (anciens emails reçus + réponses envoyées, tickets résolus, devis types, etc.)

### Q4.3 — Format et accessibilité

Sous quel format vivent ces données ? (emails dans la boîte, PDF, Word, Excel, base de données, papier...) Qui peut nous y donner accès et comment ?

### Q4.4 — La fraîcheur et la maintenance

À quelle fréquence ces informations changent-elles ? Qui sera responsable de les maintenir à jour ?

### Q4.5 — La confidentialité des sources

Parmi les documents que vous nous fournirez, y a-t-il des informations qui ne devraient **PAS** être accessibles à l'agent ? Par exemple : secrets commerciaux, négociations clients en cours, données RH ou salariales, dossiers personnels, contrats sensibles...

---

## 5. Décisions & Périmètre

> Définir précisément ce que l'agent peut faire seul, ce qu'il doit escalader à un humain, et le cadre éthique/juridique de son comportement. C'est le contrat moral entre le client et l'équipe technique.

### Q5.1 — Les actions autorisées

Quelles actions concrètes l'agent doit-il pouvoir réaliser ? Pour chaque action, indiquez : **Autorisée / Avec validation humaine / Interdite**.

**Lecture / consultation (passif)**

- ☐ Lire les emails ou messages entrants
- ☐ Consulter une base de données ou un CRM
- ☐ Consulter des documents internes (FAQ, procédures, historique)

**Rédaction (sans engagement)**

- ☐ Rédiger des brouillons de réponse (sans envoyer)
- ☐ Préparer des résumés, comptes rendus, synthèses

**Communication sortante (engagement vis-à-vis du client final)**

- ☐ Envoyer un email/message au nom de l'entreprise
- ☐ Répondre à une question simple sur les horaires, produits, tarifs publics
- ☐ Confirmer un rendez-vous, un délai, une livraison

**Actions opérationnelles (modification de données)**

- ☐ Créer ou modifier une fiche client / contact
- ☐ Créer un ticket, une tâche, une demande interne
- ☐ Mettre à jour un statut, une étape de workflow

**Engagements forts (à isoler)**

- ☐ Émettre un devis ou un prix
- ☐ Accorder un délai de paiement, une remise, un avoir
- ☐ Effectuer un paiement ou un engagement financier
- ☐ Signer un document au nom de l'entreprise

**Autres actions à mentionner :** _(à compléter)_

### Q5.2 — Les escalades vers l'humain

Dans quelles situations l'agent doit-il **OBLIGATOIREMENT** passer la main à un humain ? Soyez le plus précis possible (mots-clés à détecter, montants seuils, types de demandes...).

### Q5.3 — Le ton et la posture

Comment voulez-vous que l'agent s'exprime ? Précisez chaque dimension :

**Adresse**

- ☐ Tutoiement
- ☐ Vouvoiement
- ☐ S'adapte au client (selon contexte)

**Registre de langue**

- ☐ Très formel et corporate
- ☐ Professionnel mais accessible
- ☐ Décontracté et chaleureux
- ☐ Familier (rare)

**Longueur typique des réponses**

- ☐ Très courtes (1-3 phrases)
- ☐ Moyennes (un paragraphe)
- ☐ Longues et structurées (avec listes, sous-titres)

**Personnalité de l'agent**

- L'agent doit-il avoir un nom/prénom ? Lequel ?
- Doit-il se présenter comme un humain, ou clairement comme un assistant IA ?
- Doit-il faire preuve d'humour, d'empathie, de proactivité ?

**Signature et mentions obligatoires**

- Formule de politesse type (ex : "Cordialement, l'équipe X")
- Signature avec nom de l'entreprise, téléphone, mention RGPD ?
- Mentions légales spécifiques au secteur (déontologie, secret pro...) ?

> **Exemples concrets à fournir** : Pouvez-vous nous transmettre 2-3 emails ou messages que vous considérez comme représentatifs du "bon ton" attendu ?

### Q5.4 — Les sujets et engagements interdits

Y a-t-il des sujets, formulations, ou engagements que l'agent ne doit **JAMAIS** aborder ou promettre ? Passez en revue :

**Engagements commerciaux**

- ☐ Promesses de remise, rabais, gratuités
- ☐ Engagements de délai (livraison, traitement, intervention)
- ☐ Promesses de remboursement sans validation humaine
- ☐ Devis ou prix sur-mesure (au-delà des prix publics)

**Avis et conseils sensibles**

- ☐ Conseils juridiques (interdit pour la plupart des entreprises non habilitées)
- ☐ Conseils médicaux ou de santé
- ☐ Conseils financiers ou fiscaux personnalisés
- ☐ Conseils RH ou managériaux personnalisés

**Sujets hors champ**

- ☐ Politique, religion, débats de société
- ☐ Comparaisons avec la concurrence (favorables ou défavorables)
- ☐ Avis personnels du dirigeant ou de salariés
- ☐ Affaires en cours ou litiges

**Données à ne jamais divulguer**

- ☐ Coordonnées personnelles d'un salarié (téléphone perso, adresse...)
- ☐ Informations financières internes (CA, marge, salaires...)
- ☐ Données d'autres clients (jamais, en aucun cas)
- ☐ Détails techniques de fonctionnement interne

**Mentions ou formulations à éviter**

- Phrases types à proscrire (ex : "garantie 100%", "résultat garanti"...)
- Vocabulaire à bannir (jargon, anglicismes, expressions familières...)

**Autres interdits spécifiques à votre activité :** _(à compléter)_

### Q5.5 — Le contrôle qualité

Comment et qui va relire un échantillon des réponses de l'agent les premières semaines ? Quel pourcentage de relecture envisagez-vous ?

- ☐ 100% les 2 premières semaines (recommandé)
- ☐ 50% le mois suivant
- ☐ 10-20% en routine, avec re-vérification mensuelle

---

## 6. Risques & Sensibilité

> Identifier les risques juridiques, réglementaires et opérationnels du déploiement. Cette catégorie protège le client, l'agence et les utilisateurs finaux.

### Q6.1 — Le contexte réglementaire

Votre activité est-elle soumise à une réglementation particulière en matière de données ou de communication ? (RGPD bien sûr, mais aussi : secret professionnel, déontologie sectorielle, certifications, normes ISO, AI Act sectoriel...)

### Q6.2 — Les données personnelles

Les données traitées par l'agent contiennent-elles des informations personnelles (nom, email, téléphone, adresse) ? Y a-t-il des données dites "sensibles" au sens RGPD : santé, opinions politiques/religieuses, origine, orientation sexuelle, données biométriques, condamnations pénales ?

### Q6.3 — Les risques en cas d'erreur

Quelles seraient les conséquences d'une réponse fausse, déplacée ou inappropriée envoyée par l'agent à un client ? Estimez le risque sur 3 dimensions :

**Impact financier**

- ☐ Pas d'impact
- ☐ Faible (< 1 k€)
- ☐ Moyen (1-10 k€)
- ☐ Fort (> 10 k€)
- Quel scénario du pire pouvez-vous imaginer concrètement ?
- Avez-vous une assurance Responsabilité Civile Professionnelle (RC Pro) qui couvrirait une erreur générée par un système automatisé ?

**Impact image / réputation**

- ☐ Faible (un client mécontent géré en direct)
- ☐ Moyen (avis Google négatif, bouche-à-oreille local)
- ☐ Fort (campagne sociale, presse, perte de clients en série)
- Quels canaux sociaux ou avis vos clients utilisent-ils en cas d'insatisfaction ?

**Impact juridique / contractuel**

- ☐ Pas d'impact
- ☐ Risque de pénalités contractuelles
- ☐ Risque de litige client
- ☐ Risque de procédure réglementaire
- Avez-vous des contrats client comportant des clauses de qualité de service, de délais ou de garanties ?

**Tolérance globale aux erreurs**

- ☐ Élevée (les erreurs humaines sont déjà tolérées dans ce contexte)
- ☐ Moyenne (1-2% d'erreur acceptable, à corriger rapidement)
- ☐ Faible (zéro tolérance, validation humaine systématique)

### Q6.4 — Les obligations de transparence

Vos clients/utilisateurs doivent-ils être informés explicitement qu'ils interagissent avec un agent IA et non un humain ? Précisez :

**Position du client**

- ☐ Transparence totale assumée (l'IA est annoncée clairement)
- ☐ Mention discrète mais présente
- ☐ Préférence pour une approche "humaine" sans mention explicite (à discuter)

> ⚠️ **Rappel cadre légal applicable** : L'AI Act européen impose la transparence pour les chatbots/agents IA à partir du 2 août 2026. Le RGPD s'applique en parallèle. Cacher la nature IA de l'agent à un utilisateur qui le demande explicitement est une pratique interdite (sanction possible).

**Modalités envisagées**

- ☐ Mention en début d'interaction (ex : "Bonjour, je suis l'assistant virtuel de X...")
- ☐ Mention dans la signature des emails envoyés
- ☐ Page dédiée sur le site (politique IA / mentions légales)
- ☐ Possibilité pour l'utilisateur de demander à parler à un humain

**Obligations sectorielles spécifiques**

Votre secteur impose-t-il des règles supplémentaires ? DPO à consulter ?

---

## 7. Mesure & Succès

> Définir des indicateurs clairs pour piloter le projet, prouver le ROI et garantir la traçabilité. Sans mesure, pas de fidélisation ni d'amélioration continue.

### Q7.1 — Les indicateurs de succès

Comment saurez-vous, dans 3 mois et dans 6 mois, que l'agent IA est un succès ? **Choisissez 2 à 3 indicateurs prioritaires maximum** et précisez votre cible chiffrée.

> 💡 **Conseil** : Un projet avec 10 indicateurs prioritaires = un projet sans priorité. Mieux vaut viser et atteindre 2 indicateurs clairs que survoler 10 mesures floues.

**Indicateurs quantitatifs (mesurables automatiquement)**

- ☐ Temps économisé par semaine — Cible : ___ heures/semaine
- ☐ Nombre de tâches traitées en autonomie par l'agent — Cible : ___/jour
- ☐ Taux de résolution sans intervention humaine — Cible : ___%
- ☐ Délai moyen de réponse au client — Cible : moins de ___ min/heures
- ☐ Nombre d'erreurs détectées par mois — Cible : moins de ___
- ☐ Volume de demandes traitées en pic — Cible : ___/jour

**Indicateurs qualitatifs (sondage ou retour terrain)**

- ☐ Satisfaction des équipes internes (note sur 10) — Cible : ___
- ☐ Satisfaction des clients finaux (NPS, avis Google, retours) — Cible : ___
- ☐ Réduction du stress / charge mentale des équipes — Mesure : sondage trimestriel
- ☐ Capacité à traiter les pics sans embauche supplémentaire — Mesure : observation directe

**Indicateurs business (mesure par la direction)**

- ☐ Économie en coût salarial / charge — Cible : ___ €/mois
- ☐ Augmentation du CA permise par le temps libéré — Cible : ___ €/mois
- ☐ Réduction du turnover sur les postes concernés — Cible : ___%
- ☐ Capacité d'absorption de nouveaux clients sans recrutement — Cible : ___/an

**Réinvestissement du temps libéré**

- ☐ Tâches à plus forte valeur ajoutée (lesquelles ? : ___________)
- ☐ Développement commercial (prospection, fidélisation)
- ☐ Amélioration de la qualité de service existante
- ☐ Réduction de la charge de travail des équipes (qualité de vie au travail)
- ☐ Acceptation de nouveaux clients/dossiers
- ☐ Autre : __________

### Q7.2 — La situation de référence (baseline)

Avant de mettre l'agent en place, pouvez-vous mesurer ou estimer la situation actuelle sur les indicateurs retenus ? Sans baseline, impossible de mesurer le progrès.

| Indicateur retenu | Valeur actuelle | Méthode de mesure | Qui mesure ? | Cible 3 mois | Cible 6 mois |
|---|---|---|---|---|---|
| — |  |  |  |  |  |
| — |  |  |  |  |  |
| — |  |  |  |  |  |

### Q7.3 — La traçabilité et l'audit a posteriori

Quel niveau de traçabilité attendez-vous des actions de l'agent ?

**Conservation des interactions**

- Archivage souhaité ? ☐ Oui ☐ Non
- Durée : ___ mois (recommandation : minimum 12 mois)
- Qui consulte l'historique ? ___________________

**Audit en cas de litige**

- Reconstitution exacte des échanges : ☐ Oui ☐ Non
- Justification des décisions de l'agent : ☐ Oui ☐ Non

**Reporting régulier**

- ☐ Email de synthèse mensuel
- ☐ Tableau de bord en ligne
- ☐ Réunion mensuelle

---

## 8. Contraintes & Budget

> Qualifier le budget, les délais et les contraintes organisationnelles internes. Filtrer les prospects sérieux des curieux.

### Q8.1 — Le budget

Avez-vous une enveloppe budgétaire définie pour ce projet ?

- **Budget de mise en place** (one-shot : audit, configuration, intégration) : ___________________
- **Budget récurrent** (abonnement mensuel : maintenance, évolutions, support) : ___________________
- **Décideur budgétaire** : Qui valide la dépense ? ___________________
- Présent dans cet entretien ? ☐ Oui ☐ Non

### Q8.2 — Le calendrier

Avez-vous une contrainte de délai ?

- **Date cible de mise en production** : ___________________
- **Événement déclencheur** (rentrée, salon, pic saisonnier...) : ___________________
- **Disponibilité interne** :
  - Interlocuteur dédié au projet : ___________________
  - Disponibilité : ___ heures/semaine
- **Décisions en attente** : Validation DG, DSI, DPO... qui pourrait bloquer le démarrage ?

### Q8.3 — Le format de collaboration

Comment préférez-vous travailler avec nous sur la durée ?

**Mode de livraison**

- ☐ Pilote limité (1 cas d'usage, 1 mois)
- ☐ Déploiement complet dès le départ

**Démo ou prototype avant signature ?**

- ☐ Oui, indispensable
- ☐ Souhaitable mais pas bloquant
- ☐ Non, on fait confiance

**Niveau d'autonomie attendu**

- ☐ Clé en main — vous gérez tout
- ☐ Accompagnement — vous formez l'équipe interne
- ☐ Transfert de compétences — l'équipe reprend en main

### Q8.4 — Les freins internes

Y a-t-il des résistances prévisibles en interne à ce projet ?

- Des collaborateurs qui craignent pour leur poste
- Une direction qui n'est pas encore convaincue
- Un prestataire IT actuel qui pourrait bloquer l'intégration
- Des syndicats ou instances représentatives du personnel à consulter

> ⚠️ **Point de vigilance** : Un client qui répond "non, tout le monde est partant" sans hésiter n'a pas encore eu la vraie conversation en interne. Creuser systématiquement.

---

## 📌 Notes équipe — Cadre légal IA en France (avril 2026)

> À garder sous le coude pour les entretiens client.

### Échéances clés AI Act (Règlement UE 2024/1689)

- ✅ **Février 2025** — Pratiques interdites en vigueur (manipulation subliminale, scoring social, certaines biométries)
- ✅ **Août 2025** — Obligations GPAI (modèles à usage général) en vigueur
- ⚠️ **2 août 2026** — Application complète du règlement, dont l'**Article 50** sur la transparence des chatbots
- 📅 **2 août 2027** — Obligations pour systèmes haut risque Annexe III

### Notre positionnement

- Nous sommes **"fournisseurs"** au sens de l'AI Act (nous développons et commercialisons des systèmes d'IA)
- Nos clients sont **"déployeurs"** — obligations distinctes : Art. 26 (déployeurs) et Art. 50 (transparence)
- Nos agents = catégorie **"risque limité"** — Obligation principale : informer l'utilisateur qu'il interagit avec une IA

### Quand basculer en "haut risque"

Si l'agent du client touche à : recrutement / RH / scoring crédit / santé / éducation / accès à des services essentiels / application de la loi → obligations renforcées. À refuser ou à traiter avec un cadre juridique spécifique.

### Sanctions de non-conformité

- 🔴 Pratiques interdites : jusqu'à 35 M€ ou 7% du CA mondial
- 🟠 Haut risque non conforme : jusqu'à 15 M€ ou 3% du CA mondial
- 🟡 Manquement transparence (notre cas par défaut) : jusqu'à 7,5 M€ ou 1% du CA

### Articulation RGPD

L'AI Act ne remplace pas le RGPD, il s'y ajoute. Si l'agent traite des données personnelles : les deux régulations s'appliquent simultanément.

### Autorités françaises compétentes

- **CNIL** — autorité principale pour l'IA en France (intensification des contrôles à partir de l'automne 2026)
- **DGCCRF** — pour les usages commerciaux
- **Arcom** — pour les contenus médiatiques générés

### Réflexes de bonne pratique pour notre offre

- 💬 Toujours intégrer une mention claire en début d'interaction
- 🙋 Toujours offrir l'option "parler à un humain"
- 📄 Toujours documenter les choix de configuration avec le client (Cat. 5 du questionnaire)
- 🗂️ Toujours conserver des logs des interactions (Langfuse — principe non-négociable #6)

### Ressources à jour

- Texte officiel : Règlement (UE) 2024/1689 — [eur-lex.europa.eu](https://eur-lex.europa.eu)
- CNIL — section IA : [cnil.fr/fr/intelligence-artificielle](https://www.cnil.fr/fr/intelligence-artificielle)
- Service public AI Act : [aiacto.eu](https://aiacto.eu) (synthèses pratiques)

---

*Usage interne — Ne pas diffuser*

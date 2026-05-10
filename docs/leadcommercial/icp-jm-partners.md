# ICP JM Partners — Ideal Customer Profile v0.1

**Document** : `docs/leadcommercial/icp-jm-partners.md`  
**Auteur** : Jeffrey (JeffAgentia93-coder)  
**Sprint** : S2 — J7  
**Statut** : Brouillon — à valider avant S3  
**Dernière mise à jour** : 2026-05-10

---

## 1. Contexte

JM Partners est le client pilote de LeadCommercial. Ce document définit le profil de prospect idéal (ICP) que le système multi-agent doit identifier et scorer en priorité pour le cabinet.

L'ICP est le socle de configuration du scorer (Agent 3) et de la logique de priorisation des leads. Toute modification du scorer doit être cohérente avec ce document.

---

## 2. Profil cible

### 2.1 Type de structure

| Critère | Valeur |
|---|---|
| Forme juridique | SARL, SAS, SASU, EURL, entreprise individuelle (EI/AE) |
| Taille | TPE (1–9 salariés) **ou** PME (10–49 salariés) selon opportunité |
| Chiffre d'affaires | < 500 k€ (TPE) — 500 k€ à 5 M€ (PME) |
| Secteurs prioritaires | Commerce de détail, BTP, restauration/CHR, services aux entreprises |
| Secteurs exclus | Agriculture, professions réglementées avec obligation de cabinet dédié |
| Géographie | Île-de-France (rayon prioritaire) — extensions ponctuelles selon profil |

> **Note scorer** : le code NAF 5410 (SARL classique commerce de détail) est actuellement absent de `FORMES_PRIORITAIRES` — voir issue #35 pour le fix.

### 2.2 Profil du dirigeant

- Dirigeant opérationnel (gérant, PDG, associé majoritaire)
- Prend lui-même les décisions de prestataires
- N'a pas encore de cabinet comptable établi **ou** est en rupture avec son cabinet actuel
- Sensible à la disponibilité et à l'interlocuteur unique (pas de turn-over de collaborateurs)

---

## 3. Signaux déclencheurs (triggers)

### 3.1 Signal principal — Création récente (< 6 mois)

**Pourquoi c'est le signal le plus fort :**  
Le dirigeant vient de créer sa structure. Il n'a pas encore de comptable attitré ou vient juste d'en choisir un sans conviction. C'est la fenêtre de prospection optimale identifiée par l'équipe (cf. issue #35 : 3–6 mois > fenêtre < 7 jours).

**Sources de détection :**
- Sirene : date d'immatriculation
- RNE : date de création officielle
- BODACC : avis de constitution

**Critères de qualification du signal :**

```
date_creation >= aujourd'hui - 180 jours   → signal FORT (score +++)
date_creation entre 6 et 12 mois           → signal MOYEN (score ++)
date_creation > 12 mois                    → signal FAIBLE (score +)
```

### 3.2 Signaux secondaires (à activer en S3+)

| Signal | Source | Poids |
|---|---|---|
| Changement de dirigeant | BODACC / RNE | Moyen |
| Croissance rapide (embauches) | Pappers / annonces légales | Moyen |
| Mentions Reddit (insatisfaction comptable) | Reddit FR | Faible mais qualitatif |

---

## 4. Différenciation JM Partners

Le cabinet se positionne sur **la proximité et la réactivité**, avec un interlocuteur unique sur la durée. C'est le message central à faire ressortir dans les communications générées par l'Agent 4 (rédaction).

**Formulation cible pour les leads :**
> *"Un seul interlocuteur, disponible, qui connaît votre dossier de A à Z."*

**Ce que ça implique pour le scoring :**  
Privilégier les structures à taille humaine (TPE/PME) où le dirigeant veut parler à une personne, pas à un centre d'appels. Les grandes PME (> 50 salariés) avec DAF interne sont hors cible.

---

## 5. Critères d'exclusion (leads à ne pas remonter)

| Critère | Raison |
|---|---|
| Procédure collective en cours (liquidation) | Hors périmètre mission, risque d'impayé |
| Structure > 50 salariés | DAF interne probable, décision trop longue |
| Secteur agricole (NAF 01xx) | Expertise spécifique non couverte |
| Adresse hors France métropolitaine | Hors zone de service actuelle |
| Déjà client JM Partners | Éviter doublon dans le CRM |

---

## 6. Score cible et seuil de remontée

> ⚠️ **À calibrer** après les premiers dry_run. Les valeurs ci-dessous sont des hypothèses de départ.

| Niveau | Score | Action |
|---|---|---|
| Lead chaud | ≥ 75 / 100 | Remontée prioritaire, contact sous 48h |
| Lead tiède | 50–74 / 100 | File d'attente, contact sous 2 semaines |
| Lead froid | < 50 / 100 | Stocké, non remonté |

---

## 7. Liens et références

- Issue #35 : raffinements métier du scorer (SARL 5410, fenêtre prospection)
- Issue #34 : ADR-002 RGPD — manques juridiques avant passage payant
- ADR-001 : choix stack technique
- ADR-002 : politique RGPD LeadCommercial
- `src/leadcommercial/scorer.py` : implémentation du scoring

---

## 8. Historique des révisions

| Version | Date | Auteur | Changements |
|---|---|---|---|
| v0.1 | 2026-05-10 | Jeffrey | Création initiale — ICP JM Partners Sprint 2 |
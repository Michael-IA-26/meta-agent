# Cahier des charges — JM Partners Assistant Comptable

> Cabinet d'expertise comptable · Automatisation multi-agents · v1.0 — mai 2026

---

## 1. Contexte et objectifs

JM Partners est un cabinet d'expertise comptable accompagnant des TPE/PME (SARL, SAS, EURL).
Le projet vise à automatiser les tâches répétitives et à faible valeur ajoutée via un
système multi-agents piloté par LLM, afin de :

- **Réduire de 60 %** le temps de saisie comptable (extraction IA depuis les justificatifs)
- **Éliminer les oublis de déclarations** grâce à une surveillance proactive du calendrier fiscal
- **Améliorer l'expérience client** via des communications structurées et des rapports automatisés
- **Donner aux gestionnaires une vue temps réel** sur l'état de chaque dossier

---

## 2. Périmètre fonctionnel

### 2.1 Gestion des dossiers clients

- Création et suivi de dossiers (SIREN/SIRET, forme juridique, exercice fiscal)
- Workflow en 6 étapes : réception → saisie → validation → déclaration → rapport → archivage
- Attribution à un gestionnaire dédié
- Historique complet des événements (journal)

### 2.2 Traitement des documents

- Réception automatique via mail ou dépôt Supabase Storage
- Extraction IA : montants, dates, tiers, numéros de pièce (factures, relevés)
- Déduplication par SHA-256
- Statuts de traitement : reçu → analysé → intégré / rejeté

### 2.3 Comptabilité automatisée

- Génération des écritures comptables depuis les documents analysés
- Proposition de lettrages automatiques
- Validation obligatoire par le gestionnaire avant intégration définitive
- Respect du Plan Comptable Général (PCG 2025)

### 2.4 Obligations fiscales

**TVA**
- Support des régimes mensuel, trimestriel et réel simplifié
- Calcul automatique TVA collectée / déductible / nette
- Génération de la liasse de dépôt
- Suivi des dépôts et références DGFiP

**Impôt sur les Sociétés (IS)**
- Planification des 4 acomptes annuels (2157, 2571)
- Calcul des montants prévisionnels
- Alertes J-15 et J-5 avant chaque échéance
- Gestion des cas de dispense

### 2.5 Calendrier fiscal et alertes

- Surveillance proactive de toutes les échéances (TVA, IS, liasse fiscale, CFE…)
- Alertes configurables à J-30, J-15, J-7, J-3, J-1
- Escalade automatique si aucune action dans les délais
- Canaux : email + Telegram

### 2.6 Rapports et pilotage

- Rapport mensuel par dossier (activité, écritures, soldes, indicateurs)
- Rapport annuel de clôture d'exercice
- Dashboard gestionnaire (dossiers en retard, échéances à venir)

---

## 3. Architecture technique

```
apps/jmpartners/
├── agents/                 # 11 agents spécialisés (voir section 4)
│   ├── mail_handler.py
│   ├── document_receiver.py
│   ├── document_analyzer.py
│   ├── ecriture_generator.py
│   ├── tva_declarator.py
│   ├── is_tracker.py
│   ├── deadline_monitor.py
│   ├── validation_agent.py
│   ├── report_builder.py
│   ├── supabase_writer.py
│   └── notifier.py
├── orchestrator.py         # Coordinateur — aucune logique métier
└── main.py                 # Entrypoint APScheduler + --once
```

**Stack** : Python 3.11 · Anthropic Claude claude-sonnet-4-6 · Supabase (PostgreSQL + Storage) ·
APScheduler · Sentry · Doppler (secrets) · Railway (déploiement)

---

## 4. Les 11 agents

| # | Nom | Rôle | Déclencheur |
|---|-----|------|-------------|
| 01 | `mail_handler` | Réception, classification et routage des mails clients | Polling IMAP / webhook |
| 02 | `document_receiver` | Réception et stockage sécurisé des pièces | Mail attachment / upload |
| 03 | `document_analyzer` | Extraction IA (montants, dates, tiers) via Claude | Nouveau document reçu |
| 04 | `ecriture_generator` | Génération des propositions d'écritures PCG | Document analysé |
| 05 | `tva_declarator` | Calcul et préparation des déclarations TVA | Étape 3 validée / fin de mois |
| 06 | `is_tracker` | Suivi et calcul des acomptes IS | Étape 3 validée / calendrier |
| 07 | `deadline_monitor` | Surveillance du calendrier fiscal | Tâche planifiée quotidienne |
| 08 | `validation_agent` | Interface de validation gestionnaire | Action manuelle (webhook) |
| 09 | `report_builder` | Génération des rapports PDF mensuels / annuels | Fin de mois / exercice clos |
| 10 | `supabase_writer` | Persistance transversale et gestion d'état | Appelé par tous les agents |
| 11 | `notifier` | Alertes clients et équipe (email + Telegram) | Événements critiques |

---

## 5. Modèle de données Supabase (8 tables)

Voir `docs/jmpartners/schema.sql` pour le DDL complet.

| Table | Description | Clés étrangères |
|-------|-------------|-----------------|
| `utilisateurs` | Collaborateurs du cabinet | — |
| `dossiers` | Dossiers clients | `gestionnaire_id → utilisateurs` |
| `contacts` | Interlocuteurs par dossier | `dossier_id → dossiers` |
| `journaux` | Journaux comptables | `dossier_id → dossiers` |
| `ecritures` | Lignes comptables | `dossier_id`, `journal_id`, `document_id` |
| `documents` | Pièces justificatives | `dossier_id → dossiers` |
| `declarations_tva` | Déclarations TVA | `dossier_id → dossiers` |
| `acomptes_is` | Acomptes IS | `dossier_id → dossiers` |

**Contraintes transversales** : UUID partout, `created_at` systématique, RLS activée sur
toutes les tables, index sur `dossier_id` et `date` dans chaque table.

---

## 6. Workflow type — nouveau dossier

```
Client envoie mail avec factures
        │
        ▼
[01] mail_handler ──► détecte dossier_id, pièces jointes
        │
        ▼
[02] document_receiver ──► stocke dans Supabase Storage, statut='recu'
        │
        ▼
[03] document_analyzer ──► extraction IA, statut='analyse'
        │
        ▼
[04] ecriture_generator ──► propose écritures, valide=false
        │
        ▼
[08] validation_agent ──► gestionnaire valide (étape 3)
        │
        ▼
[05/06] tva_declarator + is_tracker ──► recalcule obligations
        │
        ▼
[09] report_builder ──► met à jour tableau de bord
        │
        ▼
[11] notifier ──► confirme au client + alerte gestionnaire si action requise
```

---

## 7. Contraintes non-fonctionnelles

- **Qualité** : ruff + mypy strict, zéro `print()`, docstrings sur toutes les fonctions publiques
- **Tests** : couverture minimale 80 % par agent, intégration Supabase via fixtures
- **Sécurité** : secrets Doppler, RLS Supabase, aucune donnée client en logs
- **Observabilité** : Sentry pour les erreurs, logging structuré JSON en production
- **RGPD** : données chiffrées au repos, durée de rétention configurable, droit à l'effacement

---

## 8. Variables d'environnement requises

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé service (écriture) |
| `ANTHROPIC_API_KEY` | Clé API Claude |
| `SENTRY_DSN` | DSN Sentry (optionnel) |
| `DOPPLER_ENVIRONMENT` | Environnement (dev/staging/prod) |
| `GMAIL_CREDENTIALS_PATH` | Chemin credentials OAuth Gmail |
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram alertes |
| `TELEGRAM_CHAT_ID_JMP` | Chat ID pour alertes JM Partners |

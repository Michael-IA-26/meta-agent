# Roadmap JM Partners — 5 Sprints

> Démarrage : 19 mai 2026 · Durée cible : 10 semaines (sprints de 2 semaines)

---

## Sprint 1 — Infrastructure & Dossiers (19 mai → 1 juin 2026)

**Objectif** : base de données opérationnelle, CRUD dossiers, premier pipeline de bout en bout.

### Livrables

- [ ] Schéma SQL déployé sur Supabase (8 tables + index + RLS)
- [ ] `apps/jmpartners/` : squelette complet (`__init__`, `orchestrator`, `main`)
- [ ] Agent `supabase_writer` — CRUD générique pour toutes les tables
- [ ] Agent `notifier` — intégration Telegram (reprise du pattern email_agent)
- [ ] Script de seed : 3 dossiers fictifs + utilisateurs de test
- [ ] Tests : 15 tests unitaires (orchestrateur, supabase_writer, notifier)
- [ ] CI : ruff + mypy passent en zéro warning
- [ ] Variables d'environnement documentées dans `.env.example`

### Critères d'acceptation

- `python -m apps.jmpartners.main --once --dry-run` s'exécute sans erreur
- Les 3 tables principales (dossiers, contacts, utilisateurs) sont accessibles via le client Supabase
- Un message Telegram de test arrive dans le bon channel

---

## Sprint 2 — Ingestion de documents (2 → 15 juin 2026)

**Objectif** : réception et extraction IA des pièces justificatives.

### Livrables

- [ ] Agent `mail_handler` — polling IMAP Gmail, détection pièces jointes, routage par dossier
- [ ] Agent `document_receiver` — stockage Supabase Storage, déduplication SHA-256
- [ ] Agent `document_analyzer` — extraction IA via Claude claude-sonnet-4-6 :
  - Factures vente/achat : montant HT/TTC, TVA, tiers, date, numéro
  - Relevés bancaires : lignes, dates, montants
  - Résultat stocké dans `documents.analyse_ia` (JSONB)
- [ ] Tests : 20 tests (mock documents PDF, fixtures Supabase)
- [ ] Intégration dans `Orchestrator.on_nouveau_mail()` et `on_document_recu()`

### Critères d'acceptation

- Un mail avec 3 factures PDF déclenche 3 entrées dans `documents` avec `statut='analyse'`
- Le champ `analyse_ia` contient les montants corrects (comparaison vs vérité terrain)
- Taux d'extraction correct ≥ 90 % sur un lot de 20 factures de test

---

## Sprint 3 — Comptabilité automatisée (16 → 29 juin 2026)

**Objectif** : de l'analyse IA aux écritures comptables validées.

### Livrables

- [ ] Agent `ecriture_generator` — génération d'écritures PCG depuis `analyse_ia` :
  - Mapping automatique comptes tiers (401/411)
  - Comptes TVA (44566/44571)
  - Comptes de charges/produits courants
- [ ] Agent `validation_agent` — endpoint webhook pour validation gestionnaire :
  - Approbation / rejet / correction manuelle
  - Transition `valide=false → true`
  - Déclenchement `Orchestrator.on_etape_3_validee()`
- [ ] Journaux comptables auto-créés à l'ouverture d'un dossier (VT, AC, BQ, OD)
- [ ] Tests : 25 tests (ecritures PCG, validation, rollback sur rejet)
- [ ] Interface de validation : message Telegram interactif avec boutons Approuver / Corriger

### Critères d'acceptation

- Une facture d'achat analysée génère les écritures 401 / 60x / 44566 correctes
- La validation gestionnaire passe `etape_courante` de 3 à 4 dans `dossiers`
- Un rejet supprime les écritures proposées et notifie l'opérateur

---

## Sprint 4 — Obligations fiscales (30 juin → 13 juillet 2026)

**Objectif** : automatisation TVA et IS, surveillance du calendrier fiscal.

### Livrables

- [ ] Agent `tva_declarator` :
  - Calcul TVA collectée / déductible depuis `ecritures` (comptes 44x)
  - Génération déclaration CA3 (mensuel) ou CA12 (annuel simplifié)
  - Mise à jour `declarations_tva.statut` : `a_preparer → valide → deposee`
  - Stockage fichier liasse dans Supabase Storage
- [ ] Agent `is_tracker` :
  - Calcul IS prévisionnel (résultat exercice N-1)
  - Planification des 4 acomptes (dates légales : 15/03, 15/06, 15/09, 15/12)
  - Gestion des cas de dispense (IS < 3 000 €)
- [ ] Agent `deadline_monitor` :
  - Agrège toutes les échéances (TVA + IS + liasse + CFE)
  - Alertes J-30, J-15, J-7, J-3, J-1
  - Escalade Telegram si aucune action gestionnaire
- [ ] Tests : 30 tests (calculs TVA sur jeux de données réels, calendrier IS)

### Critères d'acceptation

- Pour un dossier TVA mensuelle, la déclaration mars 2026 est calculée et générée automatiquement
- L'alerte J-7 TVA arrive dans Telegram avec le montant dû
- Les 4 dates d'acomptes IS 2026 sont créées à l'ouverture du dossier

---

## Sprint 5 — Rapports, portail et mise en production (14 → 27 juillet 2026)

**Objectif** : rapports automatisés, polish, déploiement Railway.

### Livrables

- [ ] Agent `report_builder` :
  - Rapport mensuel PDF : activité, écritures, soldes par compte, KPIs
  - Rapport annuel de clôture d'exercice
  - Envoi automatique au contact principal du dossier
- [ ] Dashboard gestionnaire :
  - Vue Telegram quotidienne : dossiers en retard, échéances J-7
  - Récapitulatif hebdomadaire tous les lundis matin
- [ ] Mise en production Railway :
  - `Dockerfile.jmpartners` optimisé
  - Variables Doppler configurées (prod/staging)
  - Sentry traces activées
  - Health check endpoint
- [ ] Tests d'intégration bout en bout :
  - Scénario complet : mail → documents → écritures → TVA → rapport
  - Couverture globale ≥ 80 %
- [ ] Documentation finale :
  - `ARCHITECTURE.md` à jour
  - Runbook opérationnel (redémarrage, debug, rollback)

### Critères d'acceptation

- Le rapport mensuel d'un dossier est généré et envoyé sans intervention manuelle
- Le scheduler Railway tourne 48h sans erreur en environnement staging
- Tous les tests CI passent (ruff + mypy + pytest) en < 3 minutes

---

## Récapitulatif

| Sprint | Dates | Focus | Agents livrés |
|--------|-------|-------|---------------|
| 1 | 19 mai – 1 juin | Infrastructure | `supabase_writer`, `notifier` |
| 2 | 2 – 15 juin | Ingestion docs | `mail_handler`, `document_receiver`, `document_analyzer` |
| 3 | 16 – 29 juin | Comptabilité | `ecriture_generator`, `validation_agent` |
| 4 | 30 juin – 13 juil. | Fiscalité | `tva_declarator`, `is_tracker`, `deadline_monitor` |
| 5 | 14 – 27 juil. | Rapports + prod | `report_builder` + déploiement |

**Total agents** : 11 · **Total tests cibles** : ~90 · **Durée** : 10 semaines

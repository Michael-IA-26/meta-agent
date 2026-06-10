# Architecture JM Partners — référence TDD

> Mis à jour le 2026-06-10. Source : analyse statique de `apps/jmpartners/` + résultats pytest (53 passed, 2 xfailed, 0 failed).

---

## 1. Flux complet

### 1a. Déclenchement cron (scheduler APScheduler)

```
Railway container
  └─ apps/jmpartners/main.py  (BlockingScheduler)
       ├─ lun-ven 08:00 → orchestrator.run()          [cycle complet]
       └─ lun-ven 17:30 → echeance_agent.run()        [rapport fin de journée]
```

### 1b. Déclenchement email entrant (IMAP polling)

```
IMAP_HOST (Gmail / autre)
  └─ mail_handler.run()
       ├─ fetch_unseen_emails()     IMAP SSL, INBOX UNSEEN
       ├─ identify_contact()        Supabase: contacts.email
       ├─ classify_request()        Claude Haiku → type_demande
       └─ log_journal()             journaux.type_action = "email_recu"
            ↓
       [TODO] si type_demande == "document_manquant"
              → document_checker.run(dossier_id)      ← NON IMPLÉMENTÉ
              → relance_handler.run(doc_result)        ← NON IMPLÉMENTÉ
```

### 1c. Orchestrateur — séquence complète

```
orchestrator.run(dry_run=False, cabinet_id="jmpartners")
  │
  ├─ 1. _handle_emails()                              [toujours exécuté]
  │       └─ mail_handler.run()
  │            ├─ IMAP SSL → fetch emails non lus
  │            ├─ Claude Haiku → classify_request()
  │            └─ Supabase → log_journal()
  │
  ├─ 2. tva_agent.run()                               [toujours exécuté]
  │       └─ pour chaque déclaration TVA dans horizon 15j :
  │            └─ document_checker.run(dossier_id)
  │                 └─ si pièces manquantes + jours in [15,7,3] → Telegram
  │
  ├─ 3. echeance_agent.run()                          [toujours exécuté]
  │       └─ fetch acomptes_is + declarations_tva dans 30j
  │            ├─ BUILD rapport texte (rouge/orange/vert)
  │            ├─ send_telegram()
  │            └─ send_email() → RAPPORT_DESTINATAIRE (SMTP)
  │
  ├─ 4. ClotureHandler(cabinet_id).run()              [skip si dry_run]
  │       └─ si dernier jour ouvré du mois :
  │            ├─ UPDATE dossiers.statut = "cloture_envoyee"
  │            └─ send_telegram()
  │
  ├─ 5. AcompteISAgent().run()                        [skip si dry_run]
  │       └─ pour chaque dossier actif × chaque échéance IS dans horizon :
  │            ├─ si jours in [15,7,3] → email SMTP + Telegram
  │            └─ log_journal()
  │
  ├─ 6. BilanAgent().run()                            [skip si dry_run]
  │       └─ pour chaque dossier bilan en_cours :
  │            ├─ si jours in [30,15,7] → email SMTP + Telegram
  │            └─ log_journal()
  │
  ├─ 7. DeclarationISAgent().run()                    [skip si dry_run]
  │       └─ pour chaque acompte_is non payé :
  │            ├─ si jours in [30,15,7] → email SMTP + Telegram
  │            └─ log_journal()
  │
  └─ 8. NotificationAgent()                           ← INSTANCIÉ SEULEMENT
          (hub de notifications Sprint 3 — jamais appelé, réservé pour extension)
```

Chaque étape est dans un `try/except` indépendant — une erreur n'interrompt pas les suivantes.
Les erreurs sont accumulées dans `OrchestratorResult["erreurs"]` (mail absorbé, 6 autres remontent).

### 1d. Flux document → relance (déclenché à la demande)

```
dashboard GET /api/relancer/{dossier_id}
  └─ run_document_relance_flow(dossier_id, dry_run=False)
       ├─ check_docs(dossier_id)       → DocumentCheckerResult
       └─ send_relance(doc_result)     → RelanceResult
            ├─ relance_deja_envoyee()  anti-doublon 48h
            ├─ fetch_contact_email()   Supabase: contacts
            ├─ get_anthropic_client()  compose_relance() via Claude Haiku
            │     └─ fallback statique si Claude indisponible
            ├─ send_smtp()
            └─ log_journal()
```

---

## 2. Dépendances entre agents

```
orchestrator
  ├── mail_handler           (autonome — IMAP + Claude + Supabase)
  ├── tva_agent
  │     └── document_checker (appelé pour chaque déclaration TVA)
  ├── echeance_agent         (autonome — lit acomptes_is + declarations_tva)
  ├── cloture_handler        (autonome — lit/écrit dossiers)
  ├── acompte_is_agent       (autonome — lit dossiers, calcule dates IS)
  ├── bilan_agent            (autonome — lit dossiers + documents)
  ├── declaration_is_agent   (autonome — lit acomptes_is JOIN dossiers)
  └── notification_agent     (non branché — instancié uniquement)

relance_handler
  └── document_checker       (appelé en amont via RelanceHandler.run())

document_checker             (autonome — lit dossiers + documents)
```

**Agents sans dépendances amont** : `echeance_agent`, `cloture_handler`, `acompte_is_agent`, `bilan_agent`, `declaration_is_agent`, `document_checker`.

**Claude (Anthropic)** est utilisé par : `mail_handler` (classify_request), `relance_handler` (compose_relance). Les deux ont un fallback si le client est indisponible.

---

## 3. État de chaque agent

Basé sur les 55 tests : **53 passants, 2 xfailed attendus** (fonctionnalités Sprint 3 non implémentées).

| Agent | Tests dédiés | État | Notes |
|-------|-------------|------|-------|
| `document_checker` | 10 / 10 ✅ | **Fonctionnel** | Filtrage statut côté client corrigé (fix 2026-06-10) |
| `echeance_agent` | 14 / 14 ✅ | **Fonctionnel** | N+1 queries contacts (acceptable < 50 échéances) |
| `mail_handler` | 8 / 8 ✅ | **Fonctionnel** | Env vars lues à runtime corrigées (fix 2026-06-10) |
| `relance_handler` | 9 / 9 ✅ | **Fonctionnel** | Fallback Claude statique corrigé (fix 2026-06-10) |
| `orchestrator` | 12 ✅ + 2 xfail | **Fonctionnel** | 2 features Sprint 3 marquées xfail intentionnellement |
| `tva_agent` | 0 (via orchestrator mock) | **Non testé unitairement** | Alerte uniquement aux jours exacts [15,7,3] |
| `cloture_handler` | 0 (via orchestrator mock) | **Non testé unitairement** | Pas de journalisation dans `journaux` |
| `acompte_is_agent` | 0 (via orchestrator mock) | **Non testé unitairement** | Typo `SMTP_PASSWORDWORD` corrigée (commit 3533998) |
| `bilan_agent` | 0 (via orchestrator mock) | **Non testé unitairement** | Idem — typo corrigée |
| `declaration_is_agent` | 0 (via orchestrator mock) | **Non testé unitairement** | Filtre `cabinet_id` post-fetch (perf) ; typo corrigée |
| `notification_agent` | 0 | **Non branché** | Instancié dans orchestrateur, jamais appelé (Sprint 3) |

### Fonctionnalités Sprint 3 marquées xfail (attendues)

| Test | Raison du xfail |
|------|----------------|
| `test_email_document_manquant_declenche_relance` | Flux email→document_checker→relance non implémenté dans `_handle_emails` |
| `test_notification_agent_appele_pour_alertes_urgentes` | `NotificationAgent.send()` jamais appelé depuis l'orchestrateur |

---

## 4. Comportements métier — testés vs non testés

### ✅ Testés (53 assertions vertes)

#### orchestrator
- Ordre d'exécution garanti : mail → tva → echeance → cloture → acomptes → bilans → declarations
- Chaque agent qui lève une exception n'interrompt pas les suivants
- `dry_run=True` saute exactement les étapes 4–7 (cloture, acomptes, bilans, declarations)
- `erreurs` accumule les 6 erreurs agents (mail absorbé par `_handle_emails`)
- Deux runs consécutifs retournent des structures identiques (pas de side-effects globaux)
- `OrchestratorResult` contient exactement 9 clés
- `run_document_relance_flow` appelle check_docs puis send_relance dans cet ordre
- `run_document_relance_flow` propage correctement le flag `dry_run`

#### document_checker
- Dossier inexistant → `erreur` renseigné, `manquants=[]`
- Type dossier inconnu → `erreur` renseigné
- Tous les documents présents → `manquants=[]`
- Document avec deadline passée → urgence `"J-0"`
- Document avec deadline dans 2 jours → urgence `"J-3"`
- `dry_run=True` → aucune insertion dans `journaux`
- Timeout Supabase → `erreur` renseigné, pas d'exception propagée
- Document avec statut non reconnu (`illisible`) → compté comme absent
- Dossier sans `contact_id` → `manquants` calculés quand même, `contact_id=None`
- Bilan avec 1 doc sur 5 présent → 4 manquants

#### echeance_agent
- Priorité rouge pour échéances ≤ 3 jours
- Priorité orange pour échéances 4–7 jours
- Priorité verte pour échéances > 7 jours
- Rapport contient la date du jour
- Rapport mentionne les échéances rouges
- Aucune échéance → `rapport_envoye=False`
- Échéance trouvée → rapport envoyé (Telegram + email)
- `dry_run=True` → rien envoyé
- Résultat trié par jours restants
- Compteurs rouge/orange/vert corrects
- Structure de résultat complète (`echeances_total`, `rouge`, `orange`, `vert`, `rapport_envoye`, `echeances`, `erreurs`)
- Telegram down mais email ok → `rapport_envoye=True`
- Telegram ET email down → `rapport_envoye=False`
- Acomptes IS et TVA combinés dans une même liste d'échéances

#### mail_handler
- IMAP non configuré → retour immédiat `{"traites": 0, "erreurs": ["IMAP non configuré"]}`
- IMAP configuré → `fetch_unseen_emails` appelé
- Email de contact connu → `type_demande` et `contact_id` renseignés
- Email de contact inconnu → `non_matches++`, `contact_id=None`
- Claude Haiku timeout → `type_demande="autre"` (fallback interne)
- Corps email vide → traité sans erreur
- `dry_run=True` → `log_journal` non appelé
- Boîte vide → `traites=0`, `erreurs=[]`

#### relance_handler
- Aucun document manquant → `envoye=False`, `raison_skip="Aucun document manquant"`
- `contact_id=None` → `envoye=False`, `raison_skip="contact_id manquant"`
- Relance déjà envoyée < 48h → skip avec journal `relance_skipped`
- Email contact introuvable dans Supabase → `envoye=False`, `email_destinataire=None`
- `dry_run=True` → email composé, non envoyé, `journal_id=None`, `raison_skip="dry_run"`
- SMTP down → `envoye=False`, `raison_skip="Erreur SMTP"`
- Claude timeout → compose fallback statique, envoi SMTP quand même, `envoye=True`
- Happy path → `envoye=True`, `journal_id` renseigné
- `RelanceHandler.cabinet_id` accessible

---

### ❌ Non testés (gap de couverture)

#### tva_agent (0 tests unitaires)
- Déclaration à J+16 → aucune alerte (hors horizon)
- Déclaration à J+15, J+7, J+3 → alerte Telegram
- Déclaration à J+10 → aucune alerte (jour non dans `HORIZONS_ALERTE`)
- Pas de pièces manquantes → `alerte_envoyee=False`
- Telegram down → alerte non envoyée mais pas d'exception
- UPDATE `alerte_envoyee_at` dans `declarations_tva`

#### cloture_handler (0 tests unitaires)
- Pas dernier jour ouvré du mois → `statut="skip"`
- Dernier jour ouvré, aucun dossier en cours → `statut="aucun_dossier"`
- Dernier jour ouvré avec dossiers → UPDATE Supabase + Telegram + `statut="cloture_envoyee"`
- Telegram down → clôture effectuée quand même
- Journalisation dans `journaux` (non implémentée)

#### acompte_is_agent (0 tests unitaires)
- Aucun dossier actif → retour `[]`
- Dossier avec échéance à J+3 → alerte email + Telegram
- Échéances calculées algorithmiquement (mois 3, 6, 9, 12 — jour 15)
- Dossier hors `HORIZONS_ALERTE` [15,7,3] → aucune alerte

#### bilan_agent (0 tests unitaires)
- Dossier sans deadline → ignoré (warning log)
- Dossier avec `jours_restants=15` → alerte
- Dossier avec `jours_restants=10` → pas d'alerte (hors [30,15,7])
- Email envoyé via SMTP (SMTP_PASSWORD requis)

#### declaration_is_agent (0 tests unitaires)
- Filtre `cabinet_id` post-fetch → exclut dossiers d'autres cabinets
- Acompte avec date invalide → warning + skip
- Acompte payé → exclu des alertes

#### notification_agent (0 tests unitaires)
- Urgence `J-3` → Telegram + email
- Urgence `J-7` → email seul
- Déduplication 24h (doublon → `send()` retourne `False`)
- `SMTP_PASSWORD` non configuré → warning log, pas d'exception

#### orchestrator — Sprint 3 (2 xfail)
- Email `document_manquant` avec `contact_id` connu → déclenche relance automatique
- `NotificationAgent.send()` appelé pour alertes J-3

---

## 5. Tables Supabase — matrice lecture/écriture

| Table | Lue par | Écrite par |
|-------|---------|-----------|
| `dossiers` | document_checker, bilan_agent, acompte_is_agent, cloture_handler, declaration_is_agent | cloture_handler (`UPDATE statut`) |
| `documents` | document_checker, bilan_agent | — |
| `contacts` | tva_agent, echeance_agent, mail_handler, relance_handler | — |
| `declarations_tva` | tva_agent, echeance_agent | tva_agent (`UPDATE alerte_envoyee_at, statut`) |
| `acomptes_is` | echeance_agent, declaration_is_agent | — |
| `journaux` | relance_handler (anti-doublon 48h), notification_agent (dedup 24h) | document_checker, tva_agent, mail_handler, relance_handler, echeance_agent, bilan_agent, declaration_is_agent, notification_agent |

### Schéma `journaux` (unifié)

| Colonne | Type | Usage |
|---------|------|-------|
| `id` | uuid | Supabase auto |
| `contact_id` | uuid\|null | document_checker, tva_agent, mail_handler, relance_handler |
| `dossier_id` | uuid\|null | tous sauf mail_handler |
| `type_action` | text | `"email_recu"`, `"verification_documents"`, `"relance_envoyee"`, `"relance_skipped"`, `"alerte_tva"`, `"alerte_echeance"`, `"alerte_bilan"`, `"alerte_acompte_is"`, `"alerte_declaration_is"`, `"notification_envoyee"` |
| `contenu` | text | résumé lisible (tronqué ~500 chars) |
| `statut` | text | `"ok"` \| `"erreur"` \| `"skipped"` |
| `metadata` | jsonb | contenu variable par agent |
| `created_at` | timestamptz | Supabase auto |

---

## 6. TypedDicts de référence

### OrchestratorResult
```python
mail:             MailHandlerResult | None
relances:         list[RelanceResult]          # toujours [] (flux email→relance non implémenté)
tva:              TvaAgentResult | None
echeances:        EcheanceAgentResult | None
cloture:          ClotureResult | None
acomptes_is:      list[AcompteAlert]
bilans:           list[BilanAlert]
declarations_is:  list[DeclarationISAlert]
erreurs:          list[str]                    # 6 max si tous crashent (mail absorbé)
```

### DocumentCheckerResult
```python
dossier_id:   str
contact_id:   str | None
type_dossier: str                   # "bilan"|"tva"|"is"|"paie"|"creation"
manquants:    list[DocumentManquant]
complets:     list[str]
erreur:       str | None
```

### RelanceResult
```python
envoye:               bool
raison_skip:          str | None    # "Aucun document manquant"|"contact_id manquant"|"dry_run"|"Erreur SMTP"|...
email_destinataire:   str | None
sujet:                str | None
corps:                str | None
journal_id:           str | None
```

---

## 7. Dettes techniques connues

| Problème | Agents concernés | Priorité |
|---------|----------------|----------|
| Flux email→document→relance non implémenté | orchestrator._handle_emails | Sprint 3 |
| `NotificationAgent` non branché dans l'orchestrateur | orchestrator | Sprint 3 |
| 5 agents sans tests unitaires | tva, cloture, acompte_is, bilan, declaration_is | Haute |
| Alerte uniquement aux jours exacts (miss si run raté) | tva, bilan, acompte_is, declaration_is | Moyenne |
| N+1 queries sur `contacts` | tva_agent, echeance_agent | Faible (< 50 échéances) |
| Filtre `cabinet_id` post-fetch en mémoire | declaration_is_agent | Faible |
| `cloture_handler` sans journalisation `journaux` | cloture_handler | Faible |
| Modèle `claude-haiku-4-5-20251001` potentiellement déprécié | mail_handler, relance_handler | Surveiller |

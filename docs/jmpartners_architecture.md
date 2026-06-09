# Architecture JM Partners — référence TDD

> Généré le 2026-06-09. Source : analyse statique de `apps/jmpartners/`.

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
       ├─ fetch_unseen_emails()   IMAP SSL, INBOX UNSEEN
       ├─ identify_contact()      Supabase: contacts.email
       ├─ classify_request()      Claude Haiku  →  type_demande
       └─ log_journal()           journaux.type_action = "email_recu"
            ↓
       [TODO] si type_demande == "document_manquant"
              → document_checker.run(dossier_id)      ← NON IMPLÉMENTÉ
              → relance_handler.run(doc_result)        ← NON IMPLÉMENTÉ
```

### 1c. Orchestrateur — séquence complète

```
orchestrator.run(dry_run=False, cabinet_id="jmpartners")
  │
  ├─ 1. _handle_emails()
  │      └─ mail_handler.run()
  │
  ├─ 2. tva_agent.run()
  │      └─ pour chaque déclaration TVA dans horizon 15j :
  │           └─ document_checker.run(dossier_id)
  │                └─ si pièces manquantes + jours in [15,7,3] → Telegram
  │
  ├─ 3. echeance_agent.run()
  │      └─ fetch acomptes_is + declarations_tva dans 30j
  │           └─ Telegram + email SMTP → RAPPORT_DESTINATAIRE
  │
  ├─ 4. ClotureHandler(cabinet_id).run()       [skip si dry_run]
  │      └─ si dernier jour ouvré du mois :
  │           └─ UPDATE dossiers.statut="cloture_envoyee" + Telegram
  │
  ├─ 5. AcompteISAgent().run()                 [skip si dry_run]
  │      └─ pour chaque dossier actif × chaque échéance IS dans horizon :
  │           └─ si jours in [15,7,3] → email + Telegram
  │
  ├─ 6. BilanAgent().run()                     [skip si dry_run]
  │      └─ pour chaque dossier bilan en_cours :
  │           └─ si jours in [30,15,7] → email SMTP_USER + Telegram
  │
  ├─ 7. DeclarationISAgent().run()             [skip si dry_run]
  │      └─ pour chaque acompte_is non payé :
  │           └─ si jours in [30,15,7] → email SMTP_USER + Telegram
  │
  └─ 8. NotificationAgent()                    ← INSTANCIÉ MAIS JAMAIS UTILISÉ
```

Chaque étape est dans un `try/except` indépendant — une erreur n'interrompt pas les suivantes.

---

## 2. Dépendances entre agents

```
orchestrator
  ├── mail_handler             (autonome — IMAP + Claude + Supabase)
  ├── tva_agent
  │     └── document_checker   (appelé pour chaque déclaration TVA)
  ├── echeance_agent           (autonome — lit acomptes_is + declarations_tva)
  ├── cloture_handler          (autonome — lit/écrit dossiers)
  ├── acompte_is_agent         (autonome — lit dossiers, calcule dates IS)
  ├── bilan_agent              (autonome — lit dossiers + documents)
  ├── declaration_is_agent     (autonome — lit acomptes_is JOIN dossiers)
  └── notification_agent       (non branché — Sprint 3 non terminé)

relance_handler
  └── document_checker         (appelé en amont via RelanceHandler.run())

dashboard /api/relancer/{id}
  └── RelanceHandler
        ├── document_checker
        └── relance_handler
```

---

## 3. État de chaque agent

| Agent | État | Blocants |
|-------|------|---------|
| `document_checker` | ✅ Fonctionnel | — |
| `echeance_agent` | ✅ Fonctionnel | N+1 queries contacts |
| `tva_agent` | ✅ Fonctionnel | Alerte uniquement aux jours exacts [15,7,3] |
| `relance_handler` | ✅ Fonctionnel | Modèle `claude-haiku-4-5-20251001` (daté) |
| `mail_handler` | ✅ Fonctionnel (avec garde IMAP) | Flux email→dossier non implémenté |
| `cloture_handler` | ✅ Fonctionnel | Pas de journalisation dans `journaux` |
| `bilan_agent` | ⚠️ Partiellement | `SMTP_PASSWORDWORD` typo → `NameError` à l'envoi email |
| `acompte_is_agent` | ⚠️ Partiellement | Même typo `SMTP_PASSWORDWORD` |
| `declaration_is_agent` | ⚠️ Partiellement | Même typo ; filtre `cabinet_id` post-fetch (perf) |
| `notification_agent` | ⚠️ Non branché | Instancié dans l'orchestrateur mais jamais appelé |

---

## 4. Tables Supabase — matrice lecture/écriture

| Table | Lue par | Écrite par |
|-------|---------|-----------|
| `dossiers` | document_checker, bilan_agent, acompte_is_agent, cloture_handler, declaration_is_agent, dashboard | cloture_handler (`UPDATE statut="cloture_envoyee"`) |
| `documents` | document_checker, bilan_agent, declaration_is_agent, dashboard | — |
| `contacts` | tva_agent, echeance_agent, mail_handler, relance_handler | — |
| `declarations_tva` | tva_agent, echeance_agent, dashboard | tva_agent (`UPDATE alerte_envoyee_at, statut`) |
| `acomptes_is` | echeance_agent, declaration_is_agent, dashboard | — |
| `journaux` | relance_handler (anti-doublon 48h), notification_agent (dedup 24h) | document_checker, tva_agent, mail_handler, relance_handler, echeance_agent, bilan_agent, declaration_is_agent, notification_agent |
| `lead_locks` | — | — *(leadcommercial only)* |

### Schema unifié `journaux` (post-fix M5/M6)

| Colonne | Type | Rempli par |
|---------|------|-----------|
| `id` | uuid | Supabase auto |
| `contact_id` | uuid\|null | document_checker, tva_agent, mail_handler, relance_handler |
| `dossier_id` | uuid\|null | tous sauf mail_handler |
| `type_action` | text | **tous les agents** (unifié) |
| `contenu` | text | tous (tronqué à 500–1000 chars) |
| `statut` | text | `"ok"` \| `"erreur"` \| `"skipped"` |
| `metadata` | jsonb | tous (contenu variable par agent) |
| `created_at` | timestamptz | Supabase auto |

---

## 5. TypedDicts de référence

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
erreurs:          list[str]
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

### DocumentManquant
```python
nom_document: str
type_document: str
deadline:     str | None
urgence:      str | None            # "J-0"|"J-3"|"J-7"|"J-15"|None
```

### RelanceResult
```python
envoye:               bool
raison_skip:          str | None
email_destinataire:   str | None
sujet:                str | None
corps:                str | None
journal_id:           str | None
```

---

## 6. Comportements attendus non testés (base TDD)

### Orchestrateur
- [ ] Ordre d'exécution garanti (mail → tva → echeance → cloture → acomptes → bilans → declarations)
- [ ] Un agent qui lève une exception n'interrompt pas les suivants
- [ ] `dry_run=True` saute exactement les étapes 4–7
- [ ] `OrchestratorResult.erreurs` accumule toutes les erreurs sans déduplication
- [ ] Deux runs le même jour ne dupliquent pas les entrées `journaux` (dépend de l'anti-doublon des agents)
- [ ] `relances` est toujours `[]` (flux email→relance non implémenté — attendu)

### document_checker
- [ ] Dossier inexistant → `erreur` renseigné, `manquants=[]`
- [ ] Type dossier inconnu → `erreur` renseigné
- [ ] Tous les documents présents → `manquants=[]`
- [ ] Document avec deadline passée → urgence `"J-0"`
- [ ] `dry_run=True` → aucune insertion `journaux`
- [ ] Timeout Supabase → `erreur` renseigné, pas d'exception non gérée

### tva_agent
- [ ] Déclaration à J+16 → aucune alerte (hors horizon)
- [ ] Déclaration à J+15, J+7, J+3 → alerte Telegram
- [ ] Déclaration à J+10 → aucune alerte (jour non dans `HORIZONS_ALERTE`)
- [ ] Pas de pièces manquantes → `alerte_envoyee=False`
- [ ] Telegram down → alerte non envoyée mais pas d'exception

### echeance_agent
- [ ] Aucune échéance → `rapport_envoye=False`, `echeances_total=0`
- [ ] Échéance à J-1 (déjà passée) → exclue (filtre `.gte("deadline", today)`)
- [ ] Rapport généré et tronqué à 4096 chars pour Telegram
- [ ] SMTP down → `rapport_envoye=False` si Telegram aussi down

### mail_handler
- [ ] IMAP non configuré → retour immédiat `{"traites": 0, "erreurs": ["IMAP non configuré"]}`
- [ ] Email de contact inconnu → `non_matches++`, `contact_id=None`
- [ ] Claude Haiku timeout → `type_demande="autre"` (fallback)
- [ ] Corps email vide → traité sans erreur
- [ ] `dry_run=True` → aucune insertion `journaux`

### relance_handler
- [ ] Aucun document manquant → `envoye=False`, `raison_skip="Aucun document manquant"`
- [ ] `contact_id=None` → `envoye=False`, `raison_skip="contact_id manquant"`
- [ ] Relance déjà envoyée < 48h → skip avec log `relance_skipped`
- [ ] Email contact introuvable → `envoye=False`
- [ ] SMTP down → `envoye=False`, `raison_skip="Erreur SMTP"`
- [ ] Claude timeout → compose fallback statique, envoi quand même via SMTP
- [ ] `dry_run=True` → compose l'email mais ne l'envoie pas, `journal_id=None`

### notification_agent
- [ ] Urgence `J-3` → Telegram + email
- [ ] Urgence `J-7` → email seul
- [ ] Urgence `J-15` ou `J-30` → email avec déduplication 24h
- [ ] Doublon < 24h → second `send()` retourne `False`
- [ ] `SMTP_PASSWORD` non configuré → warning log, pas d'exception

### bilan_agent
- [ ] Dossier sans deadline → ignoré (warning log)
- [ ] Dossier avec `jours_restants=15` → alerte
- [ ] Dossier avec `jours_restants=10` → pas d'alerte
- [ ] `SMTP_PASSWORD` défini → email envoyé sans `NameError`

### acompte_is_agent
- [ ] Aucun dossier actif → retour `[]`
- [ ] Dossier avec échéance à J+3 → alerte email + Telegram
- [ ] Échéances calculées algorithmiquement (mois 3, 6, 9, 12, jour 15)
- [ ] `SMTP_PASSWORD` défini → email envoyé sans `NameError`

### cloture_handler
- [ ] Pas dernier jour ouvré du mois → `statut="skip"`
- [ ] Dernier jour ouvré, aucun dossier en cours → `statut="aucun_dossier"`
- [ ] Dernier jour ouvré avec dossiers → UPDATE Supabase + Telegram
- [ ] Telegram down → clôture effectuée quand même

### declaration_is_agent
- [ ] Filtre `cabinet_id` post-fetch exclu les dossiers d'autres cabinets
- [ ] Acompte avec date invalide → warning + skip
- [ ] `SMTP_PASSWORD` défini → email envoyé sans `NameError`

---

## 7. Limites connues et dettes techniques

| Problème | Agents | Impact |
|---------|--------|--------|
| `SMTP_PASSWORDWORD` typo → `NameError` | bilan, acompte_is, declaration_is, notification | Email SMTP plante à l'exécution |
| Alerte uniquement aux jours exacts (pas les jours intermédiaires) | tva, bilan, acompte_is, declaration_is | Alerte sautée si run raté un jour J |
| Flux email→document→relance non implémenté | orchestrator._handle_emails | Emails "document_manquant" ignorés |
| `NotificationAgent` non branché | orchestrator | Sprint 3 non terminé |
| N+1 queries sur `contacts` | tva_agent, echeance_agent | Perf avec >20 échéances |
| Filtre `cabinet_id` post-fetch | declaration_is_agent | SELECT global puis filtre Python |
| `cloture_handler` sans journalisation | cloture_handler | Pas de trace dans `journaux` |
| Modèle `claude-haiku-4-5-20251001` | mail_handler, relance_handler | Dépréciation potentielle |
| Anti-doublon 48h non appliqué en `dry_run` | relance_handler | Tests dry_run peuvent diverger du comportement prod |

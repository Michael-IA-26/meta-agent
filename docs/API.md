# Meta-Agent — API Reference

> Version : 2.2 | Dernière mise à jour : juin 2026

---

## Architecture

| App | Type | Scheduler | Port |
|-----|------|-----------|------|
| `email_agent` | Pipeline + scheduler | `schedule` — 08h45 quotidien | — |
| `jmpartners` | FastAPI + BlockingScheduler | lun-ven 08h00 / 17h30 + 7 jobs nocturnes | 8000 |
| `leadcommercial` | FastAPI + BlockingScheduler | nuit 02h00 Europe/Paris | 8001 |

---

## FastAPI Endpoints

### JM Partners Dashboard

Base URL : `http://localhost:8000` (Railway : `https://jmpartners.up.railway.app`)

#### `GET /`

Retourne le dashboard HTML de suivi des dossiers.

**Réponse :** `text/html` — page de pilotage avec dossiers actifs, alertes, échéances.

---

#### `GET /api/dossiers`

Liste les dossiers actifs avec leurs alertes.

**Réponse :**
```json
[
  {
    "id": "cihan-0000-0000-0000-dossier00001",
    "contact_nom": "Mohamed Hassani",
    "type": "tva",
    "exercice": "2026",
    "statut": "en_cours",
    "secteur": "restauration",
    "deadline": "2026-06-15",
    "alertes": ["pieces_manquantes", "relance_a_envoyer"]
  }
]
```

---

#### `GET /api/echeances`

Retourne les échéances TVA + IS des 30 prochains jours.

**Réponse :**
```json
[
  {
    "type": "tva",
    "contact_id": "cihan-0000-0000-0000-contact000001",
    "contact_nom": "CIHAN Restaurant",
    "dossier_id": "cihan-0000-0000-0000-dossier00001",
    "deadline": "2026-06-15",
    "jours_restants": 14,
    "priorite": "rouge",
    "statut": "pieces_manquantes"
  }
]
```

---

#### `POST /api/relancer/{dossier_id}`

Déclenche une relance documentaire manuelle pour un dossier.

**Paramètre path :** `dossier_id` (string, UUID)

**Réponse succès :**
```json
{
  "status": "envoye",
  "email_destinataire": "gerant@cihan-restaurant.fr",
  "sujet": "Documents manquants — TVA mai 2026",
  "journal_id": "uuid-du-journal"
}
```

**Réponse si aucun document manquant :**
```json
{ "status": "skipped", "raison": "aucun document manquant" }
```

**Erreurs :** `HTTP 500` si RelanceHandler échoue.

---

#### `POST /api/dry-run`

Simule un cycle complet (document_checker → relance_handler) sans effets de bord.

**Réponse :**
```json
{
  "dossiers_verifies": 3,
  "relances_simulees": 1,
  "documents_manquants": ["Relevé bancaire BNP mai 2026"],
  "dry_run": true
}
```

---

### LeadCommercial Dashboard

Base URL : `http://localhost:8001` (Railway : `https://leadcommercial.up.railway.app`)

#### `GET /`

Dashboard HTML de suivi des leads commerciaux.

---

#### `GET /api/leads`

Retourne les 50 leads les mieux scorés depuis Supabase.

**Réponse :**
```json
[
  {
    "siren": "912345678",
    "denomination": "CIHAN RESTAURANT SASU",
    "score": 82,
    "signal_type": "creation",
    "forme_juridique": "SASU",
    "code_naf": "5610A",
    "commune": "Paris 9e",
    "dirigeant_nom": "Hassani",
    "dirigeant_prenom": "Mohamed",
    "site_web": null,
    "capital_social": 10000
  }
]
```

**Erreurs :** retourne `[]` si Supabase indisponible (log Sentry).

---

#### `POST /api/run`

Déclenche le pipeline Sirene → scoring → enrichissement → Supabase + Telegram.

**Réponse :**
```json
{ "status": "started" }
```

**Erreurs :** `HTTP 500` si la pipeline ne peut pas démarrer.

---

#### `GET /api/stats`

KPIs agrégés du pipeline.

**Réponse :**
```json
{
  "leads_today": 12,
  "leads_week": 47,
  "qualified_week": 8,
  "qualification_rate": 17.0,
  "best_score": 91
}
```

**Erreurs :** retourne `{}` si Supabase indisponible.

---

## Agents

### Email Agent (`apps/email_agent/agents/`)

| Agent | Fonction | Inputs | Output |
|-------|----------|--------|--------|
| `outlook_fetcher` | `fetch_emails(max_results=20)` | `max_results: int` | `list[EmailRaw]` |
| `email_analyzer` | `analyze_email(email, icp_context="")` | `EmailRaw`, `str` | `EmailAnalyzed` |
| `email_analyzer` | `load_icp(icp_name="agence_conseil")` | `str` | `str` (contexte ICP) |
| `report_builder` | `build_report(analyzed_emails)` | `list[EmailAnalyzed]` | `str` (HTML) |
| `outlook_reporter` | `send_email_report(html, subject, recipient="")` | `str`, `str`, `str` | `bool` |
| `supabase_writer` | `write_email(analyzed)` | `EmailAnalyzed` | `bool` |
| `supabase_writer` | `write_kpis(analyzed_emails, temps_agent_sec)` | `list[EmailAnalyzed]`, `float` | `KpiResult` |
| `telegram_sender` | `send_telegram(analyzed_emails, kpis=None)` | `list[EmailAnalyzed]`, `KpiResult\|None` | `bool` |

**Pipeline complète (déclenché à 08h45) :**
```
outlook_fetcher → email_analyzer × N → report_builder → outlook_reporter
                                  ↓                              ↓
                          supabase_writer (emails)     supabase_writer (kpis)
                                                              ↓
                                                      telegram_sender
```

---

### LeadCommercial (`apps/leadcommercial/agents/`)

| Agent | Fonction | Inputs | Output |
|-------|----------|--------|--------|
| `sirene_fetcher` | `fetch_idf_companies(params)` | `SireneInput` | `list[CompanyRaw]` |
| `lead_scorer` | `score_company(params)` | `ScoreInput` | `ScoredLead` |
| `pappers_enricher` | `enrich_lead(params)` | `EnrichInput (siren: str)` | `PappersEnrichment` |
| `supabase_writer` | `write_lead(params)` | `WriteInput` | `bool` |
| `telegram_notifier` | `notify_lead(params)` | `NotifyInput` | `bool` |

**Pipeline complète (déclenché à 02h00) :**
```
sirene_fetcher → lead_scorer (score ≥ seuil) → pappers_enricher → supabase_writer → telegram_notifier
```

---

### JM Partners (`apps/jmpartners/agents/`)

| Agent | Fonction | Input | Output | Schedule |
|-------|----------|-------|--------|----------|
| `mail_handler` | `run(dry_run=False)` | `bool` | `MailHandlerResult` | 08h00 |
| `document_checker` | `run(dossier_id, dry_run=False)` | `str`, `bool` | `DocumentCheckerResult` | 08h00 |
| `relance_handler` | `run(result, dry_run=False)` | `DocumentCheckerResult`, `bool` | `RelanceResult` | 08h00 |
| `echeance_agent` | `run(dry_run=False)` | `bool` | `EcheanceAgentResult` | 17h30 |
| `tva_agent` | `run(dry_run=False)` | `bool` | `TvaAgentResult` | 17h30 |
| `acompte_is_agent` | `AcompteISAgent().run()` | — | `list[AcompteAlert]` | 01h30 |
| `bilan_agent` | `BilanAgent().run()` | — | `list[BilanAlert]` | 00h30 |
| `declaration_is_agent` | `run()` | — | `list[DeclarationISAlert]` | 01h00 |
| `cloture_handler` | `run()` | — | `ClotureResult` | 02h00 |
| `fnp_fae_agent` | `run()` | — | `list[FNPAlert]` | nocturne |
| `lettrage_agent` | `run()` | — | `list[LettreResult]` | nocturne |
| `revision_agent` | `run()` | — | `RevisionResult` | nocturne |
| `notification_agent` | `run()` | — | — | async |

**Cycle matin (08h00) :**
```
mail_handler → document_checker × dossiers → relance_handler × dossiers
```

**Rapport 17h30 :**
```
echeance_agent ‖ tva_agent → Telegram
```

**Jobs nocturnes (00h30 → 03h30) :**
```
00h30 bilan_agent
01h00 declaration_is_agent
01h30 acompte_is_agent
02h00 cloture_handler
02h30 relance_handler (nocturne)
03h00 tva_agent (nocturne)
03h30 fnp_fae_agent
```

---

## Types & Schémas

### Email Agent

```python
EmailRaw = TypedDict("EmailRaw", {
    "id": str,
    "subject": str,
    "from": str,        # adresse expéditeur
    "date": str,        # ISO 8601
    "body": str,        # texte brut, max 500 chars
})

EmailAnalyzed = TypedDict("EmailAnalyzed", {
    **EmailRaw,
    "priority": str,            # "haute" | "moyenne" | "basse"
    "category": str,            # "client" | "prospect" | "inutile" | ...
    "summary": str,
    "action": Optional[str],
    "suggested_reply": Optional[str],
})

KpiResult = TypedDict("KpiResult", {
    "emails_analyses": int,
    "temps_theorique_min": int,
    "temps_agent_min": float,
    "temps_gagne_min": float,
    "gain_pourcentage": float,
    "valeur_estimee_eur": float,
    "semaine": str,
})
```

### LeadCommercial

```python
CompanyRaw = {
    "siren": str, "siret": str, "denomination": str,
    "forme_juridique": str, "code_naf": str,
    "dept": str, "commune": str, "date_creation": str,
}

ScoredLead = CompanyRaw | {
    "score": int,               # 0–100
    "signal_type": str,         # "creation" | "reprise" | ...
    "scoring_details": dict,
    "qualified": bool,          # score ≥ LEAD_SCORE_THRESHOLD
}

PappersEnrichment = {
    "dirigeant_nom": str, "dirigeant_prenom": str,
    "dirigeant_email": str | None,
    "site_web": str | None,
    "capital_social": int | None,
}
```

### JM Partners

```python
DocumentCheckerResult = {
    "dossier_id": str,
    "contact_id": str,
    "type_dossier": str,
    "manquants": list[DocumentManquant],  # [{nom, type_document, deadline, urgence}]
    "complets": list[str],
    "erreur": str | None,
}

RelanceResult = {
    "envoye": bool,
    "raison_skip": str | None,
    "email_destinataire": str,
    "sujet": str,
    "corps": str,
    "journal_id": str | None,
}

EcheanceAgentResult = {
    "echeances_total": int,
    "rouge": int,   # < 7 jours
    "orange": int,  # 7–15 jours
    "vert": int,    # > 15 jours
    "rapport_envoye": bool,
    "echeances": list[Echeance],
    "erreurs": list[str],
}
```

---

## Variables d'environnement

| Variable | App | Requis | Défaut | Description |
|----------|-----|--------|--------|-------------|
| `ANTHROPIC_API_KEY` | toutes | ✅ | — | Clé API Claude |
| `SUPABASE_URL` | toutes | ✅ | — | URL Supabase project |
| `SUPABASE_SERVICE_KEY` | toutes | ✅ | — | Service role key (bypasse RLS) |
| `SENTRY_DSN` | toutes | — | `None` | DSN Sentry (optionnel) |
| `DOPPLER_ENVIRONMENT` | toutes | — | `dev` | `dev` / `staging` / `prod` |
| `TELEGRAM_BOT_TOKEN` | email, jm, lc | ✅ | — | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | email, jm, lc | ✅ | — | Chat destination |
| `RAPPORT_EMAIL` | email | — | `michael@myvesper.fr` | Destinataire rapport quotidien |
| `RAPPORT_DESTINATAIRE` | jm | — | — | Destinataire rapport JM Partners |
| `OUTLOOK_CLIENT_ID` | email | ✅ | — | Azure App client ID |
| `OUTLOOK_CLIENT_SECRET` | email | ✅ | — | Azure App secret |
| `OUTLOOK_TENANT_ID` | email | ✅ | — | Azure tenant ID |
| `OUTLOOK_REFRESH_TOKEN` | email | ✅ | — | OAuth refresh token (Doppler) |
| `IMAP_HOST` | jm | ✅ | — | Serveur IMAP (ex: outlook.office365.com) |
| `IMAP_USER` | jm | ✅ | — | Email IMAP |
| `IMAP_PASSWORD` | jm | ✅ | — | Mot de passe IMAP |
| `SMTP_HOST` | jm | ✅ | `smtp.gmail.com` | Serveur SMTP |
| `SMTP_PORT` | jm | — | `587` | Port SMTP |
| `SMTP_USER` | jm | ✅ | — | Email SMTP |
| `SMTP_PASSWORD` | jm | ✅ | — | Mot de passe SMTP |
| `SIRENE_API_TOKEN` | lc | ✅ | — | Token API Sirene |
| `PAPPERS_API_KEY` | lc | ✅ | — | Clé API Pappers |
| `LEAD_SCORE_THRESHOLD` | lc | — | `50` | Score minimum pour qualifier un lead |
| `HOURLY_RATE` | email | — | `80` | Taux horaire (€) pour calcul KPI |
| `TEMPS_THEORIQUE_MIN` | email | — | `45` | Temps théorique de traitement (min) |
| `CABINET_ID` | jm | ✅ | — | Identifiant cabinet JM Partners |

---

## Démarrage rapide

### Lancer les dashboards localement

```bash
# JM Partners (port 8000)
cd /path/to/meta-agent
uvicorn apps.jmpartners.dashboard:app --port 8000 --reload

# LeadCommercial (port 8001)
uvicorn apps.leadcommercial.dashboard:app --port 8001 --reload
```

### Exemples curl

```bash
BASE_JM="http://localhost:8000"
BASE_LC="http://localhost:8001"

# Lister les dossiers actifs avec alertes
curl "$BASE_JM/api/dossiers" | jq .

# Voir les échéances TVA + IS des 30 prochains jours
curl "$BASE_JM/api/echeances" | jq '.[].jours_restants'

# Relancer manuellement un dossier
curl -X POST "$BASE_JM/api/relancer/cihan-0000-0000-0000-dossier00001" | jq .

# Simuler un cycle complet sans envoi
curl -X POST "$BASE_JM/api/dry-run" | jq .

# Leads commerciaux (top 50 par score)
curl "$BASE_LC/api/leads" | jq '.[0:3]'

# KPIs LeadCommercial
curl "$BASE_LC/api/stats" | jq .

# Déclencher le pipeline leads maintenant
curl -X POST "$BASE_LC/api/run"
```

### Lancer un agent manuellement (CLI)

```bash
# JM Partners — cycle complet une fois
.venv/bin/python -m apps.jmpartners.main --once

# JM Partners — dry-run (aucun envoi)
.venv/bin/python -m apps.jmpartners.main --once --dry-run

# LeadCommercial — exécution unique
.venv/bin/python -m apps.leadcommercial.main --once
```

### Vérifier la santé de l'email agent

```bash
# Tester la connexion Outlook Graph (nécessite les 4 vars OUTLOOK_*)
.venv/bin/python -c "
from apps.email_agent.outlook_client import get_emails
emails = get_emails(max_results=1)
print(f'OK — {len(emails)} email(s) trouvé(s)')
"
```

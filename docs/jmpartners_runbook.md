# JM Partners — Runbook opérationnel

> Dernière mise à jour : 2026-06-17

## Architecture

```
Outlook (Graph API)
       │
       ▼
apps/jmpartners/agents/mail_handler.py   ← collecte & classifie les emails
       │
       ▼
apps/jmpartners/orchestrator.py          ← cycle complet (mail → relances → TVA → IS → …)
       │
       ▼
Supabase (PostgreSQL)                    ← dossiers, documents, déclarations_tva, acomptes_is
       │
       ▼
apps/jmpartners/dashboard.py             ← FastAPI REST + dashboard HTML
       │
       ▼
Lovable frontend (https://ai-books-buddy.lovable.app)
```

## Variables d'environnement requises

| Variable | Description | Exemple |
|---|---|---|
| `ANTHROPIC_API_KEY` | Clé Anthropic pour claude-sonnet | `sk-ant-...` |
| `SUPABASE_URL` | URL du projet Supabase | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Clé service Supabase (JWT) | `eyJ...` |
| `GRAPH_TENANT_ID` | Azure AD tenant ID | `xxxxxxxx-...` |
| `GRAPH_CLIENT_ID` | Azure AD app client ID | `xxxxxxxx-...` |
| `GRAPH_CLIENT_SECRET` | Azure AD app client secret | `your-secret` |
| `GRAPH_MAILBOX` | Boîte Outlook à surveiller | `compta@jmpartners.fr` |
| `CORS_ALLOWED_ORIGINS` | Origines autorisées CORS (virgule-séparé) | `https://ai-books-buddy.lovable.app` |
| `CABINET_ID` | Identifiant du cabinet | `jmpartners` |
| `SCHEDULER_ENABLED` | Active le scheduler (true/false) | `true` |

Variables optionnelles : `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `PAPPERS_API_KEY`, `OPENAI_API_KEY`.

## Démarrage local

```bash
# Copier et compléter les variables
cp .env.example .env

# Installer les dépendances
pip install -r requirements.txt

# Lancer le dashboard
python -m apps.jmpartners.dashboard
# ou : uvicorn apps.jmpartners.dashboard:app --host 0.0.0.0 --port 8080 --reload
```

## Endpoints API

| Méthode | Route | Description | Safety |
|---|---|---|---|
| `GET` | `/` | Dashboard HTML | — |
| `GET` | `/health` | Health check | — |
| `GET` | `/api/dossiers` | Dossiers actifs (Supabase ou mock) | Lecture seule |
| `GET` | `/api/echeances` | Échéances TVA + IS (30 jours) | Lecture seule |
| `GET` | `/api/documents` | Documents pipeline (`?dossier_id=` optionnel) | Lecture seule |
| `POST` | `/api/relancer/{dossier_id}` | Déclenche une relance | Effet de bord |
| `POST` | `/api/ingest-mail` | Collecte emails Outlook | `dry_run=true` par défaut |
| `POST` | `/api/run-cycle` | Cycle orchestrateur complet | `dry_run=true` par défaut |
| `POST` | `/api/dry-run` | Alias rétro-compatible de `/api/run-cycle` (dry_run=true) | Toujours dry-run |

### Safety guardrails

`POST /api/ingest-mail` et `POST /api/run-cycle` acceptent `{"dry_run": false}` pour déclencher de vraies opérations. Par défaut (`{}` ou `{"dry_run": true}`), aucun email sortant ni écriture comptable n'est effectué.

## CORS

Le middleware CORS lit `CORS_ALLOWED_ORIGINS` à l'appel de `create_app()`, jamais au chargement du module. Cela permet aux tests de surcharger la variable avant d'instancier l'app.

```python
# Test pattern
monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://ai-books-buddy.lovable.app")
client = TestClient(create_app())
```

Origines configurées en production :
- `https://ai-books-buddy.lovable.app`
- `https://preview.lovable.app`

## Microsoft Graph — collecte mail

Le module `apps/jmpartners/integrations/graph_mail.py` implémente l'auth OAuth2 app-only (client credentials) pour lire la boîte `compta@jmpartners.fr`. `apps/jmpartners/agents/mail_handler.py` utilise ce module pour la collecte.

### Variables requises

| Variable | Valeur | Description |
|---|---|---|
| `GRAPH_TENANT_ID` | UUID Azure AD | Tenant de l'annuaire JM Partners |
| `GRAPH_CLIENT_ID` | UUID | ID de l'App Registration Azure |
| `GRAPH_CLIENT_SECRET` | Secret | Credential de l'app (rotation recommandée tous les 12 mois) |
| `GRAPH_MAILBOX` | `compta@jmpartners.fr` | Boîte Outlook à surveiller |

### Permissions Azure (App Registration)

Type : **Application** (pas Delegated) — admin-consented.

| Permission | Type | Usage |
|---|---|---|
| `Mail.Read` | Application | Lecture des messages non lus |
| `Mail.Send` | Application | Envoi de relances depuis `compta@` |

### Application Access Policy (scope minimal)

Pour limiter l'accès de l'app à la seule boîte `compta@jmpartners.fr` (bonne pratique sécurité), créer une policy Exchange via PowerShell (admin Exchange Online) :

```powershell
# Créer un mail-enabled security group contenant uniquement compta@jmpartners.fr
New-ApplicationAccessPolicy `
  -AppId "<GRAPH_CLIENT_ID>" `
  -PolicyScopeGroupId "<groupe-email>" `
  -AccessRight RestrictAccess `
  -Description "Limite graph_mail.py à compta@jmpartners.fr"
```

### Comportement si Graph non configuré

Si `GRAPH_TENANT_ID` est absent, `mail_handler.run()` retourne :
```json
{"traites": 0, "non_matches": 0, "emails": [], "erreurs": ["Graph non configuré"]}
```
Aucun crash — le dashboard absorbe l'erreur gracieusement.

## Tests

```bash
# Tous les tests jmpartners (nouveau répertoire sprint E2E)
pytest tests/jmpartners/ -v

# Tests legacy (sprint 1-3)
pytest tests/test_jmpartners/ -v

# Tests dashboard (CORS, documents, ingest-mail, run-cycle)
pytest tests/jmpartners/test_dashboard_cors.py \
       tests/jmpartners/test_dashboard_documents.py \
       tests/jmpartners/test_dashboard_ingest_mail.py \
       tests/jmpartners/test_dashboard_run_cycle.py -v

# Test de smoke Railway
pytest tests/test_jmpartners/test_smoke_railway.py -v
```

## Déploiement Railway

Le service est déployé sur Railway. La commande de démarrage est :

```
python -m apps.jmpartners.dashboard
```

ou via le `Procfile` / `railway.toml` du dépôt. Les variables d'environnement sont configurées dans le dashboard Railway.

## Schéma Supabase

Le schéma v2.2 (17 tables) est défini dans `docs/jmpartners/schema.sql`. Les tables principales utilisées par le dashboard :

- `dossiers` — dossiers clients actifs
- `documents` — documents reçus avec statut pipeline (`recu`, `analysé`, `presaisi`, `valide`)
- `declarations_tva` — déclarations TVA avec deadline
- `acomptes_is` — acomptes IS avec deadline
- `contacts` — clients du cabinet

## Troubleshooting

### Supabase indisponible

Le dashboard retourne les données mock (`_MOCK_DOSSIERS`) pour `/api/dossiers` et les calculs algorithmiques pour `/api/echeances`. Les endpoints `/api/documents` retournent `{"total": 0, "documents": [], "par_statut": {}}`.

### Graph non configuré

`POST /api/ingest-mail` retournera `{"statut": "ok", "erreurs": ["Graph non configuré"], "traites": 0}` si les variables Graph sont absentes. Vérifier `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_MAILBOX`.

### CORS bloqué depuis Lovable

Vérifier que `CORS_ALLOWED_ORIGINS` contient exactement l'origine Lovable (sans slash final). Redéployer après modification de la variable d'environnement (Railway redémarre automatiquement).

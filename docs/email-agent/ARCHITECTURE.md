# Email Agent — Architecture

## Vue d'ensemble

L'email agent est un pipeline quotidien qui :
1. Récupère les emails non-lus Gmail
2. Les classe avec Claude (priorité, catégorie, action, suggestion de réponse)
3. Persiste chaque résultat dans Supabase
4. Envoie un rapport HTML par email et un résumé Telegram avec les KPIs

Le code est structuré en **agents spécialisés** coordonnés par un **orchestrateur** sans logique métier.

---

## Structure des fichiers

```
apps/email_agent/
├── main.py                     Scheduler APScheduler + entrypoint CLI
├── orchestrator.py             Enchaîne les 6 agents, gère les erreurs
├── agents/
│   ├── __init__.py             TypedDicts partagés (EmailRaw, EmailAnalyzed, KpiResult)
│   ├── gmail_fetcher.py        [1] Récupère les emails Gmail
│   ├── email_analyzer.py       [2] Classifie 1 email avec Claude
│   ├── supabase_writer.py      [3] Persiste 1 email + KPIs dans Supabase
│   ├── report_builder.py       [4] Construit le rapport HTML
│   ├── gmail_reporter.py       [5] Envoie le rapport HTML par email
│   └── telegram_sender.py      [6] Envoie le résumé Telegram
├── gmail_client.py             Auth Gmail (prod base64 / local OAuth)
├── storage.py                  Client Supabase + calcul KPIs
├── analyzer.py                 Logique Claude (system prompt, ICP, JSON parsing)
├── sender.py                   Génération HTML du rapport (report_to_html)
└── telegram_sender.py          Envoi Telegram bas niveau (send_telegram_report)
```

---

## Rôle de chaque agent

### `agents/gmail_fetcher.py`

| | |
|---|---|
| **Fonction** | `fetch_emails(max_results: int = 20) -> list[EmailRaw]` |
| **Input** | Nombre maximum d'emails à récupérer |
| **Output** | Liste de dicts `EmailRaw` (id, subject, from, date, body) |
| **Responsabilité** | Appelle `gmail_client.get_emails()`. Lève une exception si l'API Gmail échoue. Retourne une liste vide si la boîte est vide. |
| **Dépendances** | `gmail_client.py`, variables Gmail |

```python
EmailRaw = TypedDict("EmailRaw", {
    "id": str,
    "subject": str,
    "from": str,
    "date": str,
    "body": str,   # tronqué à 500 caractères
})
```

---

### `agents/email_analyzer.py`

| | |
|---|---|
| **Fonctions** | `load_icp(icp_name: str) -> str` · `analyze_email(email, icp_context) -> EmailAnalyzed` |
| **Input** | Un `EmailRaw` + contexte ICP (string markdown) |
| **Output** | `EmailAnalyzed` : tous les champs `EmailRaw` + priority, category, summary, action, suggested_reply |
| **Responsabilité** | Appelle l'API Claude (`claude-sonnet-4-6`) avec le prompt ICP en `system=`. Parse le JSON de réponse. En cas d'échec de parsing, retourne un fallback `priority=moyenne`. **Aucun accès Supabase.** |
| **Dépendances** | `analyzer.py` (system prompt, ICP loader), `ANTHROPIC_API_KEY` |

```python
EmailAnalyzed = TypedDict("EmailAnalyzed", {
    # champs EmailRaw hérités
    "priority": str,          # "haute" | "moyenne" | "basse"
    "category": str,          # "action_requise" | "reponse_requise" | "information" | "inutile"
    "summary": str,
    "action": Optional[str],
    "suggested_reply": Optional[str],
})
```

Le contexte ICP (`load_icp`) est chargé **une seule fois** par l'orchestrateur et passé à chaque appel pour éviter des lectures disque répétées.

---

### `agents/supabase_writer.py`

| | |
|---|---|
| **Fonctions** | `write_email(analyzed: EmailAnalyzed) -> bool` · `write_kpis(emails, elapsed_sec) -> KpiResult` |
| **Input** | Un `EmailAnalyzed` / liste d'emails + durée d'exécution (secondes) |
| **Output** | `bool` (succès) / `KpiResult` |
| **Responsabilité** | Wraps `storage.save_email()` avec retry (3 tentatives, backoff exponentiel). Calcule et persiste les KPIs hebdomadaires. Ne lève jamais d'exception (retourne `False` / `{}` en cas d'erreur). |
| **Dépendances** | `storage.py`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |

```python
class KpiResult(TypedDict):
    emails_analyses: int
    temps_theorique_min: int    # TEMPS_THEORIQUE_MIN env var (défaut 45)
    temps_agent_min: float
    temps_gagne_min: float
    gain_pourcentage: float
    valeur_estimee_eur: float   # basé sur HOURLY_RATE env var (défaut 80)
    semaine: str                # format "YYYY-Wnn"
```

---

### `agents/report_builder.py`

| | |
|---|---|
| **Fonction** | `build_report(analyzed_emails: list[EmailAnalyzed]) -> str` |
| **Input** | Liste complète des emails analysés |
| **Output** | String HTML autonome (prêt à être envoyé par email) |
| **Responsabilité** | Wraps `sender.report_to_html()`. Organise les emails par priorité (haute / moyenne / basse), liste les tâches et suggestions de réponse. Aucun appel réseau. |
| **Dépendances** | `sender.py` |

---

### `agents/gmail_reporter.py`

| | |
|---|---|
| **Fonction** | `send_email_report(html: str, subject: str, recipient: str = "") -> bool` |
| **Input** | Contenu HTML, sujet, destinataire (optionnel) |
| **Output** | `True` si envoyé, `False` en cas d'erreur |
| **Responsabilité** | Construit un message MIME multipart, envoie via l'API Gmail. Utilise `RAPPORT_EMAIL` si aucun destinataire n'est fourni. Ne lève jamais d'exception. |
| **Dépendances** | `gmail_client.py`, `RAPPORT_EMAIL` |

---

### `agents/telegram_sender.py`

| | |
|---|---|
| **Fonction** | `send_telegram(analyzed_emails, kpis: KpiResult | None) -> bool` |
| **Input** | Liste d'emails analysés + KPIs (optionnel) |
| **Output** | `True` si envoyé, `False` en cas d'erreur |
| **Responsabilité** | Wraps `telegram_sender.send_telegram_report()`. Formate un résumé Markdown : compteurs par priorité, top 3 prioritaires, top 3 tâches, bloc KPIs. |
| **Dépendances** | `telegram_sender.py`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

---

## Flow de l'orchestrateur

```
main.py
  └─ orchestrator.run()
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  [1] GmailFetcher.fetch_emails(max_results=20)      │
│       → list[EmailRaw]                              │
│       ✗ Exception → log + return (pipeline avorté) │
│       ✗ Liste vide → log + return                  │
└──────────────────────┬──────────────────────────────┘
                       │ emails: list[EmailRaw]
                       ▼
┌─────────────────────────────────────────────────────┐
│  [2] EmailAnalyzer.load_icp("agence_conseil")       │
│       → icp_context: str  (chargé une seule fois)  │
└──────────────────────┬──────────────────────────────┘
                       │ icp_context: str
                       ▼
┌─────────────────────────────────────────────────────┐
│  Pour chaque email dans emails:                     │
│    [3a] EmailAnalyzer.analyze_email(email, icp)     │
│           → EmailAnalyzed                           │
│           ✗ Exception → log + skip email           │
│    [3b] SupabaseWriter.write_email(analyzed)        │
│           → bool  (erreur loggée, jamais bloquant) │
└──────────────────────┬──────────────────────────────┘
                       │ analyzed: list[EmailAnalyzed]
                       │ elapsed: float (secondes)
                       ▼
┌─────────────────────────────────────────────────────┐
│  [4] ReportBuilder.build_report(analyzed)           │
│       → html: str                                   │
│       ✗ Exception → log + html = ""                │
└──────────────────────┬──────────────────────────────┘
                       │ html: str
                       ▼
┌─────────────────────────────────────────────────────┐
│  [5] GmailReporter.send_email_report(html, subject) │
│       → bool  (ignoré si html vide)                │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  [6] SupabaseWriter.write_kpis(analyzed, elapsed)   │
│       → kpis: KpiResult                            │
└──────────────────────┬──────────────────────────────┘
                       │ kpis: KpiResult
                       ▼
┌─────────────────────────────────────────────────────┐
│  [7] TelegramSender.send_telegram(analyzed, kpis)   │
│       → bool                                        │
└─────────────────────────────────────────────────────┘
```

**Principes de l'orchestrateur :**
- Aucune logique métier — uniquement enchaînement et gestion d'erreurs
- Un email qui échoue à l'analyse est loggué et skipé ; le pipeline continue
- Les agents 5, 6, 7 ne bloquent jamais le pipeline (erreurs loggées)

---

## Variables d'environnement

### Requises en production

| Variable | Utilisée par | Description |
|----------|-------------|-------------|
| `GMAIL_TOKEN_B64` | `gmail_client.py` | Token OAuth Gmail encodé en base64 (compte principal) |
| `ANTHROPIC_API_KEY` | `agents/email_analyzer.py` | Clé API Anthropic (Claude) |
| `SUPABASE_URL` | `storage.py` | URL du projet Supabase |
| `SUPABASE_SERVICE_KEY` | `storage.py` | Clé service Supabase (rôle `service_role`) |
| `TELEGRAM_BOT_TOKEN` | `telegram_sender.py` | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | `telegram_sender.py` | ID du chat/canal de destination |

### Optionnelles

| Variable | Défaut | Description |
|----------|--------|-------------|
| `RAPPORT_EMAIL` | `michael@myvesper.fr` | Destinataire du rapport HTML quotidien |
| `TEMPS_THEORIQUE_MIN` | `45` | Temps théorique de traitement manuel (minutes), base du calcul de gain |
| `HOURLY_RATE` | `80` | Taux horaire (EUR) pour estimer la valeur générée |
| `SENTRY_DSN` | _(vide)_ | DSN Sentry pour la capture d'erreurs |
| `DOPPLER_ENVIRONMENT` | `dev` | Label d'environnement Sentry (`dev`, `prod`, etc.) |
| `TOKEN_FILE` | `token.json` | Chemin du fichier token OAuth en mode local |
| `GMAIL_TOKEN_VESPER_B64` | _(vide)_ | Token OAuth du compte Vesper (non utilisé dans le pipeline principal) |

---

## Lancer l'agent

### En local (développement)

**Prérequis :** `credentials.json` présent dans `apps/email_agent/` (téléchargé depuis Google Cloud Console).

```bash
# Installer les dépendances
uv sync

# Premier lancement — ouvre le navigateur pour l'auth OAuth Gmail
uv run python apps/email_agent/main.py --once
# → génère token.json localement

# Lancement suivants (token en cache)
uv run python apps/email_agent/main.py --once

# Mode scheduler (rapport à 08h45 chaque jour)
uv run python apps/email_agent/main.py
```

**Variables minimales en local** (fichier `.env` ou export) :
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_SERVICE_KEY=eyJ...
export TELEGRAM_BOT_TOKEN=123456:ABC...
export TELEGRAM_CHAT_ID=-100123456789
# GMAIL_TOKEN_B64 absent → mode local avec token.json
```

### En production (Railway)

Le démarrage se fait automatiquement via `railway.toml`. Les variables d'environnement sont gérées par Doppler.

**Générer `GMAIL_TOKEN_B64` depuis un token.json existant :**
```bash
base64 -i apps/email_agent/token.json | tr -d '\n'
# Copier la valeur dans la variable GMAIL_TOKEN_B64 sur Railway/Doppler
```

**Variables Railway supplémentaires :**
```
DOPPLER_ENVIRONMENT=prod
SENTRY_DSN=https://xxx@sentry.io/yyy
RAPPORT_EMAIL=michael@jmpartners.fr
```

**Exécution unique (debug prod) :**
```bash
railway run python apps/email_agent/main.py --once
```

---

## Ajouter un nouvel agent

### 1. Créer le fichier agent

```python
# apps/email_agent/agents/mon_agent.py
"""Mon agent — description courte."""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

# Import du module sous-jacent (gmail_client, storage, etc.)
from mon_module import ma_fonction  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailAnalyzed  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)


def run_agent(input_data: EmailAnalyzed) -> bool:
    """Description claire de la responsabilité de l'agent.

    Returns True on success, False on failure (never raises).
    """
    try:
        result = ma_fonction(input_data)
        logger.info("MonAgent: done — %s", result)
        return True
    except Exception as exc:
        logger.error("MonAgent: failed — %s", exc)
        return False
```

**Règles à respecter :**
- 1 fichier, 1 (ou quelques) fonctions publiques
- `TypedDict` pour input et output (définis dans `agents/__init__.py` si réutilisables)
- Zéro `print()`, zéro side-effect caché
- Toutes les fonctions publiques ont une docstring
- Ne lève jamais d'exception vers l'orchestrateur (retourner `False` / valeur vide)

### 2. Brancher dans l'orchestrateur

```python
# apps/email_agent/orchestrator.py

import agents.mon_agent as mon_agent  # noqa: E402  (avec les autres imports)

def run(...) -> None:
    ...
    # Ajouter l'étape au bon endroit dans la séquence
    mon_agent.run_agent(analyzed[-1])
```

### 3. Écrire les tests

```python
# tests/test_agents_mon_agent.py
import os, sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.mon_agent import run_agent

_MOD = "apps.email_agent.agents.mon_agent"

def test_run_agent_returns_true_on_success() -> None:
    with patch(f"{_MOD}.ma_fonction", return_value="ok"):
        assert run_agent(_SOME_INPUT) is True

def test_run_agent_returns_false_on_failure() -> None:
    with patch(f"{_MOD}.ma_fonction", side_effect=RuntimeError("boom")):
        assert run_agent(_SOME_INPUT) is False
```

### 4. Valider

```bash
uv run ruff check apps/email_agent/agents/mon_agent.py --fix
uv run mypy apps/email_agent/agents/mon_agent.py --ignore-missing-imports
uv run pytest tests/test_agents_mon_agent.py -v
```

---

## Tables Supabase utilisées

| Table | Écrit par | Contenu |
|-------|-----------|---------|
| `emails_analyzed` | `supabase_writer.write_email` | 1 ligne par email analysé (subject, from, priority, category, summary, action, suggested_reply) |
| `agent_weekly_stats` | `supabase_writer.write_kpis` | 1 ligne par semaine (temps agent, temps gagné, gain %, valeur EUR) |

---

## Modèle Claude utilisé

`claude-sonnet-4-6` — défini dans `agents/email_analyzer.py`. Pour changer de modèle, modifier uniquement cette constante dans ce fichier.

Le prompt système injecte le contenu de `packages/prompts/icps/agence_conseil.md` (profil ICP). Pour adapter la classification à un autre profil métier, créer un nouveau fichier ICP et passer son nom via le paramètre `icp_name` de `orchestrator.run()`.

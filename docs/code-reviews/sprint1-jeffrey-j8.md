# Code Review Sprint 1 — Jeffrey J8

> Review complète du code Sprint 1 livré par Mika.
> Référence : Sprint 1, tâche J8.

| Version | Date | Auteur | Durée totale review |
|---|---|---|---|
| v1.0 | 2026-05-03 | Jeffrey | ~2h |

---

## Périmètre review

PRs Mika reviewées (toutes mergées sur `main` au moment de la review) :
- #9, #10 — Supabase storage + KPIs
- #11 — Docker + Sentry
- #12 — Telegram bot
- #14 — Onboarding client (script Python)
- #15 — Client pilote
- #17 — Fix bugs Sprint 1

Approche : audit post-merge sur les fichiers cibles du brief J8 (storage.py, Dockerfile, Sentry), avec création d'issues GitHub pour les findings actionables et synthèse dans ce document pour les sujets de rétro et suggestions Sprint 2+.

---

## ✅ Conformité au brief J8

### `apps/email_agent/storage.py` — 3/4 critères

- [x] Pas de credentials en dur (`os.getenv` utilisé partout)
- [x] Erreurs Supabase gérées avec try/except + log (l'agent ne plante pas)
- [x] Retries configurés avec `tenacity` (`stop_after_attempt(3)` + `wait_exponential`)
- [ ] Docstrings absents sur les 4 fonctions publiques

`mypy` passe clean sur le fichier (vérifié avec `venv/Scripts/mypy apps/email_agent/storage.py`).

### `Dockerfile` — 4/4 critères

- [x] Image basée sur `python:3.11-slim`
- [x] Utilisateur non-root (`USER appuser` ligne 18)
- [x] Pas de secrets copiés dans l'image (vérifié par lecture)
- [x] `HEALTHCHECK` présent (lignes 20-21)

### Intégration Sentry — Conforme

- [x] DSN via `os.getenv("SENTRY_DSN")`
- [x] Environment configuré via `os.getenv("DOPPLER_ENVIRONMENT", "dev")`
- [x] `traces_sample_rate=0.1` (10%) — bonne pratique pour économiser les quotas
- [x] `sentry_sdk.capture_exception(e)` utilisé dans le try/except

---

## 🚨 Findings sécurité (issue #21)

### Token OAuth Gmail versionné dans Git

`apps/email_agent/token_myvesper.json` est tracké par Git :

    $ git ls-files apps/email_agent/token_myvesper.json
    apps/email_agent/token_myvesper.json

**Cause racine** : le `.gitignore` contient `token.json` mais pas le pattern `token*.json`. Même bug exact dans `.dockerignore`.

**Sévérité** : moyenne (repo PRIVATE, mais le token est dans tout l'historique Git et le risque s'accroît avec l'arrivée des cabinets Vesper aux S11-13).

**Issue créée** : #21 (avec commentaire d'extension pour `.dockerignore`).

---

## 🟡 Findings qualité code (issue #25)

### Pattern `print()` au lieu de `logger`

Le module `logging` est configuré dans `storage.py` mais pas utilisé. Et dans `main.py`, il n'est même pas configuré. Conséquence : les messages ne sont visibles ni dans Sentry, ni dans Langfuse.

Lignes concernées dans `storage.py` : 102, 105, 107.
Lignes concernées dans `main.py` : 5 occurrences (lancement, succès, erreur, démarrage, init Sentry).

À vérifier aussi dans `analyzer.py`, `sender.py`, `gmail_client.py`.

### Docstrings manquants sur `storage.py`

Les 4 fonctions publiques (`get_supabase_client`, `save_email`, `calculate_and_save_weekly_kpis`, `save_weekly_stats`) n'ont aucun docstring.

### Pas de tests pour `storage.py`

`find tests/ -name "*storage*"` retourne vide. Le brief Sprint 1 mentionne 5 tests pytest minimum sur le runtime.

**Issue créée** : #25 (avec commentaire d'extension pour `main.py`).

---

## 💡 Suggestions Sprint 2+ (non bloquantes)

Ces points ne sont pas des bugs, ce sont des optimisations à discuter en équipe.

### Architecture

1. **Séparer logique métier et persistence** : `calculate_and_save_weekly_kpis` dans `storage.py` mélange calcul de KPIs et écriture en base. À extraire dans `apps/email_agent/kpis.py` pour faciliter les tests unitaires.

2. **Magic numbers dans `storage.py`** : les valeurs `45` (temps théorique min) et `80` (tarif horaire) sont en `os.getenv` avec valeurs par défaut, c'est bien. Mais à terme, les centraliser dans une dataclass `KPIConfig` documentée.

3. **Restructuration packages Python** : les imports `# noqa: E402` dans `main.py` révèlent l'usage de `sys.path.insert` au lieu de packages Python propres. À refactorer en S5+ quand le code grossira.

### Sentry

4. **Tag `agent_id` manquant** : ajouter `sentry_sdk.set_tag("agent_id", "email_agent")` après l'init. Important quand on aura 5+ agents en S5+ pour filtrer les erreurs par agent dans le dashboard Sentry.

5. **`before_send` filter** : configurer un filtre pour ignorer les erreurs non-critiques (timeouts réseau passagers, rate limits Anthropic récupérables). Évite de consommer les quotas Sentry pour des erreurs sans intérêt.

### Docker

6. **Pas de multi-stage build** : l'image finale contient `uv` (tooling) en plus du runtime Python. Un multi-stage permettrait de réduire la taille (~50 MB). Pas urgent au S1, à envisager au déploiement Railway en S5.

7. **Installation `uv` via `pip` au lieu du binaire officiel** : `RUN pip install uv --no-cache-dir` ajoute ~2 secondes par build. L'install via `curl -LsSf https://astral.sh/uv/install.sh | sh` est plus rapide et plus propre.

8. **Ordre `WORKDIR` avant `useradd`** : cosmétique, mais inverser permet d'éviter le `chown -R` final.

---

## 🗣️ Sujets pour la rétro Sprint 1

À discuter ensemble lundi avant démarrage Sprint 2 :

### 1. Force-push sur `main` — pattern récurrent

Pendant le Sprint 1, **deux force-push consécutifs** ont été constatés sur `main` :
- `9795be1` → `12db40c` (matin du dimanche, suite aux fixes bugs Sprint 1)
- `12db40c` → `486aada` (soir du dimanche, après le merge de la PR #19)

Conséquences observées :
- ~30 min perdues à diagnostiquer le blocage GitHub Web pour la PR #18 (J6)
- Recréation de 2 branches en `*-v2` avec cherry-pick (PR #18, #19)
- Risque ingérable quand on sera 3+ contributeurs avec les cabinets Vesper aux S11-13

**Décisions proposées** :
- Plus de `git push --force` sur `main` (utiliser `git revert` ou nouvelle PR de fix)
- Activer les **branch protection rules** sur `main` :
  - Require a pull request before merging
  - Require status checks to pass
  - Restrict deletions
  - Ne pas autoriser les force pushes

### 2. Statut RGPD / Zero Data Retention de l'agent email (cf PR #20)

Avant tout test sur la boîte JM Partners (couverte par le secret professionnel), on doit trancher :
- Le compte Anthropic Console actuel a-t-il l'option Zero Data Retention activée ?
- Procédure d'isolation des données clients pour les tests

Bloquant pour le passage payant JM Partners au 1er septembre.

### 3. Pre-commit hook anti-secrets (cf issue #21)

Mettre en place `detect-secrets` ou `gitleaks` en pre-commit hook pour bloquer les futurs commits accidentels de secrets. Ça aurait évité l'incident `token_myvesper.json`.

### 4. Cohérence DoD avant merge sur main

La PR #17 "fix bugs Sprint 1" ne contient qu'un seul fichier (`scripts/run_email_agent.sh`) alors que d'autres fixes (bug Windows `configs/`) sont arrivés via force-push direct. Proposition : toute modification de `main` passe par une PR tracée, jamais via push direct ni force-push.

### 5. Configuration `logging` standardisée dans le projet

Le pattern `print()` vs `logger` se répète dans plusieurs fichiers. Décider une fois pour toutes :
- Quel format de log ? (JSON structuré pour Langfuse ? Texte simple ?)
- Quel niveau par défaut ? (`INFO` en prod, `DEBUG` en dev ?)
- Qui configure le logger ? (chaque agent dans son `main.py` ? Un module commun `packages/shared/logging.py` ?)

---

## Score final review J8

| Aspect | Note | Commentaire |
|---|---|---|
| Conformité brief J8 | 11/12 | Seul critère raté : docstrings storage.py |
| Sécurité (Dockerfile, Sentry, env vars) | 8/10 | Trou sur token Gmail (issue #21) |
| Qualité code | 7/10 | Logger non utilisé, pas de tests storage.py |
| Architecture | 7/10 | Fonctionnel mais quelques mélanges responsabilités |

**Note globale : 8/10** — Le code Sprint 1 est solide, les fondamentaux sécurité sont respectés (sauf token Gmail). Findings traités via 2 issues + 2 commentaires d'extension. Aucun blocker pour démarrer Sprint 2.

---

## Issues créées suite à cette review

- **#21** [security] token_myvesper.json versionné dans Git (+ commentaire `.dockerignore`)
- **#25** [code-review] storage.py — docstrings, logging, tests manquants (+ commentaire `main.py`)

## Référence

Review réalisée pendant le Sprint 1, tâche J8 (samedi-dimanche du sprint).
Méthodologie : audit post-merge sur les fichiers cibles du brief, avec vérification objective par commandes (`mypy`, `grep`, `find`, `git ls-files`) avant chaque finding pour éviter les faux positifs.
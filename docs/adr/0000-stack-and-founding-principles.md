# ADR #0 — Stack et principes fondateurs

## Statut
Accepté

## Contexte
Lancement du projet meta-agent : plateforme de génération et d'exécution d'agents IA.
Besoin de définir la stack technique et les principes fondateurs avant le premier sprint.

## Décisions

### Langage & runtime
- **Python 3.11** — maturité, écosystème IA, typing
- **uv** — gestionnaire de paquets rapide (2026)

### IA & LLM
- **Anthropic Claude** (modèle principal) via API
- **OpenAI** (modèle secondaire/fallback)

### Infrastructure
- **Supabase** — base de données PostgreSQL + auth
- **Railway** — déploiement et hosting
- **Doppler** — gestion des secrets

### Observabilité
- **Langfuse** — tracking des appels LLM, coûts, qualité

### Qualité code
- **ruff** — lint + format
- **mypy** — type checking
- **pre-commit** — hooks automatiques
- **GitHub Actions** — CI (lint, type-check, tests)

## Principes fondateurs
1. Secrets jamais dans le code — toujours via Doppler
2. Toute modification passe par une PR
3. CI verte obligatoire avant merge
4. Code typé et formaté systématiquement

## Conséquences
Stack légère, moderne et adaptée aux projets IA en 2026.

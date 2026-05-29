# Déploiement JM Partners v2.2 — Railway

## Prérequis

- Railway CLI : `npm i -g @railway/cli` puis `railway login`
- Doppler CLI : `brew install dopplerhq/cli/doppler`
- Docker Desktop installé et démarré
- Supabase v2.2 déployé (`db/migrations/001_jmpartners_v2.2.sql` appliquée)

## Étape 1 — Link du projet Railway

```bash
cd /Users/michaelsadoun/meta-agent
railway link
# Sélectionner "meta-agent" ou créer nouveau projet
```

## Étape 2 — Créer l'environnement staging

```bash
railway environment create staging
railway environment staging
```

## Étape 3 — Sync variables Doppler → Railway

```bash
doppler secrets download \
  --project meta-agent \
  --config staging \
  --format env \
  --no-file | railway variables --set
```

Variables critiques à vérifier :
- `TZ=Europe/Paris` (APScheduler — jobs décalés sinon)
- `SUPABASE_SERVICE_KEY` (service_role, pas anon)
- `ANTHROPIC_API_KEY`

## Étape 4 — Build local (dry-run)

```bash
docker build \
  -t jmpartners:v2.2 \
  -f apps/jmpartners/Dockerfile \
  .
docker run --rm jmpartners:v2.2 python -c "from apps.jmpartners.orchestrator import run; print('OK')"
```

## Étape 5 — Déploiement staging

```bash
railway up --service jmpartners
railway logs --service jmpartners --follow
```

Attendu dans les logs :
```
INFO     Orchestrateur JM Partners — démarrage
INFO     APScheduler — 7 jobs nocturnes enregistrés
```

## Étape 6 — Smoke test

```bash
STAGING_URL=$(railway domain --service jmpartners)
curl -s "$STAGING_URL/health" | jq .
# Attendu : {"status":"healthy","db":"connected","scheduler":"running","jobs":7}

# Ou via script CI
bash scripts/run_smoke_test.sh
```

## Étape 7 — Promotion → production

Après validation CIHAN réelle (cible : 8 juin 2026) :

```bash
railway environment production
railway up --service jmpartners
```

## Rollback

```bash
railway rollback --service jmpartners
```

## Points d'attention critiques

### APScheduler + multi-workers

`numReplicas = 1` **obligatoire** en v2.2. Si Railway scale > 1 instance, les 7 jobs nocturnes seront dupliqués (chaque worker crée son propre scheduler). Solution V3 : APScheduler + job store PostgreSQL Supabase.

### Timezone

`TZ=Europe/Paris` doit être définie **dans Railway** (pas seulement dans .env.example). Sans cette variable, les cron jobs s'exécutent en UTC+0 — décalage de 1h (hiver) ou 2h (été) sur les jobs 22h00/23h00/06h00.

### CMD — Script Python direct (pas FastAPI)

`main.py` utilise `BlockingScheduler` APScheduler, pas une app FastAPI. Le CMD est donc `python -m apps.jmpartners.main` (et non uvicorn). Le healthcheck Docker (`curl /health`) ne s'applique pas à ce service — Railway surveille le process directement.

### Healthcheck endpoint

Le service n'expose pas de port HTTP. La directive `HEALTHCHECK` dans le Dockerfile est conservée pour compatibilité, mais Railway s'appuie sur le statut du process. Le `healthcheckPath = "/health"` dans `railway.toml` peut être retiré si Railway remonte des erreurs 404.

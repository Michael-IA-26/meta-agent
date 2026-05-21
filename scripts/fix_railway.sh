#!/bin/bash
# Fix Supabase 401 sur Railway pour email-agent
# Usage : bash scripts/fix_railway.sh
# Prérequis : railway login déjà effectué

set -e

PROJECT_ID="fbf08128-63ba-4815-b69f-b948e7195fd5"
SERVICE_ID="76c961e6-906f-4f0a-8ff9-25c6996e0a7f"

# Récupère les secrets depuis Doppler (projet meta-agent, config prd)
SUPABASE_SERVICE_KEY="$(doppler secrets get SUPABASE_SERVICE_KEY --project meta-agent --config prd --plain 2>/dev/null)"
SUPABASE_URL="$(doppler secrets get SUPABASE_URL --project meta-agent --config prd --plain 2>/dev/null)"
TELEGRAM_CHAT_ID="$(doppler secrets get TELEGRAM_CHAT_ID --project meta-agent --config prd --plain 2>/dev/null)"

if [ -z "$SUPABASE_SERVICE_KEY" ]; then
  echo "ERREUR : impossible de récupérer SUPABASE_SERVICE_KEY depuis Doppler"
  exit 1
fi

echo "=== Fix Railway email-agent ==="

cd "$(dirname "$0")/.." || exit 1

echo "1. Injection des variables..."
railway variables --set "SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY" \
  --service "$SERVICE_ID" 2>/dev/null || \
railway variables set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY"

railway variables --set "SUPABASE_URL=$SUPABASE_URL" \
  --service "$SERVICE_ID" 2>/dev/null || \
railway variables set SUPABASE_URL="$SUPABASE_URL"

railway variables --set "TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID" \
  --service "$SERVICE_ID" 2>/dev/null || \
railway variables set TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID"

echo "2. Vérification des variables injectées..."
railway variables 2>/dev/null || echo "(vérification manuelle requise)"

echo "3. Redémarrage du service..."
railway redeploy --yes 2>/dev/null || echo "Redeploy via dashboard Railway requis"

echo "4. Logs (Ctrl+C pour arrêter)..."
sleep 5
railway logs --tail 50 2>/dev/null || echo "Voir logs via dashboard Railway"

echo "=== Fix terminé ==="

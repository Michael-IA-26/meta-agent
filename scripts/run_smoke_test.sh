#!/usr/bin/env bash
set -euo pipefail

echo "=== JM Partners v2.2 — Smoke Test Railway ==="
echo "Environment : ${RAILWAY_ENVIRONMENT:-local}"

# 1. Vérifier les vars critiques
for var in SUPABASE_URL SUPABASE_SERVICE_KEY ANTHROPIC_API_KEY SMTP_PASSWORD; do
    if [ -z "${!var:-}" ]; then
        echo "❌ Variable manquante : $var"
        exit 1
    fi
    echo "✅ $var définie"
done

# 2. Lancer les smoke tests
uv run pytest tests/test_jmpartners/test_smoke_railway.py \
    -v \
    -m smoke \
    --tb=short \
    --no-header

echo "=== Smoke test terminé ==="

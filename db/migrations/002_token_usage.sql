-- ============================================================
-- db/migrations/002_token_usage.sql
-- Suivi consommation tokens Anthropic par agent
-- À exécuter après 001_jmpartners_v2.2.sql
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS token_usage (
    id            UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name    TEXT          NOT NULL,
    model         TEXT          NOT NULL DEFAULT 'claude-sonnet-4-6',
    date          DATE          NOT NULL DEFAULT CURRENT_DATE,
    called_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    input_tokens  INTEGER       NOT NULL CHECK (input_tokens  >= 0),
    output_tokens INTEGER       NOT NULL CHECK (output_tokens >= 0),
    cost_eur      NUMERIC(10,6) NOT NULL DEFAULT 0 CHECK (cost_eur >= 0)
);

-- Requête dashboard : agrégats par agent sur période
CREATE INDEX IF NOT EXISTS idx_token_usage_agent_date ON token_usage(agent_name, date);
-- Graphe 30 jours : lecture chronologique
CREATE INDEX IF NOT EXISTS idx_token_usage_date       ON token_usage(date DESC);

ALTER TABLE token_usage ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "beta_auth_all_token_usage"
        ON token_usage FOR ALL TO authenticated
        USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Vérification
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'token_usage'
    ) THEN
        RAISE EXCEPTION 'token_usage table missing after migration';
    END IF;
    RAISE NOTICE '✅ MIGRATION 002 OK — token_usage table créée';
END $$;

COMMIT;

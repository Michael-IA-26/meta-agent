-- ── 003 : File de jobs Lovable ───────────────────────────────────────────────
-- Idempotent. Aucune donnée.

CREATE TABLE IF NOT EXISTS jobs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    type        TEXT        NOT NULL,
    payload     JSONB,
    statut      TEXT        NOT NULL DEFAULT 'pending'
                            CHECK (statut IN ('pending', 'running', 'done', 'error')),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ
);

-- Index pour le poller (ORDER BY created_at ASC)
CREATE INDEX IF NOT EXISTS idx_jobs_statut_created ON jobs(statut, created_at);

-- RLS
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    -- SELECT : authenticated peut lire ses jobs
    BEGIN
        EXECUTE 'CREATE POLICY "jobs_select_authenticated" ON jobs
                 FOR SELECT TO authenticated USING (true)';
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
    -- INSERT : authenticated peut créer des jobs
    BEGIN
        EXECUTE 'CREATE POLICY "jobs_insert_authenticated" ON jobs
                 FOR INSERT TO authenticated WITH CHECK (true)';
    EXCEPTION WHEN duplicate_object THEN NULL;
    END;
END $$;

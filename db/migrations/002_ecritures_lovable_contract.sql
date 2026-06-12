-- ── 002 : Contrat ecritures Lovable + RLS lecture seule ──────────────────────
-- Idempotent (IF NOT EXISTS / IF EXISTS). Aucune donnée modifiée.

-- ── 1. Colonnes ecritures (page Pré-saisie Lovable) ──────────────────────────

ALTER TABLE ecritures
    ADD COLUMN IF NOT EXISTS journal         TEXT,            -- ACH / VEN / BQ
    ADD COLUMN IF NOT EXISTS reference       TEXT,            -- réf pièce
    ADD COLUMN IF NOT EXISTS source          TEXT DEFAULT 'ia',  -- ia / manuel
    ADD COLUMN IF NOT EXISTS score_confiance NUMERIC(4,2);    -- 0..1 (onglet Validés auto)

-- ── 2. RLS lecture seule pour authenticated (Lovable) ────────────────────────
-- Remplace les politiques "beta_auth_all_*" (FOR ALL) sur les 4 tables exposées
-- par des politiques SELECT-seulement. Le rôle service_role contourne RLS
-- pour les opérations d'écriture backend.

DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY['ecritures', 'documents', 'dossiers', 'declarations_tva'];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- Supprime l'ancienne politique broad (idempotent)
        EXECUTE format('DROP POLICY IF EXISTS "beta_auth_all_%1$s" ON %1$s', t);

        -- Crée la politique lecture seule (idempotent via exception)
        BEGIN
            EXECUTE format(
                'CREATE POLICY "lovable_select_%1$s" ON %1$s
                 FOR SELECT TO authenticated USING (true)',
                t
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END;
    END LOOP;
END $$;

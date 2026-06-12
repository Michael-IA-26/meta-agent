-- ── 004 : RLS UPDATE ecritures pour validation Lovable ──────────────────────
-- Idempotent (DROP POLICY IF EXISTS + CREATE). Aucune donnée modifiée.
-- Conserve lovable_select_* intactes. Ne touche pas service_role.

DROP POLICY IF EXISTS "lovable_update_ecritures" ON ecritures;

CREATE POLICY "lovable_update_ecritures" ON ecritures
    FOR UPDATE TO authenticated
    USING (true)
    WITH CHECK (true);

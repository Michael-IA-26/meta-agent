-- Migration 005: v_presaisie read surface for Lovable Pré-saisie page
-- Fully idempotent, zero data changes.

-- 1. View with security_invoker so base-table RLS applies
CREATE OR REPLACE VIEW v_presaisie WITH (security_invoker = on) AS
SELECT
    id,
    dossier_id,
    date_ecriture,
    reference,
    tiers,
    journal,
    CASE journal
        WHEN 'ACH' THEN 'Achat'
        WHEN 'VEN' THEN 'Vente'
        WHEN 'BQ'  THEN 'Banque'
        ELSE 'Autre'
    END AS type,
    compte_debit,
    compte_credit,
    montant,
    montant_ttc,
    source,
    score_confiance,
    badge_anomalie,
    statut
FROM ecritures;

-- 2. Indexes for Lovable query patterns
CREATE INDEX IF NOT EXISTS idx_ecritures_dossier_statut
    ON ecritures (dossier_id, statut);

CREATE INDEX IF NOT EXISTS idx_ecritures_date
    ON ecritures (date_ecriture);

CREATE INDEX IF NOT EXISTS idx_ecritures_anomalie
    ON ecritures (badge_anomalie)
    WHERE badge_anomalie = true;

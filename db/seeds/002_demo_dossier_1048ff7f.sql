-- =============================================================================
-- Seed de démo — dossier 1048ff7f-f41c-4c88-8290-d843de803843
-- PRÉ-REQUIS : le dossier (et son contact) doivent déjà exister.
-- Idempotent : ON CONFLICT DO NOTHING sur les UUID fixés.
-- =============================================================================

-- ── 1. Document ───────────────────────────────────────────────────────────────

INSERT INTO documents (
    id,
    dossier_id,
    nom,
    type_document,
    statut,
    source,
    url_storage,
    contenu_extrait,
    score_ocr,
    score_confiance,
    categorie
) VALUES (
    'demodoc1-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'FACT-2026-0847_BureauDupont.pdf',
    'facture_achat',
    'a_saisir_sage',
    'outlook',
    'https://umentbvgavplnbyanhmy.supabase.co/storage/v1/object/public/documents/1048ff7f/FACT-2026-0847.pdf',
    '{
        "fournisseur":     "Bureau Dupont SARL",
        "numero_facture":  "FACT-2026-0847",
        "date_facture":    "2026-06-15",
        "montant_ht":      2500.00,
        "montant_tva":     500.00,
        "montant_ttc":     3000.00,
        "taux_tva":        20.0,
        "devise":          "EUR"
    }',
    0.95,
    0.92,
    'fournisseurs'
)
ON CONFLICT (id) DO NOTHING;


-- ── 2. Écritures ──────────────────────────────────────────────────────────────

-- 607 / 401 — charge HT
INSERT INTO ecritures (
    id,
    dossier_id,
    piece_justificative_id,
    date_ecriture,
    libelle,
    compte_debit,
    compte_credit,
    montant,
    montant_ht,
    montant_ttc,
    taux_tva,
    tiers,
    statut,
    source_validation
) VALUES (
    'demoecr1-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'demodoc1-f41c-4c88-8290-d843de803843',
    '2026-06-15',
    'Achat Bureau Dupont SARL — FACT-2026-0847',
    '607',
    '401',
    2500.00,
    2500.00,
    3000.00,
    20.0,
    'Bureau Dupont SARL',
    'a_valider',
    'claude'
)
ON CONFLICT (id) DO NOTHING;

-- 44566 / 401 — TVA déductible
INSERT INTO ecritures (
    id,
    dossier_id,
    piece_justificative_id,
    date_ecriture,
    libelle,
    compte_debit,
    compte_credit,
    montant,
    taux_tva,
    tiers,
    statut,
    source_validation
) VALUES (
    'demoecr2-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'demodoc1-f41c-4c88-8290-d843de803843',
    '2026-06-15',
    'TVA déductible Bureau Dupont SARL — FACT-2026-0847',
    '44566',
    '401',
    500.00,
    20.0,
    'Bureau Dupont SARL',
    'a_valider',
    'claude'
)
ON CONFLICT (id) DO NOTHING;


-- ── 3. Journaux ───────────────────────────────────────────────────────────────
-- type_action utilisées (valeurs CHECK réelles) :
--   'document_recu'     ← ta demande "reception_mail"
--   'ocr_traite'        ← ta demande "analyse_document"
--   'presaisie_generee' ← ta demande "generation_ecritures"

INSERT INTO journaux (id, dossier_id, type_action, statut, contenu, metadata, created_at)
VALUES
(
    'demojnl1-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'document_recu',
    'ok',
    'Facture FACT-2026-0847 reçue de Bureau Dupont SARL via Outlook',
    '{
        "source":       "outlook",
        "expediteur":   "facturation@bureau-dupont.fr",
        "nom_fichier":  "FACT-2026-0847_BureauDupont.pdf",
        "taille_ko":    142
    }',
    NOW() - INTERVAL '30 seconds'
),
(
    'demojnl2-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'ocr_traite',
    'ok',
    'OCR OK — score 0.95, classifié facture_achat, confiance 0.92',
    '{
        "score_ocr":       0.95,
        "score_confiance": 0.92,
        "type_document":   "facture_achat",
        "fournisseur":     "Bureau Dupont SARL",
        "montant_ttc":     3000.00
    }',
    NOW() - INTERVAL '15 seconds'
),
(
    'demojnl3-f41c-4c88-8290-d843de803843',
    '1048ff7f-f41c-4c88-8290-d843de803843',
    'presaisie_generee',
    'ok',
    '2 écritures générées — 607/401 2 500,00 € + 44566/401 500,00 €',
    '{
        "nb_ecritures": 2,
        "montant_ht":   2500.00,
        "montant_tva":  500.00,
        "montant_ttc":  3000.00,
        "ecriture_ids": [
            "demoecr1-f41c-4c88-8290-d843de803843",
            "demoecr2-f41c-4c88-8290-d843de803843"
        ]
    }',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

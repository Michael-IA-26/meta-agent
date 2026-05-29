-- =============================================================================
-- Seed de test — Dossier pilote CIHAN
-- À exécuter APRÈS la migration 001_jmpartners_v2.2.sql
-- =============================================================================

-- Nettoyage préalable (idempotent)
DELETE FROM documents       WHERE message_id LIKE 'seed-cihan-%';
DELETE FROM ecritures       WHERE libelle    LIKE '[SEED-CIHAN]%';
DELETE FROM dossiers        WHERE nom = 'CIHAN';
DELETE FROM contacts        WHERE email = 'compta@cihan.fr';

-- ─── Contact CIHAN ────────────────────────────────────────────────────────────

INSERT INTO contacts (id, nom, email, telephone, cabinet_id)
VALUES (
    'cihan-contact-uuid-0001',
    'CIHAN',
    'compta@cihan.fr',
    '+33 1 23 45 67 89',
    'jmpartners'
);

-- ─── Dossier CIHAN ────────────────────────────────────────────────────────────

INSERT INTO dossiers (id, contact_id, cabinet_id, nom, type_dossier, statut)
VALUES (
    'cihan-dossier-uuid-0001',
    'cihan-contact-uuid-0001',
    'jmpartners',
    'CIHAN',
    'restauration',
    'actif'
);

-- ─── Documents de test ────────────────────────────────────────────────────────

-- Facture fournisseur en attente OCR
INSERT INTO documents (
    id, nom_fichier, source, message_id, expediteur,
    dossier_id, statut, date_reception
) VALUES (
    'cihan-doc-uuid-0001',
    'facture_fournisseur_mai2026.pdf',
    'outlook',
    'seed-cihan-msg-001',
    'facturation@fournisseur-a.fr',
    'cihan-dossier-uuid-0001',
    'en_attente_ocr',
    NOW()
);

-- Relevé bancaire en attente OCR
INSERT INTO documents (
    id, nom_fichier, source, message_id, expediteur,
    dossier_id, statut, date_reception
) VALUES (
    'cihan-doc-uuid-0002',
    'releve_bancaire_mai2026.pdf',
    'regate',
    'seed-cihan-msg-002',
    NULL,
    'cihan-dossier-uuid-0001',
    'en_attente_ocr',
    NOW()
);

-- Document multi-factures en attente OCR
INSERT INTO documents (
    id, nom_fichier, source, message_id, expediteur,
    dossier_id, statut, multi_dossiers, date_reception
) VALUES (
    'cihan-doc-uuid-0003',
    'factures_multiples_mai2026.pdf',
    'outlook',
    'seed-cihan-msg-003',
    'direction@fournisseur-b.fr',
    'cihan-dossier-uuid-0001',
    'en_attente_ocr',
    TRUE,
    NOW()
);

-- ─── Écritures de test (pré-générées, à valider) ─────────────────────────────

-- Écriture charge fournisseur (restauration — TVA 10%)
INSERT INTO ecritures (
    id, document_id, dossier_id,
    journal, compte_debit, compte_credit,
    tiers, libelle, montant_ht, montant_tva, montant_ttc, taux_tva,
    source_validation, statut, date_ecriture
) VALUES (
    'cihan-ecriture-uuid-0001',
    'cihan-doc-uuid-0001',
    'cihan-dossier-uuid-0001',
    'ACH', '606100', '401000',
    'Fournisseur A', '[SEED-CIHAN] Achat denrées mai 2026',
    1000.00, 100.00, 1100.00, 10.0,
    'regle_comptable', 'a_valider',
    CURRENT_DATE
);

-- Écriture TVA déductible correspondante
INSERT INTO ecritures (
    id, document_id, dossier_id,
    journal, compte_debit, compte_credit,
    tiers, libelle, montant_ht, montant_tva, montant_ttc, taux_tva,
    source_validation, statut, date_ecriture
) VALUES (
    'cihan-ecriture-uuid-0002',
    'cihan-doc-uuid-0001',
    'cihan-dossier-uuid-0001',
    'ACH', '445660', '401000',
    'Fournisseur A', '[SEED-CIHAN] TVA déductible mai 2026',
    0.00, 100.00, 100.00, 10.0,
    'regle_comptable', 'a_valider',
    CURRENT_DATE
);

-- ─── Déclaration TVA test ─────────────────────────────────────────────────────

INSERT INTO declarations_tva (
    id, dossier_id, contact_id, periode, deadline, statut
) VALUES (
    'cihan-tva-uuid-0001',
    'cihan-dossier-uuid-0001',
    'cihan-contact-uuid-0001',
    'mai-2026',
    (CURRENT_DATE + INTERVAL '10 days')::DATE,
    'a_preparer'
);

-- ─── Collaborateur test ───────────────────────────────────────────────────────

INSERT INTO collaborateurs (id, nom, email, cabinet_id)
VALUES (
    'cihan-collab-uuid-0001',
    'Jean-Michel',
    'jm@jmpartners.fr',
    'jmpartners'
)
ON CONFLICT (email) DO NOTHING;

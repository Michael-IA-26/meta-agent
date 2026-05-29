-- ============================================================
-- db/seeds/001_cihan.sql
-- Seed pilote — Dossier CIHAN (SASU Restauration)
-- À exécuter APRÈS la migration 001_jmpartners_v2.2.sql
-- Pas de transaction : chaque INSERT est indépendant
-- Idempotent via ON CONFLICT DO NOTHING
-- ============================================================

-- ── 1. Utilisateur responsable (comptable JM Partners) ───────
INSERT INTO utilisateurs (id, nom, email, role, telegram_chat_id)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Michael Sadoun',
    'michael@jmpartners.fr',
    'admin',
    NULL
)
ON CONFLICT (email) DO NOTHING;

-- ── 2. Contacts CIHAN ────────────────────────────────────────
-- Contact 1 : gérant de CIHAN (interlocuteur principal)
INSERT INTO contacts (id, nom, email, telephone, siren, forme_juridique, responsable_id)
VALUES (
    'cihan-0000-0000-0000-contact000001',
    'Mohamed Hassani',
    'gerant@cihan-restaurant.fr',
    '06 12 34 56 78',
    '912345678',
    'SASU',
    '00000000-0000-0000-0000-000000000001'
)
ON CONFLICT (siren) DO NOTHING;

-- Contact 2 : comptable interne CIHAN (reçoit les relevés, prépare docs)
INSERT INTO contacts (id, nom, email, telephone, siren, forme_juridique, responsable_id)
VALUES (
    'cihan-0000-0000-0000-contact000002',
    'Sophie Martin',
    'compta@cihan-restaurant.fr',
    '06 98 76 54 32',
    NULL,
    'SASU',
    '00000000-0000-0000-0000-000000000001'
)
ON CONFLICT DO NOTHING;

-- ── 3. Dossier CIHAN ─────────────────────────────────────────
-- Dossier TVA 2026, secteur restauration
-- contact_id → gérant (Contact 1)
-- FK RESTRICT : le dossier doit être archivé avant suppression du contact
INSERT INTO dossiers (id, contact_id, type, exercice, statut, secteur, responsable_id, deadline)
VALUES (
    'cihan-0000-0000-0000-dossier00001',
    'cihan-0000-0000-0000-contact000001',
    'tva',
    '2026',
    'en_cours',
    'restauration',
    '00000000-0000-0000-0000-000000000001',
    '2026-06-15'
)
ON CONFLICT DO NOTHING;

-- ── 4. Documents fictifs (statut initial : en_attente_ocr) ───

-- Document 1 : facture achat fournisseur (Metro)
INSERT INTO documents (
    id, dossier_id, contact_id, nom, type_document, statut,
    source, message_id, url_storage, deadline, urgence
)
VALUES (
    'cihan-0000-0000-0000-document00001',
    'cihan-0000-0000-0000-dossier00001',
    'cihan-0000-0000-0000-contact000001',
    'Facture achat Metro mai 2026',
    'facture_achat',
    'en_attente_ocr',
    'outlook',
    'seed-cihan-msg-facture-achat-001',
    NULL,
    '2026-06-10',
    'J-7'
)
ON CONFLICT DO NOTHING;

-- Document 2 : facture vente client (table événementielle)
INSERT INTO documents (
    id, dossier_id, contact_id, nom, type_document, statut,
    source, message_id, url_storage, deadline, urgence
)
VALUES (
    'cihan-0000-0000-0000-document00002',
    'cihan-0000-0000-0000-dossier00001',
    'cihan-0000-0000-0000-contact000001',
    'Facture vente événement mai 2026',
    'facture_vente',
    'en_attente_ocr',
    'manuel',
    'seed-cihan-msg-facture-vente-001',
    NULL,
    '2026-06-10',
    'J-7'
)
ON CONFLICT DO NOTHING;

-- Document 3 : relevé bancaire BNP mai 2026
INSERT INTO documents (
    id, dossier_id, contact_id, nom, type_document, statut,
    source, message_id, url_storage, deadline, urgence
)
VALUES (
    'cihan-0000-0000-0000-document00003',
    'cihan-0000-0000-0000-dossier00001',
    'cihan-0000-0000-0000-contact000001',
    'Relevé bancaire BNP mai 2026',
    'releve_bancaire',
    'en_attente_ocr',
    'regate',
    'seed-cihan-msg-releve-bnp-001',
    NULL,
    '2026-06-15',
    'J-7'
)
ON CONFLICT DO NOTHING;

-- ── 5. Déclaration TVA initiale ───────────────────────────────
INSERT INTO declarations_tva (
    id, dossier_id, contact_id, periode, deadline, statut
)
VALUES (
    'cihan-0000-0000-0000-decltva00001',
    'cihan-0000-0000-0000-dossier00001',
    'cihan-0000-0000-0000-contact000001',
    'mai-2026',
    '2026-06-15',
    'pieces_manquantes'
)
ON CONFLICT DO NOTHING;

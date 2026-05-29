-- ============================================================
-- db/migrations/001_jmpartners_v2.2.sql
-- Migration JM Partners v2.1 → v2.2
-- Projet : Michael-IA-26's Project (eu-west-1)
-- Idempotente : peut être relancée sans erreur si tables existent
-- ============================================================

BEGIN;

-- ── 0. EXTENSIONS ────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector 1536 dims (PresaisieAgent)
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- fuzzy libellés bancaires (LettrageAgent)

-- ── 1. FONCTION TRIGGER ──────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

-- ── 2. ENUM ──────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE statut_document AS ENUM (
        'en_attente_ocr',           -- collecté, OCR pas encore fait
        'a_trier',                  -- OCR ok (score ≥ 0.70), à classifier
        'en_attente_collaborateur', -- score < 0.80 ou ambigu → intervention humaine
        'a_saisir_sage',            -- validé, prêt pour RPA Sage
        'valide',                   -- saisi et confirmé en Sage
        'archive'                   -- archivé en GED
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── 3. utilisateurs ──────────────────────────────────────────
-- Comptables du cabinet — cible FK pour contacts et dossiers
CREATE TABLE IF NOT EXISTS utilisateurs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom              TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE,
    role             TEXT NOT NULL CHECK (role IN ('admin', 'comptable', 'assistant')),
    telegram_chat_id TEXT,
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- ── 4. contacts ──────────────────────────────────────────────
-- Clients du cabinet (ex: CIHAN, Le Bistrot du Port…)
-- RESTRICT : impossible de supprimer un comptable ayant des clients actifs
CREATE TABLE IF NOT EXISTS contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom             TEXT NOT NULL,
    email           TEXT,
    telephone       TEXT,
    siren           TEXT UNIQUE,
    forme_juridique TEXT,
    responsable_id  UUID REFERENCES utilisateurs(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
DROP TRIGGER IF EXISTS contacts_updated_at ON contacts;
CREATE TRIGGER contacts_updated_at
    BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 5. dossiers ──────────────────────────────────────────────
-- RESTRICT sur contact_id : forcer l'archivage explicite du dossier
--   avant de pouvoir supprimer le client — zéro risque perte données
-- RESTRICT sur responsable_id : un comptable actif ne peut pas être supprimé
CREATE TABLE IF NOT EXISTS dossiers (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id     UUID NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    type           TEXT NOT NULL CHECK (type IN ('bilan', 'tva', 'is', 'paie', 'creation')),
    exercice       TEXT NOT NULL,
    statut         TEXT DEFAULT 'en_cours' CHECK (statut IN ('en_cours', 'complet', 'valide', 'archive')),
    secteur        TEXT,       -- restauration, btp, retail… (v2.2)
    responsable_id UUID REFERENCES utilisateurs(id) ON DELETE RESTRICT,
    deadline       DATE,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE dossiers ADD COLUMN IF NOT EXISTS secteur TEXT;
DROP TRIGGER IF EXISTS dossiers_updated_at ON dossiers;
CREATE TRIGGER dossiers_updated_at
    BEFORE UPDATE ON dossiers FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 6. documents ─────────────────────────────────────────────
-- CASCADE : documents supprimés si leur dossier l'est
-- SET NULL : contact dissociable sans supprimer le document
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id      UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    contact_id      UUID REFERENCES contacts(id) ON DELETE SET NULL,
    nom             TEXT NOT NULL,
    type_document   TEXT NOT NULL,
    statut          statut_document NOT NULL DEFAULT 'en_attente_ocr',
    source          TEXT CHECK (source IN ('outlook', 'regate', 'pennylane', 'manuel')),
    message_id      TEXT,               -- anti-doublon CollecteAgent (index unique partiel)
    url_storage     TEXT,               -- URL Supabase Storage (fichier brut)
    archive_path    TEXT,               -- chemin GED après archivage (GEDAgent)
    contenu_extrait JSONB DEFAULT '{}', -- texte structuré retourné par OCR Claude
    score_ocr       NUMERIC(4,2),       -- lisibilité OCR (0.00–1.00)
    score_confiance NUMERIC(4,2),       -- confiance classification (0.00–1.00)
    raison_attente  TEXT,               -- motif blocage : score_ocr_faible, multi_dossiers…
    categorie       TEXT,               -- fournisseurs/clients/banques/fiscal_social/autres
    multi_dossiers  BOOLEAN DEFAULT FALSE,
    badge_anomalie  BOOLEAN DEFAULT FALSE,
    anomalie_desc   TEXT,
    deadline        DATE,
    urgence         TEXT CHECK (urgence IN ('J-15', 'J-7', 'J-3', 'J-0')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_message_id
    ON documents(message_id) WHERE message_id IS NOT NULL;
DROP TRIGGER IF EXISTS documents_updated_at ON documents;
CREATE TRIGGER documents_updated_at
    BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 7. journaux ──────────────────────────────────────────────
-- Append-only — pas d'updated_at
-- SET NULL partout : les journaux survivent à toute suppression
CREATE TABLE IF NOT EXISTS journaux (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id     UUID REFERENCES contacts(id) ON DELETE SET NULL,
    dossier_id     UUID REFERENCES dossiers(id) ON DELETE SET NULL,
    utilisateur_id UUID REFERENCES utilisateurs(id) ON DELETE SET NULL,
    type_action    TEXT NOT NULL CHECK (type_action IN (
        'email_recu', 'email_envoye', 'relance_envoyee', 'relance_skipped',
        'verification_documents', 'alerte_tva', 'alerte_echeance',
        'document_recu', 'dossier_valide', 'note_manuelle',
        'ocr_traite', 'tri_classifie', 'presaisie_generee', 'verification_faite',
        'lettrage_auto', 'fnp_detectee', 'revision_anomalie',
        'ged_archive', 'sage_saisie', 'sage_sync'
    )),
    contenu        TEXT,
    statut         TEXT DEFAULT 'ok' CHECK (statut IN ('ok', 'erreur', 'skipped')),
    metadata       JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- ── 8. ecritures ─────────────────────────────────────────────
-- CASCADE : écritures supprimées si le dossier l'est
-- SET NULL : pièce justificative dissociable sans supprimer l'écriture
CREATE TABLE IF NOT EXISTS ecritures (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id             UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    piece_justificative_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    date_ecriture          DATE NOT NULL,
    libelle                TEXT NOT NULL,
    compte_debit           TEXT NOT NULL,
    compte_credit          TEXT NOT NULL,
    montant                NUMERIC(12,2) NOT NULL,
    montant_ht             NUMERIC(12,2),
    montant_ttc            NUMERIC(12,2),
    taux_tva               NUMERIC(5,2),
    tiers                  TEXT,
    compte_tiers           TEXT,
    statut                 TEXT DEFAULT 'a_presaisir' CHECK (statut IN (
        'a_presaisir', 'a_valider', 'valide', 'a_saisir_sage', 'rejete'
    )),
    source_validation      TEXT DEFAULT 'a_verifier' CHECK (source_validation IN (
        'claude', 'collaborateur', 'a_verifier'
    )),
    est_lettree            BOOLEAN DEFAULT FALSE,
    lettre                 TEXT,
    badge_anomalie         BOOLEAN DEFAULT FALSE,
    anomalie_desc          TEXT,
    created_at             TIMESTAMPTZ DEFAULT now(),
    updated_at             TIMESTAMPTZ DEFAULT now()
);
-- ALTER safety : si ecritures existe déjà en v2.1 (sans les colonnes v2.2)
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS montant_ht        NUMERIC(12,2);
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS montant_ttc       NUMERIC(12,2);
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS taux_tva          NUMERIC(5,2);
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS tiers             TEXT;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS compte_tiers      TEXT;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS statut            TEXT DEFAULT 'a_presaisir';
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS source_validation TEXT DEFAULT 'a_verifier';
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS est_lettree       BOOLEAN DEFAULT FALSE;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS lettre            TEXT;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS badge_anomalie    BOOLEAN DEFAULT FALSE;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS anomalie_desc     TEXT;
ALTER TABLE ecritures ADD COLUMN IF NOT EXISTS updated_at        TIMESTAMPTZ DEFAULT now();
DROP TRIGGER IF EXISTS ecritures_updated_at ON ecritures;
CREATE TRIGGER ecritures_updated_at
    BEFORE UPDATE ON ecritures FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 9. syncs_sage ────────────────────────────────────────────
-- Suivi des imports FEC depuis Sage (MiroirSageAgent)
CREATE TABLE IF NOT EXISTS syncs_sage (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabinet_id       TEXT NOT NULL,
    fichier_fec      TEXT NOT NULL,
    hash_md5         TEXT NOT NULL,
    lignes_importees INT DEFAULT 0,
    lignes_ignorees  INT DEFAULT 0,
    statut           TEXT DEFAULT 'en_cours' CHECK (statut IN ('en_cours', 'termine', 'erreur')),
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);
DROP TRIGGER IF EXISTS syncs_sage_updated_at ON syncs_sage;
CREATE TRIGGER syncs_sage_updated_at
    BEFORE UPDATE ON syncs_sage FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 10. ecritures_sage ───────────────────────────────────────
-- Miroir FEC Sage — immuable une fois importé, pas d'updated_at
-- CASCADE : lignes supprimées si le dossier l'est
-- SET NULL : on peut supprimer un sync sans perdre les lignes importées
CREATE TABLE IF NOT EXISTS ecritures_sage (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id    UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    sync_id       UUID REFERENCES syncs_sage(id) ON DELETE SET NULL,
    date_ecriture DATE NOT NULL,
    libelle       TEXT NOT NULL,
    compte_debit  TEXT NOT NULL,
    compte_credit TEXT NOT NULL,
    montant_ht    NUMERIC(12,2),
    montant_ttc   NUMERIC(12,2),
    taux_tva      NUMERIC(5,2),
    tiers         TEXT,
    journal_code  TEXT,
    piece_ref     TEXT,
    source        TEXT DEFAULT 'collaborateur',  -- paie / od_manuel / collaborateur
    hash_md5      TEXT UNIQUE,                   -- anti-doublon strict (MiroirSageAgent)
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ── 11. declarations_tva ─────────────────────────────────────
-- CASCADE : déclarations supprimées si le dossier ou le contact l'est
CREATE TABLE IF NOT EXISTS declarations_tva (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id        UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    periode           TEXT NOT NULL,
    deadline          DATE NOT NULL,
    montant_ca        NUMERIC(12,2),
    montant_tva       NUMERIC(12,2),
    statut            TEXT DEFAULT 'a_preparer' CHECK (statut IN (
        'a_preparer', 'pieces_manquantes', 'pret', 'soumis', 'valide'
    )),
    alerte_envoyee_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now()
);
DROP TRIGGER IF EXISTS declarations_tva_updated_at ON declarations_tva;
CREATE TRIGGER declarations_tva_updated_at
    BEFORE UPDATE ON declarations_tva FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 12. acomptes_is ──────────────────────────────────────────
-- Quasi-immuables après création — pas d'updated_at
-- CASCADE : acomptes supprimés si le dossier ou le contact l'est
CREATE TABLE IF NOT EXISTS acomptes_is (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id        UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    contact_id        UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    numero_acompte    INT NOT NULL CHECK (numero_acompte IN (1, 2, 3, 4)),
    exercice          TEXT NOT NULL,
    deadline          DATE NOT NULL,
    montant           NUMERIC(12,2),
    statut            TEXT DEFAULT 'a_payer' CHECK (statut IN ('a_payer', 'paye', 'exonere')),
    alerte_envoyee_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- ── 13. provisions_fnp ───────────────────────────────────────
-- FNP/FAE détectées en décembre uniquement (FNPFAEAgent)
-- CASCADE : provisions supprimées si le dossier l'est
-- SET NULL : suppression d'un collaborateur ne doit pas effacer la provision
CREATE TABLE IF NOT EXISTS provisions_fnp (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id     UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    tiers          TEXT NOT NULL,
    compte         TEXT NOT NULL,    -- 408xxx (FNP) ou 418xxx (FAE)
    type_provision TEXT NOT NULL CHECK (type_provision IN ('fnp', 'fae')),
    montant_estime NUMERIC(12,2) NOT NULL,
    montant_reel   NUMERIC(12,2),
    statut         TEXT DEFAULT 'a_valider_fnp' CHECK (statut IN (
        'a_valider_fnp', 'valide', 'rejete'
    )),
    exercice       INT NOT NULL,
    validee_par    UUID REFERENCES utilisateurs(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);
DROP TRIGGER IF EXISTS provisions_fnp_updated_at ON provisions_fnp;
CREATE TRIGGER provisions_fnp_updated_at
    BEFORE UPDATE ON provisions_fnp FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 14. apprentissage ────────────────────────────────────────
-- Feedback collaborateur — règles de lettrage + ML futur (LettrageAgent)
CREATE TABLE IF NOT EXISTS apprentissage (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    libelle_bancaire TEXT NOT NULL,
    compte_debit     TEXT NOT NULL,
    compte_credit    TEXT NOT NULL,
    tiers            TEXT,
    source           TEXT DEFAULT 'collaborateur',
    confiance        NUMERIC(4,2) DEFAULT 0.90,
    nb_utilisations  INT DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_apprentissage_libelle_unique
    ON apprentissage(libelle_bancaire);
DROP TRIGGER IF EXISTS apprentissage_updated_at ON apprentissage;
CREATE TRIGGER apprentissage_updated_at
    BEFORE UPDATE ON apprentissage FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 15. doublons_detectes ────────────────────────────────────
-- CASCADE : doublon supprimé si l'écriture source l'est
CREATE TABLE IF NOT EXISTS doublons_detectes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ecriture_id  UUID NOT NULL REFERENCES ecritures(id) ON DELETE CASCADE,
    doublon_ref  TEXT,    -- piece_ref dans ecritures_sage (si cross-Sage)
    type_doublon TEXT NOT NULL CHECK (type_doublon IN ('exact', 'approche', 'montant_tiers')),
    statut       TEXT DEFAULT 'en_attente' CHECK (statut IN (
        'en_attente', 'confirme', 'faux_positif'
    )),
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ── 16. revision ─────────────────────────────────────────────
-- Anomalies nocturnes (RevisionAgent) — corrigee=false = en attente traitement
-- SET NULL : l'historique survit à la suppression d'un dossier ou écriture
CREATE TABLE IF NOT EXISTS revision (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id    UUID REFERENCES dossiers(id) ON DELETE SET NULL,
    ecriture_id   UUID REFERENCES ecritures(id) ON DELETE SET NULL,
    type_anomalie TEXT NOT NULL CHECK (type_anomalie IN (
        'compte_incorrect', 'tiers_imprecis', 'doublon', 'lettrage_impossible'
    )),
    description   TEXT NOT NULL,
    severite      TEXT DEFAULT 'validation_requise',
    corrigee      BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
DROP TRIGGER IF EXISTS revision_updated_at ON revision;
CREATE TRIGGER revision_updated_at
    BEFORE UPDATE ON revision FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── 17. lettrages ────────────────────────────────────────────
-- Immuable : dé-lettrage = nouvelle ligne, jamais de UPDATE
-- CASCADE sur les 3 FK : sans dossier ou écriture, le lettrage est orphelin
CREATE TABLE IF NOT EXISTS lettrages (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id            UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    ecriture_reglement_id UUID NOT NULL REFERENCES ecritures(id) ON DELETE CASCADE,
    ecriture_facture_id   UUID NOT NULL REFERENCES ecritures(id) ON DELETE CASCADE,
    code_lettre           TEXT NOT NULL,    -- A, B, C… séquentiel par dossier
    type_lettrage         TEXT NOT NULL CHECK (type_lettrage IN (
        'exact', 'approche', 'apprentissage'
    )),
    confiance             NUMERIC(4,2) NOT NULL,
    created_at            TIMESTAMPTZ DEFAULT now()
);

-- ── 18. ged_index ────────────────────────────────────────────
-- Index d'archive GED — immuable une fois archivé (GEDAgent)
-- CASCADE : index supprimé si le document ou le dossier l'est
CREATE TABLE IF NOT EXISTS ged_index (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    dossier_id     UUID NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
    chemin_archive TEXT NOT NULL UNIQUE,
    nom_fichier    TEXT NOT NULL,
    categorie      TEXT NOT NULL CHECK (categorie IN (
        'fournisseurs', 'clients', 'banques', 'fiscal_social', 'autres'
    )),
    annee          INT NOT NULL,
    mois           INT NOT NULL,
    num_sequence   INT NOT NULL,    -- séquentiel par dossier+année+mois
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- ── 19. embeddings (pgvector) ────────────────────────────────
-- SET NULL sur les 2 FK : le vecteur survit à la suppression de sa source
CREATE TABLE IF NOT EXISTS embeddings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ecriture_id UUID REFERENCES ecritures(id) ON DELETE SET NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    contenu     TEXT NOT NULL,
    embedding   vector(1536) NOT NULL,
    modele      TEXT DEFAULT 'text-embedding-3-small',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 20. INDEX ────────────────────────────────────────────────

-- Vue "En attente" Lovable (filtre rapide dossier + statut)
CREATE INDEX IF NOT EXISTS idx_documents_dossier_statut
    ON documents(dossier_id, statut);
CREATE INDEX IF NOT EXISTS idx_documents_statut
    ON documents(statut);
CREATE INDEX IF NOT EXISTS idx_documents_score_ocr
    ON documents(score_ocr) WHERE score_ocr IS NOT NULL;

-- Écritures
CREATE INDEX IF NOT EXISTS idx_ecritures_dossier_statut
    ON ecritures(dossier_id, statut);
CREATE INDEX IF NOT EXISTS idx_ecritures_est_lettree
    ON ecritures(est_lettree) WHERE est_lettree = FALSE;
CREATE INDEX IF NOT EXISTS idx_ecritures_compte_debit
    ON ecritures(compte_debit);
CREATE INDEX IF NOT EXISTS idx_ecritures_tiers
    ON ecritures(tiers) WHERE tiers IS NOT NULL;

-- Miroir Sage
CREATE INDEX IF NOT EXISTS idx_ecritures_sage_dossier
    ON ecritures_sage(dossier_id);

-- Révision
CREATE INDEX IF NOT EXISTS idx_revision_corrigee
    ON revision(corrigee) WHERE corrigee = FALSE;
CREATE INDEX IF NOT EXISTS idx_revision_dossier
    ON revision(dossier_id);

-- GED
CREATE INDEX IF NOT EXISTS idx_ged_dossier_annee_mois
    ON ged_index(dossier_id, annee, mois);

-- Lettrage fuzzy (pg_trgm — LettrageAgent .like())
CREATE INDEX IF NOT EXISTS idx_apprentissage_trgm
    ON apprentissage USING gin(libelle_bancaire gin_trgm_ops);

-- pgvector IVFFlat (PresaisieAgent RPC match_historique_fec)
-- Note : index actif dès la première ligne insérée
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
    ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ── 21. RLS ──────────────────────────────────────────────────
-- Beta : tous les utilisateurs authentifiés voient tout
-- À resserrer en production (RLS par dossier/responsable_id)
ALTER TABLE utilisateurs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE dossiers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE journaux          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecritures         ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecritures_sage    ENABLE ROW LEVEL SECURITY;
ALTER TABLE syncs_sage        ENABLE ROW LEVEL SECURITY;
ALTER TABLE declarations_tva  ENABLE ROW LEVEL SECURITY;
ALTER TABLE acomptes_is       ENABLE ROW LEVEL SECURITY;
ALTER TABLE provisions_fnp    ENABLE ROW LEVEL SECURITY;
ALTER TABLE apprentissage     ENABLE ROW LEVEL SECURITY;
ALTER TABLE doublons_detectes ENABLE ROW LEVEL SECURITY;
ALTER TABLE revision          ENABLE ROW LEVEL SECURITY;
ALTER TABLE lettrages         ENABLE ROW LEVEL SECURITY;
ALTER TABLE ged_index         ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings        ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    t      TEXT;
    tables TEXT[] := ARRAY[
        'utilisateurs', 'contacts', 'dossiers', 'documents', 'journaux',
        'ecritures', 'ecritures_sage', 'syncs_sage', 'declarations_tva',
        'acomptes_is', 'provisions_fnp', 'apprentissage', 'doublons_detectes',
        'revision', 'lettrages', 'ged_index', 'embeddings'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format(
            'CREATE POLICY "beta_auth_all_%1$s" ON %1$s
             FOR ALL TO authenticated USING (true) WITH CHECK (true)', t
        );
    END LOOP;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── 22. RPC PGVECTOR ─────────────────────────────────────────
-- Utilisée par PresaisieAgent pour récupérer le contexte historique FEC
CREATE OR REPLACE FUNCTION match_historique_fec(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.75,
    match_count     INT   DEFAULT 5
)
RETURNS TABLE(id UUID, ecriture_id UUID, contenu TEXT, similarity FLOAT)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT e.id, e.ecriture_id, e.contenu,
           (1 - (e.embedding <=> query_embedding))::FLOAT AS similarity
    FROM embeddings e
    WHERE (1 - (e.embedding <=> query_embedding)) > match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ── 23. DO BLOCK VÉRIFICATION ────────────────────────────────
-- Si une vérification échoue → RAISE EXCEPTION → ROLLBACK automatique
DO $$
DECLARE
    table_names TEXT[] := ARRAY[
        'utilisateurs', 'contacts', 'dossiers', 'documents', 'journaux',
        'ecritures', 'ecritures_sage', 'syncs_sage', 'declarations_tva',
        'acomptes_is', 'provisions_fnp', 'apprentissage', 'doublons_detectes',
        'revision', 'lettrages', 'ged_index', 'embeddings'
    ];
    tbl TEXT;
BEGIN
    -- Vérif 1 : les 17 tables existent
    FOREACH tbl IN ARRAY table_names LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) THEN
            RAISE EXCEPTION 'TABLE MANQUANTE : %', tbl;
        END IF;
    END LOOP;

    -- Vérif 2 : pgvector activé
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Extension vector (pgvector) non activée';
    END IF;

    -- Vérif 3 : enum statut_document existe
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'statut_document') THEN
        RAISE EXCEPTION 'Type ENUM statut_document non créé';
    END IF;

    -- Vérif 4 : index critique documents existe
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = 'idx_documents_dossier_statut'
    ) THEN
        RAISE EXCEPTION 'Index idx_documents_dossier_statut manquant';
    END IF;

    -- Vérif 5 : colonne score_ocr dans documents
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'score_ocr'
    ) THEN
        RAISE EXCEPTION 'Colonne score_ocr manquante dans documents';
    END IF;

    -- Vérif 6 : colonne embedding dans embeddings
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'embeddings'
          AND column_name = 'embedding'
    ) THEN
        RAISE EXCEPTION 'Colonne embedding manquante dans embeddings';
    END IF;

    RAISE NOTICE '✅ MIGRATION v2.2 VALIDÉE — 17 tables + pgvector + enum + indexes OK';
END $$;

COMMIT;

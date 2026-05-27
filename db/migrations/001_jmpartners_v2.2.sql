-- =============================================================================
-- JM Partners v2.2 — Migration principale
-- Exécuter dans Supabase SQL Editor dans l'ordre indiqué.
-- RLS désactivé : service key utilisée côté agents.
-- =============================================================================

-- Extension pgvector (doit être activée avant la table embeddings)
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================================
-- TABLES CONTACTS / DOSSIERS
-- =============================================================================

CREATE TABLE IF NOT EXISTS contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom         TEXT NOT NULL,
    email       TEXT,
    telephone   TEXT,
    cabinet_id  TEXT NOT NULL DEFAULT 'jmpartners',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_cabinet ON contacts (cabinet_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email   ON contacts (email);


CREATE TABLE IF NOT EXISTS dossiers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id    UUID REFERENCES contacts (id) ON DELETE SET NULL,
    cabinet_id    TEXT NOT NULL DEFAULT 'jmpartners',
    nom           TEXT NOT NULL,
    type_dossier  TEXT NOT NULL DEFAULT 'comptabilite',
    statut        TEXT NOT NULL DEFAULT 'actif',   -- actif | archivé | clôturé
    date_cloture  DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dossiers_contact ON dossiers (contact_id);
CREATE INDEX IF NOT EXISTS idx_dossiers_statut  ON dossiers (statut);
CREATE INDEX IF NOT EXISTS idx_dossiers_cabinet ON dossiers (cabinet_id);


-- =============================================================================
-- TABLES CHAÎNE DOCUMENTAIRE
-- =============================================================================

CREATE TABLE IF NOT EXISTS documents (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom_fichier          TEXT NOT NULL,
    source               TEXT NOT NULL DEFAULT 'manuel',  -- outlook | regate | pennylane | manuel
    message_id           TEXT UNIQUE,                     -- déduplication
    expediteur           TEXT,
    dossier_id           UUID REFERENCES dossiers (id) ON DELETE SET NULL,
    dossier_id_hint      UUID,
    contenu_extrait      JSONB,
    type_piece           TEXT,    -- fournisseur | client | banque | fiscal | social | autre
    sous_type            TEXT,    -- facture | avoir | releve | declaration
    score_confiance      FLOAT,
    score_detection      FLOAT,
    statut               TEXT NOT NULL DEFAULT 'en_attente_ocr',
    -- en_attente_ocr | a_trier | qualifie | a_valider | valide | archive | en_attente_collaborateur
    raison_attente       TEXT,
    multi_dossiers       BOOLEAN NOT NULL DEFAULT FALSE,
    chemin_storage       TEXT,
    numero_sequentiel    INT,
    badge_anomalie       BOOLEAN NOT NULL DEFAULT FALSE,
    anomalie_description TEXT,
    date_reception       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_statut     ON documents (statut);
CREATE INDEX IF NOT EXISTS idx_documents_dossier    ON documents (dossier_id);
CREATE INDEX IF NOT EXISTS idx_documents_message_id ON documents (message_id);
CREATE INDEX IF NOT EXISTS idx_documents_source     ON documents (source);


CREATE TABLE IF NOT EXISTS journaux (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent       TEXT,
    action      TEXT NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'ok',
    document_id UUID REFERENCES documents (id) ON DELETE SET NULL,
    contact_id  UUID REFERENCES contacts  (id) ON DELETE SET NULL,
    dossier_id  UUID REFERENCES dossiers  (id) ON DELETE SET NULL,
    type_action TEXT,
    contenu     TEXT,
    details     JSONB,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journaux_agent      ON journaux (agent);
CREATE INDEX IF NOT EXISTS idx_journaux_statut     ON journaux (statut);
CREATE INDEX IF NOT EXISTS idx_journaux_created_at ON journaux (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journaux_dossier    ON journaux (dossier_id);


-- =============================================================================
-- TABLES COMPTABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS ecritures (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id          UUID REFERENCES documents (id) ON DELETE SET NULL,
    dossier_id           UUID REFERENCES dossiers  (id) ON DELETE SET NULL,
    journal              TEXT NOT NULL,           -- ACH | VTE | BQ | OD
    compte_debit         TEXT NOT NULL,
    compte_credit        TEXT NOT NULL,
    tiers                TEXT,
    libelle              TEXT,
    montant_ht           FLOAT,
    montant_tva          FLOAT,
    montant_ttc          FLOAT,
    taux_tva             FLOAT,
    source_validation    TEXT DEFAULT 'a_verifier',
    -- fec_reconnu | apprentissage | regle_comptable | a_verifier
    confiance            FLOAT,
    statut               TEXT NOT NULL DEFAULT 'a_valider',
    -- a_valider | a_valider_fnp | a_saisir_sage | valide | archive
    est_lettree          BOOLEAN NOT NULL DEFAULT FALSE,
    lettre               TEXT,
    badge_anomalie       BOOLEAN NOT NULL DEFAULT FALSE,
    anomalie_description TEXT,
    source               TEXT DEFAULT 'agent',    -- agent | collaborateur | regate | sage
    compte               TEXT,                    -- pour ecritures venues de Sage/FEC
    date_ecriture        DATE,
    raison_attente       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecritures_statut     ON ecritures (statut);
CREATE INDEX IF NOT EXISTS idx_ecritures_dossier    ON ecritures (dossier_id);
CREATE INDEX IF NOT EXISTS idx_ecritures_document   ON ecritures (document_id);
CREATE INDEX IF NOT EXISTS idx_ecritures_est_lettree ON ecritures (est_lettree);
CREATE INDEX IF NOT EXISTS idx_ecritures_badge      ON ecritures (badge_anomalie) WHERE badge_anomalie = TRUE;


CREATE TABLE IF NOT EXISTS ecritures_sage (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id     UUID REFERENCES dossiers (id) ON DELETE SET NULL,
    journal        TEXT NOT NULL,
    compte         TEXT NOT NULL,
    tiers          TEXT,
    libelle        TEXT,
    debit          FLOAT NOT NULL DEFAULT 0,
    credit         FLOAT NOT NULL DEFAULT 0,
    date_ecriture  DATE NOT NULL,
    source         TEXT NOT NULL DEFAULT 'collaborateur',
    -- agent | collaborateur | paie | od_manuel
    piece_ref      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecritures_sage_dossier      ON ecritures_sage (dossier_id);
CREATE INDEX IF NOT EXISTS idx_ecritures_sage_date         ON ecritures_sage (date_ecriture DESC);
CREATE INDEX IF NOT EXISTS idx_ecritures_sage_compte       ON ecritures_sage (compte);
CREATE INDEX IF NOT EXISTS idx_ecritures_sage_tiers_date   ON ecritures_sage (tiers, date_ecriture);


CREATE TABLE IF NOT EXISTS syncs_sage (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date_sync     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nb_lignes     INT NOT NULL DEFAULT 0,
    hash_fichier  TEXT NOT NULL UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_syncs_sage_hash ON syncs_sage (hash_fichier);


-- =============================================================================
-- TABLES LETTRAGE
-- =============================================================================

CREATE TABLE IF NOT EXISTS lettrages (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ecriture_id        UUID REFERENCES ecritures (id) ON DELETE CASCADE,
    reglement_id       UUID REFERENCES ecritures (id) ON DELETE CASCADE,
    montant            FLOAT NOT NULL,
    tiers              TEXT,
    methode            TEXT NOT NULL DEFAULT 'exact',  -- exact | approche | apprentissage
    confiance          FLOAT NOT NULL DEFAULT 1.0,
    date_rapprochement TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lettrages_ecriture  ON lettrages (ecriture_id);
CREATE INDEX IF NOT EXISTS idx_lettrages_reglement ON lettrages (reglement_id);


-- =============================================================================
-- TABLES FISCAL
-- =============================================================================

CREATE TABLE IF NOT EXISTS declarations_tva (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id      UUID REFERENCES dossiers  (id) ON DELETE SET NULL,
    contact_id      UUID REFERENCES contacts  (id) ON DELETE SET NULL,
    periode         TEXT NOT NULL,   -- ex: "mai-2026"
    deadline        DATE,
    tva_collectee   FLOAT,
    tva_deductible  FLOAT,
    solde           FLOAT,
    statut          TEXT NOT NULL DEFAULT 'a_preparer',
    -- a_preparer | pieces_manquantes | pret | valide
    alerte_envoyee_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_declarations_tva_dossier ON declarations_tva (dossier_id);
CREATE INDEX IF NOT EXISTS idx_declarations_tva_statut  ON declarations_tva (statut);
CREATE INDEX IF NOT EXISTS idx_declarations_tva_deadline ON declarations_tva (deadline);


CREATE TABLE IF NOT EXISTS acomptes_is (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id      UUID REFERENCES dossiers (id) ON DELETE SET NULL,
    exercice        INT  NOT NULL,
    tranche         INT  NOT NULL,   -- 1 | 2 | 3 | 4
    montant         FLOAT,
    date_echeance   DATE NOT NULL,
    statut          TEXT NOT NULL DEFAULT 'a_payer',
    alerte_envoyee  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_acomptes_is_dossier  ON acomptes_is (dossier_id);
CREATE INDEX IF NOT EXISTS idx_acomptes_is_echeance ON acomptes_is (date_echeance);


CREATE TABLE IF NOT EXISTS provisions_fnp (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id        UUID REFERENCES dossiers (id) ON DELETE SET NULL,
    fournisseur       TEXT NOT NULL,
    montant_estime    FLOAT NOT NULL DEFAULT 0,
    compte_charge     TEXT NOT NULL,    -- 6xxxxx
    compte_provision  TEXT NOT NULL,    -- 408xxx (FNP) ou 418xxx (FAE)
    description       TEXT,
    statut            TEXT NOT NULL DEFAULT 'a_valider_fnp',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provisions_fnp_dossier ON provisions_fnp (dossier_id);
CREATE INDEX IF NOT EXISTS idx_provisions_fnp_statut  ON provisions_fnp (statut);


-- =============================================================================
-- TABLES RÉVISION
-- =============================================================================

CREATE TABLE IF NOT EXISTS revision (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id    UUID REFERENCES dossiers  (id) ON DELETE SET NULL,
    ecriture_id   UUID REFERENCES ecritures (id) ON DELETE SET NULL,
    type_anomalie TEXT NOT NULL,
    -- compte_incorrect | doublon | lettrage_impossible | tiers_imprecis
    description   TEXT NOT NULL,
    suggestion    TEXT,
    severite      TEXT NOT NULL DEFAULT 'validation_requise',
    -- auto_corrigeable | validation_requise
    corrigee      BOOLEAN NOT NULL DEFAULT FALSE,
    statut        TEXT NOT NULL DEFAULT 'en_attente',
    -- en_attente | valide | rejete
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_revision_dossier  ON revision (dossier_id);
CREATE INDEX IF NOT EXISTS idx_revision_statut   ON revision (statut);
CREATE INDEX IF NOT EXISTS idx_revision_ecriture ON revision (ecriture_id);


CREATE TABLE IF NOT EXISTS doublons_detectes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id_1 UUID REFERENCES documents (id) ON DELETE CASCADE,
    document_id_2 UUID REFERENCES documents (id) ON DELETE CASCADE,
    raison        TEXT,
    statut        TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | confirme | rejete
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doublons_doc1 ON doublons_detectes (document_id_1);
CREATE INDEX IF NOT EXISTS idx_doublons_doc2 ON doublons_detectes (document_id_2);


-- =============================================================================
-- TABLES APPRENTISSAGE
-- =============================================================================

CREATE TABLE IF NOT EXISTS apprentissage (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id       UUID REFERENCES dossiers (id) ON DELETE SET NULL,
    type_pattern     TEXT NOT NULL DEFAULT 'libelle_bancaire',
    cle              TEXT NOT NULL,    -- libellé bancaire
    valeur           JSONB NOT NULL,   -- {"tiers": "...", "facture_id": "...", "montant": ...}
    libelle          TEXT,             -- colonne de recherche rapide (mirror de cle)
    tiers            TEXT,             -- mirror pour _appliquer_apprentissage
    facture_id       UUID REFERENCES ecritures (id) ON DELETE SET NULL,
    montant          FLOAT,
    nb_utilisations  INT NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_apprentissage_cle     ON apprentissage (cle);
CREATE INDEX IF NOT EXISTS idx_apprentissage_libelle ON apprentissage (libelle);
CREATE INDEX IF NOT EXISTS idx_apprentissage_dossier ON apprentissage (dossier_id);


-- =============================================================================
-- TABLE GED
-- =============================================================================

CREATE TABLE IF NOT EXISTS ged_index (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id        UUID REFERENCES documents (id) ON DELETE CASCADE,
    dossier_id         UUID REFERENCES dossiers  (id) ON DELETE SET NULL,
    chemin_archive     TEXT NOT NULL,
    numero_sequentiel  INT NOT NULL DEFAULT 1,
    annee              INT NOT NULL,
    mois               INT NOT NULL,
    type_piece         TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ged_index_dossier    ON ged_index (dossier_id);
CREATE INDEX IF NOT EXISTS idx_ged_index_annee_mois ON ged_index (dossier_id, annee, mois);


-- =============================================================================
-- TABLE COLLABORATEURS (rapport matinal MiroirSageAgent)
-- =============================================================================

CREATE TABLE IF NOT EXISTS collaborateurs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom        TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    cabinet_id TEXT NOT NULL DEFAULT 'jmpartners',
    actif      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collaborateurs_cabinet ON collaborateurs (cabinet_id);


-- =============================================================================
-- TABLE EMBEDDINGS (pgvector — pré-saisie historique FEC)
-- =============================================================================

CREATE TABLE IF NOT EXISTS embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    UUID REFERENCES documents  (id) ON DELETE CASCADE,
    dossier_id     UUID REFERENCES dossiers   (id) ON DELETE SET NULL,
    vecteur        vector(1536),
    type_embedding TEXT NOT NULL DEFAULT 'contenu_extrait',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_dossier ON embeddings (dossier_id);
-- Index HNSW pour recherche de similarité
CREATE INDEX IF NOT EXISTS idx_embeddings_vecteur
    ON embeddings USING hnsw (vecteur vector_cosine_ops);


-- =============================================================================
-- FONCTION RPC — match_historique_fec (appelée par PresaisieAgent)
-- =============================================================================

CREATE OR REPLACE FUNCTION match_historique_fec(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.75,
    match_count     INT   DEFAULT 5
)
RETURNS TABLE (
    id          UUID,
    document_id UUID,
    dossier_id  UUID,
    similarity  FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        e.id,
        e.document_id,
        e.dossier_id,
        1 - (e.vecteur <=> query_embedding) AS similarity
    FROM embeddings e
    WHERE 1 - (e.vecteur <=> query_embedding) > match_threshold
    ORDER BY e.vecteur <=> query_embedding
    LIMIT match_count;
$$;


-- =============================================================================
-- TRIGGER updated_at automatique
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['documents', 'ecritures', 'apprentissage']
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS set_updated_at ON %I;
            CREATE TRIGGER set_updated_at
                BEFORE UPDATE ON %I
                FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
        ', t, t);
    END LOOP;
END;
$$;

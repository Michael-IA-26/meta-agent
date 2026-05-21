-- JM Partners — Schéma Supabase
-- Section 5 du cahier des charges — 8 tables métier
-- 14 mai 2026

-- ===========================================================================
-- 1. UTILISATEURS
-- Collaborateurs du cabinet (gestionnaires, managers, admins)
-- ===========================================================================
CREATE TABLE utilisateurs (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at   TIMESTAMPTZ NOT NULL    DEFAULT now(),
    email        TEXT        NOT NULL    UNIQUE,
    prenom       TEXT        NOT NULL,
    nom          TEXT        NOT NULL,
    role         TEXT        NOT NULL    DEFAULT 'gestionnaire'
                             CHECK (role IN ('gestionnaire', 'manager', 'admin')),
    actif        BOOLEAN     NOT NULL    DEFAULT true
);

-- ===========================================================================
-- 2. DOSSIERS
-- Dossier client = une entreprise suivie par le cabinet
-- ===========================================================================
CREATE TABLE dossiers (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          TIMESTAMPTZ NOT NULL    DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL    DEFAULT now(),
    numero_dossier      TEXT        NOT NULL    UNIQUE,            -- ex. "JMP-2026-001"
    raison_sociale      TEXT        NOT NULL,
    siren               TEXT,
    siret               TEXT,
    forme_juridique     TEXT        CHECK (forme_juridique IN (
                            'SARL', 'SAS', 'SASU', 'EURL', 'SA', 'SNC',
                            'EI', 'EIRL', 'SCI', 'SELARL', 'autre'
                        )),
    code_naf            TEXT,
    adresse             TEXT,
    code_postal         TEXT,
    ville               TEXT,
    date_exercice_debut DATE,
    date_exercice_fin   DATE,
    regime_tva          TEXT        DEFAULT 'mensuel'
                             CHECK (regime_tva IN ('mensuel', 'trimestriel', 'franchise', 'reel_simplifie')),
    statut              TEXT        NOT NULL    DEFAULT 'actif'
                             CHECK (statut IN ('actif', 'suspendu', 'cloture')),
    etape_courante      INT         NOT NULL    DEFAULT 1
                             CHECK (etape_courante BETWEEN 1 AND 6),
    gestionnaire_id     UUID        REFERENCES utilisateurs(id)
);

-- Trigger updated_at sur dossiers
CREATE OR REPLACE FUNCTION jmp_update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dossiers_updated_at
    BEFORE UPDATE ON dossiers
    FOR EACH ROW EXECUTE FUNCTION jmp_update_updated_at();

-- ===========================================================================
-- 3. CONTACTS
-- Interlocuteurs rattachés à un dossier (dirigeants, DG, comptables…)
-- ===========================================================================
CREATE TABLE contacts (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL    DEFAULT now(),
    dossier_id  UUID        NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    prenom      TEXT,
    nom         TEXT        NOT NULL,
    email       TEXT,
    telephone   TEXT,
    role        TEXT        DEFAULT 'dirigeant'
                     CHECK (role IN ('dirigeant', 'daf', 'comptable', 'associe', 'autre')),
    actif       BOOLEAN     NOT NULL    DEFAULT true
);

-- ===========================================================================
-- 4. JOURNAUX
-- Journaux comptables du dossier (Ventes, Achats, Banque, OD…)
-- ===========================================================================
CREATE TABLE journaux (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL    DEFAULT now(),
    dossier_id  UUID        NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    code        TEXT        NOT NULL,                              -- ex. "VT", "AC", "BQ"
    libelle     TEXT        NOT NULL,                              -- ex. "Ventes", "Banque"
    type        TEXT        NOT NULL
                     CHECK (type IN ('ventes', 'achats', 'banque', 'operations_diverses', 'a_nouveaux')),
    actif       BOOLEAN     NOT NULL    DEFAULT true,
    UNIQUE (dossier_id, code)
);

-- ===========================================================================
-- 5. ECRITURES
-- Lignes comptables saisies ou générées par l'IA
-- ===========================================================================
CREATE TABLE ecritures (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ    NOT NULL    DEFAULT now(),
    dossier_id      UUID           NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    journal_id      UUID           NOT NULL    REFERENCES journaux(id),
    date_ecriture   DATE           NOT NULL,
    numero_piece    TEXT,                                          -- référence pièce justificative
    libelle         TEXT           NOT NULL,
    compte_debit    TEXT           NOT NULL,                       -- numéro de compte PCG
    compte_credit   TEXT           NOT NULL,
    montant         NUMERIC(15, 2) NOT NULL CHECK (montant > 0),
    lettrage        TEXT,                                          -- code de lettrage (ex. "AA01")
    valide          BOOLEAN        NOT NULL    DEFAULT false,
    source          TEXT           NOT NULL    DEFAULT 'manuel'
                         CHECK (source IN ('import', 'manuel', 'ia')),
    document_id     UUID                                           -- FK vers documents (nullable)
);

-- ===========================================================================
-- 6. DOCUMENTS
-- Pièces justificatives (factures, relevés, etc.) stockées dans Supabase Storage
-- ===========================================================================
CREATE TABLE documents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL    DEFAULT now(),
    dossier_id      UUID        NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    nom_fichier     TEXT        NOT NULL,
    type_document   TEXT        NOT NULL
                         CHECK (type_document IN (
                             'facture_vente', 'facture_achat',
                             'releve_bancaire', 'note_frais',
                             'contrat', 'autre'
                         )),
    storage_path    TEXT        NOT NULL,                          -- chemin Supabase Storage
    hash_sha256     TEXT,                                          -- déduplication
    statut          TEXT        NOT NULL    DEFAULT 'recu'
                         CHECK (statut IN ('recu', 'analyse', 'integre', 'rejete')),
    analyse_ia      JSONB       NOT NULL    DEFAULT '{}',          -- résultat extraction IA
    uploaded_at     TIMESTAMPTZ NOT NULL    DEFAULT now()
);

-- FK différée sur ecritures.document_id (le document peut être créé après)
ALTER TABLE ecritures
    ADD CONSTRAINT ecritures_document_fk
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;

-- ===========================================================================
-- 7. DECLARATIONS_TVA
-- Déclarations de TVA par période (mensuelle ou trimestrielle)
-- ===========================================================================
CREATE TABLE declarations_tva (
    id                      UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ    NOT NULL    DEFAULT now(),
    dossier_id              UUID           NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    periode                 TEXT           NOT NULL,               -- ex. "2026-03" ou "2026-T1"
    periodicite             TEXT           NOT NULL
                                 CHECK (periodicite IN ('mensuelle', 'trimestrielle')),
    date_limite             DATE           NOT NULL,
    date_depot              TIMESTAMPTZ,
    montant_tva_collectee   NUMERIC(15, 2) NOT NULL    DEFAULT 0,
    montant_tva_deductible  NUMERIC(15, 2) NOT NULL    DEFAULT 0,
    montant_net             NUMERIC(15, 2) GENERATED ALWAYS AS
                                (montant_tva_collectee - montant_tva_deductible) STORED,
    statut                  TEXT           NOT NULL    DEFAULT 'a_preparer'
                                 CHECK (statut IN (
                                     'a_preparer', 'en_cours', 'valide',
                                     'deposee', 'rejete'
                                 )),
    fichier_liasse_path     TEXT,
    reference_depot         TEXT,
    UNIQUE (dossier_id, periode)
);

-- ===========================================================================
-- 8. ACOMPTES_IS
-- Acomptes d'impôt sur les sociétés (4 par exercice)
-- ===========================================================================
CREATE TABLE acomptes_is (
    id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          TIMESTAMPTZ    NOT NULL    DEFAULT now(),
    dossier_id          UUID           NOT NULL    REFERENCES dossiers(id) ON DELETE CASCADE,
    exercice            INT            NOT NULL,                   -- ex. 2026
    numero_acompte      INT            NOT NULL    CHECK (numero_acompte BETWEEN 1 AND 4),
    date_echeance       DATE           NOT NULL,
    montant_prevu       NUMERIC(15, 2),
    montant_verse       NUMERIC(15, 2),
    date_versement      TIMESTAMPTZ,
    statut              TEXT           NOT NULL    DEFAULT 'planifie'
                             CHECK (statut IN (
                                 'planifie', 'rappele', 'verse', 'en_retard', 'dispense'
                             )),
    reference_paiement  TEXT,
    UNIQUE (dossier_id, exercice, numero_acompte)
);

-- ===========================================================================
-- INDEX CRITIQUES
-- ===========================================================================

-- dossiers
CREATE INDEX idx_dossiers_statut        ON dossiers(statut);
CREATE INDEX idx_dossiers_gestionnaire  ON dossiers(gestionnaire_id);
CREATE INDEX idx_dossiers_siren         ON dossiers(siren) WHERE siren IS NOT NULL;

-- contacts
CREATE INDEX idx_contacts_dossier       ON contacts(dossier_id);
CREATE INDEX idx_contacts_email         ON contacts(email)      WHERE email IS NOT NULL;

-- journaux
CREATE INDEX idx_journaux_dossier       ON journaux(dossier_id);

-- ecritures
CREATE INDEX idx_ecritures_dossier      ON ecritures(dossier_id);
CREATE INDEX idx_ecritures_date         ON ecritures(date_ecriture);
CREATE INDEX idx_ecritures_journal      ON ecritures(journal_id);
CREATE INDEX idx_ecritures_non_valide   ON ecritures(dossier_id) WHERE valide = false;

-- documents
CREATE INDEX idx_documents_dossier      ON documents(dossier_id);
CREATE INDEX idx_documents_statut       ON documents(statut);
CREATE INDEX idx_documents_hash         ON documents(hash_sha256) WHERE hash_sha256 IS NOT NULL;

-- declarations_tva
CREATE INDEX idx_tva_dossier            ON declarations_tva(dossier_id);
CREATE INDEX idx_tva_date_limite        ON declarations_tva(date_limite);
CREATE INDEX idx_tva_statut             ON declarations_tva(statut);

-- acomptes_is
CREATE INDEX idx_is_dossier             ON acomptes_is(dossier_id);
CREATE INDEX idx_is_date_echeance       ON acomptes_is(date_echeance);
CREATE INDEX idx_is_statut              ON acomptes_is(statut);

-- ===========================================================================
-- ROW LEVEL SECURITY
-- ===========================================================================

ALTER TABLE utilisateurs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE dossiers            ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE journaux            ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecritures           ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE declarations_tva    ENABLE ROW LEVEL SECURITY;
ALTER TABLE acomptes_is         ENABLE ROW LEVEL SECURITY;

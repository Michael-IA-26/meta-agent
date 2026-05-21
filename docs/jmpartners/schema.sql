-- JM Partners — Schéma Supabase
-- Sprint 1 — Mai 2026

-- 1. Utilisateurs (comptables du cabinet)
CREATE TABLE utilisateurs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'comptable', 'assistant')),
    telegram_chat_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Contacts (clients du cabinet)
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom TEXT NOT NULL,
    email TEXT,
    telephone TEXT,
    siren TEXT UNIQUE,
    forme_juridique TEXT,
    responsable_id UUID REFERENCES utilisateurs(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Dossiers comptables
CREATE TABLE dossiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    type TEXT NOT NULL CHECK (type IN ('bilan', 'tva', 'is', 'paie', 'creation')),
    exercice TEXT NOT NULL,
    statut TEXT DEFAULT 'en_cours' CHECK (statut IN ('en_cours', 'complet', 'valide', 'archive')),
    responsable_id UUID REFERENCES utilisateurs(id),
    deadline DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Documents
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id UUID NOT NULL REFERENCES dossiers(id),
    nom TEXT NOT NULL,
    type_document TEXT NOT NULL,
    statut TEXT DEFAULT 'manquant' CHECK (statut IN ('manquant', 'recu', 'valide', 'rejete')),
    deadline DATE,
    urgence TEXT CHECK (urgence IN ('J-15', 'J-7', 'J-3', 'J-0')),
    url_storage TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Journaux d'actions
CREATE TABLE journaux (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES contacts(id),
    dossier_id UUID REFERENCES dossiers(id),
    utilisateur_id UUID REFERENCES utilisateurs(id),
    type_action TEXT NOT NULL CHECK (type_action IN (
        'email_recu', 'email_envoye', 'relance_envoyee', 'relance_skipped',
        'verification_documents', 'alerte_tva', 'alerte_echeance',
        'document_recu', 'dossier_valide', 'note_manuelle'
    )),
    contenu TEXT,
    statut TEXT DEFAULT 'ok' CHECK (statut IN ('ok', 'erreur', 'skipped')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Déclarations TVA
CREATE TABLE declarations_tva (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id UUID NOT NULL REFERENCES dossiers(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    periode TEXT NOT NULL,
    deadline DATE NOT NULL,
    montant_ca NUMERIC(12, 2),
    montant_tva NUMERIC(12, 2),
    statut TEXT DEFAULT 'a_preparer' CHECK (statut IN (
        'a_preparer', 'pieces_manquantes', 'pret', 'soumis', 'valide'
    )),
    alerte_envoyee_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Acomptes IS
CREATE TABLE acomptes_is (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id UUID NOT NULL REFERENCES dossiers(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    numero_acompte INT NOT NULL CHECK (numero_acompte IN (1, 2, 3, 4)),
    exercice TEXT NOT NULL,
    deadline DATE NOT NULL,
    montant NUMERIC(12, 2),
    statut TEXT DEFAULT 'a_payer' CHECK (statut IN ('a_payer', 'paye', 'exonere')),
    alerte_envoyee_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 8. Écritures comptables
CREATE TABLE ecritures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dossier_id UUID NOT NULL REFERENCES dossiers(id),
    date_ecriture DATE NOT NULL,
    libelle TEXT NOT NULL,
    compte_debit TEXT NOT NULL,
    compte_credit TEXT NOT NULL,
    montant NUMERIC(12, 2) NOT NULL,
    piece_justificative_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index critiques
CREATE INDEX idx_contacts_email ON contacts(email);
CREATE INDEX idx_dossiers_contact ON dossiers(contact_id);
CREATE INDEX idx_dossiers_statut ON dossiers(statut);
CREATE INDEX idx_documents_dossier ON documents(dossier_id);
CREATE INDEX idx_documents_statut ON documents(statut);
CREATE INDEX idx_journaux_contact ON journaux(contact_id);
CREATE INDEX idx_journaux_dossier ON journaux(dossier_id);
CREATE INDEX idx_journaux_type ON journaux(type_action);
CREATE INDEX idx_journaux_created ON journaux(created_at DESC);
CREATE INDEX idx_declarations_tva_deadline ON declarations_tva(deadline);
CREATE INDEX idx_declarations_tva_statut ON declarations_tva(statut);
CREATE INDEX idx_acomptes_deadline ON acomptes_is(deadline);
CREATE INDEX idx_acomptes_statut ON acomptes_is(statut);

-- RLS
ALTER TABLE utilisateurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dossiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE journaux ENABLE ROW LEVEL SECURITY;
ALTER TABLE declarations_tva ENABLE ROW LEVEL SECURITY;
ALTER TABLE acomptes_is ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecritures ENABLE ROW LEVEL SECURITY;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER dossiers_updated_at BEFORE UPDATE ON dossiers FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER declarations_tva_updated_at BEFORE UPDATE ON declarations_tva FOR EACH ROW EXECUTE FUNCTION update_updated_at();

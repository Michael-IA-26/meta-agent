-- LeadCommercial — Schéma Supabase
-- Sprint 2 — 5 mai 2026

-- 1. Cabinets
CREATE TABLE cabinets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    zone_geo TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. ICPs
CREATE TABLE icps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabinet_id UUID NOT NULL REFERENCES cabinets(id),
    secteurs TEXT[] DEFAULT '{}',
    zone_deps TEXT[] DEFAULT '{}',
    forme_juridique TEXT[] DEFAULT '{}',
    taille_sal_min INT DEFAULT 1,
    taille_sal_max INT DEFAULT 20,
    ca_min BIGINT DEFAULT 50000,
    ca_max BIGINT DEFAULT 10000000,
    signaux_prioritaires TEXT[] DEFAULT '{}',
    signaux_exclus TEXT[] DEFAULT '{}',
    scoring_rules JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Lead locks (exclusivite ICP)
CREATE TABLE lead_locks (
    siren TEXT PRIMARY KEY,
    cabinet_id UUID NOT NULL REFERENCES cabinets(id),
    locked_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Leads
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabinet_id UUID NOT NULL REFERENCES cabinets(id),
    siren TEXT NOT NULL,
    denomination TEXT,
    forme_juridique TEXT,
    code_naf TEXT,
    adresse TEXT,
    dept TEXT,
    date_creation DATE,
    dirigeant_prenom TEXT,
    dirigeant_nom TEXT,
    dirigeant_email TEXT,
    dirigeant_tel TEXT,
    site_web TEXT,
    score INT CHECK (score >= 0 AND score <= 100),
    signal_type TEXT CHECK (signal_type IN ('creation','rattrapage','fiscal','intention')),
    signal_source TEXT CHECK (signal_source IN ('sirene','bodacc','reddit','forum','facebook')),
    signal_detail TEXT,
    statut TEXT DEFAULT 'nouveau' CHECK (statut IN (
        'nouveau','contacte','repondu','bant','rdv','signe','perdu','optout'
    )),
    optout_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Signaux
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    source TEXT NOT NULL,
    contenu_brut TEXT,
    signal_classifie TEXT,
    score_urgence INT CHECK (score_urgence >= 0 AND score_urgence <= 100),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Sequences email
CREATE TABLE sequences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id),
    email_index INT CHECK (email_index >= 0 AND email_index <= 3),
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    subject TEXT,
    body TEXT,
    variante TEXT CHECK (variante IN ('A','B')),
    statut TEXT DEFAULT 'scheduled' CHECK (statut IN ('scheduled','sent','opened','clicked')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Reponses
CREATE TABLE replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id),
    sequence_id UUID REFERENCES sequences(id),
    contenu TEXT,
    classification TEXT CHECK (classification IN ('interesse','neutre','negatif','desinscription')),
    bant_score INT CHECK (bant_score >= 0 AND bant_score <= 100),
    bant_detail JSONB DEFAULT '{}',
    received_at TIMESTAMPTZ DEFAULT now()
);

-- 8. Alertes
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabinet_id UUID NOT NULL REFERENCES cabinets(id),
    lead_id UUID REFERENCES leads(id),
    type TEXT CHECK (type IN ('nouveau_lead','lead_chaud','rdv_propose')),
    canal TEXT CHECK (canal IN ('telegram','email')),
    sent_at TIMESTAMPTZ DEFAULT now(),
    contenu TEXT
);

-- 9. Reports
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cabinet_id UUID NOT NULL REFERENCES cabinets(id),
    periode_debut DATE NOT NULL,
    periode_fin DATE NOT NULL,
    pdf_url TEXT,
    nb_leads INT DEFAULT 0,
    nb_contactes INT DEFAULT 0,
    nb_reponses INT DEFAULT 0,
    nb_rdv INT DEFAULT 0,
    nb_signes INT DEFAULT 0,
    generated_at TIMESTAMPTZ DEFAULT now()
);

-- Index critiques
CREATE INDEX idx_leads_cabinet ON leads(cabinet_id);
CREATE INDEX idx_leads_statut ON leads(statut);
CREATE INDEX idx_leads_score ON leads(score DESC);
CREATE INDEX idx_leads_siren ON leads(siren);
CREATE INDEX idx_signals_lead ON signals(lead_id);
CREATE INDEX idx_sequences_lead ON sequences(lead_id);
CREATE INDEX idx_sequences_scheduled ON sequences(scheduled_at) WHERE statut = 'scheduled';
CREATE INDEX idx_replies_lead ON replies(lead_id);
CREATE INDEX idx_alerts_cabinet ON alerts(cabinet_id);

-- RLS (Row Level Security)
ALTER TABLE cabinets ENABLE ROW LEVEL SECURITY;
ALTER TABLE icps ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_locks ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Trigger updated_at sur leads
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

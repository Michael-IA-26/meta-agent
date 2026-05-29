-- ============================================================
-- db/rollback/001_jmpartners_v2.2_rollback.sql
-- ROLLBACK — annule la migration 001_jmpartners_v2.2.sql
-- À utiliser UNIQUEMENT si la migration a échoué à mi-parcours
-- ⚠️  ATTENTION : supprime toutes les données insérées via le seed
-- ============================================================

BEGIN;

-- Ordre inverse des FK (bottom-up)
-- Les tables les plus dépendantes sont supprimées en premier

DROP TABLE IF EXISTS embeddings        CASCADE;
DROP TABLE IF EXISTS ged_index         CASCADE;
DROP TABLE IF EXISTS lettrages         CASCADE;
DROP TABLE IF EXISTS revision          CASCADE;
DROP TABLE IF EXISTS doublons_detectes CASCADE;
DROP TABLE IF EXISTS apprentissage     CASCADE;
DROP TABLE IF EXISTS provisions_fnp    CASCADE;
DROP TABLE IF EXISTS acomptes_is       CASCADE;
DROP TABLE IF EXISTS declarations_tva  CASCADE;
DROP TABLE IF EXISTS ecritures_sage    CASCADE;
DROP TABLE IF EXISTS syncs_sage        CASCADE;
DROP TABLE IF EXISTS journaux          CASCADE;

-- ecritures : supprimer d'abord les colonnes v2.2, puis la table
-- (si vous souhaitez conserver la table v2.1, commentez le DROP TABLE
--  et décommentez les ALTER TABLE DROP COLUMN ci-dessous)
DROP TABLE IF EXISTS ecritures CASCADE;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS montant_ht;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS montant_ttc;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS taux_tva;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS tiers;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS compte_tiers;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS statut;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS source_validation;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS est_lettree;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS lettre;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS badge_anomalie;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS anomalie_desc;
-- ALTER TABLE ecritures DROP COLUMN IF EXISTS updated_at;

DROP TABLE IF EXISTS documents CASCADE;

-- dossiers : supprimer la colonne secteur ajoutée en v2.2
-- (si vous souhaitez conserver la table, commentez DROP TABLE)
DROP TABLE IF EXISTS dossiers  CASCADE;
-- ALTER TABLE dossiers DROP COLUMN IF EXISTS secteur;

DROP TABLE IF EXISTS contacts     CASCADE;
DROP TABLE IF EXISTS utilisateurs CASCADE;

-- Supprimer le type enum
DROP TYPE IF EXISTS statut_document CASCADE;

-- Supprimer la RPC pgvector
DROP FUNCTION IF EXISTS match_historique_fec(vector(1536), FLOAT, INT);

-- Supprimer la fonction trigger (seulement si plus utilisée)
DROP FUNCTION IF EXISTS update_updated_at() CASCADE;

-- ⚠️  Extensions : ne pas supprimer en production sans confirmation manuelle
-- Les extensions vector et pg_trgm peuvent être utilisées par d'autres schemas.
-- DROP EXTENSION IF EXISTS vector CASCADE;
-- DROP EXTENSION IF EXISTS pg_trgm CASCADE;

COMMIT;

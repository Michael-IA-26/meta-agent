-- Migration 006: vues dashboard activité agents + ROI
-- Idempotente (CREATE OR REPLACE VIEW), zéro donnée modifiée.

-- 1. v_agent_runs : derniers passages de l'orchestrateur
CREATE OR REPLACE VIEW v_agent_runs WITH (security_invoker = on) AS
SELECT
    id,
    dossier_id,
    created_at,
    statut,
    (metadata->>'agents_ok')::int    AS agents_ok,
    (metadata->>'agents_ko')::int    AS agents_ko,
    (metadata->>'duree_secondes')::numeric AS duree_secondes
FROM journaux
WHERE type_action = 'orchestrator_run'
ORDER BY created_at DESC;

-- 2. v_roi_jmpartners : agrégats ROI sur le mois courant
--    temps_gagne_min = nb_docs * 8  (hypothèse : 8 min par document traité)
--    taux_auto       = écritures IA valides / total écritures IA (0–1)
--    cout_heure      = 80 €  (paramètre, modifiable ici)
CREATE OR REPLACE VIEW v_roi_jmpartners WITH (security_invoker = on) AS
WITH periode AS (
    SELECT
        date_trunc('month', now()) AS debut,
        date_trunc('month', now()) + interval '1 month' AS fin
),
docs AS (
    SELECT count(*) AS nb_docs
    FROM documents d, periode p
    WHERE d.created_at >= p.debut AND d.created_at < p.fin
),
ecritures_ia AS (
    SELECT
        count(*)                                            AS nb_ecritures,
        count(*) FILTER (WHERE statut = 'valide')          AS nb_valide_auto
    FROM ecritures e, periode p
    WHERE e.source = 'ia'
      AND e.created_at >= p.debut AND e.created_at < p.fin
),
relances AS (
    SELECT count(*) AS nb_relances
    FROM journaux j, periode p
    WHERE j.type_action = 'relance'
      AND j.created_at >= p.debut AND j.created_at < p.fin
)
SELECT
    d.nb_docs,
    ei.nb_ecritures,
    ei.nb_valide_auto                                               AS nb_ecritures_auto,
    r.nb_relances,
    (d.nb_docs * 8)                                                 AS temps_gagne_min,
    CASE WHEN ei.nb_ecritures = 0 THEN 0
         ELSE round(ei.nb_valide_auto::numeric / ei.nb_ecritures, 4)
    END                                                             AS taux_auto,
    80                                                              AS cout_heure_eur
FROM docs d, ecritures_ia ei, relances r;

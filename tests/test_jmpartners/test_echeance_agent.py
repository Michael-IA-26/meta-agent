"""Tests pour apps.jmpartners.agents.echeance_agent."""

from datetime import date, timedelta
from unittest.mock import patch

from apps.jmpartners.agents.echeance_agent import (
    Echeance,
    _priorite,
    build_rapport,
    run,
)

# ─── _priorite ────────────────────────────────────────────────────────────────


def test_priorite_rouge():
    assert _priorite(0) == "rouge"
    assert _priorite(3) == "rouge"


def test_priorite_orange():
    assert _priorite(4) == "orange"
    assert _priorite(7) == "orange"


def test_priorite_vert():
    assert _priorite(8) == "vert"
    assert _priorite(30) == "vert"


# ─── build_rapport ────────────────────────────────────────────────────────────


def _make_echeance(priorite: str, jours: int = 5) -> Echeance:
    return Echeance(
        type="tva",
        contact_id="cnt-1",
        contact_nom="SARL Test",
        dossier_id="dos-1",
        reference="TVA mai-2026",
        deadline=(date.today() + timedelta(days=jours)).isoformat(),
        jours_restants=jours,
        priorite=priorite,
        montant=None,
        statut="a_payer",
    )


def test_build_rapport_vide():
    rapport = build_rapport([])
    assert "JM Partners" in rapport


def test_build_rapport_avec_echeances():
    echeances = [
        _make_echeance("rouge", 2),
        _make_echeance("orange", 6),
        _make_echeance("vert", 15),
    ]
    rapport = build_rapport(echeances)
    assert "URGENT" in rapport
    assert "Attention" in rapport
    assert "À venir" in rapport
    assert "SARL Test" in rapport


def test_build_rapport_avec_montant():
    e = _make_echeance("rouge", 1)
    e["montant"] = 3500.0
    e["type"] = "is"
    rapport = build_rapport([e])
    assert "3" in rapport and "500" in rapport


# ─── run ──────────────────────────────────────────────────────────────────────


def test_run_aucune_echeance():
    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is") as mock_is,
        patch(
            "apps.jmpartners.agents.echeance_agent.fetch_declarations_tva"
        ) as mock_tva,
    ):
        mock_is.return_value = []
        mock_tva.return_value = []
        result = run(dry_run=True)
        assert result["echeances_total"] == 0
        assert result["rapport_envoye"] is False


def test_run_priorise_par_urgence():
    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is") as mock_is,
        patch(
            "apps.jmpartners.agents.echeance_agent.fetch_declarations_tva"
        ) as mock_tva,
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom") as mock_nom,
    ):
        today = date.today()
        mock_is.return_value = [
            {
                "id": "a1",
                "dossier_id": "d1",
                "contact_id": "c1",
                "numero_acompte": 2,
                "exercice": "2026",
                "deadline": (today + timedelta(days=2)).isoformat(),
                "montant": 1000.0,
                "statut": "a_payer",
            }
        ]
        mock_tva.return_value = [
            {
                "id": "t1",
                "dossier_id": "d2",
                "contact_id": "c2",
                "periode": "mai-2026",
                "deadline": (today + timedelta(days=15)).isoformat(),
                "statut": "a_preparer",
            }
        ]
        mock_nom.return_value = "Client"

        result = run(dry_run=True)

        assert result["echeances_total"] == 2
        assert result["rouge"] == 1
        assert result["vert"] == 1
        assert (
            result["echeances"][0]["jours_restants"]
            <= result["echeances"][1]["jours_restants"]
        )


def test_run_erreur_acompte_continue():
    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is") as mock_is,
        patch(
            "apps.jmpartners.agents.echeance_agent.fetch_declarations_tva"
        ) as mock_tva,
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom"),
    ):
        mock_is.return_value = [
            {
                "id": "a-bad",
                "deadline": "not-a-date",
                "dossier_id": "d1",
                "contact_id": "c1",
                "numero_acompte": 1,
                "exercice": "2026",
                "montant": None,
                "statut": "a_payer",
            }
        ]
        mock_tva.return_value = []

        result = run(dry_run=True)
        assert len(result["erreurs"]) == 1


def test_run_dry_run_pas_envoi():
    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is") as mock_is,
        patch(
            "apps.jmpartners.agents.echeance_agent.fetch_declarations_tva"
        ) as mock_tva,
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom") as mock_nom,
        patch("apps.jmpartners.agents.echeance_agent.send_telegram_message") as mock_tg,
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport") as mock_email,
    ):
        today = date.today()
        mock_is.return_value = [
            {
                "id": "a1",
                "dossier_id": "d1",
                "contact_id": "c1",
                "numero_acompte": 1,
                "exercice": "2026",
                "deadline": (today + timedelta(days=3)).isoformat(),
                "montant": 500.0,
                "statut": "a_payer",
            }
        ]
        mock_tva.return_value = []
        mock_nom.return_value = "Test"

        result = run(dry_run=True)
        assert result["rapport_envoye"] is False
        mock_tg.assert_not_called()
        mock_email.assert_not_called()


def test_run_rapport_envoye_non_dry_run():
    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is") as mock_is,
        patch(
            "apps.jmpartners.agents.echeance_agent.fetch_declarations_tva"
        ) as mock_tva,
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom") as mock_nom,
        patch("apps.jmpartners.agents.echeance_agent.send_telegram_message") as mock_tg,
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport") as mock_email,
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        today = date.today()
        mock_is.return_value = [
            {
                "id": "a1",
                "dossier_id": "d1",
                "contact_id": "c1",
                "numero_acompte": 2,
                "exercice": "2026",
                "deadline": (today + timedelta(days=2)).isoformat(),
                "montant": 2000.0,
                "statut": "a_payer",
            }
        ]
        mock_tva.return_value = []
        mock_nom.return_value = "Client Urgent"
        mock_tg.return_value = True
        mock_email.return_value = True

        result = run(dry_run=False)
        assert result["rapport_envoye"] is True

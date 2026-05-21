"""Tests pour apps.jmpartners.agents.relance_handler."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.document_checker import (
    DocumentCheckerResult,
    DocumentManquant,
)
from apps.jmpartners.agents.relance_handler import (
    TONALITE_PAR_URGENCE,
    _urgence_max,
    relance_deja_envoyee,
    run,
)


def _make_result(
    manquants: list[DocumentManquant], contact_id: str = "cnt-1"
) -> DocumentCheckerResult:
    return DocumentCheckerResult(
        dossier_id="dos-1",
        contact_id=contact_id,
        type_dossier="bilan",
        manquants=manquants,
        complets=[],
        erreur=None,
    )


def _manquant(urgence: str | None) -> DocumentManquant:
    return DocumentManquant(
        nom_document="Grand livre",
        type_document="grand_livre",
        deadline=(date.today() + timedelta(days=3)).isoformat(),
        urgence=urgence,
    )


# ─── _urgence_max ─────────────────────────────────────────────────────────────


def test_urgence_max_j0():
    result = _make_result([_manquant("J-7"), _manquant("J-0"), _manquant("J-3")])
    assert _urgence_max(result) == "J-0"


def test_urgence_max_single():
    result = _make_result([_manquant("J-7")])
    assert _urgence_max(result) == "J-7"


def test_urgence_max_none():
    result = _make_result([])
    assert _urgence_max(result) is None


# ─── tonalite par urgence ─────────────────────────────────────────────────────


def test_tonalite_urgent():
    assert TONALITE_PAR_URGENCE["J-0"] == "urgent"


def test_tonalite_ferme():
    assert TONALITE_PAR_URGENCE["J-3"] == "ferme"


def test_tonalite_cordial():
    assert TONALITE_PAR_URGENCE["J-7"] == "cordial"


# ─── relance_deja_envoyee ─────────────────────────────────────────────────────


def test_relance_pas_deja_envoyee():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value.data = []
    assert relance_deja_envoyee(supabase, "cnt-1", "dos-1") is False


def test_relance_deja_envoyee():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value.data = [
        {"id": "journal-1"}
    ]
    assert relance_deja_envoyee(supabase, "cnt-1", "dos-1") is True


def test_relance_doublon_check_error_returns_false():
    supabase = MagicMock()
    supabase.table.side_effect = Exception("DB error")
    assert relance_deja_envoyee(supabase, "cnt-1", "dos-1") is False


# ─── run ──────────────────────────────────────────────────────────────────────


def test_run_aucun_manquant():
    result = _make_result([])
    r = run(result, dry_run=True)
    assert r["envoye"] is False
    assert r["raison_skip"] == "Aucun document manquant"


def test_run_dry_run_compose_sans_envoyer():
    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client") as _mock_sb,
        patch(
            "apps.jmpartners.agents.relance_handler.get_anthropic_client"
        ) as _mock_ai,
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee") as mock_dd,
        patch(
            "apps.jmpartners.agents.relance_handler.fetch_contact_email"
        ) as mock_email,
        patch("apps.jmpartners.agents.relance_handler.compose_relance") as mock_compose,
        patch("apps.jmpartners.agents.relance_handler.send_smtp") as mock_smtp,
    ):
        mock_dd.return_value = False
        mock_email.return_value = ("client@example.com", "SARL Test")
        mock_compose.return_value = ("Relance docs", "Corps de l'email")

        result = run(_make_result([_manquant("J-7")]), dry_run=True)

        assert result["envoye"] is False
        assert result["raison_skip"] == "dry_run"
        assert result["email_destinataire"] == "client@example.com"
        mock_smtp.assert_not_called()


def test_run_skip_doublon():
    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee") as mock_dd,
        patch("apps.jmpartners.agents.relance_handler.log_journal") as mock_log,
    ):
        mock_dd.return_value = True
        mock_log.return_value = "journal-skip"

        result = run(_make_result([_manquant("J-3")]))
        assert result["envoye"] is False
        assert "48h" in result["raison_skip"]


def test_run_erreur_smtp_retourne_echec():
    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee") as mock_dd,
        patch(
            "apps.jmpartners.agents.relance_handler.fetch_contact_email"
        ) as mock_email,
        patch("apps.jmpartners.agents.relance_handler.compose_relance") as mock_compose,
        patch("apps.jmpartners.agents.relance_handler.send_smtp") as mock_smtp,
        patch("apps.jmpartners.agents.relance_handler.log_journal"),
    ):
        mock_dd.return_value = False
        mock_email.return_value = ("client@example.com", "Test")
        mock_compose.return_value = ("Sujet", "Corps")
        mock_smtp.return_value = False

        result = run(_make_result([_manquant("J-0")]))
        assert result["envoye"] is False
        assert result["raison_skip"] == "Erreur SMTP"


def test_run_sans_contact_id():
    result = _make_result([_manquant("J-7")], contact_id=None)
    r = run(result, dry_run=True)
    assert r["envoye"] is False
    assert "contact_id" in r["raison_skip"]


def test_run_envoi_succes():
    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee") as mock_dd,
        patch(
            "apps.jmpartners.agents.relance_handler.fetch_contact_email"
        ) as mock_email,
        patch("apps.jmpartners.agents.relance_handler.compose_relance") as mock_compose,
        patch("apps.jmpartners.agents.relance_handler.send_smtp") as mock_smtp,
        patch("apps.jmpartners.agents.relance_handler.log_journal") as mock_log,
    ):
        mock_dd.return_value = False
        mock_email.return_value = ("client@example.com", "Client Test")
        mock_compose.return_value = ("Relance urgente", "Corps")
        mock_smtp.return_value = True
        mock_log.return_value = "journal-1"

        result = run(_make_result([_manquant("J-0")]))
        assert result["envoye"] is True
        assert result["raison_skip"] is None
        assert result["journal_id"] == "journal-1"

"""Tests pour apps.jmpartners.agents.document_checker."""

from datetime import date, timedelta
from unittest.mock import patch

from apps.jmpartners.agents.document_checker import (
    DOCUMENTS_ATTENDUS,
    _compute_urgence,
    run,
)

# ─── _compute_urgence ────────────────────────────────────────────────────────


def test_urgence_j0():
    assert _compute_urgence(date.today()) == "J-0"


def test_urgence_j3():
    assert _compute_urgence(date.today() + timedelta(days=2)) == "J-3"


def test_urgence_j7():
    assert _compute_urgence(date.today() + timedelta(days=5)) == "J-7"


def test_urgence_j15():
    assert _compute_urgence(date.today() + timedelta(days=12)) == "J-15"


def test_urgence_none_far_future():
    assert _compute_urgence(date.today() + timedelta(days=30)) is None


def test_urgence_none_no_deadline():
    assert _compute_urgence(None) is None


# ─── DOCUMENTS_ATTENDUS config ───────────────────────────────────────────────


def test_documents_attendus_bilan():
    assert "grand_livre" in DOCUMENTS_ATTENDUS["bilan"]
    assert "balance" in DOCUMENTS_ATTENDUS["bilan"]
    assert len(DOCUMENTS_ATTENDUS["bilan"]) >= 4


def test_documents_attendus_tva():
    assert "ca_mensuel" in DOCUMENTS_ATTENDUS["tva"]
    assert len(DOCUMENTS_ATTENDUS["tva"]) >= 2


# ─── run — dossier bilan complet ─────────────────────────────────────────────


def test_run_dossier_complet():
    with (
        patch(
            "apps.jmpartners.agents.document_checker.get_supabase_client"
        ) as _mock_sb,
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
        patch(
            "apps.jmpartners.agents.document_checker.fetch_documents_presents"
        ) as mock_docs,
        patch("apps.jmpartners.agents.document_checker.log_journal"),
    ):
        mock_fd.return_value = {
            "id": "dos-1",
            "contact_id": "cnt-1",
            "type": "tva",
            "deadline": (date.today() + timedelta(days=10)).isoformat(),
        }
        mock_docs.return_value = ["ca_mensuel", "factures_tva", "releves_bancaires"]

        result = run("dos-1", dry_run=True)

        assert result["erreur"] is None
        assert len(result["manquants"]) == 0
        assert len(result["complets"]) == 3


def test_run_dossier_avec_manquants():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
        patch(
            "apps.jmpartners.agents.document_checker.fetch_documents_presents"
        ) as mock_docs,
        patch("apps.jmpartners.agents.document_checker.log_journal"),
    ):
        mock_fd.return_value = {
            "id": "dos-2",
            "contact_id": "cnt-2",
            "type": "bilan",
            "deadline": (date.today() + timedelta(days=2)).isoformat(),
        }
        mock_docs.return_value = ["balance", "factures_ventes"]

        result = run("dos-2", dry_run=True)

        assert len(result["manquants"]) == 3
        types_manquants = [m["type_document"] for m in result["manquants"]]
        assert "grand_livre" in types_manquants
        assert all(m["urgence"] == "J-3" for m in result["manquants"])


def test_run_type_dossier_inconnu():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
    ):
        mock_fd.return_value = {
            "id": "dos-3",
            "contact_id": "cnt-3",
            "type": "inconnu",
            "deadline": None,
        }
        result = run("dos-3", dry_run=True)
        assert result["erreur"] is not None
        assert "inconnu" in result["erreur"]


def test_run_dossier_introuvable():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
    ):
        mock_fd.return_value = None
        result = run("dos-999", dry_run=True)
        assert result["erreur"] is not None
        assert result["type_dossier"] == "inconnu"


def test_run_dossier_tva_manquants():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
        patch(
            "apps.jmpartners.agents.document_checker.fetch_documents_presents"
        ) as mock_docs,
        patch("apps.jmpartners.agents.document_checker.log_journal"),
    ):
        mock_fd.return_value = {
            "id": "dos-4",
            "contact_id": "cnt-4",
            "type": "tva",
            "deadline": (date.today() + timedelta(days=5)).isoformat(),
        }
        mock_docs.return_value = ["releves_bancaires"]

        result = run("dos-4", dry_run=True)
        assert len(result["manquants"]) == 2
        assert all(m["urgence"] == "J-7" for m in result["manquants"])


def test_run_dossier_is_manquants():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
        patch(
            "apps.jmpartners.agents.document_checker.fetch_documents_presents"
        ) as mock_docs,
        patch("apps.jmpartners.agents.document_checker.log_journal"),
    ):
        mock_fd.return_value = {
            "id": "dos-5",
            "contact_id": "cnt-5",
            "type": "is",
            "deadline": (date.today() + timedelta(days=10)).isoformat(),
        }
        mock_docs.return_value = []

        result = run("dos-5", dry_run=True)
        types = {m["type_document"] for m in result["manquants"]}
        assert types == {"resultat_comptable", "liasse_fiscale", "bilan_n_1"}


def test_run_dry_run_no_journal():
    with (
        patch("apps.jmpartners.agents.document_checker.get_supabase_client"),
        patch("apps.jmpartners.agents.document_checker.fetch_dossier") as mock_fd,
        patch(
            "apps.jmpartners.agents.document_checker.fetch_documents_presents"
        ) as mock_docs,
        patch("apps.jmpartners.agents.document_checker.log_journal") as mock_log,
    ):
        mock_fd.return_value = {
            "id": "dos-6",
            "contact_id": "cnt-6",
            "type": "tva",
            "deadline": None,
        }
        mock_docs.return_value = []
        run("dos-6", dry_run=True)
        mock_log.assert_called_once()
        _, kwargs = mock_log.call_args
        # dry_run=True doit être passé à log_journal
        assert kwargs.get("dry_run") is True or mock_log.call_args.args[-1] is True

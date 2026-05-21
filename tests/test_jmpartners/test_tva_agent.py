"""Tests pour apps.jmpartners.agents.tva_agent."""

from datetime import date, timedelta
from unittest.mock import patch

from apps.jmpartners.agents.tva_agent import run, send_telegram_alerte

# ─── send_telegram_alerte ────────────────────────────────────────────────────


def test_telegram_non_configure():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
        result = send_telegram_alerte("test message")
    assert result is False


def test_telegram_erreur_reseau():
    with (
        patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "fake-token",
                "TELEGRAM_CHAT_ID": "12345",
            },
        ),
        patch("apps.jmpartners.agents.tva_agent.httpx.post") as mock_post,
    ):
        mock_post.side_effect = Exception("network error")
        result = send_telegram_alerte("test")
    assert result is False


# ─── run ──────────────────────────────────────────────────────────────────────


def test_run_aucune_declaration():
    with (
        patch("apps.jmpartners.agents.tva_agent.get_supabase_client"),
        patch(
            "apps.jmpartners.agents.tva_agent.fetch_declarations_a_venir"
        ) as mock_decl,
    ):
        mock_decl.return_value = []
        result = run(dry_run=True)
        assert result["declarations_analysees"] == 0
        assert result["alertes_envoyees"] == 0


def test_run_declaration_avec_manquants_dry_run():
    with (
        patch("apps.jmpartners.agents.tva_agent.get_supabase_client"),
        patch(
            "apps.jmpartners.agents.tva_agent.fetch_declarations_a_venir"
        ) as mock_decl,
        patch("apps.jmpartners.agents.tva_agent.fetch_contact_nom") as mock_nom,
        patch("apps.jmpartners.agents.tva_agent.check_docs") as mock_check,
        patch("apps.jmpartners.agents.tva_agent.send_telegram_alerte") as mock_tg,
    ):
        deadline_j7 = (date.today() + timedelta(days=7)).isoformat()
        mock_decl.return_value = [
            {
                "id": "decl-1",
                "dossier_id": "dos-1",
                "contact_id": "cnt-1",
                "periode": "mai-2026",
                "deadline": deadline_j7,
                "statut": "pieces_manquantes",
            }
        ]
        mock_nom.return_value = "SARL Test"
        from apps.jmpartners.agents.document_checker import (
            DocumentCheckerResult,
            DocumentManquant,
        )

        mock_check.return_value = DocumentCheckerResult(
            dossier_id="dos-1",
            contact_id="cnt-1",
            type_dossier="tva",
            manquants=[
                DocumentManquant(
                    nom_document="CA mensuel",
                    type_document="ca_mensuel",
                    deadline=deadline_j7,
                    urgence="J-7",
                )
            ],
            complets=[],
            erreur=None,
        )

        result = run(dry_run=True)

        assert result["declarations_analysees"] == 1
        assert result["pieces_manquantes_total"] == 1
        assert result["alertes_envoyees"] == 0
        mock_tg.assert_not_called()


def test_run_declaration_complete_pas_alerte():
    with (
        patch("apps.jmpartners.agents.tva_agent.get_supabase_client"),
        patch(
            "apps.jmpartners.agents.tva_agent.fetch_declarations_a_venir"
        ) as mock_decl,
        patch("apps.jmpartners.agents.tva_agent.fetch_contact_nom") as mock_nom,
        patch("apps.jmpartners.agents.tva_agent.check_docs") as mock_check,
    ):
        mock_decl.return_value = [
            {
                "id": "decl-2",
                "dossier_id": "dos-2",
                "contact_id": "cnt-2",
                "periode": "mai-2026",
                "deadline": (date.today() + timedelta(days=7)).isoformat(),
                "statut": "pret",
            }
        ]
        mock_nom.return_value = "Boulangerie"
        from apps.jmpartners.agents.document_checker import DocumentCheckerResult

        mock_check.return_value = DocumentCheckerResult(
            dossier_id="dos-2",
            contact_id="cnt-2",
            type_dossier="tva",
            manquants=[],
            complets=["ca_mensuel", "factures_tva", "releves_bancaires"],
            erreur=None,
        )

        result = run(dry_run=True)
        assert result["alertes_envoyees"] == 0
        assert result["pieces_manquantes_total"] == 0
        assert result["declarations"][0]["statut"] == "pret"


def test_run_erreur_agent_logue_et_continue():
    with (
        patch("apps.jmpartners.agents.tva_agent.get_supabase_client"),
        patch(
            "apps.jmpartners.agents.tva_agent.fetch_declarations_a_venir"
        ) as mock_decl,
        patch("apps.jmpartners.agents.tva_agent.fetch_contact_nom"),
        patch("apps.jmpartners.agents.tva_agent.check_docs") as mock_check,
    ):
        mock_decl.return_value = [
            {
                "id": "decl-err",
                "dossier_id": "dos-err",
                "contact_id": "cnt-err",
                "periode": "X",
                "deadline": (date.today() + timedelta(days=5)).isoformat(),
                "statut": "a_preparer",
            }
        ]
        mock_check.side_effect = Exception("Supabase error")

        result = run(dry_run=True)
        assert len(result["erreurs"]) == 1
        assert result["declarations_analysees"] == 0


def test_run_alerte_envoyee_non_dry_run():
    with (
        patch("apps.jmpartners.agents.tva_agent.get_supabase_client"),
        patch(
            "apps.jmpartners.agents.tva_agent.fetch_declarations_a_venir"
        ) as mock_decl,
        patch("apps.jmpartners.agents.tva_agent.fetch_contact_nom") as mock_nom,
        patch("apps.jmpartners.agents.tva_agent.check_docs") as mock_check,
        patch("apps.jmpartners.agents.tva_agent.send_telegram_alerte") as mock_tg,
        patch("apps.jmpartners.agents.tva_agent.log_alerte_tva"),
    ):
        deadline_j7 = (date.today() + timedelta(days=7)).isoformat()
        mock_decl.return_value = [
            {
                "id": "d1",
                "dossier_id": "dos-1",
                "contact_id": "cnt-1",
                "periode": "mai-2026",
                "deadline": deadline_j7,
                "statut": "pieces_manquantes",
            }
        ]
        mock_nom.return_value = "Client Test"
        from apps.jmpartners.agents.document_checker import (
            DocumentCheckerResult,
            DocumentManquant,
        )

        mock_check.return_value = DocumentCheckerResult(
            dossier_id="dos-1",
            contact_id="cnt-1",
            type_dossier="tva",
            manquants=[
                DocumentManquant(
                    nom_document="CA",
                    type_document="ca_mensuel",
                    deadline=deadline_j7,
                    urgence="J-7",
                )
            ],
            complets=[],
            erreur=None,
        )
        mock_tg.return_value = True

        result = run(dry_run=False)
        assert result["alertes_envoyees"] == 1

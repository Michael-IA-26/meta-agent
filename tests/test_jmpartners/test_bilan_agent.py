"""Tests pour apps.jmpartners.agents.bilan_agent."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.bilan_agent import HORIZONS_ALERTE, BilanAgent

# ─── Helper factories ────────────────────────────────────────────────────────


def _make_dossier(
    dossier_id: str = "dos-bilan-1",
    deadline: str | None = None,
    contact_nom: str = "SARL Test",
) -> dict:
    if deadline is None:
        deadline = (date.today() + timedelta(days=7)).isoformat()
    return {
        "id": dossier_id,
        "contact_id": "cnt-1",
        "deadline": deadline,
        "responsable_email": "resp@cabinet.fr",
        "contacts": {"nom": contact_nom, "email": "client@test.fr"},
    }


# ─── Happy path ───────────────────────────────────────────────────────────────


def test_run_happy_path_j7():
    """J-7 exact → alerte envoyée, BilanAlert bien formée."""
    deadline = (date.today() + timedelta(days=7)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline)]
    )
    agent._check_documents = MagicMock(return_value=["grand_livre", "balance"])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()

    assert len(results) == 1
    alert = results[0]
    assert alert["dossier_id"] == "dos-bilan-1"
    assert alert["jours_restants"] == 7
    assert alert["alerte_envoyee"] is True
    assert "grand_livre" in alert["documents_manquants"]
    agent._send_alerte.assert_called_once()
    agent._log_journal.assert_called_once()


def test_run_happy_path_j30():
    """J-30 exact → alerte envoyée."""
    deadline = (date.today() + timedelta(days=30)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline)]
    )
    agent._check_documents = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["jours_restants"] == 30
    assert results[0]["alerte_envoyee"] is True


# ─── Supabase down ────────────────────────────────────────────────────────────


def test_run_supabase_down_retourne_liste_vide():
    """Si Supabase est KO lors du fetch, run() retourne une liste vide."""
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(return_value=[])  # type: ignore[method-assign]

    results = agent.run()
    assert results == []


def test_fetch_dossiers_bilan_erreur_supabase():
    """_fetch_dossiers_bilan retourne [] si Supabase lève une exception."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception(
        "connexion refusée"
    )
    with patch(
        "apps.jmpartners.agents.bilan_agent.create_client", return_value=mock_sb
    ):
        agent = BilanAgent()
        result = agent._fetch_dossiers_bilan()
    assert result == []


# ─── Aucun dossier bilan ──────────────────────────────────────────────────────


def test_run_aucun_dossier_bilan():
    """Si aucun dossier bilan n'est retourné, run() retourne une liste vide."""
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(return_value=[])  # type: ignore[method-assign]

    results = agent.run()
    assert results == []


# ─── Alerte envoyée J-7 ───────────────────────────────────────────────────────


def test_run_alerte_j7_email_et_telegram_envoyes():
    """À J-7, _send_alerte est appelé et alerte_envoyee=True si ok."""
    deadline = (date.today() + timedelta(days=7)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline, contact_nom="SAS Client")]
    )
    agent._check_documents = MagicMock(return_value=["factures_achats"])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert results[0]["alerte_envoyee"] is True
    assert results[0]["contact_nom"] == "SAS Client"
    agent._send_alerte.assert_called_once()


# ─── Alerte non envoyée si déjà envoyée (horizon hors liste) ─────────────────


def test_run_pas_alerte_si_horizon_hors_liste():
    """Si jours_restants n'est pas dans HORIZONS_ALERTE, aucune alerte n'est émise."""
    deadline = (date.today() + timedelta(days=10)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline)]
    )
    agent._send_alerte = MagicMock()  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert results == []
    agent._send_alerte.assert_not_called()


def test_run_alerte_non_envoyee_si_echec_canaux():
    """Si email et Telegram échouent tous deux, alerte_envoyee=False."""
    deadline = (date.today() + timedelta(days=15)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline)]
    )
    agent._check_documents = MagicMock(return_value=["balance"])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=False)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["alerte_envoyee"] is False


# ─── Log journal ──────────────────────────────────────────────────────────────


def test_log_journal_appele_avec_bons_args():
    """_log_journal est appelé avec le bon dossier_id et action."""
    deadline = (date.today() + timedelta(days=7)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(dossier_id="dos-42", deadline=deadline)]
    )
    agent._check_documents = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    agent.run()

    agent._log_journal.assert_called_once()
    call_args = agent._log_journal.call_args
    assert call_args[0][0] == "dos-42"
    assert "alerte_bilan" in call_args[0][1]


def test_log_journal_erreur_supabase_ne_plante_pas():
    """Si Supabase lève une exception lors du log, _log_journal ne propage pas."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception(
        "DB error"
    )
    with patch(
        "apps.jmpartners.agents.bilan_agent.create_client", return_value=mock_sb
    ):
        agent = BilanAgent()
        # Ne doit pas lever d'exception
        agent._log_journal("dos-1", "alerte_bilan", "message test")


# ─── _send_email / _send_telegram ────────────────────────────────────────────


def test_send_email_non_configure():
    """_send_email retourne False si SMTP non configuré."""
    with patch.dict("os.environ", {"SMTP_USER": "", "SMTP_PASS": ""}):
        agent = BilanAgent()
        result = agent._send_email("Sujet test", "Corps test")
    assert result is False


def test_send_telegram_non_configure():
    """_send_telegram retourne False si Telegram non configuré."""
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
        agent = BilanAgent()
        result = agent._send_telegram("message test")
    assert result is False


@pytest.mark.parametrize("jours", HORIZONS_ALERTE)
def test_horizons_alerte_reconnus(jours: int):
    """Chaque horizon d'alerte (30, 15, 7) doit déclencher une alerte."""
    deadline = (date.today() + timedelta(days=jours)).isoformat()
    agent = BilanAgent()
    agent._fetch_dossiers_bilan = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_dossier(deadline=deadline)]
    )
    agent._check_documents = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["jours_restants"] == jours

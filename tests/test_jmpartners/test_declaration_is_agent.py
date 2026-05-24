"""Tests pour apps.jmpartners.agents.declaration_is_agent."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.declaration_is_agent import (
    HORIZONS_ALERTE,
    DeclarationISAgent,
)

# ─── Helper factories ────────────────────────────────────────────────────────


def _make_echeance(
    dossier_id: str = "dos-is-1",
    echeance: str | None = None,
    siren: str = "123456789",
    raison_sociale: str = "SAS Test IS",
    statut: str = "en_attente",
) -> dict:
    if echeance is None:
        echeance = (date.today() + timedelta(days=7)).isoformat()
    return {
        "id": "ech-1",
        "dossier_id": dossier_id,
        "echeance": echeance,
        "montant_estime": 5000.0,
        "statut": statut,
        "dossiers": {
            "cabinet_id": "jmpartners",
            "siren": siren,
            "raison_sociale": raison_sociale,
        },
    }


# ─── Happy path ───────────────────────────────────────────────────────────────


def test_run_happy_path_j7():
    """J-7 exact → alerte envoyée, DeclarationISAlert bien formée."""
    echeance = (date.today() + timedelta(days=7)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(echeance=echeance)]
    )
    agent._get_elements_disponibles = MagicMock(  # type: ignore[method-assign]
        return_value=["liasse_fiscale", "resultat_comptable"]
    )
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()

    assert len(results) == 1
    alert = results[0]
    assert alert["dossier_id"] == "dos-is-1"
    assert alert["jours_restants"] == 7
    assert alert["siren"] == "123456789"
    assert alert["raison_sociale"] == "SAS Test IS"
    assert alert["alerte_envoyee"] is True
    assert "liasse_fiscale" in alert["elements_disponibles"]
    agent._send_alerte.assert_called_once()
    agent._log_journal.assert_called_once()


def test_run_happy_path_j15():
    """J-15 exact → alerte envoyée."""
    echeance = (date.today() + timedelta(days=15)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(echeance=echeance)]
    )
    agent._get_elements_disponibles = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["jours_restants"] == 15


# ─── Supabase down ────────────────────────────────────────────────────────────


def test_run_supabase_down_retourne_liste_vide():
    """Si Supabase est KO, run() retourne une liste vide."""
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(return_value=[])  # type: ignore[method-assign]

    results = agent.run()
    assert results == []


def test_fetch_echeances_erreur_supabase():
    """_fetch_echeances_is retourne [] si Supabase lève une exception."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.neq.return_value.execute.side_effect = Exception(
        "timeout"
    )
    with patch(
        "apps.jmpartners.agents.declaration_is_agent.create_client",
        return_value=mock_sb,
    ):
        agent = DeclarationISAgent()
        result = agent._fetch_echeances_is()
    assert result == []


# ─── Aucun dossier IS ────────────────────────────────────────────────────────


def test_run_aucune_echeance_is():
    """Si aucune échéance IS non payée, run() retourne une liste vide."""
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(return_value=[])  # type: ignore[method-assign]

    results = agent.run()
    assert results == []


# ─── Alerte envoyée J-7 ───────────────────────────────────────────────────────


def test_run_alerte_j7_envoyee():
    """À J-7, alerte_envoyee=True si au moins un canal réussit."""
    echeance = (date.today() + timedelta(days=7)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[
            _make_echeance(
                echeance=echeance,
                siren="987654321",
                raison_sociale="EURL Client",
            )
        ]
    )
    agent._get_elements_disponibles = MagicMock(return_value=["bilan_n_1"])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert results[0]["alerte_envoyee"] is True
    assert results[0]["raison_sociale"] == "EURL Client"


# ─── Alerte non envoyée si déjà envoyée / horizon hors liste ─────────────────


def test_run_pas_alerte_si_horizon_hors_liste():
    """Si jours_restants n'est pas dans HORIZONS_ALERTE, aucune alerte."""
    echeance = (date.today() + timedelta(days=10)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(echeance=echeance)]
    )
    agent._send_alerte = MagicMock()  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert results == []
    agent._send_alerte.assert_not_called()


def test_run_alerte_non_envoyee_si_canaux_echouent():
    """Si email et Telegram échouent, alerte_envoyee=False."""
    echeance = (date.today() + timedelta(days=30)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(echeance=echeance)]
    )
    agent._get_elements_disponibles = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=False)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["alerte_envoyee"] is False


# ─── Log journal ──────────────────────────────────────────────────────────────


def test_log_journal_appele_avec_bons_args():
    """_log_journal est appelé avec le bon dossier_id et action."""
    echeance = (date.today() + timedelta(days=7)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(dossier_id="dos-99", echeance=echeance)]
    )
    agent._get_elements_disponibles = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    agent.run()

    agent._log_journal.assert_called_once()
    call_args = agent._log_journal.call_args
    assert call_args[0][0] == "dos-99"
    assert "alerte_declaration_is" in call_args[0][1]


def test_log_journal_erreur_supabase_ne_plante_pas():
    """Si Supabase lève une exception dans _log_journal, pas de propagation."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception(
        "DB error"
    )
    with patch(
        "apps.jmpartners.agents.declaration_is_agent.create_client",
        return_value=mock_sb,
    ):
        agent = DeclarationISAgent()
        agent._log_journal("dos-1", "alerte_declaration_is", "test")


# ─── Canaux de notification ───────────────────────────────────────────────────


def test_send_email_non_configure():
    """_send_email retourne False si SMTP non configuré."""
    with patch.dict("os.environ", {"SMTP_USER": "", "SMTP_PASS": ""}):
        agent = DeclarationISAgent()
        result = agent._send_email("Sujet", "Corps")
    assert result is False


@pytest.mark.parametrize("jours", HORIZONS_ALERTE)
def test_horizons_alerte_reconnus(jours: int):
    """Chaque horizon (30, 15, 7) doit déclencher une alerte."""
    echeance = (date.today() + timedelta(days=jours)).isoformat()
    agent = DeclarationISAgent()
    agent._fetch_echeances_is = MagicMock(  # type: ignore[method-assign]
        return_value=[_make_echeance(echeance=echeance)]
    )
    agent._get_elements_disponibles = MagicMock(return_value=[])  # type: ignore[method-assign]
    agent._send_alerte = MagicMock(return_value=True)  # type: ignore[method-assign]
    agent._log_journal = MagicMock()  # type: ignore[method-assign]

    results = agent.run()
    assert len(results) == 1
    assert results[0]["jours_restants"] == jours

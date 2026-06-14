"""Tests pour apps.jmpartners.agents.acompte_is_agent."""

from datetime import date
from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.acompte_is_agent import (
    ECHEANCES_IS,
    AcompteISAgent,
    _echeances_dans_horizon,
    _prochaine_echeance_is,
)

# ─── _prochaine_echeance_is ──────────────────────────────────────────────────


def test_prochaine_echeance_is_avant_mars():
    today = date(2025, 1, 1)
    result = _prochaine_echeance_is(today)
    assert result == date(2025, 3, 15)


def test_prochaine_echeance_is_apres_decembre():
    today = date(2025, 12, 20)
    result = _prochaine_echeance_is(today)
    assert result == date(2026, 3, 15)


def test_prochaine_echeance_is_le_jour_j():
    today = date(2025, 6, 15)
    result = _prochaine_echeance_is(today)
    assert result == date(2025, 6, 15)


# ─── _echeances_dans_horizon ─────────────────────────────────────────────────


def test_echeances_dans_horizon_vide():
    today = date(2025, 1, 1)
    result = _echeances_dans_horizon(today, 5)
    assert result == []


def test_echeances_dans_horizon_j15():
    today = date(2025, 3, 1)
    result = _echeances_dans_horizon(today, 15)
    assert date(2025, 3, 15) in result


def test_echeances_dans_horizon_toutes_dans_annee():
    today = date(2025, 1, 1)
    result = _echeances_dans_horizon(today, 365)
    dates = {(d.month, d.day) for d in result}
    for mois, jour in ECHEANCES_IS:
        assert (mois, jour) in dates


# ─── AcompteISAgent.run — aucune échéance dans horizon ───────────────────────


def test_run_aucune_echeance():
    with patch(
        "apps.jmpartners.agents.acompte_is_agent._echeances_dans_horizon",
        return_value=[],
    ):
        agent = AcompteISAgent()
        result = agent.run()

    assert result == []


# ─── AcompteISAgent.run — alerte non déclenchée si jour hors horizon ─────────


def test_run_echeance_pas_dans_horizons_alerte():
    today = date(2025, 3, 4)
    echeance = date(2025, 3, 15)

    with (
        patch(
            "apps.jmpartners.agents.acompte_is_agent._echeances_dans_horizon",
            return_value=[echeance],
        ),
        patch("apps.jmpartners.agents.acompte_is_agent.date") as mock_date,
    ):
        mock_date.today.return_value = today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        agent = AcompteISAgent()
        agent._fetch_dossiers = MagicMock(return_value=[])
        result = agent.run()

    assert result == []


# ─── AcompteISAgent.run — alerte à J-15 ──────────────────────────────────────


def test_run_alerte_j15():
    today = date(2025, 2, 28)
    echeance = date(2025, 3, 15)

    dossiers = [
        {
            "id": "dos-1",
            "siren": "123456789",
            "raison_sociale": "SAS Test",
            "montant_is_estime": 5000.0,
            "statut": "actif",
        }
    ]

    with (
        patch(
            "apps.jmpartners.agents.acompte_is_agent._echeances_dans_horizon",
            return_value=[echeance],
        ),
        patch("apps.jmpartners.agents.acompte_is_agent.date") as mock_date,
    ):
        mock_date.today.return_value = today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        agent = AcompteISAgent()
        agent._fetch_dossiers = MagicMock(return_value=dossiers)
        agent._send_email = MagicMock(return_value=True)
        agent._send_telegram = MagicMock(return_value=True)
        result = agent.run()

    assert len(result) == 1
    assert result[0]["siren"] == "123456789"
    assert result[0]["jours_restants"] == 15
    assert result[0]["alerte_envoyee"] is True


# ─── AcompteISAgent._send_email — SMTP non configuré ─────────────────────────


def test_send_email_non_configure():
    with patch("apps.jmpartners.agents.acompte_is_agent.send_email", return_value=False):
        agent = AcompteISAgent()
        result = agent._send_email("dest@test.com", "sujet", "corps")

    assert result is False


# ─── AcompteISAgent._send_email — erreur mailer ──────────────────────────────


def test_send_email_erreur_smtp():
    with patch(
        "apps.jmpartners.agents.acompte_is_agent.send_email",
        return_value=False,
    ):
        agent = AcompteISAgent()
        result = agent._send_email("dest@test.com", "sujet", "corps")

    assert result is False


# ─── AcompteISAgent._send_telegram — non configuré ───────────────────────────


def test_send_telegram_non_configure():
    with patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
    ):
        agent = AcompteISAgent()
        result = agent._send_telegram("test message")

    assert result is False


# ─── AcompteISAgent._send_telegram — erreur réseau ───────────────────────────


def test_send_telegram_erreur_reseau():
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "fake-token", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch(
            "apps.jmpartners.agents.acompte_is_agent.httpx.post",
            side_effect=Exception("network error"),
        ),
    ):
        agent = AcompteISAgent()
        result = agent._send_telegram("test")

    assert result is False


# ─── AcompteISAgent._fetch_dossiers — erreur Supabase ────────────────────────


def test_fetch_dossiers_erreur_supabase():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.neq.return_value.execute.side_effect = Exception(
        "DB error"
    )

    with patch(
        "apps.jmpartners.agents.acompte_is_agent.create_client",
        return_value=mock_sb,
    ):
        agent = AcompteISAgent()
        result = agent._fetch_dossiers()

    assert result == []


# ─── AcompteISAgent.run — alerte_envoyee False si email et telegram échouent ─


def test_run_alerte_non_envoyee_si_tous_echecs():
    today = date(2025, 2, 28)
    echeance = date(2025, 3, 15)

    dossiers = [
        {
            "id": "dos-2",
            "siren": "987654321",
            "raison_sociale": "EURL Fail",
            "montant_is_estime": None,
            "statut": "actif",
        }
    ]

    with (
        patch(
            "apps.jmpartners.agents.acompte_is_agent._echeances_dans_horizon",
            return_value=[echeance],
        ),
        patch("apps.jmpartners.agents.acompte_is_agent.date") as mock_date,
    ):
        mock_date.today.return_value = today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        agent = AcompteISAgent()
        agent._fetch_dossiers = MagicMock(return_value=dossiers)
        agent._send_email = MagicMock(return_value=False)
        agent._send_telegram = MagicMock(return_value=False)
        result = agent.run()

    assert len(result) == 1
    assert result[0]["alerte_envoyee"] is False
    assert result[0]["montant_estime"] == 0.0

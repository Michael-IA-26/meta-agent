"""Tests pour apps.jmpartners.agents.notification_agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.notification_agent import (
    NotificationAgent,
    NotificationPayload,
)

# ─── Helper factory ───────────────────────────────────────────────────────────


def _make_payload(
    dossier_id: str = "dos-1",
    type_: str = "bilan",
    urgence: str = "J-7",
    message: str = "Alerte test",
    email: str = "client@test.fr",
    nom: str = "SAS Test",
) -> NotificationPayload:
    return NotificationPayload(
        dossier_id=dossier_id,
        type=type_,
        urgence=urgence,
        message=message,
        destinataire_email=email,
        destinataire_nom=nom,
    )


# ─── Routing J-3 (Telegram + email) ──────────────────────────────────────────


def test_send_j3_envoie_telegram_et_email():
    """J-3 → Telegram immédiat + email, les deux sont appelés."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_telegram = MagicMock(return_value=True)
    agent._send_email = MagicMock(return_value=True)
    agent._log_journal = MagicMock()

    payload = _make_payload(urgence="J-3")
    result = agent.send(payload)

    assert result is True
    agent._send_telegram.assert_called_once()
    agent._send_email.assert_called_once()


def test_send_j3_retourne_true_si_telegram_seul_ok():
    """J-3 → True si Telegram ok même si email échoue."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_telegram = MagicMock(return_value=True)
    agent._send_email = MagicMock(return_value=False)
    agent._log_journal = MagicMock()

    result = agent.send(_make_payload(urgence="J-3"))
    assert result is True


# ─── Routing J-7 (email seul) ────────────────────────────────────────────────


def test_send_j7_email_seul():
    """J-7 → email seul, Telegram non appelé."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_email = MagicMock(return_value=True)
    agent._send_telegram = MagicMock(return_value=True)
    agent._log_journal = MagicMock()

    payload = _make_payload(urgence="J-7")
    result = agent.send(payload)

    assert result is True
    agent._send_email.assert_called_once()
    agent._send_telegram.assert_not_called()


def test_send_j7_retourne_false_si_email_echoue():
    """J-7 → False si email échoue."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_email = MagicMock(return_value=False)
    agent._send_telegram = MagicMock()
    agent._log_journal = MagicMock()

    result = agent.send(_make_payload(urgence="J-7"))
    assert result is False
    agent._send_telegram.assert_not_called()


# ─── Déduplication 24h ────────────────────────────────────────────────────────


def test_send_digest_j15_doublon_24h_ignore():
    """J-15 avec doublon 24h → retourne False sans envoyer."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=True)
    agent._send_email = MagicMock()
    agent._send_telegram = MagicMock()
    agent._log_journal = MagicMock()

    result = agent.send(_make_payload(urgence="J-15"))

    assert result is False
    agent._send_email.assert_not_called()
    agent._send_telegram.assert_not_called()
    agent._log_journal.assert_not_called()


def test_send_digest_j30_doublon_24h_ignore():
    """J-30 avec doublon 24h → retourne False sans envoyer."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=True)
    agent._send_email = MagicMock()
    agent._send_telegram = MagicMock()
    agent._log_journal = MagicMock()

    result = agent.send(_make_payload(urgence="J-30"))

    assert result is False
    agent._send_email.assert_not_called()


def test_send_digest_j15_pas_doublon_envoie():
    """J-15 sans doublon → email envoyé."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_email = MagicMock(return_value=True)
    agent._send_telegram = MagicMock()
    agent._log_journal = MagicMock()

    result = agent.send(_make_payload(urgence="J-15"))

    assert result is True
    agent._send_email.assert_called_once()
    agent._send_telegram.assert_not_called()


# ─── Déduplication — vérification Supabase ────────────────────────────────────


def test_is_duplicate_requete_supabase_retourne_true():
    """_is_duplicate retourne True si Supabase retourne count > 0."""
    mock_sb = MagicMock()
    mock_resp = MagicMock()
    mock_resp.count = 1
    mock_resp.data = [{"id": "j-1"}]
    (
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value
    ) = mock_resp

    with patch(
        "apps.jmpartners.agents.notification_agent.create_client",
        return_value=mock_sb,
    ):
        agent = NotificationAgent()
        result = agent._is_duplicate("dos-1", "notification_bilan_J-15")

    assert result is True


def test_is_duplicate_supabase_erreur_retourne_false():
    """Si Supabase lève une exception dans _is_duplicate, retourne False."""
    mock_sb = MagicMock()
    (
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.side_effect
    ) = Exception("DB error")

    with patch(
        "apps.jmpartners.agents.notification_agent.create_client",
        return_value=mock_sb,
    ):
        agent = NotificationAgent()
        result = agent._is_duplicate("dos-1", "notification_bilan_J-15")

    assert result is False


# ─── Batch ────────────────────────────────────────────────────────────────────


def test_send_batch_retourne_liste_bool():
    """send_batch retourne une liste de bool de même longueur que l'entrée."""
    agent = NotificationAgent()
    agent._is_duplicate = MagicMock(return_value=False)
    agent._send_email = MagicMock(return_value=True)
    agent._send_telegram = MagicMock(return_value=True)
    agent._log_journal = MagicMock()

    payloads = [
        _make_payload(dossier_id="dos-1", urgence="J-7"),
        _make_payload(dossier_id="dos-2", urgence="J-3"),
        _make_payload(dossier_id="dos-3", urgence="J-15"),
    ]
    results = agent.send_batch(payloads)

    assert len(results) == 3
    assert all(isinstance(r, bool) for r in results)


def test_send_batch_erreur_une_alerte_continue_les_autres():
    """Si send() lève une exception pour une alerte, send_batch continue."""
    agent = NotificationAgent()

    call_count = 0

    def fake_send(payload: NotificationPayload) -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Erreur volontaire")
        return True

    agent.send = fake_send  # type: ignore[method-assign]

    payloads = [
        _make_payload(dossier_id="dos-1"),
        _make_payload(dossier_id="dos-2"),
        _make_payload(dossier_id="dos-3"),
    ]
    results = agent.send_batch(payloads)

    assert len(results) == 3
    assert results[0] is True
    assert results[1] is False  # exception → False
    assert results[2] is True


# ─── Telegram seul ────────────────────────────────────────────────────────────


def test_send_telegram_non_configure():
    """_send_telegram retourne False si Telegram non configuré."""
    with patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
    ):
        agent = NotificationAgent()
        result = agent._send_telegram("message test")
    assert result is False


def test_send_telegram_erreur_reseau():
    """_send_telegram retourne False si httpx lève une exception."""
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "fake-token", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch(
            "apps.jmpartners.agents.notification_agent.httpx.post",
            side_effect=Exception("network error"),
        ),
    ):
        agent = NotificationAgent()
        result = agent._send_telegram("message test")
    assert result is False

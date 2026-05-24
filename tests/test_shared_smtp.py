"""Tests pour apps.shared.smtp.send_email."""

from unittest.mock import MagicMock, patch

from apps.shared.smtp import send_email

_ENV = {"SMTP_USER": "user@test.fr", "SMTP_PASSWORD": "pass"}


def test_returns_false_si_user_absent():
    with patch.dict("os.environ", {"SMTP_USER": "", "SMTP_PASSWORD": "pass"}):
        result = send_email("dest@test.fr", "sujet", "corps")
    assert result is False


def test_returns_false_si_password_absent():
    with patch.dict("os.environ", {"SMTP_USER": "user@test.fr", "SMTP_PASSWORD": ""}):
        result = send_email("dest@test.fr", "sujet", "corps")
    assert result is False


def test_returns_true_si_succes():
    mock_server = MagicMock()
    with (
        patch.dict("os.environ", _ENV),
        patch("apps.shared.smtp.smtplib.SMTP") as MockSMTP,
    ):
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
        result = send_email("dest@test.fr", "sujet", "corps")
    assert result is True


def test_returns_false_si_erreur_smtp():
    with (
        patch.dict("os.environ", _ENV),
        patch("apps.shared.smtp.smtplib.SMTP", side_effect=Exception("refused")),
    ):
        result = send_email("dest@test.fr", "sujet", "corps")
    assert result is False


def test_destinataire_vide_envoie_a_smtp_user():
    mock_server = MagicMock()
    with (
        patch.dict("os.environ", _ENV),
        patch("apps.shared.smtp.smtplib.SMTP") as MockSMTP,
    ):
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)
        send_email("", "sujet", "corps")
    mock_server.sendmail.assert_called_once()
    args = mock_server.sendmail.call_args[0]
    assert args[1] == ["user@test.fr"]

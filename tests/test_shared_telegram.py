"""Tests pour apps.shared.telegram.send_telegram_message."""

from unittest.mock import MagicMock, patch

from apps.shared.telegram import send_telegram_message


def test_returns_false_si_token_absent():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "123"}):
        result = send_telegram_message("test")
    assert result is False


def test_returns_false_si_chat_id_absent():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": ""}):
        result = send_telegram_message("test")
    assert result is False


def test_returns_true_si_succes():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch("apps.shared.telegram.httpx.post", return_value=mock_resp),
    ):
        result = send_telegram_message("hello")
    assert result is True


def test_returns_false_si_erreur_reseau():
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch("apps.shared.telegram.httpx.post", side_effect=Exception("network error")),
    ):
        result = send_telegram_message("hello")
    assert result is False


def test_bot_token_et_chat_id_kwargs_prioritaires():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with (
        patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}),
        patch("apps.shared.telegram.httpx.post", return_value=mock_resp) as mock_post,
    ):
        result = send_telegram_message("test", bot_token="custom_tok", chat_id="456")
    assert result is True
    call_url = mock_post.call_args[0][0]
    assert "custom_tok" in call_url


def test_message_tronque_a_4096():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    long_msg = "x" * 5000
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch("apps.shared.telegram.httpx.post", return_value=mock_resp) as mock_post,
    ):
        send_telegram_message(long_msg)
    sent_text = mock_post.call_args[1]["json"]["text"]
    assert len(sent_text) == 4096

import os
import sys
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock 'storage' before importing analyzer (analyzer does a local-path import)
_storage_mock = MagicMock()
_storage_mock.save_email.return_value = True
sys.modules.setdefault("storage", _storage_mock)

from apps.email_agent.analyzer import (  # noqa: E402
    SYSTEM_BASE,
    _build_system_prompt,
    analyze_email,
    load_icp,
)


def test_load_icp_found():
    icp_content = "# ICP test\n## HAUTE\nDevis client"
    with patch("builtins.open", mock_open(read_data=icp_content)):
        result = load_icp("agence_conseil")
    assert result == icp_content


def test_load_icp_not_found():
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = load_icp("inexistant")
    assert result == ""


def test_build_system_prompt_with_icp():
    icp = "## BASSE\nNewsletter → inutile"
    result = _build_system_prompt(icp)
    assert result.startswith(SYSTEM_BASE)
    assert icp in result


def test_build_system_prompt_without_icp():
    result = _build_system_prompt("")
    assert result == SYSTEM_BASE
    assert "\n\n" not in result


def test_analyze_email_icp_injected_as_system():
    """ICP context must be passed via system= parameter, not in the user message."""
    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(
            text='{"priority":"basse","category":"inutile",'
            '"summary":"Notif LinkedIn","action":null,"suggested_reply":null}'
        )
    ]
    email = {
        "from": "noreply@linkedin.com",
        "subject": "Nouvelle connexion",
        "date": "2026-05-13",
        "body": "Quelqu'un veut vous ajouter.",
    }
    icp_context = "## BASSE\nNotification automatique → inutile"

    with patch("apps.email_agent.analyzer.client") as mock_client:
        mock_client.messages.create.return_value = fake_response
        analyze_email(email, icp_context)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" in call_kwargs
    assert icp_context in call_kwargs["system"]
    # ICP must NOT appear inside the user message content
    user_content = call_kwargs["messages"][0]["content"]
    assert icp_context not in user_content


def test_analyze_email_no_icp_uses_base_system():
    """With no ICP, system prompt must still be set to SYSTEM_BASE."""
    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(
            text='{"priority":"haute","category":"action_requise",'
            '"summary":"Devis demande","action":"Envoyer devis","suggested_reply":null}'
        )
    ]
    email = {
        "from": "client@example.com",
        "subject": "Demande de devis",
        "date": "2026-05-13",
        "body": "Bonjour, nous souhaitons un devis.",
    }

    with patch("apps.email_agent.analyzer.client") as mock_client:
        mock_client.messages.create.return_value = fake_response
        analyze_email(email, icp_context="")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == SYSTEM_BASE


if __name__ == "__main__":
    test_load_icp_found()
    test_load_icp_not_found()
    test_build_system_prompt_with_icp()
    test_build_system_prompt_without_icp()
    test_analyze_email_icp_injected_as_system()
    test_analyze_email_no_icp_uses_base_system()
    print()
    print("6/6 tests passes !")

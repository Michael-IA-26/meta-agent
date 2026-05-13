import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import httpx

from apps.leadcommercial.pappers_client import _parse_enrichment, fetch_enrichment


def test_fetch_enrichment_no_api_key():
    with patch("apps.leadcommercial.pappers_client.PAPPERS_API_KEY", ""):
        result = fetch_enrichment("123456789")
    assert result["dirigeant_nom"] == ""
    assert result["dirigeant_prenom"] == ""
    assert result["dirigeant_email"] == ""
    assert result["site_web"] == ""
    assert result["capital_social"] is None


def test_fetch_enrichment_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"
    with (
        patch("apps.leadcommercial.pappers_client.PAPPERS_API_KEY", "test_key"),
        patch("apps.leadcommercial.pappers_client.httpx.get") as mock_get,
    ):
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )
        result = fetch_enrichment("123456789")
    assert result["dirigeant_nom"] == ""
    assert result["capital_social"] is None


def test_fetch_enrichment_request_error():
    with (
        patch("apps.leadcommercial.pappers_client.PAPPERS_API_KEY", "test_key"),
        patch("apps.leadcommercial.pappers_client.httpx.get") as mock_get,
    ):
        mock_get.side_effect = httpx.RequestError("timeout", request=MagicMock())
        result = fetch_enrichment("123456789")
    assert result["site_web"] == ""
    assert result["capital_social"] is None


def test_fetch_enrichment_success():
    fake_data = {
        "dirigeants": [
            {"nom": "DUPONT", "prenom": "Jean", "email": "jean@example.com"}
        ],
        "site_web": "https://example.com",
        "capital": 10000,
    }
    with (
        patch("apps.leadcommercial.pappers_client.PAPPERS_API_KEY", "test_key"),
        patch("apps.leadcommercial.pappers_client.httpx.get") as mock_get,
    ):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = fake_data
        result = fetch_enrichment("123456789")
    assert result["dirigeant_nom"] == "DUPONT"
    assert result["dirigeant_prenom"] == "Jean"
    assert result["dirigeant_email"] == "jean@example.com"
    assert result["site_web"] == "https://example.com"
    assert result["capital_social"] == 10000


def test_parse_enrichment_no_dirigeant():
    data = {"dirigeants": [], "site_web": "", "capital": None}
    result = _parse_enrichment(data)
    assert result["dirigeant_nom"] == ""
    assert result["dirigeant_prenom"] == ""
    assert result["capital_social"] is None


def test_parse_enrichment_no_email():
    data = {
        "dirigeants": [{"nom": "MARTIN", "prenom": "Paul"}],
        "site_web": "https://martin.fr",
        "capital": 5000,
    }
    result = _parse_enrichment(data)
    assert result["dirigeant_nom"] == "MARTIN"
    assert result["dirigeant_prenom"] == "Paul"
    assert result["dirigeant_email"] == ""
    assert result["site_web"] == "https://martin.fr"
    assert result["capital_social"] == 5000


if __name__ == "__main__":
    test_fetch_enrichment_no_api_key()
    test_fetch_enrichment_http_error()
    test_fetch_enrichment_request_error()
    test_fetch_enrichment_success()
    test_parse_enrichment_no_dirigeant()
    test_parse_enrichment_no_email()
    print()
    print("6/6 tests passes !")

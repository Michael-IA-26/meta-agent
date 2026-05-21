"""Tests for apps.leadcommercial.agents.sirene_fetcher."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.agents.sirene_fetcher import SireneInput, fetch_idf_companies


def test_fetch_idf_companies_returns_companies():
    fake = [{"siren": "123456789", "denomination": "TEST SAS", "dept": "75"}]
    with patch(
        "apps.leadcommercial.agents.sirene_fetcher.fetch_and_parse_idf",
        return_value=fake,
    ) as mock:
        result = fetch_idf_companies(SireneInput(max_results=10, date=None))
    mock.assert_called_once_with(max_results=10, date=None)
    assert result == fake


def test_fetch_idf_companies_passes_date():
    with patch(
        "apps.leadcommercial.agents.sirene_fetcher.fetch_and_parse_idf",
        return_value=[],
    ) as mock:
        fetch_idf_companies(SireneInput(max_results=5, date="2026-05-01"))
    mock.assert_called_once_with(max_results=5, date="2026-05-01")


def test_fetch_idf_companies_empty_result():
    with patch(
        "apps.leadcommercial.agents.sirene_fetcher.fetch_and_parse_idf",
        return_value=[],
    ):
        result = fetch_idf_companies(SireneInput(max_results=100, date=None))
    assert result == []


def test_fetch_idf_companies_raises_on_missing_token():
    with patch(
        "apps.leadcommercial.agents.sirene_fetcher.fetch_and_parse_idf",
        side_effect=ValueError("SIRENE_API_TOKEN manquant"),
    ):
        try:
            fetch_idf_companies(SireneInput(max_results=10, date=None))
            assert False, "should have raised ValueError"
        except ValueError as exc:
            assert "SIRENE_API_TOKEN" in str(exc)

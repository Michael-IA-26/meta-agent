"""Tests for apps.leadcommercial.agents.pappers_enricher."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.agents.pappers_enricher import EnrichInput, enrich_lead


def test_enrich_lead_returns_enrichment():
    fake = {
        "dirigeant_nom": "DUPONT",
        "dirigeant_prenom": "Jean",
        "dirigeant_email": "jean@test.com",
        "site_web": "https://test.com",
        "capital_social": 10000,
    }
    with patch(
        "apps.leadcommercial.agents.pappers_enricher.fetch_enrichment",
        return_value=fake,
    ) as mock:
        result = enrich_lead(EnrichInput(siren="123456789"))
    mock.assert_called_once_with("123456789")
    assert result == fake


def test_enrich_lead_empty_on_missing_key():
    empty = {
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }
    with patch(
        "apps.leadcommercial.agents.pappers_enricher.fetch_enrichment",
        return_value=empty,
    ):
        result = enrich_lead(EnrichInput(siren="999999999"))
    assert result["capital_social"] is None
    assert result["dirigeant_nom"] == ""


def test_enrich_lead_passes_siren():
    with patch(
        "apps.leadcommercial.agents.pappers_enricher.fetch_enrichment",
        return_value={
            "dirigeant_nom": "",
            "dirigeant_prenom": "",
            "dirigeant_email": "",
            "site_web": "",
            "capital_social": None,
        },
    ) as mock:
        enrich_lead(EnrichInput(siren="111222333"))
    mock.assert_called_once_with("111222333")

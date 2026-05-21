"""Tests for apps.leadcommercial.agents.supabase_writer (LeadCommercial)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.agents.supabase_writer import WriteInput, write_lead


def _write_input(**overrides) -> WriteInput:
    base = WriteInput(
        siren="123456789",
        denomination="TEST SAS",
        forme_juridique="5710",
        code_naf="70.22Z",
        commune="PARIS",
        dept="75",
        date_creation="2026-05-01",
        score=80,
        signal_type="creation",
        dirigeant_nom="DUPONT",
        dirigeant_prenom="Jean",
        dirigeant_email="",
        site_web="",
        capital_social=None,
    )
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_write_lead_returns_true_when_persisted():
    with patch(
        "apps.leadcommercial.agents.supabase_writer.persist_lead", return_value=True
    ) as mock:
        result = write_lead(_write_input())
    mock.assert_called_once()
    assert result is True


def test_write_lead_returns_false_when_locked():
    with patch(
        "apps.leadcommercial.agents.supabase_writer.persist_lead", return_value=False
    ):
        result = write_lead(_write_input())
    assert result is False


def test_write_lead_passes_dict_to_persist():
    with patch(
        "apps.leadcommercial.agents.supabase_writer.persist_lead", return_value=True
    ) as mock:
        write_lead(_write_input(siren="999888777"))
    called_dict = mock.call_args.args[0]
    assert called_dict["siren"] == "999888777"
    assert called_dict["denomination"] == "TEST SAS"


def test_write_lead_no_siren_returns_false():
    with patch(
        "apps.leadcommercial.agents.supabase_writer.persist_lead", return_value=False
    ):
        result = write_lead(_write_input(siren=None))
    assert result is False

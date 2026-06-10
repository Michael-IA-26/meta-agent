"""Tests TDD — echeance_agent."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.echeance_agent import (
    _priorite,
    build_rapport,
    run,
)


def _acompte(offset: int) -> dict:
    return {
        "id": f"a-{offset}",
        "dossier_id": "d-1",
        "contact_id": "c-1",
        "numero_acompte": 1,
        "exercice": "2026",
        "deadline": (date.today() + timedelta(days=offset)).isoformat(),
        "montant": 5000.0,
        "statut": "a_payer",
    }


def _tva_decl(offset: int) -> dict:
    return {
        "id": f"t-{offset}",
        "dossier_id": "d-1",
        "contact_id": "c-1",
        "periode": "2026-05",
        "deadline": (date.today() + timedelta(days=offset)).isoformat(),
        "statut": "a_preparer",
    }


# ── _priorite ──────────────────────────────────────────────────────────────────


def test_priorite_rouge_pour_3_jours_ou_moins():
    assert _priorite(3) == "rouge"
    assert _priorite(1) == "rouge"
    assert _priorite(0) == "rouge"


def test_priorite_orange_entre_4_et_7():
    assert _priorite(7) == "orange"
    assert _priorite(4) == "orange"


def test_priorite_vert_au_dela_de_7():
    assert _priorite(8) == "vert"
    assert _priorite(30) == "vert"


# ── build_rapport ──────────────────────────────────────────────────────────────


def test_build_rapport_contient_date_du_jour():
    rapport = build_rapport([])
    assert date.today().isoformat() in rapport


def test_build_rapport_echeance_rouge_apparait():
    echeance = {
        "type": "is",
        "contact_id": "c-1",
        "contact_nom": "SARL Dupont",
        "dossier_id": "d-1",
        "reference": "Acompte IS n°1 2026",
        "deadline": (date.today() + timedelta(days=2)).isoformat(),
        "jours_restants": 2,
        "priorite": "rouge",
        "montant": 3000.0,
        "statut": "a_payer",
    }
    rapport = build_rapport([echeance])
    assert "SARL Dupont" in rapport
    assert "URGENT" in rapport


# ── run() ──────────────────────────────────────────────────────────────────────


def test_run_aucune_echeance_rapport_non_envoye(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram") as mock_tg,
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport") as mock_mail,
    ):
        result = run(dry_run=False)

    mock_tg.assert_not_called()
    mock_mail.assert_not_called()
    assert result["echeances_total"] == 0
    assert result["rapport_envoye"] is False


def test_run_echeance_trouvee_rapport_envoye(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(5)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value="SARL Dupont"),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=True),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        result = run(dry_run=False)

    assert result["echeances_total"] == 1
    assert result["rapport_envoye"] is True


def test_run_dry_run_nenvoie_rien(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(5)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value="SARL Test"),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram") as mock_tg,
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport") as mock_mail,
    ):
        result = run(dry_run=True)

    mock_tg.assert_not_called()
    mock_mail.assert_not_called()
    assert result["rapport_envoye"] is False


def test_run_tri_par_jours_restants(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(20), _acompte(2), _acompte(8)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value=None),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=True),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        result = run(dry_run=False)

    jours = [e["jours_restants"] for e in result["echeances"]]
    assert jours == sorted(jours)


def test_run_compte_rouge_orange_vert(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(2), _acompte(5), _acompte(20)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value=None),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=True),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        result = run(dry_run=False)

    assert result["rouge"] == 1
    assert result["orange"] == 1
    assert result["vert"] == 1


def test_run_structure_resultat(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
    ):
        result = run(dry_run=True)

    assert set(result.keys()) == {
        "echeances_total", "rouge", "orange", "vert",
        "rapport_envoye", "echeances", "erreurs",
    }


# ── erreurs réseau ─────────────────────────────────────────────────────────────


def test_telegram_down_email_ok_rapport_envoye(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(5)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value=None),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=True),
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        result = run(dry_run=False)

    assert result["rapport_envoye"] is True


def test_telegram_et_email_down_rapport_non_envoye(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(5)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva", return_value=[]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value=None),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=False),
    ):
        result = run(dry_run=False)

    assert result["rapport_envoye"] is False
    assert result["erreurs"] == []


def test_acomptes_is_et_tva_combines(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    with (
        patch("apps.jmpartners.agents.echeance_agent.get_supabase_client"),
        patch("apps.jmpartners.agents.echeance_agent.fetch_acomptes_is",
              return_value=[_acompte(10)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_declarations_tva",
              return_value=[_tva_decl(15)]),
        patch("apps.jmpartners.agents.echeance_agent.fetch_contact_nom", return_value=None),
        patch("apps.jmpartners.agents.echeance_agent.send_telegram", return_value=False),
        patch("apps.jmpartners.agents.echeance_agent.send_email_rapport", return_value=True),
        patch("apps.jmpartners.agents.echeance_agent.log_alerte_echeances"),
    ):
        result = run(dry_run=False)

    assert result["echeances_total"] == 2
    types = [e["type"] for e in result["echeances"]]
    assert "is" in types
    assert "tva" in types

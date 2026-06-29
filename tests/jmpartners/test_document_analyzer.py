"""TDD — document_analyzer : extraction IA depuis PDF/image via Claude Sonnet 4.6."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ── Fixtures / helpers ────────────────────────────────────────────────────────

FAKE_PDF = b"%PDF-1.4 fake pdf content"
FAKE_JPEG = b"\xff\xd8\xff\xe0 fake jpeg"
FAKE_PNG = b"\x89PNG\r\n fake png"


def _fake_http_response(content: bytes, content_type: str = "application/pdf") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.headers = {"content-type": content_type}
    resp.raise_for_status = MagicMock()
    return resp


def _fake_anthropic_client(analyse_dict: dict) -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(analyse_dict))]
    client.messages.create.return_value = msg
    return client


def _fake_supabase() -> MagicMock:
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "doc-1", "statut": "analysé"}
    ]
    return sb


# ── Données de test pour chaque type de document ──────────────────────────────

_ANALYSES: dict[str, dict] = {
    "facture_achat": {
        "type_document": "facture_achat",
        "montants": [{"libelle": "Total TTC", "montant": 1200.0, "devise": "EUR"}],
        "dates": ["2026-05-15"],
        "tiers": ["Fournisseur SAS"],
        "references": ["FA-2026-0542"],
        "tva": {"taux": 20, "montant_ht": 1000.0, "montant_tva": 200.0, "montant_ttc": 1200.0},
        "resume": "Facture fournisseur 1200€ TTC du 15/05/2026",
    },
    "facture_vente": {
        "type_document": "facture_vente",
        "montants": [{"libelle": "Total TTC", "montant": 2400.0, "devise": "EUR"}],
        "dates": ["2026-05-20"],
        "tiers": ["Client Dupont SARL"],
        "references": ["FV-2026-0123"],
        "tva": {"taux": 20, "montant_ht": 2000.0, "montant_tva": 400.0, "montant_ttc": 2400.0},
        "resume": "Facture vente 2400€ TTC du 20/05/2026",
    },
    "releve_bancaire": {
        "type_document": "releve_bancaire",
        "montants": [{"libelle": "Solde final", "montant": 15230.50, "devise": "EUR"}],
        "dates": ["2026-05-01", "2026-05-31"],
        "tiers": ["BNP Paribas"],
        "references": ["IBAN FR76 1234 5678 9012 3456"],
        "tva": None,
        "resume": "Relevé bancaire mai 2026, solde 15230.50€",
    },
    "grand_livre": {
        "type_document": "grand_livre",
        "montants": [{"libelle": "Total débits", "montant": 85000.0, "devise": "EUR"}],
        "dates": ["2026-01-01", "2026-05-31"],
        "tiers": [],
        "references": ["GL-2026"],
        "tva": None,
        "resume": "Grand livre jan-mai 2026",
    },
    "balance": {
        "type_document": "balance",
        "montants": [{"libelle": "Total balance", "montant": 120000.0, "devise": "EUR"}],
        "dates": ["2026-05-31"],
        "tiers": [],
        "references": ["BAL-2026-05"],
        "tva": None,
        "resume": "Balance au 31/05/2026",
    },
    "bilan_n_1": {
        "type_document": "bilan_n_1",
        "montants": [{"libelle": "Total actif", "montant": 250000.0, "devise": "EUR"}],
        "dates": ["2025-12-31"],
        "tiers": [],
        "references": ["BILAN-2025"],
        "tva": None,
        "resume": "Bilan clôture 31/12/2025, total actif 250000€",
    },
    "resultat_comptable": {
        "type_document": "resultat_comptable",
        "montants": [{"libelle": "Résultat net", "montant": 45000.0, "devise": "EUR"}],
        "dates": ["2025-12-31"],
        "tiers": [],
        "references": ["RES-2025"],
        "tva": None,
        "resume": "Résultat net 2025 : 45000€",
    },
    "liasse_fiscale": {
        "type_document": "liasse_fiscale",
        "montants": [{"libelle": "IS dû", "montant": 12000.0, "devise": "EUR"}],
        "dates": ["2025-12-31"],
        "tiers": ["Direction Générale des Finances Publiques"],
        "references": ["2065-SD"],
        "tva": None,
        "resume": "Liasse fiscale 2025, IS 12000€",
    },
    "bulletin_salaire": {
        "type_document": "bulletin_salaire",
        "montants": [{"libelle": "Net à payer", "montant": 2850.0, "devise": "EUR"}],
        "dates": ["2026-05-31"],
        "tiers": ["Jean Dupont"],
        "references": ["BS-2026-05-001"],
        "tva": None,
        "resume": "Bulletin salaire mai 2026, net 2850€",
    },
    "contrat_travail": {
        "type_document": "contrat_travail",
        "montants": [{"libelle": "Salaire brut", "montant": 3500.0, "devise": "EUR"}],
        "dates": ["2026-01-15"],
        "tiers": ["Jean Dupont"],
        "references": ["CDI-2026-01"],
        "tva": None,
        "resume": "CDI signé le 15/01/2026, salaire brut 3500€",
    },
}


# ── Tests : détection du type MIME ────────────────────────────────────────────

def test_detect_media_type_pdf():
    from apps.jmpartners.agents.document_analyzer import _detect_media_type
    assert _detect_media_type("https://storage.supabase.co/doc.pdf", None) == "application/pdf"


def test_detect_media_type_jpeg():
    from apps.jmpartners.agents.document_analyzer import _detect_media_type
    assert _detect_media_type("https://storage.supabase.co/scan.jpg", None) == "image/jpeg"


def test_detect_media_type_png():
    from apps.jmpartners.agents.document_analyzer import _detect_media_type
    assert _detect_media_type("https://storage.supabase.co/doc.png", None) == "image/png"


def test_detect_media_type_from_content_type_header():
    from apps.jmpartners.agents.document_analyzer import _detect_media_type
    # Content-Type header overrides URL extension
    assert _detect_media_type("https://storage.supabase.co/doc", "image/jpeg") == "image/jpeg"


def test_detect_media_type_unknown_defaults_to_pdf():
    from apps.jmpartners.agents.document_analyzer import _detect_media_type
    assert _detect_media_type("https://storage.supabase.co/doc.xyz", None) == "application/pdf"


# ── Tests : extraction pour les 10 types de documents ─────────────────────────

@pytest.mark.parametrize("type_document", list(_ANALYSES.keys()))
def test_run_extraction_all_document_types(monkeypatch, type_document):
    """run() extrait les données correctement pour chacun des 10 types de documents."""
    from apps.jmpartners.agents import document_analyzer as mod

    analyse = _ANALYSES[type_document]
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(analyse)
    mock_resp = _fake_http_response(FAKE_PDF, "application/pdf")

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-1", "https://storage.supabase.co/doc.pdf", type_document)

    assert result["statut"] == "analysé"
    assert result["erreur"] is None
    assert result["analyse"] is not None
    assert result["analyse"]["type_document"] == type_document
    assert result["analyse"]["resume"] == analyse["resume"]
    assert result["document_id"] == "doc-1"


# ── Tests : stockage du résultat en base ──────────────────────────────────────

def test_run_stores_analyse_ia_in_documents(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(_ANALYSES["facture_achat"])
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        mod.run("doc-42", "https://storage.supabase.co/facture.pdf", "facture_achat")

    mock_sb.table.assert_called_with("documents")
    update_call = mock_sb.table.return_value.update
    update_call.assert_called_once()
    payload = update_call.call_args[0][0]
    assert "analyse_ia" in payload
    assert "statut" in payload
    assert payload["statut"] == "analysé"


def test_run_stores_correct_analyse_ia_content(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    analyse = _ANALYSES["facture_vente"]
    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(analyse)
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-2", "https://storage.supabase.co/fv.pdf", "facture_vente")

    assert result["analyse"]["tiers"] == ["Client Dupont SARL"]
    assert result["analyse"]["references"] == ["FV-2026-0123"]
    assert result["analyse"]["tva"]["montant_ttc"] == 2400.0


# ── Tests : fallback sur timeout Claude ───────────────────────────────────────

def test_run_fallback_on_claude_timeout(monkeypatch):
    import anthropic

    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = MagicMock()
    mock_ai.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-3", "https://storage.supabase.co/doc.pdf", "facture_achat")

    assert result["statut"] == "erreur"
    assert result["analyse"] is None
    assert "timeout" in (result["erreur"] or "").lower()


def test_run_fallback_on_claude_api_error(monkeypatch):
    import anthropic

    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = MagicMock()
    mock_ai.messages.create.side_effect = anthropic.APIError(
        message="service overloaded", request=MagicMock(), body={}
    )
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-4", "https://storage.supabase.co/doc.pdf", "facture_achat")

    assert result["statut"] == "erreur"
    assert result["analyse"] is None


# ── Tests : erreur de téléchargement ─────────────────────────────────────────

def test_run_fallback_on_download_error(monkeypatch):
    import httpx

    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch("httpx.get", side_effect=httpx.RequestError("connection refused", request=MagicMock())),
    ):
        result = mod.run("doc-5", "https://storage.supabase.co/doc.pdf", "facture_achat")

    assert result["statut"] == "erreur"
    assert result["analyse"] is None
    assert result["erreur"] is not None


# ── Tests : dry_run ───────────────────────────────────────────────────────────

def test_run_dry_run_skips_supabase_update(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(_ANALYSES["grand_livre"])
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run(
            "doc-6", "https://storage.supabase.co/gl.pdf", "grand_livre", dry_run=True
        )

    assert result["statut"] == "analysé"
    mock_sb.table.return_value.update.assert_not_called()


# ── Tests : structure AnalyseIA complète ──────────────────────────────────────

def test_run_returns_complete_analyse_ia_structure(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(_ANALYSES["releve_bancaire"])
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-7", "https://storage.supabase.co/releve.pdf", "releve_bancaire")

    analyse = result["analyse"]
    assert analyse is not None
    for field in ("type_document", "montants", "dates", "tiers", "references", "tva", "resume"):
        assert field in analyse, f"Champ manquant dans AnalyseIA : {field}"
    assert isinstance(analyse["montants"], list)
    assert isinstance(analyse["dates"], list)
    assert isinstance(analyse["tiers"], list)
    assert isinstance(analyse["references"], list)


# ── Tests : le prompt Claude inclut le type de document ───────────────────────

def test_run_claude_prompt_includes_document_type(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    mock_sb = _fake_supabase()
    mock_ai = _fake_anthropic_client(_ANALYSES["liasse_fiscale"])
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "get_anthropic_client", return_value=mock_ai),
        patch("httpx.get", return_value=mock_resp),
    ):
        mod.run("doc-8", "https://storage.supabase.co/lf.pdf", "liasse_fiscale")

    call_kwargs = mock_ai.messages.create.call_args
    messages = call_kwargs[1].get("messages") or call_kwargs[0][1]
    user_text = str(messages)
    assert "liasse_fiscale" in user_text


# ── Tests : pas d'erreur si ANTHROPIC_API_KEY absente ─────────────────────────

def test_run_returns_error_if_anthropic_key_missing(monkeypatch):
    from apps.jmpartners.agents import document_analyzer as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    mock_sb = _fake_supabase()
    mock_resp = _fake_http_response(FAKE_PDF)

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = mod.run("doc-9", "https://storage.supabase.co/doc.pdf", "facture_achat")

    assert result["statut"] == "erreur"
    assert result["analyse"] is None

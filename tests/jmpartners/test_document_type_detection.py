"""TDD — document type detection before analysis. Tests written first (red)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.document_analyzer import classify_document
from apps.jmpartners.orchestrator import _process_documents

# ── classify_document ─────────────────────────────────────────────────────────

def _mock_claude(type_str: str):
    """Return a mock Anthropic client whose message returns a type JSON."""
    client = MagicMock()
    block = MagicMock()
    block.text = f'{{"type": "{type_str}"}}'
    client.messages.create.return_value.content = [block]
    return client


def test_classify_facture_achat(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=_mock_claude("facture_achat")):
        result = classify_document("facture_fournisseur.pdf", "Fournisseur SARL facture 1200€")
    assert result == "facture_achat"


def test_classify_facture_vente(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=_mock_claude("facture_vente")):
        result = classify_document("facture_client.pdf", "Client SA vente 2400€")
    assert result == "facture_vente"


def test_classify_releve_bancaire(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=_mock_claude("releve_bancaire")):
        result = classify_document("releve_mai.pdf", "Solde IBAN BNP")
    assert result == "releve_bancaire"


def test_classify_autre_on_unknown_type(monkeypatch):
    """Unknown type returned by Claude → 'autre'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=_mock_claude("contrat_location")):
        result = classify_document("contrat.pdf", "Location appartement")
    assert result == "autre"


def test_classify_autre_on_ambiguous_empty(monkeypatch):
    """Empty / whitespace text → 'autre', no raise."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=_mock_claude("autre")):
        result = classify_document("doc.pdf", "")
    assert result == "autre"


def test_classify_never_raises_on_exception(monkeypatch):
    """Claude exception → fallback 'autre', no propagation."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("API down")
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=client):
        result = classify_document("x.pdf", "some text")
    assert result == "autre"


def test_classify_never_raises_on_bad_json(monkeypatch):
    """Non-JSON response → fallback 'autre'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = MagicMock()
    block = MagicMock()
    block.text = "not json at all"
    client.messages.create.return_value.content = [block]
    with patch("apps.jmpartners.agents.document_analyzer.get_anthropic_client",
               return_value=client):
        result = classify_document("x.pdf", "some text")
    assert result == "autre"


# ── _process_documents with type detection ────────────────────────────────────

def _sb_with_docs(docs):
    sb = MagicMock()
    sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = docs
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    return sb


def test_process_documents_classifies_and_persists_before_analysis():
    """recu doc with no type_document → classify → persist type → then analyze."""
    doc = {"id": "doc-1", "url": "https://x/doc.pdf", "type_document": None, "statut": "recu",
           "nom": "facture.pdf"}
    sb = _sb_with_docs([doc])

    call_order = []

    with (
        patch("apps.jmpartners.orchestrator.classify_document",
              side_effect=lambda *a, **kw: call_order.append("classify") or "facture_achat") as mock_cls,
        patch("apps.jmpartners.orchestrator.run_document_analyzer",
              side_effect=lambda *a, **kw: call_order.append("analyze")) as mock_ana,
        patch("apps.jmpartners.orchestrator.run_ecriture_generator"),
    ):
        _process_documents(sb, dry_run=False)

    mock_cls.assert_called_once()
    mock_ana.assert_called_once()
    # classify must happen before analyze
    assert call_order.index("classify") < call_order.index("analyze")
    # type_document persisted before analysis
    update_calls = [str(c) for c in sb.table.return_value.update.call_args_list]
    assert any("facture_achat" in c for c in update_calls)


def test_process_documents_persists_type_before_analyzer_called():
    """DB update of type_document must precede run_document_analyzer invocation."""
    doc = {"id": "doc-1", "url": "u", "type_document": "", "statut": "recu", "nom": "f.pdf"}
    sb = _sb_with_docs([doc])

    sequence = []
    sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = (
        lambda: sequence.append("db_update")
    )

    with (
        patch("apps.jmpartners.orchestrator.classify_document", return_value="facture_vente"),
        patch("apps.jmpartners.orchestrator.run_document_analyzer",
              side_effect=lambda *a, **kw: sequence.append("analyze")),
        patch("apps.jmpartners.orchestrator.run_ecriture_generator"),
    ):
        _process_documents(sb, dry_run=False)

    # First update is type_document persistence; analyze follows
    assert sequence.index("db_update") < sequence.index("analyze")


def test_process_documents_skips_classification_when_type_exists():
    """recu doc with existing type_document is NOT re-classified."""
    doc = {"id": "doc-2", "url": "u", "type_document": "facture_achat", "statut": "recu",
           "nom": "f.pdf"}
    sb = _sb_with_docs([doc])

    with (
        patch("apps.jmpartners.orchestrator.classify_document") as mock_cls,
        patch("apps.jmpartners.orchestrator.run_document_analyzer"),
        patch("apps.jmpartners.orchestrator.run_ecriture_generator"),
    ):
        _process_documents(sb, dry_run=False)

    mock_cls.assert_not_called()


def test_process_documents_dry_run_no_classify_no_writes():
    """dry_run=True → no classify, no DB writes, no analyzer."""
    doc = {"id": "doc-3", "url": "u", "type_document": None, "statut": "recu", "nom": "f.pdf"}
    sb = _sb_with_docs([doc])

    with (
        patch("apps.jmpartners.orchestrator.classify_document") as mock_cls,
        patch("apps.jmpartners.orchestrator.run_document_analyzer") as mock_ana,
        patch("apps.jmpartners.orchestrator.run_ecriture_generator"),
    ):
        _process_documents(sb, dry_run=True)

    mock_cls.assert_not_called()
    mock_ana.assert_not_called()
    sb.table.return_value.update.assert_not_called()

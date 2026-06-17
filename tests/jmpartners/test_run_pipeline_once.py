import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.scripts.run_pipeline_once import build_document_row, run


def test_document_row_builder_sets_statut_recu():
    row = build_document_row(
        url="storage://documents/test.pdf", dossier_id="dossier-123"
    )
    assert row["statut"] == "recu"
    assert row["dossier_id"] == "dossier-123"
    assert row["url"] == "storage://documents/test.pdf"


def test_run_without_confirm_exits_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        run(file_path="test.pdf", dossier_id="d-123", confirm=False)
    assert exc_info.value.code != 0


def test_process_documents_wired_with_mocks(tmp_path):
    test_file = tmp_path / "doc.pdf"
    test_file.write_bytes(b"%PDF-1.4")
    mock_client = MagicMock()
    mock_client.storage.from_.return_value.upload.return_value = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "doc-id-1", "analyse_ia": None}]
    )
    mock_orch = MagicMock()
    mock_orch._process_documents.return_value = {
        "analyse_ia": "Facture fournisseur",
        "ecritures": [],
    }
    with (
        patch(
            "apps.jmpartners.scripts.run_pipeline_once.create_supabase_client",
            return_value=mock_client,
        ),
        patch(
            "apps.jmpartners.scripts.run_pipeline_once.Orchestrator",
            return_value=mock_orch,
        ),
        patch.dict(
            os.environ,
            {
                "SUPABASE_SERVICE_KEY": "fake",
                "SUPABASE_URL": "https://x.supabase.co",
                "ANTHROPIC_API_KEY": "fake",
            },
        ),
    ):
        run(file_path=str(test_file), dossier_id="d-123", confirm=True)
    mock_orch._process_documents.assert_called_once()

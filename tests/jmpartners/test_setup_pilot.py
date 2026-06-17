import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from unittest.mock import MagicMock

import pytest

from apps.jmpartners.scripts.setup_pilot import build_pilot_rows, ensure_buckets, run


def test_ensure_buckets_creates_when_absent():
    storage = MagicMock()
    storage.list_buckets.return_value = []
    ensure_buckets(storage)
    created = [c.args[0] for c in storage.create_bucket.call_args_list]
    assert "documents" in created
    assert "exports" in created


def test_ensure_buckets_skips_when_existing():
    storage = MagicMock()
    doc, exp = MagicMock(), MagicMock()
    doc.name, exp.name = "documents", "exports"
    storage.list_buckets.return_value = [doc, exp]
    ensure_buckets(storage)
    storage.create_bucket.assert_not_called()


def test_build_pilot_rows_structure():
    contact, dossier = build_pilot_rows("Dossier Test", "client@example.com")
    assert contact["email"] == "client@example.com"
    assert dossier["statut"] == "en_cours"
    assert dossier["contact_id"] == contact["id"]


def test_run_without_confirm_exits_nonzero():
    with pytest.raises(SystemExit) as exc_info:
        run("Test Dossier", "client@example.com", confirm=False)
    assert exc_info.value.code != 0

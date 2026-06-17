import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from unittest.mock import MagicMock, patch

from apps.jmpartners.scripts.sage_exporter import (
    SAGE_COLUMNS,
    build_export_rows,
    export_dossier,
)

SAMPLE_ECRITURE = {
    "date_ecriture": "2024-01-15",
    "libelle": "Facture test",
    "compte_debit": "411000",
    "compte_credit": "706000",
    "montant": 500.0,
    "tiers": "TEST SAS",
    "journal": "VEN",
    "reference": "FAC-002",
    "statut": "valide",
}


def _mock_client(data):
    client = MagicMock()
    (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.like.return_value.execute.return_value
    ) = MagicMock(data=data)
    return client


def test_sage_columns_constant():
    assert SAGE_COLUMNS == [
        "journal",
        "date",
        "compte",
        "libelle",
        "debit",
        "credit",
        "piece",
        "tiers",
    ]


def test_build_export_rows_filters_valide():
    client = _mock_client([SAMPLE_ECRITURE])
    rows = build_export_rows("dossier-1", "2024-01", client)
    client.table.assert_called_with("ecritures")
    assert len(rows) == 2


def test_ecriture_generates_two_rows():
    client = _mock_client([SAMPLE_ECRITURE])
    rows = build_export_rows("dossier-1", "2024-01", client)
    assert len(rows) == 2
    debit_row, credit_row = rows[0], rows[1]
    assert debit_row["compte"] == "411000"
    assert debit_row["debit"] == 500.0
    assert debit_row["credit"] == ""
    assert credit_row["compte"] == "706000"
    assert credit_row["credit"] == 500.0
    assert credit_row["debit"] == ""


def test_empty_set_not_exported():
    client = _mock_client([])
    rows = build_export_rows("dossier-1", "2024-01", client)
    assert rows == []
    with patch(
        "apps.jmpartners.scripts.sage_exporter.build_export_rows", return_value=[]
    ):
        result = export_dossier("dossier-1", "2024-01", client)
    assert result["exported"] is False

"""Sage export: convert validated ecritures into an xlsx file for import."""

from __future__ import annotations

import io
import logging

import openpyxl

logger = logging.getLogger(__name__)

# TODO: confirm exact Sage import layout with cabinet
SAGE_COLUMNS = [
    "journal",
    "date",
    "compte",
    "libelle",
    "debit",
    "credit",
    "piece",
    "tiers",
]


def build_export_rows(dossier_id: str, periode: str, client) -> list[dict]:
    """Return double-entry rows for all validated ecritures in the period."""
    result = (
        client.table("ecritures")
        .select("*")
        .eq("dossier_id", dossier_id)
        .eq("statut", "valide")
        .like("date_ecriture", f"{periode}%")
        .execute()
    )
    rows: list[dict] = []
    for e in result.data:
        base = {
            "journal": e["journal"],
            "date": e["date_ecriture"],
            "libelle": e["libelle"],
            "piece": e.get("reference", ""),
            "tiers": e.get("tiers", ""),
        }
        rows.append(
            {**base, "compte": e["compte_debit"], "debit": e["montant"], "credit": ""}
        )
        rows.append(
            {**base, "compte": e["compte_credit"], "debit": "", "credit": e["montant"]}
        )
    return rows


def export_dossier(dossier_id: str, periode: str, client) -> dict:
    """Export ecritures to xlsx and upload to storage, or report nothing to export."""
    rows = build_export_rows(dossier_id, periode, client)
    if not rows:
        logger.info("No validated ecritures for %s / %s", dossier_id, periode)
        return {"exported": False}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(SAGE_COLUMNS)
    for row in rows:
        ws.append([row.get(col, "") for col in SAGE_COLUMNS])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"sage_{dossier_id}_{periode}.xlsx"
    client.storage.from_("exports").upload(filename, buf.read())

    client.table("journal_events").insert(
        {"dossier_id": dossier_id, "journal": "sage_saisie", "filename": filename}
    ).execute()

    return {"exported": True, "filename": filename}

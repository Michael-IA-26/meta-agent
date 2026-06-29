"""Agent tva_declarator — génération de la déclaration TVA CA3.

Agrège les écritures comptables des comptes 44x (TVA collectée/déductible),
calcule les lignes CA3 standard, génère un PDF via ReportLab (optionnel),
stocke dans Supabase Storage, et met à jour declarations_tva.statut='generée'.
"""

from __future__ import annotations

import calendar
import logging
import os
from typing import TypedDict

__all__ = [
    "CA3Lignes",
    "TvaDeclaratorResult",
    "_compute_ca3_lignes",
    "_generate_pdf_ca3",
    "get_supabase_client",
    "run",
]

logger = logging.getLogger(__name__)


class CA3Lignes(TypedDict):
    """Montants agrégés pour la déclaration CA3."""

    ca_ht: float          # Chiffre d'affaires HT (comptes 70x)
    tva_collectee: float  # TVA collectée (44571)
    tva_deductible: float # TVA déductible (44566)
    solde: float          # tva_collectee - tva_deductible
    credit_tva: float     # abs(solde) si solde < 0, sinon 0


class TvaDeclaratorResult(TypedDict):
    declaration_id: str | None
    dossier_id: str
    periode: str
    lignes_ca3: CA3Lignes | None
    pdf_url: str | None
    statut: str  # "generée" | "erreur"
    erreur: str | None


# ── Client ────────────────────────────────────────────────────────────────────

def get_supabase_client():  # type: ignore[return]
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
    return create_client(url, key)


# ── Calcul CA3 ────────────────────────────────────────────────────────────────

def _compute_ca3_lignes(ecritures: list[dict]) -> CA3Lignes:
    """Agrège les écritures comptables pour calculer les lignes CA3.

    Comptes pris en compte :
      44571 → TVA collectée (crédit)
      44566 → TVA déductible (débit) — 44567 exclu (TVA non déductible)
      70x   → CA HT (crédit)
    """
    tva_collectee = 0.0
    tva_deductible = 0.0
    ca_ht = 0.0

    for e in ecritures:
        compte = str(e.get("compte") or "")
        credit = float(e.get("credit") or 0)
        debit = float(e.get("debit") or 0)

        if compte == "44571":
            tva_collectee += credit
        elif compte == "44566":
            tva_deductible += debit
        elif compte.startswith("70"):
            ca_ht += credit

    solde = tva_collectee - tva_deductible
    credit_tva = abs(solde) if solde < 0 else 0.0

    return CA3Lignes(
        ca_ht=round(ca_ht, 2),
        tva_collectee=round(tva_collectee, 2),
        tva_deductible=round(tva_deductible, 2),
        solde=round(solde, 2),
        credit_tva=round(credit_tva, 2),
    )


# ── Génération PDF ────────────────────────────────────────────────────────────

def _generate_pdf_ca3(periode: str, dossier_id: str, lignes: CA3Lignes) -> bytes:
    """Génère le PDF de la déclaration CA3 via ReportLab.

    Raises:
        ImportError: Si reportlab n'est pas installé.
    """
    import io  # noqa: PLC0415

    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.styles import getSampleStyleSheet  # noqa: PLC0415
    from reportlab.lib.units import cm  # noqa: PLC0415
    from reportlab.platypus import (  # noqa: PLC0415
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # En-tête
    story.append(Paragraph(f"<b>Déclaration TVA CA3 — Période {periode}</b>", styles["Title"]))
    story.append(Paragraph(f"Dossier : {dossier_id}", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # Tableau des lignes CA3
    data = [
        ["Ligne", "Libellé", "Montant (€)"],
        ["1",  "Chiffre d'affaires HT",    f"{lignes['ca_ht']:,.2f}"],
        ["A",  "TVA collectée",             f"{lignes['tva_collectee']:,.2f}"],
        ["B",  "TVA déductible",            f"{lignes['tva_deductible']:,.2f}"],
        ["",   "Solde (A - B)",             f"{lignes['solde']:,.2f}"],
    ]
    if lignes["credit_tva"] > 0:
        data.append(["C", "Crédit de TVA (report)", f"{lignes['credit_tva']:,.2f}"])

    tbl = Table(data, colWidths=[2*cm, 11*cm, 5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()


# ── Persistance Storage ───────────────────────────────────────────────────────

def _upload_pdf(supabase, dossier_id: str, periode: str, pdf_bytes: bytes) -> str:
    """Upload le PDF dans Supabase Storage et retourne l'URL publique."""
    bucket = "declarations"
    path = f"{dossier_id}/tva_ca3_{periode}.pdf"
    supabase.storage.from_(bucket).upload(
        path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"}
    )
    return supabase.storage.from_(bucket).get_public_url(path)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def run(
    dossier_id: str,
    periode: str,
    dry_run: bool = False,
) -> TvaDeclaratorResult:
    """Génère la déclaration CA3 depuis les écritures du dossier.

    Args:
        dossier_id: UUID du dossier.
        periode: Période au format "YYYY-MM" (ex : "2026-05").
        dry_run: Si True, calcule sans stocker ni mettre à jour la base.

    Returns:
        TvaDeclaratorResult avec les lignes CA3, l'URL PDF et le statut.
    """
    logger.info(f"tva_declarator — dossier {dossier_id}, période {periode}")

    try:
        supabase = get_supabase_client()
    except Exception as exc:
        return TvaDeclaratorResult(
            declaration_id=None, dossier_id=dossier_id, periode=periode,
            lignes_ca3=None, pdf_url=None, statut="erreur", erreur=str(exc),
        )

    # 1. Récupération de la déclaration TVA
    try:
        resp = (
            supabase.table("declarations_tva")
            .select("id, periode, statut")
            .eq("dossier_id", dossier_id)
            .eq("periode", periode)
            .single()
            .execute()
        )
        decl = resp.data
    except Exception as exc:
        logger.error(f"tva_declarator — lecture déclaration : {exc}")
        decl = None

    if not decl:
        return TvaDeclaratorResult(
            declaration_id=None, dossier_id=dossier_id, periode=periode,
            lignes_ca3=None, pdf_url=None, statut="erreur",
            erreur=f"Déclaration TVA introuvable pour dossier {dossier_id}, période {periode}",
        )

    declaration_id = decl["id"]

    # 2. Récupération des écritures de la période
    try:
        year, month = int(periode[:4]), int(periode[5:7])
        last_day = calendar.monthrange(year, month)[1]
        date_debut = f"{periode}-01"
        date_fin = f"{periode}-{last_day:02d}"

        resp_ecr = (
            supabase.table("ecritures")
            .select("compte, debit, credit")
            .eq("dossier_id", dossier_id)
            .gte("date", date_debut)
            .lte("date", date_fin)
            .execute()
        )
        ecritures = resp_ecr.data or []
    except Exception as exc:
        logger.error(f"tva_declarator — lecture écritures : {exc}")
        ecritures = []

    # 3. Calcul des lignes CA3
    lignes = _compute_ca3_lignes(ecritures)
    logger.info(
        f"tva_declarator — CA3 {periode} : collectée={lignes['tva_collectee']}, "
        f"déductible={lignes['tva_deductible']}, solde={lignes['solde']}"
    )

    # 4. Génération PDF
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = _generate_pdf_ca3(periode, dossier_id, lignes)
    except ImportError:
        logger.warning("tva_declarator — ReportLab non installé, PDF non généré")
    except Exception as exc:
        logger.warning(f"tva_declarator — génération PDF échouée : {exc}")

    # 5. Upload Storage + mise à jour (sauf dry_run)
    pdf_url: str | None = None
    if not dry_run:
        if pdf_bytes:
            try:
                pdf_url = _upload_pdf(supabase, dossier_id, periode, pdf_bytes)
            except Exception as exc:
                logger.warning(f"tva_declarator — upload PDF échoué : {exc}")

        try:
            update_payload: dict = {"statut": "generée", "lignes_ca3": dict(lignes)}
            if pdf_url:
                update_payload["pdf_url"] = pdf_url
            supabase.table("declarations_tva").update(update_payload).eq("id", declaration_id).execute()
        except Exception as exc:
            logger.warning(f"tva_declarator — mise à jour déclaration échouée : {exc}")

        try:
            supabase.table("journaux").insert({
                "dossier_id": dossier_id,
                "type_action": "tva_ca3_generee",
                "statut": "ok",
                "contenu": f"CA3 {periode} — solde TVA {lignes['solde']:.2f}€",
                "metadata": {
                    "declaration_id": declaration_id,
                    "periode": periode,
                    **dict(lignes),
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"tva_declarator — journal échoué : {exc}")

    return TvaDeclaratorResult(
        declaration_id=declaration_id,
        dossier_id=dossier_id,
        periode=periode,
        lignes_ca3=lignes,
        pdf_url=pdf_url,
        statut="generée",
        erreur=None,
    )

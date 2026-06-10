"""Agent report_builder — rapports PDF mensuels par dossier.

Agrège les écritures du mois, calcule les soldes par compte
(actif/passif/charges/produits), génère un PDF ReportLab avec en-tête client,
résumé KPI et tableau des écritures, envoie par SMTP et stocke dans Storage.
"""

from __future__ import annotations

import calendar
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict

__all__ = [
    "ReportBuilderResult",
    "Soldes",
    "_compute_soldes",
    "_generate_pdf_rapport",
    "_send_email_rapport",
    "get_supabase_client",
    "run",
]

logger = logging.getLogger(__name__)


class Soldes(TypedDict):
    produits: float
    charges: float
    resultat_net: float
    par_compte: dict
    nb_ecritures: int


class ReportBuilderResult(TypedDict):
    dossier_id: str
    periode: str
    soldes: Soldes | None
    pdf_url: str | None
    statut: str  # "ok" | "erreur"
    erreur: str | None


# ── Client ────────────────────────────────────────────────────────────────────

def get_supabase_client():  # type: ignore[return]
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
    return create_client(url, key)


# ── Calcul des soldes ─────────────────────────────────────────────────────────

def _compute_soldes(ecritures: list[dict]) -> Soldes:
    """Agrège les écritures par type de compte.

    Comptes :
      70x → produits (crédit)
      6x  → charges (débit)
      Autres → par_compte uniquement
    """
    produits = 0.0
    charges = 0.0
    par_compte: dict[str, float] = {}

    for e in ecritures:
        compte = str(e.get("compte") or "")
        credit = float(e.get("credit") or 0)
        debit = float(e.get("debit") or 0)
        montant = credit - debit  # positif = créditeur

        # Accumulation par compte
        par_compte[compte] = par_compte.get(compte, 0.0) + montant

        if compte.startswith("70"):
            produits += credit
        elif compte.startswith("6"):
            charges += debit

    return Soldes(
        produits=round(produits, 2),
        charges=round(charges, 2),
        resultat_net=round(produits - charges, 2),
        par_compte={k: round(v, 2) for k, v in sorted(par_compte.items())},
        nb_ecritures=len(ecritures),
    )


# ── Génération PDF ────────────────────────────────────────────────────────────

def _generate_pdf_rapport(
    raison_sociale: str,
    periode: str,
    soldes: Soldes,
    ecritures: list[dict],
) -> bytes:
    """Génère le rapport PDF mensuel via ReportLab.

    Raises:
        ImportError: Si reportlab n'est pas installé.
    """
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.units import cm  # noqa: PLC0415
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.styles import getSampleStyleSheet  # noqa: PLC0415
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer  # noqa: PLC0415
    import io  # noqa: PLC0415

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # En-tête
    story.append(Paragraph(f"<b>Rapport mensuel — {raison_sociale}</b>", styles["Title"]))
    story.append(Paragraph(f"Période : {periode}", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # KPIs
    kpi_data = [
        ["Indicateur", "Montant (€)"],
        ["Chiffre d'affaires HT",     f"{soldes['produits']:,.2f}"],
        ["Charges",                    f"{soldes['charges']:,.2f}"],
        ["Résultat net",               f"{soldes['resultat_net']:,.2f}"],
        ["Nombre d'écritures",         str(soldes["nb_ecritures"])],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[11*cm, 6*cm])
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 4), (-1, 4),
         colors.HexColor("#27ae60") if soldes["resultat_net"] >= 0 else colors.HexColor("#c0392b")),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 0.5*cm))

    # Tableau des écritures (max 50 lignes)
    story.append(Paragraph("<b>Détail des écritures</b>", styles["Heading2"]))
    ecr_data = [["Date", "Compte", "Libellé", "Débit (€)", "Crédit (€)"]]
    for e in ecritures[:50]:
        ecr_data.append([
            str(e.get("date", "")),
            str(e.get("compte", "")),
            str(e.get("libelle", ""))[:40],
            f"{e.get('debit') or 0:,.2f}" if e.get("debit") else "",
            f"{e.get('credit') or 0:,.2f}" if e.get("credit") else "",
        ])
    if len(ecritures) > 50:
        ecr_data.append(["...", "", f"+ {len(ecritures) - 50} écriture(s)", "", ""])

    ecr_tbl = Table(ecr_data, colWidths=[2.5*cm, 2.5*cm, 8*cm, 2.5*cm, 2.5*cm])
    ecr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
        ("ALIGN", (3, 0), (4, -1), "RIGHT"),
    ]))
    story.append(ecr_tbl)

    doc.build(story)
    return buf.getvalue()


# ── Envoi email ───────────────────────────────────────────────────────────────

def _send_email_rapport(
    destinataire: str,
    pdf_bytes: bytes,
    raison_sociale: str,
    periode: str,
) -> None:
    """Envoie le rapport PDF par SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning("report_builder — SMTP non configuré, email non envoyé")
        return

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = destinataire
    msg["Subject"] = f"Rapport mensuel {raison_sociale} — {periode}"

    body = (
        f"Bonjour,\n\n"
        f"Veuillez trouver ci-joint le rapport comptable mensuel de {raison_sociale} "
        f"pour la période {periode}.\n\n"
        f"Cordialement,\nJM Partners"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    attach = MIMEApplication(pdf_bytes, _subtype="pdf")
    attach.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"rapport_{raison_sociale.replace(' ', '_')}_{periode}.pdf",
    )
    msg.attach(attach)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


# ── Persistance Storage ───────────────────────────────────────────────────────

def _upload_pdf(supabase, dossier_id: str, periode: str, pdf_bytes: bytes) -> str:
    bucket = "rapports"
    path = f"{dossier_id}/rapport_mensuel_{periode}.pdf"
    supabase.storage.from_(bucket).upload(
        path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"}
    )
    return supabase.storage.from_(bucket).get_public_url(path)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def run(
    dossier_id: str,
    periode: str,
    dry_run: bool = False,
) -> ReportBuilderResult:
    """Génère et envoie le rapport mensuel d'un dossier.

    Args:
        dossier_id: UUID du dossier.
        periode: Période au format "YYYY-MM".
        dry_run: Si True, calcule sans envoyer ni stocker.

    Returns:
        ReportBuilderResult avec les soldes, l'URL PDF et le statut.
    """
    logger.info(f"report_builder — dossier {dossier_id}, période {periode}")

    try:
        supabase = get_supabase_client()
    except Exception as exc:
        return ReportBuilderResult(
            dossier_id=dossier_id, periode=periode, soldes=None,
            pdf_url=None, statut="erreur", erreur=str(exc),
        )

    # 1. Lecture du dossier
    try:
        resp = (
            supabase.table("dossiers")
            .select("id, raison_sociale, responsable_email, cabinet_id")
            .eq("id", dossier_id)
            .single()
            .execute()
        )
        dossier = resp.data
    except Exception as exc:
        logger.error(f"report_builder — lecture dossier : {exc}")
        dossier = None

    if not dossier:
        return ReportBuilderResult(
            dossier_id=dossier_id, periode=periode, soldes=None,
            pdf_url=None, statut="erreur",
            erreur=f"Dossier {dossier_id} introuvable",
        )

    raison_sociale = dossier.get("raison_sociale") or dossier_id
    email_destinataire = dossier.get("responsable_email") or ""

    # 2. Récupération des écritures de la période
    try:
        year, month = int(periode[:4]), int(periode[5:7])
        last_day = calendar.monthrange(year, month)[1]
        date_debut = f"{periode}-01"
        date_fin = f"{periode}-{last_day:02d}"

        resp_ecr = (
            supabase.table("ecritures")
            .select("compte, libelle, date, debit, credit")
            .eq("dossier_id", dossier_id)
            .gte("date", date_debut)
            .lte("date", date_fin)
            .execute()
        )
        ecritures = resp_ecr.data or []
    except Exception as exc:
        logger.warning(f"report_builder — lecture écritures : {exc}")
        ecritures = []

    # 3. Calcul des soldes
    soldes = _compute_soldes(ecritures)
    logger.info(
        f"report_builder — {len(ecritures)} écriture(s), "
        f"CA={soldes['produits']}€, résultat={soldes['resultat_net']}€"
    )

    # 4. Génération PDF
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = _generate_pdf_rapport(raison_sociale, periode, soldes, ecritures)
    except ImportError:
        logger.warning("report_builder — ReportLab non installé, PDF non généré")
    except Exception as exc:
        logger.warning(f"report_builder — génération PDF échouée : {exc}")

    pdf_url: str | None = None

    if not dry_run:
        # 5. Upload Storage
        if pdf_bytes:
            try:
                pdf_url = _upload_pdf(supabase, dossier_id, periode, pdf_bytes)
            except Exception as exc:
                logger.warning(f"report_builder — upload PDF échoué : {exc}")

        # 6. Envoi email
        if email_destinataire and pdf_bytes:
            try:
                _send_email_rapport(email_destinataire, pdf_bytes, raison_sociale, periode)
            except Exception as exc:
                logger.warning(f"report_builder — envoi email échoué : {exc}")

        # 7. Journal
        try:
            supabase.table("journaux").insert({
                "dossier_id": dossier_id,
                "type_action": "rapport_mensuel_genere",
                "statut": "ok",
                "contenu": (
                    f"Rapport {periode} — CA {soldes['produits']:.0f}€, "
                    f"résultat {soldes['resultat_net']:.0f}€"
                ),
                "metadata": {
                    "periode": periode,
                    "produits": soldes["produits"],
                    "charges": soldes["charges"],
                    "resultat_net": soldes["resultat_net"],
                    "nb_ecritures": soldes["nb_ecritures"],
                    "pdf_url": pdf_url,
                },
            }).execute()
        except Exception as exc:
            logger.warning(f"report_builder — journal échoué : {exc}")

    return ReportBuilderResult(
        dossier_id=dossier_id,
        periode=periode,
        soldes=soldes,
        pdf_url=pdf_url,
        statut="ok",
        erreur=None,
    )

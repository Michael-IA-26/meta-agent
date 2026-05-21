"""Agent echeance_agent — rapport quotidien des échéances IS et TVA à 30 jours."""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict

import httpx
from supabase import Client, create_client

__all__ = ["Echeance", "EcheanceAgentResult", "run"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
RAPPORT_DESTINATAIRE = os.getenv("RAPPORT_DESTINATAIRE", SMTP_USER)

HORIZON_JOURS = 30


def _priorite(jours: int) -> str:
    """Retourne la couleur de priorité selon le nombre de jours restants."""
    if jours <= 3:
        return "rouge"
    if jours <= 7:
        return "orange"
    return "vert"


class Echeance(TypedDict):
    """Représente une échéance fiscale à venir."""

    type: str
    contact_id: str
    contact_nom: str | None
    dossier_id: str
    reference: str
    deadline: str
    jours_restants: int
    priorite: str
    montant: float | None
    statut: str


class EcheanceAgentResult(TypedDict):
    """Résultat de l'agent echeance_agent."""

    echeances_total: int
    rouge: int
    orange: int
    vert: int
    rapport_envoye: bool
    echeances: list[Echeance]
    erreurs: list[str]


def get_supabase_client() -> Client:
    """Retourne un client Supabase initialisé depuis les variables d'env."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_acomptes_is(supabase: Client, horizon: int) -> list[dict]:
    """Récupère les acomptes IS à payer dans les N prochains jours."""
    today = date.today()
    limite = (today + timedelta(days=horizon)).isoformat()
    try:
        resp = (
            supabase.table("acomptes_is")
            .select(
                "id, dossier_id, contact_id, numero_acompte, exercice, deadline, montant, statut"
            )
            .lte("deadline", limite)
            .gte("deadline", today.isoformat())
            .eq("statut", "a_payer")
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error(f"Erreur fetch acomptes IS : {exc}")
        return []


def fetch_declarations_tva(supabase: Client, horizon: int) -> list[dict]:
    """Récupère les déclarations TVA à soumettre dans les N prochains jours."""
    today = date.today()
    limite = (today + timedelta(days=horizon)).isoformat()
    try:
        resp = (
            supabase.table("declarations_tva")
            .select("id, dossier_id, contact_id, periode, deadline, statut")
            .lte("deadline", limite)
            .gte("deadline", today.isoformat())
            .in_("statut", ["a_preparer", "pieces_manquantes", "pret"])
            .execute()
        )
        return resp.data or []
    except Exception as exc:
        logger.error(f"Erreur fetch déclarations TVA : {exc}")
        return []


def fetch_contact_nom(supabase: Client, contact_id: str) -> str | None:
    """Retourne le nom d'un contact."""
    try:
        resp = (
            supabase.table("contacts")
            .select("nom")
            .eq("id", contact_id)
            .single()
            .execute()
        )
        return resp.data.get("nom") if resp.data else None
    except Exception:
        return None


def build_rapport(echeances: list[Echeance]) -> str:
    """Génère le texte du rapport quotidien des échéances."""
    today = date.today().isoformat()
    lignes = [f"📋 *Rapport échéances JM Partners — {today}*\n"]

    for priorite, label in [
        ("rouge", "🔴 URGENT (J≤3)"),
        ("orange", "🟠 Attention (J≤7)"),
        ("vert", "🟢 À venir (J≤30)"),
    ]:
        groupe = [e for e in echeances if e["priorite"] == priorite]
        if groupe:
            lignes.append(f"\n*{label}*")
            for e in groupe:
                nom = e["contact_nom"] or e["contact_id"][:8]
                montant_str = f" — {e['montant']:,.0f} €" if e["montant"] else ""
                lignes.append(
                    f"• {e['type'].upper()} | {nom} | {e['reference']} | "
                    f"deadline {e['deadline']} (J-{e['jours_restants']}){montant_str}"
                )
    return "\n".join(lignes)


def send_telegram(message: str) -> bool:
    """Envoie le rapport Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram non configuré")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message[:4096],
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        logger.error(f"Erreur Telegram echeance_agent : {exc}")
        return False


def send_email_rapport(sujet: str, corps: str) -> bool:
    """Envoie le rapport par email SMTP."""
    if not SMTP_USER or not RAPPORT_DESTINATAIRE:
        logger.warning("SMTP non configuré — rapport email non envoyé")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = RAPPORT_DESTINATAIRE
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [RAPPORT_DESTINATAIRE], msg.as_string())
        return True
    except Exception as exc:
        logger.error(f"Erreur SMTP rapport : {exc}")
        return False


def log_alerte_echeances(
    supabase: Client, echeances: list[Echeance], rapport: str
) -> None:
    """Logue le rapport dans journaux."""
    try:
        supabase.table("journaux").insert(
            {
                "type_action": "alerte_echeance",
                "contenu": rapport[:1000],
                "statut": "ok",
                "metadata": {
                    "nb_echeances": len(echeances),
                    "rouge": sum(1 for e in echeances if e["priorite"] == "rouge"),
                },
            }
        ).execute()
    except Exception as exc:
        logger.error(f"Erreur log journal echeance_agent : {exc}")


def run(dry_run: bool = False) -> EcheanceAgentResult:
    """Scanne les échéances à 30 jours, génère et envoie un rapport quotidien.

    Args:
        dry_run: Si True, génère le rapport sans envoyer ni logguer.

    Returns:
        EcheanceAgentResult avec le bilan et les échéances.
    """
    logger.info("echeance_agent — démarrage")
    supabase = get_supabase_client()
    today = date.today()
    erreurs: list[str] = []

    acomptes = fetch_acomptes_is(supabase, HORIZON_JOURS)
    tva_decls = fetch_declarations_tva(supabase, HORIZON_JOURS)

    echeances: list[Echeance] = []

    for a in acomptes:
        try:
            deadline = date.fromisoformat(a["deadline"])
            jours = (deadline - today).days
            nom = fetch_contact_nom(supabase, a["contact_id"])
            echeances.append(
                Echeance(
                    type="is",
                    contact_id=a["contact_id"],
                    contact_nom=nom,
                    dossier_id=a["dossier_id"],
                    reference=f"Acompte IS n°{a['numero_acompte']} {a['exercice']}",
                    deadline=a["deadline"],
                    jours_restants=jours,
                    priorite=_priorite(jours),
                    montant=a.get("montant"),
                    statut=a["statut"],
                )
            )
        except Exception as exc:
            logger.error(f"Erreur acompte IS {a.get('id')} : {exc}")
            erreurs.append(str(exc))

    for d in tva_decls:
        try:
            deadline = date.fromisoformat(d["deadline"])
            jours = (deadline - today).days
            nom = fetch_contact_nom(supabase, d["contact_id"])
            echeances.append(
                Echeance(
                    type="tva",
                    contact_id=d["contact_id"],
                    contact_nom=nom,
                    dossier_id=d["dossier_id"],
                    reference=f"TVA {d['periode']}",
                    deadline=d["deadline"],
                    jours_restants=jours,
                    priorite=_priorite(jours),
                    montant=None,
                    statut=d["statut"],
                )
            )
        except Exception as exc:
            logger.error(f"Erreur TVA décl {d.get('id')} : {exc}")
            erreurs.append(str(exc))

    echeances.sort(key=lambda e: e["jours_restants"])

    rapport = build_rapport(echeances)
    rapport_envoye = False

    if not dry_run and echeances:
        ok_telegram = send_telegram(rapport)
        ok_email = send_email_rapport(
            f"Échéances JM Partners — {today.isoformat()}", rapport
        )
        rapport_envoye = ok_telegram or ok_email
        if rapport_envoye:
            log_alerte_echeances(supabase, echeances, rapport)
    elif dry_run:
        logger.info(f"[DRY RUN] Rapport non envoyé :\n{rapport[:200]}")

    rouge = sum(1 for e in echeances if e["priorite"] == "rouge")
    orange = sum(1 for e in echeances if e["priorite"] == "orange")
    vert = sum(1 for e in echeances if e["priorite"] == "vert")

    logger.info(
        f"echeance_agent terminé : {len(echeances)} échéances "
        f"(🔴{rouge} 🟠{orange} 🟢{vert})"
    )
    return EcheanceAgentResult(
        echeances_total=len(echeances),
        rouge=rouge,
        orange=orange,
        vert=vert,
        rapport_envoye=rapport_envoye,
        echeances=echeances,
        erreurs=erreurs,
    )

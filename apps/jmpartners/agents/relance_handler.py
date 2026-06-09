"""Agent relance_handler — compose et envoie les emails de relance documents."""

from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict, cast

import anthropic
from supabase import Client, create_client

from apps.jmpartners.agents.document_checker import (
    DocumentCheckerResult,
    DocumentManquant,
)

__all__ = ["RelanceResult", "run"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

DELAI_ANTI_DOUBLON_HEURES = 48

TONALITE_PAR_URGENCE = {
    "J-0": "urgent",
    "J-3": "ferme",
    "J-7": "cordial",
    "J-15": "cordial",
    None: "cordial",
}


class RelanceResult(TypedDict):
    """Résultat de l'envoi d'une relance."""

    envoye: bool
    raison_skip: str | None
    email_destinataire: str | None
    sujet: str | None
    corps: str | None
    journal_id: str | None


def get_supabase_client() -> Client:
    """Retourne un client Supabase initialisé depuis les variables d'env."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis — configure Doppler")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_anthropic_client() -> anthropic.Anthropic:
    """Retourne un client Anthropic initialisé."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY est requis — configure Doppler")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _urgence_max(result: DocumentCheckerResult) -> str | None:
    """Retourne l'urgence la plus élevée parmi les documents manquants."""
    ordre = {"J-0": 4, "J-3": 3, "J-7": 2, "J-15": 1, None: 0}
    max_urgence: str | None = None
    max_score = 0
    for doc in result["manquants"]:
        score = ordre.get(doc["urgence"], 0)
        if score > max_score:
            max_score = score
            max_urgence = doc["urgence"]
    return max_urgence


def relance_deja_envoyee(supabase: Client, contact_id: str, dossier_id: str) -> bool:
    """Vérifie si une relance a été envoyée dans les 48 dernières heures."""
    seuil = (
        datetime.now(tz=timezone.utc) - timedelta(hours=DELAI_ANTI_DOUBLON_HEURES)
    ).isoformat()
    try:
        resp = (
            supabase.table("journaux")
            .select("id")
            .eq("contact_id", contact_id)
            .eq("dossier_id", dossier_id)
            .eq("type_action", "relance_envoyee")
            .gte("created_at", seuil)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        logger.warning(f"Erreur vérification doublon relance : {exc}")
        return False


def fetch_contact_email(
    supabase: Client, contact_id: str
) -> tuple[str | None, str | None]:
    """Retourne (email, nom) d'un contact depuis Supabase."""
    try:
        resp = (
            supabase.table("contacts")
            .select("email, nom")
            .eq("id", contact_id)
            .single()
            .execute()
        )
        if resp.data:
            row = cast(dict, resp.data)
            return row.get("email"), row.get("nom")
    except Exception as exc:
        logger.error(f"Erreur fetch contact {contact_id} : {exc}")
    return None, None


def compose_relance(
    ai_client: anthropic.Anthropic,
    contact_nom: str,
    manquants: list[DocumentManquant],
    tonalite: str,
) -> tuple[str, str]:
    """Compose un email de relance via Claude.

    Returns (sujet, corps).
    """
    liste_docs = "\n".join(
        f"- {m['nom_document']}"
        + (f" (deadline : {m['deadline']})" if m.get("deadline") else "")
        for m in manquants
    )
    prompt = (
        f"Rédige un email de relance comptable en français.\n"
        f"Client : {contact_nom}\n"
        f"Tonalité : {tonalite} (cordial=poli, ferme=direct, urgent=pressant)\n"
        f"Documents manquants :\n{liste_docs}\n\n"
        "Réponds UNIQUEMENT en JSON : "
        '{"sujet": "...", "corps": "..."}\n'
        "Le corps doit être court (5-8 lignes max), professionnel, sans emojis."
    )
    try:
        msg = ai_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        block = msg.content[0]
        raw_text = block.text if hasattr(block, "text") else ""
        data = json.loads(raw_text.strip())
        return data.get("sujet", "Relance documents"), data.get("corps", "")
    except Exception as exc:
        logger.warning(f"Erreur composition relance Claude : {exc}")
        noms = ", ".join(m["nom_document"] for m in manquants[:3])
        return "Relance : documents manquants", (
            f"Bonjour {contact_nom},\n\n"
            f"Nous n'avons pas encore reçu les documents suivants : {noms}.\n"
            "Merci de nous les transmettre dans les meilleurs délais.\n\n"
            "Cordialement,\nLe cabinet JM Partners"
        )


def send_smtp(destinataire: str, sujet: str, corps: str) -> bool:
    """Envoie un email via SMTP TLS.

    Returns True si succès, False sinon (sans lever d'exception).
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = destinataire
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [destinataire], msg.as_string())
        return True
    except Exception as exc:
        logger.error(f"Erreur SMTP vers {destinataire} : {exc}")
        return False


def log_journal(
    supabase: Client,
    contact_id: str,
    dossier_id: str,
    type_action: str,
    destinataire: str | None,
    statut: str,
) -> str | None:
    """Logue l'action relance dans journaux et retourne l'id."""
    try:
        resp = (
            supabase.table("journaux")
            .insert(
                {
                    "contact_id": contact_id,
                    "dossier_id": dossier_id,
                    "type_action": type_action,
                    "contenu": f"destinataire={destinataire}",
                    "statut": statut,
                    "metadata": {"destinataire": destinataire},
                }
            )
            .execute()
        )
        if resp.data:
            return cast(dict, resp.data[0])["id"]
    except Exception as exc:
        logger.error(f"Erreur log journal relance : {exc}")
    return None


def run(result: DocumentCheckerResult, dry_run: bool = False) -> RelanceResult:
    """Envoie une relance email pour les documents manquants d'un dossier.

    Args:
        result: Résultat de document_checker avec la liste des manquants.
        dry_run: Si True, compose l'email sans l'envoyer ni logguer.

    Returns:
        RelanceResult avec le statut d'envoi.
    """
    logger.info(f"relance_handler — dossier {result['dossier_id']}")

    if not result["manquants"]:
        logger.info("relance_handler : aucun document manquant, skip")
        return RelanceResult(
            envoye=False,
            raison_skip="Aucun document manquant",
            email_destinataire=None,
            sujet=None,
            corps=None,
            journal_id=None,
        )

    contact_id = result["contact_id"]
    dossier_id = result["dossier_id"]

    if not contact_id:
        return RelanceResult(
            envoye=False,
            raison_skip="contact_id manquant",
            email_destinataire=None,
            sujet=None,
            corps=None,
            journal_id=None,
        )

    supabase = get_supabase_client()

    if not dry_run and relance_deja_envoyee(supabase, contact_id, dossier_id):
        logger.info(
            f"relance_handler : relance déjà envoyée < {DELAI_ANTI_DOUBLON_HEURES}h"
        )
        journal_id = log_journal(
            supabase, contact_id, dossier_id, "relance_skipped", None, "skipped"
        )
        return RelanceResult(
            envoye=False,
            raison_skip=f"Relance déjà envoyée dans les {DELAI_ANTI_DOUBLON_HEURES}h",
            email_destinataire=None,
            sujet=None,
            corps=None,
            journal_id=journal_id,
        )

    email_dest, contact_nom = fetch_contact_email(supabase, contact_id)
    if not email_dest:
        return RelanceResult(
            envoye=False,
            raison_skip="Email contact introuvable",
            email_destinataire=None,
            sujet=None,
            corps=None,
            journal_id=None,
        )

    urgence = _urgence_max(result)
    tonalite = TONALITE_PAR_URGENCE.get(urgence, "cordial")
    ai_client = get_anthropic_client()
    sujet, corps = compose_relance(
        ai_client, contact_nom or "Client", result["manquants"], tonalite
    )

    if dry_run:
        logger.info(f"[DRY RUN] Relance non envoyée à {email_dest}")
        return RelanceResult(
            envoye=False,
            raison_skip="dry_run",
            email_destinataire=email_dest,
            sujet=sujet,
            corps=corps,
            journal_id=None,
        )

    envoye = send_smtp(email_dest, sujet, corps)
    statut = "ok" if envoye else "erreur"
    journal_id = log_journal(
        supabase, contact_id, dossier_id, "relance_envoyee", email_dest, statut
    )

    logger.info(
        f"relance_handler : email {'envoyé' if envoye else 'ÉCHEC'} → {email_dest}"
    )
    return RelanceResult(
        envoye=envoye,
        raison_skip=None if envoye else "Erreur SMTP",
        email_destinataire=email_dest,
        sujet=sujet,
        corps=corps,
        journal_id=journal_id,
    )

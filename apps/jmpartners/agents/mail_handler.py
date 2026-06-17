"""Agent mail_handler — lecture IMAP, identification client, classification demande."""

from __future__ import annotations

import email
import imaplib
import logging
import os
from email.header import decode_header
from typing import Any, TypedDict, cast

import anthropic
from supabase import Client, create_client

__all__ = ["MailHandlerResult", "EmailItem", "run", "resolve_dossier_for_contact"]

logger = logging.getLogger(__name__)

IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TYPES_DEMANDE = ("document_manquant", "question_tva", "relance", "autre")


class EmailItem(TypedDict):
    """Représente un email traité."""

    message_id: str
    expediteur: str
    sujet: str
    corps: str
    contact_id: str | None
    contact_nom: str | None
    type_demande: str
    journal_id: str | None


class MailHandlerResult(TypedDict):
    """Résultat du traitement des emails par mail_handler."""

    traites: int
    non_matches: int
    emails: list[EmailItem]
    erreurs: list[str]


def get_supabase_client() -> Client:
    """Retourne un client Supabase initialisé depuis les variables d'env."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_anthropic_client() -> anthropic.Anthropic:
    """Retourne un client Anthropic initialisé."""
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def decode_str(value: str | bytes) -> str:
    """Décode un header email encodé (RFC 2047)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def fetch_unseen_emails(
    host: str, user: str, password: str
) -> list[tuple[str, str, str, str]]:
    """Se connecte en IMAP et retourne les emails non lus (message_id, expediteur, sujet, corps).

    Returns list of (message_id, from_addr, subject, body) tuples.
    """
    results: list[tuple[str, str, str, str]] = []
    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split() if data[0] else []
        for uid in ids:
            _, msg_data = mail.fetch(uid, "(RFC822)")
            raw = msg_data[0][1] if msg_data and msg_data[0] else None
            if not raw:
                continue
            msg = email.message_from_bytes(cast(bytes, raw))
            message_id = msg.get("Message-ID", str(uid))
            from_addr = decode_str(msg.get("From", ""))
            subject = decode_str(msg.get("Subject", ""))
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload and isinstance(payload, bytes):
                            body = payload.decode("utf-8", errors="replace")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload and isinstance(payload, bytes):
                    body = payload.decode("utf-8", errors="replace")
            results.append((message_id, from_addr, subject, body))
        mail.logout()
    except Exception as exc:
        logger.error(f"Erreur IMAP : {exc}")
    return results


def identify_contact(
    supabase: Client, expediteur: str
) -> tuple[str | None, str | None]:
    """Recherche un contact dans Supabase par email ou nom extrait de l'expéditeur.

    Returns (contact_id, contact_nom) ou (None, None) si non trouvé.
    """
    email_addr = expediteur
    if "<" in expediteur:
        email_addr = expediteur.split("<")[1].rstrip(">").strip()

    try:
        resp = (
            supabase.table("contacts")
            .select("id, nom")
            .eq("email", email_addr)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = cast(dict, resp.data[0])
            return row["id"], row["nom"]
    except Exception as exc:
        logger.warning(f"Erreur matching contact par email : {exc}")

    return None, None


def classify_request(client: anthropic.Anthropic, sujet: str, corps: str) -> str:
    """Classifie le type de demande via Claude (JSON structured output).

    Returns one of: document_manquant, question_tva, relance, autre.
    """
    prompt = (
        f"Sujet : {sujet[:200]}\n\nCorps : {corps[:800]}\n\n"
        "Classifie cette demande dans UNE des catégories suivantes :\n"
        "- document_manquant : le client signale ou demande un document\n"
        "- question_tva : question relative à la TVA\n"
        "- relance : relance de paiement ou de dossier\n"
        "- autre : tout autre sujet\n\n"
        'Réponds UNIQUEMENT avec le JSON : {"type": "<categorie>"}'
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        block = msg.content[0]
        raw_text = block.text if hasattr(block, "text") else ""
        import json

        data = json.loads(raw_text.strip())
        type_demande = data.get("type", "autre")
        if type_demande not in TYPES_DEMANDE:
            return "autre"
        return type_demande
    except Exception as exc:
        logger.warning(f"Erreur classification Claude : {exc}")
        return "autre"


def log_journal(
    supabase: Client,
    contact_id: str | None,
    type_demande: str,
    sujet: str,
    statut: str = "ok",
) -> str | None:
    """Insère une entrée dans la table journaux et retourne son id."""
    try:
        resp = (
            supabase.table("journaux")
            .insert(
                {
                    "contact_id": contact_id,
                    "type_action": "email_recu",
                    "contenu": f"type_demande={type_demande} | sujet={sujet[:200]}",
                    "statut": statut,
                    "metadata": {"type_demande": type_demande},
                }
            )
            .execute()
        )
        if resp.data:
            return cast(dict, resp.data[0])["id"]
    except Exception as exc:
        logger.error(f"Erreur log journal : {exc}")
    return None


def resolve_dossier_for_contact(supabase: Any, contact_id: str | None) -> str | None:
    """Retourne le dossier_id si le contact a exactement un dossier en_cours.

    Returns None when contact_id is None, when there are 0 or 2+ active dossiers,
    or when Supabase is unavailable (logs a warning).
    """
    if contact_id is None:
        return None
    try:
        resp = (
            supabase.table("dossiers")
            .select("id")
            .eq("contact_id", contact_id)
            .eq("statut", "en_cours")
            .execute()
        )
        rows = resp.data or []
        if len(rows) == 1:
            return str(rows[0]["id"])
        if len(rows) > 1:
            logger.warning(
                "resolve_dossier_for_contact: contact %s a %d dossiers actifs — ambigu, dossier_id=None",
                contact_id,
                len(rows),
            )
        return None
    except Exception as exc:
        logger.warning("resolve_dossier_for_contact: Supabase erreur — %s", exc)
        return None


def run(dry_run: bool = False) -> MailHandlerResult:
    """Point d'entrée principal : lit les emails IMAP, identifie les clients, classifie.

    Args:
        dry_run: Si True, ne logue pas en base et n'effectue aucun effet de bord.

    Returns:
        MailHandlerResult avec les emails traités et les statistiques.
    """
    logger.info("mail_handler — démarrage")
    supabase = get_supabase_client()
    ai_client = get_anthropic_client()

    raw_emails = fetch_unseen_emails(IMAP_HOST, IMAP_USER, IMAP_PASSWORD)
    logger.info(f"mail_handler : {len(raw_emails)} emails non lus")

    items: list[EmailItem] = []
    erreurs: list[str] = []
    non_matches = 0

    for message_id, expediteur, sujet, corps in raw_emails:
        try:
            contact_id, contact_nom = identify_contact(supabase, expediteur)
            if contact_id is None:
                non_matches += 1
                logger.info(f"Contact non trouvé pour {expediteur}")

            type_demande = classify_request(ai_client, sujet, corps)

            journal_id = None
            if not dry_run:
                journal_id = log_journal(supabase, contact_id, type_demande, sujet)

            items.append(
                EmailItem(
                    message_id=message_id,
                    expediteur=expediteur,
                    sujet=sujet,
                    corps=corps[:500],
                    contact_id=contact_id,
                    contact_nom=contact_nom,
                    type_demande=type_demande,
                    journal_id=journal_id,
                )
            )
        except Exception as exc:
            logger.error(f"Erreur traitement email {message_id} : {exc}")
            erreurs.append(str(exc))

    logger.info(
        f"mail_handler terminé : {len(items)} traités, {non_matches} non matchés"
    )
    return MailHandlerResult(
        traites=len(items),
        non_matches=non_matches,
        emails=items,
        erreurs=erreurs,
    )

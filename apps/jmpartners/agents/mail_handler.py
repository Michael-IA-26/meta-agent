"""Agent mail_handler — ingestion Outlook via Microsoft Graph, identification client, classification."""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
from typing import Any, TypedDict, cast

import anthropic
from supabase import Client, create_client

from apps.jmpartners.integrations import graph_mail

__all__ = ["MailHandlerResult", "EmailItem", "resolve_or_create_dossier", "run"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GRAPH_MAILBOX = os.getenv("GRAPH_MAILBOX", "")
STORAGE_BUCKET = "documents"

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
    pieces_jointes: int


class MailHandlerResult(TypedDict):
    """Résultat du traitement des emails par mail_handler."""

    traites: int
    non_matches: int
    emails: list[EmailItem]
    erreurs: list[str]


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis — configure Doppler")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_anthropic_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY est requis — configure Doppler")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def identify_contact(
    supabase: Client, expediteur: str
) -> tuple[str | None, str | None]:
    """Recherche un contact par email.

    Returns (contact_id, contact_nom) ou (None, None).
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
        logger.warning(f"Erreur matching contact : {exc}")
    return None, None


def resolve_or_create_dossier(supabase: Client, contact_id: str) -> str | None:
    """Retourne l'id du dossier le plus récent du contact.

    Si aucun dossier n'existe, en crée un minimal (type='tva', exercice=année courante).
    Retourne None uniquement si la création échoue.
    """
    try:
        resp = (
            supabase.table("dossiers")
            .select("id")
            .eq("contact_id", contact_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return cast(dict, resp.data[0])["id"]
    except Exception as exc:
        logger.error(f"resolve_or_create_dossier — lecture échouée pour contact {contact_id} : {exc}")
        return None

    # Aucun dossier → création automatique
    try:
        exercice = str(datetime.date.today().year)
        resp_ins = (
            supabase.table("dossiers")
            .insert({
                "contact_id": contact_id,
                "type": "tva",
                "exercice": exercice,
                "statut": "en_cours",
            })
            .execute()
        )
        if resp_ins.data:
            dossier_id = cast(dict, resp_ins.data[0])["id"]
            logger.info(
                f"resolve_or_create_dossier — dossier auto-créé pour contact "
                f"{contact_id} : {dossier_id}"
            )
            return dossier_id
    except Exception as exc:
        logger.error(
            f"resolve_or_create_dossier — création échouée pour contact {contact_id} : {exc}"
        )
    return None


def classify_request(client: anthropic.Anthropic, sujet: str, corps: str) -> str:
    """Classifie le type de demande via Claude."""
    prompt = (
        f"Sujet : {sujet[:200]}\n\nCorps : {corps[:800]}\n\n"
        "Classifie cette demande dans UNE des catégories :\n"
        "- document_manquant\n- question_tva\n- relance\n- autre\n\n"
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
        data = json.loads(raw_text.strip())
        type_demande = data.get("type", "autre")
        return type_demande if type_demande in TYPES_DEMANDE else "autre"
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
    """Insère une entrée dans la table journaux."""
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _document_exists(supabase: Client, sha256_hash: str) -> bool:
    """Return True si un document avec ce hash existe déjà."""
    try:
        resp = (
            supabase.table("documents")
            .select("id")
            .eq("hash", sha256_hash)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception as exc:
        logger.warning(f"Erreur vérification hash document : {exc}")
        return False


def _upload_and_insert(
    supabase: Client,
    filename: str,
    content: bytes,
    sha256_hash: str,
    contact_id: str | None,
    dossier_id: str | None,
) -> None:
    """Upload vers Storage puis insert dans documents."""
    storage_path = f"{dossier_id or 'unknown'}/{sha256_hash[:8]}_{filename}"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": "application/octet-stream"},
    )
    supabase.table("documents").insert(
        {
            "nom": filename,
            "hash": sha256_hash,
            "statut": "en_attente_ocr",
            "source": "outlook",
            "dossier_id": dossier_id,
            "contact_id": contact_id,
            "storage_path": storage_path,
        }
    ).execute()


def _process_attachments(
    supabase: Client,
    message: dict[str, Any],
    contact_id: str | None,
    dossier_id: str | None,
    dry_run: bool,
) -> int:
    """Traite les pièces jointes : dédup SHA-256, upload Storage, insert documents.

    Returns le nombre de pièces réellement uploadées.
    """
    uploaded = 0
    for filename, content in graph_mail.decode_attachments(message):
        h = _sha256(content)
        if _document_exists(supabase, h):
            logger.info(f"Pièce jointe dupliquée ignorée : {filename} ({h[:8]}…)")
            continue
        if not dry_run:
            try:
                _upload_and_insert(supabase, filename, content, h, contact_id, dossier_id)
                uploaded += 1
            except Exception as exc:
                logger.error(f"Erreur upload pièce jointe {filename} : {exc}")
        else:
            uploaded += 1
    return uploaded


def _graph_configured() -> bool:
    return bool(os.getenv("GRAPH_TENANT_ID") and os.getenv("GRAPH_CLIENT_ID") and os.getenv("GRAPH_CLIENT_SECRET"))


def run(dry_run: bool = False) -> MailHandlerResult:
    """Point d'entrée : lit les emails Graph, identifie les clients, classifie, traite les pièces."""
    logger.info("mail_handler — démarrage (Graph)")

    if not _graph_configured():
        logger.warning("mail_handler — Graph non configuré (GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET manquants)")
        return MailHandlerResult(traites=0, non_matches=0, emails=[], erreurs=["Graph non configuré"])

    supabase = get_supabase_client()
    ai_client = get_anthropic_client()

    try:
        messages = graph_mail.fetch_unread(mailbox=GRAPH_MAILBOX)
    except Exception as exc:
        logger.error(f"Erreur fetch_unread Graph : {exc}")
        return MailHandlerResult(traites=0, non_matches=0, emails=[], erreurs=[str(exc)])

    logger.info(f"mail_handler : {len(messages)} emails non lus")

    items: list[EmailItem] = []
    erreurs: list[str] = []
    non_matches = 0

    for msg in messages:
        message_id: str = msg.get("id", "")
        expediteur: str = (msg.get("from", {}) or {}).get("emailAddress", {}).get("address", "")
        sujet: str = msg.get("subject", "")
        corps: str = (msg.get("body", {}) or {}).get("content", "")

        try:
            contact_id, contact_nom = identify_contact(supabase, expediteur)
            if contact_id is None:
                non_matches += 1
                logger.info(f"Contact non trouvé pour {expediteur}")

            dossier_id: str | None = None
            if contact_id is not None:
                dossier_id = resolve_or_create_dossier(supabase, contact_id)
                if dossier_id is None:
                    logger.warning(
                        f"mail_handler — impossible de résoudre/créer un dossier pour "
                        f"contact {contact_id} ({contact_nom}), pièces jointes ignorées"
                    )

            type_demande = classify_request(ai_client, sujet, corps)

            if dossier_id is not None:
                pieces_jointes = _process_attachments(
                    supabase, msg, contact_id, dossier_id=dossier_id, dry_run=dry_run
                )
            else:
                pieces_jointes = 0

            journal_id = None
            if not dry_run:
                journal_id = log_journal(supabase, contact_id, type_demande, sujet)
                if message_id:
                    try:
                        graph_mail.mark_read(message_id)
                    except Exception as exc:
                        logger.warning(f"Impossible de marquer lu {message_id} : {exc}")

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
                    pieces_jointes=pieces_jointes,
                )
            )
        except Exception as exc:
            logger.error(f"Erreur traitement email {message_id} : {exc}")
            erreurs.append(str(exc))

    logger.info(f"mail_handler terminé : {len(items)} traités, {non_matches} non matchés")
    return MailHandlerResult(
        traites=len(items),
        non_matches=non_matches,
        emails=items,
        erreurs=erreurs,
    )

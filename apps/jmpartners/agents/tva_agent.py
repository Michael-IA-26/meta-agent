"""Agent tva_agent — surveillance des échéances TVA et vérification des pièces."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import TypedDict

import httpx
from supabase import Client, create_client

from apps.jmpartners.agents.document_checker import DocumentCheckerResult
from apps.jmpartners.agents.document_checker import run as check_docs

__all__ = ["TvaDeclarationStatus", "TvaAgentResult", "run"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_USER = os.getenv("SMTP_USER", "")

HORIZONS_ALERTE = [15, 7, 3]


class TvaDeclarationStatus(TypedDict):
    """Statut d'une déclaration TVA analysée."""

    declaration_id: str
    dossier_id: str
    contact_id: str
    contact_nom: str | None
    periode: str
    deadline: str
    jours_restants: int
    pieces_manquantes: list[str]
    statut: str
    alerte_envoyee: bool


class TvaAgentResult(TypedDict):
    """Résultat global de l'agent tva_agent."""

    declarations_analysees: int
    alertes_envoyees: int
    pieces_manquantes_total: int
    declarations: list[TvaDeclarationStatus]
    erreurs: list[str]


def get_supabase_client() -> Client:
    """Retourne un client Supabase initialisé depuis les variables d'env."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_declarations_a_venir(supabase: Client, horizon_jours: int = 15) -> list[dict]:
    """Récupère les déclarations TVA dont la deadline est dans les N prochains jours."""
    today = date.today()
    limite = (today + timedelta(days=horizon_jours)).isoformat()
    try:
        resp = (
            supabase.table("declarations_tva")
            .select("id, dossier_id, contact_id, periode, deadline, statut")
            .lte("deadline", limite)
            .gte("deadline", today.isoformat())
            .neq("statut", "valide")
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


def send_telegram_alerte(message: str) -> bool:
    """Envoie une alerte Telegram au cabinet.

    Returns True si succès.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram non configuré — alerte TVA non envoyée")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        logger.error(f"Erreur Telegram TVA : {exc}")
        return False


def log_alerte_tva(
    supabase: Client,
    contact_id: str,
    dossier_id: str,
    declaration_id: str,
    message: str,
) -> None:
    """Logue l'alerte TVA dans journaux et met à jour alerte_envoyee_at."""
    try:
        supabase.table("journaux").insert(
            {
                "contact_id": contact_id,
                "dossier_id": dossier_id,
                "type_action": "alerte_tva",
                "contenu": message[:500],
                "statut": "ok",
                "metadata": {"declaration_id": declaration_id},
            }
        ).execute()
        supabase.table("declarations_tva").update(
            {"alerte_envoyee_at": "now()", "statut": "pieces_manquantes"}
        ).eq("id", declaration_id).execute()
    except Exception as exc:
        logger.error(f"Erreur log alerte TVA : {exc}")


def run(dry_run: bool = False) -> TvaAgentResult:
    """Analyse les déclarations TVA à venir et envoie des alertes si pièces manquantes.

    Args:
        dry_run: Si True, ne logue pas et n'envoie pas d'alertes.

    Returns:
        TvaAgentResult avec le bilan des déclarations analysées.
    """
    logger.info("tva_agent — démarrage")
    supabase = get_supabase_client()

    declarations = fetch_declarations_a_venir(
        supabase, horizon_jours=max(HORIZONS_ALERTE)
    )
    logger.info(f"tva_agent : {len(declarations)} déclarations à traiter")

    statuts: list[TvaDeclarationStatus] = []
    alertes_envoyees = 0
    pieces_manquantes_total = 0
    erreurs: list[str] = []

    for decl in declarations:
        try:
            decl_id = decl["id"]
            dossier_id = decl["dossier_id"]
            contact_id = decl["contact_id"]
            deadline = date.fromisoformat(decl["deadline"])
            jours_restants = (deadline - date.today()).days

            contact_nom = fetch_contact_nom(supabase, contact_id)
            doc_result: DocumentCheckerResult = check_docs(dossier_id, dry_run=dry_run)
            manquants = [m["nom_document"] for m in doc_result["manquants"]]
            pieces_manquantes_total += len(manquants)

            alerte_envoyee = False
            if manquants and jours_restants in HORIZONS_ALERTE:
                msg = (
                    f"⚠️ *Alerte TVA — {contact_nom or contact_id}*\n"
                    f"Deadline : {decl['deadline']} (J-{jours_restants})\n"
                    f"Pièces manquantes :\n" + "\n".join(f"• {m}" for m in manquants)
                )
                if not dry_run:
                    alerte_envoyee = send_telegram_alerte(msg)
                    if alerte_envoyee:
                        log_alerte_tva(supabase, contact_id, dossier_id, decl_id, msg)
                        alertes_envoyees += 1
                else:
                    logger.info(f"[DRY RUN] Alerte TVA non envoyée : {msg[:80]}")

            statuts.append(
                TvaDeclarationStatus(
                    declaration_id=decl_id,
                    dossier_id=dossier_id,
                    contact_id=contact_id,
                    contact_nom=contact_nom,
                    periode=decl["periode"],
                    deadline=decl["deadline"],
                    jours_restants=jours_restants,
                    pieces_manquantes=manquants,
                    statut="pieces_manquantes" if manquants else "pret",
                    alerte_envoyee=alerte_envoyee,
                )
            )
        except Exception as exc:
            logger.error(f"Erreur tva_agent décl {decl.get('id')} : {exc}")
            erreurs.append(str(exc))

    logger.info(
        f"tva_agent terminé : {len(statuts)} analysées, "
        f"{alertes_envoyees} alertes, {pieces_manquantes_total} pièces manquantes"
    )
    return TvaAgentResult(
        declarations_analysees=len(statuts),
        alertes_envoyees=alertes_envoyees,
        pieces_manquantes_total=pieces_manquantes_total,
        declarations=statuts,
        erreurs=erreurs,
    )

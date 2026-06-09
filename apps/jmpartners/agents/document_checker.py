"""Agent document_checker — vérifie les pièces manquantes par dossier."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import TypedDict, cast

from supabase import Client, create_client

__all__ = ["DocumentManquant", "DocumentCheckerResult", "run"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Documents attendus par type de dossier
DOCUMENTS_ATTENDUS: dict[str, list[str]] = {
    "bilan": [
        "grand_livre",
        "balance",
        "factures_achats",
        "factures_ventes",
        "releves_bancaires",
    ],
    "tva": [
        "ca_mensuel",
        "factures_tva",
        "releves_bancaires",
    ],
    "is": [
        "resultat_comptable",
        "liasse_fiscale",
        "bilan_n_1",
    ],
    "paie": [
        "contrats_travail",
        "bulletins_salaire",
        "declarations_sociales",
    ],
    "creation": [
        "statuts",
        "kbis",
        "rib_societe",
        "justificatif_siege",
    ],
}


def _compute_urgence(deadline: date | None) -> str | None:
    """Calcule le niveau d'urgence selon la date limite."""
    if deadline is None:
        return None
    today = date.today()
    delta = (deadline - today).days
    if delta <= 0:
        return "J-0"
    if delta <= 3:
        return "J-3"
    if delta <= 7:
        return "J-7"
    if delta <= 15:
        return "J-15"
    return None


class DocumentManquant(TypedDict):
    """Représente un document manquant pour un dossier."""

    nom_document: str
    type_document: str
    deadline: str | None
    urgence: str | None


class DocumentCheckerResult(TypedDict):
    """Résultat de la vérification des documents d'un dossier."""

    dossier_id: str
    contact_id: str | None
    type_dossier: str
    manquants: list[DocumentManquant]
    complets: list[str]
    erreur: str | None


def get_supabase_client() -> Client:
    """Retourne un client Supabase initialisé depuis les variables d'env."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis — configure Doppler")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def fetch_dossier(supabase: Client, dossier_id: str) -> dict | None:
    """Récupère un dossier depuis Supabase par son id."""
    try:
        resp = (
            supabase.table("dossiers")
            .select("id, contact_id, type, deadline")
            .eq("id", dossier_id)
            .single()
            .execute()
        )
        return cast(dict, resp.data) if resp.data else None
    except Exception as exc:
        logger.error(f"Erreur fetch dossier {dossier_id} : {exc}")
        return None


def fetch_documents_presents(supabase: Client, dossier_id: str) -> list[str]:
    """Retourne les types de documents reçus ou validés pour un dossier."""
    try:
        resp = (
            supabase.table("documents")
            .select("type_document, statut")
            .eq("dossier_id", dossier_id)
            .in_("statut", ["recu", "valide"])
            .execute()
        )
        return [cast(dict, row)["type_document"] for row in (resp.data or [])]
    except Exception as exc:
        logger.error(f"Erreur fetch documents {dossier_id} : {exc}")
        return []


def log_journal(
    supabase: Client,
    contact_id: str | None,
    dossier_id: str,
    manquants: list[DocumentManquant],
    dry_run: bool = False,
) -> None:
    """Logue la vérification dans la table journaux."""
    if dry_run:
        return
    try:
        noms = [m["nom_document"] for m in manquants]
        supabase.table("journaux").insert(
            {
                "contact_id": contact_id,
                "dossier_id": dossier_id,
                "type_action": "verification_documents",
                "contenu": f"{len(manquants)} manquant(s) : {', '.join(noms[:5])}",
                "statut": "ok",
                "metadata": {"nb_manquants": len(manquants)},
            }
        ).execute()
    except Exception as exc:
        logger.error(f"Erreur log journal document_checker : {exc}")


def run(dossier_id: str, dry_run: bool = False) -> DocumentCheckerResult:
    """Vérifie les documents manquants pour un dossier donné.

    Args:
        dossier_id: UUID du dossier à vérifier.
        dry_run: Si True, ne logue pas en base.

    Returns:
        DocumentCheckerResult avec la liste des manquants et des complets.
    """
    logger.info(f"document_checker — dossier {dossier_id}")
    supabase = get_supabase_client()

    dossier = fetch_dossier(supabase, dossier_id)
    if dossier is None:
        return DocumentCheckerResult(
            dossier_id=dossier_id,
            contact_id=None,
            type_dossier="inconnu",
            manquants=[],
            complets=[],
            erreur=f"Dossier {dossier_id} introuvable",
        )

    type_dossier = dossier.get("type", "")
    contact_id = dossier.get("contact_id")
    raw_deadline = dossier.get("deadline")

    attendus = DOCUMENTS_ATTENDUS.get(type_dossier)
    if attendus is None:
        return DocumentCheckerResult(
            dossier_id=dossier_id,
            contact_id=contact_id,
            type_dossier=type_dossier,
            manquants=[],
            complets=[],
            erreur=f"Type dossier inconnu : {type_dossier}",
        )

    deadline: date | None = None
    if raw_deadline:
        try:
            deadline = date.fromisoformat(str(raw_deadline))
        except ValueError:
            pass

    presents = set(fetch_documents_presents(supabase, dossier_id))
    manquants: list[DocumentManquant] = []
    complets: list[str] = []

    for type_doc in attendus:
        if type_doc in presents:
            complets.append(type_doc)
        else:
            urgence = _compute_urgence(deadline)
            dl_str = deadline.isoformat() if deadline else None
            manquants.append(
                DocumentManquant(
                    nom_document=type_doc.replace("_", " ").title(),
                    type_document=type_doc,
                    deadline=dl_str,
                    urgence=urgence,
                )
            )

    log_journal(supabase, contact_id, dossier_id, manquants, dry_run=dry_run)

    logger.info(
        f"document_checker : {len(manquants)} manquant(s), "
        f"{len(complets)} complet(s) pour dossier {dossier_id}"
    )
    return DocumentCheckerResult(
        dossier_id=dossier_id,
        contact_id=contact_id,
        type_dossier=type_dossier,
        manquants=manquants,
        complets=complets,
        erreur=None,
    )

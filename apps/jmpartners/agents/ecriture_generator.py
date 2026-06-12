"""Agent ecriture_generator — génération d'écritures comptables depuis analyse_ia.

Lit documents.analyse_ia, mappe automatiquement les comptes :
  - facture_achat  → 401 (fournisseur) / 60x (charges) / 44566 (TVA déductible)
  - facture_vente  → 411 (client) / 70x (produits) / 44571 (TVA collectée)
  - releve_bancaire → 512 (banque) / 5xx

Insère les écritures équilibrées dans `ecritures` + logue dans `journaux`.
"""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = [
    "EcritureGeneratorResult",
    "_build_ecritures_facture_achat",
    "_build_ecritures_facture_vente",
    "_build_ecritures_releve",
    "get_supabase_client",
    "run",
]

logger = logging.getLogger(__name__)

# Types de documents supportés avec leur mappage
_SUPPORTED_TYPES = {"facture_achat", "facture_vente", "releve_bancaire"}

_JOURNAL_MAP = {
    "facture_achat": "ACH",
    "facture_vente": "VEN",
    "releve_bancaire": "BQ",
}
_CONFIDENCE_THRESHOLD = 0.85


def _compute_score_confiance(analyse: dict) -> float:
    """Heuristic: ratio of non-empty fields out of key fields."""
    key_fields = ["tiers", "montants", "dates", "references", "tva"]
    filled = sum(1 for f in key_fields if analyse.get(f))
    return round(filled / len(key_fields), 2)


class EcritureGeneratorResult(TypedDict):
    document_id: str
    ecritures: list[dict]
    statut: str  # "ok" | "erreur" | "non_supporte"
    erreur: str | None


# ── Client Supabase ───────────────────────────────────────────────────────────

def get_supabase_client():  # type: ignore[return]
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
    return create_client(url, key)


# ── Builders d'écritures ──────────────────────────────────────────────────────

def _build_ecritures_facture_achat(analyse: dict, date: str) -> list[dict]:
    """Mappe une facture achat : 60x/44566 au débit, 401 au crédit."""
    tva_info = analyse.get("tva") or {}
    tiers = (analyse.get("tiers") or ["Fournisseur"])[0]
    references = analyse.get("references") or []
    ref = references[0] if references else ""

    montant_ttc: float = 0.0
    montant_ht: float = 0.0
    montant_tva: float = 0.0

    if tva_info and tva_info.get("montant_ttc") is not None:
        montant_ttc = float(tva_info["montant_ttc"])
        montant_ht = float(tva_info.get("montant_ht") or 0)
        montant_tva = float(tva_info.get("montant_tva") or 0)
    else:
        for m in analyse.get("montants", []):
            if "ttc" in m.get("libelle", "").lower() or "total" in m.get("libelle", "").lower():
                montant_ttc = float(m["montant"])
                break
        montant_ht = montant_ttc

    ecritures = [
        {
            "compte": "401",
            "libelle": f"Fournisseur {tiers} — {ref}".strip(" —"),
            "date": date,
            "credit": montant_ttc,
            "debit": None,
        },
        {
            "compte": "6070",
            "libelle": f"Achat marchandises {ref}".strip(),
            "date": date,
            "debit": montant_ht,
            "credit": None,
        },
    ]

    if montant_tva and montant_tva > 0:
        ecritures.append({
            "compte": "44566",
            "libelle": f"TVA déductible {ref}".strip(),
            "date": date,
            "debit": montant_tva,
            "credit": None,
        })

    return ecritures


def _build_ecritures_facture_vente(analyse: dict, date: str) -> list[dict]:
    """Mappe une facture vente : 411 au débit, 70x/44571 au crédit."""
    tva_info = analyse.get("tva") or {}
    tiers = (analyse.get("tiers") or ["Client"])[0]
    references = analyse.get("references") or []
    ref = references[0] if references else ""

    montant_ttc: float = 0.0
    montant_ht: float = 0.0
    montant_tva: float = 0.0

    if tva_info and tva_info.get("montant_ttc") is not None:
        montant_ttc = float(tva_info["montant_ttc"])
        montant_ht = float(tva_info.get("montant_ht") or 0)
        montant_tva = float(tva_info.get("montant_tva") or 0)
    else:
        for m in analyse.get("montants", []):
            if "ttc" in m.get("libelle", "").lower() or "total" in m.get("libelle", "").lower():
                montant_ttc = float(m["montant"])
                break
        montant_ht = montant_ttc

    ecritures = [
        {
            "compte": "411",
            "libelle": f"Client {tiers} — {ref}".strip(" —"),
            "date": date,
            "debit": montant_ttc,
            "credit": None,
        },
        {
            "compte": "7070",
            "libelle": f"Vente marchandises {ref}".strip(),
            "date": date,
            "credit": montant_ht,
            "debit": None,
        },
    ]

    if montant_tva and montant_tva > 0:
        ecritures.append({
            "compte": "44571",
            "libelle": f"TVA collectée {ref}".strip(),
            "date": date,
            "credit": montant_tva,
            "debit": None,
        })

    return ecritures


def _build_ecritures_releve(analyse: dict, date: str) -> list[dict]:
    """Mappe un relevé bancaire : 512 débit solde + compte de passage crédit."""
    solde: float = 0.0
    for m in analyse.get("montants", []):
        libelle = m.get("libelle", "").lower()
        if "solde" in libelle or "final" in libelle or "total" in libelle:
            solde = abs(float(m["montant"]))
            break
    if not solde:
        montants = analyse.get("montants", [])
        solde = abs(float(montants[0]["montant"])) if montants else 0.0

    tiers = (analyse.get("tiers") or ["Banque"])[0]

    ecritures = [
        {
            "compte": "512",
            "libelle": f"Banque {tiers} — relevé {date}",
            "date": date,
            "debit": solde,
            "credit": None,
        },
        {
            "compte": "580",
            "libelle": f"Virement interne — relevé {date}",
            "date": date,
            "credit": solde,
            "debit": None,
        },
    ]

    return ecritures


_BUILDERS = {
    "facture_achat": _build_ecritures_facture_achat,
    "facture_vente": _build_ecritures_facture_vente,
    "releve_bancaire": _build_ecritures_releve,
}


def _enrich_ecritures(ecritures: list[dict], type_doc: str, analyse: dict, montant_ttc: float) -> list[dict]:
    """Injecte journal, reference, montant_ttc, source, score_confiance, statut."""
    journal = _JOURNAL_MAP.get(type_doc, "")
    references = analyse.get("references") or []
    reference = references[0] if references else ""
    score = _compute_score_confiance(analyse)
    statut = "valide" if score >= _CONFIDENCE_THRESHOLD else "a_valider"
    enriched = []
    for e in ecritures:
        enriched.append({
            **e,
            "journal": journal,
            "reference": reference,
            "montant_ttc": montant_ttc,
            "source": "ia",
            "score_confiance": score,
            "statut": statut,
        })
    return enriched


# ── Persistance ───────────────────────────────────────────────────────────────

def _insert_ecritures(supabase, dossier_id: str, document_id: str, ecritures: list[dict]) -> None:
    rows = [
        {**e, "dossier_id": dossier_id, "document_id": document_id}
        for e in ecritures
    ]
    supabase.table("ecritures").insert(rows).execute()


def _log_journal(supabase, dossier_id: str, document_id: str, nb: int, type_doc: str) -> None:
    supabase.table("journaux").insert({
        "dossier_id": dossier_id,
        "type_action": "ecritures_generees",
        "statut": "ok",
        "contenu": f"{nb} écriture(s) générée(s) — {type_doc} — doc {document_id}",
        "metadata": {"document_id": document_id, "nb_ecritures": nb, "type_document": type_doc},
    }).execute()


# ── Point d'entrée ────────────────────────────────────────────────────────────

def run(document_id: str, dry_run: bool = False) -> EcritureGeneratorResult:
    """Génère les écritures comptables depuis analyse_ia du document.

    Args:
        document_id: UUID du document dans la table documents.
        dry_run: Si True, calcule les écritures sans insérer en base.

    Returns:
        EcritureGeneratorResult avec la liste des écritures générées.
    """
    logger.info(f"ecriture_generator — document {document_id}")

    try:
        supabase = get_supabase_client()
    except Exception as exc:
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="erreur", erreur=str(exc)
        )

    # 1. Lecture du document avec son analyse_ia
    try:
        resp = (
            supabase.table("documents")
            .select("id, dossier_id, type_document, analyse_ia")
            .eq("id", document_id)
            .single()
            .execute()
        )
        doc = resp.data
    except Exception as exc:
        logger.error(f"ecriture_generator — lecture document {document_id} : {exc}")
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="erreur",
            erreur=f"Lecture document échouée : {exc}",
        )

    if not doc:
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="erreur",
            erreur=f"Document {document_id} introuvable",
        )

    analyse = doc.get("analyse_ia")
    if not analyse:
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="erreur",
            erreur="analyse_ia absent — lancer document_analyzer d'abord",
        )

    type_doc = analyse.get("type_document") or doc.get("type_document") or ""
    dossier_id = doc.get("dossier_id", "")

    # 2. Vérification du type supporté
    if type_doc not in _SUPPORTED_TYPES:
        logger.info(f"ecriture_generator — type non supporté : {type_doc}")
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="non_supporte", erreur=None,
        )

    # 3. Génération des écritures
    dates = analyse.get("dates") or []
    date = dates[0] if dates else "2026-01-01"
    builder = _BUILDERS[type_doc]

    try:
        ecritures = builder(analyse, date)
        # Compute montant_ttc for enrichment (re-derive from built rows)
        _ttc = 0.0
        for e in ecritures:
            if e.get("debit") and e.get("compte", "").startswith(("411", "401")):
                _ttc = float(e["debit"] or 0)
                break
            if e.get("credit") and e.get("compte", "").startswith(("411", "401")):
                _ttc = float(e["credit"] or 0)
                break
        ecritures = _enrich_ecritures(ecritures, type_doc, analyse, _ttc)
    except Exception as exc:
        logger.error(f"ecriture_generator — génération échouée {document_id} : {exc}")
        return EcritureGeneratorResult(
            document_id=document_id, ecritures=[], statut="erreur",
            erreur=f"Génération écritures échouée : {exc}",
        )

    logger.info(
        f"ecriture_generator — {len(ecritures)} écriture(s) générée(s) pour {document_id}"
    )

    # 4. Persistance (sauf dry_run)
    if not dry_run:
        try:
            _insert_ecritures(supabase, dossier_id, document_id, ecritures)
            _log_journal(supabase, dossier_id, document_id, len(ecritures), type_doc)
        except Exception as exc:
            logger.warning(f"ecriture_generator — persistance échouée {document_id} : {exc}")

    return EcritureGeneratorResult(
        document_id=document_id,
        ecritures=ecritures,
        statut="ok",
        erreur=None,
    )

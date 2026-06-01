"""Orchestrateur CIHAN — chaîne documentaire complète pour le dossier pilote."""

from __future__ import annotations

import logging
from typing import TypedDict

from apps.jmpartners.agents.collecte_agent import CollecteAgent
from apps.jmpartners.agents.ged_agent import GEDAgent
from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent
from apps.jmpartners.agents.ocr_agent import OCRAgent
from apps.jmpartners.agents.presaisie_agent import PresaisieAgent
from apps.jmpartners.agents.revision_agent import RevisionAgent
from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent
from apps.jmpartners.agents.tri_classification_agent import TriClassificationAgent
from apps.jmpartners.agents.verificateur_agent import VerificateurAgent

__all__ = ["CIHANOrchestratorResult", "run"]

logger = logging.getLogger(__name__)


class CIHANOrchestratorResult(TypedDict):
    """Résultat d'un cycle complet de l'orchestrateur CIHAN."""

    collecte: dict | None
    ocr: dict | None
    tri: dict | None
    presaisie: dict | None
    verificateur: dict | None
    ged: dict | None
    rpa_sage: dict | None
    miroir_sage: dict | None
    revision: dict | None
    erreurs: list[str]


def run(
    dry_run: bool = False,
    cabinet_id: str = "jmpartners",
    dossier_id: str = "",
) -> CIHANOrchestratorResult:
    """Exécute la chaîne documentaire CIHAN complète.

    Ordre : collecte → OCR → tri → présaisie → vérificateur → GED
            → RPA Sage → miroir Sage → révision

    Args:
        dry_run: Si True, simule sans effet de bord.
        cabinet_id: Identifiant du cabinet.
        dossier_id: Identifiant du dossier CIHAN.

    Returns:
        CIHANOrchestratorResult avec le résultat de chaque agent.
    """
    logger.info(f"Orchestrateur CIHAN — démarrage (dry_run={dry_run})")
    erreurs: list[str] = []

    results: dict = {
        "collecte": None,
        "ocr": None,
        "tri": None,
        "presaisie": None,
        "verificateur": None,
        "ged": None,
        "rpa_sage": None,
        "miroir_sage": None,
        "revision": None,
    }

    # 1. Collecte des documents
    try:
        collecte = CollecteAgent(cabinet_id=cabinet_id, dossier_id=dossier_id)
        results["collecte"] = collecte.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur collecte : {exc}")
        erreurs.append(f"collecte: {exc}")

    # 2. OCR
    try:
        ocr = OCRAgent(cabinet_id=cabinet_id)
        results["ocr"] = ocr.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur ocr : {exc}")
        erreurs.append(f"ocr: {exc}")

    # 3. Tri et classification
    try:
        tri = TriClassificationAgent(cabinet_id=cabinet_id)
        results["tri"] = tri.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur tri : {exc}")
        erreurs.append(f"tri: {exc}")

    # 4. Présaisie comptable
    try:
        presaisie = PresaisieAgent(cabinet_id=cabinet_id)
        results["presaisie"] = presaisie.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur presaisie : {exc}")
        erreurs.append(f"presaisie: {exc}")

    # 5. Vérification des écritures
    try:
        verificateur = VerificateurAgent(cabinet_id=cabinet_id)
        results["verificateur"] = verificateur.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur verificateur : {exc}")
        erreurs.append(f"verificateur: {exc}")

    # 6. Archivage GED
    try:
        ged = GEDAgent(cabinet_id=cabinet_id)
        results["ged"] = ged.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur ged : {exc}")
        erreurs.append(f"ged: {exc}")

    # Cycle nocturne : RPA Sage → Miroir Sage → Révision
    # 7. RPA Sage
    try:
        rpa = RPASageAgent(cabinet_id=cabinet_id)
        results["rpa_sage"] = rpa.run(mode="stub" if dry_run else "real")
    except Exception as exc:
        logger.error(f"CIHAN — erreur rpa_sage : {exc}")
        erreurs.append(f"rpa_sage: {exc}")

    # 8. Miroir Sage
    try:
        miroir = MiroirSageAgent(cabinet_id=cabinet_id)
        results["miroir_sage"] = miroir.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur miroir_sage : {exc}")
        erreurs.append(f"miroir_sage: {exc}")

    # 9. Révision
    try:
        revision = RevisionAgent(cabinet_id=cabinet_id)
        results["revision"] = revision.run()
    except Exception as exc:
        logger.error(f"CIHAN — erreur revision : {exc}")
        erreurs.append(f"revision: {exc}")

    logger.info(f"Orchestrateur CIHAN — cycle terminé ({len(erreurs)} erreurs)")

    return CIHANOrchestratorResult(
        collecte=results["collecte"],
        ocr=results["ocr"],
        tri=results["tri"],
        presaisie=results["presaisie"],
        verificateur=results["verificateur"],
        ged=results["ged"],
        rpa_sage=results["rpa_sage"],
        miroir_sage=results["miroir_sage"],
        revision=results["revision"],
        erreurs=erreurs,
    )

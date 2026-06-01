"""Agent rpa_sage_agent — intégration RPA avec Sage (stub ou réel)."""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = ["RPASageAgent", "RPASageResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class RPASageResult(TypedDict):
    """Résultat du RPA Sage."""

    mode: str
    ecritures_importees: int
    ecritures_rejetes: int
    next_agent: str
    erreurs: list[str]
    details: list[dict]


class RPASageAgent:
    """Importe les écritures vérifiées dans Sage via RPA (ou stub en dev)."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _import_stub(self, ecritures: list[dict]) -> dict:
        """Simule l'import Sage en mode stub.

        Returns:
            Dict avec importees et rejetes.
        """
        logger.info(f"rpa_sage_agent (stub) — simulation import {len(ecritures)} écritures")
        return {
            "importees": len(ecritures),
            "rejetes": 0,
            "details": [{"id": e.get("id"), "statut": "imported_stub"} for e in ecritures],
        }

    def _import_real(self, ecritures: list[dict]) -> dict:
        """Import réel via l'API Sage (à implémenter).

        Returns:
            Dict avec importees et rejetes.
        """
        raise NotImplementedError("Import Sage réel non implémenté")

    def run(self, mode: str = "stub") -> RPASageResult:
        """Importe les écritures vérifiées dans Sage.

        Args:
            mode: "stub" (simulation) ou "real" (production).

        Returns:
            RPASageResult avec next_agent="miroir_sage_agent" après l'import.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []

        resp = (
            supabase.table("ecritures_proposees")
            .select("id, journal, compte_debit, compte_credit, montant, libelle")
            .eq("statut", "verifie")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        ecritures = resp.data or []
        logger.info(f"rpa_sage_agent — {len(ecritures)} écritures à importer (mode={mode})")

        if mode == "stub":
            import_result = self._import_stub(ecritures)
        else:
            try:
                import_result = self._import_real(ecritures)
            except Exception as exc:
                logger.error(f"rpa_sage_agent — erreur import réel : {exc}")
                erreurs.append(str(exc))
                import_result = {"importees": 0, "rejetes": 0, "details": []}

        # Mettre à jour les statuts
        for ecriture in ecritures:
            try:
                supabase.table("ecritures_proposees").update({
                    "statut": "importe_sage" if mode == "stub" else "importe",
                }).eq("id", ecriture["id"]).execute()
            except Exception as exc:
                erreurs.append(f"Update {ecriture['id']}: {exc}")

        return RPASageResult(
            mode=mode,
            ecritures_importees=import_result.get("importees", 0),
            ecritures_rejetes=import_result.get("rejetes", 0),
            next_agent="miroir_sage_agent",
            erreurs=erreurs,
            details=import_result.get("details", []),
        )

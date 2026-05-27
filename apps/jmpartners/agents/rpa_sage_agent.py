"""Agent RPA Sage stub — saisie fantôme dans Sage (JM Partners)."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TypedDict

from supabase import Client, create_client

__all__ = ["RPASageResult", "RPASageAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class RPASageResult(TypedDict):
    mode: str  # "fantome" | "reel" | "stub"
    ecritures_a_saisir: int
    ecritures_saisies: int
    erreurs: list[str]
    next_agent: str  # always "miroir_sage_agent"


class RPASageAgent:
    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, mode: str = "stub") -> RPASageResult:
        """
        mode="stub": reads ecritures statut="a_saisir_sage", logs intent, returns simulated result.
        mode="fantome"/"reel": not implemented, logs warning, returns empty result with mode set.
        Always: next_agent="miroir_sage_agent"
        """
        if mode == "stub":
            sb = self._get_supabase()
            resp = sb.table("ecritures").select("*").eq("statut", "a_saisir_sage").execute()
            rows = resp.data or []
            nb = len(rows)

            self._log_journal(sb, mode, nb)

            return RPASageResult(
                mode="stub",
                ecritures_a_saisir=nb,
                ecritures_saisies=0,
                erreurs=[],
                next_agent="miroir_sage_agent",
            )

        # mode="fantome" ou "reel" : non implémenté
        logger.warning("RPASageAgent mode='%s' non implémenté — Power Automate Desktop requis.", mode)
        return RPASageResult(
            mode=mode,
            ecritures_a_saisir=0,
            ecritures_saisies=0,
            erreurs=[],
            next_agent="miroir_sage_agent",
        )

    def _log_journal(self, sb: Client, mode: str, nb_ecritures: int) -> None:
        try:
            sb.table("journaux").insert(
                {
                    "action": "rpa_sage_stub",
                    "mode": mode,
                    "nb_ecritures": nb_ecritures,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erreur journaux insert rpa_sage: %s", exc)

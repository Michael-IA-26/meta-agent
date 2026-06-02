"""
Adaptateur Sage Desktop (Power Automate / RPA).
Délègue à RPASageAgent et MiroirSageAgent existants.
"""
from __future__ import annotations

import logging

from apps.jmpartners.backends.base import (
    ComptaBackend,
    EcritureComptable,
    FECData,
    SyncResult,
)

logger = logging.getLogger(__name__)


class SageBackend(ComptaBackend):
    """
    Adaptateur Sage Desktop (Power Automate / RPA).
    Délègue à RPASageAgent et MiroirSageAgent existants.
    """

    def sync_ecritures(
        self,
        ecritures: list[EcritureComptable],
        dry_run: bool = False,
    ) -> SyncResult:
        from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent

        mode = "stub"  # "reel" quand Power Automate dispo
        result = RPASageAgent().run(mode=mode)
        return SyncResult(
            backend="sage",
            ecritures_envoyees=len(ecritures),
            ecritures_ok=result["ecritures_saisies"],
            ecritures_erreur=len(result["erreurs"]),
            erreurs=result["erreurs"],
        )

    def get_fec(self, dossier_id: str) -> FECData:
        from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent

        raw = MiroirSageAgent()._sync_fec()
        return FECData(
            lignes=[],           # FEC complet non exposé par _sync_fec — Sprint 4
            date_export=raw.get("date_sync", ""),
            hash_md5="",
        )

    def health_check(self) -> bool:
        try:
            from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent

            RPASageAgent()
            return True
        except Exception as exc:
            logger.warning("SageBackend.health_check failed: %s", exc)
            return False

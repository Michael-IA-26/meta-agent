"""
Adaptateur MyUnisoft (API REST).
TODO Sprint 5 — après déploiement Pennylane.
Docs API : https://dev.myunisoft.fr
Auth : MYUNISOFT_API_KEY + MYUNISOFT_SOCIETY_ID (Doppler)
Effort estimé : 1-2 semaines.
"""
from __future__ import annotations

from apps.jmpartners.backends.base import (
    ComptaBackend,
    EcritureComptable,
    FECData,
    SyncResult,
)


class MyUnisoftBackend(ComptaBackend):
    """
    Adaptateur MyUnisoft (API REST).
    TODO Sprint 5 — après déploiement Pennylane.
    Docs API : https://dev.myunisoft.fr
    Auth : MYUNISOFT_API_KEY + MYUNISOFT_SOCIETY_ID (Doppler)
    Effort estimé : 1-2 semaines.
    """

    def sync_ecritures(
        self,
        ecritures: list[EcritureComptable],
        dry_run: bool = False,
    ) -> SyncResult:
        raise NotImplementedError("MyUnisoftBackend.sync_ecritures — à implémenter Sprint 5")

    def get_fec(self, dossier_id: str) -> FECData:
        raise NotImplementedError("MyUnisoftBackend.get_fec — à implémenter Sprint 5")

    def health_check(self) -> bool:
        raise NotImplementedError("MyUnisoftBackend.health_check — à implémenter Sprint 5")

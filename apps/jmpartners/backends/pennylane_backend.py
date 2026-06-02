"""
Adaptateur Pennylane (API REST).
TODO Sprint 4 — après validation beta JM Partners.
Docs API : https://pennylane.readme.io/reference
Auth : PENNYLANE_API_KEY (Doppler)
Effort estimé : 1-2 semaines.
"""
from __future__ import annotations

from apps.jmpartners.backends.base import (
    ComptaBackend,
    EcritureComptable,
    FECData,
    SyncResult,
)


class PennylaneBackend(ComptaBackend):
    """
    Adaptateur Pennylane (API REST).
    TODO Sprint 4 — après validation beta JM Partners.
    Docs API : https://pennylane.readme.io/reference
    Auth : PENNYLANE_API_KEY (Doppler)
    Effort estimé : 1-2 semaines.
    """

    def sync_ecritures(
        self,
        ecritures: list[EcritureComptable],
        dry_run: bool = False,
    ) -> SyncResult:
        raise NotImplementedError("PennylaneBackend.sync_ecritures — à implémenter Sprint 4")

    def get_fec(self, dossier_id: str) -> FECData:
        raise NotImplementedError("PennylaneBackend.get_fec — à implémenter Sprint 4")

    def health_check(self) -> bool:
        raise NotImplementedError("PennylaneBackend.health_check — à implémenter Sprint 4")

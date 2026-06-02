"""
Adaptateur ACD (Groupe Cegid — API ou SFTP selon version).
TODO sur demande client.
Auth : ACD_API_KEY ou ACD_SFTP_HOST/USER/PASSWORD (Doppler)
Effort estimé : 2-3 semaines (hétérogénéité des versions ACD).
"""
from __future__ import annotations

from apps.jmpartners.backends.base import (
    ComptaBackend,
    EcritureComptable,
    FECData,
    SyncResult,
)


class ACDBackend(ComptaBackend):
    """
    Adaptateur ACD (Groupe Cegid — API ou SFTP selon version).
    TODO sur demande client.
    Auth : ACD_API_KEY ou ACD_SFTP_HOST/USER/PASSWORD (Doppler)
    Effort estimé : 2-3 semaines (hétérogénéité des versions ACD).
    """

    def sync_ecritures(
        self,
        ecritures: list[EcritureComptable],
        dry_run: bool = False,
    ) -> SyncResult:
        raise NotImplementedError("ACDBackend.sync_ecritures — à implémenter sur demande client")

    def get_fec(self, dossier_id: str) -> FECData:
        raise NotImplementedError("ACDBackend.get_fec — à implémenter sur demande client")

    def health_check(self) -> bool:
        raise NotImplementedError("ACDBackend.health_check — à implémenter sur demande client")

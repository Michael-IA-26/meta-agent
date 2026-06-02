"""
Interfaces abstraites pour les backends comptables.
Tout nouveau backend (Pennylane, MyUnisoft, ACD) doit
hériter de ComptaBackend et implémenter ces 3 méthodes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class EcritureComptable(TypedDict):
    """Contrat commun produit par la chaîne documentaire."""
    document_id: str
    dossier_id: str
    journal: str           # ACH | VTE | BQ | OD
    compte_debit: str      # PCG ex: 607000
    compte_credit: str     # PCG ex: 401000
    tiers: str | None
    libelle: str
    montant_ht: float
    montant_tva: float
    montant_ttc: float
    taux_tva: float | None
    statut: str            # a_saisir | saisie | erreur


class SyncResult(TypedDict):
    """Résultat standardisé d'une synchronisation backend."""
    backend: str           # "sage" | "pennylane" | "myunisoft" | "acd"
    ecritures_envoyees: int
    ecritures_ok: int
    ecritures_erreur: int
    erreurs: list[str]


class FECData(TypedDict):
    """FEC normalisé — indépendant du backend."""
    lignes: list[dict]
    date_export: str
    hash_md5: str


class ComptaBackend(ABC):
    """ABC — tout backend doit implémenter ces 3 méthodes."""

    @abstractmethod
    def sync_ecritures(
        self,
        ecritures: list[EcritureComptable],
        dry_run: bool = False,
    ) -> SyncResult:
        """
        Pousse les écritures validées vers le logiciel comptable.
        dry_run=True : simule sans effet de bord.
        """

    @abstractmethod
    def get_fec(self, dossier_id: str) -> FECData:
        """Exporte le FEC depuis le logiciel comptable."""

    @abstractmethod
    def health_check(self) -> bool:
        """Vérifie que le backend est joignable."""

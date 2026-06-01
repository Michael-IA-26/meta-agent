"""Agent verificateur_agent — vérifie l'équilibre débit/crédit des écritures proposées."""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = ["VerificateurAgent", "VerificateurResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

TOLERANCE = 0.01  # Tolérance d'arrondi en EUR


class VerificateurResult(TypedDict):
    """Résultat de la vérification des écritures."""

    ecritures_verifiees: int
    lot_propre: bool
    anomalies: list[dict]
    erreurs: list[str]


class VerificateurAgent:
    """Vérifie que les écritures proposées sont équilibrées (débit = crédit)."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def run(self) -> VerificateurResult:
        """Vérifie l'équilibre D/C des écritures proposées.

        Returns:
            VerificateurResult avec lot_propre=True si tout est équilibré.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []
        anomalies: list[dict] = []

        resp = (
            supabase.table("ecritures_proposees")
            .select("id, journal, compte_debit, compte_credit, montant, statut")
            .eq("statut", "proposee")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        ecritures = resp.data or []
        logger.info(f"verificateur_agent — {len(ecritures)} écritures à vérifier")

        # Calcul du total débit et crédit
        total_debit = 0.0
        total_credit = 0.0

        for ecriture in ecritures:
            montant = float(ecriture.get("montant", 0) or 0)
            compte_debit = ecriture.get("compte_debit", "")
            compte_credit = ecriture.get("compte_credit", "")

            if compte_debit:
                total_debit += montant
            if compte_credit:
                total_credit += montant

        # Vérification de l'équilibre
        ecart = abs(total_debit - total_credit)
        lot_propre = ecart <= TOLERANCE

        if not lot_propre:
            anomalies.append({
                "type_anomalie": "desequilibre_dc",
                "total_debit": total_debit,
                "total_credit": total_credit,
                "ecart": ecart,
                "message": f"Déséquilibre D/C : débit={total_debit:.2f}, crédit={total_credit:.2f}, écart={ecart:.2f}",
            })
            logger.warning(
                f"verificateur_agent — déséquilibre D/C : {total_debit:.2f} vs {total_credit:.2f}"
            )
        else:
            logger.info(
                f"verificateur_agent — lot propre : débit={total_debit:.2f} = crédit={total_credit:.2f}"
            )

        # Mettre à jour le statut si propre
        if lot_propre and ecritures:
            ids = [e["id"] for e in ecritures]
            for eid in ids:
                try:
                    supabase.table("ecritures_proposees").update({
                        "statut": "verifie",
                    }).eq("id", eid).execute()
                except Exception as exc:
                    erreurs.append(f"Update {eid}: {exc}")

        return VerificateurResult(
            ecritures_verifiees=len(ecritures),
            lot_propre=lot_propre,
            anomalies=anomalies,
            erreurs=erreurs,
        )

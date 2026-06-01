"""Agent lettrage_agent — lettrage automatique des écritures comptables."""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = ["LettrageAgent", "LettrageResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class LettrageResult(TypedDict):
    """Résultat du lettrage automatique."""

    ecritures_lettrées: int
    paires_trouvees: int
    confiance: float
    type_lettrage: str
    erreurs: list[dict]


class LettrageAgent:
    """Effectue le lettrage automatique des écritures par correspondance exacte."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client

        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def run(self) -> LettrageResult:
        """Effectue le lettrage des écritures non lettrées.

        Returns:
            LettrageResult avec le nombre d'écritures lettrées et la confiance.
        """
        supabase = self._get_supabase()
        erreurs: list[dict] = []
        paires = 0

        resp = (
            supabase.table("ecritures")
            .select("id, montant_ht, montant_ttc, tiers, est_lettree, lettre")
            .eq("est_lettree", False)
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        ecritures = resp.data or []
        logger.info(f"lettrage_agent — {len(ecritures)} écritures non lettrées")

        # Groupement par montant_ttc + tiers pour correspondance exacte
        index: dict[str, list[dict]] = {}
        for e in ecritures:
            key = f"{e.get('montant_ttc', '')}:{e.get('tiers', '')}"
            index.setdefault(key, []).append(e)

        ecritures_lettrées = 0
        confiance = 0.0
        type_lettrage = "exact"

        for key, groupe in index.items():
            if len(groupe) >= 2:
                lettre_code = f"L{paires + 1:04d}"
                for e in groupe[:2]:
                    try:
                        supabase.table("ecritures").update(
                            {"est_lettree": True, "lettre": lettre_code}
                        ).eq("id", e["id"]).execute()
                        ecritures_lettrées += 1
                    except Exception as exc:
                        erreurs.append({"id": e["id"], "erreur": str(exc)})
                paires += 1
                confiance = 1.0

        return LettrageResult(
            ecritures_lettrées=ecritures_lettrées,
            paires_trouvees=paires,
            confiance=confiance,
            type_lettrage=type_lettrage,
            erreurs=erreurs,
        )

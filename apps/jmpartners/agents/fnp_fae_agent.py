"""Agent fnp_fae_agent — gestion des FNP (Factures Non Parvenues) et FAE (Factures à Etablir)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TypedDict

__all__ = ["FNPFAEAgent", "FNPFAEResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Mois de décembre = période de clôture pour les FNP/FAE
MOIS_CLOTURE = 12


class FNPFAEResult(TypedDict):
    """Résultat du traitement FNP/FAE."""

    statut: str
    provisions_creees: int
    mois_traite: int
    annee_traitee: int
    erreurs: list[str]
    details: list[dict]


class FNPFAEAgent:
    """Crée les provisions FNP/FAE en fin d'exercice (décembre)."""

    def __init__(
        self, cabinet_id: str = "jmpartners", force_mois: int | None = None
    ) -> None:
        self.cabinet_id = cabinet_id
        self.force_mois = force_mois

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client

        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def run(self) -> FNPFAEResult:
        """Crée les provisions FNP/FAE si on est en décembre (ou force_mois=12).

        Returns:
            FNPFAEResult avec le statut et le nombre de provisions créées.
        """
        now = datetime.now()
        mois = self.force_mois if self.force_mois is not None else now.month
        annee = now.year

        logger.info(f"fnp_fae_agent — mois={mois}, annee={annee}")

        if mois != MOIS_CLOTURE:
            logger.info(
                f"fnp_fae_agent — hors période de clôture (mois={mois}), skip"
            )
            return FNPFAEResult(
                statut="hors_periode",
                provisions_creees=0,
                mois_traite=mois,
                annee_traitee=annee,
                erreurs=[],
                details=[],
            )

        supabase = self._get_supabase()
        erreurs: list[str] = []
        details: list[dict] = []
        provisions = 0

        # Récupérer les documents en attente pouvant générer des FNP
        resp = (
            supabase.table("documents")
            .select("id, nom, type_document, montant_ttc, dossier_id")
            .eq("statut", "en_attente_collaborateur")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        documents = resp.data or []
        logger.info(f"fnp_fae_agent — {len(documents)} documents potentiels FNP/FAE")

        for doc in documents:
            try:
                provision = {
                    "cabinet_id": self.cabinet_id,
                    "dossier_id": doc.get("dossier_id"),
                    "document_id": doc["id"],
                    "type_provision": "FNP",
                    "montant": doc.get("montant_ttc", 0),
                    "exercice": annee,
                    "mois_cloture": mois,
                    "libelle": f"FNP - {doc.get('nom', 'document')}",
                }
                supabase.table("provisions_fnp_fae").insert(provision).execute()
                provisions += 1
                details.append({"document_id": doc["id"], "type": "FNP"})
            except Exception as exc:
                erreurs.append(f"Provision {doc['id']}: {exc}")

        return FNPFAEResult(
            statut="provisions_creees" if provisions > 0 else "aucune_provision",
            provisions_creees=provisions,
            mois_traite=mois,
            annee_traitee=annee,
            erreurs=erreurs,
            details=details,
        )

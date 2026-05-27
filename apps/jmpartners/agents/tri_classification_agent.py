"""Agent tri_classification_agent — classifie les documents après OCR."""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = ["TriClassificationAgent", "TriResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class TriResult(TypedDict):
    """Résultat de la classification des documents."""

    documents_traites: int
    qualifies_auto: int
    en_attente_manuelle: int
    erreurs: list[str]
    details: list[dict]


class TriClassificationAgent:
    """Classifie les documents en statut a_trier et détermine leur type de pièce."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _classifier(self, contenu: dict) -> str:
        """Détermine le type de pièce à partir du contenu extrait.

        Args:
            contenu: Dictionnaire avec siret, montant_ht, montant_ttc, etc.

        Returns:
            Type de pièce : "fournisseur" | "bancaire" | "autre"
        """
        siret = contenu.get("siret")
        montant_ttc = contenu.get("montant_ttc")
        montant_ht = contenu.get("montant_ht")
        type_doc = contenu.get("type_document", "")

        # Règle : si SIRET présent ET montant → fournisseur
        if siret and (montant_ttc or montant_ht):
            return "fournisseur"

        # Règle : si type_document explicite
        if type_doc in ("fournisseur", "bancaire"):
            return type_doc

        # Règle : solde bancaire sans SIRET → bancaire
        solde = contenu.get("solde")
        if solde and not siret:
            return "bancaire"

        return "autre"

    def run(self) -> TriResult:
        """Classifie les documents en statut a_trier.

        Returns:
            TriResult avec le nombre de documents qualifiés automatiquement.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []
        details: list[dict] = []
        qualifies = 0
        en_attente = 0

        resp = (
            supabase.table("documents")
            .select("id, nom_fichier, contenu_extrait")
            .eq("statut", "a_trier")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        documents = resp.data or []
        logger.info(f"tri_classification_agent — {len(documents)} documents à classer")

        for doc in documents:
            doc_id = doc["id"]
            try:
                contenu = doc.get("contenu_extrait") or {}
                type_piece = self._classifier(contenu)

                if type_piece in ("fournisseur", "bancaire"):
                    new_statut = "qualifie"
                    qualifies += 1
                else:
                    new_statut = "en_attente_tri_manuel"
                    en_attente += 1

                supabase.table("documents").update({
                    "statut": new_statut,
                    "type_piece": type_piece,
                }).eq("id", doc_id).execute()

                details.append({
                    "id": doc_id,
                    "type_piece": type_piece,
                    "statut": new_statut,
                })
                logger.info(
                    f"tri_classification_agent — {doc['nom_fichier']} → {type_piece} / {new_statut}"
                )

            except Exception as exc:
                logger.error(f"tri_classification_agent — erreur {doc_id} : {exc}")
                erreurs.append(f"{doc_id}: {exc}")

        return TriResult(
            documents_traites=len(documents),
            qualifies_auto=qualifies,
            en_attente_manuelle=en_attente,
            erreurs=erreurs,
            details=details,
        )

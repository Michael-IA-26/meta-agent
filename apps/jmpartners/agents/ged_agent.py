"""Agent ged_agent — archive les documents validés dans la GED Supabase Storage."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import TypedDict

__all__ = ["GEDAgent", "GEDResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class GEDResult(TypedDict):
    """Résultat de l'archivage GED."""

    documents_archives: int
    documents_ignores: int
    erreurs: list[str]
    details: list[dict]


class GEDAgent:
    """Archive les documents validés dans la GED (Gestion Électronique des Documents)."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _build_archive_path(self, doc: dict) -> str:
        """Construit le chemin d'archivage GED.

        Format : {cabinet_id}/ged/{year}/{month}/{nom_fichier}
        """
        date_reception = doc.get("date_reception")
        if date_reception:
            try:
                if isinstance(date_reception, str):
                    d = date.fromisoformat(date_reception[:10])
                else:
                    d = date_reception
                year = d.year
                month = f"{d.month:02d}"
            except (ValueError, AttributeError):
                today = date.today()
                year = today.year
                month = f"{today.month:02d}"
        else:
            today = date.today()
            year = today.year
            month = f"{today.month:02d}"

        nom = doc.get("nom_fichier", "document.pdf")
        return f"{self.cabinet_id}/ged/{year}/{month}/{nom}"

    def run(self) -> GEDResult:
        """Archive les documents validés.

        Returns:
            GEDResult avec le nombre de documents archivés.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []
        details: list[dict] = []
        archives = 0
        ignores = 0

        resp = (
            supabase.table("documents")
            .select("id, nom_fichier, chemin_stockage, date_reception, type_piece")
            .eq("statut", "valide")
            .eq("cabinet_id", self.cabinet_id)
            .is_("chemin_stockage_ged", "null")
            .execute()
        )
        documents = resp.data or []
        logger.info(f"ged_agent — {len(documents)} documents à archiver")

        for doc in documents:
            doc_id = doc["id"]
            try:
                chemin_source = doc.get("chemin_stockage")

                if not chemin_source:
                    # Pas de fichier source → ignorer
                    ignores += 1
                    logger.debug(f"ged_agent — pas de chemin source pour {doc_id}")
                    continue

                # Construire le chemin GED
                chemin_ged = self._build_archive_path(doc)

                # Télécharger et re-uploader vers chemin GED
                try:
                    pdf_bytes = supabase.storage.from_("documents").download(chemin_source)
                    supabase.storage.from_("documents").upload(
                        chemin_ged, pdf_bytes, {"content-type": "application/pdf"}
                    )
                except Exception as storage_exc:
                    # Si le fichier source n'existe plus, on archive quand même le chemin
                    logger.warning(
                        f"ged_agent — impossible de copier le fichier {doc_id}: {storage_exc}"
                    )
                    chemin_ged = f"{self.cabinet_id}/ged/missing/{doc['nom_fichier']}"

                # Mettre à jour la base
                supabase.table("documents").update({
                    "chemin_stockage_ged": chemin_ged,
                    "statut": "archive",
                }).eq("id", doc_id).execute()

                archives += 1
                details.append({
                    "id": doc_id,
                    "nom_fichier": doc["nom_fichier"],
                    "chemin_ged": chemin_ged,
                })
                logger.info(f"ged_agent — archivé : {doc['nom_fichier']} → {chemin_ged}")

            except Exception as exc:
                logger.error(f"ged_agent — erreur {doc_id} : {exc}")
                erreurs.append(f"{doc_id}: {exc}")

        return GEDResult(
            documents_archives=archives,
            documents_ignores=ignores,
            erreurs=erreurs,
            details=details,
        )

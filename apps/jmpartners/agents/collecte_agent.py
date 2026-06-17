"""Agent collecte_agent — collecte les documents PDF depuis le répertoire Outlook mock."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TypedDict

__all__ = ["CollecteAgent", "CollecteResult", "OUTLOOK_MOCK_DIR"]

logger = logging.getLogger(__name__)

# Répertoire mock Outlook — surchargeable dans les tests
OUTLOOK_MOCK_DIR = os.getenv(
    "OUTLOOK_MOCK_DIR",
    str(Path(__file__).parent.parent.parent.parent / "data" / "outlook_mock"),
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class CollecteResult(TypedDict):
    """Résultat de la collecte de documents."""

    documents_uploades: int
    documents_ignores: int
    erreurs: list[str]
    details: list[dict]


class CollecteAgent:
    """Collecte les PDF depuis le répertoire Outlook mock et les uploade vers Supabase Storage."""

    def __init__(self, cabinet_id: str = "jmpartners", dossier_id: str = "") -> None:
        self.cabinet_id = cabinet_id
        self.dossier_id = dossier_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def run(self, outlook_dir: str | None = None) -> CollecteResult:
        """Collecte les PDFs et les uploade vers Supabase Storage.

        Args:
            outlook_dir: Répertoire source. Si None, utilise OUTLOOK_MOCK_DIR.

        Returns:
            CollecteResult avec le nombre de documents traités.
        """
        # Import ici pour permettre le patch dans les tests
        import apps.jmpartners.agents.collecte_agent as _self_module
        source_dir = Path(outlook_dir or _self_module.OUTLOOK_MOCK_DIR)
        erreurs: list[str] = []
        details: list[dict] = []
        uploades = 0
        ignores = 0

        if not source_dir.exists():
            logger.warning(f"collecte_agent — répertoire introuvable : {source_dir}")
            return CollecteResult(
                documents_uploades=0,
                documents_ignores=0,
                erreurs=[f"Répertoire introuvable : {source_dir}"],
                details=[],
            )

        pdf_files = list(source_dir.glob("*.pdf"))
        logger.info(f"collecte_agent — {len(pdf_files)} PDFs trouvés dans {source_dir}")

        supabase = self._get_supabase()

        for pdf_path in pdf_files:
            try:
                # Vérifier les doublons
                existing = (
                    supabase.table("documents")
                    .select("id")
                    .eq("nom_fichier", pdf_path.name)
                    .eq("cabinet_id", self.cabinet_id)
                    .execute()
                )
                if existing.data:
                    ignores += 1
                    logger.debug(f"collecte_agent — doublon ignoré : {pdf_path.name}")
                    continue

                # Upload vers Storage
                with open(pdf_path, "rb") as f:
                    content = f.read()

                storage_path = f"{self.cabinet_id}/{self.dossier_id}/{pdf_path.name}"
                supabase.storage.from_("documents").upload(
                    storage_path, content, {"content-type": "application/pdf"}
                )

                # Insérer en base
                supabase.table("documents").insert({
                    "cabinet_id": self.cabinet_id,
                    "dossier_id": self.dossier_id or None,
                    "nom_fichier": pdf_path.name,
                    "chemin_stockage": storage_path,
                    "statut": "en_attente_ocr",
                    "source": "outlook_mock",
                }).execute()

                uploades += 1
                details.append({
                    "nom_fichier": pdf_path.name,
                    "storage_path": storage_path,
                    "statut": "en_attente_ocr",
                })
                logger.info(f"collecte_agent — uploadé : {pdf_path.name}")

            except Exception as exc:
                logger.error(f"collecte_agent — erreur {pdf_path.name} : {exc}")
                erreurs.append(f"{pdf_path.name}: {exc}")

        return CollecteResult(
            documents_uploades=uploades,
            documents_ignores=ignores,
            erreurs=erreurs,
            details=details,
        )

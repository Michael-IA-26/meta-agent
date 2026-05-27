"""Agent GED — archivage structuré des documents validés (JM Partners)."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TypedDict, cast

from supabase import Client, create_client

__all__ = ["DocumentArchive", "GEDResult", "GEDAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

CATEGORIE_MAP: dict[str, str] = {
    "fournisseur": "fournisseurs",
    "client": "clients",
    "banque": "banques",
    "fiscal": "fiscal_social",
    "social": "fiscal_social",
}


class DocumentArchive(TypedDict):
    document_id: str
    chemin_archive: str  # [dossier_id]/[YYYY]/[MM]/[type]/[numero_seq]_[nom]
    numero_sequentiel: int
    statut: str  # "archive"


class GEDResult(TypedDict):
    documents_archives: int
    details: list[DocumentArchive]
    erreurs: list[str]


class GEDAgent:
    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _get_categorie(self, type_piece: str) -> str:
        return CATEGORIE_MAP.get(type_piece, "autres")

    def _get_num_seq(self, sb: Client, dossier_id: str, yyyy: str, mm: str) -> int:
        resp = (
            sb.table("documents")
            .select("id")
            .eq("statut", "archive")
            .like("chemin_stockage", f"{dossier_id}/{yyyy}/{mm}/%")
            .execute()
        )
        existing = len(resp.data) if resp.data else 0
        return existing + 1

    def _log_journal(self, sb: Client, document_id: str, chemin: str, action: str) -> None:
        try:
            sb.table("journaux").insert(
                {
                    "document_id": document_id,
                    "action": action,
                    "chemin": chemin,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erreur journaux insert: %s", exc)

    def run(self) -> GEDResult:
        sb = self._get_supabase()
        details: list[DocumentArchive] = []
        erreurs: list[str] = []

        resp = sb.table("documents").select("*").eq("statut", "valide").execute()
        documents = resp.data or []

        for raw_doc in documents:
            doc = cast(dict, raw_doc)
            document_id: str = str(doc.get("id", ""))
            chemin_stockage: str = str(doc.get("chemin_stockage") or "")

            # Déduplication : déjà archivé si chemin_stockage est non vide
            if chemin_stockage:
                logger.info("Document %s déjà archivé (chemin=%s), ignoré.", document_id, chemin_stockage)
                self._log_journal(sb, document_id, chemin_stockage, "ged_deduplicate")
                continue

            nom_fichier: str = str(doc.get("nom_fichier") or "document")
            type_piece: str = str(doc.get("type_piece") or "")
            date_reception_raw: str = str(doc.get("date_reception") or "")
            dossier_id: str = str(doc.get("dossier_id") or "inconnu")

            try:
                date_reception = datetime.fromisoformat(date_reception_raw)
            except (ValueError, TypeError):
                date_reception = datetime.utcnow()

            yyyy = date_reception.strftime("%Y")
            mm = date_reception.strftime("%m")
            categorie = self._get_categorie(type_piece)

            num_seq = self._get_num_seq(sb, dossier_id, yyyy, mm)
            chemin_archive = f"{dossier_id}/{yyyy}/{mm}/{categorie}/{num_seq:04d}_{nom_fichier}"

            # Récupération du contenu depuis le bucket existant
            try:
                existing_path: str = str(doc.get("chemin_stockage_tmp") or nom_fichier)
                file_content_resp = sb.storage.from_("documents").download(existing_path)
                file_content: bytes = (
                    file_content_resp if isinstance(file_content_resp, bytes) else b""
                )
                sb.storage.from_("documents").upload(chemin_archive, file_content)
            except Exception as exc:  # noqa: BLE001
                msg = f"Erreur storage document {document_id}: {exc}"
                logger.error(msg)
                erreurs.append(msg)
                continue

            sb.table("documents").update(
                {
                    "chemin_stockage": chemin_archive,
                    "numero_sequentiel": num_seq,
                    "statut": "archive",
                }
            ).eq("id", document_id).execute()

            self._log_journal(sb, document_id, chemin_archive, "ged_archive")

            archive: DocumentArchive = {
                "document_id": document_id,
                "chemin_archive": chemin_archive,
                "numero_sequentiel": num_seq,
                "statut": "archive",
            }
            details.append(archive)

        return GEDResult(
            documents_archives=len(details),
            details=details,
            erreurs=erreurs,
        )

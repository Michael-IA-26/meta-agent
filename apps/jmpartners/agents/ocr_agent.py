"""Agent OCR #2 — extraction de données comptables via Claude Vision (JM Partners v2.2)."""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, TypedDict, cast

import anthropic
from anthropic.types import ImageBlockParam, TextBlock, TextBlockParam
from supabase import Client, create_client

__all__ = ["DocumentOCR", "OCRAgentResult", "OCRAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SEUIL_CONFIANCE = 0.70

VISION_PROMPT = (
    "Tu es un expert comptable français. Analyse cette pièce jointe et extrais en JSON :\n"
    "{\n"
    '  "type_document": "facture_fournisseur|facture_client|releve_bancaire|autre",\n'
    '  "montant_ht": float|null,\n'
    '  "montant_tva": float|null,\n'
    '  "montant_ttc": float|null,\n'
    '  "date_document": "YYYY-MM-DD"|null,\n'
    '  "tiers_nom": str|null,\n'
    '  "siret": str|null,\n'
    '  "compte_bancaire": str|null,\n'
    '  "reference": str|null,\n'
    '  "score_confiance": float,\n'
    '  "multi_factures": bool,\n'
    '  "fragments": []\n'
    "}\n"
    "Si le document est illisible, scanné de travers ou hors-contexte comptable : score_confiance=0.0.\n"
    "Réponds UNIQUEMENT en JSON valide, sans markdown."
)

MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class DocumentOCR(TypedDict):
    document_id: str
    dossier_id: str | None
    contenu_extrait: dict
    type_document_detecte: str
    score_detection: float
    statut: str
    raison_attente: str | None
    multi_dossiers: bool
    fragments: list[dict]


class OCRAgentResult(TypedDict):
    documents_traites: int
    documents_a_trier: int
    documents_en_attente: int
    details: list[DocumentOCR]
    erreurs: list[str]


class OCRAgent:
    """Agent #2 — extrait les données comptables des documents via Claude Vision."""

    def __init__(self) -> None:
        self._supabase: Client | None = None
        self._anthropic: anthropic.Anthropic | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise EnvironmentError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _get_anthropic(self) -> anthropic.Anthropic:
        if self._anthropic is None:
            if not ANTHROPIC_API_KEY:
                raise EnvironmentError("ANTHROPIC_API_KEY requis")
            self._anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._anthropic

    def run(self, document_ids: list[str] | None = None) -> OCRAgentResult:
        """Traite les documents statut='en_attente_ocr' (ou ceux spécifiés)."""
        supabase = self._get_supabase()
        details: list[DocumentOCR] = []
        erreurs: list[str] = []

        query = supabase.table("documents").select("id, dossier_id, chemin_storage, nom_fichier")
        if document_ids:
            query = query.in_("id", document_ids)
        else:
            query = query.eq("statut", "en_attente_ocr")

        try:
            rows = query.execute().data or []
        except Exception as exc:
            logger.error("ocr_agent — erreur lecture Supabase : %s", exc)
            return OCRAgentResult(
                documents_traites=0,
                documents_a_trier=0,
                documents_en_attente=0,
                details=[],
                erreurs=[str(exc)],
            )

        for raw_row in rows:
            row: dict[str, Any] = cast(dict[str, Any], raw_row)
            document_id: str = str(row["id"])
            dossier_id: str | None = str(row["dossier_id"]) if row.get("dossier_id") else None
            chemin_storage: str = str(row.get("chemin_storage") or "")
            nom_fichier: str = str(row.get("nom_fichier") or "")

            try:
                contenu_binaire: bytes = supabase.storage.from_("documents").download(chemin_storage)

                ocr_result = self._analyser_document(document_id, contenu_binaire, nom_fichier)

                score: float = float(ocr_result.get("score_confiance", 0.0))
                multi_factures: bool = bool(ocr_result.get("multi_factures", False))
                fragments: list[dict] = ocr_result.get("fragments") or []
                multi_dossiers: bool = multi_factures and len(fragments) > 0

                if score >= SEUIL_CONFIANCE:
                    statut = "a_trier"
                    raison_attente: str | None = None
                else:
                    statut = "en_attente_collaborateur"
                    raison_attente = "score_ocr_insuffisant"

                self._update_document(document_id, ocr_result, statut)
                self._log_journal(document_id, statut)

                details.append(
                    DocumentOCR(
                        document_id=document_id,
                        dossier_id=dossier_id,
                        contenu_extrait=ocr_result,
                        type_document_detecte=ocr_result.get("type_document", "autre"),
                        score_detection=score,
                        statut=statut,
                        raison_attente=raison_attente,
                        multi_dossiers=multi_dossiers,
                        fragments=fragments,
                    )
                )

            except Exception as exc:
                erreurs.append(f"{document_id}: {exc}")
                logger.error("ocr_agent — erreur document %s : %s", document_id, exc)

        documents_a_trier = sum(1 for d in details if d["statut"] == "a_trier")
        documents_en_attente = sum(1 for d in details if d["statut"] == "en_attente_collaborateur")

        return OCRAgentResult(
            documents_traites=len(details),
            documents_a_trier=documents_a_trier,
            documents_en_attente=documents_en_attente,
            details=details,
            erreurs=erreurs,
        )

    def _analyser_document(self, document_id: str, contenu_binaire: bytes, nom_fichier: str) -> dict:
        """Appelle Claude Vision, retourne le JSON extrait."""
        client = self._get_anthropic()

        extension = ""
        if "." in nom_fichier:
            extension = "." + nom_fichier.rsplit(".", 1)[-1].lower()
        media_type = MIME_MAP.get(extension, "image/jpeg")

        image_b64 = base64.standard_b64encode(contenu_binaire).decode("utf-8")

        image_block: ImageBlockParam = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": cast(Any, media_type),
                "data": image_b64,
            },
        }
        text_block: TextBlockParam = {
            "type": "text",
            "text": VISION_PROMPT,
        }

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [image_block, text_block],
                }
            ],
        )

        raw_text: str = cast(TextBlock, response.content[0]).text
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("ocr_agent — JSON invalide pour %s : %s", document_id, exc)
            raise ValueError(f"Réponse Claude non JSON pour {document_id}: {raw_text[:200]}") from exc

    def _update_document(self, document_id: str, result: dict, statut: str) -> None:
        """UPDATE documents avec contenu_extrait, type_document_detecte, score_confiance, statut."""
        try:
            self._get_supabase().table("documents").update(
                {
                    "contenu_extrait": result,
                    "type_document_detecte": result.get("type_document", "autre"),
                    "score_confiance": result.get("score_confiance", 0.0),
                    "statut": statut,
                }
            ).eq("id", document_id).execute()
        except Exception as exc:
            logger.error("ocr_agent — erreur mise à jour document %s : %s", document_id, exc)
            raise

    def _log_journal(self, document_id: str, statut: str) -> None:
        """INSERT dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "agent": "ocr_agent",
                    "action": "ocr_extraction",
                    "statut": statut,
                    "document_id": document_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            logger.warning("ocr_agent — log journal échoué : %s", exc)

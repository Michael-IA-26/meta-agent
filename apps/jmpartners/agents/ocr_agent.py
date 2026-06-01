"""Agent ocr_agent — extrait le contenu des PDFs via Claude Vision (Anthropic)."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import TypedDict

__all__ = ["OCRAgent", "OCRResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

OCR_SCORE_SEUIL = 0.7  # Score minimum pour passer en tri


class OCRResult(TypedDict):
    """Résultat de l'extraction OCR."""

    documents_traites: int
    documents_a_trier: int
    documents_en_attente: int
    erreurs: list[str]
    details: list[dict]


class OCRAgent:
    """Extrait le contenu textuel des PDFs via Claude Vision et met à jour Supabase."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _get_anthropic(self):
        """Retourne un client Anthropic (mockable dans les tests)."""
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def _extract_pdf_content(self, supabase, storage_path: str) -> bytes:
        """Télécharge un PDF depuis Supabase Storage."""
        return supabase.storage.from_("documents").download(storage_path)

    def _ocr_with_claude(self, client, pdf_bytes: bytes) -> dict:
        """Envoie le PDF à Claude Vision pour extraction OCR."""
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode()

        prompt = """Extrayez le contenu de ce document PDF.
Retournez un JSON avec les champs :
- type_document: "fournisseur" | "bancaire" | "multi" | "autre"
- siret: string ou null
- montant_ht: string ou null
- montant_ttc: string ou null
- taux_tva: number ou null
- score_confiance: float entre 0 et 1
- multi_factures: boolean
- fragments: liste de dict si multi_factures=True
- texte_brut: string
"""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        text = response.content[0].text
        # Extraire le JSON de la réponse
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "type_document": "autre",
            "score_confiance": 0.0,
            "multi_factures": False,
            "texte_brut": text,
        }

    def run(self) -> OCRResult:
        """Traite les documents en statut en_attente_ocr.

        Returns:
            OCRResult avec le nombre de documents traités.
        """
        supabase = self._get_supabase()
        anthropic_client = self._get_anthropic()
        erreurs: list[str] = []
        details: list[dict] = []
        a_trier = 0
        en_attente = 0

        # Récupérer les documents à traiter
        resp = (
            supabase.table("documents")
            .select("id, nom_fichier, chemin_stockage")
            .eq("statut", "en_attente_ocr")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        documents = resp.data or []
        logger.info(f"ocr_agent — {len(documents)} documents à traiter")

        for doc in documents:
            doc_id = doc["id"]
            try:
                # Télécharger le PDF
                pdf_bytes = self._extract_pdf_content(supabase, doc["chemin_stockage"])

                # OCR avec Claude
                ocr_result = self._ocr_with_claude(anthropic_client, pdf_bytes)
                score = ocr_result.get("score_confiance", 0.0)
                multi = ocr_result.get("multi_factures", False)

                if score >= OCR_SCORE_SEUIL:
                    new_statut = "a_trier"
                    a_trier += 1
                else:
                    new_statut = "en_attente_validation"
                    en_attente += 1

                # Mettre à jour Supabase
                supabase.table("documents").update({
                    "statut": new_statut,
                    "contenu_extrait": ocr_result,
                    "score_ocr": score,
                }).eq("id", doc_id).execute()

                detail = {
                    "id": doc_id,
                    "statut": new_statut,
                    "score_confiance": score,
                    "multi_dossiers": multi,
                }
                if multi:
                    detail["fragments"] = ocr_result.get("fragments", [])
                details.append(detail)
                logger.info(f"ocr_agent — {doc['nom_fichier']} → {new_statut} (score={score})")

            except Exception as exc:
                logger.error(f"ocr_agent — erreur {doc_id} : {exc}")
                erreurs.append(f"{doc_id}: {exc}")

        return OCRResult(
            documents_traites=len(documents),
            documents_a_trier=a_trier,
            documents_en_attente=en_attente,
            erreurs=erreurs,
            details=details,
        )

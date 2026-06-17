"""Document analyzer with prompt caching, image downscaling, and hash-based cache."""

from __future__ import annotations

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

MAX_PAGES = 3
MAX_IMAGE_PX = 1568

STATIC_SYSTEM_PROMPT = (
    "Tu es un expert-comptable français. Analyse le document fourni et extrais "
    "les informations comptables suivantes au format JSON : type de document, "
    "date, montant HT, montant TTC, TVA, fournisseur/client, numéro de pièce, "
    "journal comptable (ACH/VEN/BQ/OD), comptes débit et crédit suggérés selon "
    "le plan comptable général français. Réponds UNIQUEMENT en JSON valide."
)


def truncate_pdf(pages: list[bytes]) -> list[bytes]:
    """Return at most MAX_PAGES pages from a PDF."""
    return pages[:MAX_PAGES]


def resize_image_if_needed(image_bytes: bytes) -> bytes:
    """Resize an image to at most MAX_IMAGE_PX in each dimension if needed."""
    buf_in = io.BytesIO(image_bytes)
    img = Image.open(buf_in)
    if img.size[0] > MAX_IMAGE_PX or img.size[1] > MAX_IMAGE_PX:
        img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
    buf_out = io.BytesIO()
    img.save(buf_out, format=img.format or "JPEG")
    return buf_out.getvalue()


class DocumentAnalyzer:
    """Analyze accounting documents using Claude with prompt caching."""

    def __init__(self, anthropic_client, db_client=None) -> None:
        self.anthropic_client = anthropic_client
        self.db_client = db_client

    def analyze(self, content: bytes, content_type: str, content_hash: str) -> str:
        """Analyze a document, using cached result if available."""
        if self.db_client:
            cached = (
                self.db_client.table("documents")
                .select("analyse_ia")
                .eq("content_hash", content_hash)
                .execute()
            )
            if cached.data:
                cached_result = cached.data[0].get("analyse_ia")
                if cached_result:
                    logger.info("Cache hit for hash %s", content_hash)
                    return cached_result

        system = [
            {
                "type": "text",
                "text": STATIC_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        import base64

        encoded = base64.standard_b64encode(content).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document" if "pdf" in content_type else "text",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": encoded,
                        },
                    }
                    if "pdf" in content_type or "image" in content_type
                    else {
                        "type": "text",
                        "text": content.decode("utf-8", errors="replace"),
                    },
                ],
            }
        ]

        response = self.anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=messages,
        )

        return response.content[0].text

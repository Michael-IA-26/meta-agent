"""Agent document_analyzer — extraction IA de documents via Claude Sonnet 4.6.

Télécharge un document (PDF ou image) depuis Supabase Storage, l'envoie à Claude
pour extraction structurée (montants, dates, tiers, références, TVA), puis stocke
le résultat dans documents.analyse_ia et passe le statut à 'analysé'.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import TypedDict

__all__ = [
    "AnalyseIA",
    "DocumentAnalyzerResult",
    "_detect_media_type",
    "get_anthropic_client",
    "get_supabase_client",
    "run",
]

logger = logging.getLogger(__name__)

# Descriptions métier par type de document (injectées dans le prompt Claude)
_DOC_DESCRIPTIONS: dict[str, str] = {
    "facture_achat": "facture fournisseur (achat) — extrais fournisseur, montants HT/TVA/TTC, date, numéro de facture",
    "facture_vente": "facture client (vente) — extrais client, montants HT/TVA/TTC, date, numéro de facture",
    "releve_bancaire": "relevé bancaire — extrais IBAN, solde final, période, banque",
    "grand_livre": "grand livre comptable — extrais période, total débits/crédits par compte",
    "balance": "balance comptable — extrais date arrêtée, totaux actif/passif",
    "bilan_n_1": "bilan comptable N-1 — extrais date clôture, total actif, capitaux propres, résultat",
    "resultat_comptable": "compte de résultat — extrais chiffre d'affaires, résultat net, exercice",
    "liasse_fiscale": "liasse fiscale IS (formulaire 2065) — extrais IS dû, exercice, SIREN",
    "bulletin_salaire": "bulletin de salaire — extrais salarié, salaire brut, net à payer, mois",
    "contrat_travail": "contrat de travail — extrais salarié, type contrat, date embauche, salaire brut",
}

_EXTRACTION_PROMPT = """\
Tu es un assistant comptable expert. Analyse ce document de type « {type_document} » \
({description}).

Retourne UNIQUEMENT un objet JSON valide avec exactement cette structure :
{{
  "type_document": "{type_document}",
  "montants": [
    {{"libelle": "...", "montant": <float>, "devise": "EUR"}}
  ],
  "dates": ["YYYY-MM-DD"],
  "tiers": ["nom du tiers ou partenaire"],
  "references": ["numéro de facture ou de référence"],
  "tva": {{
    "taux": <int ou null>,
    "montant_ht": <float ou null>,
    "montant_tva": <float ou null>,
    "montant_ttc": <float ou null>
  }} ou null si pas de TVA,
  "resume": "une ligne résumant le document"
}}

Pas d'explication, juste le JSON."""


class AnalyseIA(TypedDict):
    """Résultat structuré d'une extraction IA."""

    type_document: str
    montants: list[dict]
    dates: list[str]
    tiers: list[str]
    references: list[str]
    tva: dict | None
    resume: str


class DocumentAnalyzerResult(TypedDict):
    """Résultat de l'analyse d'un document."""

    document_id: str
    analyse: AnalyseIA | None
    statut: str  # "analysé" | "erreur"
    erreur: str | None


# ── Clients ───────────────────────────────────────────────────────────────────

def get_supabase_client():  # type: ignore[return]
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
    return create_client(url, key)


def get_anthropic_client():
    import anthropic  # noqa: PLC0415
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY est requis — configure Doppler")
    return anthropic.Anthropic(api_key=api_key)


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _detect_media_type(url: str, content_type: str | None) -> str:
    """Détecte le type MIME depuis le Content-Type header ou l'extension de l'URL."""
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
            return ct

    lower = url.lower().split("?")[0]
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/pdf"


def _build_content_block(content: bytes, media_type: str) -> dict:
    """Construit le bloc de contenu pour l'API Anthropic (document ou image)."""
    data = base64.standard_b64encode(content).decode("utf-8")
    if media_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _build_prompt(type_document: str) -> str:
    description = _DOC_DESCRIPTIONS.get(type_document, f"document de type {type_document}")
    return _EXTRACTION_PROMPT.format(type_document=type_document, description=description)


def _parse_claude_response(text: str, type_document: str) -> AnalyseIA:
    """Parse la réponse JSON de Claude en AnalyseIA. Accepte JSON avec triple backtick."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    return AnalyseIA(
        type_document=data.get("type_document", type_document),
        montants=data.get("montants", []),
        dates=data.get("dates", []),
        tiers=data.get("tiers", []),
        references=data.get("references", []),
        tva=data.get("tva"),
        resume=data.get("resume", ""),
    )


def _update_document(supabase, document_id: str, analyse: AnalyseIA) -> None:
    """Stocke l'analyse IA et met à jour le statut dans documents."""
    supabase.table("documents").update({
        "analyse_ia": dict(analyse),
        "statut": "analysé",
    }).eq("id", document_id).execute()


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def run(
    document_id: str,
    url: str,
    type_document: str,
    dry_run: bool = False,
) -> DocumentAnalyzerResult:
    """Télécharge le document, extrait les données via Claude, stocke en base.

    Args:
        document_id: UUID du document dans la table documents.
        url: URL Supabase Storage du fichier (PDF ou image).
        type_document: Type de document (facture_achat, releve_bancaire, etc.).
        dry_run: Si True, analyse sans écrire en base.

    Returns:
        DocumentAnalyzerResult avec l'analyse ou l'erreur.
    """
    import httpx  # noqa: PLC0415

    logger.info(f"document_analyzer — {document_id} ({type_document})")

    # 1. Téléchargement du fichier
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.content
        content_type = resp.headers.get("content-type")
    except Exception as exc:
        logger.error(f"document_analyzer — téléchargement échoué {url} : {exc}")
        return DocumentAnalyzerResult(
            document_id=document_id,
            analyse=None,
            statut="erreur",
            erreur=f"Téléchargement échoué : {exc}",
        )

    media_type = _detect_media_type(url, content_type)
    logger.debug(f"document_analyzer — {len(content)} octets, type {media_type}")

    # 2. Extraction IA via Claude Sonnet 4.6
    try:
        import anthropic  # noqa: PLC0415
        ai_client = get_anthropic_client()
        content_block = _build_content_block(content, media_type)
        prompt = _build_prompt(type_document)

        message = ai_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        content_block,
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        raw_text = message.content[0].text
        analyse = _parse_claude_response(raw_text, type_document)
    except anthropic.APITimeoutError as exc:
        logger.error(f"document_analyzer — timeout Claude pour {document_id} : {exc}")
        return DocumentAnalyzerResult(
            document_id=document_id,
            analyse=None,
            statut="erreur",
            erreur=f"Claude timeout : {exc}",
        )
    except Exception as exc:
        logger.error(f"document_analyzer — erreur extraction {document_id} : {exc}")
        return DocumentAnalyzerResult(
            document_id=document_id,
            analyse=None,
            statut="erreur",
            erreur=f"Extraction échouée : {exc}",
        )

    # 3. Stockage en base (sauf dry_run)
    if not dry_run:
        try:
            supabase = get_supabase_client()
            _update_document(supabase, document_id, analyse)
        except Exception as exc:
            logger.warning(f"document_analyzer — impossible de sauvegarder {document_id} : {exc}")

    logger.info(f"document_analyzer — {document_id} analysé : {analyse['resume']}")
    return DocumentAnalyzerResult(
        document_id=document_id,
        analyse=analyse,
        statut="analysé",
        erreur=None,
    )

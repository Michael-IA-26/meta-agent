"""Agent Tri & Classification #3 — classification documentaire après OCR (JM Partners v2.2)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TypedDict, cast

from supabase import Client, create_client

__all__ = ["DocumentClassifie", "TriClassificationResult", "TriClassificationAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

SEUIL_QUALIFICATION = 0.80


class DocumentClassifie(TypedDict):
    document_id: str
    type_piece: str
    sous_type: str | None
    score_confiance: float
    statut: str
    raison_attente: str | None


class TriClassificationResult(TypedDict):
    documents_traites: int
    qualifies_auto: int
    en_attente: int
    details: list[DocumentClassifie]
    erreurs: list[str]


class TriClassificationAgent:
    """Agent #3 — classe les documents après extraction OCR."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise EnvironmentError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, document_ids: list[str] | None = None) -> TriClassificationResult:
        """Classifie les documents statut='a_trier' (ou ceux spécifiés)."""
        supabase = self._get_supabase()
        details: list[DocumentClassifie] = []
        erreurs: list[str] = []

        query = supabase.table("documents").select("id, contenu_extrait")
        if document_ids:
            query = query.in_("id", document_ids)
        else:
            query = query.eq("statut", "a_trier")

        try:
            rows = query.execute().data or []
        except Exception as exc:
            logger.error("tri_agent — erreur lecture Supabase : %s", exc)
            return TriClassificationResult(
                documents_traites=0, qualifies_auto=0, en_attente=0,
                details=[], erreurs=[str(exc)]
            )

        for row in rows:
            r = cast(dict, row)
            document_id = r["id"]
            contenu = cast(dict, r.get("contenu_extrait") or {})
            try:
                type_piece, sous_type, score = self._classifier(contenu)
                if score >= SEUIL_QUALIFICATION:
                    statut = "qualifie"
                    supabase.table("documents").update(
                        {"type_piece": type_piece, "sous_type": sous_type,
                         "score_confiance": score, "statut": statut}
                    ).eq("id", document_id).execute()
                else:
                    statut = "en_attente_collaborateur"
                    self._mettre_en_attente(document_id, score, "score_confiance_insuffisant")

                self._log_journal(document_id, "tri_classification", statut)
                details.append(
                    DocumentClassifie(
                        document_id=document_id,
                        type_piece=type_piece,
                        sous_type=sous_type,
                        score_confiance=score,
                        statut=statut,
                        raison_attente=None if statut == "qualifie" else "score_confiance_insuffisant",
                    )
                )
            except Exception as exc:
                erreurs.append(f"{document_id}: {exc}")
                logger.error("tri_agent — erreur document %s : %s", document_id, exc)

        qualifies = sum(1 for d in details if d["statut"] == "qualifie")
        en_attente = sum(1 for d in details if d["statut"] == "en_attente_collaborateur")

        return TriClassificationResult(
            documents_traites=len(details),
            qualifies_auto=qualifies,
            en_attente=en_attente,
            details=details,
            erreurs=erreurs,
        )

    def _classifier(self, contenu: dict) -> tuple[str, str | None, float]:
        """Applique les règles métier comptables. Retourne (type_piece, sous_type, score)."""
        texte = " ".join(str(v) for v in contenu.values()).upper()

        # Facture fournisseur
        if contenu.get("siret") and contenu.get("montant_ht") and contenu.get("montant_ttc"):
            if not any(k in texte for k in ("DOIT", "À PAYER", "FACTURE CLIENT")):
                return "fournisseur", "facture", 0.95

        # Facture client
        if contenu.get("siret") and any(k in texte for k in ("DOIT", "À PAYER")):
            return "client", "facture", 0.90

        # Relevé bancaire
        if any(k in texte for k in ("RELEVÉ", "RELEVE", "SOLDE")) and contenu.get("compte_bancaire"):
            return "banque", "releve", 0.92

        # Social
        if any(k in texte for k in ("URSSAF", "RSI", "CIPAV", "RETRAITE")):
            return "social", "declaration", 0.88

        # Fiscal
        if any(k in texte for k in ("TVA", "CA3", "DGFIP", "DGFiP", "IMPÔT", "IMPOT")):
            return "fiscal", "declaration", 0.85

        # Avoir fournisseur
        if contenu.get("siret") and any(k in texte for k in ("AVOIR", "NOTE DE CRÉDIT", "CREDIT NOTE")):
            return "fournisseur", "avoir", 0.88

        return "autre", None, 0.40

    def _mettre_en_attente(self, document_id: str, score: float, raison: str) -> None:
        """Passe le document en attente dans Supabase."""
        try:
            self._get_supabase().table("documents").update(
                {"statut": "en_attente_collaborateur",
                 "raison_attente": raison,
                 "score_confiance": score}
            ).eq("id", document_id).execute()
        except Exception as exc:
            logger.error("tri_agent — erreur mise en attente %s : %s", document_id, exc)

    def _log_journal(self, document_id: str, action: str, statut: str) -> None:
        """INSERT dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {"agent": "tri_classification_agent", "action": action,
                 "statut": statut, "document_id": document_id,
                 "created_at": datetime.now(timezone.utc).isoformat()}
            ).execute()
        except Exception as exc:
            logger.warning("tri_agent — log journal échoué : %s", exc)

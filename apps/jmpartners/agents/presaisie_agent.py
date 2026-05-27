"""Agent pré-saisie comptable — génère les écritures comptables via Claude (JM Partners)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, TypedDict, cast

import anthropic
from anthropic.types import TextBlock
from supabase import Client, create_client

__all__ = ["EcritureProposee", "PresaisieResult", "PresaisieAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

MODEL = "claude-opus-4-7"

PROMPT_TEMPLATE = (
    "Tu es un expert-comptable français (niveau 5-8 ans). Propose les écritures comptables pour cette pièce.\n"
    "Données extraites : {contenu_extrait}\n"
    "Historique FEC similaire : {historique}\n"
    "Retourne en JSON :\n"
    "[{{\n"
    '  "journal": "ACH|VTE|BQ|OD",\n'
    '  "compte_debit": "401000",\n'
    '  "compte_credit": "606100",\n'
    '  "tiers": null,\n'
    '  "libelle": "description courte",\n'
    '  "montant_ht": 100.0,\n'
    '  "montant_tva": 20.0,\n'
    '  "montant_ttc": 120.0,\n'
    '  "taux_tva": 20.0,\n'
    '  "source_validation": "fec_reconnu|apprentissage|regle_comptable|a_verifier"\n'
    "}}]\n"
    "Règles absolues :\n"
    "Ne jamais supposer un taux TVA — lire sur le document ou marquer taux_tva=null\n"
    "Autoliquidation BTP si mention explicite → compte_debit=44562, compte_credit=44566\n"
    "Taux réduit restauration 10% sur consommation sur place, 5.5% vente à emporter"
)


class EcritureProposee(TypedDict):
    journal: str          # "ACH"|"VTE"|"BQ"|"OD"
    compte_debit: str
    compte_credit: str
    tiers: str | None
    libelle: str
    montant_ht: float
    montant_tva: float
    montant_ttc: float
    taux_tva: float | None
    source_validation: str  # "fec_reconnu"|"apprentissage"|"regle_comptable"|"a_verifier"


class PresaisieResult(TypedDict):
    documents_traites: int
    ecritures_proposees: int
    details: list[dict]   # {"document_id": str, "ecritures": list[EcritureProposee]}
    erreurs: list[str]


class PresaisieAgent:
    """Génère les écritures comptables pré-saisie depuis les documents qualifiés."""

    def __init__(self) -> None:
        self._supabase: Client | None = None
        self._anthropic: anthropic.Anthropic | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _get_anthropic(self) -> anthropic.Anthropic:
        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._anthropic

    def run(self, document_ids: list[str] | None = None) -> PresaisieResult:
        """Génère les écritures pour docs statut='qualifie'."""
        supabase = self._get_supabase()
        erreurs: list[str] = []
        details: list[dict] = []
        ecritures_proposees_total = 0

        try:
            query = supabase.table("documents").select("*")
            if document_ids:
                query = query.in_("id", document_ids)
            else:
                query = query.eq("statut", "qualifie")
            raw_data = query.execute().data
            documents: list[dict[str, Any]] = (
                [dict(r) for r in raw_data]  # type: ignore[arg-type]
                if raw_data
                else []
            )
        except Exception as exc:
            msg = f"Erreur récupération documents : {exc}"
            logger.error(msg)
            return PresaisieResult(
                documents_traites=0,
                ecritures_proposees=0,
                details=[],
                erreurs=[msg],
            )

        for doc in documents:
            doc_map: dict[str, Any] = dict(doc)
            document_id: str = str(doc_map.get("id") or "")
            raw_contenu = doc_map.get("contenu_extrait")
            contenu_extrait: dict[str, Any] = dict(raw_contenu) if isinstance(raw_contenu, dict) else {}

            historique = self._fetch_historique_similaire(contenu_extrait)

            try:
                ecritures = self._generer_ecritures(contenu_extrait, historique)
            except Exception as exc:
                logger.warning("Erreur Claude pour document %s : %s", document_id, exc)
                ecritures = [
                    EcritureProposee(
                        journal="",
                        compte_debit="",
                        compte_credit="",
                        tiers=None,
                        libelle="",
                        montant_ht=0.0,
                        montant_tva=0.0,
                        montant_ttc=0.0,
                        taux_tva=None,
                        source_validation="a_verifier",
                    )
                ]

            try:
                self._sauvegarder_ecritures(document_id, ecritures)
            except Exception as exc:
                msg = f"Erreur sauvegarde document {document_id} : {exc}"
                logger.error(msg)
                erreurs.append(msg)
                continue

            self._log_journal(document_id, len(ecritures))
            ecritures_proposees_total += len(ecritures)
            details.append({"document_id": document_id, "ecritures": list(ecritures)})

        return PresaisieResult(
            documents_traites=len(documents),
            ecritures_proposees=ecritures_proposees_total,
            details=details,
            erreurs=erreurs,
        )

    def _fetch_historique_similaire(self, contenu_extrait: dict[str, Any]) -> list[dict[str, Any]]:
        """Cherche dans ecritures_sage des entrées similaires via Supabase RPC 'match_historique_fec'.

        Retourne [] si RPC non disponible ou erreur.
        """
        try:
            supabase = self._get_supabase()
            response = supabase.rpc(
                "match_historique_fec",
                {"contenu": json.dumps(contenu_extrait)},
            ).execute()
            raw = response.data
            if isinstance(raw, list):
                return [dict(item) for item in raw]
            return []
        except Exception as exc:
            logger.debug("RPC match_historique_fec non disponible ou erreur : %s", exc)
            return []

    def _generer_ecritures(
        self,
        contenu_extrait: dict[str, Any],
        historique: list[dict[str, Any]],
    ) -> list[EcritureProposee]:
        """Appelle Claude API (text), parse le JSON retourné."""
        client = self._get_anthropic()
        prompt = PROMPT_TEMPLATE.format(
            contenu_extrait=json.dumps(contenu_extrait, ensure_ascii=False),
            historique=json.dumps(historique, ensure_ascii=False),
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        first_block = response.content[0]
        raw_text: str = cast(TextBlock, first_block).text
        parsed: list[dict[str, Any]] = json.loads(raw_text)
        ecritures: list[EcritureProposee] = []
        for item in parsed:
            taux_raw = item.get("taux_tva")
            taux_tva: float | None = float(taux_raw) if taux_raw is not None else None
            ecritures.append(
                EcritureProposee(
                    journal=str(item.get("journal") or ""),
                    compte_debit=str(item.get("compte_debit") or ""),
                    compte_credit=str(item.get("compte_credit") or ""),
                    tiers=str(item["tiers"]) if item.get("tiers") is not None else None,
                    libelle=str(item.get("libelle") or ""),
                    montant_ht=float(item.get("montant_ht") or 0.0),
                    montant_tva=float(item.get("montant_tva") or 0.0),
                    montant_ttc=float(item.get("montant_ttc") or 0.0),
                    taux_tva=taux_tva,
                    source_validation=str(item.get("source_validation") or "a_verifier"),
                )
            )
        return ecritures

    def _sauvegarder_ecritures(
        self, document_id: str, ecritures: list[EcritureProposee]
    ) -> None:
        """INSERT dans table 'ecritures' + UPDATE documents (statut='a_valider')."""
        supabase = self._get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "document_id": document_id,
                "journal": e["journal"],
                "compte_debit": e["compte_debit"],
                "compte_credit": e["compte_credit"],
                "tiers": e["tiers"],
                "libelle": e["libelle"],
                "montant_ht": e["montant_ht"],
                "montant_tva": e["montant_tva"],
                "montant_ttc": e["montant_ttc"],
                "taux_tva": e["taux_tva"],
                "source_validation": e["source_validation"],
                "created_at": now,
            }
            for e in ecritures
        ]
        supabase.table("ecritures").insert(rows).execute()
        supabase.table("documents").update({"statut": "a_valider"}).eq(
            "id", document_id
        ).execute()

    def _log_journal(self, document_id: str, nb_ecritures: int) -> None:
        logger.info(
            "PresaisieAgent — document=%s écritures_générées=%d",
            document_id,
            nb_ecritures,
        )

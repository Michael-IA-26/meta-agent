"""Agent presaisie_agent — propose des écritures comptables via Claude."""

from __future__ import annotations

import json
import logging
import os
from typing import TypedDict

__all__ = ["PresaisieAgent", "PresaisieResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class PresaisieResult(TypedDict):
    """Résultat de la présaisie comptable."""

    documents_traites: int
    ecritures_proposees: int
    erreurs: list[str]
    details: list[dict]


class PresaisieAgent:
    """Propose des écritures comptables pour les documents qualifiés."""

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

    def _proposer_ecritures(self, client, contenu: dict) -> list[dict]:
        """Demande à Claude de proposer des écritures comptables.

        Args:
            client: Client Anthropic.
            contenu: Contenu extrait du document.

        Returns:
            Liste d'écritures comptables proposées.
        """
        prompt = f"""Propose les écritures comptables pour ce document :
{json.dumps(contenu, ensure_ascii=False, indent=2)}

Retourne un JSON avec une liste "ecritures" contenant des objets :
- journal: "ACH" | "VTE" | "BQ" | "OD"
- compte_debit: string (numéro de compte PCG)
- compte_credit: string
- montant: float
- libelle: string
- taux_tva: float ou null
"""
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return data.get("ecritures", [])
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def run(self) -> PresaisieResult:
        """Traite les documents qualifiés et propose des écritures.

        Returns:
            PresaisieResult avec le nombre d'écritures proposées.
        """
        supabase = self._get_supabase()
        anthropic_client = self._get_anthropic()
        erreurs: list[str] = []
        details: list[dict] = []
        total_ecritures = 0

        resp = (
            supabase.table("documents")
            .select("id, nom_fichier, contenu_extrait, type_piece")
            .eq("statut", "qualifie")
            .eq("cabinet_id", self.cabinet_id)
            .execute()
        )
        documents = resp.data or []
        logger.info(f"presaisie_agent — {len(documents)} documents qualifiés")

        for doc in documents:
            doc_id = doc["id"]
            try:
                contenu = doc.get("contenu_extrait") or {}
                ecritures = self._proposer_ecritures(anthropic_client, contenu)

                for ecriture in ecritures:
                    supabase.table("ecritures_proposees").insert({
                        "document_id": doc_id,
                        "cabinet_id": self.cabinet_id,
                        "journal": ecriture.get("journal", "OD"),
                        "compte_debit": ecriture.get("compte_debit", ""),
                        "compte_credit": ecriture.get("compte_credit", ""),
                        "montant": ecriture.get("montant", 0.0),
                        "libelle": ecriture.get("libelle", ""),
                        "taux_tva": ecriture.get("taux_tva"),
                        "statut": "proposee",
                    }).execute()

                supabase.table("documents").update({
                    "statut": "en_verification",
                }).eq("id", doc_id).execute()

                total_ecritures += len(ecritures)
                details.append({
                    "document_id": doc_id,
                    "nb_ecritures": len(ecritures),
                    "ecritures": ecritures,
                })
                logger.info(
                    f"presaisie_agent — {doc['nom_fichier']} → {len(ecritures)} écritures"
                )

            except Exception as exc:
                logger.error(f"presaisie_agent — erreur {doc_id} : {exc}")
                erreurs.append(f"{doc_id}: {exc}")

        return PresaisieResult(
            documents_traites=len(documents),
            ecritures_proposees=total_ecritures,
            erreurs=erreurs,
            details=details,
        )

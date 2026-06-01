"""Agent revision_agent — détecte les anomalies comptables dans les écritures Sage."""

from __future__ import annotations

import logging
import os
from typing import TypedDict

__all__ = ["RevisionAgent", "RevisionResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

SEUIL_ECART = 0.01  # Tolérance d'arrondi


class RevisionResult(TypedDict):
    """Résultat de la révision comptable."""

    ecritures_analysees: int
    anomalies_detectees: int
    anomalies: list[dict]
    erreurs: list[str]


class RevisionAgent:
    """Analyse les écritures Sage et détecte les anomalies comptables."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _detecter_desequilibres(self, ecritures: list[dict]) -> list[dict]:
        """Détecte les déséquilibres D/C par journal.

        Args:
            ecritures: Liste des écritures à analyser.

        Returns:
            Liste des anomalies détectées.
        """
        anomalies = []

        # Grouper par journal
        journals: dict[str, dict] = {}
        for e in ecritures:
            j = e.get("journal", "")
            if j not in journals:
                journals[j] = {"debit": 0.0, "credit": 0.0}
            journals[j]["debit"] += float(e.get("debit", 0) or 0)
            journals[j]["credit"] += float(e.get("credit", 0) or 0)

        for journal, totaux in journals.items():
            ecart = abs(totaux["debit"] - totaux["credit"])
            if ecart > SEUIL_ECART:
                anomalies.append({
                    "type_anomalie": "desequilibre_journal",
                    "journal": journal,
                    "total_debit": totaux["debit"],
                    "total_credit": totaux["credit"],
                    "ecart": ecart,
                })

        return anomalies

    def _detecter_doublons(self, ecritures: list[dict]) -> list[dict]:
        """Détecte les doublons par référence de pièce.

        Args:
            ecritures: Liste des écritures à analyser.

        Returns:
            Liste des anomalies de doublon.
        """
        anomalies = []
        seen: dict[str, int] = {}

        for e in ecritures:
            ref = e.get("reference", "")
            if not ref:
                continue
            seen[ref] = seen.get(ref, 0) + 1

        for ref, count in seen.items():
            if count > 1:
                anomalies.append({
                    "type_anomalie": "doublon_reference",
                    "reference": ref,
                    "occurrences": count,
                })

        return anomalies

    def run(self) -> RevisionResult:
        """Analyse les écritures Sage et détecte les anomalies.

        Returns:
            RevisionResult avec le nombre d'anomalies détectées.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []
        all_anomalies: list[dict] = []

        try:
            resp = (
                supabase.table("ecritures_sage")
                .select("id, journal, reference, debit, credit, libelle, date_piece")
                .eq("cabinet_id", self.cabinet_id)
                .execute()
            )
            ecritures = resp.data or []
        except Exception as exc:
            logger.error(f"revision_agent — erreur fetch écritures : {exc}")
            return RevisionResult(
                ecritures_analysees=0,
                anomalies_detectees=0,
                anomalies=[],
                erreurs=[str(exc)],
            )

        logger.info(f"revision_agent — {len(ecritures)} écritures à analyser")

        # Détections
        all_anomalies.extend(self._detecter_desequilibres(ecritures))
        all_anomalies.extend(self._detecter_doublons(ecritures))

        if all_anomalies:
            logger.warning(
                f"revision_agent — {len(all_anomalies)} anomalie(s) détectée(s)"
            )
            # Persister les anomalies
            for anomalie in all_anomalies:
                try:
                    supabase.table("anomalies_revision").insert({
                        "cabinet_id": self.cabinet_id,
                        **anomalie,
                    }).execute()
                except Exception as exc:
                    erreurs.append(f"Insert anomalie : {exc}")
        else:
            logger.info("revision_agent — aucune anomalie détectée")

        return RevisionResult(
            ecritures_analysees=len(ecritures),
            anomalies_detectees=len(all_anomalies),
            anomalies=all_anomalies,
            erreurs=erreurs,
        )

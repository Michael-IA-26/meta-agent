"""Agent miroir_sage_agent — synchronise le FEC Sage avec Supabase."""

from __future__ import annotations

import csv
import io
import logging
import os
from typing import TypedDict

__all__ = ["MiroirSageAgent", "MiroirSageResult"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

FEC_STORAGE_PATH = "fec/sage_export.csv"


class MiroirSageResult(TypedDict):
    """Résultat de la synchronisation FEC."""

    ecritures_nouvelles: int
    ecritures_mises_a_jour: int
    erreurs: list[str]


class MiroirSageAgent:
    """Synchronise le FEC exporté par Sage avec la table ecritures_sage de Supabase."""

    def __init__(self, cabinet_id: str = "jmpartners") -> None:
        self.cabinet_id = cabinet_id

    def _get_supabase(self):
        """Retourne un client Supabase (mockable dans les tests)."""
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    def _parse_fec(self, content: bytes) -> list[dict]:
        """Parse le contenu FEC CSV.

        Args:
            content: Contenu du fichier FEC en bytes.

        Returns:
            Liste de dictionnaires représentant les écritures.
        """
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        rows = []
        for row in reader:
            rows.append({
                "journal": row.get("JournalCode", ""),
                "date_piece": row.get("EcritureDate", ""),
                "compte": row.get("CompteNum", ""),
                "libelle": row.get("EcritureLib", ""),
                "debit": float(row.get("Debit", 0) or 0),
                "credit": float(row.get("Credit", 0) or 0),
                "reference": row.get("PieceRef", ""),
                "cabinet_id": self.cabinet_id,
            })
        return rows

    def _sync_fec(self) -> MiroirSageResult:
        """Synchronise le FEC depuis Storage vers la table ecritures_sage.

        Returns:
            MiroirSageResult avec le nombre d'écritures nouvelles et mises à jour.
        """
        supabase = self._get_supabase()
        erreurs: list[str] = []
        nouvelles = 0
        mises_a_jour = 0

        try:
            content = supabase.storage.from_("fec").download(FEC_STORAGE_PATH)
        except Exception as exc:
            logger.warning(f"miroir_sage_agent — impossible de télécharger le FEC : {exc}")
            return MiroirSageResult(
                ecritures_nouvelles=0,
                ecritures_mises_a_jour=0,
                erreurs=[str(exc)],
            )

        try:
            ecritures = self._parse_fec(content)
        except Exception as exc:
            logger.error(f"miroir_sage_agent — erreur parsing FEC : {exc}")
            return MiroirSageResult(
                ecritures_nouvelles=0,
                ecritures_mises_a_jour=0,
                erreurs=[str(exc)],
            )

        logger.info(f"miroir_sage_agent — {len(ecritures)} écritures FEC parsées")

        for ecriture in ecritures:
            try:
                # Vérifier si l'écriture existe déjà
                existing = (
                    supabase.table("ecritures_sage")
                    .select("id")
                    .eq("reference", ecriture["reference"])
                    .eq("cabinet_id", self.cabinet_id)
                    .execute()
                )

                if existing.data:
                    supabase.table("ecritures_sage").update(ecriture).eq(
                        "id", existing.data[0]["id"]
                    ).execute()
                    mises_a_jour += 1
                else:
                    supabase.table("ecritures_sage").insert(ecriture).execute()
                    nouvelles += 1

            except Exception as exc:
                logger.error(f"miroir_sage_agent — erreur sync écriture : {exc}")
                erreurs.append(str(exc))

        return MiroirSageResult(
            ecritures_nouvelles=nouvelles,
            ecritures_mises_a_jour=mises_a_jour,
            erreurs=erreurs,
        )

    def run(self) -> MiroirSageResult:
        """Exécute la synchronisation FEC.

        Returns:
            MiroirSageResult.
        """
        logger.info("miroir_sage_agent — démarrage synchronisation FEC")
        return self._sync_fec()

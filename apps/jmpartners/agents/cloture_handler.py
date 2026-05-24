"""Agent cloture_handler — clôture comptable de fin de mois."""

from __future__ import annotations

import logging
import os
from calendar import monthrange
from datetime import date
from typing import TypedDict, cast

from supabase import Client, create_client

from apps.shared.telegram import send_telegram_message

__all__ = ["ClotureResult", "ClotureHandler"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class ClotureResult(TypedDict):
    cabinet_id: str
    mois: str
    dossiers_clotures: list[str]
    statut: str
    timestamp: str


def _is_dernier_jour_ouvre(today: date) -> bool:
    """Retourne True si today est le dernier jour ouvré du mois."""
    from datetime import timedelta

    _, nb_jours = monthrange(today.year, today.month)
    dernier_jour = date(today.year, today.month, nb_jours)
    while dernier_jour.weekday() >= 5:
        dernier_jour -= timedelta(days=1)
    return today == dernier_jour


class ClotureHandler:
    def __init__(self, cabinet_id: str) -> None:
        self.cabinet_id = cabinet_id
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _fetch_dossiers_en_cours(self, mois: str) -> list[dict]:
        try:
            resp = (
                self._get_supabase()
                .table("dossiers")
                .select("id, mois_comptable, statut")
                .eq("cabinet_id", self.cabinet_id)
                .eq("statut", "en_cours")
                .eq("mois_comptable", mois)
                .execute()
            )
            return [cast(dict, row) for row in (resp.data or [])]
        except Exception as exc:
            logger.error(f"Erreur fetch dossiers : {exc}")
            return []

    def _cloture_dossier(self, dossier_id: str) -> bool:
        try:
            self._get_supabase().table("dossiers").update(
                {"statut": "cloture_envoyee"}
            ).eq("id", dossier_id).execute()
            return True
        except Exception as exc:
            logger.error(f"Erreur clôture dossier {dossier_id} : {exc}")
            return False

    def run(self) -> ClotureResult:
        from datetime import datetime, timezone

        today = date.today()
        mois = today.strftime("%Y-%m")
        timestamp = datetime.now(tz=timezone.utc).isoformat()

        if not _is_dernier_jour_ouvre(today):
            logger.info(f"cloture_handler : pas le dernier jour ouvré ({today}), skip")
            return ClotureResult(
                cabinet_id=self.cabinet_id,
                mois=mois,
                dossiers_clotures=[],
                statut="skip",
                timestamp=timestamp,
            )

        logger.info(f"cloture_handler — clôture de fin de mois {mois}")
        dossiers = self._fetch_dossiers_en_cours(mois)
        clotures: list[str] = []

        for dossier in dossiers:
            dossier_id: str = dossier["id"]
            if self._cloture_dossier(dossier_id):
                clotures.append(dossier_id)
                logger.info(f"cloture_handler : dossier {dossier_id} → cloture_envoyee")

        if clotures:
            message = (
                f"Clôture comptable {mois} — cabinet {self.cabinet_id}\n"
                f"{len(clotures)} dossier(s) clôturé(s)"
            )
            send_telegram_message(message)

        statut = "ok" if clotures else "aucun_dossier"
        logger.info(f"cloture_handler terminé : {len(clotures)} dossier(s) clôturé(s)")
        return ClotureResult(
            cabinet_id=self.cabinet_id,
            mois=mois,
            dossiers_clotures=clotures,
            statut=statut,
            timestamp=timestamp,
        )

"""Agent Révision — détection nocturne d'anomalies comptables (JM Partners)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict, cast

from supabase import Client, create_client

from apps.shared.telegram import send_telegram_message

__all__ = ["AnomalieRevision", "RevisionResult", "RevisionAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class AnomalieRevision(TypedDict):
    type: str  # "compte_incorrect" | "doublon" | "lettrage_impossible" | "tiers_imprecis"
    ecriture_id: str
    description: str
    suggestion: str | None
    severite: str  # "auto_corrigeable" | "validation_requise"
    corrigee: bool


class RevisionResult(TypedDict):
    anomalies_detectees: int
    anomalies_corrigees: int
    anomalies_en_attente: int
    details: list[AnomalieRevision]


class RevisionAgent:
    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _detect_compte_incorrect(
        self,
        ecritures_sage: list[dict[str, Any]],
    ) -> list[AnomalieRevision]:
        """Charge 6xxx sans passage par 401 fournisseur pour même tiers+date."""
        anomalies: list[AnomalieRevision] = []

        # Build set of (tiers, date) pairs that have a 401 entry
        pairs_401: set[tuple[str, str]] = set()
        for e in ecritures_sage:
            compte = e.get("compte", "") or ""
            if compte.startswith("401"):
                tiers = e.get("tiers") or ""
                date_e = e.get("date_ecriture", "") or ""
                pairs_401.add((tiers, date_e))

        for e in ecritures_sage:
            compte = e.get("compte", "") or ""
            if not compte.startswith("6"):
                continue
            debit = e.get("debit", 0.0) or 0.0
            if debit <= 0:
                continue
            tiers = e.get("tiers") or ""
            date_e = e.get("date_ecriture", "") or ""
            if (tiers, date_e) not in pairs_401:
                anomalies.append(
                    AnomalieRevision(
                        type="compte_incorrect",
                        ecriture_id=str(e.get("id", "")),
                        description=(
                            f"Charge {compte} saisie sans contrepartie 401 "
                            f"pour tiers='{tiers}' date='{date_e}'"
                        ),
                        suggestion="Vérifier la saisie et ajouter l'écriture fournisseur 401.",
                        severite="validation_requise",
                        corrigee=False,
                    )
                )

        return anomalies

    def _detect_tiers_imprecis(
        self,
        ecritures_sage: list[dict[str, Any]],
    ) -> list[AnomalieRevision]:
        """Tiers contient 'Divers' ou 'Divers fournisseur' (insensible à la casse)."""
        anomalies: list[AnomalieRevision] = []
        divers_keywords = ["divers fournisseur", "divers"]

        for e in ecritures_sage:
            tiers = (e.get("tiers") or "").strip().lower()
            if any(kw in tiers for kw in divers_keywords):
                anomalies.append(
                    AnomalieRevision(
                        type="tiers_imprecis",
                        ecriture_id=str(e.get("id", "")),
                        description=(
                            f"Tiers imprécis '{e.get('tiers')}' — veuillez identifier le tiers exact."
                        ),
                        suggestion="Remplacer par le nom exact du fournisseur ou client.",
                        severite="validation_requise",
                        corrigee=False,
                    )
                )

        return anomalies

    def _detect_doublons(
        self,
        ecritures: list[dict[str, Any]],
        ecritures_sage: list[dict[str, Any]],
    ) -> list[AnomalieRevision]:
        """Même montant_ttc + tiers + date dans ecritures ET ecritures_sage."""
        anomalies: list[AnomalieRevision] = []

        # Build key set from ecritures
        keys_ecritures: set[tuple[float, str, str]] = set()
        for e in ecritures:
            montant = float(e.get("montant_ttc", 0.0) or 0.0)
            tiers = (e.get("tiers") or "").strip()
            date_e = (e.get("date_ecriture", "") or "").strip()
            if montant and tiers and date_e:
                keys_ecritures.add((montant, tiers, date_e))

        for e in ecritures_sage:
            # Use debit as proxy for montant_ttc when comparing
            montant = float(e.get("debit", 0.0) or 0.0)
            if montant == 0.0:
                montant = float(e.get("credit", 0.0) or 0.0)
            tiers = (e.get("tiers") or "").strip()
            date_e = (e.get("date_ecriture", "") or "").strip()

            if montant and tiers and date_e and (montant, tiers, date_e) in keys_ecritures:
                anomalies.append(
                    AnomalieRevision(
                        type="doublon",
                        ecriture_id=str(e.get("id", "")),
                        description=(
                            f"Doublon détecté : montant={montant}, tiers='{tiers}', "
                            f"date='{date_e}' présent dans ecritures et ecritures_sage."
                        ),
                        suggestion="Vérifier si l'écriture a déjà été comptabilisée.",
                        severite="validation_requise",
                        corrigee=False,
                    )
                )

        return anomalies

    def _detect_lettrage_impossible(
        self,
        ecritures_sage: list[dict[str, Any]],
    ) -> list[AnomalieRevision]:
        """Règlement (compte 512xxx) sans facture associée depuis > 30 jours."""
        anomalies: list[AnomalieRevision] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Build set of tiers that have facture entries (4xxx)
        tiers_avec_facture: set[str] = set()
        for e in ecritures_sage:
            compte = e.get("compte", "") or ""
            if compte.startswith("4"):
                tiers = (e.get("tiers") or "").strip()
                if tiers:
                    tiers_avec_facture.add(tiers)

        for e in ecritures_sage:
            compte = e.get("compte", "") or ""
            if not compte.startswith("512"):
                continue

            date_str = (e.get("date_ecriture", "") or "").strip()
            if not date_str:
                continue

            try:
                # FEC date format: YYYYMMDD or YYYY-MM-DD
                if len(date_str) == 8 and "-" not in date_str:
                    date_ecriture = datetime.strptime(date_str, "%Y%m%d").replace(
                        tzinfo=timezone.utc
                    )
                else:
                    date_ecriture = datetime.fromisoformat(date_str).replace(
                        tzinfo=timezone.utc
                    )
            except ValueError:
                continue

            if date_ecriture > cutoff:
                continue

            tiers = (e.get("tiers") or "").strip()
            if tiers not in tiers_avec_facture:
                anomalies.append(
                    AnomalieRevision(
                        type="lettrage_impossible",
                        ecriture_id=str(e.get("id", "")),
                        description=(
                            f"Règlement compte {compte} sans facture associée "
                            f"depuis plus de 30 jours (date='{date_str}', tiers='{tiers}')."
                        ),
                        suggestion="Rapprocher avec la facture correspondante ou contacter le tiers.",
                        severite="avertissement",
                        corrigee=False,
                    )
                )

        return anomalies

    def _log_journal(
        self,
        sb: Client,
        nb_anomalies: int,
        nb_corrigees: int,
        nb_en_attente: int,
    ) -> None:
        try:
            sb.table("journaux").insert(
                {
                    "agent": "revision_agent",
                    "action": "revision_nocturne",
                    "details": {
                        "anomalies_detectees": nb_anomalies,
                        "anomalies_corrigees": nb_corrigees,
                        "anomalies_en_attente": nb_en_attente,
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            logger.warning("revision — erreur log journal : %s", exc)

    def run(self) -> RevisionResult:
        """
        Révision nocturne (00h00) par recoupement des écritures.

        RÈGLE ABSOLUE : ne jamais UPDATE compte, montant sur ecritures sans validation collaborateur.
        """
        sb = self._get_supabase()

        ecritures_sage_resp = sb.table("ecritures_sage").select("*").execute()
        ecritures_sage: list[dict[str, Any]] = cast(
            list[dict[str, Any]], ecritures_sage_resp.data or []
        )

        ecritures_resp = sb.table("ecritures").select("*").execute()
        ecritures: list[dict[str, Any]] = cast(
            list[dict[str, Any]], ecritures_resp.data or []
        )

        all_anomalies: list[AnomalieRevision] = []

        all_anomalies.extend(self._detect_compte_incorrect(ecritures_sage))
        all_anomalies.extend(self._detect_tiers_imprecis(ecritures_sage))
        all_anomalies.extend(self._detect_doublons(ecritures, ecritures_sage))
        all_anomalies.extend(self._detect_lettrage_impossible(ecritures_sage))

        nb_corrigees = 0
        nb_en_attente = 0

        for anomalie in all_anomalies:
            if anomalie["severite"] == "auto_corrigeable":
                # Flag only — no actual DB change
                anomalie["corrigee"] = True
                nb_corrigees += 1
            else:
                # validation_requise or avertissement → INSERT into revision, corrigee=False
                # RÈGLE ABSOLUE: never UPDATE compte/montant without collaborateur validation
                anomalie["corrigee"] = False
                nb_en_attente += 1
                try:
                    sb.table("revision").insert(
                        {
                            "type": anomalie["type"],
                            "ecriture_id": anomalie["ecriture_id"],
                            "description": anomalie["description"],
                            "suggestion": anomalie["suggestion"],
                            "severite": anomalie["severite"],
                            "statut": "en_attente",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).execute()
                except Exception as exc:
                    logger.warning(
                        "revision — erreur INSERT revision pour ecriture %s : %s",
                        anomalie["ecriture_id"],
                        exc,
                    )

        self._log_journal(sb, len(all_anomalies), nb_corrigees, nb_en_attente)

        if nb_en_attente > 0:
            msg = (
                f"*Révision nocturne JM Partners*\n"
                f"{len(all_anomalies)} anomalie(s) détectée(s)\n"
                f"{nb_en_attente} en attente de validation collaborateur\n"
                f"Types : {', '.join(set(a['type'] for a in all_anomalies if not a['corrigee']))}"
            )
            try:
                send_telegram_message(msg)
            except Exception as exc:
                logger.warning("revision — erreur Telegram : %s", exc)

        logger.info(
            "revision — %d anomalies détectées, %d corrigées, %d en attente",
            len(all_anomalies),
            nb_corrigees,
            nb_en_attente,
        )

        return RevisionResult(
            anomalies_detectees=len(all_anomalies),
            anomalies_corrigees=nb_corrigees,
            anomalies_en_attente=nb_en_attente,
            details=all_anomalies,
        )

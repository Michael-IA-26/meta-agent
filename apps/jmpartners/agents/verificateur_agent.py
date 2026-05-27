"""Agent verificateur_agent — vérification des écritures comptables sans auto-correction."""

from __future__ import annotations

import logging
import os
from typing import TypedDict, cast

from supabase import Client, create_client

__all__ = ["AnomalieVerificateur", "VerificateurResult", "VerificateurAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

EPSILON_DC = 0.01
SEUIL_ATYPIQUE = 10.0


class AnomalieVerificateur(TypedDict):
    ecriture_id: str
    type_anomalie: str  # "desequilibre_dc" | "compte_incoherent" | "doublon" | "montant_atypique"
    description: str
    severite: str  # "bloquante" | "avertissement"


class VerificateurResult(TypedDict):
    ecritures_verifiees: int
    lot_propre: bool
    anomalies: list[AnomalieVerificateur]
    erreurs: list[str]


class VerificateurAgent:
    """Agent invisible — alertes visibles dans tableau de bord et pré-saisie."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        """Retourne un client Supabase initialisé depuis les variables d'env."""
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, document_ids: list[str] | None = None) -> VerificateurResult:
        """Vérifie les écritures statut='a_valider'."""
        logger.info("verificateur_agent — démarrage")
        supabase = self._get_supabase()
        anomalies: list[AnomalieVerificateur] = []
        erreurs: list[str] = []
        ecritures: list[dict] = []

        # 1. Fetch écritures avec statut='a_valider'
        try:
            query = (
                supabase.table("ecritures")
                .select("*")
                .eq("statut", "a_valider")
            )
            if document_ids is not None:
                query = query.in_("document_id", document_ids)
            resp = query.execute()
            ecritures = [cast(dict, row) for row in (resp.data or [])]
        except Exception as exc:
            logger.error(f"Erreur fetch écritures : {exc}")
            erreurs.append(str(exc))
            return VerificateurResult(
                ecritures_verifiees=0,
                lot_propre=False,
                anomalies=[],
                erreurs=erreurs,
            )

        logger.info(f"verificateur_agent : {len(ecritures)} écritures à vérifier")

        # 2. Vérification équilibre D/C
        try:
            anomalies_dc = self._verifier_equilibre_dc(ecritures)
            anomalies.extend(anomalies_dc)
        except Exception as exc:
            logger.error(f"Erreur _verifier_equilibre_dc : {exc}")
            erreurs.append(str(exc))

        # 3. Vérification cohérence PCG par écriture
        for ecriture in ecritures:
            try:
                anomalie_pcg = self._verifier_coherence_pcg(ecriture)
                if anomalie_pcg is not None:
                    anomalies.append(anomalie_pcg)
            except Exception as exc:
                logger.error(f"Erreur _verifier_coherence_pcg ecriture {ecriture.get('id')} : {exc}")
                erreurs.append(str(exc))

        # 4. Détection doublons via ecritures_sage
        try:
            anomalies_doublons = self._detecter_doublons(ecritures)
            anomalies.extend(anomalies_doublons)
        except Exception as exc:
            logger.error(f"Erreur _detecter_doublons : {exc}")
            erreurs.append(str(exc))

        # 5. Vérification montants atypiques
        for ecriture in ecritures:
            try:
                tiers = ecriture.get("tiers")
                moyenne_tiers = 0.0
                if tiers:
                    resp_sage = (
                        supabase.table("ecritures_sage")
                        .select("montant_ttc")
                        .eq("tiers", tiers)
                        .execute()
                    )
                    montants_sage = [
                        float(cast(dict, row).get("montant_ttc", 0))
                        for row in (resp_sage.data or [])
                        if cast(dict, row).get("montant_ttc") is not None
                    ]
                    if montants_sage:
                        moyenne_tiers = sum(montants_sage) / len(montants_sage)

                anomalie_atypique = self._verifier_montants_atypiques(ecriture, moyenne_tiers)
                if anomalie_atypique is not None:
                    anomalies.append(anomalie_atypique)
            except Exception as exc:
                logger.error(f"Erreur _verifier_montants_atypiques ecriture {ecriture.get('id')} : {exc}")
                erreurs.append(str(exc))

        # 6. Badge des anomalies
        try:
            self._badger_ecritures(anomalies)
        except Exception as exc:
            logger.error(f"Erreur _badger_ecritures : {exc}")
            erreurs.append(str(exc))

        # 7. lot_propre = True si aucune anomalie bloquante
        lot_propre = not any(a["severite"] == "bloquante" for a in anomalies)

        # 8. Log dans journaux
        try:
            supabase.table("journaux").insert(
                {
                    "type_action": "verification_ecritures",
                    "contenu": (
                        f"{len(ecritures)} écritures vérifiées, "
                        f"{len(anomalies)} anomalies, lot_propre={lot_propre}"
                    ),
                    "statut": "ok" if lot_propre else "anomalie",
                    "metadata": {
                        "ecritures_verifiees": len(ecritures),
                        "anomalies": len(anomalies),
                        "lot_propre": lot_propre,
                    },
                }
            ).execute()
        except Exception as exc:
            logger.error(f"Erreur log journaux : {exc}")
            erreurs.append(str(exc))

        logger.info(
            f"verificateur_agent terminé : {len(ecritures)} vérifiées, "
            f"{len(anomalies)} anomalies, lot_propre={lot_propre}"
        )
        return VerificateurResult(
            ecritures_verifiees=len(ecritures),
            lot_propre=lot_propre,
            anomalies=anomalies,
            erreurs=erreurs,
        )

    def _verifier_equilibre_dc(self, ecritures: list[dict]) -> list[AnomalieVerificateur]:
        """Somme debit != somme credit → anomalie bloquante."""
        if not ecritures:
            return []

        sum_debit = sum(float(e.get("montant_debit", 0) or 0) for e in ecritures)
        sum_credit = sum(float(e.get("montant_credit", 0) or 0) for e in ecritures)

        if abs(sum_debit - sum_credit) > EPSILON_DC:
            premier_id = str(ecritures[0].get("id", ""))
            return [
                AnomalieVerificateur(
                    ecriture_id=premier_id,
                    type_anomalie="desequilibre_dc",
                    description=(
                        f"Déséquilibre débit/crédit : "
                        f"débit={sum_debit:.2f}, crédit={sum_credit:.2f}, "
                        f"écart={abs(sum_debit - sum_credit):.2f}"
                    ),
                    severite="bloquante",
                )
            ]
        return []

    def _verifier_coherence_pcg(self, ecriture: dict) -> AnomalieVerificateur | None:
        """Compte 7xxx au debit → anomalie avertissement (charge contre produit)."""
        compte_debit = str(ecriture.get("compte_debit", "") or "")
        if compte_debit.startswith("7"):
            return AnomalieVerificateur(
                ecriture_id=str(ecriture.get("id", "")),
                type_anomalie="compte_incoherent",
                description=(
                    f"Compte de produit {compte_debit} utilisé au débit — "
                    "incohérence avec le plan comptable général (PCG)"
                ),
                severite="avertissement",
            )
        return None

    def _detecter_doublons(self, ecritures: list[dict]) -> list[AnomalieVerificateur]:
        """Même montant_ttc + même tiers + même date_ecriture dans ecritures_sage → doublon potentiel."""
        supabase = self._get_supabase()
        anomalies: list[AnomalieVerificateur] = []

        for ecriture in ecritures:
            try:
                montant_ttc = ecriture.get("montant_ttc")
                tiers = ecriture.get("tiers")
                date_ecriture = ecriture.get("date_ecriture")

                if montant_ttc is None or not tiers or not date_ecriture:
                    continue

                resp = (
                    supabase.table("ecritures_sage")
                    .select("id")
                    .eq("montant_ttc", montant_ttc)
                    .eq("tiers", tiers)
                    .eq("date_ecriture", date_ecriture)
                    .execute()
                )
                if resp.data:
                    anomalies.append(
                        AnomalieVerificateur(
                            ecriture_id=str(ecriture.get("id", "")),
                            type_anomalie="doublon",
                            description=(
                                f"Doublon potentiel détecté dans ecritures_sage : "
                                f"montant_ttc={montant_ttc}, tiers={tiers}, "
                                f"date_ecriture={date_ecriture}"
                            ),
                            severite="avertissement",
                        )
                    )
            except Exception as exc:
                logger.error(f"Erreur détection doublon ecriture {ecriture.get('id')} : {exc}")

        return anomalies

    def _verifier_montants_atypiques(
        self, ecriture: dict, moyenne_tiers: float
    ) -> AnomalieVerificateur | None:
        """Montant > 10x la moyenne → avertissement montant_atypique."""
        montant_ttc = ecriture.get("montant_ttc")
        if montant_ttc is None:
            return None

        montant = float(montant_ttc)
        if moyenne_tiers > 0 and montant > SEUIL_ATYPIQUE * moyenne_tiers:
            return AnomalieVerificateur(
                ecriture_id=str(ecriture.get("id", "")),
                type_anomalie="montant_atypique",
                description=(
                    f"Montant atypique : {montant:.2f} > 10x la moyenne tiers "
                    f"({moyenne_tiers:.2f})"
                ),
                severite="avertissement",
            )
        return None

    def _badger_ecritures(self, anomalies: list[AnomalieVerificateur]) -> None:
        """UPDATE ecritures SET badge_anomalie=True, anomalie_description=... pour chaque anomalie."""
        if not anomalies:
            return

        supabase = self._get_supabase()
        for anomalie in anomalies:
            try:
                supabase.table("ecritures").update(
                    {
                        "badge_anomalie": True,
                        "anomalie_description": anomalie["type_anomalie"],
                    }
                ).eq("id", anomalie["ecriture_id"]).execute()
            except Exception as exc:
                logger.error(
                    f"Erreur badge ecriture {anomalie['ecriture_id']} : {exc}"
                )

"""Agent Lettrage #8 — rapprochement règlements/factures + compte 471 (JM Partners v2.2)."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import TypedDict, cast

from supabase import Client, create_client

__all__ = ["LettragePaire", "LettrageAgentResult", "LettrageAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_CODE_LETTRAGE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class LettragePaire(TypedDict):
    ecriture_id: str
    reglement_id: str
    montant: float
    tiers: str
    date_rapprochement: str
    methode: str       # "exact" | "approche" | "apprentissage"
    confiance: float   # 1.0 | 0.8 | 0.9


class LettrageAgentResult(TypedDict):
    paires_trouvees: int
    montant_total_lettre: float
    compte_471_restant: int
    paires: list[LettragePaire]
    erreurs: list[str]


class LettrageAgent:
    """Agent #8 — rapprochement règlements/factures, gestion compte 471."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise EnvironmentError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, dossier_id: str | None = None) -> LettrageAgentResult:
        """Si dossier_id=None : traite tous les dossiers actifs."""
        erreurs: list[str] = []
        toutes_paires: list[LettragePaire] = []

        try:
            supabase = self._get_supabase()

            # Récupère la liste des dossiers à traiter
            if dossier_id:
                dossiers = [dossier_id]
            else:
                resp = supabase.table("dossiers").select("id").eq("statut", "actif").execute()
                dossiers = [cast(dict, r)["id"] for r in (resp.data or [])]

            for dos_id in dossiers:
                try:
                    paires = self._traiter_dossier(dos_id)
                    toutes_paires.extend(paires)
                except Exception as exc:
                    erreurs.append(f"{dos_id}: {exc}")
                    logger.error("lettrage_agent — erreur dossier %s : %s", dos_id, exc)

            if toutes_paires:
                self._lettrer_ecritures(toutes_paires)

            compte_471 = self._compter_471(dossier_id)

        except Exception as exc:
            logger.error("lettrage_agent — erreur générale : %s", exc)
            erreurs.append(str(exc))
            return LettrageAgentResult(
                paires_trouvees=0,
                montant_total_lettre=0.0,
                compte_471_restant=0,
                paires=[],
                erreurs=erreurs,
            )

        montant_total = sum(p["montant"] for p in toutes_paires)
        self._log_journal(
            "lettrage",
            "ok",
            {"paires": len(toutes_paires), "montant": montant_total},
        )

        logger.info(
            "lettrage_agent : %d paires, %.2f€ lettrés, %d compte 471 restants",
            len(toutes_paires),
            montant_total,
            compte_471,
        )
        return LettrageAgentResult(
            paires_trouvees=len(toutes_paires),
            montant_total_lettre=montant_total,
            compte_471_restant=compte_471,
            paires=toutes_paires,
            erreurs=erreurs,
        )

    def _traiter_dossier(self, dos_id: str) -> list[LettragePaire]:
        """Rapproche factures et règlements pour un dossier."""
        supabase = self._get_supabase()

        # Factures non lettrées (401xxx, 411xxx)
        factures_resp = (
            supabase.table("ecritures")
            .select("id, compte, tiers, montant_ttc, date_ecriture")
            .eq("dossier_id", dos_id)
            .in_("compte", ["401", "411"])  # prefix match via app logic
            .eq("est_lettree", False)
            .execute()
        )
        factures = [cast(dict, r) for r in (factures_resp.data or [])]
        # Filtre côté application sur le préfixe de compte
        factures = [f for f in factures if str(f.get("compte", "")).startswith(("401", "411"))]

        # Règlements non lettrés (flux Regate + ecritures_sage)
        reglements_resp = (
            supabase.table("ecritures")
            .select("id, compte, tiers, montant_ttc, date_ecriture")
            .eq("dossier_id", dos_id)
            .eq("est_lettree", False)
            .in_("source", ["regate", "sage"])
            .execute()
        )
        reglements = [cast(dict, r) for r in (reglements_resp.data or [])]

        # Rapprochement par priorité
        paires_exact = self._rapprocher_exact(factures, reglements)
        ids_matches = {p["ecriture_id"] for p in paires_exact} | {p["reglement_id"] for p in paires_exact}
        factures_restantes = [f for f in factures if f["id"] not in ids_matches]
        reglements_restants = [r for r in reglements if r["id"] not in ids_matches]

        paires_approche = self._rapprocher_approche(factures_restantes, reglements_restants)
        ids_matches2 = {p["ecriture_id"] for p in paires_approche} | {p["reglement_id"] for p in paires_approche}
        reglements_non_matches = [r for r in reglements_restants if r["id"] not in ids_matches2]

        paires_apprentissage = self._appliquer_apprentissage(reglements_non_matches)

        return paires_exact + paires_approche + paires_apprentissage

    def _rapprocher_exact(
        self, factures: list[dict], reglements: list[dict]
    ) -> list[LettragePaire]:
        """Montant exact + même tiers → paire trouvée. Un règlement = une facture max."""
        paires: list[LettragePaire] = []
        reglements_utilises: set[str] = set()

        for facture in factures:
            for reglement in reglements:
                if reglement["id"] in reglements_utilises:
                    continue
                if (
                    facture.get("tiers") == reglement.get("tiers")
                    and abs(float(facture.get("montant_ttc", 0)) - float(reglement.get("montant_ttc", 0))) < 0.001
                ):
                    reglements_utilises.add(reglement["id"])
                    paires.append(
                        LettragePaire(
                            ecriture_id=facture["id"],
                            reglement_id=reglement["id"],
                            montant=float(facture.get("montant_ttc", 0)),
                            tiers=str(facture.get("tiers", "")),
                            date_rapprochement=datetime.now(timezone.utc).isoformat(),
                            methode="exact",
                            confiance=1.0,
                        )
                    )
                    break

        return paires

    def _rapprocher_approche(
        self, factures: list[dict], reglements: list[dict]
    ) -> list[LettragePaire]:
        """Même tiers + écart date ≤3j + montant ±0.01€ → paire."""
        paires: list[LettragePaire] = []
        reglements_utilises: set[str] = set()

        for facture in factures:
            f_montant = float(facture.get("montant_ttc", 0))
            f_tiers = facture.get("tiers", "")
            try:
                f_date = date.fromisoformat(str(facture.get("date_ecriture", "")))
            except (ValueError, TypeError):
                continue

            for reglement in reglements:
                if reglement["id"] in reglements_utilises:
                    continue
                r_montant = float(reglement.get("montant_ttc", 0))
                if reglement.get("tiers") != f_tiers:
                    continue
                if abs(f_montant - r_montant) > 0.01:
                    continue
                try:
                    r_date = date.fromisoformat(str(reglement.get("date_ecriture", "")))
                except (ValueError, TypeError):
                    continue
                if abs((f_date - r_date).days) > 3:
                    continue

                reglements_utilises.add(reglement["id"])
                paires.append(
                    LettragePaire(
                        ecriture_id=facture["id"],
                        reglement_id=reglement["id"],
                        montant=f_montant,
                        tiers=str(f_tiers),
                        date_rapprochement=datetime.now(timezone.utc).isoformat(),
                        methode="approche",
                        confiance=0.8,
                    )
                )
                break

        return paires

    def _appliquer_apprentissage(
        self, reglements_non_matches: list[dict]
    ) -> list[LettragePaire]:
        """Libellés bancaires mémorisés → rattachement automatique."""
        if not reglements_non_matches:
            return []

        paires: list[LettragePaire] = []
        supabase = self._get_supabase()

        try:
            libelles = [str(r.get("libelle", "")) for r in reglements_non_matches if r.get("libelle")]
            if not libelles:
                return []

            resp = (
                supabase.table("apprentissage")
                .select("libelle, tiers, facture_id, montant")
                .in_("libelle", libelles)
                .execute()
            )
            patterns = {cast(dict, r)["libelle"]: cast(dict, r) for r in (resp.data or [])}

            for reglement in reglements_non_matches:
                libelle = str(reglement.get("libelle", ""))
                if libelle not in patterns:
                    continue
                pattern = patterns[libelle]
                paires.append(
                    LettragePaire(
                        ecriture_id=str(pattern.get("facture_id", "")),
                        reglement_id=reglement["id"],
                        montant=float(reglement.get("montant_ttc", pattern.get("montant", 0))),
                        tiers=str(pattern.get("tiers", "")),
                        date_rapprochement=datetime.now(timezone.utc).isoformat(),
                        methode="apprentissage",
                        confiance=0.9,
                    )
                )
        except Exception as exc:
            logger.error("lettrage_agent — erreur apprentissage : %s", exc)

        return paires

    def _lettrer_ecritures(self, paires: list[LettragePaire]) -> None:
        """UPDATE ecritures est_lettree=True, lettre=code séquentiel A, B, C…"""
        supabase = self._get_supabase()
        for idx, paire in enumerate(paires):
            code = _CODE_LETTRAGE[idx % len(_CODE_LETTRAGE)]
            for ecriture_id in (paire["ecriture_id"], paire["reglement_id"]):
                if not ecriture_id:
                    continue
                try:
                    supabase.table("ecritures").update(
                        {"est_lettree": True, "lettre": code}
                    ).eq("id", ecriture_id).execute()
                except Exception as exc:
                    logger.error("lettrage_agent — erreur lettrage %s : %s", ecriture_id, exc)

    def _compter_471(self, dossier_id: str | None) -> int:
        """Compte les 471 non lettrés depuis plus de 30 jours."""
        try:
            supabase = self._get_supabase()
            limite = (date.today() - timedelta(days=30)).isoformat()
            query = (
                supabase.table("ecritures")
                .select("id", count="exact")  # type: ignore[arg-type,call-overload]
                .like("compte", "471%")
                .eq("est_lettree", False)
                .lt("date_ecriture", limite)
            )
            if dossier_id:
                query = query.eq("dossier_id", dossier_id)
            resp = query.execute()
            return resp.count or 0
        except Exception as exc:
            logger.error("lettrage_agent — erreur comptage 471 : %s", exc)
            return 0

    def _log_journal(self, action: str, statut: str, details: dict) -> None:
        """INSERT dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "agent": "lettrage_agent",
                    "action": action,
                    "statut": statut,
                    "details": details,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            logger.warning("lettrage_agent — log journal échoué : %s", exc)

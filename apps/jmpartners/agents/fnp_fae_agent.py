"""Agent FNP/FAE #10 — provisions Factures Non Parvenues + Factures À Établir (décembre uniquement)."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import TypedDict, cast

from supabase import Client, create_client

from apps.shared.telegram import send_telegram_message

__all__ = ["ProvisionFNP", "FNPFAEResult", "FNPFAEAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


class ProvisionFNP(TypedDict):
    dossier_id: str
    fournisseur: str
    montant_estime: float
    compte_charge: str      # 6xxxxx
    compte_provision: str   # 408xxx (FNP) ou 418xxx (FAE)
    description: str
    statut: str             # "a_valider_fnp" — JAMAIS "auto"


class FNPFAEResult(TypedDict):
    periode: str            # "hors_periode" | "decembre"
    dossiers_traites: int
    fnp_detectees: int
    fae_detectees: int
    montant_total_fnp: float
    montant_total_fae: float
    provisions: list[ProvisionFNP]
    erreurs: list[str]


def _resultat_hors_periode() -> FNPFAEResult:
    return FNPFAEResult(
        periode="hors_periode",
        dossiers_traites=0,
        fnp_detectees=0,
        fae_detectees=0,
        montant_total_fnp=0.0,
        montant_total_fae=0.0,
        provisions=[],
        erreurs=[],
    )


class FNPFAEAgent:
    """Agent #10 — provisions FNP/FAE, décembre uniquement."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise EnvironmentError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, dossier_id: str | None = None, force_mois: int | None = None) -> FNPFAEResult:
        """Garde-fou : si mois != 12, retourne hors_periode immédiatement."""
        mois = force_mois if force_mois is not None else date.today().month
        if mois != 12:
            logger.info("fnp_fae_agent — hors décembre (mois=%d), skip", mois)
            return _resultat_hors_periode()

        erreurs: list[str] = []
        toutes_provisions: list[ProvisionFNP] = []

        try:
            supabase = self._get_supabase()

            if dossier_id:
                dossiers = [dossier_id]
            else:
                resp = supabase.table("dossiers").select("id").eq("statut", "actif").execute()
                dossiers = [cast(dict, r)["id"] for r in (resp.data or [])]

            for dos_id in dossiers:
                try:
                    fnp = self._detecter_fnp(dos_id)
                    fae = self._detecter_fae(dos_id)
                    toutes_provisions.extend(fnp)
                    toutes_provisions.extend(fae)
                except Exception as exc:
                    erreurs.append(f"{dos_id}: {exc}")
                    logger.error("fnp_fae_agent — erreur dossier %s : %s", dos_id, exc)

            # INSERT provisions (statut="a_valider_fnp" uniquement)
            for provision in toutes_provisions:
                try:
                    supabase.table("ecritures").insert(
                        {
                            "dossier_id": provision["dossier_id"],
                            "tiers": provision["fournisseur"],
                            "montant_ttc": provision["montant_estime"],
                            "compte": provision["compte_provision"],
                            "compte_contrepartie": provision["compte_charge"],
                            "libelle": provision["description"],
                            "statut": "a_valider_fnp",
                            "source": "fnp_fae_agent",
                            "date_ecriture": date.today().isoformat(),
                        }
                    ).execute()
                except Exception as exc:
                    erreurs.append(f"insert provision {provision['fournisseur']}: {exc}")
                    logger.error("fnp_fae_agent — erreur insert : %s", exc)

        except Exception as exc:
            logger.error("fnp_fae_agent — erreur générale : %s", exc)
            erreurs.append(str(exc))
            return FNPFAEResult(
                periode="decembre",
                dossiers_traites=0,
                fnp_detectees=0,
                fae_detectees=0,
                montant_total_fnp=0.0,
                montant_total_fae=0.0,
                provisions=[],
                erreurs=erreurs,
            )

        fnp_list = [p for p in toutes_provisions if p["compte_provision"].startswith("408")]
        fae_list = [p for p in toutes_provisions if p["compte_provision"].startswith("418")]

        if toutes_provisions:
            nb_total = len(toutes_provisions)
            send_telegram_message(
                f"📋 *FNP/FAE clôture décembre*\n"
                f"{len(fnp_list)} FNP + {len(fae_list)} FAE détectées\n"
                f"Total : {nb_total} provisions à valider"
            )

        self._log_journal(
            "fnp_fae_detection",
            "a_valider",
            {"fnp": len(fnp_list), "fae": len(fae_list)},
        )

        logger.info(
            "fnp_fae_agent : %d FNP, %d FAE, %d dossiers traités",
            len(fnp_list),
            len(fae_list),
            len(dossiers) if "dossiers" in dir() else 0,
        )

        return FNPFAEResult(
            periode="decembre",
            dossiers_traites=len(dossiers) if "dossiers" in dir() else 0,
            fnp_detectees=len(fnp_list),
            fae_detectees=len(fae_list),
            montant_total_fnp=sum(p["montant_estime"] for p in fnp_list),
            montant_total_fae=sum(p["montant_estime"] for p in fae_list),
            provisions=toutes_provisions,
            erreurs=erreurs,
        )

    def _detecter_fnp(self, dos_id: str) -> list[ProvisionFNP]:
        """Factures Non Parvenues : comptes 408xxx ouverts → charge engagée sans facture."""
        supabase = self._get_supabase()
        try:
            resp = (
                supabase.table("ecritures")
                .select("id, tiers, montant_ttc, compte, libelle")
                .eq("dossier_id", dos_id)
                .like("compte", "408%")
                .eq("est_lettree", False)
                .execute()
            )
            rows = [cast(dict, r) for r in (resp.data or [])]
        except Exception as exc:
            logger.error("fnp_fae_agent — erreur lecture FNP %s : %s", dos_id, exc)
            return []

        provisions: list[ProvisionFNP] = []
        for row in rows:
            fournisseur = str(row.get("tiers", "Inconnu"))
            compte_provision = str(row.get("compte", "408000"))
            montant = self._estimer_montant(fournisseur, compte_provision, dos_id)
            provisions.append(
                ProvisionFNP(
                    dossier_id=dos_id,
                    fournisseur=fournisseur,
                    montant_estime=montant,
                    compte_charge="601000",
                    compte_provision=compte_provision,
                    description=f"FNP — {fournisseur} — {row.get('libelle', '')}",
                    statut="a_valider_fnp",
                )
            )
        return provisions

    def _detecter_fae(self, dos_id: str) -> list[ProvisionFNP]:
        """Factures À Établir : comptes 418xxx ouverts → prestation livrée sans facture."""
        supabase = self._get_supabase()
        try:
            resp = (
                supabase.table("ecritures")
                .select("id, tiers, montant_ttc, compte, libelle")
                .eq("dossier_id", dos_id)
                .like("compte", "418%")
                .eq("est_lettree", False)
                .execute()
            )
            rows = [cast(dict, r) for r in (resp.data or [])]
        except Exception as exc:
            logger.error("fnp_fae_agent — erreur lecture FAE %s : %s", dos_id, exc)
            return []

        provisions: list[ProvisionFNP] = []
        for row in rows:
            client = str(row.get("tiers", "Inconnu"))
            compte_provision = str(row.get("compte", "418000"))
            montant = self._estimer_montant(client, compte_provision, dos_id)
            provisions.append(
                ProvisionFNP(
                    dossier_id=dos_id,
                    fournisseur=client,
                    montant_estime=montant,
                    compte_charge="706000",
                    compte_provision=compte_provision,
                    description=f"FAE — {client} — {row.get('libelle', '')}",
                    statut="a_valider_fnp",
                )
            )
        return provisions

    def _estimer_montant(self, fournisseur: str, compte: str, dos_id: str) -> float:
        """Moyenne des 3 derniers mois pour ce compte/fournisseur."""
        try:
            supabase = self._get_supabase()
            resp = (
                supabase.table("ecritures")
                .select("montant_ttc")
                .eq("dossier_id", dos_id)
                .eq("tiers", fournisseur)
                .like("compte", f"{compte[:3]}%")
                .limit(3)
                .order("date_ecriture", desc=True)
                .execute()
            )
            rows = [cast(dict, r) for r in (resp.data or [])]
            if not rows:
                return 0.0
            montants = [float(r.get("montant_ttc", 0) or 0) for r in rows]
            return round(sum(montants) / len(montants), 2)
        except Exception as exc:
            logger.warning("fnp_fae_agent — erreur estimation %s : %s", fournisseur, exc)
            return 0.0

    def _log_journal(self, action: str, statut: str, details: dict) -> None:
        """INSERT dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "agent": "fnp_fae_agent",
                    "action": action,
                    "statut": statut,
                    "details": details,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            logger.warning("fnp_fae_agent — log journal échoué : %s", exc)

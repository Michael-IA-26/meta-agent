"""Agent Miroir Sage — synchronisation FEC et rapport matinal (JM Partners)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict, cast

import anthropic
from supabase import Client, create_client

from apps.shared.smtp import send_email

__all__ = ["EcritureSage", "SyncSageResult", "RapportMatinalResult", "MiroirSageAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

CLAUDE_MODEL = "claude-opus-4-7"


class EcritureSage(TypedDict):
    journal: str
    compte: str
    tiers: str | None
    libelle: str
    debit: float
    credit: float
    date_ecriture: str
    source: str  # "agent" | "collaborateur" | "paie" | "od_manuel"


class SyncSageResult(TypedDict):
    ecritures_importees: int
    ecritures_nouvelles: int
    date_sync: str


class RapportMatinalResult(TypedDict):
    collaborateurs_notifies: int
    dossiers_traites_nuit: int
    actions_requises: int
    anomalies: int


class MiroirSageAgent:
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

    def _detect_source(self, ecriture_lib: str, compte_num: str) -> str:
        lib_upper = ecriture_lib.upper()
        if "PAIE" in lib_upper or "SALAIRES" in lib_upper:
            return "paie"
        if compte_num.startswith("681"):
            return "od_manuel"
        return "collaborateur"

    def _sync_fec(self, fec_path: str | None = None) -> SyncSageResult:
        """
        1. Downloads FEC CSV from Supabase Storage bucket "fec_exports" (default path: "latest_fec.csv")
        2. Parses CSV with standard FEC columns: JournalCode, EcritureDate, CompteNum, CompteLib, Debit, Credit, EcritureLib, PieceRef
           CSV delimiter is ";", decimal separator is ","
        3. Computes hash of file content (hashlib.md5)
        4. Checks syncs_sage table for existing hash — if found, returns with ecritures_nouvelles=0
        5. Detects source heuristic per row:
           - EcritureLib contains "PAIE" or "SALAIRES" → "paie"
           - CompteNum starts with "681" → "od_manuel"
           - else → "collaborateur"
        6. INSERT INTO ecritures_sage (journal, compte, tiers, libelle, debit, credit, date_ecriture, source)
        7. INSERT INTO syncs_sage (date_sync, nb_lignes, hash_fichier)
        """
        sb = self._get_supabase()
        path = fec_path or "latest_fec.csv"

        raw_bytes: bytes = sb.storage.from_("fec_exports").download(path)

        file_hash = hashlib.md5(raw_bytes).hexdigest()

        existing = (
            sb.table("syncs_sage")
            .select("id")
            .eq("hash_fichier", file_hash)
            .execute()
        )
        date_sync = datetime.now(timezone.utc).isoformat()

        if existing.data:
            logger.info("miroir_sage — FEC déjà synchronisé (hash=%s)", file_hash)
            return SyncSageResult(
                ecritures_importees=0,
                ecritures_nouvelles=0,
                date_sync=date_sync,
            )

        content = raw_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter=";")

        ecritures: list[dict] = []
        for row in reader:
            journal = row.get("JournalCode", "")
            compte_num = row.get("CompteNum", "")
            ecriture_lib = row.get("EcritureLib", "")
            piece_ref = row.get("PieceRef", None) or None

            raw_debit = row.get("Debit", "0").replace(",", ".").strip()
            raw_credit = row.get("Credit", "0").replace(",", ".").strip()

            try:
                debit = float(raw_debit) if raw_debit else 0.0
            except ValueError:
                debit = 0.0

            try:
                credit = float(raw_credit) if raw_credit else 0.0
            except ValueError:
                credit = 0.0

            source = self._detect_source(ecriture_lib, compte_num)

            ecritures.append(
                {
                    "journal": journal,
                    "compte": compte_num,
                    "tiers": piece_ref,
                    "libelle": ecriture_lib,
                    "debit": debit,
                    "credit": credit,
                    "date_ecriture": row.get("EcritureDate", ""),
                    "source": source,
                }
            )

        if ecritures:
            sb.table("ecritures_sage").insert(ecritures).execute()

        sb.table("syncs_sage").insert(
            {
                "date_sync": date_sync,
                "nb_lignes": len(ecritures),
                "hash_fichier": file_hash,
            }
        ).execute()

        logger.info(
            "miroir_sage — %d écritures importées depuis %s", len(ecritures), path
        )

        return SyncSageResult(
            ecritures_importees=len(ecritures),
            ecritures_nouvelles=len(ecritures),
            date_sync=date_sync,
        )

    def _envoyer_rapport_matinal(self) -> RapportMatinalResult:
        """
        1. Fetches collaborateurs from Supabase table "collaborateurs"
        2. For each collaborateur, fetches their dossiers (table dossiers, filtered by collaborateur_id)
        3. Fetches from ecritures_sage (last 24h), revision (statut=en_attente), journaux (last 24h), echeances (due today)
        4. Builds prompt for Claude API with sections: traité cette nuit / actions requises / anomalies / échéances du jour
        5. Sends email via from apps.shared.smtp import send_email
        6. If SMTP not configured or send_email fails: log warning, continue (no exception)
        """
        sb = self._get_supabase()
        client = self._get_anthropic()

        collaborateurs_resp = sb.table("collaborateurs").select("*").execute()
        collaborateurs: list[dict[str, Any]] = cast(
            list[dict[str, Any]], collaborateurs_resp.data or []
        )

        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        today_str = datetime.now(timezone.utc).date().isoformat()

        ecritures_resp = (
            sb.table("ecritures_sage")
            .select("*")
            .gte("created_at", since_24h)
            .execute()
        )
        ecritures_nuit = ecritures_resp.data or []

        revision_resp = (
            sb.table("revision")
            .select("*")
            .eq("statut", "en_attente")
            .execute()
        )
        anomalies_list = revision_resp.data or []

        journaux_resp = (
            sb.table("journaux")
            .select("*")
            .gte("created_at", since_24h)
            .execute()
        )
        journaux_nuit = journaux_resp.data or []

        echeances_resp = (
            sb.table("echeances")
            .select("*")
            .eq("date_echeance", today_str)
            .execute()
        )
        echeances_jour = echeances_resp.data or []

        nb_actions = len(echeances_jour) + len(anomalies_list)
        nb_anomalies = len(anomalies_list)
        dossiers_traites = len(journaux_nuit)

        collaborateurs_notifies = 0

        for collab in collaborateurs:
            collab_id: str = str(collab.get("id", ""))
            collab_email: str = str(collab.get("email", ""))
            collab_nom: str = str(collab.get("nom", "Collaborateur"))

            if not collab_email:
                continue

            dossiers_resp = (
                sb.table("dossiers")
                .select("*")
                .eq("collaborateur_id", collab_id)
                .execute()
            )
            dossiers = dossiers_resp.data or []

            prompt = (
                f"Tu es un assistant comptable. Génère un rapport matinal concis en français "
                f"pour {collab_nom}.\n\n"
                f"## Traité cette nuit\n"
                f"- {len(ecritures_nuit)} écritures Sage synchronisées\n"
                f"- {len(journaux_nuit)} entrées journal créées\n"
                f"- {len(dossiers)} dossiers assignés à ce collaborateur\n\n"
                f"## Actions requises\n"
                f"- {len(echeances_jour)} échéances aujourd'hui\n"
                f"- {len(anomalies_list)} anomalies en attente de validation\n\n"
                f"## Anomalies\n"
                f"{json.dumps(anomalies_list[:5], ensure_ascii=False, indent=2)}\n\n"
                f"## Échéances du jour\n"
                f"{json.dumps(echeances_jour[:5], ensure_ascii=False, indent=2)}\n\n"
                f"Résume en 3-5 phrases les points clés pour ce collaborateur."
            )

            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )

            first_block = message.content[0] if message.content else None
            rapport_text = (
                first_block.text
                if first_block is not None and isinstance(first_block, anthropic.types.TextBlock)
                else ""
            )

            subject = f"Rapport matinal JM Partners — {today_str}"
            body = f"Bonjour {collab_nom},\n\n{rapport_text}\n\nBonne journée,\nJM Partners Automation"

            try:
                sent = send_email(to=collab_email, subject=subject, body=body)
                if sent:
                    collaborateurs_notifies += 1
                else:
                    logger.warning(
                        "miroir_sage — email non envoyé à %s (send_email=False)",
                        collab_email,
                    )
            except Exception as exc:
                logger.warning(
                    "miroir_sage — erreur envoi email à %s : %s", collab_email, exc
                )

        logger.info(
            "miroir_sage — rapport matinal : %d/%d collaborateurs notifiés",
            collaborateurs_notifies,
            len(collaborateurs),
        )

        return RapportMatinalResult(
            collaborateurs_notifies=collaborateurs_notifies,
            dossiers_traites_nuit=dossiers_traites,
            actions_requises=nb_actions,
            anomalies=nb_anomalies,
        )

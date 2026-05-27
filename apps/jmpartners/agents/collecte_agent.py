"""Agent Collecte #1 — surveillance et récupération documents entrants (JM Partners v2.2)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TypedDict

from supabase import Client, create_client

__all__ = ["DocumentCollecte", "CollecteResult", "CollecteAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
OUTLOOK_MOCK_DIR = os.getenv("OUTLOOK_MOCK_DIR", "")
REGATE_API_KEY = os.getenv("REGATE_API_KEY", "")
PENNYLANE_API_KEY = os.getenv("PENNYLANE_API_KEY", "")


class DocumentCollecte(TypedDict):
    source: str
    nom_fichier: str
    contenu_binaire: bytes
    message_id: str
    expediteur: str | None
    date_reception: str
    dossier_id_hint: str | None


class CollecteResult(TypedDict):
    documents_recus: int
    documents_dedupliques: int
    documents_uploades: int
    documents: list[DocumentCollecte]
    erreurs: list[str]


class CollecteAgent:
    """Agent #1 — collecte les documents depuis toutes les sources actives."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise EnvironmentError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def run(self, sources: list[str] | None = None) -> CollecteResult:
        """Collecte depuis toutes les sources actives (ou celles spécifiées)."""
        sources_actives = sources or ["outlook", "regate", "pennylane", "manuel"]
        tous_documents: list[DocumentCollecte] = []
        erreurs: list[str] = []

        collecteurs = {
            "outlook": self._collecter_outlook,
            "regate": self._collecter_regate,
            "pennylane": self._collecter_pennylane,
            "manuel": self._collecter_manuel,
        }

        for source in sources_actives:
            if source not in collecteurs:
                erreurs.append(f"Source inconnue : {source}")
                continue
            try:
                docs = collecteurs[source]()
                tous_documents.extend(docs)
                logger.info("collecte_agent — source=%s docs=%d", source, len(docs))
            except Exception as exc:
                erreurs.append(f"{source}: {exc}")
                logger.error("collecte_agent — erreur source %s : %s", source, exc)

        dedupliques = 0
        uploades = 0
        for doc in tous_documents:
            try:
                uploaded = self._upload_supabase(doc)
                if uploaded:
                    uploades += 1
                else:
                    dedupliques += 1
            except Exception as exc:
                erreurs.append(f"upload {doc['nom_fichier']}: {exc}")
                logger.error("collecte_agent — erreur upload : %s", exc)

        return CollecteResult(
            documents_recus=len(tous_documents),
            documents_dedupliques=dedupliques,
            documents_uploades=uploades,
            documents=tous_documents,
            erreurs=erreurs,
        )

    def _collecter_outlook(self) -> list[DocumentCollecte]:
        """Collecte depuis compta@jmpartners.fr (Outlook API / mock local)."""
        if not OUTLOOK_MOCK_DIR or not os.path.isdir(OUTLOOK_MOCK_DIR):
            logger.debug("collecte_agent — Outlook : mock dir absent, source ignorée")
            return []
        docs = []
        for nom in os.listdir(OUTLOOK_MOCK_DIR):
            if not nom.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                continue
            chemin = os.path.join(OUTLOOK_MOCK_DIR, nom)
            try:
                with open(chemin, "rb") as f:
                    contenu = f.read()
                docs.append(
                    DocumentCollecte(
                        source="outlook",
                        nom_fichier=nom,
                        contenu_binaire=contenu,
                        message_id=f"mock-outlook-{nom}",
                        expediteur=None,
                        date_reception=datetime.now(timezone.utc).isoformat(),
                        dossier_id_hint=None,
                    )
                )
            except OSError as exc:
                logger.warning("collecte_agent — lecture fichier mock %s : %s", nom, exc)
        return docs

    def _collecter_regate(self) -> list[DocumentCollecte]:
        """Collecte depuis l'API Regate (~150 dossiers)."""
        if not REGATE_API_KEY:
            logger.debug("collecte_agent — Regate : REGATE_API_KEY absent, source ignorée")
            return []
        # En prod : appel Regate API
        return []

    def _collecter_pennylane(self) -> list[DocumentCollecte]:
        """Collecte depuis l'API PennyLane (<10 dossiers)."""
        if not PENNYLANE_API_KEY:
            logger.debug("collecte_agent — PennyLane : PENNYLANE_API_KEY absent, source ignorée")
            return []
        # En prod : appel PennyLane API
        return []

    def _collecter_manuel(self) -> list[DocumentCollecte]:
        """Collecte dépôts manuels (toujours actif — retourne [] en l'absence d'interface)."""
        return []

    def _upload_supabase(self, doc: DocumentCollecte) -> bool:
        """Upload dans Storage + INSERT documents. Retourne False si doublon."""
        supabase = self._get_supabase()
        # Vérification doublon
        existing = (
            supabase.table("documents")
            .select("id")
            .eq("message_id", doc["message_id"])
            .execute()
        )
        if existing.data:
            logger.debug("collecte_agent — doublon ignoré : %s", doc["message_id"])
            return False

        # Upload Storage
        chemin_storage = f"{doc['source']}/{doc['nom_fichier']}"
        supabase.storage.from_("documents").upload(
            chemin_storage,
            doc["contenu_binaire"],
            {"content-type": "application/octet-stream"},
        )

        # INSERT table documents
        supabase.table("documents").insert(
            {
                "nom_fichier": doc["nom_fichier"],
                "source": doc["source"],
                "message_id": doc["message_id"],
                "expediteur": doc["expediteur"],
                "dossier_id_hint": doc["dossier_id_hint"],
                "chemin_storage": chemin_storage,
                "statut": "en_attente_ocr",
                "date_reception": doc["date_reception"],
            }
        ).execute()

        self._log_journal("collecte", "en_attente_ocr", {"nom_fichier": doc["nom_fichier"], "source": doc["source"]})
        return True

    def _log_journal(self, action: str, statut: str, details: dict) -> None:
        """INSERT dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "agent": "collecte_agent",
                    "action": action,
                    "statut": statut,
                    "details": details,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            logger.warning("collecte_agent — log journal échoué : %s", exc)

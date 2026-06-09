import logging
import os
from typing import Any, cast

from supabase import Client, create_client

from apps.leadcommercial.scorer import IcpContext

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
CABINET_ID = os.getenv("CABINET_ID", "")

_client: Client | None = None


def get_client() -> Client:
    """Return a singleton Supabase client, initialised on first call."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError(
                "SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant — configure Doppler"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def is_lead_locked(siren: str) -> bool:
    """Return True if siren already has a row in lead_locks."""
    result = (
        get_client().table("lead_locks").select("siren").eq("siren", siren).execute()
    )
    return len(result.data) > 0


def insert_lead(lead: dict) -> str:
    """Insert a qualified lead into the leads table; return the new UUID."""
    if not CABINET_ID:
        raise ValueError("CABINET_ID manquant — configure Doppler")
    row = {
        "cabinet_id": CABINET_ID,
        "siren": lead["siren"],
        "denomination": lead.get("denomination"),
        "forme_juridique": lead.get("forme_juridique"),
        "code_naf": lead.get("code_naf"),
        "adresse": lead.get("commune") or None,
        "dept": lead.get("dept"),
        "date_creation": lead.get("date_creation") or None,
        "dirigeant_prenom": lead.get("dirigeant_prenom") or None,
        "dirigeant_nom": lead.get("dirigeant_nom") or None,
        "dirigeant_email": lead.get("dirigeant_email") or None,
        "site_web": lead.get("site_web") or None,
        "score": lead.get("score"),
        "signal_type": lead.get("signal_type"),
        "signal_source": "sirene",
    }
    result = get_client().table("leads").insert(row).execute()
    rows = cast(list[Any], result.data)
    return str(rows[0]["id"])


def create_lock(siren: str) -> None:
    """Insert a row in lead_locks to claim exclusivity on the siren."""
    if not CABINET_ID:
        raise ValueError("CABINET_ID manquant — configure Doppler")
    get_client().table("lead_locks").insert(
        {"siren": siren, "cabinet_id": CABINET_ID}
    ).execute()


def fetch_icp(cabinet_id: str) -> IcpContext | None:
    """Fetch ICP settings for the given cabinet from Supabase.

    Returns None if no ICP is found or if Supabase is unreachable (graceful
    fallback: the scorer will use its built-in defaults).
    """
    try:
        result = (
            get_client()
            .table("icps")
            .select(
                "secteurs,zone_deps,forme_juridique,"
                "signaux_prioritaires,signaux_exclus,scoring_rules"
            )
            .eq("cabinet_id", cabinet_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error(f"Erreur lecture ICP pour cabinet {cabinet_id}: {exc}")
        return None
    rows = cast(list[Any], result.data)
    if not rows:
        logger.warning(f"Aucun ICP trouve pour cabinet {cabinet_id}")
        return None
    row = rows[0]
    return {
        "secteurs": row.get("secteurs") or [],
        "zone_deps": row.get("zone_deps") or [],
        "forme_juridique": row.get("forme_juridique") or [],
        "signaux_prioritaires": row.get("signaux_prioritaires") or [],
        "signaux_exclus": row.get("signaux_exclus") or [],
        "scoring_rules": row.get("scoring_rules") or {},
    }


def persist_lead(lead: dict) -> bool:
    """Check lock, then insert lead and create lock if unlocked.

    Returns True if the lead was persisted, False if already locked (skipped).
    Note: insert_lead and create_lock are not wrapped in a DB transaction;
    a crash between the two would leave an orphan lead row without a lock.
    """
    siren = lead.get("siren")
    if not siren:
        logger.warning("Lead sans SIREN — skip persistance")
        return False

    if is_lead_locked(siren):
        logger.info(f"SIREN {siren} deja lock — lead ignore")
        return False

    lead_id = insert_lead(lead)
    try:
        create_lock(siren)
    except Exception as exc:
        logger.error(
            f"Lead {siren} inséré (id={lead_id}) mais lock non créé — "
            f"doublon possible au prochain cycle : {exc}"
        )
        return True
    logger.info(f"Lead {siren} persiste (id={lead_id}) et lock cree")
    return True

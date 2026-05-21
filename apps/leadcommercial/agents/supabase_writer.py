"""Agent: vérifie le lock Supabase puis insère le lead → bool."""
import logging
from typing import TypedDict

from apps.leadcommercial.supabase_client import persist_lead

logger = logging.getLogger(__name__)


class WriteInput(TypedDict):
    """Minimal lead fields required by supabase_client.persist_lead."""

    siren: str | None
    denomination: str
    forme_juridique: str | None
    code_naf: str | None
    commune: str | None
    dept: str
    date_creation: str | None
    score: int
    signal_type: str
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def write_lead(params: WriteInput) -> bool:
    """Check exclusivity lock then insert the lead into Supabase.

    Returns True if the lead was persisted, False if the SIREN is already
    locked by another cabinet or if siren is missing.
    """
    result = persist_lead(dict(params))
    logger.debug(
        "supabase_writer: siren=%s persisted=%s", params.get("siren"), result
    )
    return result

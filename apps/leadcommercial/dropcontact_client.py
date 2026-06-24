import logging
import os
import time
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

DROPCONTACT_API_KEY = os.getenv("DROPCONTACT_API_KEY", "")
DROPCONTACT_BASE_URL = "https://api.dropcontact.com"

# Max 3 tentatives de polling si l'API répond en mode asynchrone
_POLL_RETRIES = 3
_POLL_INTERVAL = 3.0


class DropcontactResult(TypedDict):
    email: str
    email_valid: bool


def fetch_email(
    first_name: str,
    last_name: str,
    company: str,
    siren: str | None = None,
) -> DropcontactResult:
    """Cherche l'email professionnel d'un dirigeant via Dropcontact.

    Retourne un résultat vide (dégradation gracieuse) si la clé est absente,
    si le dirigeant est inconnu, ou en cas d'erreur API.
    """
    empty: DropcontactResult = {"email": "", "email_valid": False}

    if not DROPCONTACT_API_KEY:
        logger.warning("DROPCONTACT_API_KEY manquant — enrichissement email désactivé")
        return empty

    if not last_name and not first_name:
        logger.debug("Dropcontact: pas de dirigeant connu — skip")
        return empty

    contact: dict = {"first_name": first_name, "last_name": last_name, "company": company}
    if siren:
        contact["num_siret"] = siren

    payload = {"data": [contact], "siren": True}

    try:
        response = httpx.post(
            f"{DROPCONTACT_BASE_URL}/b2b/v2/enrich/single",
            json=payload,
            headers={
                "X-Access-Token": DROPCONTACT_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Dropcontact HTTP %s pour %s %s: %s",
            e.response.status_code,
            first_name,
            last_name,
            e.response.text[:200],
        )
        return empty
    except httpx.RequestError as e:
        logger.error("Erreur réseau Dropcontact: %s", e)
        return empty

    data = response.json()

    if data.get("error"):
        logger.error("Dropcontact erreur API: %s", data.get("reason", "inconnu"))
        return empty

    # Réponse synchrone directe
    contacts = data.get("data", [])
    if contacts:
        return _extract_email(contacts[0])

    # Réponse asynchrone : on poll avec l'identifiant de requête
    request_id = data.get("request_id")
    if request_id:
        return _poll_result(request_id)

    logger.debug("Dropcontact: réponse vide pour %s %s", first_name, last_name)
    return empty


def _poll_result(request_id: str) -> DropcontactResult:
    empty: DropcontactResult = {"email": "", "email_valid": False}
    for attempt in range(_POLL_RETRIES):
        time.sleep(_POLL_INTERVAL)
        try:
            response = httpx.get(
                f"{DROPCONTACT_BASE_URL}/b2b/v2/enrich/{request_id}",
                headers={"X-Access-Token": DROPCONTACT_API_KEY},
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Dropcontact polling erreur (tentative %d): %s", attempt + 1, e)
            continue

        data = response.json()
        if data.get("error"):
            break
        contacts = data.get("data", [])
        if contacts:
            return _extract_email(contacts[0])

        if data.get("status") == "loading":
            logger.debug("Dropcontact: encore en cours (tentative %d)", attempt + 1)
            continue

    logger.warning("Dropcontact: résultat non disponible pour request_id=%s", request_id)
    return empty


def _extract_email(contact: dict) -> DropcontactResult:
    emails = contact.get("email", [])
    if not emails:
        return {"email": "", "email_valid": False}
    # Préférer un email valid=True et non catch_all
    best = next(
        (e for e in emails if e.get("valid") and not e.get("catch_all")),
        next((e for e in emails if e.get("valid")), emails[0]),
    )
    return {
        "email": best.get("email", ""),
        "email_valid": bool(best.get("valid")),
    }

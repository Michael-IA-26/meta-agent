import logging
import os

from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def save_email(analyzed_email: dict) -> bool:
    try:
        client = get_supabase_client()
        data = {
            "agent_id": "email_agent",
            "user_id": "michael",
            "email_subject": analyzed_email.get("subject", ""),
            "email_from": analyzed_email.get("from", ""),
            "email_date": analyzed_email.get("date", ""),
            "priority": analyzed_email.get("priority", "moyenne"),
            "category": analyzed_email.get("category", "information"),
            "summary": analyzed_email.get("summary", ""),
            "action": analyzed_email.get("action"),
            "suggested_reply": analyzed_email.get("suggested_reply"),
        }
        client.table("emails_analyzed").insert(data).execute()
        logger.info(f"Email sauvegarde : {data['email_subject'][:50]}")
        return True
    except Exception as e:
        logger.error(f"Erreur Supabase : {e}")
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def save_weekly_stats(stats: dict) -> bool:
    try:
        client = get_supabase_client()
        client.table("agent_weekly_stats").insert(stats).execute()
        logger.info("KPIs hebdo sauvegardes")
        return True
    except Exception as e:
        logger.error(f"Erreur KPIs Supabase : {e}")
        return False


if __name__ == "__main__":
    print("Test insertion Supabase...")
    test_email = {
        "subject": "Test email",
        "from": "test@test.com",
        "date": "2026-04-27",
        "priority": "haute",
        "category": "action_requise",
        "summary": "Email de test pour valider la connexion Supabase",
        "action": "Verifier la connexion",
        "suggested_reply": None,
    }
    result = save_email(test_email)
    print(f"Resultat : {'OK' if result else 'ERREUR'}")

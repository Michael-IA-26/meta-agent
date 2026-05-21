import logging
import os
from datetime import datetime
from typing import cast

from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return create_client(url, key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def save_email(analyzed_email: dict) -> bool:
    try:
        client = get_supabase_client()
        subject_str: str = analyzed_email.get("subject", "")
        data: dict[str, str | None] = {
            "agent_id": "email_agent",
            "user_id": "michael",
            "email_subject": subject_str,
            "email_from": analyzed_email.get("from", ""),
            "email_date": analyzed_email.get("date", ""),
            "priority": analyzed_email.get("priority", "moyenne"),
            "category": analyzed_email.get("category", "information"),
            "summary": analyzed_email.get("summary", ""),
            "action": analyzed_email.get("action"),
            "suggested_reply": analyzed_email.get("suggested_reply"),
        }
        client.table("emails_analyzed").insert(cast(dict, data)).execute()
        logger.info(f"Email sauvegarde : {subject_str[:50]}")
        return True
    except Exception as e:
        logger.error(f"Erreur Supabase : {e}")
        return False


def calculate_and_save_kpis(emails_analyzed: list, temps_agent_sec: float) -> dict:
    try:
        client = get_supabase_client()

        # Parametres configurables
        temps_theorique_min = int(os.getenv("TEMPS_THEORIQUE_MIN", "45"))
        tarif_horaire = float(os.getenv("HOURLY_RATE", "80"))

        # Calculs
        temps_agent_min = round(temps_agent_sec / 60, 1)
        temps_gagne_min = max(0, temps_theorique_min - temps_agent_min)
        gain_pourcentage = round((temps_gagne_min / temps_theorique_min) * 100, 1)
        valeur_estimee_eur = round((temps_gagne_min / 60) * tarif_horaire, 2)

        # Semaine courante
        week = datetime.now().strftime("%Y-W%W")

        stats = {
            "agent_id": "email_agent",
            "week": week,
            "validity_score": 1.0,
            "cost_eur": 0.0,
            "billed_eur": 0.0,
            "tasks_processed": len(emails_analyzed),
            "time_saved_min": int(temps_gagne_min),
        }

        client.table("agent_weekly_stats").insert(cast(dict, stats)).execute()

        kpis = {
            "emails_analyses": len(emails_analyzed),
            "temps_theorique_min": temps_theorique_min,
            "temps_agent_min": temps_agent_min,
            "temps_gagne_min": temps_gagne_min,
            "gain_pourcentage": gain_pourcentage,
            "valeur_estimee_eur": valeur_estimee_eur,
            "semaine": week,
        }

        logger.info(f"KPIs sauvegardes : {kpis}")
        return kpis

    except Exception as e:
        logger.error(f"Erreur KPIs : {e}")
        return {}


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
    print("Test KPIs...")
    test_emails = [{"subject": f"Email {i}"} for i in range(5)]
    kpis = calculate_and_save_kpis(test_emails, temps_agent_sec=120)
    print("\nKPIs calcules :")
    for k, v in kpis.items():
        print(f"  {k}: {v}")

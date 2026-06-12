"""File de jobs Supabase — polling + dispatch par type."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

__all__ = ["claim_next_job", "run_pending_jobs"]

logger = logging.getLogger(__name__)


def _get_supabase():  # type: ignore[return]
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY requis")
    return create_client(url, key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_next_job(supabase=None) -> dict[str, Any] | None:
    """Sélectionne le job 'pending' le plus ancien et le bascule atomiquement en 'running'.

    Returns the job dict or None if queue is empty.
    """
    sb = supabase or _get_supabase()
    try:
        resp = (
            sb.table("jobs")
            .select("*")
            .eq("statut", "pending")
            .order("created_at")
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error(f"jobs.claim_next_job — lecture échouée : {exc}")
        return None

    if not resp.data:
        return None

    job: dict[str, Any] = resp.data[0]
    job_id: str = job["id"]

    try:
        sb.table("jobs").update({
            "statut": "running",
            "updated_at": _now_iso(),
        }).eq("id", job_id).eq("statut", "pending").execute()
    except Exception as exc:
        logger.error(f"jobs.claim_next_job — transition running échouée {job_id} : {exc}")
        return None

    job["statut"] = "running"
    return job


def run_pending_jobs(
    handlers: dict[str, Callable[[dict[str, Any]], Any]],
    supabase=None,
    max_jobs: int = 50,
) -> int:
    """Dépile et exécute les jobs pending via les handlers fournis.

    Args:
        handlers: mapping type → callable(job) appelé avec le job dict.
        supabase: client optionnel (construit depuis env sinon).
        max_jobs: limite de sécurité pour éviter une boucle infinie.

    Returns:
        Nombre de jobs traités.
    """
    sb = supabase or _get_supabase()
    processed = 0

    for _ in range(max_jobs):
        job = claim_next_job(sb)
        if job is None:
            break

        job_id: str = job["id"]
        job_type: str = job.get("type", "")
        processed += 1

        handler = handlers.get(job_type)
        if handler is None:
            logger.warning(f"jobs — type inconnu : {job_type!r} (job {job_id})")
            _mark(sb, job_id, "error", f"type de job inconnu : {job_type!r}")
            continue

        try:
            handler(job)
            _mark(sb, job_id, "done")
        except Exception as exc:
            logger.error(f"jobs — handler {job_type} échoué pour {job_id} : {exc}")
            _mark(sb, job_id, "error", str(exc))

    return processed


def _mark(supabase, job_id: str, statut: str, error: str | None = None) -> None:
    payload: dict[str, Any] = {"statut": statut, "updated_at": _now_iso()}
    if error is not None:
        payload["error"] = error
    try:
        supabase.table("jobs").update(payload).eq("id", job_id).execute()
    except Exception as exc:
        logger.error(f"jobs._mark — mise à jour {job_id} échouée : {exc}")

"""Health check global — teste tous les services externes de Meta-Agent."""

from __future__ import annotations

import logging
import os
import sys
from typing import NamedTuple

import httpx

logging.basicConfig(level=logging.WARNING, format="%(levelname)s — %(message)s")

TELEGRAM_API = "https://api.telegram.org"


class ServiceResult(NamedTuple):
    """Résultat d'un check de service."""

    name: str
    ok: bool
    detail: str


def check_anthropic() -> ServiceResult:
    """Vérifie que ANTHROPIC_API_KEY est présente et non vide."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return ServiceResult("Anthropic API", False, "ANTHROPIC_API_KEY manquant ou vide")
    if len(key) < 20:
        return ServiceResult("Anthropic API", False, "ANTHROPIC_API_KEY semble invalide (trop courte)")
    return ServiceResult("Anthropic API", True, f"clé présente ({key[:8]}…)")


def check_supabase_table(client: object, table: str) -> tuple[bool, str]:
    """Effectue un SELECT 1 sur une table Supabase.

    Args:
        client: Client Supabase initialisé.
        table: Nom de la table.

    Returns:
        Tuple (succès, message).
    """
    try:
        resp = client.table(table).select("id").limit(1).execute()  # type: ignore[union-attr,attr-defined]
        count = len(resp.data) if resp.data else 0
        return True, f"'{table}' OK ({count} ligne(s))"
    except Exception as exc:
        return False, f"'{table}' erreur : {exc}"


def check_supabase() -> list[ServiceResult]:
    """Teste la connexion Supabase et l'accès aux tables principales.

    Returns:
        Liste de ServiceResult, un par table testée.
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not url or not key:
        return [ServiceResult("Supabase", False, "SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant")]

    try:
        from supabase import create_client  # type: ignore[attr-defined]

        client = create_client(url, key)
    except Exception as exc:
        return [ServiceResult("Supabase", False, f"Impossible d'initialiser le client : {exc}")]

    results = []
    for table in ("leads", "emails", "dossiers"):
        ok, detail = check_supabase_table(client, table)
        results.append(ServiceResult(f"Supabase:{table}", ok, detail))
    return results


def check_telegram() -> ServiceResult:
    """Teste la connexion Telegram via getChat.

    Returns:
        ServiceResult avec le statut de la connexion.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return ServiceResult(
            "Telegram",
            False,
            "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant",
        )

    try:
        r = httpx.get(
            f"{TELEGRAM_API}/bot{token}/getChat",
            params={"chat_id": chat_id},
            timeout=8,
        )
        data = r.json()
        if data.get("ok"):
            chat = data.get("result", {})
            title = chat.get("title") or chat.get("first_name") or chat_id
            return ServiceResult("Telegram", True, f"chat '{title}' accessible")
        return ServiceResult(
            "Telegram",
            False,
            data.get("description", "Erreur Telegram inconnue"),
        )
    except Exception as exc:
        return ServiceResult("Telegram", False, str(exc))


def _print_row(result: ServiceResult) -> None:
    """Affiche une ligne de résultat formatée."""
    status = "✅" if result.ok else "❌"
    print(f"  {status}  {result.name:<25} {result.detail}")


def main() -> None:
    """Point d'entrée du health check global Meta-Agent."""
    print("=" * 60)
    print("  META-AGENT — Health Check")
    print("=" * 60)
    print()

    all_results: list[ServiceResult] = []

    print("Anthropic")
    r = check_anthropic()
    _print_row(r)
    all_results.append(r)

    print()
    print("Supabase")
    for r in check_supabase():
        _print_row(r)
        all_results.append(r)

    print()
    print("Telegram")
    r = check_telegram()
    _print_row(r)
    all_results.append(r)

    print()
    print("=" * 60)
    failed = [r for r in all_results if not r.ok]
    if not failed:
        print("  ✅ Tous les services sont opérationnels")
        sys.exit(0)
    else:
        print(f"  ❌ {len(failed)} service(s) KO :")
        for r in failed:
            print(f"     • {r.name} — {r.detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()

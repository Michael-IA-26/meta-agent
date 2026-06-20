"""Diagnostic Supabase — vérifie la connexion et l'accès aux tables principales."""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

TABLES = {
    "leadcommercial": "leads",
    "email_agent": "emails",
    "jmpartners": "dossiers",
}


def _get_client() -> object:
    """Crée et retourne un client Supabase initialisé depuis les variables d'env."""
    from supabase import create_client  # type: ignore[attr-defined]

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not url or not key:
        logger.error("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant dans l'environnement")
        sys.exit(1)

    return create_client(url, key)  # type: ignore[no-any-return]


def check_table(client: object, table: str) -> tuple[bool, str]:
    """Effectue un SELECT limité sur une table et retourne (ok, message).

    Args:
        client: Client Supabase initialisé.
        table: Nom de la table à tester.

    Returns:
        Tuple (succès, message descriptif).
    """
    try:
        resp = client.table(table).select("id").limit(1).execute()  # type: ignore[union-attr,attr-defined]
        count = len(resp.data) if resp.data else 0
        return True, f"table '{table}' accessible ({count} ligne(s) retournée(s))"
    except Exception as exc:
        return False, f"table '{table}' — erreur : {exc}"


def main() -> None:
    """Point d'entrée du script de diagnostic Supabase."""
    print("=== Diagnostic Supabase ===\n")

    client = _get_client()
    all_ok = True

    for app, table in TABLES.items():
        ok, msg = check_table(client, table)
        status = "✅" if ok else "❌"
        print(f"{status} [{app}] {msg}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("✅ Supabase OK — toutes les tables sont accessibles")
        sys.exit(0)
    else:
        print("❌ Supabase KO — au moins une table est inaccessible")
        sys.exit(1)


if __name__ == "__main__":
    main()

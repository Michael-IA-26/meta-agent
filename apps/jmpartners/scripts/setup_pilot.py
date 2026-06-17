"""Pilot setup: create dossier, contact and storage buckets."""

from __future__ import annotations

import argparse
import sys
import uuid

BUCKETS = ["documents", "exports"]


def ensure_buckets(storage) -> None:
    """Create storage buckets if they don't already exist."""
    existing = {b.name for b in storage.list_buckets()}
    for bucket in BUCKETS:
        if bucket not in existing:
            storage.create_bucket(bucket, options={"public": False})


def build_pilot_rows(dossier_name: str, client_email: str) -> tuple[dict, dict]:
    """Return (contact_dict, dossier_dict) with a shared UUID."""
    contact_id = str(uuid.uuid4())
    contact = {"id": contact_id, "email": client_email}
    dossier = {
        "id": str(uuid.uuid4()),
        "name": dossier_name,
        "contact_id": contact_id,
        "statut": "en_cours",
    }
    return contact, dossier


def run(dossier_name: str, client_email: str, confirm: bool) -> None:
    """Execute the pilot setup."""
    if not confirm:
        print("Aborting: --confirm flag not set.", file=sys.stderr)
        sys.exit(1)

    import os

    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    ensure_buckets(client.storage)

    contact, dossier = build_pilot_rows(dossier_name, client_email)

    client.table("contacts").upsert(contact).execute()
    client.table("dossiers").upsert(dossier).execute()

    print(f"dossier_id={dossier['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pilot setup for jmpartners.")
    parser.add_argument("dossier_name", help="Name of the dossier")
    parser.add_argument("client_email", help="Client email address")
    parser.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Required to actually run",
    )
    args = parser.parse_args()
    run(args.dossier_name, args.client_email, args.confirm)


if __name__ == "__main__":
    main()

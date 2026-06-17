"""Local pipeline harness: upload a document and drive it through analysis."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from apps.jmpartners.orchestrator import Orchestrator


def create_supabase_client():
    """Build a Supabase client from environment variables."""
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def build_document_row(url: str, dossier_id: str) -> dict:
    """Return a document row dict ready for insertion."""
    return {"url": url, "dossier_id": dossier_id, "statut": "recu"}


def run(file_path: str, dossier_id: str, confirm: bool) -> None:
    """Run the pipeline for a single document."""
    if not confirm:
        print("Aborting: --confirm flag not set.", file=sys.stderr)
        sys.exit(1)

    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    client = create_supabase_client()

    path = Path(file_path)
    storage_path = path.name
    with path.open("rb") as fh:
        client.storage.from_("documents").upload(storage_path, fh)

    storage_url = f"storage://documents/{storage_path}"
    row = build_document_row(url=storage_url, dossier_id=dossier_id)
    result = client.table("documents").insert(row).execute()
    doc_id = result.data[0]["id"]

    orch = Orchestrator(client, anthropic_key)
    output = orch._process_documents(doc_id)

    print(f"analyse_ia={output.get('analyse_ia')}")
    print(f"ecritures={output.get('ecritures')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run jmpartners pipeline once.")
    parser.add_argument(
        "--file", required=True, dest="file_path", help="Path to document"
    )
    parser.add_argument("--dossier-id", required=True, help="Dossier UUID")
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()
    run(args.file_path, args.dossier_id, args.confirm)


if __name__ == "__main__":
    main()

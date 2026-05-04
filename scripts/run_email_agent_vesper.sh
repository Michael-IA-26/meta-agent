#!/bin/bash
cd "$(dirname "$0")/.."
source .venv/bin/activate
export TOKEN_FILE=token_vesper.json
doppler run -- env RAPPORT_EMAIL=michael@myvesper.fr python3.11 apps/email_agent/sender.py

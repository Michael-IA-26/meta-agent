#!/bin/bash

# Attendre la connexion réseau (max 60 secondes)
for i in $(seq 1 12); do
    if ping -c 1 google.com &>/dev/null; then
        break
    fi
    echo "Attente réseau... ($i/12)"
    sleep 5
done

# Activer le venv et lancer l'agent
cd /Users/michaelsadoun/Documents/meta-agent
source .venv/bin/activate
doppler run -- python3.11 apps/email_agent/sender.py

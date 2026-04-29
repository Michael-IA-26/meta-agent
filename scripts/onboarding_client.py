#!/usr/bin/env python3
"""
Script d'onboarding client Meta-Agent.
Lance : python3.11 scripts/onboarding_client.py
"""

import json
import os
import subprocess
import sys


def print_step(n, title):
    print(f"\n{'=' * 50}")
    print(f"ETAPE {n} — {title}")
    print("=" * 50)


def ask(question, default=None):
    if default:
        response = input(f"{question} [{default}] : ").strip()
        return response if response else default
    return input(f"{question} : ").strip()


def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def main():
    print("\n" + "=" * 50)
    print("META-AGENT — ONBOARDING CLIENT")
    print("=" * 50)
    print("Ce script va configurer l'agent email")
    print("pour un nouveau client en 30 minutes.")

    # Etape 1 — Infos client
    print_step(1, "Informations client")
    client_name = ask("Nom du client (ex: Vesper)")
    client_email = ask("Email de reception du rapport")
    client_gmail = ask("Adresse Gmail a connecter")
    hourly_rate = ask("TJM horaire du client (EUR)", "80")
    daily_email_time = ask("Heure du rapport quotidien", "08:45")
    icp = ask("ICP a utiliser (agence_conseil / cabinet_comptable)", "agence_conseil")

    config = {
        "client_name": client_name,
        "client_email": client_email,
        "client_gmail": client_gmail,
        "hourly_rate": hourly_rate,
        "daily_email_time": daily_email_time,
        "icp": icp,
        "agent_id": f"email_{client_name.lower().replace(' ', '_')}",
    }

    print("\nConfiguration client :")
    for k, v in config.items():
        print(f"  {k}: {v}")

    confirm = ask("\nConfirmer ? (oui/non)", "oui")
    if confirm.lower() != "oui":
        print("Onboarding annule.")
        sys.exit(0)

    # Sauvegarder la config
    config_path = f"configs/client_{config['agent_id']}.json"
    os.makedirs("configs", exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\nConfig sauvegardee : {config_path}")

    # Etape 2 — Secrets Doppler
    print_step(2, "Configuration des secrets Doppler")
    print("On va maintenant configurer les secrets pour ce client.")
    print("Vous aurez besoin des cles API suivantes :\n")

    anthropic_key = ask(
        "ANTHROPIC_API_KEY du client (ou 'shared' pour utiliser la cle commune)"
    )

    secrets = {
        f"CLIENT_{config['agent_id'].upper()}_EMAIL": client_email,
        f"CLIENT_{config['agent_id'].upper()}_GMAIL": client_gmail,
        f"CLIENT_{config['agent_id'].upper()}_HOURLY_RATE": hourly_rate,
        f"CLIENT_{config['agent_id'].upper()}_ICP": icp,
        f"CLIENT_{config['agent_id'].upper()}_SCHEDULE": daily_email_time,
    }

    if anthropic_key != "shared":
        secrets[f"CLIENT_{config['agent_id'].upper()}_ANTHROPIC_KEY"] = anthropic_key

    print("\nConfiguration des secrets...")
    for key, value in secrets.items():
        ok, _, err = run_cmd(f'doppler secrets set {key}="{value}"')
        status = "OK" if ok else f"ERREUR: {err}"
        print(f"  {key}: {status}")

    # Etape 3 — Test Gmail
    print_step(3, "Connexion Gmail")
    print(f"On va maintenant connecter le compte Gmail : {client_gmail}")
    print("\nLe navigateur va s'ouvrir pour autoriser l'acces.")
    print("Le client doit se connecter avec son compte Google.\n")

    input("Appuyer sur ENTREE quand le client est pret...")

    print("\nLancement de la connexion Gmail...")
    ok, out, err = run_cmd(
        'cd apps/email_agent && doppler run -- python3.11 -c "'
        "import sys; sys.path.insert(0, '.'); "
        "from gmail_client import get_gmail_service; "
        "svc = get_gmail_service(); "
        "profile = svc.users().getProfile(userId='me').execute(); "
        "print('Connecte :', profile['emailAddress'])\""
    )

    if ok and client_gmail in out:
        print(f"Gmail connecte : {client_gmail}")
    else:
        print("Connexion Gmail — verifier manuellement")

    # Etape 4 — Test complet
    print_step(4, "Test du rapport")
    print("On va lancer un rapport de test sur 3 emails.")
    input("Appuyer sur ENTREE pour lancer le test...")

    print("\nLancement du rapport de test...")
    ok, out, err = run_cmd(
        'cd apps/email_agent && doppler run -- python3.11 -c "'
        "import sys; sys.path.insert(0, '.'); "
        "from gmail_client import get_emails; "
        "from analyzer import analyze_emails; "
        "emails = get_emails(max_results=3); "
        "analyzed = analyze_emails(emails); "
        "print(f'Test OK : {len(analyzed)} emails analyses')\""
    )

    if ok:
        print("Test rapport : OK")
    else:
        print(f"Erreur test : {err}")

    # Etape 5 — Recapitulatif
    print_step(5, "Recapitulatif")
    print(f"""
Client          : {client_name}
Email rapport   : {client_email}
Gmail connecte  : {client_gmail}
ICP utilise     : {icp}
Heure rapport   : {daily_email_time}
TJM horaire     : {hourly_rate} EUR
Agent ID        : {config["agent_id"]}
Config sauvee   : {config_path}

PROCHAINES ETAPES :
1. Verifier que le rapport arrive bien a {client_email}
2. Demander au client de valider les 5 criteres
3. Documenter les retours dans docs/clients/
    """)

    print("Onboarding termine ! Le client est pret.")


if __name__ == "__main__":
    main()

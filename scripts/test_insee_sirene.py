"""
Test de connexion directe à l'API Sirene INSEE (plan public, clé simple).

Ce script vérifie que l'authentification par clé API fonctionne sans proxy.
Il lit la clé depuis l'environnement (INSEE_SIRENE_API_KEY ou SIRENE_API_TOKEN)
et affiche le status code + nombre de résultats.

Usage (avec Doppler) :
    doppler run --config prd -- uv run python scripts/test_insee_sirene.py

Usage (avec .env local) :
    uv run python scripts/test_insee_sirene.py
"""

import os
import sys

import httpx

BASE_URL = "https://api.insee.fr/api-sirene/3.11"

# Détecte quelle variable Doppler est disponible pour la clé Sirene.
# INSEE_SIRENE_API_KEY est la nouvelle variable (plan public, clé simple).
# SIRENE_API_TOKEN est l'ancienne variable encore lue par sirene_client.py.
_key_from_new = os.getenv("INSEE_SIRENE_API_KEY", "")
_key_from_old = os.getenv("SIRENE_API_TOKEN", "")

if _key_from_new:
    api_key = _key_from_new
    key_source = "INSEE_SIRENE_API_KEY (nouvelle variable Doppler)"
elif _key_from_old:
    api_key = _key_from_old
    key_source = "SIRENE_API_TOKEN (ancienne variable Doppler)"
else:
    print("[ERREUR] Aucune clé Sirene trouvée.")
    print("  Attendu : INSEE_SIRENE_API_KEY ou SIRENE_API_TOKEN dans l'environnement.")
    print("  Lance via : doppler run --config prd -- uv run python scripts/test_insee_sirene.py")
    sys.exit(1)

print(f"[INFO] Clé lue depuis : {key_source}")
print(f"[INFO] Clé (4 premiers chars) : {api_key[:4]}...")
print()

# Requête de test : établissements créés depuis le 2026-01-01 en Seine-Saint-Denis (93)
params = {
    "q": "dateCreationEtablissement:[2026-01-01 TO *] AND codePostalEtablissement:93*",
    "nombre": "5",
    "champs": "siret,denominationUniteLegale,codePostalEtablissement,dateCreationEtablissement",
}

headers = {
    "X-INSEE-Api-Key-Integration": api_key,
    "Accept": "application/json",
}

print(f"[INFO] URL : {BASE_URL}/siret")
print(f"[INFO] Query : {params['q']}")
print(f"[INFO] Header : X-INSEE-Api-Key-Integration: {api_key[:4]}...")
print()

try:
    response = httpx.get(
        f"{BASE_URL}/siret",
        headers=headers,
        params=params,
        timeout=30,
    )
except httpx.RequestError as exc:
    print(f"[ERREUR RESEAU] {exc}")
    sys.exit(2)

print(f"[RESULT] Status HTTP : {response.status_code}")

if response.status_code == 200:
    data = response.json()
    total = data.get("header", {}).get("total", "?")
    etabs = data.get("etablissements", [])
    print(f"[RESULT] Total établissements (API) : {total}")
    print(f"[RESULT] Reçus dans cette page      : {len(etabs)}")
    print()
    print("[OK] Connexion directe à l'API Sirene fonctionnelle — proxy inutile.")
    if etabs:
        print("\n--- Premier résultat ---")
        first = etabs[0]
        ul = first.get("uniteLegale", {})
        adresse = first.get("adresseEtablissement", {})
        print(f"  SIRET      : {first.get('siret')}")
        print(f"  Nom        : {ul.get('denominationUniteLegale')}")
        print(f"  Code postal: {adresse.get('codePostalEtablissement')}")
        print(f"  Création   : {first.get('dateCreationEtablissement')}")
else:
    print(f"[ERREUR] Réponse : {response.text[:500]}")
    print()
    if response.status_code == 401:
        print("[DIAGNOSTIC] 401 = clé invalide ou absente.")
    elif response.status_code == 403:
        print("[DIAGNOSTIC] 403 = clé reconnue mais accès refusé (mauvais plan ou scope).")
    elif response.status_code == 429:
        print("[DIAGNOSTIC] 429 = rate limit atteint (30 req/min sur le plan public).")
    sys.exit(3)

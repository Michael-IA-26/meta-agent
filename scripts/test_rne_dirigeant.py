"""
Test isolé de l'API RNE/INPI pour récupérer les dirigeants d'une entreprise.

Usage :
    INPI_USERNAME=xxx INPI_PASSWORD=yyy python scripts/test_rne_dirigeant.py 552032534 104118757

Aucune donnée n'est stockée : affichage console uniquement.
"""

import os
import sys
import httpx

INPI_BASE = "https://registre-national-entreprises.inpi.fr/api"
LOGIN_URL = f"{INPI_BASE}/sso/login"
COMPANY_URL = f"{INPI_BASE}/companies/{{siren}}"


def get_token(username: str, password: str) -> str:
    """Authentification RNE → retourne le JWT (valable ~24h)."""
    resp = httpx.post(
        LOGIN_URL,
        json={"username": username, "password": password},
        timeout=15,
    )
    if resp.status_code == 401:
        sys.exit("Erreur 401 : identifiants INPI incorrects (vérifiez INPI_USERNAME / INPI_PASSWORD).")
    if not resp.is_success:
        sys.exit(f"Erreur login INPI ({resp.status_code}) : {resp.text[:200]}")

    data = resp.json()
    token = data.get("token") or data.get("access_token") or data.get("jwt")
    if not token:
        sys.exit(f"Token introuvable dans la réponse login. Clés reçues : {list(data.keys())}")
    return token


def fetch_company(siren: str, token: str) -> dict | None:
    """Interroge RNE pour un SIREN. Retourne le JSON brut ou None."""
    url = COMPANY_URL.format(siren=siren)
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code == 404:
        print(f"  → 404 : SIREN {siren} introuvable dans le RNE.")
        return None
    if resp.status_code == 401:
        print(f"  → 401 : token rejeté pour le SIREN {siren}.")
        return None
    if not resp.is_success:
        print(f"  → Erreur {resp.status_code} pour {siren} : {resp.text[:200]}")
        return None
    return resp.json()


ROLE_ENTREPRISE: dict[str, str] = {
    "5":  "Gérant",
    "28": "Associé",
    "30": "Président",
    "51": "Gérant",
    "60": "Commissaire aux comptes",
    "71": "Administrateur",
    "73": "Directeur général",
}


def _normalize_prenoms(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value if v)
    if isinstance(value, str):
        return value.strip()
    return ""


def extract_dirigeants(data: dict) -> list[dict]:
    """
    Explore le JSON RNE pour extraire les représentants légaux.

    Chemin documenté (personne morale) :
      formality.content.personneMorale.composition.pouvoirs[].individu.descriptionPersonne
    On parcourt aussi les chemins alternatifs observés dans la pratique.
    """
    dirigeants = []

    # Chemin principal documenté
    try:
        pouvoirs = (
            data["formality"]["content"]["personneMorale"]
            ["composition"]["pouvoirs"]
        )
        for p in pouvoirs:
            individu = p.get("individu", {})
            desc = individu.get("descriptionPersonne", {})
            nom = (desc.get("nom") or "").strip()
            prenoms = _normalize_prenoms(desc.get("prenoms", ""))
            code = str(p.get("roleEntreprise", ""))
            qualite = ROLE_ENTREPRISE.get(code, f"rôle {code}" if code else "")
            if nom or prenoms:
                dirigeants.append({
                    "nom": nom,
                    "prenoms": prenoms,
                    "qualite": qualite,
                    "source": "personneMorale.pouvoirs",
                })
    except (KeyError, TypeError):
        pass

    # Chemin alternatif : personnePhysique (entreprise individuelle)
    if not dirigeants:
        try:
            pp = data["formality"]["content"]["personnePhysique"]
            desc = pp.get("descriptionPersonne", {})
            nom = (desc.get("nom") or "").strip()
            prenoms = _normalize_prenoms(desc.get("prenoms", ""))
            if nom or prenoms:
                dirigeants.append({
                    "nom": nom,
                    "prenoms": prenoms,
                    "qualite": "Exploitant individuel",
                    "source": "personnePhysique",
                })
        except (KeyError, TypeError):
            pass

    return dirigeants


def extract_raison_sociale(data: dict) -> str:
    """Tente plusieurs chemins pour la raison sociale."""
    try:
        return data["formality"]["content"]["personneMorale"]["identite"]["entreprise"]["denomination"]
    except (KeyError, TypeError):
        pass
    try:
        pp = data["formality"]["content"]["personnePhysique"]["descriptionPersonne"]
        return f"{pp.get('prenoms', '')} {pp.get('nom', '')}".strip()
    except (KeyError, TypeError):
        pass
    return "(raison sociale introuvable)"


def analyse(siren: str, token: str) -> None:
    print(f"\n{'='*60}")
    print(f"SIREN : {siren}")

    data = fetch_company(siren, token)
    if data is None:
        return

    raison_sociale = extract_raison_sociale(data)
    print(f"Raison sociale : {raison_sociale}")

    dirigeants = extract_dirigeants(data)
    if not dirigeants:
        print("Représentant(s) légal/légaux : aucun représentant trouvé")
        # Aide au diagnostic : affiche les clés de premier niveau pour voir la structure réelle
        try:
            content = data["formality"]["content"]
            print(f"  (clés content disponibles : {list(content.keys())})")
        except (KeyError, TypeError):
            print(f"  (clés racine : {list(data.keys())})")
    else:
        print(f"Représentant(s) légal/légaux ({len(dirigeants)}) :")
        for d in dirigeants:
            ligne = f"  - {d['prenoms']} {d['nom']}".strip()
            if d["qualite"]:
                ligne += f" [{d['qualite']}]"
            ligne += f"  (via {d['source']})"
            print(ligne)


def main() -> None:
    username = os.environ.get("INPI_USERNAME")
    password = os.environ.get("INPI_PASSWORD")

    if not username or not password:
        sys.exit(
            "Erreur : INPI_USERNAME et INPI_PASSWORD doivent être définis "
            "comme variables d'environnement."
        )

    sirens = sys.argv[1:]
    if not sirens:
        sys.exit("Usage : python scripts/test_rne_dirigeant.py <SIREN1> [SIREN2 ...]")

    print("Authentification INPI...")
    token = get_token(username, password)
    print("Token obtenu.")

    for siren in sirens:
        analyse(siren.strip(), token)

    print(f"\n{'='*60}")
    print("Fin du test. Aucune donnée stockée.")


if __name__ == "__main__":
    main()

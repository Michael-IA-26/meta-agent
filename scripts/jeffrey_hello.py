"""Script d'onboarding Jeffrey - lit un fichier JSON et compte ses cles."""

import json
import sys


def read_json_file(filepath: str) -> dict:
    """Lit un fichier JSON et retourne son contenu sous forme de dictionnaire."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def count_top_level_keys(data: dict) -> int:
    """Retourne le nombre de cles au premier niveau du dictionnaire."""
    return len(data)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/jeffrey_hello.py <chemin_vers_fichier.json>")
        sys.exit(1)

    filepath = sys.argv[1]

    try:
        content = read_json_file(filepath)
    except FileNotFoundError:
        print(f"Erreur : le fichier '{filepath}' est introuvable.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Erreur : le fichier '{filepath}' n'est pas un JSON valide.")
        print(f"Detail : {e}")
        sys.exit(1)

    print(json.dumps(content, indent=2, ensure_ascii=False))
    nb_keys = count_top_level_keys(content)
    print(f"\nNombre de cles top-level : {nb_keys}")

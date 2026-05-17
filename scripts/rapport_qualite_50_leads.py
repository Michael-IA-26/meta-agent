"""
Rapport qualité — 50 leads Sirene IDF réels — JM Partners
==========================================================
Fetch 50 entreprises IDF créées récemment via l'API Pappers,
applique les critères ICP JM Partners, écrit le rapport markdown.

Usage :
    python scripts/rapport_qualite_50_leads.py

Prérequis :
    PAPPERS_API_KEY dans .env ou variable d'environnement.
    pip install httpx python-dotenv
"""

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

API_TOKEN = os.environ.get("PAPPERS_API_KEY")
if not API_TOKEN:
    sys.exit("ERREUR : PAPPERS_API_KEY manquante. Ajoutez-la dans .env.")

BASE_URL = "https://api.pappers.fr/v2"
TARGET = 50
OUTPUT = Path("docs/leadcommercial/rapport-qualite-50-leads.md")

# ── Critères ICP JM Partners ──────────────────────────────────────────────────

DEPT_IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}

# Tranches effectif INSEE incluses (0-49 salariés)
TRANCHES_ICP = {"00", "01", "02", "03", "11", "12"}

# Secteurs exclus (NAF)
SECTEURS_EXCLUS = {
    "94.99Z", "94.11Z", "94.12Z", "94.20Z", "94.91Z", "94.92Z", "94.99Z",  # associations
    "47.11A", "47.11B",  # grandes surfaces
    "85.10Z", "85.20Z", "85.31Z", "85.32Z", "85.41Z", "85.42Z",  # enseignement public
}

# ── Helpers API ───────────────────────────────────────────────────────────────

def get_dept(company: dict) -> str:
    cp = company.get("siege", {}).get("code_postal", "") or ""
    return cp[:2] if cp else ""


def search_recent_idf(date_min: str, par_page: int = 100, page: int = 1) -> list[dict]:
    """Recherche via /v2/recherche avec filtres IDF + date de création."""
    params = {
        "api_token": API_TOKEN,
        "date_creation_min": date_min,
        "entreprise_cessee": "false",
        "par_page": par_page,
        "page": page,
    }
    try:
        r = httpx.get(f"{BASE_URL}/recherche", params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("resultats", [])
    except httpx.HTTPStatusError as e:
        print(f"  [HTTP {e.response.status_code}] recherche page {page}: {e}")
        return []
    except Exception as e:
        print(f"  [ERREUR] recherche page {page}: {e}")
        return []


def get_full_company(siren: str) -> dict | None:
    """Lookup complet /v2/entreprise pour un SIREN (procédure collective, tranche)."""
    params = {"api_token": API_TOKEN, "siren": siren}
    try:
        r = httpx.get(f"{BASE_URL}/entreprise", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        print(f"  [HTTP {e.response.status_code}] lookup SIREN {siren}")
        return None
    except Exception as e:
        print(f"  [ERREUR] lookup SIREN {siren}: {e}")
        return None


# ── Filtres ICP ───────────────────────────────────────────────────────────────

def apply_icp(company: dict) -> tuple[bool, str]:
    """
    Applique les critères ICP JM Partners.
    Retourne (qualifie, motif).
    """
    # 1. Cessation
    if company.get("entreprise_cessee"):
        return False, "Entreprise cessée"

    # 2. Localisation IDF
    dept = get_dept(company)
    if dept not in DEPT_IDF:
        ville = company.get("siege", {}).get("ville", "?")
        return False, f"Hors IDF — dept {dept} ({ville})"

    # 3. Procédure collective
    if company.get("procedure_collective_en_cours"):
        return False, "Procédure collective en cours"

    # 4. Effectif > 49 salariés
    # Priorité à effectif_min (numérique fiable) si disponible
    effectif_min = company.get("effectif_min")
    if effectif_min is not None:
        try:
            if int(effectif_min) >= 50:
                return False, f"Effectif hors ICP — {company.get('effectif', effectif_min)} salariés"
        except (ValueError, TypeError):
            pass
    else:
        # Fallback : tranche_effectif — normaliser avec zfill pour Pappers
        # qui retourne parfois "0" au lieu de "00", "1" au lieu de "01", etc.
        tranche_raw = company.get("tranche_effectif")
        if tranche_raw is not None and str(tranche_raw).strip():
            try:
                tranche = str(int(str(tranche_raw))).zfill(2)
            except (ValueError, TypeError):
                tranche = str(tranche_raw).strip()
            if tranche and tranche not in TRANCHES_ICP:
                effectif_label = company.get("effectif", f"tranche {tranche}")
                return False, f"Effectif hors ICP — {effectif_label} (tranche {tranche})"

    # 5. Secteur exclu
    naf = (company.get("code_naf") or "").strip()
    if naf in SECTEURS_EXCLUS:
        return False, f"Secteur exclu — NAF {naf}"

    return True, "Qualifié ICP"


# ── Fetch 50 leads ────────────────────────────────────────────────────────────

def fetch_leads(target: int = 50) -> list[dict]:
    date_min = (date.today() - timedelta(days=180)).isoformat()
    print(f"Recherche entreprises IDF créées depuis {date_min}…")

    raw: list[dict] = []
    page = 1
    seen_sirens: set[str] = set()

    while len(raw) < target * 2:  # fetch plus large pour avoir du choix
        batch = search_recent_idf(date_min, par_page=100, page=page)
        if not batch:
            print(f"  Aucun résultat à la page {page}, arrêt.")
            break

        for c in batch:
            siren = c.get("siren", "")
            dept = get_dept(c)
            if siren and siren not in seen_sirens and dept in DEPT_IDF:
                seen_sirens.add(siren)
                raw.append(c)

        print(f"  Page {page} : {len(batch)} résultats, {len(raw)} IDF cumulés")
        page += 1
        time.sleep(0.5)

        if len(raw) >= target * 2 or len(batch) < 100:
            break

    # Limiter à target et enrichir avec lookup individuel
    candidates = raw[:target]
    print(f"\nEnrichissement individuel pour {len(candidates)} entreprises…")
    enriched = []
    for i, c in enumerate(candidates, 1):
        siren = c.get("siren", "")
        full = get_full_company(siren)
        if full:
            enriched.append(full)
        else:
            enriched.append(c)  # fallback données search
        if i % 10 == 0:
            print(f"  {i}/{len(candidates)} lookups effectués")
        time.sleep(0.3)

    return enriched


# ── Rapport markdown ──────────────────────────────────────────────────────────

def build_report(leads: list[dict]) -> str:
    today = date.today().isoformat()
    date_min = (date.today() - timedelta(days=180)).isoformat()

    qualified = []
    excluded = []

    for c in leads:
        passes, reason = apply_icp(c)
        entry = {
            "siren": c.get("siren", "—"),
            "nom": c.get("denomination", "—"),
            "naf": c.get("code_naf", "—"),
            "libelle_naf": c.get("libelle_code_naf", "—"),
            "forme": c.get("forme_juridique", "—"),
            "dept": get_dept(c),
            "ville": c.get("siege", {}).get("ville", "—"),
            "creation": c.get("date_creation", "—"),
            "effectif": c.get("effectif", "ND"),
            "tranche": c.get("tranche_effectif", "ND"),
            "dirigeant": (c.get("representants") or [{}])[0].get("nom_complet", "—"),
            "procedure": "Oui" if c.get("procedure_collective_en_cours") else "Non",
            "reason": reason,
        }
        if passes:
            qualified.append(entry)
        else:
            excluded.append(entry)

    nb_total = len(leads)
    nb_qualifies = len(qualified)
    nb_exclus = len(excluded)
    taux = round(nb_qualifies / nb_total * 100, 1) if nb_total else 0

    # Répartition des motifs d'exclusion
    motifs: dict[str, int] = {}
    for e in excluded:
        key = e["reason"].split(" — ")[0]
        motifs[key] = motifs.get(key, 0) + 1
    motifs_sorted = sorted(motifs.items(), key=lambda x: -x[1])

    # Répartition IDF qualifiés par dept
    depts_qualifies: dict[str, int] = {}
    for q in qualified:
        d = q["dept"]
        depts_qualifies[d] = depts_qualifies.get(d, 0) + 1

    lines = []

    lines += [
        f"# Rapport qualité — 50 leads Sirene IDF réels",
        f"",
        f"**Date** : {today}  ",
        f"**Source** : API Pappers v2  ",
        f"**Périmètre** : entreprises IDF créées entre {date_min} et {today}  ",
        f"**Critères ICP** : TPE/PME IDF (0-49 sal.), non cessée, hors procédure collective, hors secteurs exclus  ",
        f"",
        f"---",
        f"",
        f"## 1. Résumé exécutif",
        f"",
        f"| Indicateur | Valeur |",
        f"|---|---|",
        f"| Leads Sirene récupérés | {nb_total} |",
        f"| Leads qualifiés ICP | **{nb_qualifies}** |",
        f"| Leads exclus | {nb_exclus} |",
        f"| Taux de passage ICP | **{taux} %** |",
        f"",
    ]

    if motifs_sorted:
        lines += [
            f"### Motifs d'exclusion",
            f"",
            f"| Motif | Nb |",
            f"|---|---|",
        ]
        for motif, nb in motifs_sorted:
            lines.append(f"| {motif} | {nb} |")
        lines.append("")

    if depts_qualifies:
        lines += [
            f"### Répartition des leads qualifiés par département",
            f"",
            f"| Département | Nb qualifiés |",
            f"|---|---|",
        ]
        for d in sorted(depts_qualifies):
            lines.append(f"| {d} | {depts_qualifies[d]} |")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 2. Leads qualifiés ICP ({nb_qualifies})",
        f"",
    ]

    if qualified:
        lines += [
            "| # | SIREN | Dénomination | Dept | Ville | NAF | Forme | Création | Effectif | Dirigeant |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, q in enumerate(qualified, 1):
            lines.append(
                f"| {i} | {q['siren']} | {q['nom']} | {q['dept']} | {q['ville']} "
                f"| {q['naf']} | {q['forme'][:30]} | {q['creation']} | {q['effectif']} | {q['dirigeant']} |"
            )
        lines.append("")
    else:
        lines += ["*Aucun lead qualifié.*", ""]

    lines += [
        f"---",
        f"",
        f"## 3. Leads exclus ({nb_exclus})",
        f"",
    ]

    if excluded:
        lines += [
            "| # | SIREN | Dénomination | Dept | NAF | Motif d'exclusion |",
            "|---|---|---|---|---|---|",
        ]
        for i, e in enumerate(excluded, 1):
            lines.append(
                f"| {i} | {e['siren']} | {e['nom']} | {e['dept']} "
                f"| {e['naf']} | {e['reason']} |"
            )
        lines.append("")
    else:
        lines += ["*Aucun lead exclu.*", ""]

    lines += [
        f"---",
        f"",
        f"## 4. Méthodologie",
        f"",
        f"**Collecte** : endpoint `/v2/recherche` Pappers avec filtre `date_creation_min={date_min}` et `entreprise_cessee=false`.  ",
        f"Enrichissement individuel via `/v2/entreprise` pour récupérer `procedure_collective_en_cours` et `tranche_effectif`.",
        f"",
        f"**Critères ICP appliqués (dans l'ordre) :**",
        f"",
        f"1. Entreprise non cessée (`entreprise_cessee = false`)",
        f"2. Siège social en Île-de-France (dept 75, 77, 78, 91, 92, 93, 94, 95)",
        f"3. Aucune procédure collective en cours",
        f"4. Effectif ≤ 49 salariés (tranches INSEE 00 à 12)",
        f"5. Secteur hors exclusions (associations, grandes surfaces, enseignement public)",
        f"",
        f"**Limites de cette analyse :**",
        f"- Les entreprises sans `tranche_effectif` renseignée sont considérées éligibles (effectif inconnu).",
        f"- Le signal « changement de dirigeant » (BODACC) n'est pas inclus dans ce rapport (prévu S3).",
        f"- Déduplication simple par SIREN — aucun rapprochement CRM effectué.",
        f"",
        f"---",
        f"",
        f"*Rapport généré automatiquement le {today} — JM Partners / Signal Agent v0.1*",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    leads = fetch_leads(TARGET)

    if not leads:
        sys.exit("Aucun lead récupéré — vérifiez la clé API et la connexion.")

    print(f"\n{len(leads)} leads récupérés, application des filtres ICP…")
    report = build_report(leads)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(report, encoding="utf-8")
    print(f"\nRapport écrit : {OUTPUT}")

    # Résumé console
    qualified_count = sum(1 for c in leads if apply_icp(c)[0])
    print(f"Qualifiés ICP : {qualified_count}/{len(leads)} ({round(qualified_count/len(leads)*100,1)} %)")

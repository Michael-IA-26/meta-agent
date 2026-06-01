"""Filtre ICP complet pour la validation dry_run JM Partners.

Pipeline :
  1. Exclusions absolues (géo, fenêtre, effectif, secteur)
  2. Scoring ICP 0-100 sur 5 critères
  3. Classification : CHAUD / TIÈDE / FROID / EXCLU

Ce module utilise les noms de formes juridiques en clair ("EURL", "SAS"…)
plutôt que les codes INSEE — adapté aux données simulées du dry_run.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# ── Configuration ICP JM Partners ────────────────────────────────────────────

CODES_POSTAUX_ICP: frozenset[str] = frozenset({
    "75010", "75011", "75012", "75018", "75019", "75020",
    "93000", "93170", "93230", "93260", "93300", "93400", "93500",
})

FENETRE_CREATION_JOURS = 30

FORMES_JURIDIQUES_ICP: frozenset[str] = frozenset({
    "EURL", "SARL", "SAS", "SASU", "EI", "AE", "MICRO-ENTREPRENEUR",
})

SEUIL_CHAUD = 75
SEUIL_TIEDE = 50
SEUIL_FROID = 30

# Codes NAF et noms de marques déclenchant un avertissement franchise
NAF_FRANCHISE_ASSURANCE: frozenset[str] = frozenset({"6621Z", "6622Z"})
MARQUES_FRANCHISE: frozenset[str] = frozenset({
    "AXA", "ALLIANZ", "MAIF", "GROUPAMA", "APRIL", "GENERALI",
    "MACIF", "MATMUT", "COVEA", "MMA", "GMF",
})


# ── Résolution des dates relatives ────────────────────────────────────────────

def resolve_date(date_str: str, today: date | None = None) -> date:
    """Convertit 'J-N' en date réelle ou parse une ISO date."""
    if today is None:
        today = date.today()
    if date_str.startswith("J-"):
        days = int(date_str[2:])
        return today - timedelta(days=days)
    return date.fromisoformat(date_str)


# ── Scoring secteur ───────────────────────────────────────────────────────────

def _score_secteur(code_naf: str) -> tuple[int, str]:
    p2 = code_naf[:2]
    p4 = code_naf[:4].replace(".", "")

    if p2 in {"41", "42", "43"}:
        return 10, "BTP (prioritaire)"
    if p2 == "47":
        return 10, "Commerce de détail (prioritaire)"
    if p2 == "56":
        return 10, "Restauration/CHR (prioritaire)"
    if p4 in {"1071"}:
        return 10, "Boulangerie (prioritaire)"
    if p2 in {"70", "71", "72", "73", "74"}:
        return 7, "Services aux entreprises"
    if p2 in {"62", "63"}:
        return 3, "Informatique / Tech (moins prioritaire)"
    if p2 in {"65", "66", "67"}:
        return 5, "Assurance / profession réglementée"
    if p2 in {"64"}:
        return 0, "Holding / Finance (hors cible)"
    return 5, "Secteur neutre"


# ── Détection franchise ───────────────────────────────────────────────────────

def _detect_franchise(denomination: str, code_naf: str) -> str | None:
    """Retourne un message d'avertissement si le lead est probablement une franchise.

    Critères : NAF assurance (6621Z / 6622Z) ET nom de grande marque détecté.
    N'exclut pas le lead — déclenche seulement une vérification manuelle.
    """
    if code_naf not in NAF_FRANCHISE_ASSURANCE:
        return None
    denom_upper = denomination.upper()
    detected = [m for m in MARQUES_FRANCHISE if m in denom_upper]
    if detected:
        return (
            f"Franchise probable ({', '.join(detected)}) — "
            "vérification manuelle recommandée : le mandant impose souvent un EC dédié"
        )
    return None


# ── Pipeline principal ────────────────────────────────────────────────────────

def evaluate_lead(lead: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Évalue un lead : exclusions puis scoring ICP.

    Args:
        lead:  Dictionnaire lead (format dry_run avec date_creation en 'J-N' ou ISO).
        today: Date de référence (défaut : date.today()).

    Returns:
        Dictionnaire avec statut, score, raison_exclusion, scoring_details,
        id, denomination, code_postal, date_creation (résolue).
    """
    if today is None:
        today = date.today()

    lead_id = lead.get("id", "?")
    denomination = lead.get("denomination", "?")
    code_naf = lead.get("code_naf", "")
    forme_juridique = (lead.get("forme_juridique") or "").upper()
    effectif_min = lead.get("effectif_min", 0)
    effectif_max = lead.get("effectif_max", 0)
    cp = (lead.get("siege") or {}).get("code_postal", "")
    date_creation_str = lead.get("date_creation", "")
    representant = lead.get("representant", {})

    date_creation = resolve_date(date_creation_str, today) if date_creation_str else None

    # ── Exclusions absolues ──────────────────────────────────────────────────

    # 1. Effectif > 50 (DAF interne probable)
    if effectif_min >= 50:
        return _exclu(lead_id, denomination, cp, date_creation,
                      f"effectif minimum déclaré ({effectif_min} sal.) > 50 — hors cible TPE JM Partners",
                      representant)

    # 2. Agriculture NAF 01xx
    if code_naf.startswith("01"):
        return _exclu(lead_id, denomination, cp, date_creation,
                      f"agriculture (NAF {code_naf} — code 01xx) — secteur exclu ICP",
                      representant)

    # 3. Hors zone géographique
    if cp not in CODES_POSTAUX_ICP:
        return _exclu(lead_id, denomination, cp, date_creation,
                      f"hors zone géographique (code postal {cp} non couvert par l'ICP JM Partners)",
                      representant)

    # 4. Hors fenêtre de création
    if date_creation is not None:
        jours_depuis_creation = (today - date_creation).days
        if jours_depuis_creation > FENETRE_CREATION_JOURS:
            return _exclu(lead_id, denomination, cp, date_creation,
                          f"hors fenêtre de détection ({jours_depuis_creation}j depuis la création > {FENETRE_CREATION_JOURS}j)",
                          representant)

    # ── Scoring ICP ──────────────────────────────────────────────────────────

    score = 0
    details: list[str] = []

    # Critère 1 — Localisation ICP : 20 pts
    score += 20
    details.append(f"+20 | Localisation ICP (code postal {cp} en zone cible)")

    # Critère 2 — Taille entreprise : 0–20 pts
    eff = effectif_max if effectif_max > 0 else effectif_min
    if eff == 0:
        pts_eff = 10
        label_eff = "0 sal. (non déclaré)"
    elif eff <= 9:
        pts_eff = 20
        label_eff = f"TPE {effectif_min}–{effectif_max} sal."
    else:
        pts_eff = 15
        label_eff = f"PME {effectif_min}–{effectif_max} sal."
    score += pts_eff
    details.append(f"+{pts_eff} | Taille entreprise ({label_eff})")

    # Critère 3 — Forme juridique : 5 ou 15 pts
    if forme_juridique in FORMES_JURIDIQUES_ICP:
        pts_fj = 15
    else:
        pts_fj = 5
    score += pts_fj
    details.append(f"+{pts_fj} | Forme juridique ({forme_juridique})")

    # Critère 4 — Signal création récente ≤ 30j : 20 pts
    if date_creation is not None:
        jours = (today - date_creation).days
        score += 20
        details.append(f"+20 | Signal création récente ({jours}j)")

    # Critère 5 — Secteur d'activité : 0–10 pts
    pts_sect, label_sect = _score_secteur(code_naf)
    score += pts_sect
    details.append(f"+{pts_sect} | Secteur {label_sect} (NAF {code_naf})")

    # ── Classification ───────────────────────────────────────────────────────

    if score >= SEUIL_CHAUD:
        statut = "CHAUD"
    elif score >= SEUIL_TIEDE:
        statut = "TIÈDE"
    elif score >= SEUIL_FROID:
        statut = "FROID"
    else:
        statut = "FROID"

    # ── Avertissements (flags non-bloquants) ─────────────────────────────────

    warnings: list[str] = []
    franchise_warning = _detect_franchise(denomination, code_naf)
    if franchise_warning:
        warnings.append(franchise_warning)

    return {
        "id": lead_id,
        "denomination": denomination,
        "code_postal": cp,
        "date_creation": date_creation.isoformat() if date_creation else None,
        "score": score,
        "statut": statut,
        "raison_exclusion": None,
        "scoring_details": details,
        "warnings": warnings,
        "franchise_probable": franchise_warning is not None,
        "representant": representant,
        "code_naf": code_naf,
        "libelle_naf": lead.get("libelle_naf", ""),
        "forme_juridique": lead.get("forme_juridique", ""),
        "secteur_label": lead.get("secteur_label", ""),
    }


def _exclu(
    lead_id: str,
    denomination: str,
    cp: str,
    date_creation: date | None,
    raison: str,
    representant: dict,
) -> dict[str, Any]:
    return {
        "id": lead_id,
        "denomination": denomination,
        "code_postal": cp,
        "date_creation": date_creation.isoformat() if date_creation else None,
        "score": 0,
        "statut": "EXCLU",
        "raison_exclusion": raison,
        "scoring_details": [f"EXCLU : {raison}"],
        "warnings": [],
        "franchise_probable": False,
        "representant": representant,
    }


def evaluate_batch(
    leads: list[dict[str, Any]],
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Évalue une liste de leads."""
    return [evaluate_lead(lead, today) for lead in leads]


def check_assertions(
    results: list[dict[str, Any]],
    assertions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Vérifie les assertions sur les résultats et retourne les failures."""
    failures: list[dict[str, Any]] = []

    for result in results:
        lead_id = result["id"]
        if lead_id not in assertions:
            continue

        assertion = assertions[lead_id]
        statut = result["statut"]
        raison = result.get("raison_exclusion") or ""

        if "statut_in" in assertion:
            if statut not in assertion["statut_in"]:
                failures.append({
                    "id": lead_id,
                    "message": f"[ASSERTION FAILED] {lead_id} : attendu statut dans {assertion['statut_in']}, obtenu '{statut}'",
                })

        if "statut" in assertion:
            if statut != assertion["statut"]:
                failures.append({
                    "id": lead_id,
                    "message": f"[ASSERTION FAILED] {lead_id} : attendu statut '{assertion['statut']}', obtenu '{statut}'",
                })

        if "raison_contains" in assertion:
            keyword = assertion["raison_contains"]
            if keyword.lower() not in raison.lower():
                failures.append({
                    "id": lead_id,
                    "message": f"[ASSERTION FAILED] {lead_id} : raison '{raison}' ne contient pas '{keyword}'",
                })

    return failures

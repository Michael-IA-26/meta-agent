"""Enrichissement contact dirigeant — Options A, B, C, D.

Volume de référence pour les estimations de coût :
  - 13 codes postaux ICP JM Partners
  - ~15 créations/jour dans la zone
  - 30 jours/mois
  - → ~450 créations/mois brutes
  - → ~180 leads CHAUD/TIÈDE/mois (taux de qualification ~40 %)

Toutes les fonctions sont en mode dry_run (mock) sauf mention contraire.
"""

from __future__ import annotations

from typing import Any

VOLUME_MENSUEL_BRUT = 450
VOLUME_MENSUEL_QUALIFIE = 180  # ~40 % qualification


# ── Option A — Recherche web (gratuit) ───────────────────────────────────────

def enrich_web_search(lead: dict[str, Any]) -> dict[str, Any]:
    """Mock : recherche web ciblée sur le dirigeant.

    En production :
    - Requête : '"[Prénom NOM]" "[Nom entreprise]" "[code_postal]" email OR contact'
    - Scraping du site web de l'entreprise (page contact)
    - Parser Societe.com, PagesJaunes, Infogreffe
    """
    prenom = lead.get("representant", {}).get("prenom", "")
    nom = lead.get("representant", {}).get("nom", "")
    denom = lead.get("denomination", "")
    cp = (lead.get("siege") or {}).get("code_postal", "")

    query = f'"{prenom} {nom}" "{denom}" "{cp}" email OR contact'

    return {
        "methode": "web_search",
        "option": "A",
        "query_simulee": query,
        "email": None,
        "telephone": None,
        "source": "dry_run — aucun appel réel",
        "fiabilite_pct": 15,
        "cout_unitaire_eur": 0.0,
        "volume_mensuel": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": 0.0,
        "note": (
            "Option A — Recherche web gratuite. En production : scraping Societe.com / "
            "PagesJaunes / site web entreprise. Fiabilité faible (15 %) car les emails "
            "publics sont rares pour les TPE. Applicable à ~30 % des leads (ceux qui "
            "ont un site web actif)."
        ),
    }


# ── Option B — APIs open data gratuites ──────────────────────────────────────

def enrich_pappers_mock(lead: dict[str, Any]) -> dict[str, Any]:
    """Mock : appel API Pappers /entreprises/{siren}.

    En production :
    - GET https://api.pappers.fr/v2/entreprise?siren={siren}&api_token={key}
    - Champs utiles : representants[0].nom, prenom, qualite, date_prise_de_poste
    - Pappers ne fournit PAS l'email ni le téléphone du dirigeant.
    - Utile pour : vérification d'identité, BODACC, statut RCS.
    """
    siren = lead.get("siren", "SIMUL")

    return {
        "methode": "pappers_api",
        "option": "B1",
        "siren": siren,
        "endpoint": f"https://api.pappers.fr/v2/entreprise?siren={siren}",
        "email": None,
        "telephone": None,
        "source": "Pappers API v2 (mock)",
        "fiabilite_pct": 0,
        "cout_unitaire_eur": 0.0,
        "volume_mensuel": VOLUME_MENSUEL_BRUT,
        "cout_mensuel_eur": 0.0,
        "limite_mensuelle": 500,
        "note": (
            "Option B1 — Pappers API (500 appels/mois gratuits). "
            "Ne fournit PAS email/tél du dirigeant. "
            "Utile pour enrichissement statut RCS, BODACC, capital social. "
            "À utiliser en pré-qualification, pas pour la recherche de contact."
        ),
    }


def enrich_insee_rne_mock(lead: dict[str, Any]) -> dict[str, Any]:
    """Mock : API RNE INPI (données représentants légaux).

    En production :
    - GET https://api.inpi.fr/entreprises/{siren}/dirigeants
    - Fournit : nom, prénom, qualité, date de prise de fonction
    - Ne fournit PAS email/tél (données publiques registre uniquement)
    """
    siren = lead.get("siren", "SIMUL")

    return {
        "methode": "inpi_rne",
        "option": "B2",
        "siren": siren,
        "endpoint": f"https://api.inpi.fr/entreprises/{siren}/dirigeants",
        "email": None,
        "telephone": None,
        "source": "INPI RNE API (mock)",
        "fiabilite_pct": 0,
        "cout_unitaire_eur": 0.0,
        "volume_mensuel": VOLUME_MENSUEL_BRUT,
        "cout_mensuel_eur": 0.0,
        "note": (
            "Option B2 — INPI RNE API (illimité, gratuit). "
            "Données représentants légaux officielles. "
            "Pas d'email/tél — confirm identité dirigeant uniquement."
        ),
    }


# ── Option C — APIs payantes (POC documenté, aucun appel) ────────────────────

APIS_PAYANTES: dict[str, dict[str, Any]] = {
    "dropcontact": {
        "nom": "Dropcontact",
        "url": "https://dropcontact.com",
        "description": "Enrichissement email B2B par domaine + prénom/nom dirigeant",
        "cout_unitaire_eur": 0.10,
        "fiabilite_pct": 70,
        "volume_mensuel_qualifie": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": round(0.10 * VOLUME_MENSUEL_QUALIFIE, 2),
        "champs_fournis": ["email_pro", "email_verifie", "nom_complet", "entreprise"],
        "avantages": "RGPD natif, enrichissement uniquement sur emails professionnels vérifiés",
        "inconvenients": "Ne couvre pas les dirigeants sans domaine email dédié (~30 % des TPE)",
        "usage": "POST /enrich avec {first_name, last_name, company, siren}",
    },
    "kaspr": {
        "nom": "Kaspr",
        "url": "https://kaspr.io",
        "description": "Email pro + mobile dirigeant via LinkedIn",
        "cout_unitaire_eur": 0.30,
        "fiabilite_pct": 65,
        "volume_mensuel_qualifie": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": round(0.30 * VOLUME_MENSUEL_QUALIFIE, 2),
        "champs_fournis": ["email_pro", "telephone_mobile", "linkedin_url"],
        "avantages": "Numéro mobile direct — taux de contact très élevé",
        "inconvenients": "Coût élevé, requiert profil LinkedIn du dirigeant",
        "usage": "API REST ou extension Chrome (plan Team)",
    },
    "hunter_io": {
        "nom": "Hunter.io",
        "url": "https://hunter.io",
        "description": "Email pro par domaine entreprise",
        "cout_unitaire_eur": 0.05,
        "fiabilite_pct": 55,
        "volume_mensuel_qualifie": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": round(0.05 * VOLUME_MENSUEL_QUALIFIE, 2),
        "champs_fournis": ["email_pro", "score_confiance"],
        "avantages": "Peu cher, API simple, bonne couverture PME avec site web",
        "inconvenients": "Pas de mobile, faible couverture TPE sans site web (~50 % des cas)",
        "usage": "GET /v2/email-finder?domain={domaine}&first_name={prenom}&last_name={nom}",
    },
    "clearbit": {
        "nom": "Clearbit (Hubspot)",
        "url": "https://clearbit.com",
        "description": "Enrichissement complet entreprise + dirigeant",
        "cout_unitaire_eur": 0.20,
        "fiabilite_pct": 60,
        "volume_mensuel_qualifie": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": round(0.20 * VOLUME_MENSUEL_QUALIFIE, 2),
        "champs_fournis": ["email_pro", "titre", "linkedin_url", "taille_equipe", "secteur"],
        "avantages": "Enrichissement complet, intégration native HubSpot/Salesforce",
        "inconvenients": "Couverture FR TPE limitée (outil orienté marché anglo-saxon)",
        "usage": "GET /v2/people/find?email={email} ou /v2/company/find?domain={domaine}",
    },
}


def get_apis_payantes_summary() -> list[dict[str, Any]]:
    """Retourne un résumé comparatif des APIs payantes."""
    return [
        {
            "option": "C",
            "nom": v["nom"],
            "fiabilite_pct": v["fiabilite_pct"],
            "cout_unitaire_eur": v["cout_unitaire_eur"],
            "cout_mensuel_eur": v["cout_mensuel_eur"],
            "avantages": v["avantages"],
            "inconvenients": v["inconvenients"],
        }
        for v in APIS_PAYANTES.values()
    ]


# ── Option D — Stub LinkedIn (sprint futur) ───────────────────────────────────

def enrich_linkedin_stub(lead: dict[str, Any]) -> dict[str, Any]:
    """Stub LinkedIn — NE PAS implémenter (Terms of Service LinkedIn).

    Documente la logique pour un sprint futur avec Sales Navigator API.
    """
    rep = lead.get("representant", {})
    prenom = rep.get("prenom", "")
    nom = rep.get("nom", "")
    denom = lead.get("denomination", "")

    query = f"{prenom} {nom} gérant {denom}"
    search_url_template = (
        f"https://www.linkedin.com/search/results/people/"
        f"?keywords={query.replace(' ', '%20')}"
    )

    return {
        "methode": "linkedin_stub",
        "option": "D",
        "query_template": query,
        "search_url_template": search_url_template,
        "email": None,
        "telephone": None,
        "fiabilite_pct": 80,
        "cout_unitaire_eur": 0.30,
        "volume_mensuel": VOLUME_MENSUEL_QUALIFIE,
        "cout_mensuel_eur": round(0.30 * VOLUME_MENSUEL_QUALIFIE, 2),
        "statut": "STUB — ne pas appeler en production sans accord Sales Navigator",
        "note": (
            "Option D — LinkedIn Sales Navigator API. "
            "Haute fiabilité (80 %) pour les dirigeants actifs sur LinkedIn. "
            "Requiert accord commercial LinkedIn (~1 000 €/mois pour l'accès API). "
            "À planifier sprint S4+. "
            "Requête suggérée : {query}".format(query=query)
        ),
    }


# ── Enrichissement global d'un lead (toutes options A+B) ─────────────────────

def enrich_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Applique toutes les méthodes d'enrichissement disponibles (dry_run).

    Retourne un dict avec les résultats de chaque option.
    """
    return {
        "id": lead.get("id"),
        "denomination": lead.get("denomination"),
        "options": {
            "A_web_search": enrich_web_search(lead),
            "B1_pappers": enrich_pappers_mock(lead),
            "B2_inpi_rne": enrich_insee_rne_mock(lead),
            "D_linkedin_stub": enrich_linkedin_stub(lead),
        },
        "meilleure_option": "C_dropcontact",
        "recommandation": (
            "En production, privilégier Dropcontact (Option C1) pour les leads CHAUD "
            "à 0,10 €/lead — ROI positif si 1 RDV converti en client sur 10 emails."
        ),
    }

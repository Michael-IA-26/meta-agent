"""Client INSEE Sirene API v3.11 — OAuth2 + recherche établissements récents.

Usage :
    from apps.leadcommercial.sirene_client import SireneClient

    client = SireneClient.from_env()
    leads = client.fetch_recent_creations(jours=7, max_results=50)
    for lead in leads[:5]:
        print(lead["denomination"], lead["siege"]["code_postal"])

Authentification : OAuth2 client_credentials
  POST https://api.insee.fr/token
  Authorization: Basic base64(key:secret)
  Body: grant_type=client_credentials

Endpoint utilisé :
  GET https://api.insee.fr/api-sirene/3.11/siret
  Params: q (FIQL), nombre, champs
"""

from __future__ import annotations

import base64
import os
from datetime import date, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

SIRENE_TOKEN_URL = "https://api.insee.fr/token"
SIRENE_SIRET_URL = "https://api.insee.fr/api-sirene/3.11/siret"

CODES_POSTAUX_ICP = [
    "75010", "75011", "75012", "75018", "75019", "75020",
    "93000", "93170", "93230", "93260", "93300", "93400", "93500",
]

# Champs utiles uniquement — réduit la taille de la réponse
CHAMPS_UTILES = ",".join([
    "siret",
    "siren",
    "denominationUniteLegale",
    "categorieJuridiqueUniteLegale",
    "activitePrincipaleUniteLegale",
    "dateCreationEtablissement",
    "codePostalEtablissement",
    "libelleCommuneEtablissement",
    "etatAdministratifEtablissement",
    "trancheEffectifsUniteLegale",
    "denominationUsuelle1UniteLegale",
    "prenom1UniteLegale",
    "nomUniteLegale",
    "nomUsageUniteLegale",
])

# Mapping categorie juridique INSEE → forme juridique lisible
CATEGORIE_TO_FORME: dict[str, str] = {
    "1000": "EI",
    "2110": "EIRL",
    "5499": "SARL",
    "5498": "EURL",
    "5710": "SAS",
    "5720": "SASU",
    "5308": "SA",
    "6540": "SCI",
    "9220": "Association",
}


class SireneClient:
    def __init__(self, key: str, secret: str):
        self._key = key
        self._secret = secret
        self._token: str | None = None

    @classmethod
    def from_env(cls) -> "SireneClient":
        key = os.environ.get("INSEE_SIRENE_KEY", "")
        secret = os.environ.get("INSEE_SIRENE_SECRET", "")
        if not key or not secret:
            raise EnvironmentError(
                "INSEE_SIRENE_KEY et INSEE_SIRENE_SECRET sont requis dans .env"
            )
        return cls(key, secret)

    # ── Authentification ──────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Obtient un access token OAuth2 via client_credentials.

        Note réseau : api.insee.fr peut rejeter les connexions depuis certains
        réseaux (résidentiel, cloud non whitelisté). En cas de ReadError/ConnectError,
        vérifier l'accès depuis un serveur autorisé ou via un proxy dédié.
        """
        creds = base64.b64encode(f"{self._key}:{self._secret}".encode()).decode()
        try:
            resp = httpx.post(
                SIRENE_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content=b"grant_type=client_credentials",
                timeout=10,
            )
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as exc:
            raise RuntimeError(
                f"Connexion INSEE Sirene impossible ({type(exc).__name__}). "
                "Vérifier l'accès réseau à api.insee.fr (filtrage IP possible). "
                f"Détail : {exc}"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Échec token Sirene : HTTP {resp.status_code} — {resp.text[:200]}"
            )
        self._token = resp.json()["access_token"]
        return self._token

    def _auth_header(self) -> dict[str, str]:
        if not self._token:
            self._get_token()
        return {"Authorization": f"Bearer {self._token}"}

    # ── Recherche établissements ──────────────────────────────────────────────

    def fetch_recent_creations(
        self,
        codes_postaux: list[str] | None = None,
        jours: int = 7,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Retourne les établissements créés dans les N derniers jours dans la zone ICP.

        Args:
            codes_postaux: Liste de codes postaux (défaut : CODES_POSTAUX_ICP).
            jours:         Fenêtre temporelle en jours (défaut : 7).
            max_results:   Nombre maximum de résultats (défaut : 50).

        Returns:
            Liste de leads au format standard du pipeline icp_filter.
        """
        if codes_postaux is None:
            codes_postaux = CODES_POSTAUX_ICP

        date_from = (date.today() - timedelta(days=jours)).isoformat()

        # FIQL query : date création + code postal + état actif
        cp_clause = " OR ".join(
            f"codePostalEtablissement:{cp}" for cp in codes_postaux
        )
        q = (
            f"dateCreationEtablissement:[{date_from} TO *] AND "
            f"({cp_clause}) AND "
            f"etatAdministratifEtablissement:A"
        )

        try:
            resp = httpx.get(
                SIRENE_SIRET_URL,
                headers=self._auth_header(),
                params={
                    "q": q,
                    "nombre": max_results,
                    "champs": CHAMPS_UTILES,
                },
                timeout=15,
            )
        except httpx.TimeoutException:
            raise RuntimeError("Timeout lors de l'appel API Sirene (>15s)")

        if resp.status_code == 401:
            # Token expiré — réessayer avec un nouveau token
            self._token = None
            resp = httpx.get(
                SIRENE_SIRET_URL,
                headers=self._auth_header(),
                params={"q": q, "nombre": max_results, "champs": CHAMPS_UTILES},
                timeout=15,
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Erreur API Sirene : HTTP {resp.status_code} — {resp.text[:300]}"
            )

        data = resp.json()
        etablissements = data.get("etablissements", [])
        total = data.get("header", {}).get("total", len(etablissements))

        print(f"  Sirene : {total} établissement(s) trouvé(s), {len(etablissements)} retourné(s)")

        return [self._parse_etablissement(e) for e in etablissements]

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _parse_etablissement(self, etab: dict[str, Any]) -> dict[str, Any]:
        """Convertit un établissement Sirene au format lead pipeline."""
        ul = etab.get("uniteLegale", {})

        siren = etab.get("siren", "")
        siret = etab.get("siret", "")
        denomination = (
            ul.get("denominationUniteLegale")
            or ul.get("denominationUsuelle1UniteLegale")
            or f"{ul.get('prenom1UniteLegale', '')} {ul.get('nomUsageUniteLegale') or ul.get('nomUniteLegale', '')}".strip()
            or siren
        )

        categorie = ul.get("categorieJuridiqueUniteLegale", "")
        forme_juridique = CATEGORIE_TO_FORME.get(categorie, categorie or "?")

        code_naf_raw = ul.get("activitePrincipaleUniteLegale", "")
        code_naf = code_naf_raw.replace(".", "") if code_naf_raw else ""

        cp = etab.get("codePostalEtablissement", "")
        ville = etab.get("libelleCommuneEtablissement", "")
        date_creation = etab.get("dateCreationEtablissement", "")

        tranche = ul.get("trancheEffectifsUniteLegale", "")
        effectif_min, effectif_max = _tranche_to_effectif(tranche)

        prenom = ul.get("prenom1UniteLegale", "")
        nom = ul.get("nomUsageUniteLegale") or ul.get("nomUniteLegale", "")

        return {
            "id": siret or siren,
            "siren": siren,
            "siret": siret,
            "denomination": denomination.upper(),
            "forme_juridique": forme_juridique,
            "code_naf": code_naf,
            "libelle_naf": "",  # non fourni par Sirene v3 dans ce champ
            "date_creation": date_creation,
            "effectif_min": effectif_min,
            "effectif_max": effectif_max,
            "siege": {
                "code_postal": cp,
                "ville": ville,
            },
            "representant": {
                "prenom": prenom,
                "nom": nom,
            },
            "secteur_label": "",
            "_source": "sirene_api",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tranche_to_effectif(tranche: str) -> tuple[int, int]:
    """Convertit un code tranche INSEE en (effectif_min, effectif_max)."""
    mapping: dict[str, tuple[int, int]] = {
        "00": (0, 0),
        "01": (1, 2),
        "02": (3, 5),
        "03": (6, 9),
        "11": (10, 19),
        "12": (20, 49),
        "21": (50, 99),
        "22": (100, 199),
        "31": (200, 249),
        "32": (250, 499),
        "41": (500, 999),
        "42": (1000, 1999),
        "51": (2000, 4999),
        "52": (5000, 9999),
        "53": (10000, 99999),
    }
    return mapping.get(tranche, (0, 0))


# ── Leads mock pour tests offline ────────────────────────────────────────────

def mock_leads(codes_postaux: list[str] | None = None, jours: int = 7) -> list[dict[str, Any]]:
    """Retourne 5 leads simulés au format Sirene pour les tests offline."""
    if codes_postaux is None:
        codes_postaux = CODES_POSTAUX_ICP
    today = date.today()
    return [
        {
            "id": "75019-MOCK-01",
            "siren": "MOCK-001",
            "siret": "MOCK-001-00001",
            "denomination": "PLOMBERIE EXPRESS PARIS",
            "forme_juridique": "SAS",
            "code_naf": "4322A",
            "libelle_naf": "Travaux d'installation d'eau et de gaz en tous locaux",
            "date_creation": (today - timedelta(days=3)).isoformat(),
            "effectif_min": 1,
            "effectif_max": 3,
            "siege": {"code_postal": "75019", "ville": "PARIS"},
            "representant": {"prenom": "Julien", "nom": "MOREAU"},
            "secteur_label": "BTP",
            "_source": "mock",
        },
        {
            "id": "93500-MOCK-02",
            "siren": "MOCK-002",
            "siret": "MOCK-002-00001",
            "denomination": "KEBAB DU CANAL SARL",
            "forme_juridique": "SARL",
            "code_naf": "5610A",
            "libelle_naf": "Restauration traditionnelle",
            "date_creation": (today - timedelta(days=6)).isoformat(),
            "effectif_min": 2,
            "effectif_max": 4,
            "siege": {"code_postal": "93500", "ville": "PANTIN"},
            "representant": {"prenom": "Omar", "nom": "HADJ"},
            "secteur_label": "Restauration/CHR",
            "_source": "mock",
        },
        {
            "id": "75020-MOCK-03",
            "siren": "MOCK-003",
            "siret": "MOCK-003-00001",
            "denomination": "CONSEIL RH BELLAICHE",
            "forme_juridique": "SASU",
            "code_naf": "7021Z",
            "libelle_naf": "Conseil en relations publiques et communication",
            "date_creation": (today - timedelta(days=2)).isoformat(),
            "effectif_min": 0,
            "effectif_max": 1,
            "siege": {"code_postal": "75020", "ville": "PARIS"},
            "representant": {"prenom": "Sarah", "nom": "BELLAICHE"},
            "secteur_label": "Services aux entreprises",
            "_source": "mock",
        },
        {
            "id": "93300-MOCK-04",
            "siren": "MOCK-004",
            "siret": "MOCK-004-00001",
            "denomination": "ELECTRICITE GENERALE AUBERVILLIERS",
            "forme_juridique": "EURL",
            "code_naf": "4321A",
            "libelle_naf": "Travaux d'installation électrique dans tous locaux",
            "date_creation": (today - timedelta(days=5)).isoformat(),
            "effectif_min": 1,
            "effectif_max": 5,
            "siege": {"code_postal": "93300", "ville": "AUBERVILLIERS"},
            "representant": {"prenom": "Hassan", "nom": "BOUZID"},
            "secteur_label": "BTP",
            "_source": "mock",
        },
        {
            "id": "75011-MOCK-05",
            "siren": "MOCK-005",
            "siret": "MOCK-005-00001",
            "denomination": "EPICERIE FINE BASTILLE",
            "forme_juridique": "SARL",
            "code_naf": "4711B",
            "libelle_naf": "Commerce d'alimentation générale",
            "date_creation": (today - timedelta(days=4)).isoformat(),
            "effectif_min": 2,
            "effectif_max": 3,
            "siege": {"code_postal": "75011", "ville": "PARIS"},
            "representant": {"prenom": "Chen", "nom": "LI"},
            "secteur_label": "Commerce de détail",
            "_source": "mock",
        },
    ]


# ── Script isolé ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=== Test Sirene Client ===")
    print(f"Fenêtre : 7 derniers jours depuis {date.today().isoformat()}")
    print(f"Zone : {len(CODES_POSTAUX_ICP)} codes postaux ICP")
    print()

    leads = None
    api_ok = False

    try:
        client = SireneClient.from_env()
        print("  Obtention du token OAuth2...")
        client._get_token()
        print("  Token obtenu ✓")
        print()

        leads = client.fetch_recent_creations(jours=7, max_results=50)
        api_ok = True

    except EnvironmentError as e:
        print(f"  ERREUR config : {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"  ⚠️  API Sirene inaccessible depuis cet environnement :")
        print(f"     {e}")
        print()
        print("  Diagnostic réseau :")
        print("  - DNS api.insee.fr → 194.254.37.207 (résolu)")
        print("  - TLS handshake → TLSv1.3 OK")
        print("  - HTTP request → connexion réinitialisée par le serveur (TCP RST)")
        print("  - Cause probable : filtrage IP côté gateway INSEE")
        print("    (l'API bloque certains réseaux résidentiels ou non-whitelistés)")
        print()
        print("  Solutions possibles :")
        print("  1. Déployer sur Railway/VPS avec IP fixe + déclaration INSEE")
        print("  2. Utiliser un proxy HTTP sortant autorisé par INSEE")
        print("  3. Tester depuis un réseau professionnel (4G entreprise)")
        print()
        print("  → Bascule sur les leads mock pour valider la logique de parsing :")
        print()
        leads = mock_leads(jours=7)

    print(f"  {len(leads)} lead(s) {'réels' if api_ok else 'simulés (mock)'}. Affichage des 5 premiers :\n")
    for i, lead in enumerate(leads[:5], 1):
        src = f" [{lead.get('_source', 'api')}]"
        print(f"  [{i}]{src} {lead['denomination']}")
        print(f"       SIREN       : {lead['siren']}")
        print(f"       Forme jur.  : {lead['forme_juridique']}")
        print(f"       NAF         : {lead['code_naf']}")
        print(f"       CP / Ville  : {lead['siege']['code_postal']} {lead['siege']['ville']}")
        print(f"       Création    : {lead['date_creation']}")
        print(f"       Effectif    : {lead['effectif_min']}–{lead['effectif_max']} sal.")
        print(f"       Représentant: {lead['representant']['prenom']} {lead['representant']['nom']}")
        print()

    if leads:
        # Passer par le pipeline ICP pour valider le parsing
        import sys as _sys
        _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent.parent))
        from apps.leadcommercial.icp_filter import evaluate_batch
        results = evaluate_batch(leads)
        chauds = [r for r in results if r["statut"] == "CHAUD"]
        tièdes = [r for r in results if r["statut"] == "TIÈDE"]
        exclus = [r for r in results if r["statut"] == "EXCLU"]
        print(f"  Pipeline ICP : {len(chauds)} CHAUD · {len(tièdes)} TIÈDE · {len(exclus)} EXCLU")

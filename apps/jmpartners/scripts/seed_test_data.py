"""Seed script — données réalistes pour tester les agents JM Partners.

Usage :
    uv run python -m apps.jmpartners.scripts.seed_test_data

Génère :
  - 5 contacts (noms français + emails)
  - 7 dossiers (3 avec statuts variés + 4 bilans J+5/15/30/60)
  - 8 déclarations TVA (deadlines J+3 à J+30, statuts variés)
  - 6 acomptes IS (deadlines variées, champs compatibles echeance_agent + declaration_is_agent)
  - 18 documents (mix recu/valide/illisible/en_attente pour les cas limites)

Idempotent : upsert avec ignore_duplicates=True — pas de doublon si relancé.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

# ── UUIDs fixes (seed déterministe) ───────────────────────────────────────────

# contacts
C1 = "seed0000-0000-0000-0001-000000000001"
C2 = "seed0000-0000-0000-0001-000000000002"
C3 = "seed0000-0000-0000-0001-000000000003"
C4 = "seed0000-0000-0000-0001-000000000004"
C5 = "seed0000-0000-0000-0001-000000000005"

# dossiers
D1 = "seed0000-0000-0000-0002-000000000001"  # bilan     en_cours
D2 = "seed0000-0000-0000-0002-000000000002"  # tva       en_cours
D3 = "seed0000-0000-0000-0002-000000000003"  # is        cloture_envoyee
D4 = "seed0000-0000-0000-0002-000000000004"  # bilan     en_cours  J+5
D5 = "seed0000-0000-0000-0002-000000000005"  # bilan     en_cours  J+15
D6 = "seed0000-0000-0000-0002-000000000006"  # bilan     en_cours  J+30
D7 = "seed0000-0000-0000-0002-000000000007"  # bilan     en_cours  J+60

# déclarations TVA
TVA = [f"seed0000-0000-0000-0003-{i:012d}" for i in range(1, 9)]

# acomptes IS
IS = [f"seed0000-0000-0000-0004-{i:012d}" for i in range(1, 7)]

# documents
DOC = [f"seed0000-0000-0000-0005-{i:012d}" for i in range(1, 19)]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _d(days: int) -> str:
    """Retourne une date ISO à J+days."""
    return (date.today() + timedelta(days=days)).isoformat()


def _doc(
    uid: str,
    dossier_id: str,
    type_document: str,
    nom_document: str,
    statut: str,
) -> dict:
    """Construit un document avec les deux schémas (statut + present)."""
    return {
        "id": uid,
        "dossier_id": dossier_id,
        "type_document": type_document,
        "nom_document": nom_document,
        "statut": statut,
        "present": statut in ("recu", "valide"),
    }


# ── Données ───────────────────────────────────────────────────────────────────

def _contacts() -> list[dict]:
    return [
        {"id": C1, "nom": "Dupont SARL",        "email": "contact@dupont-sarl.fr"},
        {"id": C2, "nom": "Martin & Associés",   "email": "cabinet@martin-associes.fr"},
        {"id": C3, "nom": "Lemaire SAS",          "email": "compta@lemaire-sas.fr"},
        {"id": C4, "nom": "Bernard & Fils",       "email": "info@bernard-fils.fr"},
        {"id": C5, "nom": "Petit Négoce EURL",    "email": "direction@petit-negoce.fr"},
    ]


def _dossiers() -> list[dict]:
    cabinet = os.getenv("CABINET_ID", "jmpartners")
    return [
        # ── Les 3 dossiers demandés ────────────────────────────────────────────
        {
            "id": D1, "contact_id": C1, "type": "bilan", "statut": "en_cours",
            "deadline": _d(12), "cabinet_id": cabinet,
            "siren": "123456789", "raison_sociale": "Dupont SARL",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 8500,
        },
        {
            "id": D2, "contact_id": C2, "type": "tva", "statut": "en_cours",
            "deadline": _d(7), "cabinet_id": cabinet,
            "siren": "234567890", "raison_sociale": "Martin & Associés",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 12000,
        },
        {
            "id": D3, "contact_id": C3, "type": "is", "statut": "cloture_envoyee",
            "deadline": _d(45), "cabinet_id": cabinet,
            "siren": "345678901", "raison_sociale": "Lemaire SAS",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 5200,
        },
        # ── 4 bilans avec jours_restants variés ────────────────────────────────
        {
            "id": D4, "contact_id": C4, "type": "bilan", "statut": "en_cours",
            "deadline": _d(5), "cabinet_id": cabinet,
            "siren": "456789012", "raison_sociale": "Bernard & Fils",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 3100,
        },
        {
            "id": D5, "contact_id": C5, "type": "bilan", "statut": "en_cours",
            "deadline": _d(15), "cabinet_id": cabinet,
            "siren": "567890123", "raison_sociale": "Petit Négoce EURL",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 1800,
        },
        {
            "id": D6, "contact_id": C1, "type": "bilan", "statut": "en_cours",
            "deadline": _d(30), "cabinet_id": cabinet,
            "siren": "123456789", "raison_sociale": "Dupont SARL",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 9200,
        },
        {
            "id": D7, "contact_id": C2, "type": "bilan", "statut": "en_cours",
            "deadline": _d(60), "cabinet_id": cabinet,
            "siren": "234567890", "raison_sociale": "Martin & Associés",
            "responsable_email": os.getenv("SMTP_USER", ""),
            "montant_is_estime": 14000,
        },
    ]


def _declarations_tva() -> list[dict]:
    """8 déclarations TVA — J+3, J+7 (x2), J+15 (x2), J+30 (x3)."""
    today = date.today()

    def _periode(days: int) -> str:
        d = today + timedelta(days=days)
        # La période TVA est le mois précédant la deadline
        prev = date(d.year, d.month, 1) - timedelta(days=1)
        return prev.strftime("%Y-%m")

    return [
        # J+3 — urgent
        {
            "id": TVA[0], "dossier_id": D2, "contact_id": C2,
            "periode": _periode(3), "deadline": _d(3),
            "statut": "pieces_manquantes", "montant_tva": 2840.50,
            "alerte_envoyee_at": None,
        },
        # J+7 — attention (D2 mois suivant)
        {
            "id": TVA[1], "dossier_id": D2, "contact_id": C2,
            "periode": _periode(7), "deadline": _d(7),
            "statut": "a_preparer", "montant_tva": 3120.00,
            "alerte_envoyee_at": None,
        },
        # J+7 — D1
        {
            "id": TVA[2], "dossier_id": D1, "contact_id": C1,
            "periode": _periode(7), "deadline": _d(7),
            "statut": "a_preparer", "montant_tva": 1560.75,
            "alerte_envoyee_at": None,
        },
        # J+15 — à surveiller
        {
            "id": TVA[3], "dossier_id": D4, "contact_id": C4,
            "periode": _periode(15), "deadline": _d(15),
            "statut": "a_preparer", "montant_tva": 890.00,
            "alerte_envoyee_at": None,
        },
        # J+15 — D5
        {
            "id": TVA[4], "dossier_id": D5, "contact_id": C5,
            "periode": _periode(15), "deadline": _d(15),
            "statut": "pieces_manquantes", "montant_tva": 450.25,
            "alerte_envoyee_at": None,
        },
        # J+30 — D1
        {
            "id": TVA[5], "dossier_id": D1, "contact_id": C1,
            "periode": _periode(30), "deadline": _d(30),
            "statut": "a_preparer", "montant_tva": 1750.00,
            "alerte_envoyee_at": None,
        },
        # J+30 — D6
        {
            "id": TVA[6], "dossier_id": D6, "contact_id": C1,
            "periode": _periode(30), "deadline": _d(30),
            "statut": "pret", "montant_tva": 3200.00,
            "alerte_envoyee_at": None,
        },
        # J+30 — D7 (déjà validée — exclue par les agents)
        {
            "id": TVA[7], "dossier_id": D7, "contact_id": C2,
            "periode": _periode(30), "deadline": _d(30),
            "statut": "valide", "montant_tva": 4100.00,
            "alerte_envoyee_at": None,
        },
    ]


def _acomptes_is() -> list[dict]:
    """6 acomptes IS — champs compatibles echeance_agent (deadline) + declaration_is_agent (echeance)."""
    def _acompte(uid, dossier_id, contact_id, numero, exercice, days, montant, statut):
        dl = _d(days)
        return {
            "id": uid,
            "dossier_id": dossier_id,
            "contact_id": contact_id,
            "numero_acompte": numero,
            "exercice": exercice,
            # echeance_agent utilise "deadline"
            "deadline": dl,
            # declaration_is_agent utilise "echeance"
            "echeance": dl,
            "montant": montant,
            "montant_estime": montant,
            # echeance_agent filtre statut = "a_payer"
            # declaration_is_agent filtre statut != "paye"
            "statut": statut,
        }

    return [
        _acompte(IS[0], D3, C3, 1, "2026", 3,  1240.00, "a_payer"),   # J+3  urgent
        _acompte(IS[1], D1, C1, 2, "2026", 7,  2100.50, "a_payer"),   # J+7  attention
        _acompte(IS[2], D2, C2, 1, "2026", 15, 3800.00, "a_payer"),   # J+15 surveiller
        _acompte(IS[3], D4, C4, 3, "2026", 20,  950.00, "a_payer"),   # J+20
        _acompte(IS[4], D5, C5, 2, "2026", 45, 1600.00, "a_payer"),   # J+45 hors horizon
        _acompte(IS[5], D6, C1, 4, "2026", 7,  5200.00, "paye"),      # J+7  payé — exclu par echeance_agent
    ]


def _documents() -> list[dict]:
    """18 documents — mix recu/valide/illisible/en_attente pour les cas limites."""
    rows = []

    # D1 — bilan : 3/5 pièces (grand_livre recu, balance valide, factures_achats illisible)
    rows += [
        _doc(DOC[0],  D1, "grand_livre",       "Grand Livre",        "recu"),
        _doc(DOC[1],  D1, "balance",            "Balance",            "valide"),
        _doc(DOC[2],  D1, "factures_achats",    "Factures Achats",    "illisible"),
        # factures_ventes et releves_bancaires absents → pas de ligne en base
    ]

    # D2 — tva : 1/3 pièce (ca_mensuel recu)
    rows += [
        _doc(DOC[3],  D2, "ca_mensuel",         "CA Mensuel",         "recu"),
        # factures_tva et releves_bancaires absents
    ]

    # D3 — is (clôturé) : 1 valide, 1 illisible
    rows += [
        _doc(DOC[4],  D3, "resultat_comptable",  "Résultat Comptable", "valide"),
        _doc(DOC[5],  D3, "bilan_n_1",           "Bilan N-1",          "illisible"),
        # liasse_fiscale absente
    ]

    # D4 — bilan J+5 : aucune pièce reçue (0/5) — cas limite tous absents
    rows += [
        _doc(DOC[6],  D4, "grand_livre",        "Grand Livre",        "en_attente"),
    ]

    # D5 — bilan J+15 : 3/5 pièces valides
    rows += [
        _doc(DOC[7],  D5, "grand_livre",        "Grand Livre",        "valide"),
        _doc(DOC[8],  D5, "balance",            "Balance",            "valide"),
        _doc(DOC[9],  D5, "factures_achats",    "Factures Achats",    "recu"),
        # factures_ventes et releves_bancaires absents
    ]

    # D6 — bilan J+30 : complet (5/5 valides)
    rows += [
        _doc(DOC[10], D6, "grand_livre",        "Grand Livre",        "valide"),
        _doc(DOC[11], D6, "balance",            "Balance",            "valide"),
        _doc(DOC[12], D6, "factures_achats",    "Factures Achats",    "valide"),
        _doc(DOC[13], D6, "factures_ventes",    "Factures Ventes",    "valide"),
        _doc(DOC[14], D6, "releves_bancaires",  "Relevés Bancaires",  "valide"),
    ]

    # D7 — bilan J+60 : 2/5 dont un illisible
    rows += [
        _doc(DOC[15], D7, "grand_livre",        "Grand Livre",        "recu"),
        _doc(DOC[16], D7, "balance",            "Balance",            "illisible"),
        # reste absent
    ]

    # Document orphelin pour tester la robustesse (dossier_id inexistant)
    rows += [
        _doc(DOC[17], "seed0000-0000-0000-0099-000000000001",
             "ca_mensuel", "CA Mensuel orphelin", "recu"),
    ]

    return rows


# ── Logique d'insertion ────────────────────────────────────────────────────────

def _upsert(sb, table: str, rows: list[dict]) -> tuple[int, int]:
    """Insère les lignes avec ignore_duplicates=True. Retourne (insérés, skippés)."""
    if not rows:
        return 0, 0
    try:
        resp = sb.table(table).upsert(rows, ignore_duplicates=True).execute()
        inserted = len(resp.data) if resp.data else 0
        skipped = len(rows) - inserted
        return inserted, skipped
    except Exception as exc:
        print(f"  ⚠️  {table} — erreur upsert : {exc}", file=sys.stderr)
        return 0, len(rows)


def _print_row(table: str, inserted: int, skipped: int, total: int) -> None:
    status = "✅" if inserted > 0 or skipped == total else "⚠️ "
    skip_note = f"  ({skipped} déjà présents)" if skipped else ""
    print(f"  {status}  {table:<22} {inserted:>3} insérés{skip_note}")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main() -> None:
    """Seed toutes les tables JM Partners avec des données de test réalistes."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not url or not key:
        print(
            "❌ SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis.\n"
            "   Exemple : SUPABASE_URL=https://xxx.supabase.co "
            "SUPABASE_SERVICE_KEY=eyJ... uv run python -m apps.jmpartners.scripts.seed_test_data",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from supabase import create_client
        sb = create_client(url, key)
    except Exception as exc:
        print(f"❌ Impossible de se connecter à Supabase : {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n🌱 Seed JM Partners — données de test\n")
    print(f"   Supabase : {url}")
    print(f"   Date de référence : {date.today().isoformat()}\n")

    totals = {"insérés": 0, "skippés": 0}

    datasets: list[tuple[str, list[dict]]] = [
        ("contacts",        _contacts()),
        ("dossiers",        _dossiers()),
        ("declarations_tva", _declarations_tva()),
        ("acomptes_is",     _acomptes_is()),
        ("documents",       _documents()),
    ]

    for table, rows in datasets:
        inserted, skipped = _upsert(sb, table, rows)
        totals["insérés"] += inserted
        totals["skippés"] += skipped
        _print_row(table, inserted, skipped, len(rows))

    print(f"\n{'─' * 50}")
    print(f"   Total : {totals['insérés']} insérés, {totals['skippés']} déjà présents")

    # Résumé métier
    today = date.today()
    print("\n📋 Résumé des données insérées :")
    print(f"   5 contacts  — Dupont, Martin, Lemaire, Bernard, Petit Négoce")
    print(f"   7 dossiers  — 5 en_cours (bilan/tva), 1 cloture_envoyee (is), 1 bilan complet")
    print(f"   8 décl. TVA — J+3 🔴, J+7 🟠×2, J+15 🟡×2, J+30 ×3 (dont 1 valide)")
    print(f"   6 acomptes IS — J+3 🔴, J+7 🟠×2, J+15 🟡, J+20, J+45, 1 payé")
    print(f"  18 documents — recu×5, valide×8, illisible×3, en_attente×1, orphelin×1")

    print(f"\n✅ Seed terminé. Lancez maintenant :")
    print(f"   python -m apps.jmpartners.main --once --dry-run  # vérification sans envoi")
    print(f"   curl https://<votre-service>/health              # état du service\n")


if __name__ == "__main__":
    main()

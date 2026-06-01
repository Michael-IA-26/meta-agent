#!/usr/bin/env python
"""Orchestrateur LeadCommercial — mode dry_run.

Usage :
    python scripts/dry_run_orchestrator.py \\
      --leads tests/fixtures/validation_leads.json \\
      --codes-postaux 75010,75011,75012,75018,75019,75020,93000,93170,93230,93260,93300,93400,93500 \\
      --fenetre-jours 30 \\
      --mode dry_run
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Force UTF-8 sur Windows (évite UnicodeEncodeError avec cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Rendre les modules apps/ accessibles depuis scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from apps.leadcommercial.email_generator import generate_cold_email, generate_fiche_lead
from apps.leadcommercial.enrichment import enrich_lead, get_apis_payantes_summary
from apps.leadcommercial.icp_filter import (
    FENETRE_CREATION_JOURS,
    check_assertions,
    evaluate_batch,
    resolve_date,
)

# ── Assertions attendues ──────────────────────────────────────────────────────

ASSERTIONS: dict[str, dict] = {
    "TEST-01": {"statut_in": ["CHAUD"]},
    "TEST-02": {"statut_in": ["CHAUD"]},
    "TEST-03": {"statut_in": ["CHAUD", "TIÈDE"]},
    "TEST-04": {"statut_in": ["CHAUD", "TIÈDE"]},
    "TEST-05": {"statut": "EXCLU", "raison_contains": "effectif"},
    "TEST-06": {"statut": "EXCLU"},
    "TEST-07": {"statut": "EXCLU", "raison_contains": "fenêtre"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_leads(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_leads_dates(leads: list[dict], today: date) -> list[dict]:
    """Convertit les dates relatives 'J-N' en dates ISO réelles."""
    resolved = []
    for lead in leads:
        lead = dict(lead)
        dc = lead.get("date_creation", "")
        if dc.startswith("J-"):
            lead["date_creation"] = resolve_date(dc, today).isoformat()
        resolved.append(lead)
    return resolved


def print_separator(char: str = "─", width: int = 70) -> None:
    print(char * width)


def print_result(result: dict, idx: int) -> None:
    statut = result["statut"]
    score_str = f"{result['score']}/100" if statut != "EXCLU" else "EXCLU"
    print(f"\n[{idx}] {result['id']} — {result['denomination']}")
    print(f"     CP: {result['code_postal']} | Création: {result.get('date_creation', '?')}")
    print(f"     Statut: {statut} | Score: {score_str}")
    if result.get("raison_exclusion"):
        print(f"     Raison exclusion: {result['raison_exclusion']}")
    else:
        for d in result.get("scoring_details", []):
            print(f"       {d}")


# ── Pipeline principal ────────────────────────────────────────────────────────

def run(
    leads_path: str,
    codes_postaux: list[str] | None,
    fenetre_jours: int,
    mode: str,
) -> int:
    today = date.today()
    print_separator("═")
    print(f"  LeadCommercial — Orchestrateur {mode.upper()}")
    print(f"  Date d'exécution : {today.strftime('%d/%m/%Y')}")
    print(f"  Fenêtre création : {fenetre_jours} jours")
    if codes_postaux:
        print(f"  Codes postaux ICP : {', '.join(codes_postaux)}")
    print_separator("═")

    # Chargement et résolution des dates
    leads = load_leads(leads_path)
    leads = resolve_leads_dates(leads, today)
    print(f"\n  {len(leads)} lead(s) chargé(s) depuis {leads_path}\n")

    # Évaluation ICP
    results = evaluate_batch(leads, today)

    # Affichage des résultats
    print_separator()
    print("  RÉSULTATS SCORING ICP")
    print_separator()
    for i, result in enumerate(results, 1):
        print_result(result, i)

    # Résumé par statut
    from collections import Counter
    counts = Counter(r["statut"] for r in results)
    print(f"\n  ── Résumé ──")
    for statut, n in sorted(counts.items()):
        print(f"     {statut}: {n} lead(s)")

    # Vérification des assertions
    print_separator()
    print("  ASSERTIONS")
    print_separator()
    failures = check_assertions(results, ASSERTIONS)
    passed = 0
    for lead_id, assertion in ASSERTIONS.items():
        result = next((r for r in results if r["id"] == lead_id), None)
        if result is None:
            print(f"  ⚠️  {lead_id} : lead non trouvé dans les résultats")
            continue
        failure = next((f for f in failures if f["id"] == lead_id), None)
        if failure:
            print(f"  ❌  {failure['message']}")
        else:
            print(f"  ✅  {lead_id} : {result['statut']} (attendu {assertion})")
            passed += 1

    total = len(ASSERTIONS)
    print(f"\n  {passed}/{total} assertions passées")

    # Génération emails et fiches pour leads qualifiés
    leads_qualifies = [r for r in results if r["statut"] in {"CHAUD", "TIÈDE"}]
    enrichissements = []

    if leads_qualifies:
        print_separator()
        print("  GÉNÉRATION EMAILS COLD OUTREACH (dry_run)")
        print_separator()

        # Trouver le lead d'origine pour accéder aux champs complets
        leads_by_id = {lead["id"]: lead for lead in leads}

        for result in leads_qualifies:
            lead_orig = leads_by_id.get(result["id"], {})
            # Reconstruire le lead enrichi pour le générateur
            lead_for_email = {**lead_orig, **result}
            if "representant" not in lead_for_email:
                lead_for_email["representant"] = {}

            date_creation = result.get("date_creation")
            if date_creation:
                jours = (today - date.fromisoformat(date_creation)).days
            else:
                jours = 0

            email = generate_cold_email(lead_for_email, jours)
            print(f"\n  [{result['id']}] {result['denomination']} — {result['statut']} ({result['score']}/100)")
            print(f"  Objet : {email['objet']}")
            print(f"  Mots (corps) : {email['word_count']} {'✅' if email['conforme_120_mots'] else '❌ > 120 mots'}")

            # Enrichissement
            enrichissement = enrich_lead(lead_for_email)
            enrichissements.append({"result": result, "enrichissement": enrichissement})

    # Meilleur lead CHAUD → email complet + fiche
    chauds = [r for r in results if r["statut"] == "CHAUD"]
    if chauds:
        best = max(chauds, key=lambda r: r["score"])
        lead_orig = {lead["id"]: lead for lead in leads}.get(best["id"], {})
        lead_for_best = {**lead_orig, **best}
        if "representant" not in lead_for_best:
            lead_for_best["representant"] = {}

        date_creation = best.get("date_creation")
        jours_best = (today - date.fromisoformat(date_creation)).days if date_creation else 0

        email_best = generate_cold_email(lead_for_best, jours_best)
        fiche_best = generate_fiche_lead(lead_for_best, email_best)

        print_separator()
        print(f"  EMAIL COMPLET — Meilleur lead CHAUD : {best['denomination']} (score {best['score']}/100)")
        print_separator()
        print(email_best["email_complet"])
        print_separator()
        print("  FICHE LEAD")
        print_separator()
        print(fiche_best)

    # Résumé enrichissement APIs payantes
    print_separator()
    print("  ENRICHISSEMENT CONTACT — COMPARATIF OPTIONS")
    print_separator()
    apis = get_apis_payantes_summary()
    print(f"  {'Option':<12} {'Fiabilité':>10} {'Coût/lead':>10} {'Coût/mois':>12}  Avantage")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12}  {'-'*30}")
    for a in apis:
        print(
            f"  {a['nom']:<12} {a['fiabilite_pct']:>9}% "
            f"{a['cout_unitaire_eur']:>9.2f}€ "
            f"{a['cout_mensuel_eur']:>11.2f}€  "
            f"{a['avantages'][:50]}"
        )
    print(f"\n  Volume mensuel estimé : {180} leads qualifiés (450 bruts × 40 %)")

    # Code retour
    if failures:
        print(f"\n  ⚠️  {len(failures)} assertion(s) en échec")
        return 1
    print(f"\n  ✅  Toutes les assertions sont validées — pipeline opérationnel")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LeadCommercial dry_run orchestrator")
    parser.add_argument("--leads", default="tests/fixtures/validation_leads.json")
    parser.add_argument("--codes-postaux", default=None, help="Liste CSV de codes postaux")
    parser.add_argument("--fenetre-jours", type=int, default=FENETRE_CREATION_JOURS)
    parser.add_argument("--mode", default="dry_run", choices=["dry_run", "live"])
    args = parser.parse_args()

    codes_postaux = args.codes_postaux.split(",") if args.codes_postaux else None

    if args.mode == "live":
        print("⚠️  Mode live non implémenté — bascule automatique sur dry_run", file=sys.stderr)

    exit_code = run(
        leads_path=args.leads,
        codes_postaux=codes_postaux,
        fenetre_jours=args.fenetre_jours,
        mode=args.mode,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

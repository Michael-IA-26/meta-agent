"""Tests automatiques de la validation dry_run Jour 1.

Couvre les 7 profils de test ICP JM Partners :
- TEST-01 à TEST-04 : leads qualifiés (CHAUD / TIÈDE)
- TEST-05 à TEST-07 : leads exclus (effectif, agriculture, fenêtre)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from apps.leadcommercial.icp_filter import (
    check_assertions,
    evaluate_batch,
    evaluate_lead,
    resolve_date,
    _detect_franchise,
)
from apps.leadcommercial.email_generator import generate_cold_email, generate_fiche_lead

TODAY = date.today()

FIXTURES_PATH = ROOT / "tests" / "fixtures" / "validation_leads.json"

ASSERTIONS = {
    "TEST-01": {"statut_in": ["CHAUD"]},
    "TEST-02": {"statut_in": ["CHAUD"]},
    "TEST-03": {"statut_in": ["TIÈDE"]},   # J2 : tech NAF 62xx abaissé à +3 → 73 pts
    "TEST-04": {"statut_in": ["CHAUD", "TIÈDE"]},
    "TEST-05": {"statut": "EXCLU", "raison_contains": "effectif"},
    "TEST-06": {"statut": "EXCLU"},
    "TEST-07": {"statut": "EXCLU", "raison_contains": "fenêtre"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_lead(lead_id: str) -> dict:
    leads = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    lead = next(l for l in leads if l["id"] == lead_id)
    # Résoudre les dates relatives
    dc = lead.get("date_creation", "")
    if dc.startswith("J-"):
        lead = dict(lead)
        lead["date_creation"] = resolve_date(dc, TODAY).isoformat()
    return lead


# ── TEST-01 : Boulangerie Paris 19e ──────────────────────────────────────────

def test_01_boulangerie_chaud():
    lead = load_lead("TEST-01")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "CHAUD", f"TEST-01 : attendu CHAUD, obtenu {result['statut']}"
    assert result["score"] >= 75


def test_01_boulangerie_score_detail():
    lead = load_lead("TEST-01")
    result = evaluate_lead(lead, TODAY)
    # Zone ICP, EURL (prioritaire), TPE, création récente, secteur prioritaire
    assert result["score"] >= 80, f"Score {result['score']} trop bas pour boulangerie TPE Paris 19"


# ── TEST-02 : BTP Pantin ─────────────────────────────────────────────────────

def test_02_btp_chaud():
    lead = load_lead("TEST-02")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "CHAUD", f"TEST-02 : attendu CHAUD, obtenu {result['statut']}"


def test_02_btp_secteur_prioritaire():
    lead = load_lead("TEST-02")
    result = evaluate_lead(lead, TODAY)
    details_joined = " ".join(result.get("scoring_details", []))
    assert "BTP" in details_joined or "btp" in details_joined.lower() or result["score"] >= 75


# ── TEST-03 : Tech Paris 11e ─────────────────────────────────────────────────

def test_03_tech_tiede_apres_ajustement_j2():
    """J2 : NAF 62xx abaissé de +7 à +3 → score 73 → TIÈDE (< 75)."""
    lead = load_lead("TEST-03")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "TIÈDE", (
        f"TEST-03 J2 : attendu TIÈDE (score < 75), obtenu {result['statut']} ({result['score']}/100)"
    )
    assert result["score"] < 75, f"Score {result['score']} devrait être < 75 après ajustement J2"


# ── TEST-04 : Assurance Aubervilliers ─────────────────────────────────────────

def test_04_assurance_chaud_ou_tiede():
    lead = load_lead("TEST-04")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] in {"CHAUD", "TIÈDE"}, (
        f"TEST-04 : attendu CHAUD ou TIÈDE, obtenu {result['statut']}"
    )


def test_04_axa_flag_franchise_probable():
    """AXA + NAF 6622Z → franchise_probable=True avec avertissement."""
    lead = load_lead("TEST-04")
    result = evaluate_lead(lead, TODAY)
    assert result["franchise_probable"] is True, (
        "TEST-04 AXA : franchise_probable doit être True (marque AXA + NAF 6622Z)"
    )
    assert len(result["warnings"]) > 0
    assert "AXA" in result["warnings"][0] or "franchise" in result["warnings"][0].lower()


def test_04_axa_non_exclu_malgre_franchise():
    """Le flag franchise ne doit pas exclure le lead — il reste CHAUD ou TIÈDE."""
    lead = load_lead("TEST-04")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] != "EXCLU", (
        "TEST-04 AXA : franchise_probable ne doit pas forcer l'exclusion"
    )


def test_franchise_detection_naf_hors_assurance():
    """Un lead non-assurance (BTP) ne doit pas déclencher le flag franchise."""
    result = _detect_franchise("AXA RENOVATION BTP", "4391B")
    assert result is None, "NAF BTP ne doit pas déclencher le flag franchise assurance"


def test_franchise_detection_sans_marque():
    """NAF assurance sans nom de grande marque → pas de flag."""
    result = _detect_franchise("DUPONT ASSURANCES CONSEILS", "6622Z")
    assert result is None, "Assurance indépendante sans marque ne doit pas déclencher le flag"


# ── TEST-05 : Holding 120 salariés ────────────────────────────────────────────

def test_05_holding_exclu_effectif():
    lead = load_lead("TEST-05")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "EXCLU", f"TEST-05 : attendu EXCLU, obtenu {result['statut']}"
    assert "effectif" in (result.get("raison_exclusion") or "").lower(), (
        f"TEST-05 : raison doit contenir 'effectif', obtenu : {result.get('raison_exclusion')}"
    )
    assert result["score"] == 0


# ── TEST-06 : Agriculture hors zone ───────────────────────────────────────────

def test_06_agriculture_exclu():
    lead = load_lead("TEST-06")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "EXCLU", f"TEST-06 : attendu EXCLU, obtenu {result['statut']}"
    assert result["score"] == 0


def test_06_agriculture_raison_agriculture_ou_geo():
    lead = load_lead("TEST-06")
    result = evaluate_lead(lead, TODAY)
    raison = (result.get("raison_exclusion") or "").lower()
    assert "agriculture" in raison or "géograph" in raison or "zone" in raison, (
        f"TEST-06 : raison inattendue : {result.get('raison_exclusion')}"
    )


# ── TEST-07 : Restaurant hors fenêtre ─────────────────────────────────────────

def test_07_restaurant_exclu_fenetre():
    lead = load_lead("TEST-07")
    result = evaluate_lead(lead, TODAY)
    assert result["statut"] == "EXCLU", f"TEST-07 : attendu EXCLU, obtenu {result['statut']}"
    assert "fenêtre" in (result.get("raison_exclusion") or "").lower(), (
        f"TEST-07 : raison doit contenir 'fenêtre', obtenu : {result.get('raison_exclusion')}"
    )


# ── Tests batch + assertions ──────────────────────────────────────────────────

def test_batch_no_exception():
    """Les 7 leads doivent être traités sans lever d'exception Python."""
    leads = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    for lead in leads:
        dc = lead.get("date_creation", "")
        if dc.startswith("J-"):
            lead = dict(lead)
            lead["date_creation"] = resolve_date(dc, TODAY).isoformat()
    results = evaluate_batch(leads, TODAY)
    assert len(results) == 7


def test_all_assertions_pass():
    """Toutes les assertions ICP doivent passer sans failure."""
    leads = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    for i, lead in enumerate(leads):
        dc = lead.get("date_creation", "")
        if dc.startswith("J-"):
            leads[i] = dict(lead)
            leads[i]["date_creation"] = resolve_date(dc, TODAY).isoformat()
    results = evaluate_batch(leads, TODAY)
    failures = check_assertions(results, ASSERTIONS)
    assert failures == [], "\n".join(f["message"] for f in failures)


def test_au_moins_un_chaud():
    """Au moins 1 lead CHAUD doit être généré sur les 7."""
    leads = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    for i, lead in enumerate(leads):
        dc = lead.get("date_creation", "")
        if dc.startswith("J-"):
            leads[i] = dict(lead)
            leads[i]["date_creation"] = resolve_date(dc, TODAY).isoformat()
    results = evaluate_batch(leads, TODAY)
    chauds = [r for r in results if r["statut"] == "CHAUD"]
    assert len(chauds) >= 1, "Aucun lead CHAUD généré — vérifier le scorer"


def test_trois_exclus():
    """Exactement 3 leads doivent être exclus (TEST-05, 06, 07)."""
    leads = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    for i, lead in enumerate(leads):
        dc = lead.get("date_creation", "")
        if dc.startswith("J-"):
            leads[i] = dict(lead)
            leads[i]["date_creation"] = resolve_date(dc, TODAY).isoformat()
    results = evaluate_batch(leads, TODAY)
    exclus = [r for r in results if r["statut"] == "EXCLU"]
    assert len(exclus) == 3, f"Attendu 3 exclusions, obtenu {len(exclus)}: {[r['id'] for r in exclus]}"


# ── Tests email cold outreach ─────────────────────────────────────────────────

def test_email_conforme_120_mots():
    """L'email du meilleur lead CHAUD doit respecter la limite de 120 mots."""
    lead = load_lead("TEST-01")
    lead["siren"] = "SIMUL-001"
    result = evaluate_lead(lead, TODAY)
    lead_merged = {**lead, **result}
    date_creation = result.get("date_creation")
    jours = (TODAY - date.fromisoformat(date_creation)).days if date_creation else 8
    email = generate_cold_email(lead_merged, jours)
    assert email["conforme_120_mots"], (
        f"Email trop long : {email['word_count']} mots (max 120)"
    )


def test_email_contient_cta():
    """L'email doit contenir le CTA standard '20 min'."""
    lead = load_lead("TEST-01")
    lead["siren"] = "SIMUL-001"
    result = evaluate_lead(lead, TODAY)
    lead_merged = {**lead, **result}
    email = generate_cold_email(lead_merged, 8)
    assert "20 min" in email["corps"], "CTA '20 min' absent du corps de l'email"


def test_email_contient_mention_rgpd():
    """L'email doit contenir la mention RGPD obligatoire."""
    lead = load_lead("TEST-01")
    lead["siren"] = "SIMUL-001"
    result = evaluate_lead(lead, TODAY)
    lead_merged = {**lead, **result}
    email = generate_cold_email(lead_merged, 8)
    assert "STOP" in email["email_complet"], "Mention STOP/RGPD absente de l'email"


def test_email_en_francais():
    """L'email ne doit pas contenir de mots anglais courants (hello, dear, meeting)."""
    lead = load_lead("TEST-02")
    lead["siren"] = "SIMUL-002"
    result = evaluate_lead(lead, TODAY)
    lead_merged = {**lead, **result}
    email = generate_cold_email(lead_merged, 22)
    corps_lower = email["corps"].lower()
    for mot_anglais in ["hello", "dear", "meeting", "follow-up"]:
        assert mot_anglais not in corps_lower, f"Mot anglais '{mot_anglais}' détecté dans l'email"

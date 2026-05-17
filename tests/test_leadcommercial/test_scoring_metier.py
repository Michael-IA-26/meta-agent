import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.leadcommercial.scorer import score_batch, score_lead


def make_company(**kwargs):
    """Société de base éligible : SAS IDF Paris, services, création ancienne."""
    base = {
        "siren": "000000001",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",  # SAS — prioritaire
        "code_naf": "70.22Z",
        "dept": "75",
        "date_creation": "2026-01-01",
    }
    base.update(kwargs)
    return base


# ── 1. Malus forme juridique non prioritaire ──────────────────────────────────

def test_forme_non_prioritaire_malus_10pts():
    """Forme hors FORMES_PRIORITAIRES → -10 pts sur signal creation (100 → 90)."""
    company = make_company(siren="001", forme_juridique="8110")
    result = score_lead(company, "creation")
    assert result["score"] == 90
    assert any("-10" in d for d in result["scoring_details"])


# ── 2. Bonus création très récente (≤ 7 jours) ───────────────────────────────

def test_creation_tres_recente_bonus_10pts():
    """Création il y a 3 jours + signal rattrapage (80) → 80+10=90."""
    company = make_company(
        siren="002",
        date_creation=(date.today() - timedelta(days=3)).isoformat(),
    )
    result = score_lead(company, "rattrapage")
    assert result["score"] == 90
    assert any("+10" in d for d in result["scoring_details"])


# ── 3. Bonus création récente (7 < jours ≤ 14) ───────────────────────────────

def test_creation_recente_bonus_5pts():
    """Création il y a 10 jours + signal rattrapage (80) → 80+5=85."""
    company = make_company(
        siren="003",
        date_creation=(date.today() - timedelta(days=10)).isoformat(),
    )
    result = score_lead(company, "rattrapage")
    assert result["score"] == 85
    assert any("+5" in d for d in result["scoring_details"])


# ── 4. Signal intention → qualifié au seuil 50 ───────────────────────────────

def test_signal_intention_qualifie():
    """Signal intention = 60 pts → score 60, qualified=True (≥ 50)."""
    company = make_company(siren="004")
    result = score_lead(company, "intention")
    assert result["score"] == 60
    assert result["qualified"] is True


# ── 5. Seuil de qualification exact à 50 (edge case) ─────────────────────────

def test_seuil_qualification_exactement_50():
    """intention (60) + forme non prioritaire (-10) = 50 → qualified=True."""
    company = make_company(siren="005", forme_juridique="8110")
    result = score_lead(company, "intention")
    assert result["score"] == 50
    assert result["qualified"] is True


# ── 6. Tous les départements IDF produisent un score positif ─────────────────

@pytest.mark.parametrize("dept", ["75", "77", "78", "91", "92", "93", "94", "95"])
def test_tous_depts_idf_qualifies(dept):
    """Chaque code département IDF doit passer le filtre géographique."""
    company = make_company(siren=f"06{dept}", dept=dept)
    result = score_lead(company, "creation")
    assert result["score"] > 0, f"dept {dept} a produit un score nul"
    assert result["qualified"] is True


# ── 7. Procédure collective → score forcé à 0 ────────────────────────────────
# TDD : exclusion métier non encore implémentée dans scorer.py

@pytest.mark.xfail(reason="Exclusion procédure collective non implémentée dans scorer.py", strict=True)
def test_procedure_collective_score_zero():
    """Société en procédure collective → score 0, qualified=False (règle métier ICP)."""
    company = make_company(siren="007", procedure_collective=True)
    result = score_lead(company, "creation")
    assert result["score"] == 0
    assert result["qualified"] is False


# ── 8. Effectif > 50 salariés → hors ICP ─────────────────────────────────────
# TDD : filtre effectif non encore implémenté dans scorer.py

@pytest.mark.xfail(reason="Filtre effectif > 50 non implémenté dans scorer.py", strict=True)
def test_effectif_superieur_50_exclu():
    """Effectif 75 salariés → hors cible TPE JM Partners, qualified=False."""
    company = make_company(siren="008", effectif=75)
    result = score_lead(company, "creation")
    assert result["qualified"] is False


# ── 9. Secteur exclu (association NAF 94.99Z) → score 0 ──────────────────────
# TDD : liste de NAF exclus non encore implémentée dans scorer.py

@pytest.mark.xfail(reason="Exclusion par secteur NAF non implémentée dans scorer.py", strict=True)
def test_secteur_exclu_association_score_zero():
    """NAF 94.99Z (association loi 1901) est un secteur exclu → score 0."""
    company = make_company(siren="009", code_naf="94.99Z")
    result = score_lead(company, "creation")
    assert result["score"] == 0
    assert result["qualified"] is False


# ── 10. Déduplication : SIREN doublon → une seule entrée en sortie ───────────
# TDD : déduplication non encore implémentée dans score_batch

@pytest.mark.xfail(reason="Déduplication par SIREN non implémentée dans score_batch", strict=True)
def test_deduplication_siren_doublon_batch():
    """score_batch avec le même SIREN deux fois ne doit retourner qu'un résultat."""
    company = make_company(siren="010")
    results = score_batch([company, company], "creation")
    assert len(results) == 1

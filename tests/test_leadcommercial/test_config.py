"""Tests pour apps/leadcommercial/config (schema + loader)."""

import pytest
from pathlib import Path

from apps.leadcommercial.config.schema import (
    CriteresRecherche,
    LeadHunterConfig,
    SeuilsScoring,
    effectif_codes,
)
from apps.leadcommercial.config.loader import load_config

_YAML_PATH = Path(__file__).parent.parent.parent / "apps/leadcommercial/config/lead_hunter.yaml"


# ---------------------------------------------------------------------------
# Test 1 : charge le YAML de référence et vérifie les valeurs attendues
# ---------------------------------------------------------------------------

def test_load_yaml_valeurs_reference():
    cfg = load_config(_YAML_PATH)

    assert cfg.recherche.codes_postaux == ["93300"]
    assert cfg.recherche.anciennete_jours == 30
    assert cfg.recherche.effectif_min == 0
    assert cfg.recherche.effectif_max == 49
    assert cfg.recherche.inclure_effectif_non_renseigne is True
    assert cfg.scoring.chaud_min == 75
    assert cfg.scoring.tiede_min == 50
    assert cfg.scoring.exclu_max == 30


# ---------------------------------------------------------------------------
# Test 2 : anciennete_jours + date → ValueError
# ---------------------------------------------------------------------------

def test_anciennete_et_dates_mutuellement_exclusifs():
    with pytest.raises(ValueError, match="mutuellement exclusifs"):
        CriteresRecherche(
            codes_postaux=["75001"],
            anciennete_jours=30,
            date_creation_min="2026-01-01",
        )


# ---------------------------------------------------------------------------
# Test 3 : précédence CLI > YAML (code postal CLI surcharge le YAML)
# ---------------------------------------------------------------------------

def test_precedence_cli_sur_yaml():
    cfg = load_config(_YAML_PATH, codes_postaux=["75008"])

    assert cfg.recherche.codes_postaux == ["75008"], (
        "Le code postal CLI doit surcharger celui du YAML"
    )
    # Les autres valeurs restent celles du YAML
    assert cfg.recherche.anciennete_jours == 30


def test_precedence_cli_anciennete_efface_dates_yaml(tmp_path):
    yaml_content = """
recherche:
  codes_postaux: ["93300"]
  date_creation_min: "2026-01-01"
  date_creation_max: "2026-01-31"
scoring:
  chaud_min: 75
  tiede_min: 50
  exclu_max: 30
"""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    # CLI anciennete_jours efface les dates du YAML
    cfg = load_config(yaml_file, anciennete_jours=7)
    assert cfg.recherche.anciennete_jours == 7
    assert cfg.recherche.date_creation_min is None
    assert cfg.recherche.date_creation_max is None


# ---------------------------------------------------------------------------
# Test 4 : seuils incohérents → ValueError
# ---------------------------------------------------------------------------

def test_seuils_incoherents_rejetes():
    with pytest.raises(ValueError, match="incohérents"):
        SeuilsScoring(chaud_min=40, tiede_min=50, exclu_max=30)

    with pytest.raises(ValueError, match="incohérents"):
        SeuilsScoring(chaud_min=75, tiede_min=50, exclu_max=60)


# ---------------------------------------------------------------------------
# Test 5 : effectif_min=0 + inclure_effectif_non_renseigne=True
#          → "00" et "NN" sont dans la liste autorisée
# ---------------------------------------------------------------------------

def test_effectif_tranches_inclut_zero_et_nn():
    r = CriteresRecherche(
        codes_postaux=["93300"],
        effectif_min=0,
        effectif_max=49,
        inclure_effectif_non_renseigne=True,
    )
    tranches = r.effectif_tranches()

    assert "NN" in tranches, "NN (non renseigné) doit être dans les tranches autorisées"
    assert "" in tranches, "chaîne vide (effectif None → '') doit être dans les tranches autorisées"
    assert "00" in tranches, "00 (0 salarié) doit être dans les tranches autorisées"
    assert "12" in tranches, "12 (20-49 sal.) doit être dans les tranches autorisées"
    # Hors plage
    assert "21" not in tranches, "21 (50-99 sal.) ne doit pas être inclus"


def test_effectif_tranches_exclu_nn_quand_false():
    r = CriteresRecherche(
        codes_postaux=["93300"],
        effectif_min=0,
        effectif_max=49,
        inclure_effectif_non_renseigne=False,
    )
    tranches = r.effectif_tranches()

    assert "NN" not in tranches
    assert "" not in tranches
    assert "00" in tranches

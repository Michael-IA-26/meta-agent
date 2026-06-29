"""TDD — tva_declarator : génération déclaration TVA CA3 depuis écritures comptables."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _ecritures_normales():
    """Mois normal : TVA collectée 2000€, TVA déductible 500€ → solde 1500€."""
    return [
        {"compte_debit": "411",   "compte_credit": "44571", "montant": 2000.0},  # TVA collectée
        {"compte_debit": "44566", "compte_credit": "401",   "montant": 500.0},   # TVA déductible
        {"compte_debit": "411",   "compte_credit": "7070",  "montant": 8000.0},  # Produits
        {"compte_debit": "6070",  "compte_credit": "401",   "montant": 3000.0},  # Charges
    ]


def _ecritures_solde_negatif():
    """TVA déductible > collectée → crédit de TVA."""
    return [
        {"compte_debit": "411",   "compte_credit": "44571", "montant": 300.0},
        {"compte_debit": "44566", "compte_credit": "401",   "montant": 1200.0},
    ]


def _ecritures_exoneration():
    """Pas de TVA collectée ni déductible."""
    return [
        {"compte_debit": "411", "compte_credit": "7070", "montant": 5000.0},
    ]


def _ecritures_prorata():
    """TVA partiellement déductible (prorata 60%)."""
    return [
        {"compte_debit": "411",   "compte_credit": "44571", "montant": 1000.0},
        {"compte_debit": "44566", "compte_credit": "401",   "montant": 600.0},   # déjà proratisé
        {"compte_debit": "44567", "compte_credit": "401",   "montant": 400.0},   # TVA non déductible
    ]


def _make_sb(dossier_id="doss-1", ecritures=None, declarations=None):
    sb = MagicMock()
    ecritures = ecritures or _ecritures_normales()
    declarations = declarations or [{"id": "decl-1", "periode": "2026-05", "statut": "a_preparer"}]

    # Cache per-table mocks so the same object is returned on repeated calls
    _cache: dict = {}

    def _table(name):
        if name in _cache:
            return _cache[name]
        t = MagicMock()
        if name == "ecritures":
            t.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = ecritures
        elif name == "declarations_tva":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = declarations[0] if declarations else None
            t.update.return_value.eq.return_value.execute.return_value.data = [{"id": "decl-1"}]
        elif name == "journaux":
            t.insert.return_value.execute.return_value.data = [{"id": "jnl-1"}]
        _cache[name] = t
        return t

    sb.table = MagicMock(side_effect=_table)
    sb._table_cache = _cache  # expose for assertions
    return sb


def _make_storage():
    storage = MagicMock()
    storage.from_.return_value.upload.return_value = MagicMock()
    storage.from_.return_value.get_public_url.return_value = "https://storage.supabase.co/decl.pdf"
    return storage


# ── Tests : calcul des lignes CA3 ─────────────────────────────────────────────

def test_ca3_tva_collectee_correcte():
    """La ligne TVA collectée (44571) est correctement agrégée."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_normales())

    assert abs(lignes["tva_collectee"] - 2000.0) < 0.01


def test_ca3_tva_deductible_correcte():
    """La ligne TVA déductible (44566) est correctement agrégée."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_normales())

    assert abs(lignes["tva_deductible"] - 500.0) < 0.01


def test_ca3_solde_normal():
    """Solde CA3 = TVA collectée - TVA déductible."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_normales())

    assert abs(lignes["solde"] - 1500.0) < 0.01


def test_ca3_solde_negatif_credit_de_tva():
    """Solde négatif → crédit de TVA (report ou remboursement)."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_solde_negatif())

    assert lignes["solde"] < 0
    assert abs(lignes["solde"] - (-900.0)) < 0.01
    assert lignes["credit_tva"] == abs(lignes["solde"])


def test_ca3_exoneration_tout_zero():
    """Sans 44571/44566, tous les montants TVA sont zéro."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_exoneration())

    assert lignes["tva_collectee"] == 0.0
    assert lignes["tva_deductible"] == 0.0
    assert lignes["solde"] == 0.0


def test_ca3_prorata_compte_44567():
    """La TVA non déductible (44567) est exclue du calcul."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_prorata())

    # 44566 seul compte, 44567 exclu
    assert abs(lignes["tva_deductible"] - 600.0) < 0.01
    assert abs(lignes["solde"] - 400.0) < 0.01


def test_ca3_chiffre_affaires_hors_taxe():
    """Le CA HT est calculé depuis les comptes 70x."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_normales())

    assert abs(lignes["ca_ht"] - 8000.0) < 0.01


def test_ca3_structure_complete():
    """Les lignes CA3 doivent contenir tous les champs requis."""
    from apps.jmpartners.agents.tva_declarator import _compute_ca3_lignes

    lignes = _compute_ca3_lignes(_ecritures_normales())

    for field in ("tva_collectee", "tva_deductible", "solde", "credit_tva", "ca_ht"):
        assert field in lignes, f"Champ manquant : {field}"


# ── Tests : génération PDF ────────────────────────────────────────────────────

def test_generate_pdf_retourne_bytes():
    """La génération PDF retourne des bytes non vides."""
    from apps.jmpartners.agents.tva_declarator import _generate_pdf_ca3

    lignes = {
        "tva_collectee": 2000.0,
        "tva_deductible": 500.0,
        "solde": 1500.0,
        "credit_tva": 0.0,
        "ca_ht": 8000.0,
    }

    try:
        pdf_bytes = _generate_pdf_ca3("2026-05", "doss-1", lignes)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
    except ImportError:
        pytest.skip("reportlab non installé")


# ── Tests : flux run() complet ────────────────────────────────────────────────

def test_run_retourne_result_ok(monkeypatch):
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    mock_storage = _make_storage()
    mock_sb.storage = mock_storage

    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_ca3", return_value=fake_pdf),
    ):
        result = mod.run("doss-1", "2026-05")

    assert result["statut"] == "generée"
    assert result["erreur"] is None
    assert result["declaration_id"] is not None


def test_run_met_a_jour_statut_declaration(monkeypatch):
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    mock_sb.storage = _make_storage()

    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_ca3", return_value=fake_pdf),
    ):
        mod.run("doss-1", "2026-05")

    mock_sb.table("declarations_tva").update.assert_called()
    update_payload = mock_sb.table("declarations_tva").update.call_args[0][0]
    assert update_payload.get("statut") == "generée"


def test_run_stocke_pdf_dans_storage(monkeypatch):
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    mock_storage = _make_storage()
    mock_sb.storage = mock_storage

    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_ca3", return_value=fake_pdf),
    ):
        result = mod.run("doss-1", "2026-05")

    mock_storage.from_.assert_called()
    assert result["pdf_url"] is not None


def test_run_erreur_si_declaration_introuvable(monkeypatch):
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = MagicMock()

    def _table(name):
        t = MagicMock()
        if name == "declarations_tva":
            t.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        return t

    mock_sb.table = MagicMock(side_effect=_table)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doss-x", "2026-05")

    assert result["statut"] == "erreur"
    assert "introuvable" in (result["erreur"] or "").lower()


def test_run_dry_run_ne_persiste_pas(monkeypatch):
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    mock_sb.storage = _make_storage()

    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_ca3", return_value=fake_pdf),
    ):
        result = mod.run("doss-1", "2026-05", dry_run=True)

    assert result["statut"] == "generée"
    # Storage.upload ne doit pas être appelé
    mock_sb.storage.from_.return_value.upload.assert_not_called()


def test_run_retourne_lignes_ca3(monkeypatch):
    """Le résultat doit inclure les lignes CA3 calculées."""
    from apps.jmpartners.agents import tva_declarator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    mock_sb.storage = _make_storage()

    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_ca3", return_value=fake_pdf),
    ):
        result = mod.run("doss-1", "2026-05")

    assert "lignes_ca3" in result
    assert "tva_collectee" in result["lignes_ca3"]
    assert "solde" in result["lignes_ca3"]

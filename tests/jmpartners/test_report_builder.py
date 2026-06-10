"""TDD — report_builder : rapports PDF mensuels par dossier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ── Helpers / fixtures ────────────────────────────────────────────────────────

def _ecritures(mois: str = "2026-05"):
    """Écritures d'un mois normal."""
    return [
        {"compte": "7070", "libelle": "Vente A", "date": f"{mois}-05", "credit": 8000.0, "debit": None},
        {"compte": "7070", "libelle": "Vente B", "date": f"{mois}-20", "credit": 4000.0, "debit": None},
        {"compte": "6070", "libelle": "Achat fournitures", "date": f"{mois}-10", "credit": None, "debit": 2000.0},
        {"compte": "6110", "libelle": "Loyer", "date": f"{mois}-01", "credit": None, "debit": 1500.0},
        {"compte": "512",  "libelle": "Banque", "date": f"{mois}-31", "credit": 1000.0, "debit": None},
        {"compte": "44571","libelle": "TVA collectée", "date": f"{mois}-31", "credit": 2400.0, "debit": None},
    ]


def _ecritures_zero():
    """Aucune écriture dans le mois."""
    return []


def _ecritures_solde_negatif():
    """Charges > produits → résultat négatif."""
    return [
        {"compte": "7070", "libelle": "Vente", "date": "2026-05-05", "credit": 1000.0, "debit": None},
        {"compte": "6070", "libelle": "Achat", "date": "2026-05-10", "credit": None, "debit": 5000.0},
    ]


def _dossier(dossier_id="doss-1", raison_sociale="Dupont SARL", email="contact@dupont.fr"):
    return {
        "id": dossier_id,
        "raison_sociale": raison_sociale,
        "responsable_email": email,
        "cabinet_id": "jmpartners",
    }


def _make_sb(dossier=None, ecritures=None):
    sb = MagicMock()
    dossier = dossier if dossier is not None else _dossier()
    ecritures = ecritures if ecritures is not None else _ecritures()
    _cache: dict = {}

    def _table(name):
        if name in _cache:
            return _cache[name]
        t = MagicMock()
        if name == "dossiers":
            t.select.return_value.eq.return_value.single.return_value.execute.return_value.data = dossier
        elif name == "ecritures":
            t.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = ecritures
        elif name == "journaux":
            t.insert.return_value.execute.return_value.data = [{"id": "jnl-1"}]
        _cache[name] = t
        return t

    sb.table = MagicMock(side_effect=_table)
    sb._cache = _cache
    sb.storage = MagicMock()
    sb.storage.from_.return_value.upload.return_value = MagicMock()
    sb.storage.from_.return_value.get_public_url.return_value = "https://storage.supabase.co/rapport.pdf"
    return sb


# ── Tests : calcul des soldes ─────────────────────────────────────────────────

def test_compute_soldes_produits_70x():
    """Les crédits des comptes 70x sont comptés dans les produits."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    assert abs(soldes["produits"] - 12000.0) < 0.01


def test_compute_soldes_charges_6x():
    """Les débits des comptes 6x sont comptés dans les charges."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    assert abs(soldes["charges"] - 3500.0) < 0.01


def test_compute_soldes_resultat_net():
    """Résultat net = produits - charges."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    expected = 12000.0 - 3500.0
    assert abs(soldes["resultat_net"] - expected) < 0.01


def test_compute_soldes_zero_sans_ecritures():
    """Sans écritures, tous les soldes sont zéro."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures_zero())

    assert soldes["produits"] == 0.0
    assert soldes["charges"] == 0.0
    assert soldes["resultat_net"] == 0.0


def test_compute_soldes_negatif():
    """Charges > produits → résultat négatif."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures_solde_negatif())

    assert soldes["resultat_net"] < 0
    assert abs(soldes["resultat_net"] - (-4000.0)) < 0.01


def test_compute_soldes_par_compte():
    """Les soldes par compte (actif/passif) sont calculés."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    assert "par_compte" in soldes
    assert "512" in soldes["par_compte"]  # Banque
    assert "7070" in soldes["par_compte"]  # Ventes


def test_compute_soldes_structure_complete():
    """Les soldes doivent contenir les champs requis."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    for field in ("produits", "charges", "resultat_net", "par_compte", "nb_ecritures"):
        assert field in soldes, f"Champ manquant : {field}"


def test_compute_soldes_nb_ecritures():
    """nb_ecritures reflète le nombre d'écritures traitées."""
    from apps.jmpartners.agents.report_builder import _compute_soldes

    soldes = _compute_soldes(_ecritures())

    assert soldes["nb_ecritures"] == len(_ecritures())


# ── Tests : génération PDF ────────────────────────────────────────────────────

def test_generate_pdf_retourne_bytes():
    """La génération PDF retourne des bytes non vides."""
    from apps.jmpartners.agents.report_builder import _generate_pdf_rapport

    soldes = {
        "produits": 12000.0,
        "charges": 3500.0,
        "resultat_net": 8500.0,
        "par_compte": {"7070": 12000.0, "6070": -2000.0},
        "nb_ecritures": 6,
    }

    try:
        pdf_bytes = _generate_pdf_rapport(
            raison_sociale="Dupont SARL",
            periode="2026-05",
            soldes=soldes,
            ecritures=_ecritures(),
        )
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"
    except ImportError:
        pytest.skip("reportlab non installé")


# ── Tests : flux run() ────────────────────────────────────────────────────────

def test_run_retourne_statut_ok(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_USER", "user@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport"),
    ):
        result = mod.run("doss-1", "2026-05")

    assert result["statut"] == "ok"
    assert result["erreur"] is None


def test_run_envoie_email_avec_pdf(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_USER", "user@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"
    mock_send = MagicMock()

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport", mock_send),
    ):
        mod.run("doss-1", "2026-05")

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    assert call_kwargs[0][0] == "contact@dupont.fr"  # destinataire
    assert fake_pdf in call_kwargs[0]  # PDF en pièce jointe


def test_run_stocke_dans_storage(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport"),
    ):
        result = mod.run("doss-1", "2026-05")

    mock_sb.storage.from_.assert_called()
    assert result["pdf_url"] is not None


def test_run_logue_dans_journaux(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport"),
    ):
        mod.run("doss-1", "2026-05")

    table_calls = [c[0][0] for c in mock_sb.table.call_args_list]
    assert "journaux" in table_calls


def test_run_erreur_si_dossier_introuvable(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doss-inexistant", "2026-05")

    assert result["statut"] == "erreur"
    assert "introuvable" in (result["erreur"] or "").lower()


def test_run_dry_run_ne_persiste_pas(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"
    mock_send = MagicMock()

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport", mock_send),
    ):
        result = mod.run("doss-1", "2026-05", dry_run=True)

    assert result["statut"] == "ok"
    # Aucun upload ni email en dry_run
    mock_sb.storage.from_.return_value.upload.assert_not_called()
    mock_send.assert_not_called()


def test_run_retourne_soldes_dans_result(monkeypatch):
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb()
    fake_pdf = b"%PDF-1.4 fake"

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport"),
    ):
        result = mod.run("doss-1", "2026-05")

    assert "soldes" in result
    assert "produits" in result["soldes"]
    assert "charges" in result["soldes"]
    assert "resultat_net" in result["soldes"]


def test_run_zero_mouvement_ne_crash_pas(monkeypatch):
    """Aucune écriture dans le mois → rapport avec zéros, pas d'erreur."""
    from apps.jmpartners.agents import report_builder as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = _make_sb(ecritures=[])
    fake_pdf = b"%PDF-1.4 fake"

    with (
        patch.object(mod, "get_supabase_client", return_value=mock_sb),
        patch.object(mod, "_generate_pdf_rapport", return_value=fake_pdf),
        patch.object(mod, "_send_email_rapport"),
    ):
        result = mod.run("doss-1", "2026-05")

    assert result["statut"] == "ok"
    assert result["soldes"]["produits"] == 0.0
    assert result["soldes"]["resultat_net"] == 0.0

"""TDD — ecriture_generator : génération d'écritures comptables depuis analyse_ia."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import apps.jmpartners.agents.ecriture_generator as eg_mod

# ── Données d'entrée type ─────────────────────────────────────────────────────

def _analyse_facture_achat(montant_ht=1000.0, montant_tva=200.0, tiers="Fournisseur SAS"):
    return {
        "type_document": "facture_achat",
        "montants": [{"libelle": "Total TTC", "montant": montant_ht + montant_tva, "devise": "EUR"}],
        "dates": ["2026-05-15"],
        "tiers": [tiers],
        "references": ["FA-2026-0542"],
        "tva": {"taux": 20, "montant_ht": montant_ht, "montant_tva": montant_tva,
                "montant_ttc": montant_ht + montant_tva},
        "resume": f"Facture {tiers}",
    }


def _analyse_facture_vente(montant_ht=2000.0, montant_tva=400.0, tiers="Client SA"):
    return {
        "type_document": "facture_vente",
        "montants": [{"libelle": "Total TTC", "montant": montant_ht + montant_tva, "devise": "EUR"}],
        "dates": ["2026-05-20"],
        "tiers": [tiers],
        "references": ["FV-2026-0123"],
        "tva": {"taux": 20, "montant_ht": montant_ht, "montant_tva": montant_tva,
                "montant_ttc": montant_ht + montant_tva},
        "resume": f"Vente {tiers}",
    }


def _analyse_releve_bancaire(solde=15230.50):
    return {
        "type_document": "releve_bancaire",
        "montants": [{"libelle": "Solde", "montant": solde, "devise": "EUR"}],
        "dates": ["2026-05-01", "2026-05-31"],
        "tiers": ["BNP Paribas"],
        "references": ["IBAN FR76 1234"],
        "tva": None,
        "resume": "Relevé bancaire",
    }


def _analyse_facture_vente_multi_tva():
    """Facture vente avec deux lignes de TVA (10% et 20%)."""
    return {
        "type_document": "facture_vente",
        "montants": [
            {"libelle": "HT services", "montant": 1000.0, "devise": "EUR"},
            {"libelle": "HT marchandises", "montant": 500.0, "devise": "EUR"},
            {"libelle": "TVA 20% services", "montant": 200.0, "devise": "EUR"},
            {"libelle": "TVA 10% marchandises", "montant": 50.0, "devise": "EUR"},
            {"libelle": "Total TTC", "montant": 1750.0, "devise": "EUR"},
        ],
        "dates": ["2026-05-22"],
        "tiers": ["Client Multi SAS"],
        "references": ["FV-2026-0999"],
        "tva": {"taux": None, "montant_ht": 1500.0, "montant_tva": 250.0, "montant_ttc": 1750.0},
        "resume": "Facture multi-TVA",
    }


def _make_supabase_with_doc(analyse: dict, document_id: str = "doc-1", dossier_id: str = "doss-1"):
    sb = MagicMock()
    doc_row = {
        "id": document_id,
        "dossier_id": dossier_id,
        "type_document": analyse["type_document"],
        "analyse_ia": analyse,
    }
    sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = doc_row
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "ecr-new"}]
    return sb


# ── Tests : mappage des comptes ───────────────────────────────────────────────

def test_facture_achat_mappe_compte_401_60x_44566():
    """Facture achat : crédit 401, débit 60x (charges), débit 44566 (TVA déductible)."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(_analyse_facture_achat(), "2026-05-15")

    assert any(e["compte_credit"] == "401" for e in ecritures)
    assert any(e["compte_debit"].startswith("60") for e in ecritures)
    assert any(e["compte_debit"] == "44566" for e in ecritures)


def test_facture_achat_balance_zero():
    """Chaque mouvement est équilibré — somme des montants = TTC."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(_analyse_facture_achat(1000.0, 200.0), "2026-05-15")

    assert ecritures, "Aucune écriture générée"
    total = sum(e["montant"] for e in ecritures)
    assert abs(total - 1200.0) < 0.01, f"Somme montants ≠ TTC : {total}"


def test_facture_vente_mappe_compte_411_70x_44571():
    """Facture vente : débit 411, crédit 70x (produits), crédit 44571 (TVA collectée)."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_vente

    ecritures = _build_ecritures_facture_vente(_analyse_facture_vente(), "2026-05-20")

    assert any(e["compte_debit"] == "411" for e in ecritures)
    assert any(e["compte_credit"].startswith("70") for e in ecritures)
    assert any(e["compte_credit"] == "44571" for e in ecritures)


def test_facture_vente_balance_zero():
    """Chaque mouvement est équilibré — somme des montants = TTC."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_vente

    ecritures = _build_ecritures_facture_vente(_analyse_facture_vente(2000.0, 400.0), "2026-05-20")

    assert ecritures
    total = sum(e["montant"] for e in ecritures)
    assert abs(total - 2400.0) < 0.01


def test_releve_bancaire_mappe_compte_512():
    """Relevé bancaire : utilise le compte 512 (banque) en compte_debit."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_releve

    ecritures = _build_ecritures_releve(_analyse_releve_bancaire(), "2026-05-31")

    assert any(e["compte_debit"] == "512" for e in ecritures)


def test_facture_achat_sans_tva_pas_de_44566():
    """Facture achat sans TVA : pas d'écriture 44566."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    analyse = _analyse_facture_achat(1000.0, 0.0)
    analyse["tva"] = None

    ecritures = _build_ecritures_facture_achat(analyse, "2026-05-15")

    assert not any(e.get("compte_debit") == "44566" for e in ecritures)


def test_facture_vente_multi_tva_balance_zero():
    """Facture vente multi-TVA : somme des montants = TTC."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_vente

    analyse = _analyse_facture_vente_multi_tva()
    ecritures = _build_ecritures_facture_vente(analyse, "2026-05-22")

    assert ecritures
    total = sum(e["montant"] for e in ecritures)
    assert abs(total - 1750.0) < 0.01


# ── Tests : structure des écritures ───────────────────────────────────────────

def test_ecriture_has_required_fields():
    """Chaque écriture doit avoir compte_debit, compte_credit, montant, libelle, date_ecriture."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(_analyse_facture_achat(), "2026-05-15")

    for e in ecritures:
        assert "compte_debit" in e and e["compte_debit"]
        assert "compte_credit" in e and e["compte_credit"]
        assert "montant" in e and e["montant"] > 0
        assert "libelle" in e
        assert "date_ecriture" in e


def test_ecriture_tiers_in_libelle():
    """Le tiers doit apparaître dans le libellé du mouvement principal."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(
        _analyse_facture_achat(tiers="Fournisseur Test SARL"), "2026-05-15"
    )

    # Le mouvement charge (6070/401) doit mentionner le tiers
    e_main = next(e for e in ecritures if e["compte_credit"] == "401" and e["compte_debit"].startswith("60"))
    assert "Fournisseur Test SARL" in e_main["libelle"]


def test_ecriture_reference_in_libelle():
    """La référence (numéro de facture) doit être dans au moins un libellé."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(_analyse_facture_achat(), "2026-05-15")

    libelles = " ".join(e["libelle"] for e in ecritures)
    assert "FA-2026-0542" in libelles


# ── Tests : flux run() complet ────────────────────────────────────────────────

def test_run_insere_ecritures_dans_supabase(monkeypatch):
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_facture_achat()
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-1")

    assert result["statut"] == "ok"
    assert result["erreur"] is None
    mock_sb.table.assert_any_call("ecritures")
    # insert appelé 2× : une fois pour ecritures, une fois pour journaux
    assert mock_sb.table.return_value.insert.call_count >= 1


def test_run_insere_aussi_dans_journaux(monkeypatch):
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_facture_vente()
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        mod.run("doc-1")

    table_calls = [c[0][0] for c in mock_sb.table.call_args_list]
    assert "journaux" in table_calls


def test_run_retourne_ecritures_generees(monkeypatch):
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_facture_achat()
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-1")

    assert isinstance(result["ecritures"], list)
    assert len(result["ecritures"]) >= 2  # au moins débit + crédit


def test_run_erreur_si_document_sans_analyse_ia(monkeypatch):
    """run() retourne une erreur si le document n'a pas d'analyse_ia."""
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "doc-x", "dossier_id": "doss-1", "type_document": "facture_achat", "analyse_ia": None
    }

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-x")

    assert result["statut"] == "erreur"
    assert "analyse_ia" in (result["erreur"] or "").lower()


def test_run_erreur_si_type_document_non_supporte(monkeypatch):
    """run() retourne une erreur pour un type de document sans mappage comptable."""
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = {"type_document": "contrat_travail", "montants": [], "dates": [],
               "tiers": [], "references": [], "tva": None, "resume": "CDI"}
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-ct")

    assert result["statut"] == "non_supporte"


def test_run_dry_run_ne_persiste_pas(monkeypatch):
    """run() avec dry_run=True calcule mais n'insère rien."""
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_facture_achat()
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-1", dry_run=True)

    assert result["statut"] == "ok"
    mock_sb.table.return_value.insert.assert_not_called()


# ── Tests : cas limites comptables ───────────────────────────────────────────

def test_facture_achat_montant_ttc_correct():
    """La somme des montants côté 401 doit être égale au TTC de la facture."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_achat

    ecritures = _build_ecritures_facture_achat(_analyse_facture_achat(1000.0, 200.0), "2026-05-15")

    total_401 = sum(e["montant"] for e in ecritures if e["compte_credit"] == "401")
    assert abs(total_401 - 1200.0) < 0.01


def test_facture_vente_montant_411_correct():
    """La somme des montants côté 411 doit être égale au TTC de la facture."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_facture_vente

    ecritures = _build_ecritures_facture_vente(_analyse_facture_vente(2000.0, 400.0), "2026-05-20")

    total_411 = sum(e["montant"] for e in ecritures if e["compte_debit"] == "411")
    assert abs(total_411 - 2400.0) < 0.01


def test_releve_bancaire_balance_zero():
    """Le relevé bancaire génère un mouvement 512/580 pour le montant du solde."""
    from apps.jmpartners.agents.ecriture_generator import _build_ecritures_releve

    ecritures = _build_ecritures_releve(_analyse_releve_bancaire(15230.50), "2026-05-31")

    assert ecritures, "Aucune écriture générée"
    assert ecritures[0]["compte_debit"] == "512"
    assert ecritures[0]["compte_credit"] == "580"
    assert abs(ecritures[0]["montant"] - 15230.50) < 0.01


def test_run_retourne_result_avec_bonne_structure(monkeypatch):
    """EcritureGeneratorResult doit contenir document_id, ecritures, statut, erreur."""
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_releve_bancaire()
    mock_sb = _make_supabase_with_doc(analyse)

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-rb")

    for field in ("document_id", "ecritures", "statut", "erreur"):
        assert field in result, f"Champ manquant : {field}"
    assert result["document_id"] == "doc-rb"


# ── Lovable contract fields ────────────────────────────────────────────────────

def test_journal_facture_achat():
    ecritures = eg_mod._build_ecritures_facture_achat(_analyse_facture_achat(), "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", _analyse_facture_achat(), 1200.0)
    assert all(e["journal"] == "ACH" for e in enriched)


def test_journal_facture_vente():
    ecritures = eg_mod._build_ecritures_facture_vente(_analyse_facture_vente(), "2026-05-20")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_vente", _analyse_facture_vente(), 2400.0)
    assert all(e["journal"] == "VEN" for e in enriched)


def test_journal_releve_bancaire():
    ecritures = eg_mod._build_ecritures_releve(_analyse_releve_bancaire(), "2026-05-31")
    enriched = eg_mod._enrich_ecritures(ecritures, "releve_bancaire", _analyse_releve_bancaire(), 15230.50)
    assert all(e["journal"] == "BQ" for e in enriched)


def test_reference_propagated_from_analyse():
    analyse = _analyse_facture_achat()
    ecritures = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", analyse, 1200.0)
    assert all(e["reference"] == "FA-2026-0542" for e in enriched)


def test_montant_ttc_set_on_entries():
    analyse = _analyse_facture_achat()
    ecritures = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", analyse, 1200.0)
    assert all(e["montant_ttc"] == 1200.0 for e in enriched)


def test_source_ia_on_every_entry():
    analyse = _analyse_facture_vente()
    ecritures = eg_mod._build_ecritures_facture_vente(analyse, "2026-05-20")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_vente", analyse, 2400.0)
    assert all(e["source"] == "ia" for e in enriched)


def test_score_confiance_high_sets_statut_valide():
    """All 5 key fields filled → score 1.0 → statut 'valide'."""
    analyse = _analyse_facture_achat()  # has tiers, montants, dates, references, tva
    ecritures = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", analyse, 1200.0)
    assert all(e["score_confiance"] >= 0.85 for e in enriched)
    assert all(e["statut"] == "valide" for e in enriched)


def test_score_confiance_low_sets_statut_a_valider():
    """Only 2 fields filled → score < 0.85 → statut 'a_valider'."""
    analyse = {
        "type_document": "facture_achat",
        "montants": [{"libelle": "Total", "montant": 100.0, "devise": "EUR"}],
        "dates": ["2026-05-15"],
        "tiers": None,
        "references": None,
        "tva": None,
    }
    ecritures = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", analyse, 100.0)
    assert all(e["score_confiance"] < 0.85 for e in enriched)
    assert all(e["statut"] == "a_valider" for e in enriched)


def test_debit_credit_balance_still_holds():
    """Enrichment préserve le schéma compte_debit/compte_credit/montant et la somme = TTC."""
    analyse = _analyse_facture_achat(montant_ht=1000.0, montant_tva=200.0)
    ecritures = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")
    enriched = eg_mod._enrich_ecritures(ecritures, "facture_achat", analyse, 1200.0)
    assert all("compte_debit" in e and "compte_credit" in e for e in enriched)
    assert all(e["montant"] > 0 for e in enriched)
    assert abs(sum(e["montant"] for e in enriched) - 1200.0) < 0.01


# ── Tests TDD : contrat schéma table ecritures (à faire passer) ──────────────

_SCHEMA_ECRITURES = frozenset({
    "compte_debit", "compte_credit", "montant", "date_ecriture",
    "libelle", "journal", "reference", "montant_ttc", "source",
    "score_confiance", "statut", "dossier_id", "piece_justificative_id",
})


def test_rows_conformes_schema():
    """Les clés des rows produites pour l'insert sont ⊆ du schéma table ecritures."""
    analyse = _analyse_facture_achat(montant_ht=1000.0, montant_tva=200.0)
    legs = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")

    rows = eg_mod._to_table_rows(
        legs=legs,
        date="2026-05-15",
        journal="ACH",
        reference="FA-2026-0542",
        score=1.0,
        statut="valide",
        montant_ttc=1200.0,
    )

    assert rows, "_to_table_rows ne doit pas retourner une liste vide"
    for row in rows:
        assert "compte_debit" in row and row["compte_debit"], "compte_debit manquant ou vide"
        assert "compte_credit" in row and row["compte_credit"], "compte_credit manquant ou vide"
        assert "montant" in row and row["montant"] > 0, "montant manquant ou nul"
        assert "date_ecriture" in row, "date_ecriture manquant"
        unknown = set(row.keys()) - _SCHEMA_ECRITURES
        assert not unknown, f"Clés hors-schéma table ecritures : {unknown}"


def test_equilibre_achat():
    """Facture achat HT 1000 / TVA 200 → 2 mouvements, 401 en compte_credit, somme montants = TTC."""
    analyse = _analyse_facture_achat(montant_ht=1000.0, montant_tva=200.0)
    legs = eg_mod._build_ecritures_facture_achat(analyse, "2026-05-15")

    rows = eg_mod._to_table_rows(
        legs=legs,
        date="2026-05-15",
        journal="ACH",
        reference="FA-2026-0542",
        score=1.0,
        statut="valide",
        montant_ttc=1200.0,
    )

    assert len(rows) == 2, f"Attendu 2 mouvements (6070/401 + 44566/401), obtenu {len(rows)}"
    assert all(r["compte_credit"] == "401" for r in rows), (
        f"401 doit être compte_credit sur tous les mouvements, obtenu : {[r['compte_credit'] for r in rows]}"
    )

    comptes_debit = {r["compte_debit"] for r in rows}
    assert comptes_debit == {"6070", "44566"}, (
        f"Attendu {{6070, 44566}} en compte_debit, obtenu {comptes_debit}"
    )

    montant_ht_row = next(r["montant"] for r in rows if r["compte_debit"] == "6070")
    montant_tva_row = next(r["montant"] for r in rows if r["compte_debit"] == "44566")
    assert abs(montant_ht_row - 1000.0) < 0.01, f"Mouvement 6070/401 : attendu 1000, obtenu {montant_ht_row}"
    assert abs(montant_tva_row - 200.0) < 0.01, f"Mouvement 44566/401 : attendu 200, obtenu {montant_tva_row}"
    assert abs(sum(r["montant"] for r in rows) - 1200.0) < 0.01, (
        f"Somme montants ≠ TTC (1200) : {sum(r['montant'] for r in rows)}"
    )


def test_equilibre_vente():
    """Facture vente HT 2000 / TVA 400 → 2 mouvements, 411 en compte_debit, somme montants = TTC."""
    analyse = _analyse_facture_vente(montant_ht=2000.0, montant_tva=400.0)
    legs = eg_mod._build_ecritures_facture_vente(analyse, "2026-05-20")

    rows = eg_mod._to_table_rows(
        legs=legs,
        date="2026-05-20",
        journal="VEN",
        reference="FV-2026-0123",
        score=1.0,
        statut="valide",
        montant_ttc=2400.0,
    )

    assert len(rows) == 2, f"Attendu 2 mouvements (411/7070 + 411/44571), obtenu {len(rows)}"
    assert all(r["compte_debit"] == "411" for r in rows), (
        f"411 doit être compte_debit sur tous les mouvements, obtenu : {[r['compte_debit'] for r in rows]}"
    )

    comptes_credit = {r["compte_credit"] for r in rows}
    assert comptes_credit == {"7070", "44571"}, (
        f"Attendu {{7070, 44571}} en compte_credit, obtenu {comptes_credit}"
    )

    montant_ht_row = next(r["montant"] for r in rows if r["compte_credit"] == "7070")
    montant_tva_row = next(r["montant"] for r in rows if r["compte_credit"] == "44571")
    assert abs(montant_ht_row - 2000.0) < 0.01, f"Mouvement 411/7070 : attendu 2000, obtenu {montant_ht_row}"
    assert abs(montant_tva_row - 400.0) < 0.01, f"Mouvement 411/44571 : attendu 400, obtenu {montant_tva_row}"
    assert abs(sum(r["montant"] for r in rows) - 2400.0) < 0.01, (
        f"Somme montants ≠ TTC (2400) : {sum(r['montant'] for r in rows)}"
    )


def test_insert_echec_remonte_erreur(monkeypatch):
    """Si supabase.insert lève une exception, run() doit retourner statut='erreur', pas 'ok'."""
    from apps.jmpartners.agents import ecriture_generator as mod

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    analyse = _analyse_facture_achat()
    mock_sb = _make_supabase_with_doc(analyse)
    mock_sb.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "insert or update on table 'ecritures' violates foreign key constraint"
    )

    with patch.object(mod, "get_supabase_client", return_value=mock_sb):
        result = mod.run("doc-1")

    assert result["statut"] == "erreur", (
        f"run() a retourné statut='{result['statut']}' au lieu de 'erreur' "
        f"— l'exception d'insert ne doit plus être avalée silencieusement"
    )
    assert result["erreur"] is not None, "Le champ 'erreur' doit être renseigné en cas d'échec d'insert"

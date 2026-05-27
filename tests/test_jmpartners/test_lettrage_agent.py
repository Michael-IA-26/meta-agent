"""Tests pour apps.jmpartners.agents.lettrage_agent."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from apps.jmpartners.agents.lettrage_agent import LettrageAgent, LettragePaire


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _facture(id_: str, tiers: str, montant: float, date_: str = "2026-05-01") -> dict:
    return {"id": id_, "tiers": tiers, "montant_ttc": montant, "date_ecriture": date_, "compte": "401000"}


def _reglement(id_: str, tiers: str, montant: float, date_: str = "2026-05-01", libelle: str = "") -> dict:
    return {"id": id_, "tiers": tiers, "montant_ttc": montant, "date_ecriture": date_, "source": "regate", "libelle": libelle}


def _mock_supabase_vide() -> MagicMock:
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.like.return_value.eq.return_value.execute.return_value.count = 0
    mock.table.return_value.select.return_value.like.return_value.eq.return_value.execute.return_value.data = []
    return mock


# ─── _rapprocher_exact ────────────────────────────────────────────────────────


def test_rapprocher_exact_montant_identique():
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00)]
    reglements = [_reglement("r1", "Fournisseur A", 1200.00)]
    paires = agent._rapprocher_exact(factures, reglements)
    assert len(paires) == 1
    assert paires[0]["ecriture_id"] == "f1"
    assert paires[0]["reglement_id"] == "r1"
    assert paires[0]["confiance"] == 1.0
    assert paires[0]["methode"] == "exact"


def test_rapprocher_exact_montant_different():
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00)]
    reglements = [_reglement("r1", "Fournisseur A", 900.00)]
    paires = agent._rapprocher_exact(factures, reglements)
    assert len(paires) == 0


def test_rapprocher_exact_meme_montant_tiers_different():
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00)]
    reglements = [_reglement("r1", "Fournisseur B", 1200.00)]
    paires = agent._rapprocher_exact(factures, reglements)
    assert len(paires) == 0


def test_rapprocher_exact_reglement_utilise_une_seule_fois():
    """Un règlement ne peut matcher qu'une seule facture."""
    agent = LettrageAgent()
    factures = [
        _facture("f1", "Fournisseur A", 1200.00),
        _facture("f2", "Fournisseur A", 1200.00),
    ]
    reglements = [_reglement("r1", "Fournisseur A", 1200.00)]
    paires = agent._rapprocher_exact(factures, reglements)
    assert len(paires) == 1


# ─── _rapprocher_approche ─────────────────────────────────────────────────────


def test_rapprocher_approche_tolerance_centime():
    """Écart 0.005€ + même tiers + date ±1j → paire, confiance=0.8."""
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00, "2026-05-01")]
    reglements = [_reglement("r1", "Fournisseur A", 1200.005, "2026-05-02")]
    paires = agent._rapprocher_approche(factures, reglements)
    assert len(paires) == 1
    assert paires[0]["confiance"] == 0.8
    assert paires[0]["methode"] == "approche"


def test_rapprocher_approche_ecart_trop_grand():
    """Écart > 0.01€ → aucune paire approchée."""
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00, "2026-05-01")]
    reglements = [_reglement("r1", "Fournisseur A", 1200.02, "2026-05-01")]
    paires = agent._rapprocher_approche(factures, reglements)
    assert len(paires) == 0


def test_rapprocher_approche_date_trop_eloignee():
    """Écart de date > 3 jours → aucune paire."""
    agent = LettrageAgent()
    factures = [_facture("f1", "Fournisseur A", 1200.00, "2026-05-01")]
    reglements = [_reglement("r1", "Fournisseur A", 1200.00, "2026-05-05")]
    paires = agent._rapprocher_approche(factures, reglements)
    assert len(paires) == 0


# ─── _appliquer_apprentissage ─────────────────────────────────────────────────


def test_appliquer_apprentissage_libelle_connu():
    """Libellé bancaire mémorisé → rattachement, confiance=0.9."""
    agent = LettrageAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"libelle": "VIR SEPA LOYER MAI", "tiers": "Propriétaire", "facture_id": "f-loyer", "montant": 800.0}
    ]
    reglements = [_reglement("r1", "Propriétaire", 800.0, libelle="VIR SEPA LOYER MAI")]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        paires = agent._appliquer_apprentissage(reglements)

    assert len(paires) == 1
    assert paires[0]["confiance"] == 0.9
    assert paires[0]["methode"] == "apprentissage"
    assert paires[0]["reglement_id"] == "r1"


def test_appliquer_apprentissage_libelle_inconnu():
    """Libellé inconnu → aucun rattachement."""
    agent = LettrageAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []
    reglements = [_reglement("r1", "X", 100.0, libelle="LIBELLE INCONNU")]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        paires = agent._appliquer_apprentissage(reglements)

    assert len(paires) == 0


# ─── _compter_471 ─────────────────────────────────────────────────────────────


def test_compter_471_vieux_de_30j():
    """Règlements 471 non lettrés > 30j → comptés."""
    agent = LettrageAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.like.return_value.eq.return_value.lt.return_value.execute.return_value.count = 3

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        count = agent._compter_471(None)

    assert count == 3


def test_compter_471_recent_ignore():
    """Règlement 471 récent → count=0."""
    agent = LettrageAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.like.return_value.eq.return_value.lt.return_value.execute.return_value.count = 0

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        count = agent._compter_471(None)

    assert count == 0


# ─── _lettrer_ecritures ───────────────────────────────────────────────────────


def test_lettrer_ecritures_code_sequentiel():
    """Première paire → lettre='A', deuxième → 'B'."""
    agent = LettrageAgent()
    mock_sb = MagicMock()

    paires = [
        LettragePaire(
            ecriture_id="f1", reglement_id="r1", montant=100.0, tiers="A",
            date_rapprochement="2026-05-01", methode="exact", confiance=1.0
        ),
        LettragePaire(
            ecriture_id="f2", reglement_id="r2", montant=200.0, tiers="B",
            date_rapprochement="2026-05-01", methode="exact", confiance=1.0
        ),
    ]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        agent._lettrer_ecritures(paires)

    update_calls = mock_sb.table.return_value.update.call_args_list
    lettres_utilisees = [c[0][0]["lettre"] for c in update_calls]
    assert "A" in lettres_utilisees
    assert "B" in lettres_utilisees


# ─── run() ────────────────────────────────────────────────────────────────────


def test_run_dossier_specifique():
    """run(dossier_id='xxx') → seul ce dossier traité, pas d'appel table dossiers."""
    agent = LettrageAgent()
    mock_sb = _mock_supabase_vide()

    # Pour dossier_id spécifique, on ne lit pas la table dossiers
    # ecritures retourne vide → pas de paires
    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run(dossier_id="dos-1")

    assert result["paires_trouvees"] == 0
    assert result["erreurs"] == []
    # Vérifie qu'on n'a PAS cherché dans la table dossiers
    dossiers_calls = [
        c for c in mock_sb.table.call_args_list
        if c[0][0] == "dossiers"
    ]
    assert len(dossiers_calls) == 0


def test_run_sans_ecritures():
    """Aucune écriture → résultat vide, pas d'erreur."""
    agent = LettrageAgent()
    mock_sb = MagicMock()
    # Dossiers actifs
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # Comptage 471
    mock_sb.table.return_value.select.return_value.like.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value.count = 0

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["paires_trouvees"] == 0
    assert result["montant_total_lettre"] == 0.0
    assert result["erreurs"] == []


def test_run_erreur_supabase():
    """Erreur Supabase → loggée, agent continue, retourne résultat vide."""
    agent = LettrageAgent()

    with patch.object(agent, "_get_supabase", side_effect=Exception("connexion perdue")):
        result = agent.run()

    assert result["paires_trouvees"] == 0
    assert len(result["erreurs"]) == 1
    assert "connexion perdue" in result["erreurs"][0]

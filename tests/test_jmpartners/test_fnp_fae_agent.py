"""Tests pour apps.jmpartners.agents.fnp_fae_agent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.fnp_fae_agent import FNPFAEAgent, ProvisionFNP


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mock_sb_vide() -> MagicMock:
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.like.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    return mock


def _provision_a_valider(dossier_id: str = "dos-1", compte: str = "408000") -> ProvisionFNP:
    return ProvisionFNP(
        dossier_id=dossier_id,
        fournisseur="Fournisseur Test",
        montant_estime=1000.0,
        compte_charge="601000",
        compte_provision=compte,
        description="FNP — test",
        statut="a_valider_fnp",
    )


# ─── Garde-fou mois ───────────────────────────────────────────────────────────


def test_run_hors_decembre_retourne_hors_periode():
    """Mois 1-11 → periode='hors_periode', 0 provisions, aucun appel Supabase."""
    agent = FNPFAEAgent()
    result = agent.run(force_mois=6)
    assert result["periode"] == "hors_periode"
    assert result["fnp_detectees"] == 0
    assert result["fae_detectees"] == 0
    assert result["provisions"] == []


def test_run_hors_decembre_mois_1():
    agent = FNPFAEAgent()
    result = agent.run(force_mois=1)
    assert result["periode"] == "hors_periode"


def test_run_hors_decembre_mois_11():
    agent = FNPFAEAgent()
    result = agent.run(force_mois=11)
    assert result["periode"] == "hors_periode"


def test_run_hors_periode_pas_appel_supabase():
    """Hors décembre → aucun appel Supabase."""
    agent = FNPFAEAgent()
    with patch.object(agent, "_get_supabase") as mock_get:
        agent.run(force_mois=5)
    mock_get.assert_not_called()


def test_run_force_mois_decembre_traite():
    """force_mois=12 → traitement déclenché."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run(force_mois=12)

    assert result["periode"] == "decembre"


# ─── Détection FNP ────────────────────────────────────────────────────────────


def test_detecter_fnp_engagement_sans_facture():
    """Compte 408xxx ouvert sans facture → FNP détectée."""
    agent = FNPFAEAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.like.return_value.eq.return_value.execute.return_value.data = [
        {"id": "e1", "tiers": "EDF", "montant_ttc": 500.0, "compte": "408100", "libelle": "Electricité"}
    ]
    # Estimation montant : retourne 0 (pas d'historique)
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.like.return_value.limit.return_value.order.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        fnp_list = agent._detecter_fnp("dos-1")

    assert len(fnp_list) == 1
    assert fnp_list[0]["fournisseur"] == "EDF"
    assert fnp_list[0]["compte_provision"].startswith("408")
    assert fnp_list[0]["statut"] == "a_valider_fnp"


def test_detecter_fnp_facture_presente():
    """Compte 408xxx soldé (aucune ligne ouverte) → pas de FNP."""
    agent = FNPFAEAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.like.return_value.eq.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        fnp_list = agent._detecter_fnp("dos-1")

    assert len(fnp_list) == 0


# ─── Détection FAE ────────────────────────────────────────────────────────────


def test_detecter_fae_prestation_sans_facture():
    """Compte 418xxx ouvert → FAE détectée."""
    agent = FNPFAEAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.like.return_value.eq.return_value.execute.return_value.data = [
        {"id": "e2", "tiers": "Client XYZ", "montant_ttc": 2000.0, "compte": "418000", "libelle": "Prestation déc"}
    ]
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.like.return_value.limit.return_value.order.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        fae_list = agent._detecter_fae("dos-1")

    assert len(fae_list) == 1
    assert fae_list[0]["fournisseur"] == "Client XYZ"
    assert fae_list[0]["compte_provision"].startswith("418")
    assert fae_list[0]["statut"] == "a_valider_fnp"


# ─── Estimation montant ───────────────────────────────────────────────────────


def test_estimer_montant_avec_historique():
    """3 mois d'historique → moyenne calculée."""
    agent = FNPFAEAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.like.return_value.limit.return_value.order.return_value.execute.return_value.data = [
        {"montant_ttc": 900.0},
        {"montant_ttc": 1000.0},
        {"montant_ttc": 1100.0},
    ]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        montant = agent._estimer_montant("EDF", "408100", "dos-1")

    assert montant == 1000.0


def test_estimer_montant_sans_historique():
    """Aucun historique → 0.0, pas d'erreur."""
    agent = FNPFAEAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.like.return_value.limit.return_value.order.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        montant = agent._estimer_montant("EDF", "408100", "dos-1")

    assert montant == 0.0


# ─── Statut provisions ────────────────────────────────────────────────────────


def test_provisions_statut_a_valider_uniquement():
    """TOUTES les provisions ont statut='a_valider_fnp'."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "dos-1"}
    ]

    with patch.object(agent, "_detecter_fnp", return_value=[_provision_a_valider("dos-1", "408000")]):
        with patch.object(agent, "_detecter_fae", return_value=[_provision_a_valider("dos-1", "418000")]):
            with patch.object(agent, "_get_supabase", return_value=mock_sb):
                result = agent.run(force_mois=12)

    for p in result["provisions"]:
        assert p["statut"] == "a_valider_fnp"


def test_aucune_validation_automatique():
    """Aucun INSERT avec statut='valide' dans les sorties."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "dos-1"}
    ]

    with patch.object(agent, "_detecter_fnp", return_value=[_provision_a_valider()]):
        with patch.object(agent, "_detecter_fae", return_value=[]):
            with patch.object(agent, "_get_supabase", return_value=mock_sb):
                agent.run(force_mois=12)

    # Vérifie qu'aucun INSERT ne contient statut="valide"
    for insert_call in mock_sb.table.return_value.insert.call_args_list:
        payload = insert_call[0][0]
        assert payload.get("statut") != "valide", "Validation auto interdite"


# ─── Run complet ──────────────────────────────────────────────────────────────


def test_run_decembre_sans_provisions():
    """Décembre + aucun engagement → résultat vide, pas d'erreur."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run(force_mois=12)

    assert result["periode"] == "decembre"
    assert result["fnp_detectees"] == 0
    assert result["fae_detectees"] == 0
    assert result["provisions"] == []
    assert result["erreurs"] == []


def test_run_decembre_avec_fnp_et_fae():
    """FNP + FAE détectées → compteurs corrects."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "dos-1"}
    ]

    with patch.object(agent, "_detecter_fnp", return_value=[_provision_a_valider("dos-1", "408000")]):
        with patch.object(agent, "_detecter_fae", return_value=[_provision_a_valider("dos-1", "418000")]):
            with patch.object(agent, "_get_supabase", return_value=mock_sb):
                with patch("apps.jmpartners.agents.fnp_fae_agent.send_telegram_message"):
                    result = agent.run(force_mois=12)

    assert result["periode"] == "decembre"
    assert result["fnp_detectees"] == 1
    assert result["fae_detectees"] == 1
    assert len(result["provisions"]) == 2


def test_run_erreur_supabase():
    """Erreur Supabase → loggée, agent continue."""
    agent = FNPFAEAgent()

    with patch.object(agent, "_get_supabase", side_effect=Exception("DB down")):
        result = agent.run(force_mois=12)

    assert result["periode"] == "decembre"
    assert len(result["erreurs"]) == 1
    assert "DB down" in result["erreurs"][0]


def test_telegram_envoye_si_provisions():
    """Si provisions > 0 → send_telegram_message appelé une fois."""
    agent = FNPFAEAgent()
    mock_sb = _mock_sb_vide()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "dos-1"}
    ]

    with patch.object(agent, "_detecter_fnp", return_value=[_provision_a_valider()]):
        with patch.object(agent, "_detecter_fae", return_value=[]):
            with patch.object(agent, "_get_supabase", return_value=mock_sb):
                with patch("apps.jmpartners.agents.fnp_fae_agent.send_telegram_message") as mock_tg:
                    agent.run(force_mois=12)

    mock_tg.assert_called_once()

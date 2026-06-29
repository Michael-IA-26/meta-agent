"""Tests TDD — document_checker."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.document_checker import run


def _make_supabase(dossier=None, documents=None):
    sb = MagicMock()
    dossier_resp = MagicMock()
    dossier_resp.data = dossier
    doc_resp = MagicMock()
    doc_resp.data = documents or []

    def table_side(name):
        t = MagicMock()
        chain = MagicMock()
        if name == "dossiers":
            chain.execute.return_value = dossier_resp
        else:
            chain.execute.return_value = doc_resp
        for attr in ("select", "eq", "neq", "in_", "lte", "gte", "limit", "single"):
            setattr(chain, attr, MagicMock(return_value=chain))
        t.select = MagicMock(return_value=chain)
        t.insert = MagicMock(return_value=chain)
        return t

    sb.table = MagicMock(side_effect=table_side)
    return sb


def test_happy_path_bilan_documents_manquants():
    dossier = {"id": "d1", "contact_id": "c1", "type": "bilan",
               "deadline": (date.today() + timedelta(days=20)).isoformat()}
    docs_presents = [{"type_document": "grand_livre", "statut": "recu"}]

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, docs_presents)):
        result = run("d1", dry_run=True)

    assert result["dossier_id"] == "d1"
    assert result["erreur"] is None
    assert len(result["manquants"]) == 4  # bilan a 5 docs, 1 présent
    assert "grand_livre" not in [m["type_document"] for m in result["manquants"]]


def test_tous_documents_presents():
    dossier = {"id": "d1", "contact_id": "c1", "type": "tva",
               "deadline": (date.today() + timedelta(days=10)).isoformat()}
    docs = [{"type_document": t, "statut": "valide"}
            for t in ("ca_mensuel", "factures_tva", "releves_bancaires")]

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, docs)):
        result = run("d1", dry_run=True)

    assert result["manquants"] == []
    assert len(result["complets"]) == 3


def test_dossier_introuvable():
    sb = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=None)
    for attr in ("select", "eq", "single"):
        setattr(chain, attr, MagicMock(return_value=chain))
    sb.table.return_value.select.return_value = chain

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=sb):
        result = run("inconnu", dry_run=True)

    assert result["erreur"] is not None
    assert "introuvable" in result["erreur"]
    assert result["manquants"] == []


def test_type_dossier_inconnu():
    dossier = {"id": "d1", "contact_id": "c1", "type": "inconnu", "deadline": None}

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, [])):
        result = run("d1", dry_run=True)

    assert result["erreur"] is not None
    assert "inconnu" in result["erreur"].lower()


def test_dry_run_true_ninsere_pas_dans_journaux():
    dossier = {"id": "d1", "contact_id": "c1", "type": "tva", "deadline": None}
    sb = _make_supabase(dossier, [])

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=sb):
        run("d1", dry_run=True)

    # Aucun appel à table("journaux").insert
    calls = [str(c) for c in sb.table.call_args_list]
    assert not any("journaux" in c for c in calls)


def test_deadline_passee_urgence_j0():
    dossier = {"id": "d1", "contact_id": "c1", "type": "tva",
               "deadline": (date.today() - timedelta(days=1)).isoformat()}

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, [])):
        result = run("d1", dry_run=True)

    urgences = [m["urgence"] for m in result["manquants"]]
    assert all(u == "J-0" for u in urgences)


def test_deadline_dans_3_jours_urgence_j3():
    dossier = {"id": "d1", "contact_id": "c1", "type": "tva",
               "deadline": (date.today() + timedelta(days=2)).isoformat()}

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, [])):
        result = run("d1", dry_run=True)

    urgences = [m["urgence"] for m in result["manquants"]]
    assert all(u == "J-3" for u in urgences)


def test_timeout_supabase_retourne_erreur():
    sb = MagicMock()
    sb.table.side_effect = Exception("Connection timeout")

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=sb):
        result = run("d1", dry_run=True)

    assert result["erreur"] is not None
    assert result["manquants"] == []


def test_document_illisible_statut_inconnu_compte_comme_absent():
    """Un document avec un statut non reconnu est considéré absent."""
    dossier = {"id": "d1", "contact_id": "c1", "type": "tva",
               "deadline": (date.today() + timedelta(days=10)).isoformat()}
    docs = [{"type_document": "ca_mensuel", "statut": "illisible"}]  # statut non valide

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, docs)):
        result = run("d1", dry_run=True)

    # ca_mensuel avec statut "illisible" ne compte pas comme présent
    manquants_types = [m["type_document"] for m in result["manquants"]]
    assert "ca_mensuel" in manquants_types


def test_dossier_sans_contact_id():
    """Un dossier sans contact_id retourne quand même les documents manquants."""
    dossier = {"id": "d1", "contact_id": None, "type": "is", "deadline": None}

    with patch("apps.jmpartners.agents.document_checker.get_supabase_client",
               return_value=_make_supabase(dossier, [])):
        result = run("d1", dry_run=True)

    assert result["contact_id"] is None
    assert result["erreur"] is None
    assert len(result["manquants"]) == 3  # is : 3 docs attendus

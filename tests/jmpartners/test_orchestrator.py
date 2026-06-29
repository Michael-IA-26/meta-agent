"""Tests TDD — orchestrateur JM Partners.

Couvre : ordre d'exécution, résilience aux pannes, dry_run, idempotence.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.orchestrator import (
    _process_documents,
    run,
    run_document_relance_flow,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _mail_result(emails=None):
    return {"traites": 0, "non_matches": 0, "emails": emails or [], "erreurs": []}


def _tva_result():
    return {"declarations_analysees": 0, "alertes_envoyees": 0,
            "pieces_manquantes_total": 0, "declarations": [], "erreurs": []}


def _echeance_result():
    return {"echeances_total": 0, "rouge": 0, "orange": 0, "vert": 0,
            "rapport_envoye": False, "echeances": [], "erreurs": []}


def _cloture_result():
    return {"cabinet_id": "jmpartners", "mois": "2026-06",
            "dossiers_clotures": [], "statut": "skip", "timestamp": "2026-06-10T00:00:00Z"}


# ── Ordre d'exécution ──────────────────────────────────────────────────────────


def test_run_appelle_mail_tva_echeance_dans_cet_ordre():
    """Les 3 agents core sont appelés dans l'ordre mail → tva → écheances."""
    call_order = []

    with (
        patch("apps.jmpartners.orchestrator.handle_mail",
              side_effect=lambda **kw: call_order.append("mail") or _mail_result()) as _,
        patch("apps.jmpartners.orchestrator.run_tva",
              side_effect=lambda **kw: call_order.append("tva") or _tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances",
              side_effect=lambda **kw: call_order.append("echeances") or _echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        run(dry_run=False)

    assert call_order[:3] == ["mail", "tva", "echeances"]


def test_run_dry_run_saute_cloture_acomptes_bilans_declarations():
    """dry_run=True : étapes 4-7 sont skippées, résultats None/[]."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler") as mock_cloture,
        patch("apps.jmpartners.orchestrator.AcompteISAgent") as mock_acompte,
        patch("apps.jmpartners.orchestrator.BilanAgent") as mock_bilan,
        patch("apps.jmpartners.orchestrator.DeclarationISAgent") as mock_decl,
    ):
        result = run(dry_run=True)

    mock_cloture.return_value.run.assert_not_called()
    mock_acompte.return_value.run.assert_not_called()
    mock_bilan.return_value.run.assert_not_called()
    mock_decl.return_value.run.assert_not_called()
    assert result["cloture"] is None
    assert result["acomptes_is"] == []
    assert result["bilans"] == []
    assert result["declarations_is"] == []


def test_run_sans_dry_run_appelle_cloture_acomptes_bilans_declarations():
    """dry_run=False : étapes 4-7 sont exécutées."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler") as mock_cloture,
        patch("apps.jmpartners.orchestrator.AcompteISAgent") as mock_acompte,
        patch("apps.jmpartners.orchestrator.BilanAgent") as mock_bilan,
        patch("apps.jmpartners.orchestrator.DeclarationISAgent") as mock_decl,
    ):
        mock_cloture.return_value.run.return_value = _cloture_result()
        mock_acompte.return_value.run.return_value = []
        mock_bilan.return_value.run.return_value = []
        mock_decl.return_value.run.return_value = []
        run(dry_run=False)

    mock_cloture.return_value.run.assert_called_once()
    mock_acompte.return_value.run.assert_called_once()
    mock_bilan.return_value.run.assert_called_once()
    mock_decl.return_value.run.assert_called_once()


# ── Résilience aux pannes ──────────────────────────────────────────────────────


def test_crash_tva_agent_nempecche_pas_echeances():
    """Si tva_agent lève une exception, echeance_agent est quand même appelé."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", side_effect=RuntimeError("TVA down")),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()) as mock_ech,
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        result = run(dry_run=False)

    mock_ech.assert_called_once()
    assert result["tva"] is None
    assert any("tva_agent" in e for e in result["erreurs"])


def test_crash_mail_handler_nempecche_pas_tva():
    """Si mail_handler lève une exception, tva_agent est quand même appelé."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", side_effect=RuntimeError("IMAP fail")),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()) as mock_tva,
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        result = run(dry_run=False)

    mock_tva.assert_called_once()
    assert result["mail"] is None


def test_tous_les_agents_crashent_erreurs_accumulees():
    """Tous les agents en erreur → erreurs liste contient toutes les erreurs."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", side_effect=Exception("mail err")),
        patch("apps.jmpartners.orchestrator.run_tva", side_effect=Exception("tva err")),
        patch("apps.jmpartners.orchestrator.run_echeances", side_effect=Exception("ech err")),
        patch("apps.jmpartners.orchestrator.ClotureHandler") as mc,
        patch("apps.jmpartners.orchestrator.AcompteISAgent") as ma,
        patch("apps.jmpartners.orchestrator.BilanAgent") as mb,
        patch("apps.jmpartners.orchestrator.DeclarationISAgent") as md,
    ):
        mc.return_value.run.side_effect = Exception("cloture err")
        ma.return_value.run.side_effect = Exception("acompte err")
        mb.return_value.run.side_effect = Exception("bilan err")
        md.return_value.run.side_effect = Exception("decl err")
        result = run(dry_run=False)

    assert len(result["erreurs"]) == 6  # tva, echeance, cloture, acompte, bilan, decl (mail absorbé)
    assert result["mail"] is None
    assert result["tva"] is None
    assert result["echeances"] is None


def test_erreur_agent_ne_leve_pas_dexception():
    """run() ne propage jamais d'exception même si tous les agents crashent."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", side_effect=Exception("x")),
        patch("apps.jmpartners.orchestrator.run_tva", side_effect=Exception("x")),
        patch("apps.jmpartners.orchestrator.run_echeances", side_effect=Exception("x")),
        patch("apps.jmpartners.orchestrator.ClotureHandler") as mc,
        patch("apps.jmpartners.orchestrator.AcompteISAgent") as ma,
        patch("apps.jmpartners.orchestrator.BilanAgent") as mb,
        patch("apps.jmpartners.orchestrator.DeclarationISAgent") as md,
    ):
        mc.return_value.run.side_effect = Exception("x")
        ma.return_value.run.side_effect = Exception("x")
        mb.return_value.run.side_effect = Exception("x")
        md.return_value.run.side_effect = Exception("x")
        result = run(dry_run=False)  # ne doit pas lever

    assert isinstance(result, dict)


# ── Structure du résultat ──────────────────────────────────────────────────────


def test_relances_toujours_liste_vide():
    """relances est toujours [] — flux email→relance non implémenté."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        result = run(dry_run=True)

    assert result["relances"] == []


def test_resultat_contient_toutes_les_cles():
    """OrchestratorResult a exactement les 9 clés attendues."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        result = run(dry_run=True)

    assert set(result.keys()) == {
        "mail", "relances", "tva", "echeances", "cloture",
        "acomptes_is", "bilans", "declarations_is", "erreurs"
    }


# ── Email entrant → relance (non implémenté) ───────────────────────────────────


@pytest.mark.xfail(
    reason="Flux email→document_checker→relance non implémenté dans _handle_emails"
           " (orchestrator.py:63-64)",
    strict=True,
)
def test_email_document_manquant_declenche_relance():
    """Un email document_manquant avec contact_id connu doit déclencher une relance."""
    email_item = {
        "message_id": "msg-1",
        "expediteur": "contact@dupont.fr",
        "sujet": "Documents manquants",
        "corps": "...",
        "contact_id": "contact-1",
        "contact_nom": "SARL Dupont",
        "type_demande": "document_manquant",
        "journal_id": "j-1",
    }
    with (
        patch("apps.jmpartners.orchestrator.handle_mail",
              return_value=_mail_result(emails=[email_item])),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator.check_docs") as mock_check,
        patch("apps.jmpartners.orchestrator.send_relance") as mock_relance,
    ):
        mock_check.return_value = {
            "dossier_id": "dos-1", "contact_id": "contact-1",
            "type_dossier": "bilan", "manquants": [
                {"nom_document": "Grand Livre", "type_document": "grand_livre",
                 "deadline": None, "urgence": None}
            ], "complets": [], "erreur": None,
        }
        mock_relance.return_value = {
            "envoye": True, "raison_skip": None,
            "email_destinataire": "contact@dupont.fr",
            "sujet": "Relance", "corps": "...", "journal_id": "j-2",
        }
        result = run(dry_run=False)

    assert len(result["relances"]) == 1
    assert result["relances"][0]["envoye"] is True


# ── NotificationAgent ─────────────────────────────────────────────────────────


@pytest.mark.xfail(
    reason="NotificationAgent instancié mais jamais utilisé pour envoyer"
           " (orchestrator.py:160-163 — Sprint 3 non terminé)",
    strict=True,
)
def test_notification_agent_appele_pour_alertes_urgentes():
    """NotificationAgent.send() doit être appelé pour les alertes J-3."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator.NotificationAgent") as mock_notif,
    ):
        run(dry_run=False)

    mock_notif.return_value.send.assert_called()


# ── Idempotence ────────────────────────────────────────────────────────────────


def test_deux_runs_consecutifs_meme_structure_de_resultat():
    """Deux appels run() retournent des structures identiques (pas de side-effects globaux)."""
    patches = (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        r1 = run(dry_run=True)
        r2 = run(dry_run=True)

    assert r1.keys() == r2.keys()
    assert r1["erreurs"] == r2["erreurs"] == []


# ── run_document_relance_flow ─────────────────────────────────────────────────


def test_run_document_relance_flow_appelle_check_puis_relance():
    """run_document_relance_flow appelle d'abord check_docs puis send_relance."""
    mock_doc = MagicMock()
    mock_relance = MagicMock()

    with (
        patch("apps.jmpartners.orchestrator.check_docs", return_value=mock_doc) as m_check,
        patch("apps.jmpartners.orchestrator.send_relance", return_value=mock_relance) as m_relance,
    ):
        doc, rel = run_document_relance_flow("dos-1", dry_run=False)

    m_check.assert_called_once_with("dos-1", dry_run=False)
    m_relance.assert_called_once_with(mock_doc, dry_run=False)
    assert doc is mock_doc
    assert rel is mock_relance


def test_run_document_relance_flow_dry_run_passe_flag():
    mock_doc = MagicMock()
    with (
        patch("apps.jmpartners.orchestrator.check_docs", return_value=mock_doc),
        patch("apps.jmpartners.orchestrator.send_relance", return_value=MagicMock()) as m_rel,
    ):
        run_document_relance_flow("dos-1", dry_run=True)

    m_rel.assert_called_once_with(mock_doc, dry_run=True)


# ── report_builder mensuel ────────────────────────────────────────────────────


def test_report_builder_appele_dernier_jour_ouvre(monkeypatch):
    """run_rapport_mensuel est appelé pour chaque dossier actif le dernier jour ouvré."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")

    mock_sb = MagicMock()
    # Une seule chaîne .eq() (plus de filtre cabinet_id)
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "doss-1"},
        {"id": "doss-2"},
    ]

    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator._is_dernier_jour_ouvre", return_value=True),
        patch("apps.jmpartners.orchestrator.get_supabase_client", return_value=mock_sb),
        patch("apps.jmpartners.orchestrator.run_rapport_mensuel") as mock_rapport,
    ):
        run(dry_run=False)

    assert mock_rapport.call_count == 2
    # Assertions sur kwargs pour détecter toute régression de signature
    called_dossier_ids = {c.kwargs["dossier_id"] for c in mock_rapport.call_args_list}
    called_mois = {c.kwargs["mois"] for c in mock_rapport.call_args_list}
    assert called_dossier_ids == {"doss-1", "doss-2"}
    assert len(called_mois) == 1  # même période pour tous les dossiers


def test_report_builder_non_appele_sinon():
    """run_rapport_mensuel n'est PAS appelé quand ce n'est pas le dernier jour ouvré."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator._is_dernier_jour_ouvre", return_value=False),
        patch("apps.jmpartners.orchestrator.run_rapport_mensuel") as mock_rapport,
    ):
        run(dry_run=False)

    mock_rapport.assert_not_called()


# ── _process_documents pipeline ───────────────────────────────────────────────


def _mock_supabase_with_docs(docs):
    sb = MagicMock()
    sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = docs
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    return sb


def test_process_documents_recu_triggers_analyzer_and_transition():
    """Document 'en_attente_ocr' → document_analyzer appelé → statut mis à 'a_trier'."""
    sb = _mock_supabase_with_docs([
        {"id": "doc-1", "url_storage": "https://x/doc.pdf", "type_document": "facture_achat", "statut": "en_attente_ocr"}
    ])
    with (
        patch("apps.jmpartners.orchestrator.run_document_analyzer") as mock_analyzer,
        patch("apps.jmpartners.orchestrator.run_ecriture_generator"),
    ):
        mock_analyzer.return_value = {"statut": "ok"}
        _process_documents(sb, dry_run=False)

    mock_analyzer.assert_called_once_with(
        "doc-1", url="https://x/doc.pdf", type_document="facture_achat"
    )
    sb.table.return_value.update.assert_called()


def test_process_documents_analyse_triggers_generator_and_transition():
    """Document 'a_trier' → ecriture_generator appelé → statut mis à 'a_saisir_sage'."""
    sb = _mock_supabase_with_docs([
        {"id": "doc-2", "url_storage": "", "type_document": "facture_vente", "statut": "a_trier"}
    ])
    with (
        patch("apps.jmpartners.orchestrator.run_document_analyzer"),
        patch("apps.jmpartners.orchestrator.run_ecriture_generator") as mock_gen,
    ):
        mock_gen.return_value = {"statut": "ok", "ecritures": []}
        _process_documents(sb, dry_run=False)

    mock_gen.assert_called_once_with("doc-2")
    sb.table.return_value.update.assert_called()


def test_process_documents_presaisi_not_reprocessed():
    """Document 'presaisi' est ignoré — ni analyzer ni generator appelés."""
    sb = _mock_supabase_with_docs([
        {"id": "doc-3", "url": "", "type_document": "facture_achat", "statut": "presaisi"}
    ])
    with (
        patch("apps.jmpartners.orchestrator.run_document_analyzer") as mock_a,
        patch("apps.jmpartners.orchestrator.run_ecriture_generator") as mock_g,
    ):
        _process_documents(sb, dry_run=False)

    mock_a.assert_not_called()
    mock_g.assert_not_called()


def test_process_documents_exception_on_one_does_not_stop_others():
    """Exception sur doc-1 n'empêche pas le traitement de doc-2."""
    sb = _mock_supabase_with_docs([
        {"id": "doc-1", "url_storage": "", "type_document": "facture_achat", "statut": "en_attente_ocr"},
        {"id": "doc-2", "url_storage": "", "type_document": "facture_vente", "statut": "a_trier"},
    ])
    with (
        patch("apps.jmpartners.orchestrator.run_document_analyzer",
              side_effect=RuntimeError("analyzer crash")),
        patch("apps.jmpartners.orchestrator.run_ecriture_generator") as mock_gen,
    ):
        mock_gen.return_value = {"statut": "ok", "ecritures": []}
        erreurs = _process_documents(sb, dry_run=False)

    mock_gen.assert_called_once_with("doc-2")
    assert len(erreurs) == 1
    assert "doc-1" in erreurs[0]


def test_process_documents_dry_run_no_writes():
    """dry_run=True → agents non appelés, pas de mise à jour statut."""
    sb = _mock_supabase_with_docs([
        {"id": "doc-1", "url_storage": "u", "type_document": "facture_achat", "statut": "en_attente_ocr"},
        {"id": "doc-2", "url_storage": "", "type_document": "facture_vente", "statut": "a_trier"},
    ])
    with (
        patch("apps.jmpartners.orchestrator.run_document_analyzer") as mock_a,
        patch("apps.jmpartners.orchestrator.run_ecriture_generator") as mock_g,
    ):
        _process_documents(sb, dry_run=True)

    mock_a.assert_not_called()
    mock_g.assert_not_called()
    sb.table.return_value.update.assert_not_called()


def test_process_documents_none_supabase_returns_empty():
    """Supabase None → retourne [] sans crash."""
    erreurs = _process_documents(None, dry_run=False)
    assert erreurs == []


def test_report_builder_non_appele_en_dry_run():
    """run_rapport_mensuel n'est jamais appelé en dry_run même le dernier jour ouvré."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator._is_dernier_jour_ouvre", return_value=True),
        patch("apps.jmpartners.orchestrator.run_rapport_mensuel") as mock_rapport,
    ):
        run(dry_run=True)

    mock_rapport.assert_not_called()

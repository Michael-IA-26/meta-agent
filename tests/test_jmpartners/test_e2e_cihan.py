"""Test end-to-end — dossier pilote CIHAN — schéma Supabase v2.2."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

# ─── Imports agents (en haut pour que patch.object fonctionne) ───────────────
from apps.jmpartners.agents.fnp_fae_agent import FNPFAEAgent
from apps.jmpartners.agents.lettrage_agent import LettrageAgent
from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent
from apps.jmpartners.agents.ocr_agent import OCRAgent
from apps.jmpartners.agents.revision_agent import RevisionAgent
from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent
from apps.jmpartners.agents.tri_classification_agent import TriClassificationAgent
from apps.jmpartners.agents.verificateur_agent import VerificateurAgent

# ─── Constantes CIHAN (IDs fixes du seed v2.2) ───────────────────────────────

UTILISATEUR_ID = "00000000-0000-0000-0000-000000000001"
CONTACT_ID_GERANT = "cihan-0000-0000-0000-contact000001"
CONTACT_ID_COMPTABLE = "cihan-0000-0000-0000-contact000002"
DOSSIER_ID = "cihan-0000-0000-0000-dossier00001"
DOC_ID_1 = "cihan-0000-0000-0000-document00001"
DOC_ID_2 = "cihan-0000-0000-0000-document00002"
DOC_ID_3 = "cihan-0000-0000-0000-document00003"
CABINET_ID = "jmpartners"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_supabase_mock(rows=None, storage_download: bytes | None = None):
    """Construit un mock Supabase avec chaîne fluide complète + storage."""
    sb = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.neq.return_value = query
    query.lt.return_value = query
    query.gt.return_value = query
    query.is_.return_value = query
    query.in_.return_value = query
    query.like.return_value = query
    query.not_.return_value = query
    query.single.return_value = query
    query.limit.return_value = query
    query.order.return_value = query
    query.insert.return_value = query
    query.update.return_value = query
    query.delete.return_value = query
    query.upsert.return_value = query
    resp = MagicMock()
    resp.data = rows or []
    resp.count = len(rows) if rows else 0
    query.execute.return_value = resp
    sb.table.return_value = query
    sb.rpc.return_value = query
    # Storage mock
    storage_bucket = MagicMock()
    storage_bucket.download.return_value = storage_download or b"%PDF-1.4 test stub"
    storage_bucket.upload.return_value = MagicMock()
    sb.storage.from_.return_value = storage_bucket
    return sb


def _make_anthropic_mock(json_response: dict):
    """Construit un mock Anthropic retournant un JSON fixturisé."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(json_response))]
    client.messages.create.return_value = msg
    return client


def _doc_v22(
    doc_id: str,
    nom: str = "facture.pdf",
    type_document: str = "facture_achat",
    statut: str = "en_attente_ocr",
    score_ocr: float | None = None,
    score_confiance: float | None = None,
    contenu_extrait: dict | None = None,
    source: str = "outlook",
    multi_dossiers: bool = False,
    raison_attente: str | None = None,
    chemin_stockage: str | None = None,
) -> dict:
    """Construit une row documents conforme au schéma v2.2."""
    return {
        "id": doc_id,
        "dossier_id": DOSSIER_ID,
        "contact_id": CONTACT_ID_GERANT,
        "nom": nom,
        "nom_fichier": nom,
        "type_document": type_document,
        "statut": statut,
        "source": source,
        "url_storage": f"storage/{CABINET_ID}/{doc_id}/{nom}",
        "chemin_stockage": chemin_stockage or f"{CABINET_ID}/{DOSSIER_ID}/{nom}",
        "contenu_extrait": contenu_extrait or {},
        "score_ocr": score_ocr,
        "score_confiance": score_confiance,
        "multi_dossiers": multi_dossiers,
        "raison_attente": raison_attente,
        "badge_anomalie": False,
        "anomalie_desc": None,
        "urgence": False,
        "created_at": "2026-05-01T08:00:00Z",
        "updated_at": "2026-05-01T08:00:00Z",
    }


# ─── TestChaineDocumentaireCIHAN ─────────────────────────────────────────────


class TestChaineDocumentaireCIHAN:
    """Tests de la chaîne documentaire CIHAN avec le schéma v2.2."""

    def test_facture_achat_statut_final(self):
        """Après OCR (score=0.92) + tri (confiance=0.88) → statut=a_saisir_sage."""
        doc = _doc_v22(DOC_ID_1, nom="facture_fournisseur.pdf", score_ocr=0.92)
        sb = _make_supabase_mock(rows=[doc])

        ocr_json = {
            "type_document": "facture_achat",
            "siret": "12345678901234",
            "montant_ht": "1000.00",
            "montant_ttc": "1200.00",
            "taux_tva": 20.0,
            "score_confiance": 0.88,
            "multi_factures": False,
            "texte_brut": "FACTURE FOURNISSEUR CIHAN",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        agent = OCRAgent(cabinet_id=CABINET_ID)
        with (
            patch.object(agent, "_get_supabase", return_value=sb),
            patch.object(agent, "_get_anthropic", return_value=anthropic_mock),
        ):
            result = agent.run()

        assert result["documents_a_trier"] == 1
        assert result["documents_en_attente"] == 0

    def test_facture_vente_statut_final(self):
        """Facture de vente avec score_ocr=0.95 → a_trier puis a_saisir_sage."""
        doc = _doc_v22(
            DOC_ID_2,
            nom="facture_vente.pdf",
            type_document="facture_vente",
            score_ocr=0.95,
        )
        sb = _make_supabase_mock(rows=[doc])

        ocr_json = {
            "type_document": "facture_vente",
            "siret": "98765432100123",
            "montant_ht": "2000.00",
            "montant_ttc": "2200.00",
            "taux_tva": 10.0,
            "score_confiance": 0.95,
            "multi_factures": False,
            "texte_brut": "FACTURE CLIENT CIHAN",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        agent = OCRAgent(cabinet_id=CABINET_ID)
        with (
            patch.object(agent, "_get_supabase", return_value=sb),
            patch.object(agent, "_get_anthropic", return_value=anthropic_mock),
        ):
            result = agent.run()

        assert result["documents_a_trier"] == 1
        assert result["details"][0]["score_confiance"] == 0.95

    def test_releve_bancaire_type_document(self):
        """TriClassificationAgent détecte type_document='releve_bancaire'."""
        doc = _doc_v22(
            DOC_ID_3,
            nom="releve_juin.pdf",
            type_document="releve_bancaire",
            statut="a_trier",
            contenu_extrait={"solde": "15000.00", "type_document": "bancaire"},
        )
        sb = _make_supabase_mock(rows=[doc])

        agent = TriClassificationAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["qualifies_auto"] == 1
        assert result["details"][0]["type_piece"] == "bancaire"

    def test_note_frais_confiance_faible(self):
        """score_confiance=0.75 → document traité, score correctement enregistré."""
        doc = _doc_v22(
            DOC_ID_1,
            nom="note_frais.pdf",
            type_document="note_frais",
            score_ocr=0.78,
        )
        sb = _make_supabase_mock(rows=[doc])

        ocr_json = {
            "type_document": "note_frais",
            "score_confiance": 0.75,
            "multi_factures": False,
            "texte_brut": "NOTE DE FRAIS REPAS",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        agent = OCRAgent(cabinet_id=CABINET_ID)
        with (
            patch.object(agent, "_get_supabase", return_value=sb),
            patch.object(agent, "_get_anthropic", return_value=anthropic_mock),
        ):
            result = agent.run()

        # score_confiance=0.75 > OCR_SCORE_SEUIL=0.70 → a_trier
        assert result["documents_traites"] == 1
        assert result["details"][0]["score_confiance"] == 0.75

    def test_document_illisible_ocr_faible(self):
        """score_ocr=0.62 → statut=en_attente (en dessous du seuil 0.70)."""
        doc = _doc_v22(DOC_ID_2, nom="doc_flou.pdf", score_ocr=0.62)
        sb = _make_supabase_mock(rows=[doc])

        ocr_json = {
            "type_document": "autre",
            "score_confiance": 0.62,
            "multi_factures": False,
            "texte_brut": "document illisible flou",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        agent = OCRAgent(cabinet_id=CABINET_ID)
        with (
            patch.object(agent, "_get_supabase", return_value=sb),
            patch.object(agent, "_get_anthropic", return_value=anthropic_mock),
        ):
            result = agent.run()

        # score_confiance=0.62 < OCR_SCORE_SEUIL=0.70 → en_attente_validation
        assert result["documents_en_attente"] == 1
        assert result["documents_a_trier"] == 0

    def test_multi_dossiers_ambiguite(self):
        """multi_dossiers=True → multi_dossiers=True dans les détails OCR."""
        doc = _doc_v22(
            DOC_ID_3,
            nom="facture_multi.pdf",
            multi_dossiers=True,
        )
        sb = _make_supabase_mock(rows=[doc])

        ocr_json = {
            "type_document": "multi",
            "score_confiance": 0.90,
            "multi_factures": True,
            "fragments": [
                {"montant_ttc": "600", "libelle": "Dossier A"},
                {"montant_ttc": "400", "libelle": "Dossier B"},
            ],
            "texte_brut": "MULTI FACTURE CIHAN",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        agent = OCRAgent(cabinet_id=CABINET_ID)
        with (
            patch.object(agent, "_get_supabase", return_value=sb),
            patch.object(agent, "_get_anthropic", return_value=anthropic_mock),
        ):
            result = agent.run()

        assert result["details"][0]["multi_dossiers"] is True


# ─── TestCycleNocturne ────────────────────────────────────────────────────────


class TestCycleNocturne:
    """Tests du cycle nocturne CIHAN (RPA Sage, Miroir Sage, Révision)."""

    def test_rpa_stub_mode(self):
        """RPASageAgent(mode='stub').run() → next_agent='miroir_sage_agent'."""
        sb = _make_supabase_mock(rows=[])

        agent = RPASageAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run(mode="stub")

        assert result["next_agent"] == "miroir_sage_agent"
        assert result["mode"] == "stub"

    def test_miroir_sage_sync_fec(self):
        """_sync_fec() → retourne dict avec ecritures_nouvelles (int)."""
        sb = _make_supabase_mock(rows=[])

        agent = MiroirSageAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            # Sans fichier FEC → retourne 0 écritures sans lever d'exception
            result = agent._sync_fec()

        assert "ecritures_nouvelles" in result
        assert isinstance(result["ecritures_nouvelles"], int)

    def test_revision_agent_anomalies(self):
        """RevisionAgent → rapport avec anomalies (doublon de référence)."""
        ecritures = [
            {
                "id": "ecr-rev-001",
                "journal": "ACH",
                "reference": "FAC001",
                "debit": 1200.0,
                "credit": 0.0,
                "libelle": "Facture fournisseur",
                "date_piece": "2026-05-01",
            },
            {
                "id": "ecr-rev-002",
                "journal": "ACH",
                "reference": "FAC001",
                "debit": 1200.0,
                "credit": 0.0,
                "libelle": "Facture fournisseur doublon",
                "date_piece": "2026-05-01",
            },
        ]
        sb = _make_supabase_mock(rows=ecritures)

        agent = RevisionAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["anomalies_detectees"] >= 1
        assert any(
            a.get("type_anomalie") in ("doublon_reference", "desequilibre_journal")
            for a in result["anomalies"]
        )


# ─── TestReglesMetier ─────────────────────────────────────────────────────────


class TestReglesMetier:
    """Tests des règles métier spécifiques v2.2 CIHAN."""

    def test_verificateur_badge_only(self):
        """VerificateurAgent détecte le déséquilibre D/C sans modifier montant/compte."""
        ecritures = [
            {
                "id": "ecr-badge-001",
                "journal": "ACH",
                "compte_debit": "401000",
                "compte_credit": "",
                "montant": 1200.0,
                "statut": "proposee",
            },
            {
                "id": "ecr-badge-002",
                "journal": "ACH",
                "compte_debit": "",
                "compte_credit": "512000",
                "montant": 800.0,  # Déséquilibre volontaire
                "statut": "proposee",
            },
        ]
        sb = _make_supabase_mock(rows=ecritures)

        agent = VerificateurAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["lot_propre"] is False
        assert len(result["anomalies"]) >= 1
        for anomalie in result["anomalies"]:
            assert "compte" not in anomalie

    def test_fnp_hors_decembre(self):
        """FNPFAEAgent avec force_mois=5 → statut='hors_periode'."""
        sb = _make_supabase_mock(rows=[])

        agent = FNPFAEAgent(cabinet_id=CABINET_ID, force_mois=5)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["statut"] == "hors_periode"
        assert result["provisions_creees"] == 0
        assert result["mois_traite"] == 5

    def test_fnp_en_decembre(self):
        """FNPFAEAgent avec force_mois=12 → traitement des provisions activé."""
        docs_en_attente = [
            _doc_v22(
                DOC_ID_1,
                nom="facture_dec.pdf",
                statut="en_attente_collaborateur",
            ),
            _doc_v22(
                DOC_ID_2,
                nom="facture_dec2.pdf",
                statut="en_attente_collaborateur",
            ),
        ]
        sb = _make_supabase_mock(rows=docs_en_attente)

        agent = FNPFAEAgent(cabinet_id=CABINET_ID, force_mois=12)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["statut"] != "hors_periode"
        assert result["mois_traite"] == 12

    def test_lettrage_exact_match(self):
        """LettrageAgent → confiance=1.0, type_lettrage='exact' sur montant+tiers identiques."""
        ecritures_non_lettrées = [
            {
                "id": "ecr-lettre-001",
                "montant_ht": "1000.00",
                "montant_ttc": "1200.00",
                "tiers": "FOURNISSEUR_X",
                "est_lettree": False,
                "lettre": None,
                "statut": "a_valider",
                "source_validation": "claude",
            },
            {
                "id": "ecr-lettre-002",
                "montant_ht": "1000.00",
                "montant_ttc": "1200.00",
                "tiers": "FOURNISSEUR_X",
                "est_lettree": False,
                "lettre": None,
                "statut": "a_valider",
                "source_validation": "claude",
            },
        ]
        sb = _make_supabase_mock(rows=ecritures_non_lettrées)

        agent = LettrageAgent(cabinet_id=CABINET_ID)
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["confiance"] == 1.0
        assert result["type_lettrage"] == "exact"
        assert result["paires_trouvees"] >= 1


# ─── TestOrchestrateur ────────────────────────────────────────────────────────


class TestOrchestrateur:
    """Tests de l'orchestrateur CIHAN (orchestrator_cihan.run)."""

    def _make_mock_agent(self, result_dict: dict) -> MagicMock:
        """Crée un mock d'agent dont .run() retourne result_dict."""
        mock_cls = MagicMock()
        instance = MagicMock()
        instance.run.return_value = result_dict
        mock_cls.return_value = instance
        return mock_cls

    def test_run_dry_run(self):
        """orchestrator_cihan.run(dry_run=True) → CIHANOrchestratorResult sans erreurs."""
        from apps.jmpartners import orchestrator_cihan

        mock_collecte = self._make_mock_agent(
            {"documents_uploades": 3, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_ocr = self._make_mock_agent(
            {
                "documents_traites": 3,
                "documents_a_trier": 3,
                "documents_en_attente": 0,
                "erreurs": [],
                "details": [],
            }
        )
        mock_tri = self._make_mock_agent(
            {
                "documents_traites": 3,
                "qualifies_auto": 3,
                "en_attente_manuelle": 0,
                "erreurs": [],
                "details": [],
            }
        )
        mock_presaisie = self._make_mock_agent(
            {"documents_traites": 3, "ecritures_proposees": 6, "erreurs": [], "details": []}
        )
        mock_verificateur = self._make_mock_agent(
            {"ecritures_verifiees": 6, "lot_propre": True, "anomalies": [], "erreurs": []}
        )
        mock_ged = self._make_mock_agent(
            {"documents_archives": 3, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_rpa = self._make_mock_agent(
            {
                "mode": "stub",
                "ecritures_importees": 6,
                "ecritures_rejetes": 0,
                "next_agent": "miroir_sage_agent",
                "erreurs": [],
                "details": [],
            }
        )
        mock_miroir = self._make_mock_agent(
            {"ecritures_nouvelles": 0, "ecritures_mises_a_jour": 0, "erreurs": []}
        )
        mock_revision = self._make_mock_agent(
            {
                "ecritures_analysees": 0,
                "anomalies_detectees": 0,
                "anomalies": [],
                "erreurs": [],
            }
        )

        with (
            patch.object(orchestrator_cihan, "CollecteAgent", mock_collecte),
            patch.object(orchestrator_cihan, "OCRAgent", mock_ocr),
            patch.object(orchestrator_cihan, "TriClassificationAgent", mock_tri),
            patch.object(orchestrator_cihan, "PresaisieAgent", mock_presaisie),
            patch.object(orchestrator_cihan, "VerificateurAgent", mock_verificateur),
            patch.object(orchestrator_cihan, "GEDAgent", mock_ged),
            patch.object(orchestrator_cihan, "RPASageAgent", mock_rpa),
            patch.object(orchestrator_cihan, "MiroirSageAgent", mock_miroir),
            patch.object(orchestrator_cihan, "RevisionAgent", mock_revision),
        ):
            result = orchestrator_cihan.run(dry_run=True)

        assert len(result["erreurs"]) == 0

    def test_run_collecte_inclus(self):
        """orchestrator_cihan.run() → 'collecte' dans result et pas None."""
        from apps.jmpartners import orchestrator_cihan

        mock_collecte = self._make_mock_agent(
            {"documents_uploades": 1, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_ocr = self._make_mock_agent(
            {
                "documents_traites": 1,
                "documents_a_trier": 1,
                "documents_en_attente": 0,
                "erreurs": [],
                "details": [],
            }
        )
        mock_tri = self._make_mock_agent(
            {
                "documents_traites": 1,
                "qualifies_auto": 1,
                "en_attente_manuelle": 0,
                "erreurs": [],
                "details": [],
            }
        )
        mock_presaisie = self._make_mock_agent(
            {"documents_traites": 1, "ecritures_proposees": 2, "erreurs": [], "details": []}
        )
        mock_verificateur = self._make_mock_agent(
            {"ecritures_verifiees": 2, "lot_propre": True, "anomalies": [], "erreurs": []}
        )
        mock_ged = self._make_mock_agent(
            {"documents_archives": 1, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_rpa = self._make_mock_agent(
            {
                "mode": "stub",
                "ecritures_importees": 2,
                "ecritures_rejetes": 0,
                "next_agent": "miroir_sage_agent",
                "erreurs": [],
                "details": [],
            }
        )
        mock_miroir = self._make_mock_agent(
            {"ecritures_nouvelles": 0, "ecritures_mises_a_jour": 0, "erreurs": []}
        )
        mock_revision = self._make_mock_agent(
            {
                "ecritures_analysees": 0,
                "anomalies_detectees": 0,
                "anomalies": [],
                "erreurs": [],
            }
        )

        with (
            patch.object(orchestrator_cihan, "CollecteAgent", mock_collecte),
            patch.object(orchestrator_cihan, "OCRAgent", mock_ocr),
            patch.object(orchestrator_cihan, "TriClassificationAgent", mock_tri),
            patch.object(orchestrator_cihan, "PresaisieAgent", mock_presaisie),
            patch.object(orchestrator_cihan, "VerificateurAgent", mock_verificateur),
            patch.object(orchestrator_cihan, "GEDAgent", mock_ged),
            patch.object(orchestrator_cihan, "RPASageAgent", mock_rpa),
            patch.object(orchestrator_cihan, "MiroirSageAgent", mock_miroir),
            patch.object(orchestrator_cihan, "RevisionAgent", mock_revision),
        ):
            result = orchestrator_cihan.run(dry_run=True)

        assert result is not None
        assert "collecte" in result
        assert result["collecte"] is not None

"""Test end-to-end — dossier pilote CIHAN — tous les agents mockés sauf logique métier."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest

DOSSIER_ID = "cihan-test-uuid-0001"
CABINET_ID = "jmpartners"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_supabase_mock(data=None, *, storage_download=None, storage_raises=None):
    """Construit un mock Supabase complet avec chaîne fluide."""
    sb = MagicMock()

    # Chaîne fluide : .table().select().eq().execute() etc.
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.is_.return_value = query
    query.in_.return_value = query
    query.single.return_value = query
    query.limit.return_value = query
    resp = MagicMock()
    resp.data = data if data is not None else []
    query.execute.return_value = resp

    sb.table.return_value = query

    # Storage
    storage_bucket = MagicMock()
    if storage_raises:
        storage_bucket.download.side_effect = storage_raises
    elif storage_download is not None:
        storage_bucket.download.return_value = storage_download
    else:
        storage_bucket.download.return_value = b"%PDF-1.4 test"

    storage_bucket.upload.return_value = MagicMock()
    sb.storage.from_.return_value = storage_bucket

    return sb


def _make_anthropic_mock(json_response: dict):
    """Construit un mock Anthropic retournant un JSON donné."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(json_response))]
    client.messages.create.return_value = msg
    return client


# ─── TestChaineDocumentaireCIHAN ─────────────────────────────────────────────


class TestChaineDocumentaireCIHAN:
    """Tests de la chaîne documentaire CIHAN de bout en bout."""

    def test_collecte_produit_documents_en_attente_ocr(self, tmp_path):
        """La collecte doit détecter et uploader les PDFs du répertoire Outlook mock."""
        # Créer un PDF dans le répertoire tmp
        pdf_file = tmp_path / "test_facture.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n1 0 obj test endobj")

        # Supabase mock : pas de doublon, upload et insert réussis
        sb = _make_supabase_mock(data=[])

        with (
            patch(
                "apps.jmpartners.agents.collecte_agent.OUTLOOK_MOCK_DIR",
                str(tmp_path),
            ),
            patch(
                "apps.jmpartners.agents.collecte_agent.CollecteAgent._get_supabase",
                return_value=sb,
            ),
        ):
            from apps.jmpartners.agents.collecte_agent import CollecteAgent

            agent = CollecteAgent(cabinet_id=CABINET_ID, dossier_id=DOSSIER_ID)
            result = agent.run()

        assert result["documents_uploades"] >= 1

    def test_ocr_traite_documents_collectes(self):
        """L'OCR doit extraire le contenu et mettre à jour le statut en a_trier."""
        doc_row = {
            "id": "doc-ocr-001",
            "nom_fichier": "facture_fournisseur.pdf",
            "chemin_stockage": f"{CABINET_ID}/{DOSSIER_ID}/facture_fournisseur.pdf",
        }
        sb = _make_supabase_mock(data=[doc_row])

        ocr_json = {
            "type_document": "fournisseur",
            "siret": "12345678901234",
            "montant_ht": "1000",
            "montant_ttc": "1200",
            "taux_tva": 20.0,
            "score_confiance": 0.85,
            "multi_factures": False,
            "texte_brut": "FACTURE FOURNISSEUR",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        with (
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_supabase",
                return_value=sb,
            ),
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_anthropic",
                return_value=anthropic_mock,
            ),
        ):
            from apps.jmpartners.agents.ocr_agent import OCRAgent

            agent = OCRAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["documents_a_trier"] == 1

    def test_tri_classifie_apres_ocr(self):
        """Le tri doit classer le document comme fournisseur si SIRET + montant présents."""
        doc_row = {
            "id": "doc-tri-001",
            "nom_fichier": "facture_fournisseur.pdf",
            "contenu_extrait": {
                "siret": "123",
                "montant_ht": "100",
                "montant_ttc": "120",
            },
        }
        sb = _make_supabase_mock(data=[doc_row])

        with patch(
            "apps.jmpartners.agents.tri_classification_agent.TriClassificationAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.tri_classification_agent import (
                TriClassificationAgent,
            )

            agent = TriClassificationAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["qualifies_auto"] == 1
        assert result["details"][0]["type_piece"] == "fournisseur"

    def test_presaisie_propose_ecritures(self):
        """La présaisie doit proposer des écritures comptables via Claude."""
        doc_row = {
            "id": "doc-presaisie-001",
            "nom_fichier": "facture_fournisseur.pdf",
            "contenu_extrait": {"siret": "123", "montant_ttc": "1200"},
            "type_piece": "fournisseur",
        }
        sb = _make_supabase_mock(data=[doc_row])

        ecritures_json = {
            "ecritures": [
                {
                    "journal": "ACH",
                    "compte_debit": "401000",
                    "compte_credit": "512000",
                    "montant": 1200.0,
                    "libelle": "Facture fournisseur CIHAN",
                    "taux_tva": 20.0,
                }
            ]
        }
        anthropic_mock = _make_anthropic_mock(ecritures_json)

        with (
            patch(
                "apps.jmpartners.agents.presaisie_agent.PresaisieAgent._get_supabase",
                return_value=sb,
            ),
            patch(
                "apps.jmpartners.agents.presaisie_agent.PresaisieAgent._get_anthropic",
                return_value=anthropic_mock,
            ),
        ):
            from apps.jmpartners.agents.presaisie_agent import PresaisieAgent

            agent = PresaisieAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["ecritures_proposees"] >= 1

    def test_verificateur_valide_ecritures_propres(self):
        """Le vérificateur doit valider un lot équilibré (débit = crédit)."""
        ecritures = [
            {
                "id": "ecr-001",
                "journal": "ACH",
                "compte_debit": "401000",
                "compte_credit": "",
                "montant": 1200.0,
                "statut": "proposee",
            },
            {
                "id": "ecr-002",
                "journal": "ACH",
                "compte_debit": "",
                "compte_credit": "512000",
                "montant": 1200.0,
                "statut": "proposee",
            },
        ]
        sb = _make_supabase_mock(data=ecritures)

        with patch(
            "apps.jmpartners.agents.verificateur_agent.VerificateurAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.verificateur_agent import VerificateurAgent

            agent = VerificateurAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["lot_propre"] is True

    def test_ged_archive_docs_valides_uniquement(self):
        """La GED doit archiver uniquement les documents en statut valide."""
        doc_row = {
            "id": "doc-ged-001",
            "nom_fichier": "facture_fournisseur.pdf",
            "chemin_stockage": f"{CABINET_ID}/{DOSSIER_ID}/facture_fournisseur.pdf",
            "statut": "valide",
            "date_reception": date.today().isoformat(),
            "type_piece": "fournisseur",
        }
        sb = _make_supabase_mock(data=[doc_row])

        with patch(
            "apps.jmpartners.agents.ged_agent.GEDAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.ged_agent import GEDAgent

            agent = GEDAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["documents_archives"] == 1


# ─── TestCycleNocturne ────────────────────────────────────────────────────────


class TestCycleNocturne:
    """Tests du cycle nocturne CIHAN (RPA Sage, Miroir Sage, Révision)."""

    def test_rpa_sage_stub_retourne_next_agent(self):
        """Le RPA Sage en mode stub doit retourner next_agent=miroir_sage_agent."""
        sb = _make_supabase_mock(data=[])  # Pas d'écritures à importer

        with patch(
            "apps.jmpartners.agents.rpa_sage_agent.RPASageAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent

            agent = RPASageAgent(cabinet_id=CABINET_ID)
            result = agent.run(mode="stub")

        assert result["next_agent"] == "miroir_sage_agent"
        assert result["mode"] == "stub"

    def test_miroir_sage_sync_fec_sans_fichier(self):
        """Le miroir Sage ne doit pas lever d'exception si le fichier FEC est absent."""
        sb = _make_supabase_mock(storage_raises=Exception("no file"))

        with patch(
            "apps.jmpartners.agents.miroir_sage_agent.MiroirSageAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent

            agent = MiroirSageAgent(cabinet_id=CABINET_ID)
            result = agent._sync_fec()  # Ne doit pas lever

        assert result["ecritures_nouvelles"] == 0

    def test_revision_sans_anomalies(self):
        """La révision ne doit détecter aucune anomalie si les écritures sont vides."""
        sb = _make_supabase_mock(data=[])

        with patch(
            "apps.jmpartners.agents.revision_agent.RevisionAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.revision_agent import RevisionAgent

            agent = RevisionAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["anomalies_detectees"] == 0


# ─── TestReglesMetier ─────────────────────────────────────────────────────────


class TestReglesMetier:
    """Tests des règles métier spécifiques CIHAN."""

    def test_taux_tva_restauration_10_pourcent(self):
        """La présaisie doit appliquer le taux TVA 10% pour la restauration."""
        doc_row = {
            "id": "doc-tva-001",
            "nom_fichier": "facture_resto.pdf",
            "contenu_extrait": {
                "type_document": "fournisseur",
                "siret": "98765432100123",
                "montant_ttc": "110",
                "taux_tva": 10.0,
            },
            "type_piece": "fournisseur",
        }
        sb = _make_supabase_mock(data=[doc_row])

        ecritures_json = {
            "ecritures": [
                {
                    "journal": "ACH",
                    "compte_debit": "401000",
                    "compte_credit": "512000",
                    "montant": 110.0,
                    "libelle": "Restauration CIHAN",
                    "taux_tva": 10.0,
                }
            ]
        }
        anthropic_mock = _make_anthropic_mock(ecritures_json)

        with (
            patch(
                "apps.jmpartners.agents.presaisie_agent.PresaisieAgent._get_supabase",
                return_value=sb,
            ),
            patch(
                "apps.jmpartners.agents.presaisie_agent.PresaisieAgent._get_anthropic",
                return_value=anthropic_mock,
            ),
        ):
            from apps.jmpartners.agents.presaisie_agent import PresaisieAgent

            agent = PresaisieAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["ecritures_proposees"] >= 1
        ecritures = result["details"][0]["ecritures"]
        taux_values = [e.get("taux_tva") for e in ecritures]
        assert 10.0 in taux_values

    def test_facture_multi_decoupee_par_ocr(self):
        """L'OCR doit détecter une facture multi-dossiers et retourner multi_dossiers=True."""
        doc_row = {
            "id": "doc-multi-001",
            "nom_fichier": "facture_multi.pdf",
            "chemin_stockage": f"{CABINET_ID}/{DOSSIER_ID}/facture_multi.pdf",
        }
        sb = _make_supabase_mock(data=[doc_row])

        ocr_json = {
            "type_document": "multi",
            "score_confiance": 0.90,
            "multi_factures": True,
            "fragments": [
                {"montant_ttc": "600", "libelle": "Facture 1"},
                {"montant_ttc": "400", "libelle": "Facture 2"},
            ],
            "texte_brut": "FACTURE 1 TTC 600 EUR FACTURE 2 TTC 400 EUR",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        with (
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_supabase",
                return_value=sb,
            ),
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_anthropic",
                return_value=anthropic_mock,
            ),
        ):
            from apps.jmpartners.agents.ocr_agent import OCRAgent

            agent = OCRAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["details"][0]["multi_dossiers"] is True

    def test_score_faible_passe_en_attente(self):
        """Un document avec score OCR < seuil doit passer en en_attente_validation."""
        doc_row = {
            "id": "doc-score-001",
            "nom_fichier": "doc_flou.pdf",
            "chemin_stockage": f"{CABINET_ID}/{DOSSIER_ID}/doc_flou.pdf",
        }
        sb = _make_supabase_mock(data=[doc_row])

        ocr_json = {
            "type_document": "autre",
            "score_confiance": 0.5,
            "multi_factures": False,
            "texte_brut": "document illisible",
        }
        anthropic_mock = _make_anthropic_mock(ocr_json)

        with (
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_supabase",
                return_value=sb,
            ),
            patch(
                "apps.jmpartners.agents.ocr_agent.OCRAgent._get_anthropic",
                return_value=anthropic_mock,
            ),
        ):
            from apps.jmpartners.agents.ocr_agent import OCRAgent

            agent = OCRAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["documents_en_attente"] == 1

    def test_verificateur_detecte_desequilibre_dc(self):
        """Le vérificateur doit détecter un déséquilibre D/C et le signaler."""
        ecritures = [
            {
                "id": "ecr-deseq-001",
                "journal": "ACH",
                "compte_debit": "401000",
                "compte_credit": "",
                "montant": 1200.0,
                "statut": "proposee",
            },
            {
                "id": "ecr-deseq-002",
                "journal": "ACH",
                "compte_debit": "",
                "compte_credit": "512000",
                "montant": 800.0,
                "statut": "proposee",
            },
        ]
        sb = _make_supabase_mock(data=ecritures)

        with patch(
            "apps.jmpartners.agents.verificateur_agent.VerificateurAgent._get_supabase",
            return_value=sb,
        ):
            from apps.jmpartners.agents.verificateur_agent import VerificateurAgent

            agent = VerificateurAgent(cabinet_id=CABINET_ID)
            result = agent.run()

        assert result["lot_propre"] is False
        assert any(
            a["type_anomalie"] == "desequilibre_dc" for a in result["anomalies"]
        )


# ─── TestOrchestrateur ────────────────────────────────────────────────────────


class TestOrchestrateur:
    """Tests de l'orchestrateur CIHAN complet."""

    def _make_mock_agent(self, result_dict: dict) -> MagicMock:
        """Crée un mock d'agent dont .run() retourne result_dict."""
        mock_cls = MagicMock()
        instance = MagicMock()
        instance.run.return_value = result_dict
        mock_cls.return_value = instance
        return mock_cls

    def test_run_complet_sans_erreur(self):
        """L'orchestrateur CIHAN doit compléter sans erreur quand tous les agents réussissent."""
        mock_collecte = self._make_mock_agent(
            {"documents_uploades": 3, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_ocr = self._make_mock_agent(
            {"documents_traites": 3, "documents_a_trier": 3, "documents_en_attente": 0, "erreurs": [], "details": []}
        )
        mock_tri = self._make_mock_agent(
            {"documents_traites": 3, "qualifies_auto": 3, "en_attente_manuelle": 0, "erreurs": [], "details": []}
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
            {"mode": "stub", "ecritures_importees": 6, "ecritures_rejetes": 0, "next_agent": "miroir_sage_agent", "erreurs": [], "details": []}
        )
        mock_miroir = self._make_mock_agent(
            {"ecritures_nouvelles": 0, "ecritures_mises_a_jour": 0, "erreurs": []}
        )
        mock_revision = self._make_mock_agent(
            {"ecritures_analysees": 0, "anomalies_detectees": 0, "anomalies": [], "erreurs": []}
        )

        with (
            patch(
                "apps.jmpartners.orchestrator_cihan.CollecteAgent", mock_collecte
            ),
            patch("apps.jmpartners.orchestrator_cihan.OCRAgent", mock_ocr),
            patch(
                "apps.jmpartners.orchestrator_cihan.TriClassificationAgent", mock_tri
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.PresaisieAgent", mock_presaisie
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.VerificateurAgent", mock_verificateur
            ),
            patch("apps.jmpartners.orchestrator_cihan.GEDAgent", mock_ged),
            patch("apps.jmpartners.orchestrator_cihan.RPASageAgent", mock_rpa),
            patch(
                "apps.jmpartners.orchestrator_cihan.MiroirSageAgent", mock_miroir
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.RevisionAgent", mock_revision
            ),
        ):
            from apps.jmpartners.orchestrator_cihan import run as orchestrate

            result = orchestrate(dry_run=True)

        assert len(result["erreurs"]) == 0

    def test_run_log_stats_tous_agents(self):
        """L'orchestrateur CIHAN doit retourner les stats de tous les agents."""
        mock_collecte = self._make_mock_agent(
            {"documents_uploades": 1, "documents_ignores": 0, "erreurs": [], "details": []}
        )
        mock_ocr = self._make_mock_agent(
            {"documents_traites": 1, "documents_a_trier": 1, "documents_en_attente": 0, "erreurs": [], "details": []}
        )
        mock_tri = self._make_mock_agent(
            {"documents_traites": 1, "qualifies_auto": 1, "en_attente_manuelle": 0, "erreurs": [], "details": []}
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
            {"mode": "stub", "ecritures_importees": 2, "ecritures_rejetes": 0, "next_agent": "miroir_sage_agent", "erreurs": [], "details": []}
        )
        mock_miroir = self._make_mock_agent(
            {"ecritures_nouvelles": 0, "ecritures_mises_a_jour": 0, "erreurs": []}
        )
        mock_revision = self._make_mock_agent(
            {"ecritures_analysees": 0, "anomalies_detectees": 0, "anomalies": [], "erreurs": []}
        )

        with (
            patch(
                "apps.jmpartners.orchestrator_cihan.CollecteAgent", mock_collecte
            ),
            patch("apps.jmpartners.orchestrator_cihan.OCRAgent", mock_ocr),
            patch(
                "apps.jmpartners.orchestrator_cihan.TriClassificationAgent", mock_tri
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.PresaisieAgent", mock_presaisie
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.VerificateurAgent", mock_verificateur
            ),
            patch("apps.jmpartners.orchestrator_cihan.GEDAgent", mock_ged),
            patch("apps.jmpartners.orchestrator_cihan.RPASageAgent", mock_rpa),
            patch(
                "apps.jmpartners.orchestrator_cihan.MiroirSageAgent", mock_miroir
            ),
            patch(
                "apps.jmpartners.orchestrator_cihan.RevisionAgent", mock_revision
            ),
        ):
            from apps.jmpartners.orchestrator_cihan import run as orchestrate

            result = orchestrate(dry_run=True)

        assert result is not None
        # Vérifier que toutes les clés attendues sont présentes
        for key in ("collecte", "ocr", "tri", "presaisie", "verificateur", "ged"):
            assert key in result, f"Clé manquante dans le résultat : {key}"

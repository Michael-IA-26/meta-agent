"""Tests unitaires — couche abstraction multi-backend comptable."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RPA_MOD = "apps.jmpartners.agents.rpa_sage_agent.RPASageAgent"
_MIROIR_MOD = "apps.jmpartners.agents.miroir_sage_agent.MiroirSageAgent"


def _mock_rpa_result(
    ecritures_a_saisir: int = 3,
    ecritures_saisies: int = 0,
    erreurs: list[str] | None = None,
) -> MagicMock:
    m = MagicMock()
    m.run.return_value = {
        "mode": "stub",
        "ecritures_a_saisir": ecritures_a_saisir,
        "ecritures_saisies": ecritures_saisies,
        "erreurs": erreurs or [],
        "next_agent": "miroir_sage_agent",
    }
    return m


def _mock_sync_fec_result(date_sync: str = "2026-06-02T00:00:00+00:00") -> dict:
    return {
        "ecritures_importees": 10,
        "ecritures_nouvelles": 10,
        "date_sync": date_sync,
    }


# ---------------------------------------------------------------------------
# base.py — TypedDicts
# ---------------------------------------------------------------------------

class TestEcritureComptable:
    def test_required_fields(self) -> None:
        from apps.jmpartners.backends.base import EcritureComptable
        ec: EcritureComptable = {
            "document_id": "doc-001",
            "dossier_id": "dos-001",
            "journal": "ACH",
            "compte_debit": "607000",
            "compte_credit": "401000",
            "tiers": "Fournisseur SA",
            "libelle": "Achat Metro mai 2026",
            "montant_ht": 1000.0,
            "montant_tva": 200.0,
            "montant_ttc": 1200.0,
            "taux_tva": 20.0,
            "statut": "a_saisir",
        }
        assert ec["journal"] == "ACH"
        assert ec["statut"] == "a_saisir"
        assert ec["tiers"] == "Fournisseur SA"

    def test_tiers_none(self) -> None:
        from apps.jmpartners.backends.base import EcritureComptable
        ec: EcritureComptable = {
            "document_id": "doc-002",
            "dossier_id": "dos-001",
            "journal": "OD",
            "compte_debit": "512000",
            "compte_credit": "411000",
            "tiers": None,
            "libelle": "OD régularisation",
            "montant_ht": 500.0,
            "montant_tva": 0.0,
            "montant_ttc": 500.0,
            "taux_tva": None,
            "statut": "saisie",
        }
        assert ec["tiers"] is None


class TestSyncResult:
    def test_structure(self) -> None:
        from apps.jmpartners.backends.base import SyncResult
        sr: SyncResult = {
            "backend": "sage",
            "ecritures_envoyees": 5,
            "ecritures_ok": 5,
            "ecritures_erreur": 0,
            "erreurs": [],
        }
        assert sr["backend"] == "sage"
        assert sr["erreurs"] == []


# ---------------------------------------------------------------------------
# SageBackend
# ---------------------------------------------------------------------------

class TestSageBackend:
    def test_implements_abc(self) -> None:
        """SageBackend peut être instancié (ABC satisfait)."""
        from apps.jmpartners.backends.sage_backend import SageBackend
        backend = SageBackend()
        assert backend is not None

    @patch("apps.jmpartners.agents.rpa_sage_agent.RPASageAgent", return_value=_mock_rpa_result(3, 0))
    def test_sync_ecritures_returns_sync_result(self, mock_rpa: MagicMock) -> None:
        from apps.jmpartners.backends.base import EcritureComptable
        from apps.jmpartners.backends.sage_backend import SageBackend

        ecritures: list[EcritureComptable] = [
            {
                "document_id": f"doc-{i:03d}",
                "dossier_id": "dos-001",
                "journal": "ACH",
                "compte_debit": "607000",
                "compte_credit": "401000",
                "tiers": None,
                "libelle": f"Ligne {i}",
                "montant_ht": 100.0,
                "montant_tva": 20.0,
                "montant_ttc": 120.0,
                "taux_tva": 20.0,
                "statut": "a_saisir",
            }
            for i in range(3)
        ]
        result = SageBackend().sync_ecritures(ecritures)
        assert result["backend"] == "sage"
        assert result["ecritures_envoyees"] == 3
        assert isinstance(result["erreurs"], list)

    @patch("apps.jmpartners.agents.miroir_sage_agent.MiroirSageAgent")
    def test_get_fec_returns_fec_data(self, mock_miroir_cls: MagicMock) -> None:
        mock_miroir_cls.return_value._sync_fec.return_value = _mock_sync_fec_result()
        from apps.jmpartners.backends.sage_backend import SageBackend

        fec = SageBackend().get_fec("dos-001")
        assert "lignes" in fec
        assert "date_export" in fec
        assert "hash_md5" in fec
        assert isinstance(fec["lignes"], list)

    @patch("apps.jmpartners.agents.rpa_sage_agent.RPASageAgent")
    def test_health_check_true_on_success(self, mock_rpa: MagicMock) -> None:
        from apps.jmpartners.backends.sage_backend import SageBackend
        assert SageBackend().health_check() is True

    @patch("apps.jmpartners.agents.rpa_sage_agent.RPASageAgent", side_effect=ImportError("missing"))
    def test_health_check_false_on_error(self, mock_rpa: MagicMock) -> None:
        from apps.jmpartners.backends.sage_backend import SageBackend
        assert SageBackend().health_check() is False


# ---------------------------------------------------------------------------
# Stubs — NotImplementedError
# ---------------------------------------------------------------------------

class TestPennylaneBackend:
    def test_sync_ecritures_raises(self) -> None:
        from apps.jmpartners.backends.pennylane_backend import PennylaneBackend
        with pytest.raises(NotImplementedError, match="Sprint 4"):
            PennylaneBackend().sync_ecritures([])

    def test_get_fec_raises(self) -> None:
        from apps.jmpartners.backends.pennylane_backend import PennylaneBackend
        with pytest.raises(NotImplementedError):
            PennylaneBackend().get_fec("dos-001")

    def test_health_check_raises(self) -> None:
        from apps.jmpartners.backends.pennylane_backend import PennylaneBackend
        with pytest.raises(NotImplementedError):
            PennylaneBackend().health_check()


class TestMyUnisoftBackend:
    def test_sync_ecritures_raises(self) -> None:
        from apps.jmpartners.backends.myunisoft_backend import MyUnisoftBackend
        with pytest.raises(NotImplementedError, match="Sprint 5"):
            MyUnisoftBackend().sync_ecritures([])


class TestACDBackend:
    def test_sync_ecritures_raises(self) -> None:
        from apps.jmpartners.backends.acd_backend import ACDBackend
        with pytest.raises(NotImplementedError):
            ACDBackend().sync_ecritures([])


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_sage_returns_sage_backend(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        from apps.jmpartners.backends.sage_backend import SageBackend
        backend = get_backend("sage")
        assert isinstance(backend, SageBackend)

    def test_pennylane_returns_pennylane_backend(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        from apps.jmpartners.backends.pennylane_backend import PennylaneBackend
        backend = get_backend("pennylane")
        assert isinstance(backend, PennylaneBackend)

    def test_myunisoft_returns_myunisoft_backend(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        from apps.jmpartners.backends.myunisoft_backend import MyUnisoftBackend
        backend = get_backend("myunisoft")
        assert isinstance(backend, MyUnisoftBackend)

    def test_acd_returns_acd_backend(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        from apps.jmpartners.backends.acd_backend import ACDBackend
        backend = get_backend("acd")
        assert isinstance(backend, ACDBackend)

    def test_unknown_raises_value_error(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        with pytest.raises(ValueError, match="Backend inconnu"):
            get_backend("unknown")

    def test_error_message_lists_valid_backends(self) -> None:
        from apps.jmpartners.backends.factory import get_backend
        with pytest.raises(ValueError) as exc_info:
            get_backend("cegid")
        assert "sage" in str(exc_info.value)
        assert "pennylane" in str(exc_info.value)

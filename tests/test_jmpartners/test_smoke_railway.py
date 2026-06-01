"""Smoke tests Railway — marqués @pytest.mark.smoke, exécutés uniquement en CI."""
import os

import pytest

pytestmark = pytest.mark.smoke


def test_health_env_vars_presents():
    """Variables d'env critiques définies (pas nécessairement valides)."""
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ANTHROPIC_API_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    assert not missing, f"Variables manquantes : {missing}"


def test_import_orchestrator():
    from apps.jmpartners.orchestrator import OrchestratorResult, run  # noqa: F401

    assert callable(run)


def test_import_tous_agents():
    """Vérifier que les 13 agents s'importent sans erreur."""
    from apps.jmpartners.agents.collecte_agent import CollecteAgent  # noqa: F401
    from apps.jmpartners.agents.fnp_fae_agent import FNPFAEAgent  # noqa: F401
    from apps.jmpartners.agents.ged_agent import GEDAgent  # noqa: F401
    from apps.jmpartners.agents.lettrage_agent import LettrageAgent  # noqa: F401
    from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent  # noqa: F401
    from apps.jmpartners.agents.ocr_agent import OCRAgent  # noqa: F401
    from apps.jmpartners.agents.presaisie_agent import PresaisieAgent  # noqa: F401
    from apps.jmpartners.agents.revision_agent import RevisionAgent  # noqa: F401
    from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent  # noqa: F401
    from apps.jmpartners.agents.tri_classification_agent import (  # noqa: F401
        TriClassificationAgent,
    )
    from apps.jmpartners.agents.verificateur_agent import (
        VerificateurAgent,  # noqa: F401
    )
    assert True


def test_apscheduler_setup_nocturne():
    from apscheduler.schedulers.background import BackgroundScheduler

    from apps.jmpartners.orchestrator import setup_nocturne_jobs

    scheduler = BackgroundScheduler()
    setup_nocturne_jobs(scheduler)
    assert len(scheduler.get_jobs()) == 7

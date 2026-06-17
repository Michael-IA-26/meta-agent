import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from apps.jmpartners.echeance_agent import EcheanceAgent


def test_get_echeance_returns_dict():
    agent = EcheanceAgent()
    result = agent.get_echeance("dossier-1")
    assert result["dossier_id"] == "dossier-1"


def test_echeance_calculates_late_fee():
    agent = EcheanceAgent()
    fee = agent.compute_late_fee(1000.0)
    assert fee == 100.0

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from apps.jmpartners.relance_handler import RelanceHandler


def test_send_relance_returns_string():
    handler = RelanceHandler()
    result = handler.send_relance("client@example.com")
    assert "relance" in result


def test_relance_sends_second_reminder():
    handler = RelanceHandler()
    result = handler.send_second_reminder("client@example.com")
    assert "2" in result

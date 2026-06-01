"""Fixtures partagées pour les tests JM Partners."""
import pytest
from unittest.mock import MagicMock


def make_supabase_mock(rows=None):
    """Mock Supabase avec chaîne fluide complète."""
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
    return sb


@pytest.fixture
def supabase_mock():
    return make_supabase_mock()


@pytest.fixture
def dossier_id_cihan():
    return "cihan-0000-0000-0000-dossier00001"


@pytest.fixture
def contact_id_cihan():
    return "cihan-0000-0000-0000-contact000001"

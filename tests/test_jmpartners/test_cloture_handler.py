"""Tests pour apps.jmpartners.agents.cloture_handler."""

from datetime import date
from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.cloture_handler import (
    ClotureHandler,
    _is_dernier_jour_ouvre,
)

# ─── _is_dernier_jour_ouvre ──────────────────────────────────────────────────


def test_dernier_jour_ouvre_vendredi():
    # Trouver un vendredi qui est le dernier jour ouvré d'un mois
    # Janvier 2025 se termine le 31 (vendredi)
    assert _is_dernier_jour_ouvre(date(2025, 1, 31)) is True


def test_pas_dernier_jour_ouvre_milieu_de_mois():
    assert _is_dernier_jour_ouvre(date(2025, 1, 15)) is False


def test_dernier_calendaire_weekend_retourne_vendredi():
    # Août 2025 : le 31 est un dimanche, le dernier jour ouvré est le 29 (vendredi)
    assert _is_dernier_jour_ouvre(date(2025, 8, 29)) is True
    assert _is_dernier_jour_ouvre(date(2025, 8, 31)) is False


def test_pas_dernier_jour_ouvre_premier_du_mois():
    assert _is_dernier_jour_ouvre(date(2025, 5, 1)) is False


# ─── ClotureHandler.run — skip si pas fin de mois ────────────────────────────


def test_run_skip_si_pas_fin_de_mois():
    with patch(
        "apps.jmpartners.agents.cloture_handler._is_dernier_jour_ouvre",
        return_value=False,
    ):
        handler = ClotureHandler(cabinet_id="cab-1")
        result = handler.run()

    assert result["statut"] == "skip"
    assert result["dossiers_clotures"] == []
    assert result["cabinet_id"] == "cab-1"


# ─── ClotureHandler.run — aucun dossier en cours ─────────────────────────────


def test_run_aucun_dossier_en_cours():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

    with (
        patch(
            "apps.jmpartners.agents.cloture_handler._is_dernier_jour_ouvre",
            return_value=True,
        ),
        patch(
            "apps.jmpartners.agents.cloture_handler.create_client",
            return_value=mock_sb,
        ),
    ):
        handler = ClotureHandler(cabinet_id="cab-1")
        result = handler.run()

    assert result["statut"] == "aucun_dossier"
    assert result["dossiers_clotures"] == []


# ─── ClotureHandler.run — dossiers clôturés et notification Telegram ─────────


def test_run_cloture_dossiers_et_telegram():
    mock_sb = MagicMock()

    dossiers_data = [{"id": "dos-1"}, {"id": "dos-2"}]

    def make_chain(*args, **kwargs):
        m = MagicMock()
        m.execute.return_value.data = dossiers_data
        m.eq.return_value = m
        m.select.return_value = m
        m.update.return_value = m
        return m

    mock_sb.table.return_value = make_chain()

    with (
        patch(
            "apps.jmpartners.agents.cloture_handler._is_dernier_jour_ouvre",
            return_value=True,
        ),
        patch(
            "apps.jmpartners.agents.cloture_handler.create_client",
            return_value=mock_sb,
        ),
        patch(
            "apps.jmpartners.agents.cloture_handler.httpx.post"
        ) as mock_post,
    ):
        mock_post.return_value.raise_for_status = MagicMock()
        handler = ClotureHandler(cabinet_id="cab-2")
        handler._fetch_dossiers_en_cours = MagicMock(return_value=dossiers_data)
        handler._cloture_dossier = MagicMock(return_value=True)
        result = handler.run()

    assert result["statut"] == "ok"
    assert set(result["dossiers_clotures"]) == {"dos-1", "dos-2"}
    assert result["cabinet_id"] == "cab-2"


# ─── ClotureHandler._cloture_dossier — erreur Supabase ───────────────────────


def test_cloture_dossier_erreur_supabase():
    mock_sb = MagicMock()
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("DB error")

    with patch(
        "apps.jmpartners.agents.cloture_handler.create_client",
        return_value=mock_sb,
    ):
        handler = ClotureHandler(cabinet_id="cab-3")
        handler._supabase = mock_sb
        result = handler._cloture_dossier("dos-err")

    assert result is False


# ─── ClotureHandler._send_telegram — non configuré ───────────────────────────


def test_send_telegram_non_configure():
    with patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
    ):
        handler = ClotureHandler(cabinet_id="cab-4")
        result = handler._send_telegram("test")

    assert result is False


# ─── ClotureHandler._send_telegram — erreur réseau ───────────────────────────


def test_send_telegram_erreur_reseau():
    with (
        patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "123"},
        ),
        patch(
            "apps.jmpartners.agents.cloture_handler.httpx.post",
            side_effect=Exception("network"),
        ),
    ):
        handler = ClotureHandler(cabinet_id="cab-5")
        result = handler._send_telegram("test")

    assert result is False


# ─── ClotureHandler.run — résultat contient mois et timestamp ────────────────


def test_run_result_structure():
    with patch(
        "apps.jmpartners.agents.cloture_handler._is_dernier_jour_ouvre",
        return_value=False,
    ):
        handler = ClotureHandler(cabinet_id="cab-x")
        result = handler.run()

    assert "mois" in result
    assert "timestamp" in result
    assert result["mois"] == date.today().strftime("%Y-%m")

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from unittest.mock import MagicMock, patch

from apps.jmpartners.document_analyzer import MAX_IMAGE_PX, MAX_PAGES, DocumentAnalyzer


def test_extraction_request_has_cache_control():
    """The static system prompt message must have cache_control={type:'ephemeral'}."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"analyse": "test"}')]
    )
    analyzer = DocumentAnalyzer(anthropic_client=mock_client)
    analyzer.analyze(
        content=b"fake content", content_type="text/plain", content_hash="abc123"
    )
    call_kwargs = mock_client.messages.create.call_args.kwargs
    system = call_kwargs.get("system", [])
    has_cache_control = any(
        isinstance(block, dict)
        and block.get("cache_control", {}).get("type") == "ephemeral"
        for block in system
    )
    assert has_cache_control, (
        "System prompt must include a cache_control ephemeral block"
    )


def test_pdf_truncated_to_max_pages(tmp_path):
    """A PDF with more than MAX_PAGES pages must be truncated."""
    from apps.jmpartners.document_analyzer import truncate_pdf

    assert MAX_PAGES > 0
    pages = [b"page" + bytes([i]) for i in range(MAX_PAGES + 3)]
    result = truncate_pdf(pages)
    assert len(result) <= MAX_PAGES


def test_oversized_image_resized():
    """An image larger than MAX_IMAGE_PX must be resized."""
    from apps.jmpartners.document_analyzer import resize_image_if_needed

    with patch("apps.jmpartners.document_analyzer.Image") as mock_pil:
        mock_img = MagicMock()
        mock_img.size = (MAX_IMAGE_PX + 500, MAX_IMAGE_PX + 500)
        mock_pil.open.return_value = mock_img
        mock_img.thumbnail = MagicMock()
        mock_img.save = MagicMock()
        import io

        mock_output = io.BytesIO(b"resized")
        with patch(
            "apps.jmpartners.document_analyzer.io.BytesIO", return_value=mock_output
        ):
            resize_image_if_needed(b"fake_image_bytes")
        mock_img.thumbnail.assert_called_once()


def test_skip_analysis_when_hash_cached():
    """If content_hash already has analyse_ia, do NOT call Claude."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"analyse_ia": "Facture existante"}]
    )
    analyzer = DocumentAnalyzer(anthropic_client=mock_client, db_client=mock_db)
    result = analyzer.analyze(
        content=b"fake", content_type="text/plain", content_hash="known_hash"
    )
    mock_client.messages.create.assert_not_called()
    assert result == "Facture existante"

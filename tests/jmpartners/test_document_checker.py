import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from apps.jmpartners.document_checker import DocumentChecker


def test_pdf_is_valid():
    checker = DocumentChecker()
    assert checker.is_valid("invoice.pdf") is True


def test_txt_is_invalid():
    checker = DocumentChecker()
    assert checker.is_valid("notes.txt") is False


def test_document_checker_validates_pdf_extension():
    checker = DocumentChecker()
    assert checker.is_valid("rapport.PDF") is True  # case-insensitive

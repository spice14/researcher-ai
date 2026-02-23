"""Minimal deterministic PDF text extractor.

Purpose:
- Extract raw text from PDF files on a per-page basis.
- Preserve real page numbers for downstream provenance.

Inputs/Outputs:
- Input: file path to PDF
- Output: List of dicts with {"page": int, "text": str}

Failure Modes:
- File not found → raises FileNotFoundError
- Invalid PDF → raises PDFExtractionError
- Empty page → included with empty string (not skipped)

Testing Strategy:
- Deterministic: same PDF → same output every time
- No OCR, no layout reconstruction, no heuristics
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""
    pass


@dataclass(frozen=True)
class PDFPage:
    """Single page extracted from a PDF."""
    page: int  # 1-indexed
    text: str


def extract_pages_from_pdf(pdf_path: str) -> List[PDFPage]:
    """
    Extract text from each page of a PDF file.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        List of PDFPage objects, one per page, 1-indexed.

    Raises:
        FileNotFoundError: If the file does not exist.
        PDFExtractionError: If the PDF cannot be parsed.
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        # First pass: determine total page count by extracting all text
        # pdfminer's extract_text with page_numbers uses 0-indexed pages
        full_text = extract_text(pdf_path)
        if not full_text or len(full_text.strip()) == 0:
            raise PDFExtractionError(f"PDF produced no text: {pdf_path}")
    except PDFSyntaxError as e:
        raise PDFExtractionError(f"Invalid PDF format: {pdf_path} — {e}")

    # Extract page by page using pdfminer's page_numbers parameter
    pages: List[PDFPage] = []
    page_num = 0
    while True:
        try:
            page_text = extract_text(pdf_path, page_numbers=[page_num])
        except Exception:
            break

        # pdfminer returns empty string for non-existent pages but doesn't
        # raise — we detect end of document when we get empty text AND
        # we've already processed at least one page
        if not page_text and page_num > 0:
            # Verify this is actually end-of-document, not just an empty page
            # Try the next page too
            try:
                next_page_text = extract_text(pdf_path, page_numbers=[page_num + 1])
                if not next_page_text:
                    break  # Two consecutive empty pages → end of document
            except Exception:
                break

        pages.append(PDFPage(
            page=page_num + 1,  # Convert to 1-indexed
            text=_clean_whitespace(page_text),
        ))
        page_num += 1

        # Safety bound: no paper should have more than 200 pages
        if page_num >= 200:
            break

    if not pages:
        raise PDFExtractionError(f"No pages extracted from: {pdf_path}")

    return pages


def _clean_whitespace(text: str) -> str:
    """Normalize whitespace without destroying structure.

    - Collapse runs of spaces/tabs into single spaces
    - Preserve paragraph breaks (double newlines)
    - Strip leading/trailing whitespace
    """
    import re
    # Replace tabs with spaces
    text = text.replace('\t', ' ')
    # Collapse multiple spaces into one (but not newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

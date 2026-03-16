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

import logging
import os
from dataclasses import dataclass
from typing import List

from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError

logger = logging.getLogger(__name__)

_HAS_PYMUPDF = False
try:
    import pymupdf
    _HAS_PYMUPDF = True
except ImportError:
    pass


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

    Uses pymupdf (MuPDF) as primary extractor for better word boundary
    detection. Falls back to pdfminer if pymupdf is unavailable or fails.

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

    if _HAS_PYMUPDF:
        try:
            return _extract_with_pymupdf(pdf_path)
        except Exception as e:
            logger.warning("pymupdf extraction failed, falling back to pdfminer: %s", e)

    return _extract_with_pdfminer(pdf_path)


def _extract_with_pymupdf(pdf_path: str) -> List[PDFPage]:
    """Extract pages using pymupdf (handles spaceless PDFs correctly)."""
    doc = pymupdf.open(pdf_path)
    try:
        if doc.page_count == 0:
            raise PDFExtractionError(f"PDF has no pages: {pdf_path}")

        pages: List[PDFPage] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            pages.append(PDFPage(
                page=page_num + 1,
                text=_clean_whitespace(text),
            ))

        if not pages or all(not p.text.strip() for p in pages):
            raise PDFExtractionError(f"PDF produced no text: {pdf_path}")

        return pages
    finally:
        doc.close()


def _extract_with_pdfminer(pdf_path: str) -> List[PDFPage]:
    """Extract pages using pdfminer (legacy fallback)."""
    try:
        full_text = extract_text(pdf_path)
        if not full_text or len(full_text.strip()) == 0:
            raise PDFExtractionError(f"PDF produced no text: {pdf_path}")
    except PDFSyntaxError as e:
        raise PDFExtractionError(f"Invalid PDF format: {pdf_path} — {e}")

    pages: List[PDFPage] = []
    page_num = 0
    while True:
        try:
            page_text = extract_text(pdf_path, page_numbers=[page_num])
        except Exception:
            break

        if not page_text and page_num > 0:
            try:
                next_page_text = extract_text(pdf_path, page_numbers=[page_num + 1])
                if not next_page_text:
                    break
            except Exception:
                break

        pages.append(PDFPage(
            page=page_num + 1,
            text=_clean_whitespace(page_text),
        ))
        page_num += 1

        if page_num >= 200:
            break

    if not pages:
        raise PDFExtractionError(f"No pages extracted from: {pdf_path}")

    return pages


def _repair_spaceless_text(text: str) -> str:
    """Detect and repair text where pdfminer concatenated words without spaces.

    Some PDFs (especially LaTeX-generated arXiv papers) produce output like
    "ProximalPolicyOptimizationAlgorithms" instead of proper words.

    Detection: if the ratio of spaces to non-space characters is very low
    AND there are long runs of lowercase-followed-by-uppercase (camelCase),
    we insert spaces at word boundaries.
    """
    import re

    # Only process lines that look spaceless (long stretches without spaces)
    lines = text.split('\n')
    repaired_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            repaired_lines.append(line)
            continue

        # Check if line is spaceless: long (>40 chars) with very few spaces
        non_space = len(stripped.replace(' ', ''))
        space_count = stripped.count(' ')

        if non_space > 40 and space_count < non_space * 0.05:
            # Insert space before uppercase preceded by lowercase: "wordWord" -> "word Word"
            repaired = re.sub(r'([a-z])([A-Z])', r'\1 \2', stripped)
            # Insert space before sequences of digits preceded by letters: "model28" -> "model 28"
            repaired = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', repaired)
            # Insert space after digits followed by letters: "28BLEU" -> "28 BLEU"
            repaired = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', repaired)
            # Fix common ligature artifacts from pdfminer
            repaired = repaired.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff')
            repaired_lines.append(repaired)
        else:
            # Fix ligatures even in normal lines
            fixed = stripped.replace('ﬁ', 'fi').replace('ﬂ', 'fl').replace('ﬀ', 'ff')
            repaired_lines.append(fixed)

    return '\n'.join(repaired_lines)


def _strip_arxiv_header(text: str) -> str:
    """Remove arXiv metadata header that appears as single characters per line.

    arXiv PDFs often start with character-per-line metadata like:
    7\\n1\\n0\\n2\\n\\ng\\nu\\nA\\n...\\narXiv:1707.06347v2
    """
    import re
    # Pattern: lines that are single characters (including digits, symbols)
    # at the start of the text, typically the arXiv stamp
    lines = text.split('\n')
    start_idx = 0

    # Skip leading single-character lines (arXiv header artifact)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) <= 2 and stripped:
            start_idx = i + 1
        else:
            break

    if start_idx > 5:  # Only strip if there were many single-char lines
        return '\n'.join(lines[start_idx:])
    return text


def _clean_whitespace(text: str) -> str:
    """Normalize whitespace without destroying structure.

    - Strip arXiv header artifacts
    - Repair spaceless concatenated text from pdfminer
    - Collapse runs of spaces/tabs into single spaces
    - Preserve paragraph breaks (double newlines)
    - Strip leading/trailing whitespace
    """
    import re
    # Strip arXiv single-character header
    text = _strip_arxiv_header(text)
    # Repair spaceless text from pdfminer
    text = _repair_spaceless_text(text)
    # Replace tabs with spaces
    text = text.replace('\t', ' ')
    # Collapse multiple spaces into one (but not newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

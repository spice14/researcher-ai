"""Deterministic PDF body text extraction using PyMuPDF.

Purpose:
- Extract body text from PDF files using PyMuPDF (fitz)
- Preserve deterministic block ordering by (page_number, y0, x0)
- No text merging, no deduplication, no sorting by content length
- Maintain strict determinism: identical output across multiple runs

Inputs/Outputs:
- Input: file path to PDF
- Output: List of dicts with {"page": int, "block_id": str, "type": "BODY", "text": str}

Failure Modes:
- File not found → raises FileNotFoundError
- Invalid PDF → raises PDFExtractionError
- Empty page → included with empty list (page recorded but no blocks)
- PyMuPDF not installed → raises ImportError

Testing Strategy:
- Deterministic: same PDF → same output every time
- Strict ordering: (page_number, y0, x0) for all blocks
- Whitespace normalization: multiple spaces → single space, fix hyphen breaks
- No implicit ordering by block size or coordinate magnitude

Architectural Notes:
- Blocks are extracted via page.get_text("blocks") API
- Each block is (x0, y0, x1, y1, text, block_number, block_type)
- block_type: 0=text, 1=image, etc. We only extract text blocks (type=0)
- Ordering is STRICT: sort by (page, y0, x0) before numbering
- block_id format: "pdf_body_{page}_{sort_index}_{block_number}"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Dict, Any
import hashlib
import re


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""
    pass


@dataclass(frozen=True)
class PyMuPDFBlock:
    """Single text block extracted from PDF using PyMuPDF."""
    page: int              # 1-indexed
    block_id: str          # Deterministic identifier
    type: str              # Always "BODY" for body text extraction
    text: str              # Extracted text
    y0: float              # Top coordinate (for deterministic ordering)
    x0: float              # Left coordinate (for deterministic ordering)


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in extracted text.
    
    - Replace tabs with spaces
    - Collapse multiple spaces into single space
    - Remove leading/trailing whitespace
    - Fix hyphen breaks (join hyphenated word fragments)
    """
    # Replace tabs with spaces
    text = text.replace('\t', ' ')
    
    # Collapse multiple spaces into one (but preserve newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    
    # Fix hyphenation: "word-\n" becomes "word" (remove hyphen at EOL followed by newline)
    text = re.sub(r'-\s*\n\s*', '', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def _make_block_id(page: int, sort_index: int, block_number: int) -> str:
    """Generate deterministic block ID.
    
    Format: pdf_body_{page}_{sort_index}_{block_number}
    
    Args:
        page: 1-indexed page number
        sort_index: Position in deterministic sort order (0-based)
        block_number: Original block number from PyMuPDF
    
    Returns:
        Deterministic block identifier
    """
    return f"pdf_body_{page}_{sort_index}_{block_number}"


def extract_body_blocks_from_pdf(pdf_path: str) -> List[PyMuPDFBlock]:
    """Extract body text blocks from a PDF file using PyMuPDF.
    
    Process:
    1. Open PDF with PyMuPDF (fitz)
    2. For each page, extract text blocks via get_text("blocks")
    3. Filter to text blocks only (type=0)
    4. Sort blocks by (page_number, y0, x0) for deterministic ordering
    5. Generate deterministic block IDs
    6. Normalize whitespace
    7. Return list of PyMuPDFBlock objects
    
    Args:
        pdf_path: Absolute or relative path to the PDF file.
    
    Returns:
        List of PyMuPDFBlock objects, sorted by (page, y0, x0).
    
    Raises:
        FileNotFoundError: If the file does not exist.
        PDFExtractionError: If the PDF cannot be parsed or fitz is unavailable.
    """
    # Check file existence
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Import fitz (PyMuPDF)
    try:
        import fitz
    except ImportError as e:
        raise PDFExtractionError(
            f"PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF"
        ) from e
    
    # Open PDF
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF: {pdf_path} — {e}")
    
    if doc.page_count == 0:
        raise PDFExtractionError(f"PDF has no pages: {pdf_path}")
    
    # Collect all blocks from all pages
    all_blocks: List[Dict[str, Any]] = []
    
    for page_num in range(doc.page_count):
        try:
            page = doc[page_num]
            blocks = page.get_text("blocks")
            
            for block in blocks:
                # block = (x0, y0, x1, y1, text, block_number, block_type)
                if len(block) >= 7 and block[6] == 0:  # block_type == 0 means text
                    x0, y0, x1, y1 = block[0], block[1], block[2], block[3]
                    text = block[4]
                    block_number = block[5]
                    
                    # Skip empty blocks
                    if not text or not text.strip():
                        continue
                    
                    # Normalize whitespace
                    normalized_text = _normalize_whitespace(text)
                    if not normalized_text:
                        continue
                    
                    all_blocks.append({
                        'page': page_num + 1,  # Convert to 1-indexed
                        'y0': y0,
                        'x0': x0,
                        'text': normalized_text,
                        'block_number': block_number,
                    })
        except Exception as e:
            raise PDFExtractionError(f"Failed to extract text from page {page_num + 1}: {e}")
    
    # Close document
    try:
        doc.close()
    except Exception:
        pass  # Non-fatal if close fails
    
    # Sort all blocks by (page, y0, x0) for deterministic ordering
    all_blocks.sort(key=lambda b: (b['page'], b['y0'], b['x0']))
    
    # Generate PyMuPDFBlock objects with deterministic IDs
    result: List[PyMuPDFBlock] = []
    for sort_index, block_data in enumerate(all_blocks):
        block_id = _make_block_id(
            page=block_data['page'],
            sort_index=sort_index,
            block_number=block_data['block_number'],
        )
        result.append(PyMuPDFBlock(
            page=block_data['page'],
            block_id=block_id,
            type="BODY",
            text=block_data['text'],
            y0=block_data['y0'],
            x0=block_data['x0'],
        ))
    
    return result

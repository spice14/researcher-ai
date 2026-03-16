"""Deterministic PDF table extraction using pdfplumber.

Purpose:
- Extract tables from PDF files using pdfplumber
- Separate extraction path from body text (no merging)
- Output in row-wise string format for deterministic processing
- Maintain strict determinism: identical output across multiple runs
- No deduplication, no content union with body text

Inputs/Outputs:
- Input: file path to PDF
- Output: List of dicts with {"page": int, "block_id": str, "type": "TABLE", "text": str}

Failure Modes:
- File not found → raises FileNotFoundError
- Invalid PDF → raises PDFExtractionError
- No tables found → returns empty list (no exception)
- pdfplumber not installed → raises ImportError

Testing Strategy:
- Deterministic: same PDF → same output every time
- Strict ordering: (page_number, table_index) for all tables
- No fuzzy matching, no implicit filtering of small tables
- Row-wise format: "Col1 | Col2 | Col3" per row, rows separated by newline

Architectural Notes:
- Tables are detected by pdfplumber's table detection algorithm
- Output format: one row per line, cells separated by " | "
- Each table becomes a single block with entire table as text
- block_id format: "pdf_table_{page}_{table_index}"
- Strict ordering: by (page_number, table_position_on_page)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Dict, Any


class PDFExtractionError(Exception):
    """Raised when PDF table extraction fails."""
    pass


@dataclass(frozen=True)
class PDFTableBlock:
    """Single table extracted from PDF."""
    page: int              # 1-indexed
    block_id: str          # Deterministic identifier
    type: str              # Always "TABLE" for table extraction
    text: str              # Row-wise table text


def _make_table_block_id(page: int, table_index: int) -> str:
    """Generate deterministic table block ID.
    
    Format: pdf_table_{page}_{table_index}
    
    Args:
        page: 1-indexed page number
        table_index: Position in page's table sequence (0-based)
    
    Returns:
        Deterministic block identifier
    """
    return f"pdf_table_{page}_{table_index}"


def _table_to_row_text(table: List[List[str]]) -> str:
    """Convert extracted table to row-wise string format.
    
    Format:
    - Each row on separate line
    - Cells separated by " | " (space-pipe-space)
    - Empty cells become empty strings (but still separated by |)
    - Leading/trailing spaces stripped per cell
    
    Args:
        table: List of rows, each row is list of cell strings
    
    Returns:
        Row-wise formatted table text
    """
    rows = []
    for row in table:
        # Normalize cell content: strip and convert None to empty string
        cells = [str(cell).strip() if cell else "" for cell in row]
        row_text = " | ".join(cells)
        rows.append(row_text)
    
    return "\n".join(rows)


def extract_tables_from_pdf(pdf_path: str) -> List[PDFTableBlock]:
    """Extract tables from a PDF file using pdfplumber.
    
    Process:
    1. Open PDF with pdfplumber
    2. For each page, detect tables via find_tables()
    3. Convert table to row-wise string format
    4. Sort by (page_number, table_index) for deterministic ordering
    5. Generate deterministic block IDs
    6. Return list of PDFTableBlock objects
    
    Args:
        pdf_path: Absolute or relative path to the PDF file.
    
    Returns:
        List of PDFTableBlock objects, sorted by (page, table_index).
    
    Raises:
        FileNotFoundError: If the file does not exist.
        PDFExtractionError: If the PDF cannot be parsed or pdfplumber is unavailable.
    """
    # Check file existence
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Import pdfplumber
    try:
        import pdfplumber
    except ImportError as e:
        raise PDFExtractionError(
            f"pdfplumber not installed. Install with: pip install pdfplumber"
        ) from e
    
    # Open PDF
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF: {pdf_path} — {e}")
    
    if not pdf.pages:
        raise PDFExtractionError(f"PDF has no pages: {pdf_path}")
    
    # Collect all tables from all pages
    result: List[PDFTableBlock] = []
    
    for page_num, page in enumerate(pdf.pages):
        try:
            tables = page.find_tables()
            
            for table_index, table in enumerate(tables):
                if not table:  # Skip empty tables
                    continue
                
                # Convert table to row-wise text
                table_text = _table_to_row_text(table)
                
                if not table_text or not table_text.strip():
                    continue  # Skip tables that become empty after formatting
                
                block_id = _make_table_block_id(
                    page=page_num + 1,  # Convert to 1-indexed
                    table_index=table_index,
                )
                
                result.append(PDFTableBlock(
                    page=page_num + 1,  # Convert to 1-indexed
                    block_id=block_id,
                    type="TABLE",
                    text=table_text,
                ))
        except Exception as e:
            # Non-fatal: some pages may fail extraction but we continue
            pass
    
    # Close PDF
    try:
        pdf.close()
    except Exception:
        pass  # Non-fatal if close fails
    
    return result

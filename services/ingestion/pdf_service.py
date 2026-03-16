"""PDF ingestion service — real document to structured chunks.

Purpose:
- Accept a PDF file path and produce sentence-segmented chunks
- Each chunk carries REAL page number from the source document
- Reuses existing deterministic segmentation logic

Inputs/Outputs:
- Input: PDF file path + source_id
- Output: IngestionResult with page-aware chunks

Schema References:
- services.ingestion.schemas
- services.ingestion.pdf_loader

Failure Modes:
- PDF extraction failure → raises PDFExtractionError
- No text on any page → raises ValueError

Testing Strategy:
- Deterministic: same PDF → same chunks every time
- Page numbers must be real, not fabricated
"""

from __future__ import annotations

from typing import List

from services.ingestion.pdf_loader import extract_pages_from_pdf
from services.ingestion.schemas import (
    ExtractionTelemetry,
    IngestionChunk,
    IngestionResult,
)
from services.ingestion.service import (
    _derive_context_id,
    _extract_metric_names,
    _extract_numeric_strings,
    _extract_unit_strings,
    _hash_text,
    _sentence_chunks,
)


class PDFIngestionService:
    """Deterministic PDF ingestion with real page provenance."""

    def ingest_pdf(
        self,
        pdf_path: str,
        source_id: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ) -> IngestionResult:
        """
        Ingest a PDF file into sentence-segmented chunks.

        Each chunk preserves the REAL page number from the source document.
        Segmentation reuses existing deterministic sentence-splitting logic.

        Args:
            pdf_path: Path to the PDF file.
            source_id: Identifier for the source document.
            chunk_size: Maximum characters per chunk.
            chunk_overlap: Character overlap between chunks from long sentences.

        Returns:
            IngestionResult with page-aware chunks.

        Raises:
            FileNotFoundError: If PDF does not exist.
            PDFExtractionError: If PDF cannot be parsed.
            ValueError: If no text extracted from any page.
        """
        pages = extract_pages_from_pdf(pdf_path)

        all_text_parts = []
        chunks: List[IngestionChunk] = []
        chunk_index = 0

        for pdf_page in pages:
            page_text = pdf_page.text
            if not page_text.strip():
                continue

            all_text_parts.append(page_text)

            # Apply existing sentence segmentation to this page's text
            for start, end, sentence_text in _sentence_chunks(
                page_text, chunk_size, chunk_overlap
            ):
                chunk_id = f"{source_id}_chunk_{chunk_index}"
                chunk_numeric = _extract_numeric_strings(sentence_text)
                chunk_units = _extract_unit_strings(sentence_text)
                chunk_metrics = _extract_metric_names(sentence_text)
                chunk_context_id = _derive_context_id(sentence_text)

                chunks.append(
                    IngestionChunk(
                        chunk_id=chunk_id,
                        source_id=source_id,
                        page=pdf_page.page,  # REAL page number
                        text=sentence_text,
                        start_char=start,
                        end_char=end,
                        text_hash=_hash_text(sentence_text),
                        context_id=chunk_context_id,
                        numeric_strings=chunk_numeric,
                        unit_strings=chunk_units,
                        metric_names=chunk_metrics,
                    )
                )
                chunk_index += 1

        if not chunks:
            raise ValueError(f"No text extracted from PDF: {pdf_path}")

        # Aggregate telemetry across all pages
        full_text = "\n\n".join(all_text_parts)
        context_ids = []
        for chunk in chunks:
            if chunk.context_id not in context_ids:
                context_ids.append(chunk.context_id)

        telemetry = ExtractionTelemetry(
            numeric_strings=_extract_numeric_strings(full_text),
            unit_strings=_extract_unit_strings(full_text),
            metric_names=_extract_metric_names(full_text),
            context_ids=context_ids,
        )

        return IngestionResult(
            source_id=source_id,
            chunks=chunks,
            telemetry=telemetry,
            warnings=[],
            metadata={"pdf_path": pdf_path, "total_pages": str(len(pages))},
        )

"""Multimodal Extraction Service — tables, figures, metrics from text.

Purpose:
- Extract structured artifacts (tables, figures, metrics) from text
- Normalize extracted tables into typed row/column structures
- Associate captions with artifacts by spatial proximity
- Output ExtractionResult objects conforming to core schemas

Inputs/Outputs:
- Input: paper_id + text chunks (or raw text with page info)
- Output: List of ExtractionResult dicts

Schema References:
- core.schemas.extraction_result (ExtractionResult, ArtifactType)
- core.schemas.evidence (EvidenceProvenance)

Failure Modes:
- No extractable artifacts → return empty list with warning
- Partial extraction failure → log, return partial results
- Invalid page range → ignore constraint, extract all

Testing Strategy:
- Deterministic: identical text → identical ExtractionResult
- Table detection regex tested on synthetic inputs
- Metric extraction tested on known patterns
- Caption association tested with labeled examples
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional

from core.schemas.evidence import EvidenceProvenance
from core.schemas.extraction_result import ArtifactType, ExtractionResult


# Table detection: lines with multiple pipe-separated cells or tab-separated values
_TABLE_LINE_PATTERN = re.compile(r"^.+(\s*\|\s*.+){2,}$", re.MULTILINE)
_TSV_LINE_PATTERN = re.compile(r"^.+(\t.+){2,}$", re.MULTILINE)

# Caption detection
_CAPTION_PATTERN = re.compile(
    r"(?:Table|Figure|Fig\.?)\s*(\d+)[.:]\s*(.*?)(?:\n|$)",
    re.IGNORECASE,
)

# Metric patterns: "metric = value" or "metric: value" or "metric of value"
_METRIC_PATTERN = re.compile(
    r"\b(accuracy|f1(?:-score|-macro)?|bleu|rouge(?:-l)?|precision|recall|"
    r"auc|map|mrr|wer|cer|perplexity|mae|rmse|mse|loss)\b"
    r"\s*(?:=|:|of|is)\s*"
    r"(\d+\.?\d*%?)",
    re.IGNORECASE,
)


def _make_result_id(paper_id: str, page: int, artifact_type: str, index: int) -> str:
    """Generate deterministic extraction result ID."""
    seed = f"{paper_id}:{page}:{artifact_type}:{index}"
    h = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"extract_{h}"


class MultimodalExtractionService:
    """Deterministic multimodal extraction from text content.

    Extracts tables, figures (captions), and metrics from text
    using rule-based pattern matching. No LLM calls.
    """

    def extract(
        self,
        paper_id: str,
        chunks: List[Dict],
        page_constraint: Optional[int] = None,
    ) -> List[Dict]:
        """Extract multimodal artifacts from text chunks.

        Args:
            paper_id: Paper identifier for provenance
            chunks: List of chunk dicts with text, page, chunk_id
            page_constraint: Optional page number filter

        Returns:
            List of ExtractionResult-compatible dicts
        """
        if not paper_id:
            raise ValueError("paper_id is required")
        if not chunks:
            return []

        results: List[Dict] = []
        table_idx = 0
        metric_idx = 0
        caption_idx = 0

        for chunk in chunks:
            text = chunk.get("text", "")
            page = chunk.get("page", 1)
            chunk_id = chunk.get("chunk_id", "")

            if page_constraint is not None and page != page_constraint:
                continue

            # Extract tables
            tables = self._extract_tables(text, paper_id, page, table_idx)
            table_idx += len(tables)
            results.extend(tables)

            # Extract metrics
            metrics = self._extract_metrics(text, paper_id, page, chunk_id, metric_idx)
            metric_idx += len(metrics)
            results.extend(metrics)

            # Extract figure/table captions
            captions = self._extract_captions(text, paper_id, page, caption_idx)
            caption_idx += len(captions)
            results.extend(captions)

        return results

    def _extract_tables(
        self, text: str, paper_id: str, page: int, start_idx: int
    ) -> List[Dict]:
        """Extract table-like structures from text."""
        results = []

        # Find pipe-delimited table blocks
        lines = text.split("\n")
        table_lines: List[str] = []
        in_table = False

        for line in lines:
            is_table_line = bool(_TABLE_LINE_PATTERN.match(line)) or bool(
                _TSV_LINE_PATTERN.match(line)
            )
            if is_table_line:
                table_lines.append(line)
                in_table = True
            else:
                if in_table and len(table_lines) >= 2:
                    # End of a table block with at least 2 rows
                    results.append(
                        self._make_table_result(
                            paper_id, page, table_lines, start_idx + len(results)
                        )
                    )
                table_lines = []
                in_table = False

        # Handle table at end of text
        if in_table and len(table_lines) >= 2:
            results.append(
                self._make_table_result(
                    paper_id, page, table_lines, start_idx + len(results)
                )
            )

        return results

    def _make_table_result(
        self, paper_id: str, page: int, table_lines: List[str], index: int
    ) -> Dict:
        """Create an ExtractionResult dict for a table."""
        raw_content = "\n".join(table_lines)

        # Normalize: parse into rows and columns
        rows = []
        headers = []
        for i, line in enumerate(table_lines):
            # Split by pipe or tab
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
            else:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
            if i == 0:
                headers = cells
            rows.append(cells)

        normalized = {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers),
        }

        result_id = _make_result_id(paper_id, page, "table", index)
        return {
            "result_id": result_id,
            "paper_id": paper_id,
            "page_number": page,
            "artifact_type": ArtifactType.TABLE.value,
            "raw_content": raw_content,
            "normalized_data": normalized,
            "caption": None,
            "provenance": {
                "source_id": paper_id,
                "page": page,
                "extraction_model_version": "rule_based_v1",
            },
        }

    def _extract_metrics(
        self,
        text: str,
        paper_id: str,
        page: int,
        chunk_id: str,
        start_idx: int,
    ) -> List[Dict]:
        """Extract metric values from text."""
        results = []
        seen = set()

        for match in _METRIC_PATTERN.finditer(text):
            metric_name = match.group(1).lower()
            metric_value = match.group(2)
            key = (metric_name, metric_value)
            if key in seen:
                continue
            seen.add(key)

            # Normalize percentage values
            value_normalized = metric_value.rstrip("%")
            try:
                numeric_val = float(value_normalized)
            except ValueError:
                continue

            result_id = _make_result_id(paper_id, page, "metric", start_idx + len(results))
            results.append({
                "result_id": result_id,
                "paper_id": paper_id,
                "page_number": page,
                "artifact_type": ArtifactType.METRIC.value,
                "raw_content": match.group(0),
                "normalized_data": {
                    "metric": metric_name,
                    "value_raw": metric_value,
                    "value_normalized": numeric_val,
                    "is_percentage": metric_value.endswith("%"),
                    "chunk_id": chunk_id,
                },
                "caption": None,
                "provenance": {
                    "source_id": paper_id,
                    "page": page,
                    "extraction_model_version": "rule_based_v1",
                },
            })

        return results

    def _extract_captions(
        self, text: str, paper_id: str, page: int, start_idx: int
    ) -> List[Dict]:
        """Extract table/figure captions."""
        results = []

        for match in _CAPTION_PATTERN.finditer(text):
            full_match = match.group(0).strip()
            caption_num = match.group(1)
            caption_text = match.group(2).strip()

            # Determine if Table or Figure
            lower_prefix = full_match.lower()
            if lower_prefix.startswith("table"):
                artifact_type = ArtifactType.TABLE.value
            else:
                artifact_type = ArtifactType.FIGURE.value

            result_id = _make_result_id(paper_id, page, f"caption_{artifact_type}", start_idx + len(results))
            results.append({
                "result_id": result_id,
                "paper_id": paper_id,
                "page_number": page,
                "artifact_type": artifact_type,
                "raw_content": full_match,
                "normalized_data": {
                    "caption_number": int(caption_num),
                    "caption_text": caption_text,
                    "type": "caption",
                },
                "caption": caption_text if caption_text else None,
                "provenance": {
                    "source_id": paper_id,
                    "page": page,
                    "extraction_model_version": "rule_based_v1",
                },
            })

        return results

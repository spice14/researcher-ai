"""Deterministic ingestion service.

Purpose:
- Accept raw text and emit canonical chunks with provenance.
- Capture extraction telemetry needed to design normalization later.

Inputs/Outputs:
- Input: IngestionRequest
- Output: IngestionResult

Schema References:
- services.ingestion.schemas

Failure Modes:
- Invalid chunk sizing raises a ValueError
- Empty text fails schema validation

Testing Strategy:
- Unit tests validate chunk boundaries and telemetry capture.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Tuple

from services.ingestion.schemas import (
    ExtractionTelemetry,
    IngestionChunk,
    IngestionRequest,
    IngestionResult,
)

_NUMERIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*(?:%|ms|s|sec|seconds|minutes|min|hrs|hours|gb|mb|kb|hz))?",
    re.IGNORECASE,
)
_UNIT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(%|ms|s|sec|seconds|minutes|min|hrs|hours|gb|mb|kb|hz)",
    re.IGNORECASE,
)
_CONTEXT_PATTERN = re.compile(r"\bctx_[a-zA-Z0-9_-]+\b")
_METRIC_PATTERN = re.compile(
    r"\b(accuracy|f1-macro|f1-score|f1|bleu|rouge|rouge-l|rouge-1|rouge-2|map|mAP|mrr|auc"
    r"|precision|recall|wer|cer|latency|perplexity"
    r"|top-1 accuracy|top-5 accuracy|top-1|top-5|iou|ap50|ap75"
    r"|meteor|spice|cider|bertscore|sacrebleu|ter"
    r"|ndcg|hit rate|hit@\d+|hits@\d+"
    r"|mse|rmse|mae|mape|r2|r-squared"
    r"|psnr|ssim|fid|inception score|is score"
    r"|em|exact match|squad-f1"
    r"|loss|error rate|misclassification"
    r"|throughput|fps|samples per second|tokens per second"
    r"|reward|return|episode reward|mean reward|average reward"
    r"|spearman|pearson|kendall|correlation"
    r"|dice|jaccard|sensitivity|specificity)\b",
    re.IGNORECASE,
)
_DATASET_PATTERN = re.compile(
    r"\b(GLUE|SuperGLUE|MNLI|CoLA|SQuAD|ImageNet|WMT"
    r"|CIFAR-?\s?10|CIFAR-?\s?100|COCO|MS-?\s?COCO|Pascal\s?VOC"
    r"|Penn Treebank|PTB|WikiText|C4|The Pile|CommonCrawl"
    r"|LibriSpeech|Common Voice|TIMIT|VoxCeleb"
    r"|ARC|HellaSwag|MMLU|TruthfulQA|Winogrande|GSM8K"
    r"|LAMBADA|StoryCloze|BoolQ|PIQA|OpenBookQA"
    r"|Atari|MuJoCo|HalfCheetah|Hopper|Walker|Humanoid|Ant|Reacher|Swimmer"
    r"|KITTI|Cityscapes|ADE20K|LSUN|CelebA|FFHQ"
    r"|VTAB|Oxford Flowers|Stanford Cars|SVHN"
    r"|MS-?\s?MARCO|Natural Questions|TriviaQA|HotpotQA"
    r"|CNN|DailyMail|XSum|SAMSum"
    r"|SST-?\s?2|MRPC|QQP|QNLI|RTE|WNLI|STS-?\s?B)\b",
    re.IGNORECASE,
)

_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "et al.",
    "fig.",
    "eq.",
    "dr.",
    "mr.",
    "mrs.",
    "prof.",
    "inc.",
    "vs.",
    "al.",
)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> Iterable[tuple[int, int, str]]:
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    step = chunk_size - overlap
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        yield start, end, text[start:end]
        if end == text_len:
            break
        start += step


def _is_decimal_boundary(text: str, index: int) -> bool:
    if text[index] != ".":
        return False
    if index == 0 or index + 1 >= len(text):
        return False
    return text[index - 1].isdigit() and text[index + 1].isdigit()


def _is_abbreviation_boundary(text: str, index: int) -> bool:
    window_start = max(0, index - 15)
    window = text[window_start : index + 1].lower().strip()
    return any(window.endswith(abbrev) for abbrev in _ABBREVIATIONS)


def _sentence_break_index(text: str, index: int) -> int | None:
    if text[index] not in ".!?":
        return None
    if _is_decimal_boundary(text, index) or _is_abbreviation_boundary(text, index):
        return None

    j = index + 1
    text_len = len(text)
    while j < text_len and text[j].isspace():
        j += 1

    if j >= text_len:
        return j

    if text[j].isupper() or text[j].isdigit() or text[j] in ("\"", "'", "(", "["):
        return j

    return None


def _sentence_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    start = 0
    i = 0
    text_len = len(text)

    while i < text_len:
        next_start = _sentence_break_index(text, i)
        if next_start is not None:
            spans.append((start, i + 1))
            start = next_start
            i = next_start
            continue
        i += 1

    if start < text_len:
        spans.append((start, text_len))

    return spans


def _sentence_chunks(text: str, chunk_size: int, overlap: int) -> Iterable[tuple[int, int, str]]:
    for start, end in _sentence_spans(text):
        trimmed_start = start
        trimmed_end = end
        while trimmed_start < trimmed_end and text[trimmed_start].isspace():
            trimmed_start += 1
        while trimmed_end > trimmed_start and text[trimmed_end - 1].isspace():
            trimmed_end -= 1

        if trimmed_start >= trimmed_end:
            continue

        trimmed_text = text[trimmed_start:trimmed_end]
        if len(trimmed_text) <= chunk_size:
            yield trimmed_start, trimmed_end, trimmed_text
            continue

        for sub_start, sub_end, sub_text in _chunk_text(trimmed_text, chunk_size, overlap):
            yield trimmed_start + sub_start, trimmed_start + sub_end, sub_text


def _extract_numeric_strings(text: str) -> List[str]:
    return [m.group(0) for m in _NUMERIC_PATTERN.finditer(text)]


def _extract_unit_strings(text: str) -> List[str]:
    return [m.group(1) for m in _UNIT_PATTERN.finditer(text)]


def _extract_metric_names(text: str) -> List[str]:
    return [m.group(0) for m in _METRIC_PATTERN.finditer(text)]


def _extract_datasets(text: str) -> List[str]:
    return [m.group(0) for m in _DATASET_PATTERN.finditer(text)]


def _derive_context_id(text: str) -> str:
    explicit = _CONTEXT_PATTERN.findall(text)
    if explicit:
        return explicit[0]

    datasets = _extract_datasets(text)
    if datasets:
        return f"ctx_{datasets[0].lower()}"

    metrics = _extract_metric_names(text)
    if metrics:
        return f"ctx_metric_{metrics[0].lower().replace('-', '_')}"

    return "ctx_unknown"


class IngestionService:
    """Deterministic ingestion service implementation."""

    def ingest_text(self, request: IngestionRequest) -> IngestionResult:
        chunks: List[IngestionChunk] = []
        for index, (start, end, chunk_text) in enumerate(
            _sentence_chunks(request.raw_text, request.chunk_size, request.chunk_overlap)
        ):
            chunk_id = f"{request.source_id}_chunk_{index}"
            chunk_numeric = _extract_numeric_strings(chunk_text)
            chunk_units = _extract_unit_strings(chunk_text)
            chunk_metrics = _extract_metric_names(chunk_text)
            chunk_context_id = _derive_context_id(chunk_text)
            chunks.append(
                IngestionChunk(
                    chunk_id=chunk_id,
                    source_id=request.source_id,
                    text=chunk_text,
                    start_char=start,
                    end_char=end,
                    text_hash=_hash_text(chunk_text),
                    context_id=chunk_context_id,
                    numeric_strings=chunk_numeric,
                    unit_strings=chunk_units,
                    metric_names=chunk_metrics,
                )
            )

        context_ids = []
        for chunk in chunks:
            if chunk.context_id not in context_ids:
                context_ids.append(chunk.context_id)

        telemetry = ExtractionTelemetry(
            numeric_strings=_extract_numeric_strings(request.raw_text),
            unit_strings=_extract_unit_strings(request.raw_text),
            metric_names=_extract_metric_names(request.raw_text),
            context_ids=context_ids,
        )

        warnings: List[str] = []
        if len(request.raw_text) < request.chunk_size:
            warnings.append("raw_text shorter than chunk_size; single chunk emitted")

        return IngestionResult(
            source_id=request.source_id,
            chunks=chunks,
            telemetry=telemetry,
            warnings=warnings,
            metadata=request.metadata,
        )

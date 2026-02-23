"""Deterministic claim normalization service (Step 3B).

Purpose:
- Canonicalize numeric values, units, and metric names.
- Bind numeric values to metrics using positional proximity.
- Reject year and reference numbers deterministically.

Inputs/Outputs:
- Input: NormalizationRequest
- Output: NormalizationResult

Schema References:
- services.normalization.schemas
- core.schemas.claim

Failure Modes:
- Missing metric
- Missing numeric value
- Unparseable units
- Ambiguous numeric binding (numbers exist but none bind to metric)

Testing Strategy:
- Determinism tests
- Unit conversion tests
- Metric alias tests
- Adversarial numeric binding tests (year, table index rejection)
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from services.normalization.schemas import (
    NormalizationRequest,
    NormalizationResult,
    NormalizedClaim,
    NoNormalization,
    NoNormalizationReason,
)
from services.normalization.diagnostics import (
    NormalizationFailureReason,
    NormalizationDiagnostic,
)

def _normalize_metric_key(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", token.lower())


_METRIC_ALIASES = {
    # Accuracy (Top-1 collapsed)
    "accuracy": "ACCURACY",
    "acc": "ACCURACY",
    "classificationaccuracy": "ACCURACY",
    "modelaccuracy": "ACCURACY",
    "top1": "ACCURACY",
    "top1accuracy": "ACCURACY",
    "top1acc": "ACCURACY",
    "accuracy1": "ACCURACY",
    "acc1": "ACCURACY",
    # Top-5 accuracy (kept distinct)
    "top5": "TOP5_ACCURACY",
    "top5accuracy": "TOP5_ACCURACY",
    "top5acc": "TOP5_ACCURACY",
    "accuracy5": "TOP5_ACCURACY",
    # Other metrics
    "f1macro": "F1_MACRO",
    "f1score": "F1",
    "f1": "F1",
    "bleu": "BLEU",
    "bleu4": "BLEU",
    "rouge": "ROUGE",
    "rougel": "ROUGE_L",
    "latency": "LATENCY",
    "perplexity": "PERPLEXITY",
    "ppl": "PERPLEXITY",
    "map": "MAP",
    "iou": "IOU",
    "ap50": "AP50",
    "ap75": "AP75",
    "wer": "WER",
    "cer": "CER",
    "mrr": "MRR",
    "auc": "AUC",
    "precision": "PRECISION",
    "recall": "RECALL",
}

_VALUE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?P<unit>%|ms|s|sec|seconds|gb|mb|kb))?",
    re.IGNORECASE,
)

_METRIC_PATTERN = re.compile(
    r"\b("
    r"classification accuracy|model accuracy|accuracy@1|acc@1|accuracy@5|"
    r"top-1 accuracy|top1 accuracy|top-1 acc|top1 acc|top-1|top1|"
    r"top-5 accuracy|top5 accuracy|top-5 acc|top5 acc|top-5|top5|"
    r"accuracy|acc|f1-macro|f1 macro|f1-score|f1|bleu-4|bleu|rouge-l|rouge|"
    r"latency|perplexity|ppl|map|mAP|iou|ap50|ap75|wer|cer|mrr|auc|precision|recall"
    r")\b",
    re.IGNORECASE,
)

# Pattern to detect reference prefixes before a number
_REFERENCE_PREFIX_PATTERN = re.compile(
    r"(?:table|figure|fig\.?|section|§|chapter)\s*$",
    re.IGNORECASE,
)

# Maximum character distance between metric token and numeric value
_MAX_METRIC_VALUE_DISTANCE = 80


def _canonical_metric(text: str) -> Optional[str]:
    match = _METRIC_PATTERN.search(text)
    if not match:
        return None
    token = match.group(0)
    normalized = _normalize_metric_key(token)
    return _METRIC_ALIASES.get(normalized)


def _is_year(value_str: str, numeric: float) -> bool:
    """Reject integers in range [1900, 2099] as likely years."""
    if "." in value_str:
        return False
    return 1900 <= int(numeric) <= 2099


# Pattern to detect citation-year contexts that should be rejected
_CITATION_YEAR_BRACKET_PATTERN = re.compile(
    r"[\[\(][^\]\)]*\b(\d{4})\b[^\]\)]*[\]\)]",
)
_CITATION_YEAR_AUTHOR_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+(?:\s+(?:et\s+al|and))?[.,]?\s+)(\d{4})\b",
)


def _is_citation_year(text: str, match_start: int, match_end: int) -> bool:
    """Reject a number if it appears in a citation-year context.

    Rejects if:
    - Number is inside [...] or (...)
    - Number is within 5 characters of '[' or ']'
    - Number matches 'Author et al. YYYY' pattern
    """
    value_str = text[match_start:match_end]
    # Only applies to 4-digit year-like integers
    if "." in value_str:
        return False
    try:
        val = int(value_str)
    except ValueError:
        return False
    if not (1900 <= val <= 2099):
        return False

    # Check if within 5 characters of bracket
    window_start = max(0, match_start - 5)
    window_end = min(len(text), match_end + 5)
    window = text[window_start:window_end]
    if '[' in window or ']' in window:
        return True

    # Check if inside parentheses
    # Find the nearest ( before and ) after
    before = text[:match_start]
    after = text[match_end:]
    open_paren = before.rfind('(')
    close_paren = after.find(')')
    if open_paren != -1 and close_paren != -1:
        # Check there's no intervening close paren before the number
        between_open_and_num = before[open_paren:]
        if ')' not in between_open_and_num:
            return True

    # Check Author et al. YYYY pattern
    prefix = text[max(0, match_start - 30):match_start]
    if re.search(r"\b[A-Z][a-z]+(?:\s+(?:et\s+al|and))?[.,]?\s*$", prefix):
        return True

    return False


def _is_reference_number(text: str, match_start: int) -> bool:
    """Reject numbers preceded by 'Table', 'Figure', 'Section', etc."""
    prefix = text[max(0, match_start - 15):match_start]
    return bool(_REFERENCE_PREFIX_PATTERN.search(prefix))


def _is_embedded_in_token(text: str, match_start: int) -> bool:
    """Reject numbers embedded in alphanumeric tokens (e.g., 'newstest2014')."""
    if match_start > 0 and text[match_start - 1].isalpha():
        return True
    return False


def _is_dataset_year(text: str, value_str: str, numeric: float, match_start: int) -> bool:
    """Reject a year if it appears as part of a dataset/benchmark name.
    
    Common patterns:
    - WMT 2014, WMT 2012
    - PASCAL VOC 2007, VOC 2007, PASCAL VOC 2012
    - CoNLL-2012, CoNLL 2012
    - newstest2014 (already caught by _is_embedded_in_token)
    - COCO 2017, ImageNet 2012
    - Composite patterns: "2007+2012", "07+12"
    
    Root cause: These years are dataset identifiers, not metric values.
    """
    # Only applies to 4-digit year-like integers
    if "." in value_str:
        return False
    try:
        val = int(numeric)
    except ValueError:
        return False
    if not (1900 <= val <= 2099):
        return False
    
    # Extract window around the number (30 chars before, 10 chars after)
    window_start = max(0, match_start - 30)
    window_end = min(len(text), match_start + len(value_str) + 10)
    window = text[window_start:window_end]
    
    # Dataset name patterns (case-insensitive)
    dataset_patterns = [
        r"\bWMT\s+\d{4}\b",                    # WMT 2014
        r"\b(?:PASCAL\s+)?VOC[-\s]\d{4}\b",   # PASCAL VOC 2007, VOC 2007, VOC-2012
        r"\bCoNLL[-\s]\d{4}\b",               # CoNLL-2012, CoNLL 2012
        r"\bCOCO[-\s]\d{4}\b",                # COCO 2017, COCO-2017
        r"\bMSCOCO[-\s]\d{4}\b",              # MSCOCO 2014, MSCOCO-2014
        r"\bImageNet[-\s]\d{4}\b",            # ImageNet 2012, ImageNet-2012
        r"\bSQuAD[-\s]\d{4}\b",               # SQuAD 2018, SQuAD-2018
        r"\bGLUE[-\s]\d{4}\b",                # GLUE 2018, GLUE-2018
        r"\bSuperGLUE[-\s]\d{4}\b",           # SuperGLUE 2019, SuperGLUE-2019
        r"\d{4}\s*\+\s*\d{4}",                # 2007+2012 (composite datasets)
    ]
    
    for pattern in dataset_patterns:
        if re.search(pattern, window, re.IGNORECASE):
            return True
    
    return False


def _is_temporal_year_context(text: str, match_start: int, value_str: str, numeric: float) -> bool:
    """Reject years in temporal/historical context.
    
    Examples that should be rejected:
    - "mid-2019 state of the art"
    - "early 2020 models"
    - "late-2018 baseline"
    - "circa 2017 performance"
    - "as of 2021"
    - "in 2019"
    - "2019 state of the art"
    - "SOTA models from 2020"
    
    Root cause: These years refer to temporal context (when research was done),
    not metric values or measurements.
    """
    # Only applies to 4-digit year-like integers
    if "." in value_str:
        return False
    try:
        val = int(numeric)
    except ValueError:
        return False
    if not (1900 <= val <= 2099):
        return False
    
    # Extract wider window (60 chars before, 60 chars after)
    window_start = max(0, match_start - 60)
    window_end = min(len(text), match_start + len(value_str) + 60)
    window = text[window_start:window_end]
    
    # Temporal modifier patterns (hyphenated or space-separated before year)
    temporal_prefix_patterns = [
        r"\b(?:early|mid|late|circa|around|before|after|since|as\s+of|in)\s*[-\s]?\s*\d{4}\b",
    ]
    
    # Temporal context patterns (after year)
    temporal_suffix_patterns = [
        r"\d{4}\s+(?:state of the art|SOTA|baseline|models?|era|period|generation|prior work|literature)",
    ]
    
    # Check prefix patterns (e.g., "mid-2019")
    for pattern in temporal_prefix_patterns:
        if re.search(pattern, window, re.IGNORECASE):
            return True
    
    # Check suffix patterns (e.g., "2019 state of the art")
    for pattern in temporal_suffix_patterns:
        if re.search(pattern, window, re.IGNORECASE):
            return True
    
    return False


def _convert_unit(
    raw_value: str, numeric: float, unit: Optional[str]
) -> Optional[Tuple[str, float, Optional[str]]]:
    """Apply unit conversion. Returns (raw_display, normalized_value, canonical_unit)."""
    if unit is None:
        return raw_value, numeric, None

    unit_lower = unit.lower()
    if unit_lower == "%":
        return f"{raw_value}%", numeric / 100.0, "ratio"
    if unit_lower in {"ms"}:
        return f"{raw_value}ms", numeric / 1000.0, "s"
    if unit_lower in {"s", "sec", "seconds"}:
        return f"{raw_value}{unit_lower}", numeric, "s"
    if unit_lower == "gb":
        return f"{raw_value}gb", numeric, "gb"
    if unit_lower == "mb":
        return f"{raw_value}mb", numeric / 1024.0, "gb"
    if unit_lower == "kb":
        return f"{raw_value}kb", numeric / (1024.0 * 1024.0), "gb"

    return None


# ── DIRECT METRIC-ADJACENCY PATTERN ──
# If a number is directly adjacent to a metric token (within ~10 chars),
# it is the authoritative binding. Overrides all distance ranking.
# Patterns:
#   "{metric}\s*(=|of)?\s*\d"  (metric followed by number)
#   "\d\s*%?\s*{metric}"       (number followed by metric)
_DIRECT_ADJACENCY_DISTANCE = 10

# Debug flag: set to True to print numeric binding trace
NUMERIC_BINDING_TRACE = False


def _find_direct_adjacent_value(
    text: str, metric_match: re.Match,
) -> Optional[re.Match]:
    """Find a number directly adjacent to the metric token.

    Checks within _DIRECT_ADJACENCY_DISTANCE characters:
    - metric {=|of}? number
    - number {%}? metric

    Returns the VALUE_PATTERN match if found, else None.
    """
    metric_start = metric_match.start()
    metric_end = metric_match.end()

    # Look for number AFTER metric: "{metric}\s*(=|of)?\s*\d"
    after_text = text[metric_end:metric_end + _DIRECT_ADJACENCY_DISTANCE + 20]
    after_match = re.match(r"\s*(?:=|of|score\s+of)?\s*", after_text)
    if after_match:
        gap = after_match.end()
        num_match = _VALUE_PATTERN.match(after_text[gap:])
        if num_match:
            # Compute absolute position in original text
            abs_start = metric_end + gap
            if abs_start - metric_end <= _DIRECT_ADJACENCY_DISTANCE + len(after_match.group()):
                # Re-find this match at the absolute position
                for m in _VALUE_PATTERN.finditer(text):
                    if m.start() == abs_start:
                        return m

    # Look for number BEFORE metric: "\d\s*%?\s*{metric}"
    # Find the last number in the window before metric
    last_num = None
    for m in _VALUE_PATTERN.finditer(text):
        m_end = m.end()
        # Skip numbers that overlap with the metric match itself
        if m.start() >= metric_start:
            break
        # Allow optional % and whitespace between number end and metric start
        between = text[m_end:metric_start]
        if re.fullmatch(r"\s*%?\s*", between) and (metric_start - m.start()) <= _DIRECT_ADJACENCY_DISTANCE + 10:
            last_num = m

    return last_num


def _metric_proximate_value(
    text: str,
) -> Optional[Tuple[str, float, Optional[str], bool]]:
    """Find the numeric value nearest to the metric token.

    Priority order:
    1. Direct metric-adjacent value (within 10 chars) — authoritative
    2. Nearest value by character distance (with rejection filters)

    Applies deterministic rejection filters:
    - Years (1900-2099 integers)
    - Citation-year contexts ([YYYY], (YYYY), Author et al. YYYY)
    - Reference numbers (Table N, Figure N, Section N)
    - Numbers embedded in alphanumeric tokens (newstest2014)

    Returns:
        Tuple of (raw_display, normalized_value, canonical_unit, had_candidates)
        or None if no valid binding found.
        had_candidates is True if there were numbers but none survived filtering.
    """
    metric_match = _METRIC_PATTERN.search(text)
    if not metric_match:
        return None

    metric_pos = metric_match.start()

    if NUMERIC_BINDING_TRACE:
        print(f"  [TRACE] sentence: {text[:120]}...")
        print(f"  [TRACE] metric: {metric_match.group()} at pos {metric_pos}")

    # ── PHASE 1: Try direct metric-adjacency (authoritative) ──
    direct_match = _find_direct_adjacent_value(text, metric_match)
    if direct_match:
        value_str = direct_match.group("value")
        numeric = float(value_str)
        # Even direct-adjacent values must pass basic sanity
        if not _is_embedded_in_token(text, direct_match.start()):
            # Citation-year, year, dataset-year, and temporal-year filters all apply
            if (not _is_year(value_str, numeric) 
                and not _is_citation_year(text, direct_match.start(), direct_match.start() + len(value_str))
                and not _is_dataset_year(text, value_str, numeric, direct_match.start())
                and not _is_temporal_year_context(text, direct_match.start(), value_str, numeric)):
                unit = direct_match.group("unit")
                converted = _convert_unit(value_str, numeric, unit)
                if converted is not None:
                    if NUMERIC_BINDING_TRACE:
                        print(f"  [TRACE] DIRECT ADJACENT: {value_str} (pos {direct_match.start()})")
                    raw_display, norm_value, canon_unit = converted
                    return raw_display, norm_value, canon_unit, True

    # ── PHASE 2: Proximity-based fallback with full rejection filters ──
    candidates: List[Tuple[int, re.Match]] = []
    had_any_candidates = False
    rejection_log: List[str] = []

    for m in _VALUE_PATTERN.finditer(text):
        value_str = m.group("value")
        numeric = float(value_str)
        had_any_candidates = True

        # Apply rejection filters
        if _is_year(value_str, numeric):
            rejection_log.append(f"year:{value_str}")
            continue
        if _is_citation_year(text, m.start(), m.start() + len(value_str)):
            rejection_log.append(f"citation_year:{value_str}")
            continue
        if _is_reference_number(text, m.start()):
            rejection_log.append(f"reference:{value_str}")
            continue
        if _is_embedded_in_token(text, m.start()):
            rejection_log.append(f"embedded:{value_str}")
            continue
        if _is_dataset_year(text, value_str, numeric, m.start()):
            rejection_log.append(f"dataset_year:{value_str}")
            continue
        if _is_temporal_year_context(text, m.start(), value_str, numeric):
            rejection_log.append(f"temporal_year:{value_str}")
            continue

        # Compute distance to metric token
        distance = abs(m.start() - metric_pos)
        candidates.append((distance, m))

    if NUMERIC_BINDING_TRACE:
        print(f"  [TRACE] candidates: {[(d, m.group('value')) for d, m in candidates]}")
        print(f"  [TRACE] rejections: {rejection_log}")

    if not candidates:
        # Return sentinel: had numbers but none survived
        if had_any_candidates:
            return None  # Caller checks _VALUE_PATTERN separately for AMBIGUOUS
        return None

    # Pick closest candidate to metric token
    candidates.sort(key=lambda x: x[0])
    best_distance, best_match = candidates[0]

    # Proximity gate: reject if too far from metric
    if best_distance > _MAX_METRIC_VALUE_DISTANCE:
        if NUMERIC_BINDING_TRACE:
            print(f"  [TRACE] REJECTED: closest candidate too far ({best_distance} > {_MAX_METRIC_VALUE_DISTANCE})")
        return None

    raw_value = best_match.group("value")
    unit = best_match.group("unit")
    numeric = float(raw_value)

    converted = _convert_unit(raw_value, numeric, unit)
    if converted is None:
        return None

    if NUMERIC_BINDING_TRACE:
        print(f"  [TRACE] BOUND: {raw_value} at distance {best_distance}")

    raw_display, norm_value, canon_unit = converted
    return raw_display, norm_value, canon_unit, had_any_candidates


class NormalizationService:
    """Deterministic normalization implementation with metric-proximate binding."""

    def normalize(self, request: NormalizationRequest, debug_mode: bool = False) -> NormalizationResult:
        claim = request.claim
        metric = _canonical_metric(claim.object)
        
        # Classify rejection if needed
        if not metric:
            diagnostic = None
            if debug_mode:
                diagnostic = {
                    "claim_id": claim.claim_id,
                    "reason": NormalizationFailureReason.MISSING_METRIC.value,
                    "metric_candidate": None,
                    "dataset_candidate": claim.conditions.dataset if claim.conditions else None,
                    "numeric_values_detected": [],
                    "context_id": claim.context_id,
                    "snippet": claim.object[:100],
                }
            return NormalizationResult(
                no_normalization=NoNormalization(reason_code=NoNormalizationReason.MISSING_METRIC),
                diagnostic=diagnostic,
            )

        result = _metric_proximate_value(claim.object)

        if result is None:
            # Distinguish: were there ANY numbers at all?
            has_any_numbers = bool(_VALUE_PATTERN.search(claim.object))
            numeric_values = [float(m.group("value")) for m in _VALUE_PATTERN.finditer(claim.object) if m.group("value").replace(".", "", 1).isdigit()]
            
            diagnostic = None
            if debug_mode:
                if has_any_numbers:
                    reason = NormalizationFailureReason.AMBIGUOUS_NUMERIC_BINDING
                else:
                    reason = NormalizationFailureReason.MISSING_METRIC
                
                diagnostic = {
                    "claim_id": claim.claim_id,
                    "reason": reason.value,
                    "metric_candidate": metric,
                    "dataset_candidate": claim.conditions.dataset if claim.conditions else None,
                    "numeric_values_detected": numeric_values,
                    "context_id": claim.context_id,
                    "snippet": claim.object[:100],
                }
            
            return NormalizationResult(
                no_normalization=NoNormalization(
                    reason_code=(
                        NoNormalizationReason.AMBIGUOUS_NUMERIC_BINDING if has_any_numbers
                        else NoNormalizationReason.MISSING_VALUE
                    ),
                    detail="Numbers exist but none bind to metric (year/reference/distance rejection)" if has_any_numbers else None,
                ),
                diagnostic=diagnostic,
            )

        raw_value, value_normalized, unit_normalized, _ = result

        normalized = NormalizedClaim(
            claim_id=claim.claim_id,
            context_id=claim.context_id,
            subject=claim.subject,
            predicate=claim.predicate,
            object_raw=claim.object,
            metric_canonical=metric,
            value_raw=raw_value,
            value_normalized=value_normalized,
            unit_normalized=unit_normalized,
            polarity=claim.polarity,
            claim_subtype=claim.claim_subtype,
        )

        return NormalizationResult(normalized=normalized)

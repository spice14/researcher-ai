"""Deterministic claim extraction service (Phase 3A).

Purpose:
- Convert sentence-level chunks into structured Claim objects.
- Support three ontological claim types:
  PERFORMANCE — numeric metric on dataset
  EFFICIENCY — compute, training time, memory, cost
  STRUCTURAL — architecture or mechanism description (non-numeric)
- Multi-claim sentence decomposition for compound result sentences.
- Emit NoClaim for non-quantitative or ambiguous sentences.

Inputs/Outputs:
- Input: List[IngestionChunk]
- Output: List[Claim]

Schema References:
- services.extraction.schemas
- core.schemas.claim

Failure Modes:
- Missing context produces NoClaim (for performance claims)
- Non-quantitative sentences produce NoClaim (unless structural)

Testing Strategy:
- Determinism tests for identical inputs
- True-positive and true-negative extraction cases
- Real-paper sentence golden tests
- Multi-claim decomposition tests
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Tuple

from core.schemas.claim import Claim, ClaimEvidence, ClaimSubtype, ClaimType, ConfidenceLevel, Polarity
from services.extraction.schemas import ClaimExtractionRequest, ClaimExtractionResult, NoClaim, NoClaimReason
from services.ingestion.schemas import IngestionChunk

# ── PERFORMANCE CLAIM PREDICATES ──
_VERB_LEXICON = (
    "achieves",
    "attains",
    "obtains",
    "reaches",
    "reports",
    "yields",
    "scores",
    "improves",
    "outperforms",
    "surpasses",
    "establishes",
    "demonstrates",
    "produces",
    "delivers",
    "records",
    "shows",
    "exhibits",
    "sets",
)

# ── EFFICIENCY CLAIM PREDICATES ──
_EFFICIENCY_VERBS = (
    "requires",
    "takes",
    "took",
    "trains",
    "trained",
    "costs",
    "consumes",
    "uses",
    "reduces",
    "needs",
)

# ── STRUCTURAL CLAIM PREDICATES ──
_STRUCTURAL_VERBS = (
    "introduces",
    "introduce",
    "proposes",
    "propose",
    "removes",
    "remove",
    "replaces",
    "replace",
    "consists of",
    "consist of",
    "is based on",
    "are based on",
    "relies on",
    "rely on",
    "relies entirely on",
    "rely entirely on",
    "employs",
    "employ",
    "eliminates",
    "eliminate",
    "dispenses with",
    "dispense with",
    "eschews",
    "eschew",
    "eschewing",
    "uses",
    "use",
)

# ── STRUCTURAL ENTITY NOUNS ──
_STRUCTURAL_ENTITIES = (
    "transformer",
    "model",
    "architecture",
    "network",
    "mechanism",
    "attention",
    "encoder",
    "decoder",
    "layer",
    "module",
    "framework",
)

# ── EFFICIENCY UNITS ──
_EFFICIENCY_UNITS = re.compile(
    r"\b(hours?|days?|GPUs?|TPUs?|FLOPs?|parameters?|P100|V100|A100)\b",
    re.IGNORECASE,
)

_HEDGE_MARKERS = (
    "reportedly",
    "may",
    "might",
    "appears to",
    "suggests",
    "could",
)

_NON_PERFORMANCE_TERMS = (
    "epoch",
    "epochs",
    "parameter",
    "parameters",
    "layer",
    "layers",
    "token",
    "tokens",
    "batch",
    "batch size",
    "training data",
    "split",
)

# ── METRIC PATTERN FOR IMPLICIT PREDICATE DETECTION ──
_METRIC_PATTERN = re.compile(
    r"\b(accuracy|f1-macro|f1-score|f1|bleu|rouge-l|rouge|map|mAP|mrr|auc|precision|recall|wer|cer|latency|perplexity"
    r"|top-1 accuracy|top-5 accuracy|top-1|top-5|iou|ap50|ap75)\b",
    re.IGNORECASE,
)

# ── IMPLICIT PREDICATE: "BLEU score of 41.0" or "BLEU of 41.0" ──
_IMPLICIT_METRIC_OF = re.compile(
    r"\b(accuracy|f1-macro|f1-score|f1|bleu|rouge-l|rouge|map|mAP|mrr|auc|precision|recall|wer|cer|latency|perplexity"
    r"|top-1 accuracy|top-5 accuracy|top-1|top-5|iou|ap50|ap75)"
    r"\s+(?:score\s+)?of\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# ── IMPLICIT PREDICATE: "28.4 BLEU" ──
_IMPLICIT_VALUE_METRIC = re.compile(
    r"(\d+(?:\.\d+)?)\s*(%\s+)?"
    r"(accuracy|f1-macro|f1-score|f1|bleu|rouge-l|rouge|map|mAP|mrr|auc|precision|recall|wer|cer|latency|perplexity"
    r"|top-1 accuracy|top-5 accuracy|top-1|top-5|iou|ap50|ap75)\b",
    re.IGNORECASE,
)

# ── YEAR FILTER ──
_YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")

_CITATION_PATTERNS = (
    re.compile(r"\([^)]*\)"),
    re.compile(r"\[[^\]]*\]"),
)

# ── TABLE/FIGURE PREFIX PATTERN ──
_CAPTION_PREFIX = re.compile(r"^(?:Table|Figure|Fig\.?)\s*\d+\s*[:.]\s*", re.IGNORECASE)

# ── MULTI-CLAIM DECOMPOSITION ──
# Matches patterns like "28.4 BLEU on X and 41.0 BLEU on Y"
# or "28.4 on X and 41.0 on Y" when metric context is clear
_CONJUNCTION_SPLIT = re.compile(
    r",?\s+and\s+",
    re.IGNORECASE,
)


def _hash_claim(context_id: str, subject: str, predicate: str, obj: str) -> str:
    payload = f"{context_id}|{subject}|{predicate}|{obj}".encode("utf-8")
    return "claim_" + hashlib.sha256(payload).hexdigest()


def _strip_citations(text: str) -> str:
    cleaned = text
    for pattern in _CITATION_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned


def _normalize_space(text: str) -> str:
    return " ".join(text.split()).strip()


def _clean_subject(raw_subject: str) -> str:
    """Clean extracted subject: strip citations, table prefixes, leading prepositions."""
    subject = _strip_citations(raw_subject).rstrip(" ,;:")
    subject = _CAPTION_PREFIX.sub("", subject)
    # Strip leading prepositions
    subject = re.sub(r"^(?:On|For|In|With|Using)\s+(?:the\s+)?", "", subject, flags=re.IGNORECASE)
    return _normalize_space(subject)


def _find_predicate(text: str) -> Optional[str]:
    lowered = text.lower()
    for verb in _VERB_LEXICON:
        pattern = re.compile(rf"\b{re.escape(verb)}\b")
        match = pattern.search(lowered)
        if match:
            return verb
    return None


def _find_implicit_predicate(text: str) -> Optional[Tuple[str, str, str]]:
    """Detect implicit predicates like 'BLEU score of 41.0' or '28.4 BLEU'.

    Returns:
        (predicate, subject, object) tuple or None.
    """
    # Check "BLEU score of N" pattern
    match = _IMPLICIT_METRIC_OF.search(text)
    if match:
        subject_text = text[:match.start()].strip()
        object_text = text[match.start():].strip()
        if subject_text:
            return "scores", subject_text, object_text

    # Check "N BLEU" pattern
    match = _IMPLICIT_VALUE_METRIC.search(text)
    if match:
        subject_text = text[:match.start()].strip()
        object_text = text[match.start():].strip()
        if subject_text:
            return "scores", subject_text, object_text

    return None


def _find_efficiency_predicate(text: str) -> Optional[str]:
    """Find efficiency verb in text."""
    lowered = text.lower()
    for verb in _EFFICIENCY_VERBS:
        pattern = re.compile(rf"\b{re.escape(verb)}\b")
        if pattern.search(lowered):
            return verb
    return None


def _find_structural_predicate(text: str) -> Optional[str]:
    """Find structural architecture verb in text."""
    lowered = text.lower()
    # Check multi-word predicates first (longest match)
    sorted_verbs = sorted(_STRUCTURAL_VERBS, key=len, reverse=True)
    for verb in sorted_verbs:
        pattern = re.compile(rf"\b{re.escape(verb)}\b")
        if pattern.search(lowered):
            return verb
    return None


def _has_structural_entity(text: str) -> bool:
    """Check if text contains a model/architecture entity noun."""
    lowered = text.lower()
    for entity in _STRUCTURAL_ENTITIES:
        if re.search(rf"\b{re.escape(entity)}\b", lowered):
            return True
    return False


def _split_subject_object(text: str, predicate: str) -> Tuple[str, str]:
    lowered = text.lower()
    idx = lowered.find(predicate)
    if idx == -1:
        return "", ""
    subject = text[:idx]
    obj = text[idx + len(predicate):]
    return subject, obj


def _is_quantitative_candidate(numbers: List[str], metrics: List[str]) -> bool:
    if not numbers:
        return False
    if not metrics:
        return False
    return True


def _is_hedged_statement(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _HEDGE_MARKERS)


def _is_non_performance_adjacent(text: str, numbers: List[str]) -> bool:
    """Check if non-performance terms are ADJACENT to numbers (positional filter).

    Only rejects when a non-performance term is the direct context of a number,
    AND there are no other valid metric-adjacent numbers in the sentence.
    This prevents rejection of sentences like:
    "Our model achieved 2014 tokens per second and 28.4 BLEU."
    where 28.4 is a valid metric binding despite 2014 being non-performance.
    """
    lowered = text.lower()
    non_perf_numbers = set()

    for term in _NON_PERFORMANCE_TERMS:
        if term not in lowered:
            continue
        for num in numbers:
            if _term_adjacent_to_number(lowered, text, term, num):
                non_perf_numbers.add(num)

    if not non_perf_numbers:
        return False

    # Check if there are any numbers NOT flagged as non-performance
    # that have a metric nearby — if so, don't reject the chunk
    clean_numbers = [n for n in numbers if n not in non_perf_numbers]
    if clean_numbers and _has_metric_adjacent_number(text, clean_numbers):
        return False

    return True


def _has_metric_adjacent_number(text: str, numbers: List[str]) -> bool:
    """Check if any number in the list is adjacent to a metric token."""
    for m in _METRIC_PATTERN.finditer(text):
        metric_pos = m.start()
        for num in numbers:
            for vm in re.finditer(re.escape(num), text):
                if abs(vm.start() - metric_pos) < 50:
                    return True
    return False


def _term_adjacent_to_number(lowered: str, text: str, term: str, num: str) -> bool:
    """Check if a non-performance term is adjacent to a number and no metric is closer."""
    pattern = re.compile(
        rf"\b{re.escape(num)}\s*{re.escape(term)}\b|\b{re.escape(term)}\s*{re.escape(num)}\b",
        re.IGNORECASE,
    )
    if not pattern.search(lowered):
        return False
    # Check if there's a valid metric also adjacent to this number
    for m in _METRIC_PATTERN.finditer(text):
        metric_pos = m.start()
        for vm in re.finditer(re.escape(num), text):
            if abs(vm.start() - metric_pos) < 30:
                return False
    return True


def _filter_year_numbers(numbers: List[str]) -> List[str]:
    """Remove year-like numbers from a number list."""
    result = []
    for n in numbers:
        try:
            val = float(n.rstrip("%mskbgb "))
            if "." not in n and 1900 <= int(val) <= 2099:
                continue
            result.append(n)
        except (ValueError, OverflowError):
            result.append(n)
    return result


def _is_compound_metric(text: str, metrics: List[str], numbers: List[str]) -> bool:
    """Check for truly compound metric sentences.

    Deduplicated: same metric mentioned twice is OK.
    Year numbers filtered: 2014 doesn't count as a second number.
    """
    unique_metrics = {m.lower() for m in metrics}
    if len(unique_metrics) > 1:
        return True
    # Filter year-like numbers before checking compound
    real_numbers = _filter_year_numbers(numbers)
    if " and " in text.lower() and len(real_numbers) > 1:
        return True
    return False


def _try_decompose_compound(
    text: str, metrics: List[str],
) -> Optional[List[Tuple[str, str, str]]]:
    """Try to decompose a sentence with same metric + 'and' into atomic claims.

    Pattern: "28.4 BLEU on X and 41.0 BLEU on Y"
    Returns list of (subject_fragment, predicate, object_fragment) or None.
    """
    unique_metrics = {m.lower() for m in metrics}
    if len(unique_metrics) != 1:
        return None

    # Only decompose if "and" is present
    if " and " not in text.lower():
        return None

    # Split at " and " — try to get atomic segments
    parts = _CONJUNCTION_SPLIT.split(text)
    if len(parts) < 2:
        return None

    # Each part must contain a number to be a valid atomic claim
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        part_numbers = [m.group(0) for m in re.finditer(r"\d+(?:\.\d+)?", part)]
        part_numbers = _filter_year_numbers(part_numbers)
        if part_numbers:
            result.append(part)

    if len(result) < 2:
        return None

    return result


# ── DELTA vs ABSOLUTE DETECTION ──
# Comparative language patterns that indicate a claim reports a difference,
# not an absolute measurement. Delta claims must NOT be aggregated with
# absolute values in belief state computation.
_DELTA_PATTERNS = re.compile(
    r"\b(?:"
    r"improv(?:ing|es?|ed|ement)\s+(?:of|by|over)"
    r"|more\s+than\s+\d"
    r"|by\s+(?:over\s+)?\d"
    r"|outperforms?\s+.*?\s+by\s+\d"
    r"|surpass(?:es|ing)?\s+.*?\s+by\s+\d"
    r"|exceeds?\s+.*?\s+by\s+\d"
    r"|better\s+than\s+.*?\s+by\s+\d"
    r"|over\s+\d+(?:\.\d+)?\s+(?:BLEU|points?|percent)"
    r"|gains?\s+of\s+\d"
    r"|increase\s+of\s+\d"
    r"|reduction\s+of\s+\d"
    r"|drop\s+of\s+\d"
    r")",
    re.IGNORECASE,
)


def _is_delta_claim(text: str) -> bool:
    """Detect whether claim text describes a relative improvement (delta) vs absolute value."""
    return bool(_DELTA_PATTERNS.search(text))


# ── TABLE FRAGMENT DETECTION ──

_TABLE_NUMERIC_TOKEN = re.compile(r"\b\d+(?:\.\d+)?\b")
_TABLE_NEWLINE_COUNT = 3
_TABLE_NUMERIC_TOKEN_THRESHOLD = 5
_TABLE_SUBJECT_MAX_LENGTH = 300


def _is_table_fragment(text: str) -> bool:
    """Detect if text is a table fragment that should not produce claims.

    A table fragment is detected when:
    - Text length > 300 characters
    - AND contains >= 5 numeric tokens
    - AND contains >= 3 newline breaks

    This prevents table-dense PDFs (e.g., ViT) from producing oversized
    subjects or garbage claims from parsed table data.
    """
    if len(text) <= _TABLE_SUBJECT_MAX_LENGTH:
        return False
    newline_count = text.count("\n")
    if newline_count < _TABLE_NEWLINE_COUNT:
        return False
    numeric_count = len(_TABLE_NUMERIC_TOKEN.findall(text))
    if numeric_count < _TABLE_NUMERIC_TOKEN_THRESHOLD:
        return False
    return True


def _is_table_block(text: str) -> bool:
    """Detect table-like blocks: >= 4 consecutive numeric-only lines or grid patterns.

    Used to suppress structural extraction on table chunks while still
    allowing metric-adjacent performance claims.
    """
    lines = text.split("\n")
    consecutive_numeric = 0
    max_consecutive = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # A line is "numeric-only" if after removing whitespace, dots, commas, %, it's all digits
        cleaned = re.sub(r"[\s.,/%±\-]+", "", stripped)
        if cleaned and cleaned.replace(".", "").isdigit():
            consecutive_numeric += 1
            max_consecutive = max(max_consecutive, consecutive_numeric)
        else:
            consecutive_numeric = 0
    if max_consecutive >= 4:
        return True
    # Grid pattern: many short lines (< 20 chars) with numbers
    short_numeric_lines = sum(
        1 for line in lines
        if line.strip() and len(line.strip()) < 20 and re.search(r"\d", line)
    )
    return short_numeric_lines >= 6


def _compute_retrieval_score(chunk_text: str, metric_names: List[str], numeric_strings: List[str]) -> float:
    """Compute retrieval quality score: evidence signal density."""
    signal_count = len(metric_names) + len(numeric_strings)
    text_length = max(len(chunk_text), 1)
    score = min(signal_count / (text_length / 100.0), 1.0)
    return round(max(score, 0.01), 4)


class ClaimExtractor:
    """Deterministic claim extractor supporting performance, efficiency, and structural claims."""

    def extract(self, chunks: List[IngestionChunk], include_weak: bool = True) -> List[Claim]:
        """Extract claims from chunks using the canonical entrypoint.
        
        Args:
            chunks: List of ingestion chunks
            include_weak: If True, also extract weak-tier claims (inferred context)
        
        Returns:
            List of Claim objects (strong tier only if include_weak=False)
        """
        claims: List[Claim] = []
        
        # Strong tier extraction
        for chunk in chunks:
            request = ClaimExtractionRequest(chunk=chunk)
            results = self._extract_all(request)
            for result in results:
                if result.claim:
                    claims.append(result.claim)
        
        # Weak tier extraction (optional)
        if include_weak:
            weak_claims = self._extract_weak_tier(chunks)
            claims.extend(weak_claims)
        
        return claims

    def _extract_all(self, request: ClaimExtractionRequest) -> List[ClaimExtractionResult]:
        """Extract all claims from a chunk, including decomposed compound claims.

        Returns a list of ClaimExtractionResult. May return:
        - Multiple results for decomposed compound sentences
        - Single result for normal claims
        - Single NoClaim result for rejected sentences
        """
        chunk = request.chunk

        # ── TABLE FRAGMENT GUARD ──
        # Reject chunks that are table fragments (long, multi-line, many numbers).
        # Prevents subject explosion crashes on table-dense PDFs (e.g., ViT).
        if _is_table_fragment(chunk.text):
            return [ClaimExtractionResult(
                no_claim=NoClaim(
                    reason_code=NoClaimReason.TABLE_FRAGMENT_REJECTED,
                    detail=f"Table fragment: len={len(chunk.text)}, newlines={chunk.text.count(chr(10))}, "
                           f"numerics={len(_TABLE_NUMERIC_TOKEN.findall(chunk.text))}",
                )
            )]

        # ── STRUCTURAL CLAIM PATH (no context or numeric requirement) ──
        # Skip structural extraction on table blocks to avoid garbage
        if not _is_table_block(chunk.text):
            structural = self._try_structural(chunk)
            if structural:
                return [structural]

        # ── EFFICIENCY CLAIM PATH (no context requirement) ──
        efficiency = self._try_efficiency(chunk)
        if efficiency:
            return [efficiency]

        # ── PERFORMANCE CLAIM PATH ──
        return self._try_performance(chunk)

    def _try_structural(self, chunk) -> Optional[ClaimExtractionResult]:
        """Try to extract a structural claim (architecture/mechanism description)."""
        text = chunk.text

        # Must have structural entity
        if not _has_structural_entity(text):
            return None

        # Must have structural predicate
        predicate = _find_structural_predicate(text)
        if not predicate:
            return None

        # Hedge filter
        if _is_hedged_statement(text):
            return None

        raw_subject, raw_object = _split_subject_object(text, predicate)
        subject = _clean_subject(raw_subject)
        obj = _normalize_space(_strip_citations(raw_object).rstrip(" .;:"))

        if not subject or not obj:
            return None

        # Must have meaningful subject (at least 2 chars)
        if len(subject) < 2:
            return None

        # Guard against schema length limits on subject/object
        if len(subject) > 500 or len(obj) > 500:
            return ClaimExtractionResult(
                no_claim=NoClaim(
                    reason_code=NoClaimReason.NON_CLAIM,
                    detail=(
                        "structural claim too long: "
                        f"subject_len={len(subject)}, object_len={len(obj)}"
                    ),
                )
            )

        # Guard against oversized subjects from table-dense text
        if len(subject) > _TABLE_SUBJECT_MAX_LENGTH:
            return None

        context_id = chunk.context_id if chunk.context_id and chunk.context_id != "ctx_unknown" else "ctx_structural"

        claim_id = _hash_claim(context_id, subject, predicate, obj)
        retrieval_score = _compute_retrieval_score(chunk.text, chunk.metric_names, chunk.numeric_strings)

        evidence = ClaimEvidence(
            source_id=chunk.source_id,
            page=chunk.page,
            snippet=chunk.text,
            retrieval_score=retrieval_score,
        )

        claim = Claim(
            claim_id=claim_id,
            context_id=context_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.LOW,
            claim_type=ClaimType.STRUCTURAL,
            claim_subtype=ClaimSubtype.ABSOLUTE,
        )

        return ClaimExtractionResult(claim=claim)

    def _try_efficiency(self, chunk) -> Optional[ClaimExtractionResult]:
        """Try to extract an efficiency claim (compute, time, cost)."""
        text = chunk.text

        # Must mention efficiency units
        if not _EFFICIENCY_UNITS.search(text):
            return None

        # Must have numbers
        if not chunk.numeric_strings:
            return None

        # Hedge filter
        if _is_hedged_statement(text):
            return None

        # Must have efficiency predicate OR contain direct efficiency statement
        predicate = _find_efficiency_predicate(text)
        if not predicate:
            # Check performance predicates as fallback (e.g., "achieves X hours")
            predicate = _find_predicate(text)
        if not predicate:
            return None

        raw_subject, raw_object = _split_subject_object(text, predicate)
        subject = _clean_subject(raw_subject)
        obj = _normalize_space(_strip_citations(raw_object).rstrip(" .;:"))

        if not subject or not obj:
            return None

        # Guard against oversized subjects from table-dense text
        if len(subject) > _TABLE_SUBJECT_MAX_LENGTH:
            return None

        # Verify efficiency content is in the object
        if not _EFFICIENCY_UNITS.search(obj):
            return None

        context_id = chunk.context_id if chunk.context_id and chunk.context_id != "ctx_unknown" else "ctx_efficiency"

        claim_id = _hash_claim(context_id, subject, predicate, obj)
        retrieval_score = _compute_retrieval_score(chunk.text, chunk.metric_names, chunk.numeric_strings)

        evidence = ClaimEvidence(
            source_id=chunk.source_id,
            page=chunk.page,
            snippet=chunk.text,
            retrieval_score=retrieval_score,
        )

        claim = Claim(
            claim_id=claim_id,
            context_id=context_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.LOW,
            claim_type=ClaimType.EFFICIENCY,
            claim_subtype=ClaimSubtype.DELTA if _is_delta_claim(text) else ClaimSubtype.ABSOLUTE,
        )

        return ClaimExtractionResult(claim=claim)

    def _try_performance(self, chunk) -> List[ClaimExtractionResult]:
        """Try to extract performance claim(s) from chunk."""
        # Context gate: performance claims require context
        if not chunk.context_id or chunk.context_id == "ctx_unknown":
            return [ClaimExtractionResult(
                no_claim=NoClaim(
                    reason_code=NoClaimReason.CONTEXT_MISSING,
                    detail="context_id missing or unknown",
                )
            )]

        rejection = self._check_performance_rejections(chunk)
        if rejection:
            return [rejection]

        # Try explicit predicate first
        predicate = _find_predicate(chunk.text)
        implicit = None
        if not predicate:
            implicit = _find_implicit_predicate(chunk.text)
            if not implicit:
                return [ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NO_PREDICATE))]
            predicate = implicit[0]

        quant_rejection = self._check_quantitative_requirements(chunk)
        if quant_rejection:
            return [quant_rejection]

        # Compound metric check — try decomposition first
        if _is_compound_metric(chunk.text, chunk.metric_names, chunk.numeric_strings):
            return self._handle_compound(chunk, predicate)

        # Normal single-claim extraction
        return self._build_performance_claim(chunk, predicate, implicit)

    def _check_performance_rejections(self, chunk) -> Optional[ClaimExtractionResult]:
        """Check hedge and non-performance rejections."""
        if _is_hedged_statement(chunk.text):
            return ClaimExtractionResult(
                no_claim=NoClaim(reason_code=NoClaimReason.HEDGED_STATEMENT)
            )
        if chunk.numeric_strings and _is_non_performance_adjacent(chunk.text, chunk.numeric_strings):
            return ClaimExtractionResult(
                no_claim=NoClaim(reason_code=NoClaimReason.NON_PERFORMANCE_NUMERIC)
            )
        return None

    def _check_quantitative_requirements(self, chunk) -> Optional[ClaimExtractionResult]:
        """Check that chunk has both numbers and metrics."""
        if not _is_quantitative_candidate(chunk.numeric_strings, chunk.metric_names):
            if not chunk.numeric_strings:
                return ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NO_NUMBER))
            if not chunk.metric_names:
                return ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NO_METRIC))
            return ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.NON_CLAIM))
        return None

    def _handle_compound(self, chunk, predicate: str) -> List[ClaimExtractionResult]:
        """Handle compound metric sentences — attempt decomposition."""
        decomposed = _try_decompose_compound(
            chunk.text, chunk.metric_names,
        )
        if decomposed:
            return self._extract_decomposed(chunk, decomposed, predicate)
        return [ClaimExtractionResult(
            no_claim=NoClaim(reason_code=NoClaimReason.COMPOUND_METRIC)
        )]

    def _build_performance_claim(
        self, chunk, predicate: str, implicit: Optional[Tuple[str, str, str]]
    ) -> List[ClaimExtractionResult]:
        """Build a single performance claim from chunk."""
        if implicit:
            subject_raw, obj_raw = implicit[1], implicit[2]
        else:
            subject_raw, obj_raw = _split_subject_object(chunk.text, predicate)

        subject = _clean_subject(subject_raw)
        obj = _normalize_space(_strip_citations(obj_raw).rstrip(" .;:"))

        if not subject:
            return [ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.SUBJECT_MISSING))]
        if not obj:
            return [ClaimExtractionResult(no_claim=NoClaim(reason_code=NoClaimReason.OBJECT_MISSING))]
        # Guard against oversized subjects from table-dense text
        if len(subject) > _TABLE_SUBJECT_MAX_LENGTH:
            return [ClaimExtractionResult(
                no_claim=NoClaim(
                    reason_code=NoClaimReason.TABLE_FRAGMENT_REJECTED,
                    detail=f"Subject too long: {len(subject)} chars",
                )
            )]

        claim_id = _hash_claim(chunk.context_id, subject, predicate, obj)
        retrieval_score = _compute_retrieval_score(chunk.text, chunk.metric_names, chunk.numeric_strings)

        evidence = ClaimEvidence(
            source_id=chunk.source_id,
            page=chunk.page,
            snippet=chunk.text,
            retrieval_score=retrieval_score,
        )

        claim = Claim(
            claim_id=claim_id,
            context_id=chunk.context_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.LOW,
            claim_type=ClaimType.PERFORMANCE,
            claim_subtype=ClaimSubtype.DELTA if _is_delta_claim(chunk.text) else ClaimSubtype.ABSOLUTE,
        )

        return [ClaimExtractionResult(claim=claim)]

    def _extract_decomposed(
        self, chunk, parts: List[str], predicate: str
    ) -> List[ClaimExtractionResult]:
        """Extract atomic claims from decomposed compound sentence."""
        results = []
        carry_subject = ""
        carry_predicate = predicate
        for part in parts:
            part = part.strip()
            if not part:
                continue

            part_predicate, subject, obj_clean = self._parse_decomposed_part(
                part, carry_subject, carry_predicate,
            )
            if not subject or not obj_clean:
                continue

            carry_subject = subject
            carry_predicate = part_predicate

            claim_id = _hash_claim(chunk.context_id, subject, part_predicate, obj_clean)
            retrieval_score = _compute_retrieval_score(chunk.text, chunk.metric_names, chunk.numeric_strings)

            evidence = ClaimEvidence(
                source_id=chunk.source_id,
                page=chunk.page,
                snippet=chunk.text,
                retrieval_score=retrieval_score,
            )

            claim = Claim(
                claim_id=claim_id,
                context_id=chunk.context_id,
                subject=subject,
                predicate=part_predicate,
                object=obj_clean,
                evidence=[evidence],
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.LOW,
                claim_type=ClaimType.PERFORMANCE,
                claim_subtype=ClaimSubtype.DELTA if _is_delta_claim(chunk.text) else ClaimSubtype.ABSOLUTE,
            )

            results.append(ClaimExtractionResult(claim=claim))

        if not results:
            return [ClaimExtractionResult(
                no_claim=NoClaim(reason_code=NoClaimReason.COMPOUND_METRIC)
            )]

        return results

    @staticmethod
    def _parse_decomposed_part(
        part: str, carry_subject: str, carry_predicate: str,
    ) -> Tuple[str, str, str]:
        """Parse a single decomposed fragment into (predicate, subject, object)."""
        part_predicate = _find_predicate(part)
        if part_predicate:
            sub, obj = _split_subject_object(part, part_predicate)
        else:
            implicit = _find_implicit_predicate(part)
            if implicit:
                part_predicate, sub, obj = implicit
            else:
                part_predicate = carry_predicate
                sub = carry_subject
                obj = part

        subject = _clean_subject(sub)
        obj_clean = _normalize_space(_strip_citations(obj).rstrip(" .;:"))
        return part_predicate, subject, obj_clean

    def _extract_weak_tier(self, chunks: List[IngestionChunk]) -> List[Claim]:
        """Extract weak-tier claims from chunks.
        
        Weak claims accept quantitative delta + measurable property without requiring
        explicit dataset/metric context. These are tagged as context_inferred=True
        and kept in a separate tier to prevent mixing with strong claims.
        
        Examples of weak claims:
        - "Latency improved by 34%"
        - "Error reduced from 0.54 to 0.31"
        - "2.3x improvement over baseline"
        - "p < 0.01 for mortality reduction"
        
        Returns:
            List of Claim objects with tier=WEAK and context_inferred=True
        """
        from services.extraction.weak_claim_validator import WeakClaimValidator
        from services.extraction.context_stitcher import (
            stitch_context,
            get_inferred_dataset,
            has_inferred_performancy_context,
        )
        from core.schemas.claim import ClaimTier
        
        weak_claims: List[Claim] = []
        enriched_chunks = stitch_context(chunks)
        enriched_by_id = {ec.chunk.chunk_id: ec for ec in enriched_chunks}
        
        for chunk in chunks:
            text = chunk.text.strip()
            if not text or len(text) < 10:  # Skip very short chunks
                continue

            enriched = enriched_by_id.get(chunk.chunk_id)
            has_context_signal = bool(
                enriched and has_inferred_performancy_context(enriched)
            )
            
            # Validate against weak claim criteria
            is_valid, _ = WeakClaimValidator.validate(text)
            if not is_valid:
                continue

            # Weak claims still require some local or paragraph-level context signal
            if not chunk.metric_names and not has_context_signal:
                continue
            
            # Extract numeric value for object representation
            value = WeakClaimValidator.extract_quantitative_value(text)
            inferred_dataset = get_inferred_dataset(enriched) if enriched else None

            inferred_metric = None
            if chunk.metric_names:
                inferred_metric = sorted(chunk.metric_names)[0]
            elif enriched and enriched.paragraph_context and enriched.paragraph_context.metric_names:
                inferred_metric = sorted(enriched.paragraph_context.metric_names)[0]

            subject = "quantitative property"
            if inferred_dataset:
                subject = f"quantitative property on {inferred_dataset}"
            
            # Construct weak claim
            try:
                claim = Claim(
                    claim_id=f"weak_{chunk.chunk_id}",
                    context_id=chunk.context_id,
                    subject=subject,
                    predicate="changed",
                    object=f"{value}%" if value else "observed improvement",
                    claim_type=ClaimType.PERFORMANCE,
                    claim_subtype=ClaimSubtype.DELTA,
                    polarity=Polarity.SUPPORTS,
                    confidence_level=ConfidenceLevel.MEDIUM,
                    evidence=[
                        ClaimEvidence(
                            source_id=chunk.source_id,
                            page=chunk.page,
                            snippet=text,
                            retrieval_score=0.8,  # Weak claims get lower confidence
                        )
                    ],
                    tier=ClaimTier.WEAK,
                    context_explicit=False,
                    context_inferred=True,
                    dataset_explicit=None,
                    metric_explicit=inferred_metric,
                )
                weak_claims.append(claim)
            except Exception:
                # Skip malformed claims
                continue
        
        return weak_claims

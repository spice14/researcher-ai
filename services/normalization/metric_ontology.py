"""Metric Ontology Layer — Deterministic domain metric synonym mapping.

PHASE B: Semantic Recall Expansion
Goal: Increase normalized claim yield from ~12.9% to ≥30%

Strategy: Map domain-specific metric synonyms to canonical metric names
WITHOUT introducing nondeterminism or numeric misbindings.

Rules:
- All mappings are static and deterministic
- No fuzzy matching, no embeddings, no LLM calls
- Lowercase normalization + punctuation stripping
- Multiple synonym forms supported per canonical metric
- Cross-domain coverage (CV, NLP, Speech, RL, General ML, Performance)

Architecture:
- This module is PURE DATA
- No service imports, no dynamic lookups
- Can be versioned independently
- Can be audited for correctness

Usage:
    from services.normalization.metric_ontology import resolve_metric_synonym
    
    canonical = resolve_metric_synonym("top-1 accuracy")  # → "ACCURACY"
    canonical = resolve_metric_synonym("word error rate")  # → "WER"
    canonical = resolve_metric_synonym("unknown metric")  # → None
"""

from typing import Optional, Dict, List
import re


# Canonical Metric Ontology (Domain-Specific)
# Key: Canonical metric name (uppercase)
# Value: List of lowercase synonym variants (include punctuation variations)
METRIC_SYNONYMS: Dict[str, List[str]] = {
    # Computer Vision - Classification
    "ACCURACY": [
        "accuracy",
        "top1",
        "top-1",
        "top 1",
        "top1 accuracy",
        "top-1 accuracy",
        "top 1 accuracy",
        "classification accuracy",
        "test accuracy",
        "validation accuracy",
        "val accuracy",
    ],
    "TOP5_ACCURACY": [
        "top5",
        "top-5",
        "top 5",
        "top5 accuracy",
        "top-5 accuracy",
        "top 5 accuracy",
    ],
    
    # Computer Vision - Detection/Segmentation
    "MAP": [
        "map",
        "mean average precision",
        "mean ap",
        "average precision",
    ],
    "IOU": [
        "iou",
        "intersection over union",
        "mean iou",
        "miou",
    ],
    "FPS": [
        "fps",
        "frames per second",
        "frame rate",
        "inference fps",
    ],
    
    # NLP - General
    "F1": [
        "f1",
        "f1-score",
        "f1 score",
        "f-1",
        "f measure",
    ],
    "PRECISION": [
        "precision",
        "prec",
    ],
    "RECALL": [
        "recall",
        "rec",
    ],
    "EXACT_MATCH": [
        "exact match",
        "em",
        "exact match score",
        "squad em",
    ],
    
    # NLP - Machine Translation
    "BLEU": [
        "bleu",
        "bleu score",
        "bleu-4",
        "bleu4",
    ],
    "ROUGE": [
        "rouge",
        "rouge score",
    ],
    "ROUGE_L": [
        "rouge-l",
        "rouge l",
        "rougel",
    ],
    "METEOR": [
        "meteor",
        "meteor score",
    ],
    
    # NLP - Language Modeling
    "PERPLEXITY": [
        "perplexity",
        "ppl",
        "test perplexity",
        "validation perplexity",
    ],
    
    # NLP - Benchmarks
    "GLUE_SCORE": [
        "glue",
        "glue score",
        "average glue",
    ],
    "SUPERGLUE_SCORE": [
        "superglue",
        "superglue score",
        "average superglue",
    ],
    
    # Speech Recognition
    "WER": [
        "wer",
        "word error rate",
        "test wer",
    ],
    "CER": [
        "cer",
        "character error rate",
    ],
    
    # Reinforcement Learning
    "REWARD": [
        "reward",
        "average reward",
        "mean reward",
        "average return",
        "mean return",
        "episodic return",
        "episode reward",
        "cumulative reward",
    ],
    "SUCCESS_RATE": [
        "success rate",
        "task success",
        "success percentage",
    ],
    
    # Regression Metrics
    "MSE": [
        "mse",
        "mean squared error",
        "mean square error",
    ],
    "RMSE": [
        "rmse",
        "root mean squared error",
        "root mean square error",
    ],
    "MAE": [
        "mae",
        "mean absolute error",
    ],
    "MAPE": [
        "mape",
        "mean absolute percentage error",
    ],
    "R_SQUARED": [
        "r-squared",
        "r squared",
        "r2",
        "r^2",
        "coefficient of determination",
    ],
    
    # Classification Metrics
    "AUC": [
        "auc",
        "auroc",
        "roc auc",
        "area under roc",
        "roc-auc",
    ],
    "AUPRC": [
        "auprc",
        "pr auc",
        "area under pr",
        "pr-auc",
    ],
    
    # Performance Metrics
    "THROUGHPUT": [
        "throughput",
        "samples/sec",
        "samples per second",
        "samples/s",
        "tokens/sec",
        "tokens per second",
        "tokens/s",
        "images/sec",
        "images per second",
    ],
    "LATENCY": [
        "latency",
        "inference latency",
        "inference time",
        "ms latency",
        "millisecond latency",
    ],
    "MEMORY": [
        "memory",
        "memory usage",
        "peak memory",
        "gpu memory",
    ],
    
    # Training Metrics
    "TRAINING_TIME": [
        "training time",
        "train time",
        "time to train",
    ],
    "CONVERGENCE_STEPS": [
        "convergence steps",
        "steps to convergence",
        "training steps",
    ],
    
    # Other Common Metrics
    "LOSS": [
        "loss",
        "training loss",
        "test loss",
        "validation loss",
        "cross-entropy loss",
    ],
    "ERROR_RATE": [
        "error rate",
        "test error",
        "classification error",
    ],
}


# Reverse index: synonym → canonical (built once at module load)
_SYNONYM_TO_CANONICAL: Dict[str, str] = {}
for canonical, synonyms in METRIC_SYNONYMS.items():
    for synonym in synonyms:
        if synonym in _SYNONYM_TO_CANONICAL:
            raise ValueError(
                f"Duplicate synonym '{synonym}' mapped to both "
                f"'{canonical}' and '{_SYNONYM_TO_CANONICAL[synonym]}'"
            )
        _SYNONYM_TO_CANONICAL[synonym] = canonical


def normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase + strip punctuation.
    
    Rules:
    - Convert to lowercase
    - Replace hyphens/underscores with spaces
    - Remove all other punctuation
    - Collapse multiple spaces
    - Strip leading/trailing whitespace
    
    Args:
        text: Raw metric name from paper
    
    Returns:
        Normalized text ready for lookup
    
    Examples:
        >>> normalize_text("Top-1 Accuracy")
        'top 1 accuracy'
        >>> normalize_text("BLEU-4")
        'bleu 4'
        >>> normalize_text("F1-Score")
        'f1 score'
    """
    normalized = text.lower()
    
    # Replace hyphens/underscores with spaces
    normalized = normalized.replace("-", " ").replace("_", " ")
    
    # Remove punctuation except spaces
    normalized = re.sub(r"[^\w\s]", "", normalized)
    
    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized)
    
    # Strip whitespace
    normalized = normalized.strip()
    
    return normalized


def resolve_metric_synonym(metric_text: str) -> Optional[str]:
    """Resolve a metric synonym to its canonical form.
    
    Deterministic lookup using static synonym table.
    No fuzzy matching, no LLM calls, no embeddings.
    
    Args:
        metric_text: Metric name from paper (e.g., "Top-1 Accuracy", "BLEU")
    
    Returns:
        Canonical metric name (e.g., "ACCURACY", "BLEU") or None if unknown
    
    Examples:
        >>> resolve_metric_synonym("top-1 accuracy")
        'ACCURACY'
        >>> resolve_metric_synonym("Top1")
        'ACCURACY'
        >>> resolve_metric_synonym("BLEU-4")
        'BLEU'
        >>> resolve_metric_synonym("unknown metric")
        None
    """
    normalized = normalize_text(metric_text)
    return _SYNONYM_TO_CANONICAL.get(normalized)


def find_metric_candidates_in_text(text: str) -> List[str]:
    """Find all potential metric references in a text snippet.
    
    Scans text for known metric synonyms (deterministic keyword matching).
    Returns canonical metric names for all matches found.
    
    PHASE B: Enhanced to prefer longer matches (e.g., "word error rate" over "error rate").
    
    Args:
        text: Text snippet (e.g., sentence, claim text)
    
    Returns:
        List of canonical metric names found (deduplicated, longest matches preferred)
    
    Examples:
        >>> find_metric_candidates_in_text("achieves 93.2% top-1 accuracy")
        ['ACCURACY']
        >>> find_metric_candidates_in_text("BLEU of 28.4 and ROUGE-L of 0.52")
        ['BLEU', 'ROUGE_L']
        >>> find_metric_candidates_in_text("no metrics here")
        []
    """
    normalized_text = normalize_text(text)
    
    # Find all matches with their positions
    matches = []  # List of (start, end, canonical_name, synonym)
    
    for synonym, canonical in _SYNONYM_TO_CANONICAL.items():
        # Word boundary check (avoid partial matches like "top" in "laptop")
        pattern = r'\b' + re.escape(synonym) + r'\b'
        for match in re.finditer(pattern, normalized_text):
            matches.append((match.start(), match.end(), canonical, synonym))
    
    if not matches:
        return []
    
    # Sort by start position, then by length (longest first)
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    
    # Filter overlapping matched: prefer longer matches
    selected = []
    used_ranges = []
    
    for start, end, canonical, synonym in matches:
        # Check if this range overlaps with any previously selected range
        overlaps = False
        for used_start, used_end in used_ranges:
            if not (end <= used_start or start >= used_end):  # Ranges overlap
                overlaps = True
                break
        
        if not overlaps:
            selected.append(canonical)
            used_ranges.append((start, end))
    
    # Deduplicate while preserving order
    seen = set()
    result = []
    for canonical in selected:
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    
    return result


def resolve_metric_from_context(
    metric_text: Optional[str],
    context_text: str
) -> Optional[str]:
    """Resolve metric using both explicit metric field and context.
    
    Strategy:
    1. If metric_text is valid synonym → resolve directly
    2. Else, scan context_text for metric synonyms
    3. If exactly one canonical metric found → return it
    4. If zero or multiple found → return None (ambiguous)
    
    This function is used by normalization service to improve recall
    when metric names are implicit or embedded in text.
    
    Args:
        metric_text: Explicit metric field (may be None or non-standard)
        context_text: Surrounding text (e.g., full claim sentence)
    
    Returns:
        Canonical metric name or None if ambiguous/unknown
    
    Examples:
        >>> resolve_metric_from_context(None, "achieves 93.2% top-1 accuracy")
        'ACCURACY'
        >>> resolve_metric_from_context("top1", "...")
        'ACCURACY'
        >>> resolve_metric_from_context(None, "BLEU and ROUGE scores")
        None  # Ambiguous (multiple metrics)
    """
    # Try explicit metric first
    if metric_text:
        canonical = resolve_metric_synonym(metric_text)
        if canonical:
            return canonical
    
    # Scan context for metric synonyms
    candidates = find_metric_candidates_in_text(context_text)
    
    # Return only if exactly one match (unambiguous)
    if len(candidates) == 1:
        return candidates[0]
    
    # Zero or multiple matches → reject as ambiguous
    return None


def get_all_canonical_metrics() -> List[str]:
    """Get list of all canonical metric names in ontology.
    
    Returns:
        Sorted list of canonical metric names
    """
    return sorted(METRIC_SYNONYMS.keys())


def get_synonyms_for_metric(canonical: str) -> List[str]:
    """Get all synonyms for a canonical metric.
    
    Args:
        canonical: Canonical metric name (e.g., "ACCURACY")
    
    Returns:
        List of synonyms or empty list if unknown
    """
    return METRIC_SYNONYMS.get(canonical, [])


# Validation on module load
if __name__ == "__main__":
    # Self-test: ensure no duplicate synonyms
    print(f"Loaded {len(METRIC_SYNONYMS)} canonical metrics")
    print(f"Mapped {len(_SYNONYM_TO_CANONICAL)} total synonyms")
    
    # Test examples
    test_cases = [
        ("Top-1 Accuracy", "ACCURACY"),
        ("BLEU", "BLEU"),
        ("word error rate", "WER"),
        ("f1-score", "F1_SCORE"),
        ("unknown", None),
    ]
    
    print("\nTest cases:")
    for text, expected in test_cases:
        result = resolve_metric_synonym(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected {expected})")

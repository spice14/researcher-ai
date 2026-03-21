"""Evaluation metrics for ScholarOS pipeline quality.

Computes:
- Claim extraction: Precision, Recall, F1
- Cluster quality: Purity, NMI
- Hypothesis quality scoring
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple


# ─── Claim Extraction Metrics ──────────────────────────────────────────────

def compute_claim_metrics(
    predicted_claims: List[Dict],
    gold_claims: List[Dict],
    match_field: str = "text",
    fuzzy: bool = True,
) -> Dict[str, float]:
    """Compute Precision, Recall, F1 for claim extraction.

    Args:
        predicted_claims: Claims extracted by the pipeline
        gold_claims: Ground truth annotated claims
        match_field: Field to match on ('text', 'claim_id')
        fuzzy: Use token overlap for text matching

    Returns:
        Dict with precision, recall, f1, tp, fp, fn counts
    """
    if not gold_claims:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": len(predicted_claims), "fn": 0}

    gold_texts = {_normalize(c.get(match_field, "")) for c in gold_claims}
    pred_texts = {_normalize(c.get(match_field, "")) for c in predicted_claims}

    if fuzzy:
        tp = sum(1 for p in pred_texts if _fuzzy_match(p, gold_texts))
        fp = len(pred_texts) - tp
        fn = sum(1 for g in gold_texts if not _fuzzy_match(g, pred_texts))
    else:
        tp = len(pred_texts & gold_texts)
        fp = len(pred_texts - gold_texts)
        fn = len(gold_texts - pred_texts)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _fuzzy_match(query: str, candidates: Set[str], threshold: float = 0.6) -> bool:
    """Return True if query overlaps with any candidate above threshold."""
    qtoks = set(query.split())
    if not qtoks:
        return False
    for cand in candidates:
        ctoks = set(cand.split())
        if not ctoks:
            continue
        overlap = len(qtoks & ctoks) / max(len(qtoks), len(ctoks))
        if overlap >= threshold:
            return True
    return False


# ─── Cluster Quality Metrics ───────────────────────────────────────────────

def compute_cluster_purity(
    predicted_clusters: List[Dict],
    gold_clusters: List[Dict],
) -> Dict[str, float]:
    """Compute cluster purity and NMI.

    Args:
        predicted_clusters: Clusters from pipeline (each with 'paper_ids', 'label')
        gold_clusters: Ground truth clusters (each with 'paper_ids', 'label')

    Returns:
        Dict with purity, nmi
    """
    # Build assignment maps
    pred_assignment: Dict[str, str] = {}
    for c in predicted_clusters:
        for pid in c.get("paper_ids", []):
            pred_assignment[pid] = c.get("cluster_id", c.get("label", "unk"))

    gold_assignment: Dict[str, str] = {}
    for c in gold_clusters:
        for pid in c.get("paper_ids", []):
            gold_assignment[pid] = c.get("cluster_id", c.get("label", "unk"))

    # Only evaluate papers in both
    common = set(pred_assignment.keys()) & set(gold_assignment.keys())
    if not common:
        return {"purity": 0.0, "nmi": 0.0, "n_papers": 0}

    n = len(common)
    # Purity: for each predicted cluster, find majority gold label
    pred_to_gold: Dict[str, List[str]] = {}
    for pid in common:
        pc = pred_assignment[pid]
        gc = gold_assignment[pid]
        pred_to_gold.setdefault(pc, []).append(gc)

    correct = 0
    for cluster_pids_gold in pred_to_gold.values():
        # Count most common gold label
        counts: Dict[str, int] = {}
        for g in cluster_pids_gold:
            counts[g] = counts.get(g, 0) + 1
        correct += max(counts.values())

    purity = correct / n

    # NMI approximation
    nmi = _compute_nmi(list(common), pred_assignment, gold_assignment)

    return {
        "purity": round(purity, 4),
        "nmi": round(nmi, 4),
        "n_papers": n,
    }


def _compute_nmi(
    papers: List[str],
    pred: Dict[str, str],
    gold: Dict[str, str],
) -> float:
    """Compute normalized mutual information between two clusterings."""
    n = len(papers)
    if n == 0:
        return 0.0

    pred_labels = [pred[p] for p in papers]
    gold_labels = [gold[p] for p in papers]

    # Count joint and marginal frequencies
    pred_counts: Dict[str, int] = {}
    gold_counts: Dict[str, int] = {}
    joint_counts: Dict[Tuple[str, str], int] = {}

    for pl, gl in zip(pred_labels, gold_labels):
        pred_counts[pl] = pred_counts.get(pl, 0) + 1
        gold_counts[gl] = gold_counts.get(gl, 0) + 1
        key = (pl, gl)
        joint_counts[key] = joint_counts.get(key, 0) + 1

    # Mutual information
    mi = 0.0
    for (pl, gl), count in joint_counts.items():
        p_joint = count / n
        p_pred = pred_counts[pl] / n
        p_gold = gold_counts[gl] / n
        if p_joint > 0:
            mi += p_joint * math.log(p_joint / (p_pred * p_gold) + 1e-10)

    # Entropies
    h_pred = -sum((c / n) * math.log(c / n + 1e-10) for c in pred_counts.values())
    h_gold = -sum((c / n) * math.log(c / n + 1e-10) for c in gold_counts.values())

    denom = (h_pred + h_gold) / 2
    if denom == 0:
        return 1.0
    return max(0.0, mi / denom)


# ─── Hypothesis Quality Scoring ────────────────────────────────────────────

def score_hypothesis(hypothesis: Dict) -> Dict[str, float]:
    """Score hypothesis quality on multiple dimensions.

    Args:
        hypothesis: Hypothesis dict from pipeline

    Returns:
        Dict with dimension scores and aggregate
    """
    scores = {}

    # Completeness: required fields present and non-empty
    required = ["statement", "assumptions", "independent_variables", "dependent_variables", "novelty_basis"]
    completeness = sum(1 for f in required if hypothesis.get(f)) / len(required)
    scores["completeness"] = round(completeness, 4)

    # Confidence: use numeric score if available
    conf = hypothesis.get("confidence_score")
    if conf is not None:
        scores["confidence"] = round(float(conf), 4)
    else:
        # Map qualitative
        qual = str(hypothesis.get("qualitative_confidence", "")).lower()
        qual_map = {"high": 0.85, "medium": 0.5, "low": 0.2}
        scores["confidence"] = qual_map.get(qual, 0.5)

    # Evidence grounding
    supporting = len(hypothesis.get("supporting_citations", []) + hypothesis.get("grounding_claim_ids", []))
    scores["evidence_grounding"] = min(1.0, supporting / 5.0)

    # Revision depth
    revision_history = hypothesis.get("revision_history", [])
    scores["revision_depth"] = min(1.0, len(revision_history) / 3.0)

    # Aggregate
    weights = {"completeness": 0.4, "confidence": 0.3, "evidence_grounding": 0.2, "revision_depth": 0.1}
    aggregate = sum(scores[k] * w for k, w in weights.items() if k in scores)
    scores["aggregate"] = round(aggregate, 4)

    return scores


# ─── Provenance Metrics ─────────────────────────────────────────────────────

def compute_provenance_coverage(trace_entries: List[Dict]) -> Dict[str, Any]:
    """Compute what fraction of trace entries have full provenance.

    Args:
        trace_entries: List of trace entry dicts

    Returns:
        Dict with coverage stats
    """
    if not trace_entries:
        return {"coverage": 0.0, "total": 0, "with_hash": 0}

    with_hash = sum(
        1 for e in trace_entries
        if e.get("input_hash") and e.get("output_hash")
    )
    return {
        "coverage": round(with_hash / len(trace_entries), 4),
        "total": len(trace_entries),
        "with_hash": with_hash,
    }

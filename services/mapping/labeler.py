"""LLM cluster labeler with versioned prompt.

Generates human-readable labels for literature clusters using
representative paper text. Falls back to deterministic labels
when LLM is unavailable.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CLUSTER_LABEL_PROMPT = """\
You are labeling a cluster of related research papers. Based on the following \
representative text snippets from papers in this cluster, generate a short \
(5-15 word) descriptive label that captures the main research theme.

Snippets:
{snippets}

Respond with ONLY the label text, no quotes, no explanation."""

CLUSTER_LABEL_PROMPT_VERSION = "cluster_label_v1.0.0"


def label_cluster(
    representative_texts: List[str],
    llm_client=None,
    cluster_index: int = 0,
) -> str:
    """Generate a label for a cluster of papers.

    Args:
        representative_texts: Text snippets from representative papers
        llm_client: Optional OllamaClient for LLM-based labeling
        cluster_index: Fallback index for deterministic label

    Returns:
        Human-readable cluster label
    """
    if not representative_texts:
        return f"Research Cluster {cluster_index}"

    # Try LLM labeling
    if llm_client is not None:
        try:
            snippets = "\n".join(f"- {t[:200]}" for t in representative_texts[:5])
            prompt = CLUSTER_LABEL_PROMPT.format(snippets=snippets)
            resp = llm_client.generate(
                prompt,
                prompt_version=CLUSTER_LABEL_PROMPT_VERSION,
                temperature=0.2,
                max_tokens=50,
            )
            label = resp.text.strip().strip('"').strip("'")
            if label and len(label) < 100:
                return label
        except Exception as exc:
            logger.warning("LLM cluster labeling failed: %s", exc)

    # Deterministic fallback: extract common terms
    return _deterministic_label(representative_texts, cluster_index)


def _deterministic_label(texts: List[str], cluster_index: int) -> str:
    """Generate a deterministic label from common terms in texts."""
    import re
    from collections import Counter

    # Stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "of", "in", "to",
        "for", "with", "on", "at", "from", "by", "about", "as", "into",
        "through", "during", "before", "after", "above", "below", "between",
        "out", "off", "over", "under", "again", "further", "then", "once",
        "and", "but", "or", "nor", "not", "no", "so", "than", "too", "very",
        "that", "this", "these", "those", "it", "its", "we", "our", "they",
        "their", "which", "what", "who", "whom", "when", "where", "how",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "only", "own", "same", "also", "just", "if",
        "using", "based", "results", "paper", "show", "propose", "method",
    }

    word_counts: Counter = Counter()
    for text in texts:
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        for w in words:
            if w not in stopwords:
                word_counts[w] += 1

    top_words = [w for w, _ in word_counts.most_common(5)]
    if top_words:
        return " ".join(w.capitalize() for w in top_words[:4])

    return f"Research Cluster {cluster_index}"

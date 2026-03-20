"""HDBSCAN clustering wrapper with deterministic seed.

Wraps HDBSCAN for literature clustering with fallback to KMeans
when HDBSCAN is unavailable.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def cluster_embeddings(
    paper_ids: List[str],
    embeddings: List[List[float]],
    min_cluster_size: int = 3,
    random_seed: int = 42,
) -> Tuple[Dict[int, List[str]], List[str]]:
    """Cluster paper embeddings and return cluster assignments.

    Args:
        paper_ids: Paper identifiers
        embeddings: Paper embedding vectors
        min_cluster_size: Minimum cluster size

    Returns:
        Tuple of (cluster_id -> paper_ids, noise_paper_ids)
    """
    if len(paper_ids) < min_cluster_size:
        return {}, list(paper_ids)

    emb_array = np.array(embeddings, dtype=np.float64)

    # Try HDBSCAN first
    try:
        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
            core_dist_n_jobs=1,
        )
        labels = clusterer.fit_predict(emb_array)
        logger.info("HDBSCAN clustering: %d clusters found", len(set(labels) - {-1}))
    except ImportError:
        logger.info("HDBSCAN not available, falling back to KMeans")
        labels = _kmeans_fallback(emb_array, min_cluster_size, random_seed)

    # Build cluster dict
    clusters: Dict[int, List[str]] = {}
    noise: List[str] = []

    for i, label in enumerate(labels):
        if label == -1:
            noise.append(paper_ids[i])
        else:
            label_int = int(label)
            if label_int not in clusters:
                clusters[label_int] = []
            clusters[label_int].append(paper_ids[i])

    return clusters, noise


def _kmeans_fallback(
    embeddings: np.ndarray,
    min_cluster_size: int,
    random_seed: int,
) -> List[int]:
    """Simple KMeans fallback when HDBSCAN is unavailable."""
    from sklearn.cluster import KMeans

    n_samples = len(embeddings)
    # Estimate k: sqrt(n/2) rounded, minimum 2
    k = max(2, min(int((n_samples / 2) ** 0.5), n_samples // min_cluster_size))

    kmeans = KMeans(n_clusters=k, random_state=random_seed, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    return labels.tolist()


def find_representative_papers(
    paper_ids: List[str],
    embeddings: List[List[float]],
    n: int = 3,
) -> List[str]:
    """Find papers closest to the centroid."""
    if not paper_ids:
        return []

    emb_array = np.array(embeddings, dtype=np.float64)
    centroid = emb_array.mean(axis=0)
    distances = np.linalg.norm(emb_array - centroid, axis=1)
    indices = np.argsort(distances)[:n]
    return [paper_ids[i] for i in indices]


def find_boundary_papers(
    paper_ids: List[str],
    embeddings: List[List[float]],
    n: int = 2,
) -> List[str]:
    """Find papers farthest from the centroid (boundary papers)."""
    if not paper_ids:
        return []

    emb_array = np.array(embeddings, dtype=np.float64)
    centroid = emb_array.mean(axis=0)
    distances = np.linalg.norm(emb_array - centroid, axis=1)
    indices = np.argsort(distances)[-n:]
    return [paper_ids[i] for i in indices]


def compute_centroid(embeddings: List[List[float]]) -> List[float]:
    """Compute the centroid of a set of embeddings."""
    if not embeddings:
        return []
    return np.array(embeddings, dtype=np.float64).mean(axis=0).tolist()

"""Tests for the literature mapping service — clustering, labeling, integration."""

import numpy as np
import pytest

from services.mapping.service import LiteratureMappingService
from services.mapping.schemas import MappingRequest
from services.mapping.clusterer import (
    cluster_embeddings,
    compute_centroid,
    find_boundary_papers,
    find_representative_papers,
)
from services.mapping.labeler import label_cluster, _deterministic_label
from services.mapping.tool import MappingTool


def _make_synthetic_embeddings(n_clusters=3, points_per_cluster=8, dim=32):
    """Generate synthetic embeddings with clear cluster structure."""
    rng = np.random.RandomState(42)
    paper_ids = []
    embeddings = []

    for c in range(n_clusters):
        center = rng.randn(dim) * 3 + c * 5
        for i in range(points_per_cluster):
            point = center + rng.randn(dim) * 0.5
            paper_ids.append(f"paper_{c}_{i}")
            embeddings.append(point.tolist())

    return paper_ids, embeddings


class TestClustering:
    """HDBSCAN/KMeans clustering tests."""

    def test_cluster_basic(self):
        paper_ids, embeddings = _make_synthetic_embeddings(n_clusters=3, points_per_cluster=8)
        clusters, noise = cluster_embeddings(paper_ids, embeddings, min_cluster_size=3)

        assert len(clusters) >= 2, f"Expected >= 2 clusters, got {len(clusters)}"
        total_clustered = sum(len(v) for v in clusters.values())
        assert total_clustered + len(noise) == len(paper_ids)

    def test_deterministic_clustering(self):
        paper_ids, embeddings = _make_synthetic_embeddings()
        c1, n1 = cluster_embeddings(paper_ids, embeddings, min_cluster_size=3)
        c2, n2 = cluster_embeddings(paper_ids, embeddings, min_cluster_size=3)
        assert c1 == c2
        assert n1 == n2

    def test_too_few_papers(self):
        clusters, noise = cluster_embeddings(
            ["p1", "p2"], [[1, 0], [0, 1]], min_cluster_size=3
        )
        assert len(clusters) == 0
        assert len(noise) == 2

    def test_representative_papers(self):
        paper_ids = ["a", "b", "c", "d"]
        embeddings = [[0, 0], [1, 0], [0, 1], [0.1, 0.1]]
        reps = find_representative_papers(paper_ids, embeddings, n=2)
        assert len(reps) == 2
        # Paper closest to centroid should be first
        assert reps[0] in paper_ids

    def test_boundary_papers(self):
        paper_ids = ["a", "b", "c"]
        embeddings = [[0, 0], [10, 10], [5, 5]]
        boundary = find_boundary_papers(paper_ids, embeddings, n=1)
        assert len(boundary) == 1

    def test_compute_centroid(self):
        embeddings = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        centroid = compute_centroid(embeddings)
        assert len(centroid) == 2
        assert abs(centroid[0] - 2/3) < 0.01
        assert abs(centroid[1] - 2/3) < 0.01

    def test_empty_centroid(self):
        assert compute_centroid([]) == []


class TestLabeler:
    """Cluster labeling tests."""

    def test_deterministic_label(self):
        texts = [
            "Transformer models for natural language processing",
            "Attention mechanisms in transformer architectures",
            "BERT and GPT transformer language models",
        ]
        label = _deterministic_label(texts, 0)
        assert len(label) > 0
        assert "transformer" in label.lower() or "language" in label.lower() or "attention" in label.lower()

    def test_empty_texts_fallback(self):
        label = label_cluster([], cluster_index=5)
        assert "5" in label

    def test_label_without_llm(self):
        texts = ["deep learning for computer vision"]
        label = label_cluster(texts, llm_client=None, cluster_index=0)
        assert len(label) > 0


class TestLiteratureMappingService:
    """Service-level mapping tests."""

    def test_build_map_from_embeddings(self):
        paper_ids, embeddings = _make_synthetic_embeddings(n_clusters=3, points_per_cluster=8)
        svc = LiteratureMappingService()
        result = svc.build_map_from_embeddings(
            paper_ids, embeddings, min_cluster_size=3
        )

        assert result.map_id
        assert result.paper_count == len(paper_ids)
        assert len(result.clusters) >= 2
        for cluster in result.clusters:
            assert cluster["label"]
            assert cluster["paper_count"] > 0
            assert len(cluster["representative_paper_ids"]) > 0


class TestMappingTool:
    """MCP contract tests for the mapping tool."""

    def test_manifest(self):
        tool = MappingTool()
        m = tool.manifest()
        assert m.name == "mapping"
        assert m.version == "1.0.0"

    def test_call_no_vector_store(self):
        tool = MappingTool(service=LiteratureMappingService())
        result = tool.call({"topic": "transformers"})
        assert "map_id" in result
        assert "warnings" in result

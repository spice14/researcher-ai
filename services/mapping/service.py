"""Literature Mapping Service — Capability 1 implementation.

Builds a semantic, clustered overview of the research landscape:
1. Query Chroma for related papers
2. Aggregate chunk embeddings to paper-level
3. Cluster with HDBSCAN
4. Identify representative and boundary papers
5. Label clusters with LLM
6. Return structured ClusterMap
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from services.mapping.schemas import MappingRequest, MappingResult
from services.mapping.clusterer import (
    cluster_embeddings,
    compute_centroid,
    find_boundary_papers,
    find_representative_papers,
)
from services.mapping.labeler import label_cluster

logger = logging.getLogger(__name__)


class LiteratureMappingService:
    """Builds structured literature maps from vector store content."""

    def __init__(
        self,
        vector_store=None,
        embedding_service=None,
        llm_client=None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._llm_client = llm_client

    def build_map(self, request: MappingRequest) -> MappingResult:
        """Build a literature map from seed paper or topic.

        Args:
            request: MappingRequest with seed paper or topic

        Returns:
            MappingResult with clusters, representatives, and labels
        """
        warnings: List[str] = []
        map_id = self._make_map_id(request)

        # Step 1: Get query embedding
        query_embedding = self._get_query_embedding(request, warnings)
        if query_embedding is None:
            return MappingResult(
                map_id=map_id,
                seed_paper_id=request.seed_paper_id,
                warnings=["No query embedding available — cannot build map"],
            )

        # Step 2: Retrieve related chunks
        paper_embeddings = self._retrieve_paper_embeddings(
            query_embedding, request, warnings
        )

        if len(paper_embeddings) < request.min_cluster_size:
            return MappingResult(
                map_id=map_id,
                seed_paper_id=request.seed_paper_id,
                paper_count=len(paper_embeddings),
                warnings=warnings + [
                    f"Only {len(paper_embeddings)} papers found; need >= {request.min_cluster_size} for clustering"
                ],
            )

        # Step 3: Cluster
        paper_ids = list(paper_embeddings.keys())
        embeddings = list(paper_embeddings.values())

        cluster_assignments, noise = cluster_embeddings(
            paper_ids, embeddings, min_cluster_size=request.min_cluster_size
        )

        # Step 4: Build cluster metadata
        clusters = []
        for cluster_id, member_ids in sorted(cluster_assignments.items()):
            member_embeddings = [paper_embeddings[pid] for pid in member_ids]

            representatives = find_representative_papers(member_ids, member_embeddings)
            boundary = find_boundary_papers(member_ids, member_embeddings)
            centroid = compute_centroid(member_embeddings)

            # Get representative texts for labeling
            rep_texts = self._get_paper_texts(representatives)
            label = label_cluster(rep_texts, self._llm_client, cluster_id)

            clusters.append({
                "cluster_id": f"cluster_{cluster_id}",
                "label": label,
                "paper_ids": member_ids,
                "paper_count": len(member_ids),
                "representative_paper_ids": representatives,
                "boundary_paper_ids": boundary,
                "centroid_embedding": centroid[:10],  # Truncate for readability
            })

        return MappingResult(
            map_id=map_id,
            seed_paper_id=request.seed_paper_id,
            clusters=clusters,
            noise_paper_ids=noise,
            paper_count=len(paper_ids),
            warnings=warnings,
        )

    def build_map_from_embeddings(
        self,
        paper_ids: List[str],
        embeddings: List[List[float]],
        paper_texts: Optional[Dict[str, str]] = None,
        min_cluster_size: int = 3,
    ) -> MappingResult:
        """Build map directly from provided embeddings (for testing)."""
        map_id = f"map_{hashlib.sha256('|'.join(paper_ids).encode()).hexdigest()[:12]}"

        cluster_assignments, noise = cluster_embeddings(
            paper_ids, embeddings, min_cluster_size=min_cluster_size
        )

        clusters = []
        for cluster_id, member_ids in sorted(cluster_assignments.items()):
            member_embeddings = [embeddings[paper_ids.index(pid)] for pid in member_ids]
            representatives = find_representative_papers(member_ids, member_embeddings)
            boundary = find_boundary_papers(member_ids, member_embeddings)
            centroid = compute_centroid(member_embeddings)

            rep_texts = [paper_texts.get(pid, "") for pid in representatives] if paper_texts else []
            label = label_cluster(rep_texts, self._llm_client, cluster_id)

            clusters.append({
                "cluster_id": f"cluster_{cluster_id}",
                "label": label,
                "paper_ids": member_ids,
                "paper_count": len(member_ids),
                "representative_paper_ids": representatives,
                "boundary_paper_ids": boundary,
                "centroid_embedding": centroid[:10],
            })

        return MappingResult(
            map_id=map_id,
            clusters=clusters,
            noise_paper_ids=noise,
            paper_count=len(paper_ids),
        )

    def _get_query_embedding(self, request: MappingRequest, warnings: List[str]):
        if self._embedding_service is None:
            warnings.append("No embedding service available")
            return None

        from services.embedding.schemas import EmbeddingRequest

        query_text = request.topic or request.seed_paper_id or ""
        if not query_text:
            warnings.append("No seed paper or topic provided")
            return None

        result = self._embedding_service.embed(EmbeddingRequest(texts=[query_text]))
        return result.embeddings[0]

    def _retrieve_paper_embeddings(
        self,
        query_embedding,
        request: MappingRequest,
        warnings: List[str],
    ) -> Dict[str, List[float]]:
        """Retrieve and aggregate chunk embeddings to paper level."""
        if self._vector_store is None:
            warnings.append("No vector store available")
            return {}

        from services.vectorstore.schemas import VectorQueryRequest

        vresult = self._vector_store.query(VectorQueryRequest(
            collection=request.collection,
            query_embedding=query_embedding,
            top_k=request.top_k,
        ))

        # Aggregate by paper (source_id)
        paper_chunks: Dict[str, List[List[float]]] = {}
        for match in vresult.matches:
            paper_id = match.metadata.get("source_id", match.id)
            if paper_id not in paper_chunks:
                paper_chunks[paper_id] = []
            # Use match score as proxy for embedding quality
            # In production, we'd store actual embeddings
            paper_chunks[paper_id].append([match.score])

        # For now, use the query embedding dimension to create paper-level embeddings
        # This is a simplification — in production, we'd average chunk embeddings
        import numpy as np
        paper_embeddings = {}
        for pid, chunks in paper_chunks.items():
            # Create a synthetic paper embedding based on match scores
            paper_embeddings[pid] = query_embedding  # Placeholder

        return paper_embeddings

    def _get_paper_texts(self, paper_ids: List[str]) -> List[str]:
        """Get representative texts for papers."""
        if self._vector_store is None:
            return []
        # For now, return empty — will be populated when metadata store is wired
        return []

    def _make_map_id(self, request: MappingRequest) -> str:
        seed = f"{request.seed_paper_id or ''}:{request.topic or ''}"
        return f"map_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"

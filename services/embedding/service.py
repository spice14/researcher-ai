"""Embedding service wrapping sentence-transformers or Ollama embeddings.

Purpose:
- Generate dense vector embeddings from text
- Support sentence-transformers (local) or Ollama as backends
- Return 384-dim vectors (all-MiniLM-L6-v2) or model-dependent dims

Failure Modes:
- No model available -> fall back to hash-based pseudo-embeddings (testing only)
- Ollama unreachable -> try sentence-transformers, then fallback
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import List, Optional

from services.embedding.schemas import EmbeddingRequest, EmbeddingResult

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
FALLBACK_DIM = 384


class EmbeddingService:
    """Embedding service with sentence-transformers and Ollama backends."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
    ) -> None:
        self._model_name = model_name or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        self._ollama_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._st_model = None
        self._backend = "none"
        self._dimension = FALLBACK_DIM
        self._init_backend()

    def _init_backend(self) -> None:
        # Try sentence-transformers first
        try:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self._model_name)
            test_emb = self._st_model.encode(["test"])
            self._dimension = len(test_emb[0])
            self._backend = "sentence_transformers"
            logger.info(
                "Embedding backend: sentence-transformers (%s, dim=%d)",
                self._model_name,
                self._dimension,
            )
            return
        except Exception as exc:
            logger.info("sentence-transformers not available: %s", exc)

        # Try Ollama
        try:
            import json
            from urllib.request import urlopen, Request

            req = Request(f"{self._ollama_url}/api/embeddings", method="POST")
            req.add_header("Content-Type", "application/json")
            body = json.dumps({"model": self._model_name, "prompt": "test"}).encode()
            with urlopen(req, data=body, timeout=10) as resp:
                data = json.loads(resp.read())
                if "embedding" in data:
                    self._dimension = len(data["embedding"])
                    self._backend = "ollama"
                    logger.info(
                        "Embedding backend: ollama (%s, dim=%d)",
                        self._model_name,
                        self._dimension,
                    )
                    return
        except Exception as exc:
            logger.info("Ollama embeddings not available: %s", exc)

        # Fallback to hash-based pseudo-embeddings
        self._backend = "hash_fallback"
        self._dimension = FALLBACK_DIM
        logger.warning(
            "No embedding backend available, using hash-based fallback (dim=%d). "
            "Install sentence-transformers for production use.",
            FALLBACK_DIM,
        )

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        if not request.texts:
            raise ValueError("texts must not be empty")

        if self._backend == "sentence_transformers" and self._st_model is not None:
            embeddings = self._st_model.encode(request.texts).tolist()
        elif self._backend == "ollama":
            embeddings = self._ollama_embed(request.texts)
        else:
            embeddings = [self._hash_embed(text) for text in request.texts]

        return EmbeddingResult(
            embeddings=embeddings,
            model=self._model_name,
            dimension=self._dimension,
        )

    def _ollama_embed(self, texts: List[str]) -> List[List[float]]:
        import json
        from urllib.request import urlopen, Request

        embeddings = []
        for text in texts:
            req = Request(f"{self._ollama_url}/api/embeddings", method="POST")
            req.add_header("Content-Type", "application/json")
            body = json.dumps({"model": self._model_name, "prompt": text}).encode()
            with urlopen(req, data=body, timeout=30) as resp:
                data = json.loads(resp.read())
                embeddings.append(data["embedding"])
        return embeddings

    def _hash_embed(self, text: str) -> List[float]:
        """Deterministic hash-based pseudo-embedding for testing."""
        h = hashlib.sha256(text.encode()).digest()
        # Expand hash to fill dimension
        expanded = []
        for i in range(self._dimension):
            byte_val = h[i % len(h)]
            # Normalize to [-1, 1] range
            val = (byte_val / 127.5) - 1.0
            expanded.append(round(val, 6))
        # Normalize to unit vector
        norm = math.sqrt(sum(v * v for v in expanded))
        if norm > 0:
            expanded = [round(v / norm, 6) for v in expanded]
        return expanded

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def dimension(self) -> int:
        return self._dimension

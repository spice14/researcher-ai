"""Shared pytest fixtures and configuration."""

import sys
from pathlib import Path

# Add parent directory to path so we can import services and core
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def sample_text():
    """Sample research paper text for testing."""
    return """
    We evaluated our model on ImageNet-1K dataset.
    The accuracy achieved 0.92 with precision of 0.89 and recall of 0.87.
    Training time was 48 hours on 8 GPUs.
    We compared against BERT baseline which achieved 0.85 accuracy.
    The model outperformed the baseline by 7 percentage points.
    """


@pytest.fixture
def sample_claim_dict():
    """Sample raw claim dictionary for testing."""
    return {
        "sentence": "The model achieved 92% accuracy on ImageNet.",
        "claim_type": "performance",
        "entities": ["model", "ImageNet"],
        "metric_candidates": ["accuracy"],
        "numeric_values": [92.0],
        "context_id": "ctx_test_001",
    }


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def mock_context_result():
    """Mock ContextExtractionResult for testing."""
    from services.context.service import ContextExtractionResult
    from core.schemas.experimental_context import ContextRegistry

    registry = ContextRegistry(contexts=[])
    return ContextExtractionResult(registry=registry)


@pytest.fixture
def sample_ingestion_request():
    """Sample ingestion request for testing."""
    from services.ingestion.schemas import IngestionRequest

    return IngestionRequest(
        raw_text="Sample text with 0.95 accuracy on dataset.",
        source_id="test_source",
        chunk_size=256,
        chunk_overlap=32,
    )


@pytest.fixture
def sample_ingestion_chunks():
    """Sample ingestion chunks for testing."""
    from services.ingestion.schemas import IngestionChunk

    return [
        IngestionChunk(
            chunk_id="chunk_001",
            source_id="test_source",
            page=1,
            text="The model achieved 0.95 accuracy.",
            start_char=0,
            end_char=33,
            text_hash="abc123",
            context_id="ctx_001",
            numeric_strings=["0.95"],
            unit_strings=[],
            metric_names=["accuracy"],
        ),
        IngestionChunk(
            chunk_id="chunk_002",
            source_id="test_source",
            page=1,
            text="Training took 24 hours on GPU.",
            start_char=34,
            end_char=64,
            text_hash="def456",
            context_id="ctx_001",
            numeric_strings=["24"],
            unit_strings=["hours"],
            metric_names=[],
        ),
    ]


@pytest.fixture
def sample_normalized_claim():
    """Sample normalized claim for testing."""
    from services.normalization.schemas import NormalizedClaim

    return NormalizedClaim(
        claim_id="claim_001",
        context_id="ctx_001",
        subject="model",
        metric_canonical="accuracy",
        value_normalized=0.95,
        unit_normalized="ratio",
        polarity="supports",
        evidence_text="The model achieved 0.95 accuracy.",
        dataset="ImageNet",
        year=2024,
        determinism_hash="hash123",
    )


@pytest.fixture
def sample_claim():
    """Sample extracted claim for testing."""
    from core.schemas.claim import Claim, ClaimType

    return Claim(
        claim_id="claim_001",
        claim_type=ClaimType.PERFORMANCE,
        sentence="The model achieved 0.95 accuracy.",
        subject="model",
        predicate="achieved",
        metric_candidate="accuracy",
        numeric_value=0.95,
        context_id="ctx_001",
        ground_truth=None,
    )

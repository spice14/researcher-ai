"""Phase 1 schema coverage for newly added core contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from core.schemas import (
    ArtifactType,
    Chunk,
    ChunkType,
    ClaimEvidence,
    ClusterMap,
    ClusterProvenance,
    ContradictionPair,
    ContradictionReport,
    Critique,
    CritiqueSeverity,
    ExtractionResult,
    LiteratureCluster,
    MetricDefinition,
    EvaluationProtocol,
    ExperimentalContext,
    NormalizedClaim,
    Paper,
    Polarity,
    Proposal,
    Session,
    TaskType,
)
from core.schemas.claim import ClaimSubtype
from core.schemas.evidence import EvidenceProvenance
from core.schemas.hypothesis import Hypothesis


def test_phase1_paper_schema_creation() -> None:
    paper = Paper(
        paper_id="paper_001",
        title="Structured Research Systems",
        authors=["Ada Lovelace", "Grace Hopper"],
        abstract="A paper about rigorous research infrastructure.",
        arxiv_id="2603.00001",
        pdf_path="papers/structured.pdf",
        ingestion_timestamp=datetime.now(UTC),
        chunk_ids=["chunk_001", "chunk_002"],
    )

    assert paper.paper_id == "paper_001"
    assert len(paper.chunk_ids) == 2


def test_phase1_chunk_schema_creation() -> None:
    chunk = Chunk(
        chunk_id="chunk_001",
        paper_id="paper_001",
        text="This sentence contains a measurable finding.",
        page_number=3,
        embedding_id="embed_001",
        chunk_type=ChunkType.SENTENCE,
    )

    assert chunk.chunk_type == ChunkType.SENTENCE


def test_phase1_claim_compatibility_fields() -> None:
    evidence = ClaimEvidence(source_id="arxiv:1", page=2, snippet="Improves F1 by 3 points.", retrieval_score=0.9)
    hypothesis = Hypothesis(
        hypothesis_id="hyp_compat",
        statement="Structured critique improves research quality.",
        rationale="Because adversarial loops surface hidden assumptions.",
        assumptions=["Evidence is diverse"],
        independent_variables=["Critique loop"],
        dependent_variables=["Proposal quality"],
        novelty_basis="Few systems preserve structured critique provenance.",
        supporting_citations=["paper_001"],
        known_risks=["Sparse evidence in new domains"],
        confidence_score=0.72,
        grounding_claim_ids=["claim_001"],
        iteration_number=2,
        qualitative_confidence="medium",
    )

    assert hypothesis.rationale is not None
    assert hypothesis.iteration_number == 2
    assert hypothesis.grounding_claim_ids == ["claim_001"]
    assert evidence.source_id == "arxiv:1"


def test_phase1_normalized_claim_compatibility_fields() -> None:
    normalized = NormalizedClaim(
        claim_id="claim_001",
        normalized_claim_id="norm_001",
        canonical_text="Model A improves F1 on Dataset X.",
        source_claim_ids=["claim_001", "claim_002"],
        domain="nlp",
        metric="f1",
        conditions={"dataset": "Dataset X"},
        evidence_strength=0.8,
        subject="Model A",
        predicate="improves",
        object_raw="F1 by 3 points",
        metric_canonical="f1",
        value_raw="3",
        value_normalized=3.0,
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.DELTA,
    )

    assert normalized.normalized_claim_id == "norm_001"
    assert normalized.source_claim_ids[0] == "claim_001"


def test_phase1_cluster_map_schema_creation() -> None:
    cluster_map = ClusterMap(
        map_id="map_001",
        seed_paper_id="paper_001",
        clusters=[
            LiteratureCluster(
                cluster_id="cluster_001",
                label="Benchmarking and evaluation",
                representative_paper_ids=["paper_001"],
                boundary_paper_ids=["paper_002"],
                centroid_embedding=[0.1, 0.2, 0.3],
            )
        ],
        provenance=[
            ClusterProvenance(
                paper_id="paper_001",
                chunk_id="chunk_001",
                snippet="These works focus on evaluation methodology.",
            )
        ],
    )

    assert cluster_map.clusters[0].label == "Benchmarking and evaluation"


def test_phase1_contradiction_report_schema_creation() -> None:
    evidence_a = ClaimEvidence(source_id="paper_001", page=4, snippet="Model A reaches 91 F1.", retrieval_score=0.88)
    evidence_b = ClaimEvidence(source_id="paper_002", page=7, snippet="Model A reaches 84 F1.", retrieval_score=0.91)
    report = ContradictionReport(
        report_id="report_001",
        claim_cluster_id="norm_001",
        consensus_claims=["claim_003"],
        contradiction_pairs=[
            ContradictionPair(
                claim_a="claim_001",
                claim_b="claim_002",
                evidence_a=[evidence_a],
                evidence_b=[evidence_b],
            )
        ],
        uncertainty_markers=["Insufficient replication across domains"],
    )

    assert report.contradiction_pairs[0].claim_a == "claim_001"


def test_phase1_critique_schema_creation() -> None:
    critique = Critique(
        critique_id="crit_001",
        hypothesis_id="hyp_001",
        counter_evidence=[
            ClaimEvidence(source_id="paper_003", page=5, snippet="The effect disappears out of domain.", retrieval_score=0.77)
        ],
        weak_assumptions=["Assumes training and deployment distributions match"],
        suggested_revisions=["Constrain the hypothesis to in-domain settings"],
        severity=CritiqueSeverity.HIGH,
    )

    assert critique.severity == CritiqueSeverity.HIGH


def test_phase1_proposal_schema_creation() -> None:
    proposal = Proposal(
        proposal_id="proposal_001",
        hypothesis_id="hyp_001",
        novelty_statement="This proposal targets a gap in structured critique-aware tooling.",
        motivation="Researchers need auditable support for literature-grounded iteration.",
        methodology_outline="Build deterministic services, then add bounded agent critique loops.",
        expected_outcomes="Higher-quality, evidence-grounded research hypotheses.",
        references=["paper_001", "paper_002"],
    )

    assert len(proposal.references) == 2


def test_phase1_extraction_result_schema_creation() -> None:
    provenance = EvidenceProvenance(page=6, extraction_model_version="v1.0")
    result = ExtractionResult(
        result_id="extract_001",
        paper_id="paper_001",
        page_number=6,
        artifact_type=ArtifactType.TABLE,
        raw_content={"rows": [["Model A", "91.2"]]},
        normalized_data={"metric": "f1", "value": 91.2},
        caption="Table 1: Main results.",
        provenance=provenance,
    )

    assert result.artifact_type == ArtifactType.TABLE


def test_phase1_session_schema_creation() -> None:
    created_at = datetime.now(UTC)
    session = Session(
        session_id="session_001",
        user_input="Compare the literature on structured critique systems.",
        active_paper_ids=["paper_001", "paper_002"],
        hypothesis_ids=["hyp_001"],
        phase="mapping",
        created_at=created_at,
        updated_at=created_at + timedelta(minutes=5),
    )

    assert session.phase == "mapping"


def test_phase1_experimental_context_schema_creation() -> None:
    context = ExperimentalContext(
        context_id="ctx_001",
        task=TaskType.CLASSIFICATION,
        dataset="ResearchBench",
        metric=MetricDefinition(name="accuracy", unit="%", higher_is_better=True),
        evaluation_protocol=EvaluationProtocol(split_type="train/test"),
    )

    assert context.get_identity_key().startswith("classification")


def test_phase1_session_temporal_order_rejected() -> None:
    created_at = datetime.now(UTC)
    with pytest.raises(ValueError):
        Session(
            session_id="session_bad",
            user_input="Bad timing",
            phase="ingestion",
            created_at=created_at,
            updated_at=created_at - timedelta(seconds=1),
        )
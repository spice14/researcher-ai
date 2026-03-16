"""Phase 1 validator coverage for newly added core contracts."""

from datetime import UTC, datetime

from core.schemas import (
    ArtifactType,
    Chunk,
    ChunkType,
    ClaimEvidence,
    ClusterMap,
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
from core.validators import (
    ChunkValidator,
    ClusterMapValidator,
    ContradictionReportValidator,
    CritiqueValidator,
    ExperimentalContextValidator,
    ExtractionResultValidator,
    NormalizedClaimValidator,
    PaperValidator,
    ProposalValidator,
    SessionValidator,
)


def test_phase1_paper_validator_flags_duplicate_chunk_ids() -> None:
    paper = Paper(
        paper_id="paper_001",
        title="A title",
        authors=["Ada"],
        pdf_path="paper.pdf",
        ingestion_timestamp=datetime.now(UTC),
        chunk_ids=["chunk_001", "chunk_001"],
    )

    result = PaperValidator.validate(paper)
    assert not result.is_valid


def test_phase1_chunk_validator_warns_on_short_text() -> None:
    chunk = Chunk(
        chunk_id="chunk_001",
        paper_id="paper_001",
        text="short",
        page_number=1,
        embedding_id="embed_001",
        chunk_type=ChunkType.SENTENCE,
    )

    result = ChunkValidator.validate(chunk)
    assert result.is_valid
    assert result.has_warnings()


def test_phase1_experimental_context_validator_rejects_inverted_metric_range() -> None:
    context = ExperimentalContext(
        context_id="ctx_001",
        task=TaskType.CLASSIFICATION,
        dataset="EvalSet",
        metric=MetricDefinition(name="accuracy", higher_is_better=True, range_min=1.0, range_max=0.0),
        evaluation_protocol=EvaluationProtocol(split_type="train/test"),
    )

    result = ExperimentalContextValidator.validate(context)
    assert not result.is_valid


def test_phase1_normalized_claim_validator_warns_on_metric_alias_mismatch() -> None:
    normalized = NormalizedClaim(
        claim_id="claim_001",
        normalized_claim_id="norm_001",
        source_claim_ids=["claim_002"],
        subject="Model A",
        predicate="improves",
        object_raw="BLEU by 2 points",
        metric="accuracy",
        metric_canonical="bleu",
        value_raw="2",
        value_normalized=2.0,
        polarity=Polarity.SUPPORTS,
        claim_subtype=ClaimSubtype.DELTA,
    )

    result = NormalizedClaimValidator.validate(normalized)
    assert result.is_valid
    assert result.has_warnings()


def test_phase1_cluster_map_validator_rejects_missing_clusters() -> None:
    cluster_map = ClusterMap(map_id="map_001", clusters=[])

    result = ClusterMapValidator.validate(cluster_map)
    assert not result.is_valid


def test_phase1_contradiction_report_validator_rejects_empty_report() -> None:
    report = ContradictionReport(report_id="report_001", claim_cluster_id="norm_001")

    result = ContradictionReportValidator.validate(report)
    assert not result.is_valid


def test_phase1_critique_validator_rejects_empty_substance() -> None:
    critique = Critique(
        critique_id="crit_001",
        hypothesis_id="hyp_001",
        severity=CritiqueSeverity.LOW,
    )

    result = CritiqueValidator.validate(critique)
    assert not result.is_valid


def test_phase1_proposal_validator_warns_without_references() -> None:
    proposal = Proposal(
        proposal_id="proposal_001",
        hypothesis_id="hyp_001",
        novelty_statement="Novelty",
        motivation="Motivation",
        methodology_outline="Method",
        expected_outcomes="Outcome",
    )

    result = ProposalValidator.validate(proposal)
    assert result.is_valid
    assert result.has_warnings()


def test_phase1_extraction_result_validator_warns_on_page_mismatch() -> None:
    result_model = ExtractionResult(
        result_id="extract_001",
        paper_id="paper_001",
        page_number=2,
        artifact_type=ArtifactType.FIGURE,
        raw_content={"kind": "plot"},
        provenance=EvidenceProvenance(page=3, extraction_model_version="v1"),
    )

    result = ExtractionResultValidator.validate(result_model)
    assert result.is_valid
    assert result.has_warnings()


def test_phase1_session_validator_warns_on_duplicate_active_papers() -> None:
    session = Session(
        session_id="session_001",
        user_input="Inspect papers",
        active_paper_ids=["paper_001", "paper_001"],
        hypothesis_ids=["hyp_001", "hyp_001"],
        phase="mapping",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    result = SessionValidator.validate(session)
    assert result.is_valid
    assert result.has_warnings()


def test_phase1_contradiction_pair_rejects_self_comparison() -> None:
    evidence = ClaimEvidence(source_id="paper_001", page=1, snippet="Snippet", retrieval_score=0.9)

    try:
        ContradictionPair(
            claim_a="claim_001",
            claim_b="claim_001",
            evidence_a=[evidence],
            evidence_b=[evidence],
        )
        assert False, "Expected self-comparison to be rejected"
    except ValueError:
        assert True


def test_phase1_cluster_map_validator_rejects_cluster_without_representative() -> None:
    cluster_map = ClusterMap(
        map_id="map_001",
        clusters=[
            LiteratureCluster(
                cluster_id="cluster_001",
                label="Label",
                representative_paper_ids=[],
                boundary_paper_ids=["paper_002"],
                centroid_embedding=[0.1, 0.2],
            )
        ],
    )

    result = ClusterMapValidator.validate(cluster_map)
    assert not result.is_valid
"""Additional tests for core schemas to improve coverage."""

import pytest
from core.schemas.claim import Claim, ClaimEvidence, ClaimConditions, ClaimType, ClaimSubtype, Polarity, ConfidenceLevel
from core.schemas.hypothesis import Hypothesis, HypothesisRevision
from core.schemas.experimental_context import ExperimentalContext, TaskType
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance


class TestClaimSchemaCreation:
    """Test Claim schema with various valid configurations."""

    def test_create_claim_with_all_fields(self):
        """Test creating a Claim with all fields specified."""
        evidence = ClaimEvidence(
            source_id="arxiv:2020.12345",
            page=5,
            snippet="The model achieved 95% accuracy.",
            retrieval_score=0.95,
        )
        claim = Claim(
            claim_id="c1",
            subject="BERT",
            predicate="achieves",
            object="95% accuracy",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        assert claim.claim_id == "c1"
        assert claim.subject == "BERT"
        assert len(claim.evidence) == 1

    def test_claim_polarity_enum_values(self):
        """Test all Polarity enum values."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        for polarity in [Polarity.SUPPORTS, Polarity.REFUTES, Polarity.NEUTRAL]:
            claim = Claim(
                claim_id="c1",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                polarity=polarity,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            assert claim.polarity == polarity

    def test_claim_confidence_level_values(self):
        """Test all ConfidenceLevel enum values."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        for conf_level in [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]:
            claim = Claim(
                claim_id="c1",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                polarity=Polarity.SUPPORTS,
                confidence_level=conf_level,
            )
            assert claim.confidence_level == conf_level

    def test_claim_type_enum_values(self):
        """Test all ClaimType enum values."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        for claim_type in [ClaimType.PERFORMANCE, ClaimType.EFFICIENCY, ClaimType.STRUCTURAL]:
            claim = Claim(
                claim_id="c1",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                claim_type=claim_type,
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            assert claim.claim_type == claim_type

    def test_claim_subtype_enum_values(self):
        """Test ClaimSubtype enum values."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        for subtype in [ClaimSubtype.ABSOLUTE, ClaimSubtype.DELTA]:
            claim = Claim(
                claim_id="c1",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                claim_subtype=subtype,
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            assert claim.claim_subtype == subtype

    def test_claim_with_context_id(self):
        """Test Claim with explicit context_id."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            context_id="ctx_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        assert claim.context_id == "ctx_001"

    def test_claim_with_conditions(self):
        """Test Claim with explicit conditions."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        conditions = ClaimConditions(
            dataset="ImageNet",
            domain="Computer Vision",
            constraints=["RGB images only"],
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            conditions=conditions,
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        assert claim.conditions.dataset == "ImageNet"

    def test_claim_to_statement(self):
        """Test Claim.to_statement() method."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="BERT",
            predicate="outperforms",
            object="GPT",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        statement = claim.to_statement()
        assert "BERT" in statement
        assert "outperforms" in statement
        assert "GPT" in statement

    def test_claim_multiple_evidence(self):
        """Test Claim with multiple evidence sources."""
        evidence1 = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test 1",
            retrieval_score=0.8,
        )
        evidence2 = ClaimEvidence(
            source_id="src2",
            page=2,
            snippet="test 2",
            retrieval_score=0.9,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence1, evidence2],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        assert len(claim.evidence) == 2


class TestHypothesisSchemaCreation:
    """Test Hypothesis schema creation."""

    def test_create_hypothesis_basic(self):
        """Test creating a basic Hypothesis."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Model A outperforms Model B",
            assumptions=["Both models trained on same data"],
            independent_variables=["Model type"],
            dependent_variables=["Accuracy"],
            novelty_basis="First direct comparison",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        assert hypothesis.hypothesis_id == "h1"
        assert hypothesis.statement == "Model A outperforms Model B"

    def test_hypothesis_with_boundary_conditions(self):
        """Test Hypothesis with boundary conditions."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            boundary_conditions=["On ImageNet only", "For RGB images"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.HIGH,
        )
        assert len(hypothesis.boundary_conditions) == 2

    def test_hypothesis_add_revision(self):
        """Test adding revisions to a Hypothesis."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        hypothesis.add_revision("Changed scope", "Based on new findings")
        assert len(hypothesis.revision_history) == 1
        assert hypothesis.revision_history[0].iteration == 1

    def test_hypothesis_get_evidence_balance(self):
        """Test calculating evidence balance."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        balance = hypothesis.get_evidence_balance()
        assert balance["supporting_count"] == 0
        assert balance["contradicting_count"] == 0
        assert balance["total_evidence"] == 0


class TestExperimentalContextSchemaCreation:
    """Test ExperimentalContext schema creation."""

    def test_create_experimental_context_basic(self):
        """Test creating a basic ExperimentalContext."""
        from core.schemas.experimental_context import EvaluationProtocol as ProtocolModel, MetricDefinition
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = ProtocolModel(split_type="train/test")
        context = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        assert context.context_id == "ctx1"
        assert context.task == TaskType.CLASSIFICATION

    def test_context_task_types(self):
        """Test all TaskType enum values."""
        from core.schemas.experimental_context import EvaluationProtocol as ProtocolModel, MetricDefinition
        metric = MetricDefinition(name="test", higher_is_better=True)
        protocol = ProtocolModel(split_type="train/test")
        task_types = [
            TaskType.CLASSIFICATION,
            TaskType.REGRESSION,
            TaskType.SEQUENCE_LABELING,
            TaskType.TRANSLATION,
            TaskType.GENERATION,
            TaskType.QUESTION_ANSWERING,
            TaskType.SUMMARIZATION,
            TaskType.OTHER,
        ]
        for task_type in task_types:
            context = ExperimentalContext(
                context_id="ctx1",
                task=task_type,
                dataset="test",
                metric=metric,
                evaluation_protocol=protocol,
            )
            assert context.task == task_type

    def test_context_evaluation_protocols(self):
        """Test EvaluationProtocol creation."""
        from core.schemas.experimental_context import EvaluationProtocol as ProtocolModel, MetricDefinition
        metric = MetricDefinition(name="test", higher_is_better=True)
        protocol = ProtocolModel(split_type="k-fold", cross_validation_folds=5)
        context = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="test",
            metric=metric,
            evaluation_protocol=protocol,
        )
        assert context.evaluation_protocol.split_type == "k-fold"

    def test_context_with_all_optional_fields(self):
        """Test ExperimentalContext with all optional fields."""
        from core.schemas.experimental_context import EvaluationProtocol as ProtocolModel, MetricDefinition
        metric = MetricDefinition(
            name="accuracy",
            unit="%",
            higher_is_better=True,
            range_min=0.0,
            range_max=100.0,
        )
        protocol = ProtocolModel(
            split_type="train/test",
            test_set_size=1000,
            random_seed=42,
            evaluation_runs=3,
        )
        context = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
            model_class="transformer",
            training_regime="supervised",
            domain="Computer Vision",
            additional_constraints={"gpus": 8, "batch_size": 128},
        )
        assert context.model_class == "transformer"
        assert context.training_regime == "supervised"


class TestEvidenceRecordSchemaCreation:
    """Test EvidenceRecord schema creation."""

    def test_create_evidence_record_text(self):
        """Test creating a text EvidenceRecord."""
        provenance = EvidenceProvenance(
            page=1,
            extraction_model_version="v1.0",
        )
        context = EvidenceContext(caption="Figure 1")
        record = EvidenceRecord(
            evidence_id="ev1",
            source_id="paper1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        assert record.evidence_id == "ev1"
        assert record.type == EvidenceType.TEXT

    def test_evidence_types(self):
        """Test all EvidenceType enum values."""
        for ev_type in [EvidenceType.TEXT, EvidenceType.TABLE, EvidenceType.FIGURE]:
            provenance = EvidenceProvenance(page=1, extraction_model_version="v1")
            context = EvidenceContext()
            record = EvidenceRecord(
                evidence_id="ev1",
                source_id="src1",
                type=ev_type,
                extracted_data={},
                context=context,
                provenance=provenance,
            )
            assert record.type == ev_type

    def test_evidence_context_with_all_fields(self):
        """Test EvidenceContext with all fields."""
        context = EvidenceContext(
            caption="Figure 1: Results",
            method_reference="Section 4.1",
            metric_name="accuracy",
            units="percent",
        )
        assert context.caption == "Figure 1: Results"
        assert context.metric_name == "accuracy"

    def test_evidence_provenance_with_bounding_box(self):
        """Test EvidenceProvenance with bounding box."""
        provenance = EvidenceProvenance(
            page=5,
            extraction_model_version="v2.1",
            bounding_box={"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.3},
        )
        assert provenance.page == 5
        assert provenance.bounding_box is not None
        assert "x" in provenance.bounding_box

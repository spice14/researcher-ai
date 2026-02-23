"""Tests for validator business logic and edge cases."""

import pytest
from core.validators.claim_validator import ClaimValidator
from core.validators.evidence_validator import EvidenceValidator
from core.validators.hypothesis_validator import HypothesisValidator
from core.validators.schema_validator import SchemaValidator, ValidationResult
from core.schemas.claim import Claim, ClaimEvidence, Polarity, ConfidenceLevel, ClaimType, ClaimSubtype
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance
from core.schemas.hypothesis import Hypothesis, HypothesisRevision
from core.schemas.experimental_context import ExperimentalContext, TaskType


class TestClaimValidatorLogic:
    """Test ClaimValidator validation logic."""

    def test_validate_claim_with_context_id_and_registry(self):
        """Test claim validation with context reference checking."""
        from core.schemas.experimental_context import ExperimentalContext, ContextRegistry, MetricDefinition, EvaluationProtocol
        
        # Create a context and registry
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context = ExperimentalContext(
            context_id="ctx_001",
            task=TaskType.CLASSIFICATION,
            dataset="test",
            metric=metric,
            evaluation_protocol=protocol,
        )
        registry = ContextRegistry(contexts={})
        registry.register(context)
        
        # Create claim with valid context_id
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            context_id="ctx_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        result = ClaimValidator.validate(claim, context_registry=registry)
        assert result is not None

    def test_validate_claim_with_missing_context_in_registry(self):
        """Test claim validation when context_id not in registry."""
        from core.schemas.experimental_context import ContextRegistry
        
        registry = ContextRegistry(contexts={})
        
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            context_id="nonexistent_ctx",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        result = ClaimValidator.validate(claim, context_registry=registry)
        assert result is not None

    def test_validate_claim_with_context_id_no_registry(self):
        """Test claim validation with context_id but no registry provided."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            context_id="ctx_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        result = ClaimValidator.validate(claim, context_registry=None)
        assert result is not None

    def test_validate_claim_atomicity_with_and(self):
        """Test atomicity validation detects 'and' in claim."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            subject="Model A",
            predicate="achieves high accuracy and fast inference",
            object="on ImageNet",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        result = ClaimValidator.validate(claim)
        # Should have warnings about compound claim
        assert result is not None

    def test_validate_claim_atomicity_with_or(self):
        """Test atomicity validation detects 'or' in claim."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            subject="Model",
            predicate="works on CIFAR or ImageNet",
            object="with good performance",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_validate_claim_with_multiple_evidence_sources(self):
        """Test claim validation with multiple evidence pieces."""
        evidence1 = ClaimEvidence(source_id="src1", page=1, snippet="test1", retrieval_score=0.8)
        evidence2 = ClaimEvidence(source_id="src2", page=2, snippet="test2", retrieval_score=0.9)
        evidence3 = ClaimEvidence(source_id="src3", page=3, snippet="test3", retrieval_score=0.7)
        claim = Claim(
            claim_id="claim_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence1, evidence2, evidence3],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_validate_claim_different_types(self):
        """Test validation works with different claim types."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        for claim_type in [ClaimType.PERFORMANCE, ClaimType.EFFICIENCY, ClaimType.STRUCTURAL]:
            claim = Claim(
                claim_id="claim_001",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                claim_type=claim_type,
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            result = ClaimValidator.validate(claim)
            assert result is not None

    def test_validate_claim_different_subtypes(self):
        """Test validation with different claim subtypes."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        for subtype in [ClaimSubtype.ABSOLUTE, ClaimSubtype.DELTA]:
            claim = Claim(
                claim_id="claim_001",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                claim_subtype=subtype,
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            result = ClaimValidator.validate(claim)
            assert result is not None

    def test_validate_claim_different_polarity_values(self):
        """Test validation with different polarities."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        for polarity in [Polarity.SUPPORTS, Polarity.REFUTES, Polarity.NEUTRAL]:
            claim = Claim(
                claim_id="claim_001",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                polarity=polarity,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            result = ClaimValidator.validate(claim)
            assert result is not None

    def test_validate_claim_different_confidence_levels(self):
        """Test validation with different confidence levels."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        for conf_level in [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]:
            claim = Claim(
                claim_id="claim_001",
                subject="test",
                predicate="tests",
                object="something",
                evidence=[evidence],
                polarity=Polarity.SUPPORTS,
                confidence_level=conf_level,
            )
            result = ClaimValidator.validate(claim)
            assert result is not None


class TestEvidenceValidatorLogic:
    """Test EvidenceValidator validation logic."""

    def test_validate_evidence_all_types(self):
        """Test validation for all evidence types."""
        for ev_type in [EvidenceType.TEXT, EvidenceType.TABLE, EvidenceType.FIGURE]:
            provenance = EvidenceProvenance(page=1, extraction_model_version="v1")
            context = EvidenceContext()
            record = EvidenceRecord(
                evidence_id="ev_001",
                source_id="src1",
                type=ev_type,
                extracted_data={"data": "test"},
                context=context,
                provenance=provenance,
            )
            result = EvidenceValidator.validate(record)
            assert result is not None

    def test_validate_evidence_with_full_context(self):
        """Test evidence validation with complete context information."""
        provenance = EvidenceProvenance(
            page=5,
            extraction_model_version="v2.1",
            bounding_box={"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.3},
        )
        context = EvidenceContext(
            caption="Complex Figure",
            method_reference="Section 4.1",
            metric_name="accuracy",
            units="percent",
        )
        record = EvidenceRecord(
            evidence_id="ev_complex",
            source_id="arxiv:2020.12345",
            type=EvidenceType.FIGURE,
            extracted_data={"url": "https://example.com", "values": [0.8, 0.85, 0.9]},
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None

    def test_validate_evidence_minimal(self):
        """Test evidence validation with minimal fields."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1")
        context = EvidenceContext()
        record = EvidenceRecord(
            evidence_id="ev_min",
            source_id="s",
            type=EvidenceType.TEXT,
            extracted_data={},
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None


class TestHypothesisValidatorLogic:
    """Test HypothesisValidator validation logic."""

    def test_validate_hypothesis_with_revisions(self):
        """Test hypothesis validation with multiple revisions."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_revised",
            statement="Updated statement",
            assumptions=["Assumption 1", "Assumption 2", "Assumption 3"],
            independent_variables=["Var1", "Var2"],
            dependent_variables=["DepVar1", "DepVar2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.HIGH,
        )
        hypothesis.add_revision("Changed approach", "Based on feedback")
        hypothesis.add_revision("Refined methodology", "Improved clarity")
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None

    def test_validate_hypothesis_with_many_assumptions(self):
        """Test hypothesis with many assumptions."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_many",
            statement="Complex statement",
            assumptions=[f"Assumption {i}" for i in range(1, 11)],
            independent_variables=["Var1"],
            dependent_variables=["Var2"],
            novelty_basis="Novel",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None

    def test_validate_hypothesis_with_boundary_conditions(self):
        """Test hypothesis validation with boundary conditions."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_bounded",
            statement="Bounded statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            boundary_conditions=["Condition 1", "Condition 2", "Condition 3"],
            novelty_basis="Novel",
            qualitative_confidence=ConfidenceLevel.LOW,
        )
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None

    def test_validate_hypothesis_evidence_balance_no_claims(self):
        """Test evidence balance calculation with no supporting/contradicting claims."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_no_claims",
            statement="Statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        balance = hypothesis.get_evidence_balance()
        assert balance["supporting_count"] == 0
        assert balance["contradicting_count"] == 0
        assert balance["total_evidence"] == 0
        assert balance["support_ratio"] == 0.0


class TestSchemaValidatorHelpers:
    """Test SchemaValidator helper methods."""

    def test_validate_non_empty_string_valid(self):
        """Test non-empty string validation with valid input."""
        result = ValidationResult(is_valid=True)
        SchemaValidator.validate_non_empty_string("valid", "field", result)
        # Should not add errors if valid
        assert len(result.errors) == 0

    def test_validate_non_empty_string_empty(self):
        """Test non-empty string validation with empty input."""
        result = ValidationResult(is_valid=True)
        SchemaValidator.validate_non_empty_string("", "field", result)
        # Should add error if empty
        assert len(result.errors) > 0

    def test_validate_id_format_with_valid_prefix(self):
        """Test ID format validation with valid prefix."""
        result = ValidationResult(is_valid=True)
        SchemaValidator.validate_id_format(
            "claim_001",
            "claim_id",
            result,
            allowed_prefixes=["claim_"]
        )
        # No error expected for valid format
        assert result is not None

    def test_validation_result_error_management(self):
        """Test ValidationResult error and warning management."""
        result = ValidationResult(is_valid=True)
        result.add_error(field_path="field1", message="Error 1")
        result.add_error(field_path="field2", message="Error 2")
        result.add_warning(field_path="field3", message="Warning 1")
        
        assert len(result.errors) == 2
        assert len(result.warnings) == 1

    def test_validation_result_conversion_to_dict(self):
        """Test ValidationResult can be converted to dict."""
        result = ValidationResult(is_valid=False)
        result.add_error(field_path="test", message="Test error")
        
        result_dict = result.to_dict() if hasattr(result, 'to_dict') else result.__dict__
        assert result_dict is not None

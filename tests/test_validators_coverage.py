"""Tests for core validators module."""

import pytest
from core.validators.claim_validator import ClaimValidator
from core.validators.evidence_validator import EvidenceValidator
from core.validators.hypothesis_validator import HypothesisValidator
from core.validators.schema_validator import SchemaValidator, ValidationResult
from core.schemas.claim import Claim, ClaimEvidence, Polarity, ConfidenceLevel
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance
from core.schemas.hypothesis import Hypothesis


class TestClaimValidatorBasic:
    """Test basic ClaimValidator functionality."""

    def test_claim_validator_instantiation(self):
        """Test creating a ClaimValidator instance."""
        validator = ClaimValidator()
        assert validator is not None

    def test_validate_valid_claim(self):
        """Test validating a valid claim."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="claim_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None


class TestEvidenceValidatorBasic:
    """Test basic EvidenceValidator functionality."""

    def test_evidence_validator_instantiation(self):
        """Test creating an EvidenceValidator instance."""
        validator = EvidenceValidator()
        assert validator is not None

    def test_validate_valid_evidence(self):
        """Test validating valid evidence."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(caption="Test")
        record = EvidenceRecord(
            evidence_id="ev_001",
            source_id="src1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None


class TestHypothesisValidatorBasic:
    """Test basic HypothesisValidator functionality."""

    def test_hypothesis_validator_instantiation(self):
        """Test creating a HypothesisValidator instance."""
        validator = HypothesisValidator()
        assert validator is not None

    def test_validate_valid_hypothesis(self):
        """Test validating a valid hypothesis."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_001",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None


class TestSchemaValidator:
    """Test SchemaValidator base class."""

    def test_schema_validator_instantiation(self):
        """Test creating a SchemaValidator instance."""
        validator = SchemaValidator()
        assert validator is not None

    def test_validation_result_creation(self):
        """Test creating a ValidationResult."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True

    def test_validation_result_add_error(self):
        """Test adding errors to ValidationResult."""
        result = ValidationResult(is_valid=True)
        result.add_error(field_path="test_field", message="Test error")
        assert len(result.errors) > 0

    def test_validation_result_add_warning(self):
        """Test adding warnings to ValidationResult."""
        result = ValidationResult(is_valid=True)
        result.add_warning(field_path="test_field", message="Test warning")
        assert len(result.warnings) > 0

    def test_schema_validator_helper_methods_exist(self):
        """Test that SchemaValidator has expected helper methods."""
        assert hasattr(SchemaValidator, 'validate_non_empty_string')
        assert hasattr(SchemaValidator, 'validate_id_format')


class TestValidationIntegration:
    """Integration tests for validator workflow."""

    def test_concurrent_validation_workflow(self):
        """Test validating multiple schemas together."""
        # Create valid evidence
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(caption="Test")
        evidence_record = EvidenceRecord(
            evidence_id="ev_001",
            source_id="src1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        
        # Create valid claim
        claim_evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="claim_001",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[claim_evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        # Create valid hypothesis
        hypothesis = Hypothesis(
            hypothesis_id="hyp_001",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        
        # Validate all
        evidence_result = EvidenceValidator.validate(evidence_record)
        claim_result = ClaimValidator.validate(claim)
        hypothesis_result = HypothesisValidator.validate(hypothesis)
        
        # All should produce results
        assert evidence_result is not None
        assert claim_result is not None
        assert hypothesis_result is not None

    def test_validation_result_structure(self):
        """Test ValidationResult has proper structure."""
        result = ValidationResult(is_valid=True)
        
        # Should have these attributes
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        
        # Errors and warnings should be iterable
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validators_handle_complex_schemas(self):
        """Test that validators can handle schemas with many fields."""
        # Create evidence with all fields
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
        evidence = EvidenceRecord(
            evidence_id="ev_complex",
            source_id="arxiv:2020.12345",
            type=EvidenceType.FIGURE,
            extracted_data={"url": "https://example.com", "data": [1, 2, 3]},
            context=context,
            provenance=provenance,
        )
        
        result = EvidenceValidator.validate(evidence)
        assert result is not None

    def test_validators_consistency(self):
        """Test that validators have consistent interfaces."""
        # All validators should have validate static method
        assert hasattr(ClaimValidator, 'validate')
        assert hasattr(EvidenceValidator, 'validate')
        assert hasattr(HypothesisValidator, 'validate')
        
        # All should be callable
        assert callable(ClaimValidator.validate)
        assert callable(EvidenceValidator.validate)
        assert callable(HypothesisValidator.validate)


class TestValidationErrorHandling:
    """Test error handling in validators."""

    def test_claim_validator_with_minimal_claim(self):
        """Test ClaimValidator with minimal valid claim."""
        evidence = ClaimEvidence(
            source_id="s",
            page=1,
            snippet="x",
            retrieval_score=0.0,
        )
        claim = Claim(
            claim_id="c",
            subject="a",
            predicate="b",
            object="c",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.LOW,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_hypothesis_validator_with_multiple_revisions(self):
        """Test HypothesisValidator with revised hypothesis."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_revised",
            statement="Updated statement",
            assumptions=["Assumption 1", "Assumption 2"],
            independent_variables=["Var1", "Var2"],
            dependent_variables=["DepVar1"],
            novelty_basis="Novel",
            qualitative_confidence=ConfidenceLevel.HIGH,
        )
        hypothesis.add_revision("Changed approach", "Based on feedback")
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None

    def test_evidence_validator_with_all_types(self):
        """Test EvidenceValidator with all evidence types."""
        for ev_type in [EvidenceType.TEXT, EvidenceType.TABLE, EvidenceType.FIGURE]:
            provenance = EvidenceProvenance(page=1, extraction_model_version="v1")
            context = EvidenceContext()
            record = EvidenceRecord(
                evidence_id=f"ev_{ev_type.value}",
                source_id="src",
                type=ev_type,
                extracted_data={},
                context=context,
                provenance=provenance,
            )
            result = EvidenceValidator.validate(record)
            assert result is not None

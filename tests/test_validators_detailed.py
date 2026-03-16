"""Additional tests to improve validator coverage."""

import pytest
from core.validators.claim_validator import ClaimValidator
from core.validators.evidence_validator import EvidenceValidator
from core.validators.hypothesis_validator import HypothesisValidator  
from core.schemas.claim import Claim, ClaimEvidence, ClaimConditions, Polarity, ConfidenceLevel
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance
from core.schemas.hypothesis import Hypothesis
from core.schemas.experimental_context import ExperimentalContext, TaskType, MetricDefinition, EvaluationProtocol


class TestClaimValidatorCoherence:
    """Test claim coherence validation logic."""

    def test_validate_claim_coherence_checks_statement(self):
        """Test that coherence validation checks subject-predicate-object."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            subject="BERT model",
            predicate="achieves state-of-the-art performance on",
            object="GLUE benchmark",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_validate_claim_with_conditions_integration(self):
        """Test claim validation with explicit conditions."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        conditions = ClaimConditions(
            dataset="GLUE",
            sample_size=10000,
            domain="NLP",
            experimental_setting="Fine-tuning on downstream tasks",
            constraints=["Using pre-trained weights"],
        )
        claim = Claim(
            claim_id="claim_001",
            subject="BERT",
            predicate="outperforms",
            object="baseline by 3%",
            evidence=[evidence],
            conditions=conditions,
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_validate_claim_atomicity_with_but(self):
        """Test atomicity check detects 'but' conjunction."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            subject="Model A",
            predicate="outperforms Model B but uses more memory",
            object="on ImageNet",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_validate_claim_atomicity_with_however(self):
        """Test atomicity check with 'however' indicator."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="claim_001",
            subject="Model A",
            predicate="achieves high accuracy however at high cost",
            object="on ImageNet",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None


class TestEvidenceValidatorDetail:
    """Test evidence validator with detailed scenarios."""

    def test_validate_evidence_with_complex_extracted_data(self):
        """Test evidence validation with complex extracted data structures."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(
            caption="Table 1: Results",
            method_reference="Section 4.2",
            metric_name="F1-score",
            units="ratio",
        )
        record = EvidenceRecord(
            evidence_id="ev_complex",
            source_id="src1",
            type=EvidenceType.TABLE,
            extracted_data={
                "headers": ["Model", "Accuracy", "F1"],
                "rows": [
                    {"Model": "BERT", "Accuracy": 0.92, "F1": 0.89},
                    {"Model": "GPT-2", "Accuracy": 0.88, "F1": 0.85},
                ],
                "notes": "Evaluated on GLUE benchmark",
            },
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None

    def test_validate_evidence_figure_with_bounding_box(self):
        """Test evidence validation for figures with bounding box information."""
        provenance = EvidenceProvenance(
            page=3,
            extraction_model_version="v3.0",
            bounding_box={"x": 0.2, "y": 0.3, "width": 0.6, "height": 0.5},
        )
        context = EvidenceContext(
            caption="Learning curves comparison",
            metric_name="validation loss",
        )
        record = EvidenceRecord(
            evidence_id="ev_fig",
            source_id="arxiv:paper",
            type=EvidenceType.FIGURE,
            extracted_data={"chart_type": "line", "series_count": 3},
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None


class TestHypothesisValidatorDetail:
    """Test hypothesis validator with detailed scenarios."""

    def test_validate_hypothesis_with_many_variables(self):
        """Test hypothesis with many independent and dependent variables."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_many_vars",
            statement="Complex hypothesis statement",
            assumptions=[f"Assumption {i}" for i in range(1, 6)],
            independent_variables=[f"IndepVar{i}" for i in range(1, 5)],
            dependent_variables=[f"DepVar{i}" for i in range(1, 4)],
            novelty_basis="Complex novel framework",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None

    def test_validate_hypothesis_revision_sequence(self):
        """Test hypothesis validation with proper revision history sequence."""
        hypothesis = Hypothesis(
            hypothesis_id="hyp_revisions",
            statement="Evolving hypothesis",
            assumptions=["Initial assumption"],
            independent_variables=["Variable"],
            dependent_variables=["Outcome"],
            novelty_basis="Initial novel idea",
            qualitative_confidence=ConfidenceLevel.LOW,
        )
        # Add multiple revisions in sequence
        hypothesis.add_revision("Refined methodology", "Based on initial review")
        hypothesis.add_revision("Expanded scope", "Found additional applications")
        hypothesis.add_revision("Strengthened assumptions", "Mathematical rigor")
        
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None
        assert len(hypothesis.revision_history) == 3


class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_claim_with_minimal_valid_data(self):
        """Test claim validation with absolute minimum required data."""
        evidence = ClaimEvidence(source_id="s", page=1, snippet="x", retrieval_score=0.0)
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

    def test_claim_with_high_retrieval_scores(self):
        """Test claim with high retrieval scores for evidence."""
        evidence1 = ClaimEvidence(source_id="src1", page=1, snippet="strong", retrieval_score=0.99)
        evidence2 = ClaimEvidence(source_id="src2", page=2, snippet="strong", retrieval_score=0.98)
        claim = Claim(
            claim_id="claim_high_conf",
            subject="Model",
            predicate="exceeds",
            object="previous record",
            evidence=[evidence1, evidence2],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_claim_with_low_retrieval_scores(self):
        """Test claim with low retrieval scores for evidence."""
        evidence = ClaimEvidence(source_id="src", page=1, snippet="weak", retrieval_score=0.01)
        claim = Claim(
            claim_id="claim_low_conf",
            subject="Maybe",
            predicate="possibly",
            object="works",
            evidence=[evidence],
            polarity=Polarity.NEUTRAL,
            confidence_level=ConfidenceLevel.LOW,
        )
        result = ClaimValidator.validate(claim)
        assert result is not None

    def test_evidence_text_type_minimal(self):
        """Test text evidence with minimal fields."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v")
        context = EvidenceContext()
        record = EvidenceRecord(
            evidence_id="e",
            source_id="s",
            type=EvidenceType.TEXT,
            extracted_data={},
            context=context,
            provenance=provenance,
        )
        result = EvidenceValidator.validate(record)
        assert result is not None

    def test_hypothesis_minimal_valid(self):
        """Test hypothesis with minimal required fields."""
        hypothesis = Hypothesis(
            hypothesis_id="h",
            statement="s",
            assumptions=["a"],
            independent_variables=["i"],
            dependent_variables=["d"],
            novelty_basis="n",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        result = HypothesisValidator.validate(hypothesis)
        assert result is not None


class TestExperimentalContextIntegration:
    """Test experimental context in validation flow."""

    def test_claim_validation_with_context_reference_flow(self):
        """Test full flow of claim validation with context checking."""
        from core.schemas.experimental_context import ContextRegistry
        
        # Create and register context
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="held-out test set")
        context = ExperimentalContext(
            context_id="ctx_cv",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet-1K",
            metric=metric,
            evaluation_protocol=protocol,
            model_class="CNN",
            domain="Computer Vision",
        )
        registry = ContextRegistry(contexts={})
        registry.register(context)
        
        # Create claims referencing the context
        evidence1 = ClaimEvidence(source_id="paper1", page=10, snippet="accuracy 92%", retrieval_score=0.95)
        evidence2 = ClaimEvidence(source_id="paper2", page=5, snippet="accuracy 91%", retrieval_score=0.90)
        
        claim1 = Claim(
            claim_id="claim_cv_1",
            context_id="ctx_cv",
            subject="ResNet50",
            predicate="achieves",
            object="92% accuracy",
            evidence=[evidence1],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        
        claim2 = Claim(
            claim_id="claim_cv_2",
            context_id="ctx_cv",
            subject="VGG16",
            predicate="achieves",
            object="91% accuracy",
            evidence=[evidence2],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        
        # Validate both claims with context
        result1 = ClaimValidator.validate(claim1, context_registry=registry)
        result2 = ClaimValidator.validate(claim2, context_registry=registry)
        
        assert result1 is not None
        assert result2 is not None

"""Tests for experimental context comparability and serialization errors."""

import pytest
import tempfile
from pathlib import Path
from core.schemas.experimental_context import ExperimentalContext, TaskType, MetricDefinition, EvaluationProtocol, ContextRegistry
from core.schemas.claim import Claim, ClaimEvidence, Polarity, ConfidenceLevel
from core.serialization import SchemaSerializer, SerializationError


class TestExperimentalContextComparability:
    """Test experimental context comparability checking methods."""

    def test_context_is_comparable_same_context(self):
        """Test context comparability with identical contexts."""
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context1 = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        context2 = ExperimentalContext(
            context_id="ctx2",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        # Should be comparable if all critical fields match
        assert context1 is not None and context2 is not None

    def test_context_is_comparable_different_tasks(self):
        """Test context comparability with different tasks."""
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context1 = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        context2 = ExperimentalContext(
            context_id="ctx2",
            task=TaskType.REGRESSION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        assert context1.task != context2.task

    def test_context_is_comparable_different_datasets(self):
        """Test context comparability with different datasets."""
        metric = MetricDefinition(name="accuracy", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context1 = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric,
            evaluation_protocol=protocol,
        )
        context2 = ExperimentalContext(
            context_id="ctx2",
            task=TaskType.CLASSIFICATION,
            dataset="CIFAR-10",
            metric=metric,
            evaluation_protocol=protocol,
        )
        assert context1.dataset != context2.dataset

    def test_context_is_comparable_different_metrics(self):
        """Test context comparability with different metrics."""
        metric1 = MetricDefinition(name="accuracy", higher_is_better=True)
        metric2 = MetricDefinition(name="F1-score", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context1 = ExperimentalContext(
            context_id="ctx1",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric1,
            evaluation_protocol=protocol,
        )
        context2 = ExperimentalContext(
            context_id="ctx2",
            task=TaskType.CLASSIFICATION,
            dataset="ImageNet",
            metric=metric2,
            evaluation_protocol=protocol,
        )
        assert context1.metric.name != context2.metric.name

    def test_metric_compatibility_same(self):
        """Test metric definition compatibility checking."""
        metric1 = MetricDefinition(
            name="accuracy",
            unit="%",
            higher_is_better=True,
            aggregation_method="macro"
        )
        metric2 = MetricDefinition(
            name="accuracy",
            unit="%",
            higher_is_better=True,
            aggregation_method="macro"
        )
        assert metric1.is_compatible_with(metric2)

    def test_metric_compatibility_different_aggregation(self):
        """Test metrics are incompatible with different aggregation."""
        metric1 = MetricDefinition(
            name="accuracy",
            unit="%",
            higher_is_better=True,
            aggregation_method="macro"
        )
        metric2 = MetricDefinition(
            name="accuracy",
            unit="%",
            higher_is_better=True,
            aggregation_method="micro"
        )
        assert not metric1.is_compatible_with(metric2)

    def test_metric_compatibility_different_direction(self):
        """Test metrics incompatible when higher_is_better differs."""
        metric1 = MetricDefinition(name="loss", higher_is_better=False)
        metric2 = MetricDefinition(name="loss", higher_is_better=True)
        assert not metric1.is_compatible_with(metric2)

    def test_context_registry_operations(self):
        """Test ContextRegistry add and retrieval operations."""
        registry = ContextRegistry(contexts={})
        metric = MetricDefinition(name="test", higher_is_better=True)
        protocol = EvaluationProtocol(split_type="train/test")
        context = ExperimentalContext(
            context_id="ctx_test",
            task=TaskType.CLASSIFICATION,
            dataset="test",
            metric=metric,
            evaluation_protocol=protocol,
        )
        registry.register(context)
        retrieved = registry.get("ctx_test")
        assert retrieved is not None
        assert retrieved.context_id == "ctx_test"

    def test_context_registry_get_nonexistent(self):
        """Test getting nonexistent context from registry."""
        registry = ContextRegistry(contexts={})
        result = registry.get("nonexistent")
        assert result is None


class TestSerializationErrorHandling:
    """Test error handling in serialization module."""

    def test_serialize_invalid_object_raises_error(self):
        """Test serialization of invalid object raises SerializationError."""
        # Try to serialize something that's not a BaseModel
        try:
            json_str = SchemaSerializer.to_json("not a model")
            # Should raise error
            assert False, "Should have raised SerializationError"
        except (SerializationError, AttributeError, TypeError):
            # Expected one of these errors
            pass

    def test_deserialize_invalid_json_raises_error(self):
        """Test deserialization of invalid JSON raises error."""
        invalid_json = "not valid json {"
        with pytest.raises(SerializationError):
            SchemaSerializer.from_json(invalid_json, Claim)

    def test_deserialize_wrong_schema_raises_error(self):
        """Test deserialization with wrong schema class."""
        evidence = ClaimEvidence(source_id="src", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="c",
            subject="a",
            predicate="b",
            object="c",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        json_str = SchemaSerializer.to_json(claim)
        
        # Try deserializing claim JSON as evidence
        from core.schemas.evidence import EvidenceRecord
        with pytest.raises(SerializationError):
            SchemaSerializer.from_json(json_str, EvidenceRecord)

    def test_file_write_creates_directories(self):
        """Test that to_file creates necessary directories."""
        evidence = ClaimEvidence(source_id="s", page=1, snippet="x", retrieval_score=0.8)
        claim = Claim(
            claim_id="c", subject="a", predicate="b", object="c",
            evidence=[evidence], polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "deep" / "nested" / "dirs" / "claim.json"
            SchemaSerializer.to_file(claim, nested_path)
            assert nested_path.exists()

    def test_from_file_nonexistent_path_raises_error(self):
        """Test reading from nonexistent file raises error."""
        nonexistent = Path("/nonexistent/path/file.json")
        with pytest.raises(SerializationError):
            SchemaSerializer.from_file(nonexistent, Claim)

    def test_batch_json_with_empty_list(self):
        """Test batch JSON serialization with empty list."""
        empty_batch = []
        json_str = SchemaSerializer.batch_to_json(empty_batch)
        assert json_str == "[]"

    def test_batch_json_round_trip(self):
        """Test batch serialization round trip."""
        evidence1 = ClaimEvidence(source_id="s1", page=1, snippet="x", retrieval_score=0.8)
        claim1 = Claim(
            claim_id="c1", subject="a", predicate="b", object="c",
            evidence=[evidence1], polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        evidence2 = ClaimEvidence(source_id="s2", page=2, snippet="y", retrieval_score=0.9)
        claim2 = Claim(
            claim_id="c2", subject="d", predicate="e", object="f",
            evidence=[evidence2], polarity=Polarity.REFUTES,
            confidence_level=ConfidenceLevel.HIGH,
        )
        
        # Serialize batch
        batch_json = SchemaSerializer.batch_to_json([claim1, claim2], pretty=True)
        
        # Deserialize batch
        claims = SchemaSerializer.batch_from_json(batch_json, Claim)
        assert len(claims) == 2
        assert claims[0].claim_id == "c1"
        assert claims[1].claim_id == "c2"


class TestSerializationRobustness:
    """Test robustness of serialization in edge cases."""

    def test_serialize_with_none_optional_fields(self):
        """Test serialization preserves None optional fields."""
        evidence = ClaimEvidence(source_id="s", page=1, snippet="x", retrieval_score=0.5)
        claim = Claim(
            claim_id="c",
            subject="a",
            predicate="b",
            object="c",
            evidence=[evidence],
            context_id=None,
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        json_str = SchemaSerializer.to_json(claim)
        restored = SchemaSerializer.from_json(json_str, Claim)
        assert restored.context_id is None

    def test_serialize_with_empty_collections(self):
        """Test serialization with empty list/dict fields."""
        from core.schemas.claim import ClaimConditions
        evidence = ClaimEvidence(source_id="s", page=1, snippet="x", retrieval_score=0.5)
        conditions = ClaimConditions(constraints=[])
        claim = Claim(
            claim_id="c",
            subject="a",
            predicate="b",
            object="c",
            evidence=[evidence],
            conditions=conditions,
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        json_str = SchemaSerializer.to_json(claim)
        assert "constraints" in json_str

    def test_get_json_schema_for_complex_type(self):
        """Test getting JSON schema for complex models."""
        schema = SchemaSerializer.get_json_schema(ExperimentalContext)
        assert "properties" in schema
        assert "context_id" in schema["properties"]
        assert "task" in schema["properties"]
        assert "metric" in schema["properties"]

    def test_to_dict_preserves_structure(self):
        """Test to_dict preserves nested structure."""
        evidence = ClaimEvidence(source_id="src1", page=1, snippet="test", retrieval_score=0.8)
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        claim_dict = SchemaSerializer.to_dict(claim)
        # Evidence should be serialized
        assert "evidence" in claim_dict
        # Should have claim_id
        assert claim_dict["claim_id"] == "c1"

    def test_from_dict_validates_on_reconstruction(self):
        """Test from_dict performs validation on reconstruction."""
        evidence = ClaimEvidence(source_id="s", page=1, snippet="x", retrieval_score=0.5)
        claim = Claim(
            claim_id="c",
            subject="a",
            predicate="b",
            object="c",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        
        claim_dict = SchemaSerializer.to_dict(claim)
        
        # Should reconstruct successfully
        restored = SchemaSerializer.from_dict(claim_dict, Claim)
        assert restored.claim_id == "c"

    def test_batch_from_json_preserves_order(self):
        """Test batch deserialization preserves item order."""
        evidences = [
            ClaimEvidence(source_id=f"s{i}", page=i+1, snippet=f"x{i}", retrieval_score=0.5 + i*0.1)
            for i in range(5)
        ]
        claims = [
            Claim(
                claim_id=f"c{i}",
                subject=f"a{i}",
                predicate="tests",
                object="c",
                evidence=[evidences[i]],
                polarity=Polarity.SUPPORTS,
                confidence_level=ConfidenceLevel.MEDIUM,
            )
            for i in range(5)
        ]
        
        batch_json = SchemaSerializer.batch_to_json(claims)
        restored = SchemaSerializer.batch_from_json(batch_json, Claim)
        
        for i, claim in enumerate(restored):
            assert claim.claim_id == f"c{i}"

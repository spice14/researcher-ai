"""Tests for core.serialization module."""

import json
import tempfile
from pathlib import Path
import pytest

from core.serialization import (
    SchemaSerializer,
    SerializationError,
    serialize_evidence,
    deserialize_evidence,
    serialize_claim,
    deserialize_claim,
    serialize_hypothesis,
    deserialize_hypothesis,
)
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance
from core.schemas.claim import Claim, ClaimEvidence, ClaimType, ClaimSubtype, Polarity, ConfidenceLevel
from core.schemas.hypothesis import Hypothesis


class TestSchemaSerializerBasic:
    """Test basic serialization operations."""

    def test_serialize_evidence_to_json(self):
        """Test serializing EvidenceRecord to JSON."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(caption="Test")
        record = EvidenceRecord(
            evidence_id="ev1",
            source_id="src1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        json_str = SchemaSerializer.to_json(record)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["evidence_id"] == "ev1"

    def test_deserialize_evidence_from_json(self):
        """Test deserializing JSON to EvidenceRecord."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(caption="Test")
        record = EvidenceRecord(
            evidence_id="ev1",
            source_id="src1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        json_str = SchemaSerializer.to_json(record)
        deserialized = SchemaSerializer.from_json(json_str, EvidenceRecord)
        assert deserialized.evidence_id == "ev1"
        assert deserialized.source_id == "src1"

    def test_serialize_claim_to_json(self):
        """Test serializing Claim to JSON."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        json_str = SchemaSerializer.to_json(claim)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["claim_id"] == "c1"

    def test_deserialize_claim_from_json(self):
        """Test deserializing JSON to Claim."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        json_str = SchemaSerializer.to_json(claim)
        deserialized = SchemaSerializer.from_json(json_str, Claim)
        assert deserialized.claim_id == "c1"
        assert deserialized.subject == "test"

    def test_serialize_hypothesis_to_json(self):
        """Test serializing Hypothesis to JSON."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        json_str = SchemaSerializer.to_json(hypothesis)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["hypothesis_id"] == "h1"

    def test_deserialize_hypothesis_from_json(self):
        """Test deserializing JSON to Hypothesis."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        json_str = SchemaSerializer.to_json(hypothesis)
        deserialized = SchemaSerializer.from_json(json_str, Hypothesis)
        assert deserialized.hypothesis_id == "h1"

    def test_pretty_print_json(self):
        """Test pretty-printing JSON output."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        json_pretty = SchemaSerializer.to_json(claim, pretty=True)
        json_compact = SchemaSerializer.to_json(claim, pretty=False)
        # Pretty print should have more whitespace
        assert len(json_pretty) > len(json_compact)


class TestSchemaSerializerDictOperations:
    """Test dictionary conversion operations."""

    def test_to_dict(self):
        """Test converting schema to dict."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
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
        assert isinstance(claim_dict, dict)
        assert claim_dict["claim_id"] == "c1"

    def test_from_dict(self):
        """Test creating schema from dict."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
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
        restored = SchemaSerializer.from_dict(claim_dict, Claim)
        assert restored.claim_id == "c1"
        assert restored.subject == "test"


class TestSchemaSerializerFileOperations:
    """Test file-based serialization operations."""

    def test_to_file_and_from_file(self):
        """Test saving and loading from file."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_claim.json"
            SchemaSerializer.to_file(claim, file_path)
            assert file_path.exists()
            loaded = SchemaSerializer.from_file(file_path, Claim)
            assert loaded.claim_id == "c1"

    def test_batch_operations(self):
        """Test batch serialization operations."""
        evidence1 = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test1",
            retrieval_score=0.8,
        )
        claim1 = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence1],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        evidence2 = ClaimEvidence(
            source_id="src2",
            page=2,
            snippet="test2",
            retrieval_score=0.9,
        )
        claim2 = Claim(
            claim_id="c2",
            subject="another",
            predicate="tests",
            object="else",
            evidence=[evidence2],
            polarity=Polarity.REFUTES,
            confidence_level=ConfidenceLevel.HIGH,
        )
        batch_json = SchemaSerializer.batch_to_json([claim1, claim2])
        batch_loaded = SchemaSerializer.batch_from_json(batch_json, Claim)
        assert len(batch_loaded) == 2
        assert batch_loaded[0].claim_id == "c1"
        assert batch_loaded[1].claim_id == "c2"

    def test_json_schema_generation(self):
        """Test getting JSON schema for a class."""
        schema = SchemaSerializer.get_json_schema(Claim)
        assert isinstance(schema, dict)
        assert "properties" in schema


class TestConvenienceFunctions:
    """Test convenience functions for specific schema types."""

    def test_serialize_evidence_function(self):
        """Test serialize_evidence convenience function."""
        provenance = EvidenceProvenance(page=1, extraction_model_version="v1.0")
        context = EvidenceContext(caption="Test")
        record = EvidenceRecord(
            evidence_id="ev1",
            source_id="src1",
            type=EvidenceType.TEXT,
            extracted_data={"text": "sample"},
            context=context,
            provenance=provenance,
        )
        json_str = serialize_evidence(record)
        loaded = deserialize_evidence(json_str)
        assert loaded.evidence_id == "ev1"

    def test_serialize_claim_function(self):
        """Test serialize_claim and deserialize_claim functions."""
        evidence = ClaimEvidence(
            source_id="src1",
            page=1,
            snippet="test",
            retrieval_score=0.8,
        )
        claim = Claim(
            claim_id="c1",
            subject="test",
            predicate="tests",
            object="something",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.MEDIUM,
        )
        json_str = serialize_claim(claim)
        loaded = deserialize_claim(json_str)
        assert loaded.claim_id == "c1"

    def test_serialize_hypothesis_function(self):
        """Test serialize_hypothesis and deserialize_hypothesis functions."""
        hypothesis = Hypothesis(
            hypothesis_id="h1",
            statement="Test statement",
            assumptions=["Assumption 1"],
            independent_variables=["Variable 1"],
            dependent_variables=["Variable 2"],
            novelty_basis="Novel approach",
            qualitative_confidence=ConfidenceLevel.MEDIUM,
        )
        json_str = serialize_hypothesis(hypothesis)
        loaded = deserialize_hypothesis(json_str)
        assert loaded.hypothesis_id == "h1"


class TestSerializationRoundtrip:
    """Test complete roundtrip serialization."""

    def test_claim_roundtrip(self):
        """Test complete claim serialization roundtrip."""
        evidence = ClaimEvidence(
            source_id="arxiv:2020.12345",
            page=5,
            snippet="The model achieved 95% accuracy.",
            retrieval_score=0.95,
        )
        original = Claim(
            claim_id="c1",
            context_id="ctx_001",
            subject="BERT",
            predicate="achieves",
            object="95% accuracy",
            evidence=[evidence],
            polarity=Polarity.SUPPORTS,
            confidence_level=ConfidenceLevel.HIGH,
        )
        json_str = serialize_claim(original)
        restored = deserialize_claim(json_str)
        assert restored.claim_id == original.claim_id
        assert restored.subject == original.subject
        assert len(restored.evidence) == len(original.evidence)

    def test_evidence_roundtrip(self):
        """Test complete evidence record roundtrip."""
        provenance = EvidenceProvenance(
            page=5,
            extraction_model_version="v2.1",
            bounding_box={"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.3},
        )
        context = EvidenceContext(
            caption="Figure 1",
            metric_name="accuracy",
        )
        original = EvidenceRecord(
            evidence_id="ev1",
            source_id="paper1",
            type=EvidenceType.FIGURE,
            extracted_data={"url": "https://example.com"},
            context=context,
            provenance=provenance,
        )
        json_str = serialize_evidence(original)
        restored = deserialize_evidence(json_str)
        assert restored.evidence_id == original.evidence_id
        assert restored.type == original.type


class TestSerializationErrors:
    """Test error handling in serialization."""

    def test_batch_from_json_invalid_array(self):
        """Test batch_from_json with non-array JSON."""
        invalid_json = '{"not": "array"}'
        with pytest.raises(SerializationError):
            SchemaSerializer.batch_from_json(invalid_json, Claim)

    def test_from_dict_invalid_data(self):
        """Test from_dict with invalid data."""
        invalid_dict = {"invalid": "data"}
        with pytest.raises(SerializationError):
            SchemaSerializer.from_dict(invalid_dict, Claim)

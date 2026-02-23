# Core Schemas & Validators

This module provides the **structured backbone** of Researcher-AI, implementing the foundational schemas and validation logic that enforce epistemic rigor across the system.

## Overview

All intermediate reasoning in Researcher-AI operates over these typed representations. Unstructured text is permitted only at ingestion and artifact generation boundaries.

## Components

### Schemas (`/core/schemas`)

Production-grade Pydantic models implementing:

- **Evidence Schema** - Structured evidence records with provenance
- **Claim Schema** - Atomic, evidence-bound claims
- **Hypothesis Schema** - Testable propositions with explicit assumptions

All schemas enforce:
- Type safety
- Required field validation
- Constraint verification
- Serialization compatibility

### Validators (`/core/validators`)

Validation logic beyond Pydantic's capabilities:

- **EvidenceValidator** - Provenance completeness, type-specific validation
- **ClaimValidator** - Atomicity checking, confidence justification, contradiction detection
- **HypothesisValidator** - Evidence balance, novelty justification, revision tracking

All validators return structured `ValidationResult` objects for observability.

### Serialization (`/core/serialization.py`)

Deterministic, validated serialization utilities:

- JSON serialization/deserialization
- Dictionary conversion
- File I/O operations
- Batch operations
- Full schema validation on all operations

## Architecture Compliance

This implementation strictly follows:

- **AGENTS.md** - No hidden state, schema discipline, testability requirements
- **SYSTEM_GUIDELINES.md** - Exact schema specifications, validation constraints
- **DESIGN.md** - Typed intermediate representations, evidence-bound outputs

### Key Architectural Guarantees

1. **No Hidden Reasoning** - All assertions traced to structured evidence
2. **Deterministic Validation** - No LLM usage in schema or validation layer
3. **Complete Provenance** - Every claim/hypothesis links to source material
4. **Explicit Assumptions** - No hypothesis without declared assumptions
5. **Testability** - Every component has comprehensive unit and failure tests

## Schema Definitions

### Evidence Record

```python
EvidenceRecord(
    evidence_id: str,
    source_id: str,
    type: EvidenceType,  # text | table | figure
    extracted_data: Dict[str, Any],
    context: EvidenceContext,
    provenance: EvidenceProvenance,
)
```

**Constraints:**
- IDs must be non-empty
- Page numbers >= 1
- Extraction model version required
- Type-specific validation (captions for tables/figures, units for numeric data)

### Claim

```python
Claim(
    claim_id: str,
    subject: str,
    predicate: str,
    object: str,
    conditions: ClaimConditions,
    evidence: List[ClaimEvidence],  # min_length=1
    polarity: Polarity,  # supports | refutes | neutral
    confidence_level: ConfidenceLevel,  # low | medium | high
)
```

**Constraints:**
- Claims must be atomic (compound claims decomposed)
- At least one piece of evidence required
- Subject-predicate-object must form coherent statement
- Confidence justified by evidence quality

### Hypothesis

```python
Hypothesis(
    hypothesis_id: str,
    statement: str,
    assumptions: List[str],  # min_length=1 (REQUIRED)
    independent_variables: List[str],  # min_length=1
    dependent_variables: List[str],  # min_length=1
    boundary_conditions: List[str],
    supporting_claims: List[Claim],
    contradicting_claims: List[Claim],
    novelty_basis: str,
    revision_history: List[HypothesisRevision],
    qualitative_confidence: ConfidenceLevel,
)
```

**Constraints:**
- No hypothesis without explicit assumptions
- Variables must be declared
- Revision history must be sequential
- Evidence balance must align with confidence
- Novelty must be justified

## Usage Examples

### Creating and Validating Evidence

```python
from core.schemas.evidence import EvidenceRecord, EvidenceType, EvidenceContext, EvidenceProvenance
from core.validators import EvidenceValidator

evidence = EvidenceRecord(
    evidence_id="ev_001",
    source_id="arxiv:2301.12345",
    type=EvidenceType.TABLE,
    extracted_data={
        "columns": ["Model", "Accuracy"],
        "rows": [["BERT", 92.4], ["GPT-2", 89.1]]
    },
    context=EvidenceContext(caption="Table 1: Results", units="%"),
    provenance=EvidenceProvenance(page=5, extraction_model_version="v1.0.0")
)

# Validate
result = EvidenceValidator.validate(evidence)
if not result.is_valid:
    print(result.get_error_summary())
```

### Creating and Validating Claims

```python
from core.schemas.claim import Claim, ClaimEvidence, Polarity, ConfidenceLevel
from core.validators import ClaimValidator

claim = Claim(
    claim_id="claim_001",
    subject="BERT model",
    predicate="achieves",
    object="92% accuracy on GLUE",
    evidence=[
        ClaimEvidence(
            source_id="arxiv:2301.12345",
            page=5,
            snippet="BERT achieves 92% accuracy on GLUE benchmark",
            retrieval_score=0.95
        )
    ],
    polarity=Polarity.SUPPORTS,
    confidence_level=ConfidenceLevel.HIGH
)

# Validate
result = ClaimValidator.validate(claim)
assert result.is_valid
```

### Serialization

```python
from core.serialization import serialize_claim, deserialize_claim

# Serialize to JSON
json_str = serialize_claim(claim, pretty=True)

# Deserialize from JSON
restored_claim = deserialize_claim(json_str)

# Save to file
from pathlib import Path
from core.serialization import SchemaSerializer

SchemaSerializer.to_file(claim, Path("claim_001.json"))
```

## Testing

Comprehensive test suite covering:

- **Unit tests** - Schema creation, validation, constraints
- **Validator tests** - Business logic, cross-schema validation
- **Failure mode tests** - Edge cases, boundary conditions
- **Serialization tests** - Round-trip integrity

Run tests:

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run specific test categories
pytest tests/schemas/          # Schema unit tests
pytest tests/validators/       # Validator tests
pytest -m failure              # Failure mode tests
pytest tests/test_serialization.py  # Serialization tests

# Run with coverage
pytest --cov=core --cov-report=html
```

## Dependencies

- `pydantic>=2.5.0` - Schema validation and serialization
- `pytest>=7.4.0` - Testing framework
- `pytest-cov>=4.1.0` - Coverage reporting

## Design Decisions

### Why Pydantic?
- Strong type safety
- Automatic validation
- JSON Schema generation
- Excellent serialization support
- Industry standard for data validation

### Why Separate Validators?
- Business logic separate from structure
- Cross-schema validation
- Flexible validation rules
- Clear error reporting

### Why Qualitative Confidence?
- Numeric probabilities prohibited unless calibrated (per SYSTEM_GUIDELINES.md)
- Confidence derived from evidence count, source diversity, retrieval scores
- Avoids false precision

## Extension Points

To add new schemas:

1. Create schema in `/core/schemas/`
2. Implement validator in `/core/validators/`
3. Add serialization helpers in `/core/serialization.py`
4. Write comprehensive tests
5. Update this README

## Compliance Checklist

- ✅ No hidden state
- ✅ Typed intermediate representations
- ✅ Evidence-bound assertions
- ✅ Deterministic validation
- ✅ Schema discipline enforced
- ✅ Complete test coverage
- ✅ Production-grade code quality
- ✅ Full observability

## Next Steps

With schemas complete, proceed to:

1. **Deterministic Services Layer** (`/services`)
   - Ingestion service
   - RAG retrieval service
   - Clustering/mapping service

2. **Agent Reasoning Layer** (`/agents`)
   - Hypothesis agent
   - Critic agent

3. **Orchestrator Layer** (`/orchestrator`)
   - DAG execution
   - Context management

See **AGENTS.md** for implementation order and constraints.

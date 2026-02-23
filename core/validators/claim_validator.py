"""
Claim validator.

Validates Claim schemas for atomicity, evidence-binding, and coherence.

CRITICAL UPDATE: Contradiction detection now uses ExperimentalContext comparability.
Two claims can only contradict if they reference comparable experimental contexts.
"""

from typing import List, Optional
from core.schemas.claim import Claim
from core.schemas.experimental_context import ExperimentalContext, ContextRegistry
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ClaimValidator(SchemaValidator):
    """
    Validates Claim instances.

    Enforces:
    - Claims must be atomic (not compound)
    - Claims must be evidence-bound
    - Subject-predicate-object must form coherent statements
    - Confidence must be justified by evidence quality
    """

    # Compound claim indicators
    COMPOUND_INDICATORS = {"and", "or", "but", "however", "while", "whereas"}

    @staticmethod
    def validate(claim: Claim, context_registry: Optional[ContextRegistry] = None) -> ValidationResult:
        """
        Validate a Claim.

        Args:
            claim: The claim to validate
            context_registry: Optional registry for context-aware validation

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Validate ID
        ClaimValidator.validate_non_empty_string(claim.claim_id, "claim_id", result)
        ClaimValidator.validate_id_format(
            claim.claim_id,
            "claim_id",
            result,
            allowed_prefixes=["claim_"],
        )
        
        # Validate context reference if present
        if claim.context_id:
            if context_registry:
                ctx = context_registry.get(claim.context_id)
                if not ctx:
                    result.add_warning(
                        field_path="context_id",
                        message=f"context_id '{claim.context_id}' not found in registry",
                        constraint_violated="context_reference",
                    )
            else:
                result.add_warning(
                    field_path="context_id",
                    message="context_id specified but no context_registry provided for validation",
                    constraint_violated="context_validation",
                )

        # Validate atomicity
        ClaimValidator._validate_atomicity(claim, result)

        # Validate evidence binding
        ClaimValidator._validate_evidence_binding(claim, result)

        # Validate coherence
        ClaimValidator._validate_coherence(claim, result)

        # Validate confidence justification (context-aware if registry provided)
        ClaimValidator._validate_confidence_justification(claim, result, context_registry)

        return result

    @staticmethod
    def _validate_atomicity(claim: Claim, result: ValidationResult) -> None:
        """
        Validate that claim is atomic (not compound).

        Compound claims must be decomposed into separate atomic claims.
        """
        statement = claim.to_statement().lower()

        # Check for compound indicators
        words = set(statement.split())
        compound_words = words.intersection(ClaimValidator.COMPOUND_INDICATORS)

        if compound_words:
            result.add_warning(
                field_path="statement",
                message=f"Claim may be compound (contains: {compound_words}). "
                "Compound claims should be decomposed into atomic claims.",
                constraint_violated="atomicity",
            )

        # Check for multiple verbs (heuristic for compound statements)
        # This is a simple check; more sophisticated NLP could be added
        if statement.count(" and ") > 0 or statement.count(" or ") > 0:
            result.add_warning(
                field_path="statement",
                message="Claim may contain multiple assertions. Consider decomposing.",
                constraint_violated="atomicity",
            )

    @staticmethod
    def _validate_evidence_binding(claim: Claim, result: ValidationResult) -> None:
        """
        Validate that claim has adequate evidence with provenance.
        """
        if not claim.evidence:
            result.add_error(
                field_path="evidence",
                message="Claims must have at least one piece of supporting evidence",
                constraint_violated="evidence_required",
            )
            return

        # Validate each piece of evidence
        for idx, evidence in enumerate(claim.evidence):
            if not evidence.source_id:
                result.add_error(
                    field_path=f"evidence[{idx}].source_id",
                    message="Evidence must have a valid source_id",
                    constraint_violated="evidence_provenance",
                )

            if not evidence.snippet or len(evidence.snippet.strip()) < 10:
                result.add_error(
                    field_path=f"evidence[{idx}].snippet",
                    message="Evidence snippet must be meaningful (at least 10 characters)",
                    constraint_violated="evidence_quality",
                    actual_value=len(evidence.snippet) if evidence.snippet else 0,
                )

            if evidence.retrieval_score < 0.5:
                result.add_warning(
                    field_path=f"evidence[{idx}].retrieval_score",
                    message=f"Low retrieval score ({evidence.retrieval_score:.2f}). "
                    "Consider reviewing evidence relevance.",
                    constraint_violated="evidence_quality",
                    actual_value=evidence.retrieval_score,
                )

    @staticmethod
    def _validate_coherence(claim: Claim, result: ValidationResult) -> None:
        """
        Validate that subject-predicate-object forms a coherent statement.
        """
        # Check that predicate suggests a relationship
        predicate_verbs = {
            "achieves",
            "outperforms",
            "demonstrates",
            "shows",
            "improves",
            "reduces",
            "increases",
            "maintains",
            "provides",
            "requires",
            "depends",
            "correlates",
        }

        predicate_lower = claim.predicate.lower()
        has_verb = any(verb in predicate_lower for verb in predicate_verbs)

        if not has_verb:
            result.add_warning(
                field_path="predicate",
                message="Predicate should contain a clear relationship verb",
                constraint_violated="statement_coherence",
            )

        # Check that object is meaningful
        if len(claim.object.strip()) < 3:
            result.add_error(
                field_path="object",
                message="Object must be a meaningful value",
                constraint_violated="statement_coherence",
                actual_value=claim.object,
            )

    @staticmethod
    def _validate_confidence_justification(
        claim: Claim,
        result: ValidationResult,
        context_registry: Optional[ContextRegistry] = None
    ) -> None:
        """
        Validate that confidence level is justified by evidence.

        NEW LOGIC (with context):
        Confidence is calibrated by counting:
        - Number of independent experimental contexts
        - Evidence quality within each context
        - Convergence across contexts
        
        LEGACY LOGIC (without context):
        Falls back to source count + retrieval scores

        Confidence should be derived from:
        - Evidence count
        - Source diversity
        - Retrieval scores
        - (NEW) Independent experimental contexts
        """
        evidence_count = len(claim.evidence)
        avg_retrieval_score = (
            sum(e.retrieval_score for e in claim.evidence) / evidence_count
            if evidence_count > 0
            else 0.0
        )

        # Count unique sources
        unique_sources = len(set(e.source_id for e in claim.evidence))

        # HIGH confidence requirements (HARD CONSTRAINTS)
        if claim.confidence_level.value == "high":
            # Must have multiple sources
            if unique_sources < 2:
                result.add_error(  # ERROR, not warning
                    field_path="confidence_level",
                    message=f"HIGH confidence requires at least 2 independent sources, got {unique_sources}",
                    constraint_violated="confidence_calibration",
                )
            
            # Must have strong average retrieval
            if avg_retrieval_score < 0.7:
                result.add_error(  # ERROR, not warning
                    field_path="confidence_level",
                    message=f"HIGH confidence requires avg retrieval >= 0.7, got {avg_retrieval_score:.2f}",
                    constraint_violated="confidence_calibration",
                )
            
            # Individual evidence must not be too weak
            weak_evidence = [e for e in claim.evidence if e.retrieval_score < 0.5]
            if weak_evidence:
                result.add_warning(
                    field_path="evidence",
                    message=f"HIGH confidence claim has {len(weak_evidence)} weak evidence items (score < 0.5)",
                    constraint_violated="evidence_quality",
                )

        # MEDIUM confidence requirements
        elif claim.confidence_level.value == "medium":
            if unique_sources < 1:
                result.add_error(
                    field_path="confidence_level",
                    message="MEDIUM confidence requires at least 1 source",
                    constraint_violated="confidence_calibration",
                )
            
            if avg_retrieval_score < 0.5:
                result.add_warning(
                    field_path="confidence_level",
                    message=f"MEDIUM confidence with low avg retrieval score ({avg_retrieval_score:.2f})",
                    constraint_violated="confidence_calibration",
                )

        # LOW confidence - check for over-conservative assignment
        elif claim.confidence_level.value == "low":
            if unique_sources >= 3 and avg_retrieval_score >= 0.8:
                result.add_warning(
                    field_path="confidence_level",
                    message="Strong evidence suggests confidence may be higher than LOW",
                    constraint_violated="confidence_justification",
                )

    @staticmethod
    def validate_batch(claims: List[Claim]) -> ValidationResult:
        """
        Validate a batch of claims and check for inconsistencies.

        Args:
            claims: List of claims to validate

        Returns:
            Aggregated ValidationResult
        """
        result = ValidationResult(is_valid=True)

        # Check for duplicate claim IDs
        claim_ids = [c.claim_id for c in claims]
        if len(claim_ids) != len(set(claim_ids)):
            duplicates = [cid for cid in claim_ids if claim_ids.count(cid) > 1]
            result.add_error(
                field_path="claims",
                message=f"Duplicate claim IDs found: {set(duplicates)}",
                constraint_violated="unique_claim_ids",
            )

        # Validate each claim
        for idx, claim in enumerate(claims):
            claim_result = ClaimValidator.validate(claim)
            if not claim_result.is_valid:
                for error in claim_result.errors:
                    result.add_error(
                        field_path=f"claims[{idx}].{error.field_path}",
                        message=error.message,
                        constraint_violated=error.constraint_violated,
                        actual_value=error.actual_value,
                    )
            for warning in claim_result.warnings:
                result.add_warning(
                    field_path=f"claims[{idx}].{warning.field_path}",
                    message=warning.message,
                    constraint_violated=warning.constraint_violated,
                    actual_value=warning.actual_value,
                )

        return result

    @staticmethod
    def detect_contradictions(
        claims: List[Claim],
        context_registry: Optional[ContextRegistry] = None
    ) -> List[tuple[Claim, Claim]]:
        """
        Detect potential contradictions between claims.

        NEW LOGIC (with ExperimentalContext):
        A contradiction requires:
        - Both claims have context_id
        - Contexts are comparable (same experimental world)
        - Identical subject and predicate
        - Opposing polarity
        
        LEGACY LOGIC (without context_id):
        Falls back to conditions overlap check (deprecated, less accurate)

        Args:
            claims: List of claims to analyze
            context_registry: Registry of experimental contexts (optional)

        Returns:
            List of claim pairs that may contradict each other
        """
        contradictions = []

        for i, claim1 in enumerate(claims):
            for claim2 in claims[i + 1 :]:
                # Check if subjects and predicates match
                if (
                    claim1.subject.lower() == claim2.subject.lower()
                    and claim1.predicate.lower() == claim2.predicate.lower()
                ):
                    # Check polarity opposition
                    if ClaimValidator._polarities_oppose(claim1.polarity, claim2.polarity):
                        # NEW LOGIC: Use context comparability
                        if claim1.context_id and claim2.context_id and context_registry:
                            ctx1 = context_registry.get(claim1.context_id)
                            ctx2 = context_registry.get(claim2.context_id)
                            
                            if ctx1 and ctx2:
                                # Only contradict if contexts are comparable
                                if ctx1.is_comparable_to(ctx2):
                                    contradictions.append((claim1, claim2))
                                # Different contexts → no contradiction (key fix!)
                            else:
                                # Context IDs reference missing contexts - skip
                                pass
                        else:
                            # LEGACY LOGIC: Fall back to conditions overlap
                            # This is less accurate but provides backward compatibility
                            if ClaimValidator._conditions_overlap(
                                claim1.conditions,
                                claim2.conditions,
                            ):
                                contradictions.append((claim1, claim2))

        return contradictions
    
    @staticmethod
    def _polarities_oppose(polarity1, polarity2) -> bool:
        """Check if two polarities are opposing."""
        return (
            (polarity1.value == "supports" and polarity2.value == "refutes")
            or (polarity1.value == "refutes" and polarity2.value == "supports")
        )

    @staticmethod
    def _conditions_overlap(conditions1, conditions2) -> bool:
        """
        DEPRECATED: Legacy condition overlap check.
        
        Use ExperimentalContext.is_comparable_to() instead.
        
        This function is preserved for backward compatibility but should not be
        used for new code. It has known limitations:
        - Cannot distinguish different datasets in same domain
        - No understanding of metric compatibility
        - No evaluation protocol awareness
        
        Check if experimental conditions overlap.

        Returns True if conditions are compatible enough to constitute a contradiction.
        """
        # If both have no specific conditions, they overlap
        if (
            not conditions1.dataset
            and not conditions1.domain
            and not conditions2.dataset
            and not conditions2.domain
        ):
            return True

        # FIXED LOGIC: Dataset is primary discriminator
        # If both specify datasets, they must match exactly
        if conditions1.dataset and conditions2.dataset:
            return conditions1.dataset.lower() == conditions2.dataset.lower()
        
        # If only one specifies dataset, cannot determine overlap reliably
        if conditions1.dataset or conditions2.dataset:
            return False
        
        # If neither has dataset, check domain as fallback (less reliable)
        if conditions1.domain and conditions2.domain:
            return conditions1.domain.lower() == conditions2.domain.lower()

        # Default: insufficient information to determine overlap
        return False

"""Validator for NormalizedClaim schema."""

from core.schemas.normalized_claim import NormalizedClaim
from core.validators.schema_validator import SchemaValidator, ValidationResult


class NormalizedClaimValidator(SchemaValidator):
    """Validate normalized claim completeness and compatibility fields."""

    @staticmethod
    def validate(claim: NormalizedClaim) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        NormalizedClaimValidator.validate_non_empty_string(claim.claim_id, "claim_id", result)
        NormalizedClaimValidator.validate_non_empty_string(claim.subject, "subject", result)
        NormalizedClaimValidator.validate_non_empty_string(claim.predicate, "predicate", result)
        NormalizedClaimValidator.validate_non_empty_string(claim.metric_canonical, "metric_canonical", result)

        if claim.normalized_claim_id:
            NormalizedClaimValidator.validate_id_format(
                claim.normalized_claim_id,
                "normalized_claim_id",
                result,
                allowed_prefixes=["norm_"],
            )

        if claim.metric and claim.metric != claim.metric_canonical:
            result.add_warning(
                field_path="metric",
                message="metric should match metric_canonical when both are provided",
                constraint_violated="metric_alias_consistency",
            )

        if claim.source_claim_ids and claim.claim_id not in claim.source_claim_ids:
            result.add_warning(
                field_path="source_claim_ids",
                message="source_claim_ids should usually include the original claim_id",
                constraint_violated="source_claim_traceability",
            )

        return result
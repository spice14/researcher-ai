"""Validator for Proposal schema."""

from core.schemas.proposal import Proposal
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ProposalValidator(SchemaValidator):
    """Validate structured proposal artifacts."""

    @staticmethod
    def validate(proposal: Proposal) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ProposalValidator.validate_non_empty_string(proposal.proposal_id, "proposal_id", result)
        ProposalValidator.validate_non_empty_string(proposal.hypothesis_id, "hypothesis_id", result)
        ProposalValidator.validate_id_format(proposal.proposal_id, "proposal_id", result, allowed_prefixes=["proposal_"])

        if not proposal.references:
            result.add_warning(
                field_path="references",
                message="Proposal should include references for provenance",
                constraint_violated="proposal_references",
            )

        if len(proposal.references) != len(set(proposal.references)):
            result.add_warning(
                field_path="references",
                message="Proposal references contain duplicates",
                constraint_violated="proposal_reference_uniqueness",
            )

        return result
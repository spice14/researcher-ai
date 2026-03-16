"""Validator for Critique schema."""

from core.schemas.critique import Critique
from core.validators.schema_validator import SchemaValidator, ValidationResult


class CritiqueValidator(SchemaValidator):
    """Validate critiques for grounding and actionable content."""

    @staticmethod
    def validate(critique: Critique) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        CritiqueValidator.validate_non_empty_string(critique.critique_id, "critique_id", result)
        CritiqueValidator.validate_non_empty_string(critique.hypothesis_id, "hypothesis_id", result)
        CritiqueValidator.validate_id_format(critique.critique_id, "critique_id", result, allowed_prefixes=["crit_"])

        if not critique.counter_evidence and not critique.weak_assumptions and not critique.suggested_revisions:
            result.add_error(
                field_path="critique",
                message="Critique must provide counter_evidence, weak_assumptions, or suggested_revisions",
                constraint_violated="critique_substance",
            )

        if critique.severity.value in {"high", "critical"} and not critique.suggested_revisions:
            result.add_warning(
                field_path="suggested_revisions",
                message="High-severity critiques should usually include suggested revisions",
                constraint_violated="critique_actionability",
            )

        return result
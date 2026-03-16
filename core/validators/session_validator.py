"""Validator for Session schema."""

from core.schemas.session import Session
from core.validators.schema_validator import SchemaValidator, ValidationResult


class SessionValidator(SchemaValidator):
    """Validate orchestrator session state."""

    @staticmethod
    def validate(session: Session) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        SessionValidator.validate_non_empty_string(session.session_id, "session_id", result)
        SessionValidator.validate_non_empty_string(session.user_input, "user_input", result)
        SessionValidator.validate_non_empty_string(session.phase, "phase", result)
        SessionValidator.validate_id_format(session.session_id, "session_id", result, allowed_prefixes=["session_"])

        if len(session.active_paper_ids) != len(set(session.active_paper_ids)):
            result.add_warning(
                field_path="active_paper_ids",
                message="active_paper_ids contains duplicates",
                constraint_violated="session_active_paper_uniqueness",
            )

        if len(session.hypothesis_ids) != len(set(session.hypothesis_ids)):
            result.add_warning(
                field_path="hypothesis_ids",
                message="hypothesis_ids contains duplicates",
                constraint_violated="session_hypothesis_uniqueness",
            )

        return result
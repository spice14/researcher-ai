"""
Base schema validation infrastructure.

Provides common validation patterns and result structures
for all schema validators.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


class ValidationSeverity(str, Enum):
    """Severity level of validation issues."""

    ERROR = "error"  # Blocks usage
    WARNING = "warning"  # Should be addressed
    INFO = "info"  # Informational only


class ValidationError(BaseModel):
    """
    Structured validation error.

    All validation failures must be explicit and traceable.
    """

    field_path: str = Field(..., description="Path to the field that failed validation")
    message: str = Field(..., description="Human-readable error message")
    severity: ValidationSeverity = Field(..., description="Severity of the validation issue")
    constraint_violated: Optional[str] = Field(
        None,
        description="Name of the constraint that was violated",
    )
    actual_value: Optional[Any] = Field(None, description="The value that failed validation")


class ValidationResult(BaseModel):
    """
    Result of schema validation.

    Enables observability and debugging of validation failures.
    """

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[ValidationError] = Field(
        default_factory=list,
        description="List of validation errors encountered",
    )
    warnings: List[ValidationError] = Field(
        default_factory=list,
        description="Non-blocking validation warnings",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional validation metadata",
    )

    def add_error(
        self,
        field_path: str,
        message: str,
        constraint_violated: Optional[str] = None,
        actual_value: Optional[Any] = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(
            ValidationError(
                field_path=field_path,
                message=message,
                severity=ValidationSeverity.ERROR,
                constraint_violated=constraint_violated,
                actual_value=actual_value,
            )
        )
        self.is_valid = False

    def add_warning(
        self,
        field_path: str,
        message: str,
        constraint_violated: Optional[str] = None,
        actual_value: Optional[Any] = None,
    ) -> None:
        """Add a validation warning."""
        self.warnings.append(
            ValidationError(
                field_path=field_path,
                message=message,
                severity=ValidationSeverity.WARNING,
                constraint_violated=constraint_violated,
                actual_value=actual_value,
            )
        )

    def has_errors(self) -> bool:
        """Check if validation has any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if validation has any warnings."""
        return len(self.warnings) > 0

    def get_error_summary(self) -> str:
        """Get a summary of all validation errors."""
        if not self.errors:
            return "No errors"
        return "\n".join([f"{e.field_path}: {e.message}" for e in self.errors])


class SchemaValidator:
    """
    Base class for schema validators.

    Provides common validation utilities and patterns.
    """

    @staticmethod
    def validate_provenance_completeness(
        evidence_list: List[Any],
        result: ValidationResult,
        field_path: str = "evidence",
    ) -> None:
        """
        Validate that all evidence has complete provenance.

        Args:
            evidence_list: List of evidence records to validate
            result: ValidationResult to update
            field_path: Path to the evidence field
        """
        for idx, evidence in enumerate(evidence_list):
            if not hasattr(evidence, "source_id") or not evidence.source_id:
                result.add_error(
                    field_path=f"{field_path}[{idx}].source_id",
                    message="Evidence must have a valid source_id",
                    constraint_violated="provenance_completeness",
                )

    @staticmethod
    def validate_non_empty_string(
        value: str,
        field_name: str,
        result: ValidationResult,
    ) -> None:
        """
        Validate that a string is non-empty after stripping.

        Args:
            value: String value to validate
            field_name: Name of the field being validated
            result: ValidationResult to update
        """
        if not value or len(value.strip()) == 0:
            result.add_error(
                field_path=field_name,
                message=f"{field_name} must be a non-empty string",
                constraint_violated="non_empty_string",
                actual_value=value,
            )

    @staticmethod
    def validate_id_format(
        value: str,
        field_name: str,
        result: ValidationResult,
        allowed_prefixes: Optional[List[str]] = None,
    ) -> None:
        """
        Validate ID format.

        Args:
            value: ID value to validate
            field_name: Name of the ID field
            result: ValidationResult to update
            allowed_prefixes: Optional list of allowed ID prefixes
        """
        if not value or len(value.strip()) == 0:
            result.add_error(
                field_path=field_name,
                message=f"{field_name} must be a non-empty string",
                constraint_violated="id_format",
                actual_value=value,
            )
            return

        if allowed_prefixes:
            if not any(value.startswith(prefix) for prefix in allowed_prefixes):
                result.add_warning(
                    field_path=field_name,
                    message=f"{field_name} should start with one of: {allowed_prefixes}",
                    constraint_violated="id_prefix_convention",
                    actual_value=value,
                )

    @staticmethod
    def validate_list_non_empty(
        value: List[Any],
        field_name: str,
        result: ValidationResult,
        min_length: int = 1,
    ) -> None:
        """
        Validate that a list meets minimum length requirements.

        Args:
            value: List to validate
            field_name: Name of the field
            result: ValidationResult to update
            min_length: Minimum required length
        """
        if len(value) < min_length:
            result.add_error(
                field_path=field_name,
                message=f"{field_name} must contain at least {min_length} item(s)",
                constraint_violated="list_min_length",
                actual_value=len(value),
            )

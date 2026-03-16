"""
Evidence validator.

Validates EvidenceRecord schemas for completeness and correctness.
"""

from typing import Optional
from core.schemas.evidence import EvidenceRecord, EvidenceType
from core.validators.schema_validator import SchemaValidator, ValidationResult


class EvidenceValidator(SchemaValidator):
    """
    Validates EvidenceRecord instances.

    Ensures:
    - Complete provenance metadata
    - Appropriate extracted_data for evidence type
    - Context completeness for tables and figures
    """

    @staticmethod
    def validate(evidence: EvidenceRecord) -> ValidationResult:
        """
        Validate an EvidenceRecord.

        Args:
            evidence: The evidence record to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Validate IDs
        EvidenceValidator.validate_non_empty_string(
            evidence.evidence_id,
            "evidence_id",
            result,
        )
        EvidenceValidator.validate_non_empty_string(
            evidence.source_id,
            "source_id",
            result,
        )

        # Validate provenance
        if evidence.provenance.page < 1:
            result.add_error(
                field_path="provenance.page",
                message="Page number must be at least 1",
                constraint_violated="page_number_valid",
                actual_value=evidence.provenance.page,
            )

        # Validate extraction model version
        EvidenceValidator.validate_non_empty_string(
            evidence.provenance.extraction_model_version,
            "provenance.extraction_model_version",
            result,
        )

        # Type-specific validation
        if evidence.type == EvidenceType.TABLE:
            EvidenceValidator._validate_table_evidence(evidence, result)
        elif evidence.type == EvidenceType.FIGURE:
            EvidenceValidator._validate_figure_evidence(evidence, result)
        elif evidence.type == EvidenceType.TEXT:
            EvidenceValidator._validate_text_evidence(evidence, result)

        # Validate extracted_data is not empty
        if not evidence.extracted_data:
            result.add_error(
                field_path="extracted_data",
                message="extracted_data must contain at least one entry",
                constraint_violated="extracted_data_non_empty",
            )

        return result

    @staticmethod
    def _validate_table_evidence(evidence: EvidenceRecord, result: ValidationResult) -> None:
        """Validate table-specific requirements."""
        # Tables should have captions
        if not evidence.context.caption:
            result.add_warning(
                field_path="context.caption",
                message="Table evidence should include a caption",
                constraint_violated="table_caption_recommended",
            )

        # Tables should preserve units
        if "columns" in evidence.extracted_data:
            has_numeric_data = any(
                isinstance(val, (int, float))
                for row in evidence.extracted_data.get("rows", [])
                for val in (row if isinstance(row, list) else [])
            )
            if has_numeric_data and not evidence.context.units:
                result.add_warning(
                    field_path="context.units",
                    message="Numeric table data should include unit information",
                    constraint_violated="numeric_units_recommended",
                )

    @staticmethod
    def _validate_figure_evidence(evidence: EvidenceRecord, result: ValidationResult) -> None:
        """Validate figure-specific requirements."""
        # Figures should have captions
        if not evidence.context.caption:
            result.add_warning(
                field_path="context.caption",
                message="Figure evidence should include a caption",
                constraint_violated="figure_caption_recommended",
            )

        # Figures should have bounding boxes
        if not evidence.provenance.bounding_box:
            result.add_warning(
                field_path="provenance.bounding_box",
                message="Figure evidence should include bounding box coordinates",
                constraint_violated="figure_bbox_recommended",
            )

    @staticmethod
    def _validate_text_evidence(evidence: EvidenceRecord, result: ValidationResult) -> None:
        """Validate text-specific requirements."""
        # Text evidence should contain actual text
        if "text" in evidence.extracted_data:
            text_content = evidence.extracted_data["text"]
            if isinstance(text_content, str) and len(text_content.strip()) < 10:
                result.add_warning(
                    field_path="extracted_data.text",
                    message="Text evidence seems unusually short",
                    constraint_violated="text_length_check",
                    actual_value=len(text_content),
                )

    @staticmethod
    def validate_batch(evidence_list: list[EvidenceRecord]) -> ValidationResult:
        """
        Validate a batch of evidence records.

        Args:
            evidence_list: List of evidence records to validate

        Returns:
            Aggregated ValidationResult
        """
        result = ValidationResult(is_valid=True)

        # Check for duplicate evidence IDs
        evidence_ids = [e.evidence_id for e in evidence_list]
        if len(evidence_ids) != len(set(evidence_ids)):
            duplicates = [eid for eid in evidence_ids if evidence_ids.count(eid) > 1]
            result.add_error(
                field_path="evidence_list",
                message=f"Duplicate evidence IDs found: {set(duplicates)}",
                constraint_violated="unique_evidence_ids",
            )

        # Validate each evidence record
        for idx, evidence in enumerate(evidence_list):
            evidence_result = EvidenceValidator.validate(evidence)
            if not evidence_result.is_valid:
                for error in evidence_result.errors:
                    result.add_error(
                        field_path=f"evidence_list[{idx}].{error.field_path}",
                        message=error.message,
                        constraint_violated=error.constraint_violated,
                        actual_value=error.actual_value,
                    )
            for warning in evidence_result.warnings:
                result.add_warning(
                    field_path=f"evidence_list[{idx}].{warning.field_path}",
                    message=warning.message,
                    constraint_violated=warning.constraint_violated,
                    actual_value=warning.actual_value,
                )

        return result

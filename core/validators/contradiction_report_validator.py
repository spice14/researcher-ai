"""Validator for ContradictionReport schema."""

from core.schemas.contradiction_report import ContradictionReport
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ContradictionReportValidator(SchemaValidator):
    """Validate contradiction and consensus reports."""

    @staticmethod
    def validate(report: ContradictionReport) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ContradictionReportValidator.validate_non_empty_string(report.report_id, "report_id", result)
        ContradictionReportValidator.validate_non_empty_string(report.claim_cluster_id, "claim_cluster_id", result)
        ContradictionReportValidator.validate_id_format(
            report.report_id,
            "report_id",
            result,
            allowed_prefixes=["report_"],
        )

        if not report.consensus_claims and not report.contradiction_pairs and not report.uncertainty_markers:
            result.add_error(
                field_path="report",
                message="ContradictionReport must contain consensus claims, contradiction pairs, or uncertainty markers",
                constraint_violated="report_non_empty",
            )

        return result
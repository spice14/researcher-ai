"""Validator for ExperimentalContext schema."""

from core.schemas.experimental_context import ExperimentalContext
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ExperimentalContextValidator(SchemaValidator):
    """Validate experimental context consistency and comparability metadata."""

    @staticmethod
    def validate(context: ExperimentalContext) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ExperimentalContextValidator.validate_non_empty_string(context.context_id, "context_id", result)
        ExperimentalContextValidator.validate_non_empty_string(context.dataset, "dataset", result)
        ExperimentalContextValidator.validate_id_format(
            context.context_id,
            "context_id",
            result,
            allowed_prefixes=["ctx_"],
        )

        if context.metric.range_min is not None and context.metric.range_max is not None:
            if context.metric.range_min >= context.metric.range_max:
                result.add_error(
                    field_path="metric.range",
                    message="metric.range_min must be smaller than metric.range_max",
                    constraint_violated="metric_range_order",
                )

        if context.evaluation_protocol.cross_validation_folds and context.evaluation_protocol.split_type == "train/test":
            result.add_warning(
                field_path="evaluation_protocol.cross_validation_folds",
                message="cross_validation_folds is unusual for a train/test split",
                constraint_violated="protocol_consistency",
            )

        return result
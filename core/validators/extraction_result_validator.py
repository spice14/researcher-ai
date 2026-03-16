"""Validator for ExtractionResult schema."""

from core.schemas.extraction_result import ArtifactType, ExtractionResult
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ExtractionResultValidator(SchemaValidator):
    """Validate multimodal extraction outputs."""

    @staticmethod
    def validate(result_model: ExtractionResult) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ExtractionResultValidator.validate_non_empty_string(result_model.result_id, "result_id", result)
        ExtractionResultValidator.validate_non_empty_string(result_model.paper_id, "paper_id", result)
        ExtractionResultValidator.validate_id_format(result_model.result_id, "result_id", result, allowed_prefixes=["extract_"])

        if result_model.provenance.page != result_model.page_number:
            result.add_warning(
                field_path="provenance.page",
                message="provenance.page should usually match page_number",
                constraint_violated="extraction_page_alignment",
            )

        if result_model.artifact_type in {ArtifactType.TABLE, ArtifactType.FIGURE} and not result_model.caption:
            result.add_warning(
                field_path="caption",
                message="Table and figure extraction results should include captions when available",
                constraint_violated="artifact_caption_recommended",
            )

        if not result_model.normalized_data:
            result.add_warning(
                field_path="normalized_data",
                message="ExtractionResult has no normalized_data payload",
                constraint_violated="normalized_data_recommended",
            )

        return result
"""Validator for Paper schema."""

from core.schemas.paper import Paper
from core.validators.schema_validator import SchemaValidator, ValidationResult


class PaperValidator(SchemaValidator):
    """Validate ingested paper metadata."""

    @staticmethod
    def validate(paper: Paper) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        PaperValidator.validate_non_empty_string(paper.paper_id, "paper_id", result)
        PaperValidator.validate_non_empty_string(paper.title, "title", result)
        PaperValidator.validate_non_empty_string(paper.pdf_path, "pdf_path", result)
        PaperValidator.validate_id_format(paper.paper_id, "paper_id", result, allowed_prefixes=["paper_"])

        if not paper.abstract and not paper.doi and not paper.arxiv_id:
            result.add_warning(
                field_path="paper",
                message="Paper should include at least one of abstract, doi, or arxiv_id",
                constraint_violated="paper_metadata_completeness",
            )

        if len(paper.chunk_ids) != len(set(paper.chunk_ids)):
            result.add_error(
                field_path="chunk_ids",
                message="chunk_ids must be unique within a paper",
                constraint_violated="unique_chunk_ids",
            )

        return result
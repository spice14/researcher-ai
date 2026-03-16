"""Validator for Chunk schema."""

from core.schemas.chunk import Chunk
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ChunkValidator(SchemaValidator):
    """Validate retrievable chunk payloads."""

    @staticmethod
    def validate(chunk: Chunk) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ChunkValidator.validate_non_empty_string(chunk.chunk_id, "chunk_id", result)
        ChunkValidator.validate_non_empty_string(chunk.paper_id, "paper_id", result)
        ChunkValidator.validate_non_empty_string(chunk.text, "text", result)
        ChunkValidator.validate_non_empty_string(chunk.embedding_id, "embedding_id", result)
        ChunkValidator.validate_id_format(chunk.chunk_id, "chunk_id", result, allowed_prefixes=["chunk_"])

        if len(chunk.text.strip()) < 10:
            result.add_warning(
                field_path="text",
                message="Chunk text is unusually short for retrieval",
                constraint_violated="chunk_text_length",
                actual_value=len(chunk.text.strip()),
            )

        return result
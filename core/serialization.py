"""
Serialization and deserialization utilities for Researcher-AI schemas.

Provides deterministic, validated serialization to/from JSON and other formats.
All serialization preserves full schema validation.
"""

import json
from typing import Dict, Any, Type, TypeVar, List
from pathlib import Path
from pydantic import BaseModel, ValidationError

from core.schemas.evidence import EvidenceRecord
from core.schemas.claim import Claim
from core.schemas.hypothesis import Hypothesis

T = TypeVar("T", bound=BaseModel)


class SerializationError(Exception):
    """Raised when serialization or deserialization fails."""

    pass


class SchemaSerializer:
    """
    Handles serialization and deserialization of schema objects.

    All operations are deterministic and preserve validation.
    """

    @staticmethod
    def to_json(schema_obj: BaseModel, pretty: bool = False) -> str:
        """
        Serialize a schema object to JSON string.

        Args:
            schema_obj: The schema object to serialize
            pretty: Whether to format with indentation

        Returns:
            JSON string representation

        Raises:
            SerializationError: If serialization fails
        """
        try:
            if pretty:
                return schema_obj.model_dump_json(indent=2, exclude_none=False)
            return schema_obj.model_dump_json(exclude_none=False)
        except Exception as e:
            raise SerializationError(f"Failed to serialize to JSON: {e}") from e

    @staticmethod
    def from_json(json_str: str, schema_class: Type[T]) -> T:
        """
        Deserialize JSON string to schema object.

        Args:
            json_str: JSON string to deserialize
            schema_class: The schema class to deserialize into

        Returns:
            Validated schema object

        Raises:
            SerializationError: If deserialization or validation fails
        """
        try:
            return schema_class.model_validate_json(json_str)
        except ValidationError as e:
            raise SerializationError(f"Validation failed during deserialization: {e}") from e
        except Exception as e:
            raise SerializationError(f"Failed to deserialize from JSON: {e}") from e

    @staticmethod
    def to_dict(schema_obj: BaseModel) -> Dict[str, Any]:
        """
        Convert schema object to dictionary.

        Args:
            schema_obj: The schema object to convert

        Returns:
            Dictionary representation
        """
        return schema_obj.model_dump(exclude_none=False, mode="python")

    @staticmethod
    def from_dict(data: Dict[str, Any], schema_class: Type[T]) -> T:
        """
        Create schema object from dictionary.

        Args:
            data: Dictionary containing schema data
            schema_class: The schema class to instantiate

        Returns:
            Validated schema object

        Raises:
            SerializationError: If validation fails
        """
        try:
            return schema_class.model_validate(data)
        except ValidationError as e:
            raise SerializationError(f"Validation failed during dict conversion: {e}") from e
        except Exception as e:
            raise SerializationError(f"Failed to create from dict: {e}") from e

    @staticmethod
    def to_file(schema_obj: BaseModel, file_path: Path, pretty: bool = True) -> None:
        """
        Save schema object to JSON file.

        Args:
            schema_obj: The schema object to save
            file_path: Path to the output file
            pretty: Whether to format with indentation

        Raises:
            SerializationError: If file writing fails
        """
        try:
            json_str = SchemaSerializer.to_json(schema_obj, pretty=pretty)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(json_str, encoding="utf-8")
        except Exception as e:
            raise SerializationError(f"Failed to write to file {file_path}: {e}") from e

    @staticmethod
    def from_file(file_path: Path, schema_class: Type[T]) -> T:
        """
        Load schema object from JSON file.

        Args:
            file_path: Path to the JSON file
            schema_class: The schema class to deserialize into

        Returns:
            Validated schema object

        Raises:
            SerializationError: If file reading or validation fails
        """
        try:
            json_str = file_path.read_text(encoding="utf-8")
            return SchemaSerializer.from_json(json_str, schema_class)
        except Exception as e:
            raise SerializationError(f"Failed to read from file {file_path}: {e}") from e

    @staticmethod
    def batch_to_json(schema_objs: List[BaseModel], pretty: bool = False) -> str:
        """
        Serialize a list of schema objects to JSON array.

        Args:
            schema_objs: List of schema objects
            pretty: Whether to format with indentation

        Returns:
            JSON array string

        Raises:
            SerializationError: If serialization fails
        """
        try:
            data = [obj.model_dump(exclude_none=False, mode="python") for obj in schema_objs]
            if pretty:
                return json.dumps(data, indent=2, ensure_ascii=False)
            return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            raise SerializationError(f"Failed to serialize batch to JSON: {e}") from e

    @staticmethod
    def batch_from_json(json_str: str, schema_class: Type[T]) -> List[T]:
        """
        Deserialize JSON array to list of schema objects.

        Args:
            json_str: JSON array string
            schema_class: The schema class to deserialize into

        Returns:
            List of validated schema objects

        Raises:
            SerializationError: If deserialization or validation fails
        """
        try:
            data = json.loads(json_str)
            if not isinstance(data, list):
                raise ValueError("JSON must be an array")
            return [schema_class.model_validate(item) for item in data]
        except ValidationError as e:
            raise SerializationError(f"Validation failed during batch deserialization: {e}") from e
        except Exception as e:
            raise SerializationError(f"Failed to deserialize batch from JSON: {e}") from e

    @staticmethod
    def get_json_schema(schema_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        Get JSON Schema definition for a schema class.

        Args:
            schema_class: The schema class

        Returns:
            JSON Schema dictionary
        """
        return schema_class.model_json_schema()


# Convenience functions for common schema types
def serialize_evidence(evidence: EvidenceRecord, pretty: bool = False) -> str:
    """Serialize EvidenceRecord to JSON."""
    return SchemaSerializer.to_json(evidence, pretty=pretty)


def deserialize_evidence(json_str: str) -> EvidenceRecord:
    """Deserialize JSON to EvidenceRecord."""
    return SchemaSerializer.from_json(json_str, EvidenceRecord)


def serialize_claim(claim: Claim, pretty: bool = False) -> str:
    """Serialize Claim to JSON."""
    return SchemaSerializer.to_json(claim, pretty=pretty)


def deserialize_claim(json_str: str) -> Claim:
    """Deserialize JSON to Claim."""
    return SchemaSerializer.from_json(json_str, Claim)


def serialize_hypothesis(hypothesis: Hypothesis, pretty: bool = False) -> str:
    """Serialize Hypothesis to JSON."""
    return SchemaSerializer.to_json(hypothesis, pretty=pretty)


def deserialize_hypothesis(json_str: str) -> Hypothesis:
    """Deserialize JSON to Hypothesis."""
    return SchemaSerializer.from_json(json_str, Hypothesis)

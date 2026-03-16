"""Validator for ClusterMap schema."""

from core.schemas.cluster_map import ClusterMap
from core.validators.schema_validator import SchemaValidator, ValidationResult


class ClusterMapValidator(SchemaValidator):
    """Validate structured literature maps."""

    @staticmethod
    def validate(cluster_map: ClusterMap) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        ClusterMapValidator.validate_non_empty_string(cluster_map.map_id, "map_id", result)
        ClusterMapValidator.validate_id_format(cluster_map.map_id, "map_id", result, allowed_prefixes=["map_"])

        if not cluster_map.clusters:
            result.add_error(
                field_path="clusters",
                message="ClusterMap must include at least one cluster",
                constraint_violated="cluster_map_non_empty",
            )
            return result

        cluster_ids = [cluster.cluster_id for cluster in cluster_map.clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            result.add_error(
                field_path="clusters",
                message="cluster_id values must be unique within a ClusterMap",
                constraint_violated="unique_cluster_ids",
            )

        for index, cluster in enumerate(cluster_map.clusters):
            if not cluster.representative_paper_ids:
                result.add_error(
                    field_path=f"clusters[{index}].representative_paper_ids",
                    message="Each cluster must have at least one representative paper",
                    constraint_violated="cluster_representative_required",
                )
            if not cluster.centroid_embedding:
                result.add_error(
                    field_path=f"clusters[{index}].centroid_embedding",
                    message="Each cluster must include a centroid embedding",
                    constraint_violated="cluster_centroid_required",
                )

        if not cluster_map.provenance:
            result.add_warning(
                field_path="provenance",
                message="ClusterMap should include provenance snippets for interpretability",
                constraint_violated="cluster_map_provenance",
            )

        return result
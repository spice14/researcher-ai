"""
Hypothesis validator.

Validates Hypothesis schemas for scientific rigor, completeness, and
evidence grounding.
"""

from typing import List
from core.schemas.hypothesis import Hypothesis
from core.validators.schema_validator import SchemaValidator, ValidationResult


class HypothesisValidator(SchemaValidator):
    """
    Validates Hypothesis instances.

    Enforces:
    - No hypothesis without explicit assumptions
    - Variables must be clearly defined
    - Evidence balance must be considered
    - Novelty must be explicitly justified
    - Revision history must be sequential
    """

    @staticmethod
    def validate(hypothesis: Hypothesis) -> ValidationResult:
        """
        Validate a Hypothesis.

        Args:
            hypothesis: The hypothesis to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Validate ID
        HypothesisValidator.validate_non_empty_string(
            hypothesis.hypothesis_id,
            "hypothesis_id",
            result,
        )
        HypothesisValidator.validate_id_format(
            hypothesis.hypothesis_id,
            "hypothesis_id",
            result,
            allowed_prefixes=["hyp_"],
        )

        # Validate required fields
        HypothesisValidator._validate_required_fields(hypothesis, result)

        # Validate assumptions
        HypothesisValidator._validate_assumptions(hypothesis, result)

        # Validate variables
        HypothesisValidator._validate_variables(hypothesis, result)

        # Validate evidence balance
        HypothesisValidator._validate_evidence_balance(hypothesis, result)

        # Validate novelty justification
        HypothesisValidator._validate_novelty(hypothesis, result)

        # Validate revision history
        HypothesisValidator._validate_revision_history(hypothesis, result)

        # Validate boundary conditions
        HypothesisValidator._validate_boundary_conditions(hypothesis, result)

        return result

    @staticmethod
    def _validate_required_fields(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """Validate that all required fields are meaningful."""
        HypothesisValidator.validate_non_empty_string(
            hypothesis.statement,
            "statement",
            result,
        )
        HypothesisValidator.validate_non_empty_string(
            hypothesis.novelty_basis,
            "novelty_basis",
            result,
        )

        # Statement should be substantial
        if len(hypothesis.statement.strip()) < 20:
            result.add_warning(
                field_path="statement",
                message="Hypothesis statement seems too short for a meaningful proposition",
                constraint_violated="statement_length",
                actual_value=len(hypothesis.statement),
            )

    @staticmethod
    def _validate_assumptions(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate that assumptions are explicit and non-empty.

        No hypothesis without assumptions is acceptable.
        """
        if not hypothesis.assumptions:
            result.add_error(
                field_path="assumptions",
                message="Hypothesis must have at least one explicit assumption",
                constraint_violated="no_hypothesis_without_assumptions",
            )
            return

        # Validate each assumption is meaningful
        for idx, assumption in enumerate(hypothesis.assumptions):
            if len(assumption.strip()) < 5:
                result.add_error(
                    field_path=f"assumptions[{idx}]",
                    message="Assumptions must be meaningful statements",
                    constraint_violated="assumption_quality",
                    actual_value=assumption,
                )

    @staticmethod
    def _validate_variables(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate that variables are clearly defined.
        """
        if not hypothesis.independent_variables:
            result.add_error(
                field_path="independent_variables",
                message="Hypothesis must declare at least one independent variable",
                constraint_violated="variables_required",
            )

        if not hypothesis.dependent_variables:
            result.add_error(
                field_path="dependent_variables",
                message="Hypothesis must declare at least one dependent variable",
                constraint_violated="variables_required",
            )

        # Check for overlap between independent and dependent variables
        iv_set = {v.lower().strip() for v in hypothesis.independent_variables}
        dv_set = {v.lower().strip() for v in hypothesis.dependent_variables}

        overlap = iv_set.intersection(dv_set)
        if overlap:
            result.add_error(
                field_path="variables",
                message=f"Variables cannot be both independent and dependent: {overlap}",
                constraint_violated="variable_independence",
            )

        # Validate each variable is meaningful
        for idx, var in enumerate(hypothesis.independent_variables):
            if len(var.strip()) < 2:
                result.add_error(
                    field_path=f"independent_variables[{idx}]",
                    message="Variable names must be meaningful",
                    constraint_violated="variable_quality",
                    actual_value=var,
                )

        for idx, var in enumerate(hypothesis.dependent_variables):
            if len(var.strip()) < 2:
                result.add_error(
                    field_path=f"dependent_variables[{idx}]",
                    message="Variable names must be meaningful",
                    constraint_violated="variable_quality",
                    actual_value=var,
                )

    @staticmethod
    def _validate_evidence_balance(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate evidence balance and confidence alignment.
        """
        balance = hypothesis.get_evidence_balance()

        # Warning if no evidence at all
        if balance["total_evidence"] == 0:
            result.add_warning(
                field_path="evidence",
                message="Hypothesis has no supporting or contradicting claims",
                constraint_violated="evidence_required",
            )
            return

        # High confidence requires evidence support
        if hypothesis.qualitative_confidence.value == "high":
            if balance["support_ratio"] < 0.7:
                result.add_warning(
                    field_path="qualitative_confidence",
                    message=f"High confidence with support ratio {balance['support_ratio']:.2f}. "
                    "Consider lowering confidence or addressing contradictions.",
                    constraint_violated="confidence_evidence_alignment",
                )

            if balance["supporting_count"] < 2:
                result.add_warning(
                    field_path="qualitative_confidence",
                    message="High confidence should be backed by multiple supporting claims",
                    constraint_violated="confidence_evidence_count",
                )

        # Contradicting claims should be acknowledged
        if balance["contradicting_count"] > 0 and hypothesis.qualitative_confidence.value == "high":
            result.add_warning(
                field_path="contradicting_claims",
                message=f"Hypothesis has {balance['contradicting_count']} contradicting claim(s) "
                "but maintains high confidence. Ensure contradictions are addressed.",
                constraint_violated="contradictions_acknowledged",
            )

    @staticmethod
    def _validate_novelty(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate that novelty is explicitly justified.
        """
        if len(hypothesis.novelty_basis.strip()) < 20:
            result.add_warning(
                field_path="novelty_basis",
                message="Novelty justification seems insufficient",
                constraint_violated="novelty_justification",
                actual_value=len(hypothesis.novelty_basis),
            )

        # Check if novelty basis actually explains novelty
        novelty_keywords = {
            "new",
            "novel",
            "first",
            "unprecedented",
            "unexplored",
            "gap",
            "missing",
            "lacks",
        }
        novelty_lower = hypothesis.novelty_basis.lower()
        has_novelty_indicator = any(keyword in novelty_lower for keyword in novelty_keywords)

        if not has_novelty_indicator:
            result.add_warning(
                field_path="novelty_basis",
                message="Novelty basis should explicitly state what is new or unexplored",
                constraint_violated="novelty_clarity",
            )

    @staticmethod
    def _validate_revision_history(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate that revision history is properly maintained.
        """
        if not hypothesis.revision_history:
            # No revisions is acceptable for initial hypotheses
            return

        # Revisions should be sequential
        for idx, revision in enumerate(hypothesis.revision_history):
            expected_iteration = idx + 1
            if revision.iteration != expected_iteration:
                result.add_error(
                    field_path=f"revision_history[{idx}].iteration",
                    message=f"Expected iteration {expected_iteration}, got {revision.iteration}",
                    constraint_violated="revision_history_sequential",
                )

            # Validate revision content
            if len(revision.changes.strip()) < 10:
                result.add_warning(
                    field_path=f"revision_history[{idx}].changes",
                    message="Revision changes should be descriptive",
                    constraint_violated="revision_quality",
                )

            if len(revision.rationale.strip()) < 10:
                result.add_warning(
                    field_path=f"revision_history[{idx}].rationale",
                    message="Revision rationale should be descriptive",
                    constraint_violated="revision_quality",
                )

    @staticmethod
    def _validate_boundary_conditions(hypothesis: Hypothesis, result: ValidationResult) -> None:
        """
        Validate boundary conditions when applicable.
        """
        if not hypothesis.boundary_conditions:
            result.add_warning(
                field_path="boundary_conditions",
                message="Consider specifying boundary conditions to define hypothesis scope",
                constraint_violated="boundary_conditions_recommended",
            )
            return

        # Validate each boundary condition is meaningful
        for idx, condition in enumerate(hypothesis.boundary_conditions):
            if len(condition.strip()) < 5:
                result.add_warning(
                    field_path=f"boundary_conditions[{idx}]",
                    message="Boundary conditions should be meaningful",
                    constraint_violated="boundary_condition_quality",
                    actual_value=condition,
                )

    @staticmethod
    def validate_batch(hypotheses: List[Hypothesis]) -> ValidationResult:
        """
        Validate a batch of hypotheses.

        Args:
            hypotheses: List of hypotheses to validate

        Returns:
            Aggregated ValidationResult
        """
        result = ValidationResult(is_valid=True)

        # Check for duplicate hypothesis IDs
        hypothesis_ids = [h.hypothesis_id for h in hypotheses]
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            duplicates = [hid for hid in hypothesis_ids if hypothesis_ids.count(hid) > 1]
            result.add_error(
                field_path="hypotheses",
                message=f"Duplicate hypothesis IDs found: {set(duplicates)}",
                constraint_violated="unique_hypothesis_ids",
            )

        # Validate each hypothesis
        for idx, hypothesis in enumerate(hypotheses):
            hyp_result = HypothesisValidator.validate(hypothesis)
            if not hyp_result.is_valid:
                for error in hyp_result.errors:
                    result.add_error(
                        field_path=f"hypotheses[{idx}].{error.field_path}",
                        message=error.message,
                        constraint_violated=error.constraint_violated,
                        actual_value=error.actual_value,
                    )
            for warning in hyp_result.warnings:
                result.add_warning(
                    field_path=f"hypotheses[{idx}].{warning.field_path}",
                    message=warning.message,
                    constraint_violated=warning.constraint_violated,
                    actual_value=warning.actual_value,
                )

        return result

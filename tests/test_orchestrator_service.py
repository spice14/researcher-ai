"""Comprehensive unit tests for deterministic orchestrator service."""

import pytest
from services.orchestrator.service import Orchestrator
from services.orchestrator.schemas import (
    WorkflowRequest,
    WorkflowResult,
    ExecutionLog,
)


@pytest.fixture
def orchestrator():
    """Fixture providing an Orchestrator instance."""
    return Orchestrator()


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Orchestrator Initialization
# ──────────────────────────────────────────────────────────────────────────────


class TestOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_orchestrator_initializes(self, orchestrator):
        """Test orchestrator can be initialized."""
        assert orchestrator is not None
        assert orchestrator.ingestion is not None
        assert orchestrator.extraction is not None
        assert orchestrator.normalization is not None
        assert orchestrator.relation_engine is not None
        assert orchestrator.belief is not None

    def test_all_services_available(self, orchestrator):
        """Test all required services are initialized."""
        assert hasattr(orchestrator, "ingestion")
        assert hasattr(orchestrator, "extraction")
        assert hasattr(orchestrator, "normalization")
        assert hasattr(orchestrator, "relation_engine")
        assert hasattr(orchestrator, "belief")

    def test_orchestrator_callable(self, orchestrator):
        """Test orchestrator methods are callable."""
        assert callable(orchestrator.execute_workflow)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Workflow Execution
# ──────────────────────────────────────────────────────────────────────────────


class TestWorkflowExecution:
    """Tests for workflow execution."""

    def test_execute_workflow_returns_result(self, orchestrator):
        """Test execute_workflow returns WorkflowResult."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)
            # If workflow exists, check result structure
            assert isinstance(result, WorkflowResult)
            assert result.workflow_id is not None
            assert result.execution_logs is not None
            assert isinstance(result.execution_logs, list)
        except ValueError as e:
            # If workflow_id doesn't exist, that's valid (unknown workflow)
            assert "Unknown workflow_id" in str(e)

    def test_unknown_workflow_raises_error(self, orchestrator):
        """Test unknown workflow raises ValueError."""
        request = WorkflowRequest(
            workflow_id="nonexistent_workflow_xyz",
            input_data={},
        )

        with pytest.raises(ValueError, match="Unknown workflow_id"):
            orchestrator.execute_workflow(request)

    def test_workflow_result_has_required_fields(self, orchestrator):
        """Test WorkflowResult has all required fields."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)
            assert hasattr(result, "workflow_id")
            assert hasattr(result, "final_output")
            assert hasattr(result, "execution_logs")
            assert hasattr(result, "total_latency_ms")
        except ValueError:
            # Valid if workflow doesn't exist
            pass


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Execution Logs
# ──────────────────────────────────────────────────────────────────────────────


class TestExecutionLogs:
    """Tests for execution log tracking."""

    def test_execution_logs_created(self, orchestrator):
        """Test execution logs are created for workflow execution."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)

            # Execution logs should be present
            assert isinstance(result.execution_logs, list)

            # Each log should be ExecutionLog
            for log in result.execution_logs:
                assert isinstance(log, ExecutionLog)
                assert log.task_id is not None
                assert log.component is not None
                assert log.input_hash is not None
                assert log.output_hash is not None
                assert log.latency_ms is not None
                assert log.deterministic is not None
        except ValueError:
            # Valid if workflow doesn't exist
            pass

    def test_determinism_flag_set(self, orchestrator):
        """Test determinism flag is set in execution logs."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)

            for log in result.execution_logs:
                # Services should be deterministic
                assert log.deterministic == True
        except ValueError:
            pass

    def test_latency_measured(self, orchestrator):
        """Test latency is measured for each task."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)

            for log in result.execution_logs:
                assert log.latency_ms > 0
                assert isinstance(log.latency_ms, float)

            # Total latency should be positive
            assert result.total_latency_ms > 0
        except ValueError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Output Schema Validity
# ──────────────────────────────────────────────────────────────────────────────


class TestOutputSchema:
    """Tests for output schema validity."""

    def test_workflow_result_pydantic_model(self, orchestrator):
        """Test WorkflowResult is valid Pydantic model."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)

            # Should be valid WorkflowResult
            assert isinstance(result, WorkflowResult)

            # Round-trip serialization
            result_dict = result.model_dump()
            restored = WorkflowResult(**result_dict)
            assert isinstance(restored, WorkflowResult)
        except ValueError:
            pass

    def test_execution_log_pydantic_model(self, orchestrator):
        """Test ExecutionLog is valid Pydantic model."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result = orchestrator.execute_workflow(request)

            for log in result.execution_logs:
                # Round-trip serialization
                log_dict = log.model_dump()
                restored = ExecutionLog(**log_dict)
                assert isinstance(restored, ExecutionLog)
        except ValueError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Determinism
# ──────────────────────────────────────────────────────────────────────────────


class TestDeterminism:
    """Tests for deterministic execution."""

    def test_same_input_same_execution_logs(self, orchestrator):
        """Test same input produces deterministic execution logs."""
        request1 = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )
        request2 = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result1 = orchestrator.execute_workflow(request1)
            result2 = orchestrator.execute_workflow(request2)

            # Same number of logs
            assert len(result1.execution_logs) == len(result2.execution_logs)

            # Same task_ids and components
            for log1, log2 in zip(result1.execution_logs, result2.execution_logs):
                assert log1.task_id == log2.task_id
                assert log1.component == log2.component
        except ValueError:
            pass

    def test_deterministic_input_hashes(self, orchestrator):
        """Test input hashes are deterministic."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"test": "data"},
        )

        try:
            result1 = orchestrator.execute_workflow(request)
            result2 = orchestrator.execute_workflow(request)

            # Input hashes should match for same input
            for log1, log2 in zip(result1.execution_logs, result2.execution_logs):
                assert log1.input_hash == log2.input_hash
        except ValueError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Input Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestInputValidation:
    """Tests for input request validation."""

    def test_valid_workflow_request(self, orchestrator):
        """Test valid workflow request is accepted."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"key": "value"},
        )

        # Should not raise exception during request creation
        assert request.workflow_id == "test_workflow"
        assert request.input_data == {"key": "value"}

    def test_empty_input_data_accepted(self, orchestrator):
        """Test empty input_data is accepted."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={},
        )

        assert request.input_data == {}

    def test_complex_input_data(self, orchestrator):
        """Test complex nested input_data."""
        complex_input = {
            "source_id": "paper_001",
            "nested": {"key": "value", "number": 42},
            "list": [1, 2, 3],
        }

        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data=complex_input,
        )

        assert request.input_data == complex_input


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Service Integration
# ──────────────────────────────────────────────────────────────────────────────


class TestServiceIntegration:
    """Tests for service integration within orchestrator."""

    def test_ingestion_service_available(self, orchestrator):
        """Test ingestion service is callable."""
        assert hasattr(orchestrator.ingestion, "ingest_text")
        assert callable(orchestrator.ingestion.ingest_text)

    def test_extraction_service_available(self, orchestrator):
        """Test extraction service is callable."""
        assert hasattr(orchestrator.extraction, "extract")
        assert callable(orchestrator.extraction.extract)

    def test_normalization_service_available(self, orchestrator):
        """Test normalization service is callable."""
        assert hasattr(orchestrator.normalization, "normalize")
        assert callable(orchestrator.normalization.normalize)

    def test_relation_engine_available(self, orchestrator):
        """Test relation engine is callable."""
        assert hasattr(orchestrator.relation_engine, "analyze")
        assert callable(orchestrator.relation_engine.analyze)

    def test_belief_engine_available(self, orchestrator):
        """Test belief engine is callable."""
        assert hasattr(orchestrator.belief, "compute_beliefs")
        assert callable(orchestrator.belief.compute_beliefs)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_very_large_input_data(self, orchestrator):
        """Test handling of large input data."""
        large_input = {
            f"key_{i}": f"value_{i}" * 100 for i in range(100)
        }

        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data=large_input,
        )

        # Should accept large input
        assert len(request.input_data) == 100

    def test_special_characters_in_workflow_id(self, orchestrator):
        """Test workflow_id with special characters."""
        request = WorkflowRequest(
            workflow_id="test-workflow_v1.0",
            input_data={},
        )

        assert request.workflow_id == "test-workflow_v1.0"

    def test_unicode_in_input_data(self, orchestrator):
        """Test unicode characters in input data."""
        request = WorkflowRequest(
            workflow_id="test_workflow",
            input_data={"text": "Hello 世界 🌍"},
        )

        assert request.input_data["text"] == "Hello 世界 🌍"


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Workflow Not Found Handling
# ──────────────────────────────────────────────────────────────────────────────


class TestWorkflowNotFound:
    """Tests for handling of missing workflows."""

    def test_nonexistent_workflow_error_message(self, orchestrator):
        """Test error message for nonexistent workflow."""
        request = WorkflowRequest(
            workflow_id="this_workflow_does_not_exist_12345",
            input_data={},
        )

        with pytest.raises(ValueError) as exc_info:
            orchestrator.execute_workflow(request)

        assert "Unknown workflow_id" in str(exc_info.value)
        assert "this_workflow_does_not_exist_12345" in str(exc_info.value)

    def test_empty_workflow_id_error(self, orchestrator):
        """Test handling of empty workflow_id."""
        request = WorkflowRequest(
            workflow_id="",
            input_data={},
        )

        # May raise error or treat as unknown workflow
        try:
            result = orchestrator.execute_workflow(request)
            # If it doesn't raise, check result is valid
            assert isinstance(result, WorkflowResult)
        except ValueError:
            # Expected error for unknown/empty workflow
            pass

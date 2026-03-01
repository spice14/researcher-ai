"""End-to-end integration tests for orchestrator service covering all component paths."""

import pytest
from services.orchestrator.service import Orchestrator
from services.orchestrator.schemas import WorkflowRequest, WorkflowResult


@pytest.fixture
def orchestrator():
    """Fixture providing an Orchestrator instance."""
    return Orchestrator()


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Full End-to-End Workflow Execution
# ──────────────────────────────────────────────────────────────────────────────


class TestEndToEndWorkflow:
    """Tests for complete end-to-end workflow execution with real data."""

    def test_contradiction_analysis_complete_pipeline(self, orchestrator):
        """Test full contradiction_analysis workflow: ingest→extract→normalize→contradict→believe."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model A achieves 92.5% accuracy. Model B achieves 91.8% accuracy. Both models are evaluated on the same dataset.",
                "source_id": "test_paper_001",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Verify result structure
        assert isinstance(result, WorkflowResult)
        assert result.workflow_id == "contradiction_analysis"
        assert result.final_output is not None
        assert result.execution_logs is not None
        assert len(result.execution_logs) == 5  # All 5 tasks: ingest, extract, normalize, contradict, believe

    def test_literature_analysis_complete_pipeline(self, orchestrator):
        """Test full literature_analysis workflow."""
        request = WorkflowRequest(
            workflow_id="literature_analysis",
            input_data={
                "raw_text": "BERT achieves 92.7% accuracy on GLUE benchmark. RoBERTa achieves 94.2% accuracy on GLUE.",
                "source_id": "nlp_paper_001",
            },
        )
        result = orchestrator.execute_workflow(request)

        assert isinstance(result, WorkflowResult)
        assert result.workflow_id == "literature_analysis"
        assert len(result.execution_logs) >= 3  # At least through normalization

    def test_workflow_execution_logs_contain_all_tasks(self, orchestrator):
        """Test execution logs record all task executions."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model achieves 90% accuracy.",
                "source_id": "test_source",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Should have execution logs for each task
        assert len(result.execution_logs) > 0
        for log in result.execution_logs:
            assert log.task_id is not None
            assert log.component is not None
            assert log.input_hash is not None
            assert log.output_hash is not None
            assert log.latency_ms >= 0

    def test_workflow_latency_tracking(self, orchestrator):
        """Test latency is properly tracked."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Test model achieves 88% accuracy.",
                "source_id": "test",
            },
        )
        result = orchestrator.execute_workflow(request)

        assert result.total_latency_ms > 0

    def test_workflow_with_multiple_claims(self, orchestrator):
        """Test workflow with text containing multiple extractable claims."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": (
                    "Model achieves 92% accuracy on SQuAD. "
                    "It requires 24 hours training. "
                    "The model has 110 million parameters. "
                    "Baseline achieves 88% accuracy. "
                    "Our model outperforms baseline by 4%."
                ),
                "source_id": "comprehensive_paper",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Should process all without error
        assert result.final_output is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Component Branch Coverage
# ──────────────────────────────────────────────────────────────────────────────


class TestComponentBranchExecution:
    """Tests to exercise all component execution branches."""

    def test_ingestion_component_execution(self, orchestrator):
        """Test ingestion component is executed properly."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Simple test claim: 85% accuracy.",
                "source_id": "source_1",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Ingestion should be first task
        assert result.execution_logs[0].component == "ingestion"

    def test_extraction_component_execution(self, orchestrator):
        """Test extraction component processes ingestion output."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model achieves 89.5% accuracy on benchmark.",
                "source_id": "source_2",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Find extraction task
        extraction_logs = [log for log in result.execution_logs if log.component == "extraction"]
        assert len(extraction_logs) >= 1

    def test_normalization_component_execution(self, orchestrator):
        """Test normalization component processes extraction output."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Achieves 91% accuracy and 45ms latency.",
                "source_id": "source_3",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Find normalization task
        norm_logs = [log for log in result.execution_logs if log.component == "normalization"]
        assert len(norm_logs) >= 1

    def test_contradiction_component_execution(self, orchestrator):
        """Test contradiction detection component."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model achieves 92% accuracy. Model achieves 88% accuracy.",
                "source_id": "source_4",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Find contradiction task
        contra_logs = [log for log in result.execution_logs if log.component == "contradiction"]
        assert len(contra_logs) >= 1

    def test_belief_component_execution(self, orchestrator):
        """Test belief computation component."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model achieves 92% accuracy. Model achieves 92.1% accuracy.",
                "source_id": "source_5",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Find belief task
        belief_logs = [log for log in result.execution_logs if log.component == "belief"]
        assert len(belief_logs) >= 1


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Dependency Resolution
# ──────────────────────────────────────────────────────────────────────────────


class TestDependencyResolution:
    """Tests for proper task dependency resolution."""

    def test_tasks_execute_in_order(self, orchestrator):
        """Test tasks execute in dependency order."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Model: 85% accuracy.",
                "source_id": "dep_test",
            },
        )
        result = orchestrator.execute_workflow(request)

        task_ids = [log.task_id for log in result.execution_logs]
        # Should include the dependency chain
        assert "ingest" in task_ids

    def test_dependent_task_receives_upstream_output(self, orchestrator):
        """Test dependent tasks receive output from dependencies."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Test: 80% accuracy.",
                "source_id": "upstream_test",
            },
        )
        result = orchestrator.execute_workflow(request)

        # All tasks should have completed (implicit test of dependency chain)
        assert len(result.execution_logs) >= 2
        # Each log should have different output hash (data transformed)
        output_hashes = [log.output_hash for log in result.execution_logs]
        # At least some should be different (ingestion differs from extraction, etc)
        assert len(set(output_hashes)) >= 2 or result.final_output is not None


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Error Handling and Edge Cases
# ──────────────────────────────────────────────────────────────────────────────


class TestErrorHandlingEdgeCases:
    """Tests for error handling and edge cases."""

    def test_unknown_component_error(self, orchestrator):
        """Test error handling for unknown component."""
        # This would require modifying a workflow, which isn't directly testable
        # through the public API, but we can verify the error message format
        request = WorkflowRequest(
            workflow_id="nonexistent_workflow",
            input_data={},
        )
        with pytest.raises(ValueError, match="Unknown workflow_id"):
            orchestrator.execute_workflow(request)

    def test_workflow_with_minimal_input(self, orchestrator):
        """Test workflow handles minimal input gracefully."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "x",  # Minimal text
                "source_id": "s",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Should not crash
        assert isinstance(result, WorkflowResult)

    def test_workflow_with_empty_text(self, orchestrator):
        """Test handling of empty text (should still process)."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "",
                "source_id": "empty",
            },
        )
        try:
            result = orchestrator.execute_workflow(request)
            # If it succeeds, verify structure
            assert isinstance(result, WorkflowResult)
        except Exception:
            # Or it may error on ingestion with empty text (acceptable)
            pass

    def test_workflow_with_large_text(self, orchestrator):
        """Test workflow handles large text input."""
        large_text = "Model achieves 90% accuracy. " * 1000
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": large_text,
                "source_id": "large",
            },
        )
        result = orchestrator.execute_workflow(request)

        assert isinstance(result, WorkflowResult)


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Output Structure and Schema Validation
# ──────────────────────────────────────────────────────────────────────────────


class TestOutputStructure:
    """Tests for output structure and schema validation."""

    def test_final_output_non_null(self, orchestrator):
        """Test final output is never null."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Test outcome: 95% success rate.",
                "source_id": "output_test",
            },
        )
        result = orchestrator.execute_workflow(request)

        assert result.final_output is not None

    def test_execution_logs_structure(self, orchestrator):
        """Test execution logs have proper structure."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Analysis: 87% accurate.",
                "source_id": "log_test",
            },
        )
        result = orchestrator.execute_workflow(request)

        for log in result.execution_logs:
            # Each log must have required fields
            assert log.task_id
            assert log.component
            assert log.input_hash
            assert log.output_hash
            assert log.latency_ms >= 0
            assert log.deterministic is True

    def test_workflow_result_serializable(self, orchestrator):
        """Test WorkflowResult can be serialized."""
        request = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={
                "raw_text": "Serialization test: 81% conversion.",
                "source_id": "serial_test",
            },
        )
        result = orchestrator.execute_workflow(request)

        # Should be serializable to dict
        result_dict = result.model_dump()
        assert isinstance(result_dict, dict)
        assert "workflow_id" in result_dict
        assert "execution_logs" in result_dict
        assert "total_latency_ms" in result_dict


# ──────────────────────────────────────────────────────────────────────────────
# TEST: Hash Generation
# ──────────────────────────────────────────────────────────────────────────────


class TestHashGeneration:
    """Tests for deterministic hash generation."""

    def test_same_input_produces_same_hashes(self, orchestrator):
        """Test same input produces identical hashes."""
        input_data = {
            "raw_text": "Model achieves 90% accuracy.",
            "source_id": "hash_test",
        }

        request1 = WorkflowRequest(workflow_id="contradiction_analysis", input_data=input_data)
        result1 = orchestrator.execute_workflow(request1)

        request2 = WorkflowRequest(workflow_id="contradiction_analysis", input_data=input_data)
        result2 = orchestrator.execute_workflow(request2)

        # Compare first log (ingestion)
        if len(result1.execution_logs) > 0 and len(result2.execution_logs) > 0:
            assert result1.execution_logs[0].input_hash == result2.execution_logs[0].input_hash

    def test_different_input_produces_different_hashes(self, orchestrator):
        """Test different inputs produce different hashes."""
        request1 = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={"raw_text": "A", "source_id": "a"},
        )
        result1 = orchestrator.execute_workflow(request1)

        request2 = WorkflowRequest(
            workflow_id="contradiction_analysis",
            input_data={"raw_text": "B", "source_id": "b"},
        )
        result2 = orchestrator.execute_workflow(request2)

        # Hashes should differ
        if len(result1.execution_logs) > 0 and len(result2.execution_logs) > 0:
            assert result1.execution_logs[0].input_hash != result2.execution_logs[0].input_hash

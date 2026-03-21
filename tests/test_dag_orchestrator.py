"""Tests for DAG orchestrator — execution, conditional branching, pause/resume."""

import pytest
from typing import Any, Dict

from core.mcp.mcp_tool import MCPTool
from core.mcp.mcp_manifest import MCPManifest
from core.mcp.registry import MCPRegistry
from services.orchestrator.dag import DAGDefinition, DAGNode
from services.orchestrator.mcp_orchestrator import MCPOrchestrator, InMemorySessionStore


class EchoTool(MCPTool):
    """Simple tool that echoes input with a tag."""

    def __init__(self, name: str, tag: str):
        self._name = name
        self._tag = tag

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name=self._name,
            version="1.0.0",
            description=f"Echo tool for testing ({self._tag})",
            input_schema={"type": "any"},
            output_schema={"type": "any"},
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(payload)
        result[f"visited_{self._tag}"] = True
        return result


class FailTool(MCPTool):
    """Tool that always fails."""

    def manifest(self) -> MCPManifest:
        return MCPManifest(
            name="fail_tool",
            version="1.0.0",
            description="Tool that always fails for testing",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )

    def call(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("intentional failure")


def _make_registry(*tools):
    reg = MCPRegistry()
    for t in tools:
        reg.register(t)
    return reg


class TestDAGDefinition:
    """DAG structure and validation tests."""

    def test_topological_sort_linear(self):
        dag = DAGDefinition(dag_id="test")
        dag.add_node(DAGNode(task_id="a", tool="tool_a"))
        dag.add_node(DAGNode(task_id="b", tool="tool_b", depends_on=["a"]))
        dag.add_node(DAGNode(task_id="c", tool="tool_c", depends_on=["b"]))

        order = dag.topological_sort()
        assert order == ["a", "b", "c"]

    def test_topological_sort_diamond(self):
        dag = DAGDefinition(dag_id="diamond")
        dag.add_node(DAGNode(task_id="root", tool="t"))
        dag.add_node(DAGNode(task_id="left", tool="t", depends_on=["root"]))
        dag.add_node(DAGNode(task_id="right", tool="t", depends_on=["root"]))
        dag.add_node(DAGNode(task_id="merge", tool="t", depends_on=["left", "right"]))

        order = dag.topological_sort()
        assert order[0] == "root"
        assert order[-1] == "merge"
        assert set(order[1:3]) == {"left", "right"}

    def test_cycle_detection(self):
        dag = DAGDefinition(dag_id="cyclic")
        dag.add_node(DAGNode(task_id="a", tool="t", depends_on=["b"]))
        dag.add_node(DAGNode(task_id="b", tool="t", depends_on=["a"]))

        errors = dag.validate()
        assert any("cycle" in e.lower() for e in errors)

    def test_missing_dependency(self):
        dag = DAGDefinition(dag_id="bad")
        dag.add_node(DAGNode(task_id="a", tool="t", depends_on=["nonexistent"]))

        errors = dag.validate()
        assert len(errors) > 0

    def test_parallel_groups(self):
        dag = DAGDefinition(dag_id="parallel")
        dag.add_node(DAGNode(task_id="root", tool="t"))
        dag.add_node(DAGNode(task_id="branch_a", tool="t", depends_on=["root"]))
        dag.add_node(DAGNode(task_id="branch_b", tool="t", depends_on=["root"]))
        dag.add_node(DAGNode(task_id="final", tool="t", depends_on=["branch_a", "branch_b"]))

        groups = dag.get_parallel_groups()
        assert len(groups) == 3
        assert groups[0] == ["root"]
        assert set(groups[1]) == {"branch_a", "branch_b"}
        assert groups[2] == ["final"]

    def test_duplicate_task_id_raises(self):
        dag = DAGDefinition(dag_id="dup")
        dag.add_node(DAGNode(task_id="a", tool="t"))
        with pytest.raises(ValueError, match="Duplicate"):
            dag.add_node(DAGNode(task_id="a", tool="t"))


class TestDAGExecution:
    """DAG execution with MCPOrchestrator."""

    def test_linear_dag_execution(self):
        reg = _make_registry(
            EchoTool("tool_a", "a"),
            EchoTool("tool_b", "b"),
            EchoTool("tool_c", "c"),
        )
        orch = MCPOrchestrator(reg, session_store=InMemorySessionStore())

        dag = DAGDefinition(dag_id="linear")
        dag.add_node(DAGNode(task_id="step1", tool="tool_a"))
        dag.add_node(DAGNode(task_id="step2", tool="tool_b", depends_on=["step1"]))
        dag.add_node(DAGNode(task_id="step3", tool="tool_c", depends_on=["step2"]))

        trace = orch.execute_dag(dag, {"input": "data"}, persist_trace=False)
        assert trace.success
        assert len(trace.entries) == 3
        assert trace.final_output.get("visited_a")
        assert trace.final_output.get("visited_c")

    def test_conditional_branch_skip(self):
        reg = _make_registry(
            EchoTool("tool_a", "a"),
            EchoTool("tool_b", "b"),
        )
        orch = MCPOrchestrator(reg, session_store=InMemorySessionStore())

        dag = DAGDefinition(dag_id="conditional")
        dag.add_node(DAGNode(task_id="step1", tool="tool_a"))
        dag.add_node(DAGNode(
            task_id="step2",
            tool="tool_b",
            depends_on=["step1"],
            condition=lambda payload: payload.get("should_run", False),
        ))

        trace = orch.execute_dag(dag, {"input": "data"}, persist_trace=False)
        assert trace.success
        # step2 should be skipped because condition is not met
        assert len(trace.entries) == 1

    def test_conditional_branch_execute(self):
        reg = _make_registry(
            EchoTool("tool_a", "a"),
            EchoTool("tool_b", "b"),
        )
        orch = MCPOrchestrator(reg, session_store=InMemorySessionStore())

        dag = DAGDefinition(dag_id="conditional")
        dag.add_node(DAGNode(task_id="step1", tool="tool_a"))
        dag.add_node(DAGNode(
            task_id="step2",
            tool="tool_b",
            depends_on=["step1"],
            condition=lambda payload: payload.get("visited_a", False),
        ))

        trace = orch.execute_dag(dag, {}, persist_trace=False)
        assert trace.success
        assert len(trace.entries) == 2

    def test_pause_and_resume(self):
        reg = _make_registry(
            EchoTool("tool_a", "a"),
            EchoTool("tool_b", "b"),
            EchoTool("tool_c", "c"),
        )
        orch = MCPOrchestrator(reg, session_store=InMemorySessionStore())

        dag = DAGDefinition(dag_id="pausable")
        dag.add_node(DAGNode(task_id="step1", tool="tool_a"))
        dag.add_node(DAGNode(task_id="step2", tool="tool_b", depends_on=["step1"]))
        dag.add_node(DAGNode(task_id="step3", tool="tool_c", depends_on=["step2"]))

        # Execute with pause at tool_b
        trace1 = orch.execute_dag(dag, {"start": True}, persist_trace=False, pause_at="tool_b")
        # Only step1 should have executed
        assert len(trace1.entries) == 1

        # Resume
        trace2 = orch.resume_pipeline()
        assert trace2 is not None
        assert trace2.success
        assert trace2.final_output.get("visited_c")

    def test_dag_error_handling(self):
        reg = _make_registry(EchoTool("tool_a", "a"), FailTool())
        orch = MCPOrchestrator(reg, session_store=InMemorySessionStore())

        dag = DAGDefinition(dag_id="failing")
        dag.add_node(DAGNode(task_id="ok", tool="tool_a"))
        dag.add_node(DAGNode(task_id="bad", tool="fail_tool", depends_on=["ok"]))

        with pytest.raises(RuntimeError, match="intentional failure"):
            orch.execute_dag(dag, {}, persist_trace=False)


class TestSemanticRAG:
    """Semantic RAG retrieval tests with mocked vector store."""

    def test_semantic_retrieval(self):
        from services.rag.service import RAGService
        from services.rag.schemas import QueryRequest
        from services.vectorstore.service import VectorStoreService
        from services.vectorstore.schemas import VectorAddRequest
        from services.embedding.service import EmbeddingService
        from services.embedding.schemas import EmbeddingRequest

        # Setup
        vs = VectorStoreService(chroma_host="x", chroma_port=9999)
        es = EmbeddingService(model_name="x", ollama_base_url="http://x:9999")

        # Add some documents
        texts = ["transformers achieve state of the art", "convolutional networks for images", "recurrent models for sequences"]
        emb_result = es.embed(EmbeddingRequest(texts=texts))

        vs.add_embeddings(VectorAddRequest(
            ids=["c1", "c2", "c3"],
            embeddings=emb_result.embeddings,
            documents=texts,
            metadatas=[
                {"source_id": "p1", "start_char": "0", "end_char": "100"},
                {"source_id": "p1", "start_char": "100", "end_char": "200"},
                {"source_id": "p2", "start_char": "0", "end_char": "100"},
            ],
        ))

        # Query
        rag = RAGService(vector_store=vs, embedding_service=es)
        result = rag.retrieve(QueryRequest(
            query="transformer models",
            corpus=[],
            top_k=2,
        ))

        assert result.retrieval_method == "semantic_chroma_v1"
        assert len(result.matches) > 0

    def test_lexical_fallback(self):
        from services.rag.service import RAGService
        from services.rag.schemas import QueryRequest
        from services.ingestion.schemas import IngestionChunk

        rag = RAGService()  # No vector store
        result = rag.retrieve(QueryRequest(
            query="transformer accuracy",
            corpus=[
                IngestionChunk(
                    chunk_id="c1", source_id="p1", text="transformer achieves 92% accuracy on GLUE",
                    start_char=0, end_char=50, text_hash="h1", context_id="ctx_glue",
                ),
            ],
            top_k=5,
        ))

        assert result.retrieval_method == "lexical_overlap_v1"
        assert len(result.matches) > 0


class TestFullAnalysisDAG:
    """Test that the FULL_ANALYSIS DAG is well-formed."""

    def test_full_analysis_dag_validates(self):
        from services.orchestrator.workflows import FULL_ANALYSIS_DAG
        errors = FULL_ANALYSIS_DAG.validate()
        assert errors == [], f"DAG validation errors: {errors}"

    def test_full_analysis_dag_topological_sort(self):
        from services.orchestrator.workflows import FULL_ANALYSIS_DAG
        order = FULL_ANALYSIS_DAG.topological_sort()
        assert "ingest" == order[0]
        assert "proposal" == order[-1]
        assert order.index("believe") < order.index("hypothesis_critique_loop")
        assert order.index("mapping") < order.index("hypothesis_critique_loop")

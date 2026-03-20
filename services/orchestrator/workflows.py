"""Pre-defined bounded workflows.

Includes both linear pipelines (Workflow) and DAG-based workflows (DAGDefinition).
"""

from services.orchestrator.schemas import Task, Workflow
from services.orchestrator.dag import DAGDefinition, DAGNode

# Workflow 1: Contradiction Analysis
# Extract claims → normalize → detect contradictions → compute beliefs
CONTRADICTION_ANALYSIS = Workflow(
    workflow_id="contradiction_analysis",
    description="Extract claims, normalize metrics, detect contradictions, compute belief states",
    tasks=[
        Task(
            task_id="ingest",
            component="ingestion",
            input_schema="IngestionRequest",
            output_schema="IngestionResult",
            dependencies=[],
        ),
        Task(
            task_id="extract",
            component="extraction",
            input_schema="IngestionResult",
            output_schema="ExtractionResult",
            dependencies=["ingest"],
        ),
        Task(
            task_id="normalize",
            component="normalization",
            input_schema="ExtractionResult",
            output_schema="NormalizationResult",
            dependencies=["extract"],
        ),
        Task(
            task_id="contradict",
            component="contradiction",
            input_schema="NormalizationResult",
            output_schema="ContradictionResult",
            dependencies=["normalize"],
        ),
        Task(
            task_id="believe",
            component="belief",
            input_schema="ContradictionResult",
            output_schema="BeliefResult",
            dependencies=["contradict"],
        ),
    ],
)

# Workflow 2: Literature Analysis
LITERATURE_ANALYSIS = Workflow(
    workflow_id="literature_analysis",
    description="Analyze literature: extract, normalize, detect contradictions, compute beliefs",
    tasks=[
        Task(
            task_id="ingest",
            component="ingestion",
            input_schema="IngestionRequest",
            output_schema="IngestionResult",
            dependencies=[],
        ),
        Task(
            task_id="extract",
            component="extraction",
            input_schema="IngestionResult",
            output_schema="ExtractionResult",
            dependencies=["ingest"],
        ),
        Task(
            task_id="normalize",
            component="normalization",
            input_schema="NormalizationResult",
            output_schema="NormalizationResult",
            dependencies=["extract"],
        ),
        Task(
            task_id="contradict",
            component="contradiction",
            input_schema="NormalizationResult",
            output_schema="ContradictionResult",
            dependencies=["normalize"],
        ),
        Task(
            task_id="believe",
            component="belief",
            input_schema="ContradictionResult",
            output_schema="BeliefResult",
            dependencies=["contradict"],
        ),
    ],
)


def build_full_analysis_dag() -> DAGDefinition:
    """Build the FULL_ANALYSIS DAG per Design.md 7-step flow.

    1. Ingestion (PDF → chunks + embeddings → Chroma + SQLite)
    2. Context Extraction (chunks → ExperimentalContext registry)
    3a. Claim Extraction → Normalization → Contradiction → Belief  [linear]
    3b. Literature Mapping (chunks → HDBSCAN → ClusterMap)         [parallel with 3a]
    4. Hypothesis-Critique Loop (claims + contradictions + map → validated hypothesis)
    5. Consolidation (hypothesis + beliefs + map → structured analysis)
    6. Multimodal Extraction (PDF → tables, metrics)                [parallel, starts at step 1]
    7. Proposal Generation (hypothesis + evidence + tables → Markdown/LaTeX)
    """
    dag = DAGDefinition(dag_id="full_analysis")

    # Step 1: Ingestion
    dag.add_node(DAGNode(task_id="ingest", tool="ingestion"))

    # Step 2: Context extraction
    dag.add_node(DAGNode(task_id="context", tool="context", depends_on=["ingest"]))

    # Step 3a: Claim pipeline (linear)
    dag.add_node(DAGNode(task_id="extract", tool="extraction", depends_on=["context"]))
    dag.add_node(DAGNode(task_id="normalize", tool="normalization", depends_on=["extract"]))
    dag.add_node(DAGNode(task_id="contradict", tool="contradiction", depends_on=["normalize"]))
    dag.add_node(DAGNode(task_id="believe", tool="belief", depends_on=["contradict"]))

    # Step 3b: Literature mapping (parallel with 3a)
    dag.add_node(DAGNode(task_id="mapping", tool="mapping", depends_on=["ingest"]))

    # Step 4: Hypothesis-critique loop (depends on both 3a and 3b)
    dag.add_node(DAGNode(
        task_id="hypothesis_critique_loop",
        tool="agent_loop",
        depends_on=["believe", "mapping"],
    ))

    # Step 5: Consolidation
    dag.add_node(DAGNode(
        task_id="consolidation",
        tool="consolidation",
        depends_on=["hypothesis_critique_loop"],
    ))

    # Step 6: Multimodal extraction (parallel, starts after ingestion)
    dag.add_node(DAGNode(task_id="multimodal", tool="multimodal", depends_on=["ingest"]))

    # Step 7: Proposal generation (depends on consolidation + multimodal)
    dag.add_node(DAGNode(
        task_id="proposal",
        tool="proposal",
        depends_on=["consolidation", "multimodal"],
    ))

    return dag


# DAG-based workflow definitions
FULL_ANALYSIS_DAG = build_full_analysis_dag()


# Workflow registry
WORKFLOWS = {
    "contradiction_analysis": CONTRADICTION_ANALYSIS,
    "literature_analysis": LITERATURE_ANALYSIS,
}

DAG_WORKFLOWS = {
    "full_analysis": FULL_ANALYSIS_DAG,
}

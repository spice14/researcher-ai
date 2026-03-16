"""Pre-defined bounded workflows."""

from services.orchestrator.schemas import Task, Workflow

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

# Workflow 2: Literature Analysis (identical to contradiction_analysis for now)
# Can be extended later with additional literature-specific tasks
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

# Workflow registry
WORKFLOWS = {
    "contradiction_analysis": CONTRADICTION_ANALYSIS,
    "literature_analysis": LITERATURE_ANALYSIS,
}

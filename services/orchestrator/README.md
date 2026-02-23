# Orchestrator

## Purpose

Deterministic DAG execution engine for bounded workflows.

Executes pre-defined task graphs with topological ordering.

**No dynamic planning.**  
**No LLM-driven routing.**  
**No autonomous behavior.**

All execution paths are explicit and declared in code.

## Architecture

### Task Model

```python
Task {
    task_id: str
    component: str  # e.g., "ingestion", "extraction"
    input_schema: str
    output_schema: str
    dependencies: List[str]  # Task IDs
}
```

### Workflow Model

```python
Workflow {
    workflow_id: str
    description: str
    tasks: List[Task]  # In topological order
}
```

## Supported Workflows

### 1. `contradiction_analysis`

```
ingest → extract → normalize → contradict → believe
```

Produces: `List[BeliefState]`

### 2. `literature_analysis`

```
ingest → extract → normalize → contradict → believe
```

Identical to `contradiction_analysis`.  
Can be extended with literature-specific tasks later.

## Execution Model

1. Retrieve workflow by `workflow_id`
2. Execute tasks in declared order
3. Pass output of task N to task N+1
4. Log every execution with:
   - input hash
   - output hash
   - latency
   - deterministic flag (always True)

## Observability

Every task execution emits:

```python
ExecutionLog {
    task_id: str
    component: str
    input_hash: str
    output_hash: str
    latency_ms: float
    deterministic: bool
}
```

Logs are serializable and inspectable.

## Determinism Guarantee

Same workflow + same input → identical output + identical hashes.

No hidden state.  
No global mutations.  
No randomness.

## Testing

See `tests/services/test_orchestrator.py` for:
- DAG execution order validation
- Hash determinism tests
- Full pipeline integration tests

# SYSTEM STATUS — 2026-02

## 1. Executive Snapshot

- Architecture status (Phase A): **PARTIAL**
  - MCP primitives and wrappers exist and are tested (`core/mcp/*`, `services/*/tool.py`, `tests/test_mcp_contract_enforcement.py`, `tests/test_mcp_contract_integrity.py`).
  - Canonical E2E harness currently executes a 4-step MCP path (`ingestion -> extraction -> normalization -> belief`) in `run_minimal_e2e.py`.
  - Full 5-step contradiction path is present architecturally but disabled in the current canonical harness due belief→contradiction payload mismatch.
- Extraction status (Weak Tier): **PARTIAL**
  - Weak tier is integrated in `services/extraction/service.py` and validated in `services/extraction/weak_claim_validator.py` + `tests/test_weak_claim_extraction.py`.
  - Real-paper E2E run shown in terminal context extracts `0` claims on `real_paper_arxiv.pdf`.
- Determinism status: **PARTIAL**
  - Current canonical E2E check passes determinism and registry isolation (`python run_minimal_e2e.py` exit `0`, 5 identical hashes, trace entries `4`).
  - Historical brutal 82-paper result in session record reports deterministic rate `77.8%`.
- Misbinding status: **COMPLETE (for recorded audit scope)**
  - Historical brutal 82-paper session record reports misbindings `0`.
- Brutal 82-paper headline metrics (from recorded audit session context):
  - Total papers: `82`
  - Deterministic rate: `77.8%`
  - Zero-extraction rate: `61.7%`
  - Normalization yield: `7.8%`
  - Weak Tier lift: `+7.2%` yield
  - `CONTEXT_MISSING` reduction: `-11.3%`
  - Misbindings: `0`
- Known weaknesses:
  - Contradiction stage is not active in canonical E2E pipeline (`run_minimal_e2e.py`).
  - Extraction remains low-recall on at least one real-paper E2E sample (0 extracted claims).
  - Brutal audit artifacts/count tables were removed from current workspace; several absolute counts are not recoverable from files now present.

## 2. Architecture State (Phase A Compliance)

### Principle: Separation of Concerns

- Principle (Design.md): retrieval, reasoning, extraction, generation remain distinct components.
- Current implementation:
  - Deterministic domain services are separated: `services/ingestion/service.py`, `services/extraction/service.py`, `services/normalization/service.py`, `services/belief/service.py`, `services/contradiction/service.py`, `services/rag/service.py`, `services/context/service.py`.
  - MCP orchestrator path is isolated in `services/orchestrator/mcp_orchestrator.py`.
  - Isolation tests: `tests/test_architecture_isolation.py`.
- MCP enforcement mechanisms:
  - Tool wrappers per domain in `services/*/tool.py`.
  - Registry and pipeline validation in `core/mcp/registry.py`.
- Status: **COMPLETE**

### Principle: Selective Agentic Reasoning

- Principle (Design.md): agentic reasoning used only where critique adds value.
- Current implementation:
  - Hypothesis schema/validator exists: `core/schemas/hypothesis.py`, `core/validators/hypothesis_validator.py`.
  - No implemented `agents/` runtime layer in current workspace root.
- Test references:
  - Validator coverage in `tests/test_validators_logic.py` and related validator tests.
- Status: **PARTIAL**

### Principle: Protocol-First Design (MCP)

- Principle (Design.md): components communicate through MCP interfaces.
- Current implementation:
  - Manifest contract: `core/mcp/mcp_manifest.py`.
  - Tool interface: `core/mcp/mcp_tool.py`.
  - Registry/discovery: `core/mcp/registry.py`.
  - Deterministic MCP executor: `services/orchestrator/mcp_orchestrator.py`.
  - Wrappers: `services/ingestion/tool.py`, `services/extraction/tool.py`, `services/normalization/tool.py`, `services/belief/tool.py`, `services/contradiction/tool.py`.
- Test references:
  - `tests/test_mcp_contract_enforcement.py`
  - `tests/test_mcp_contract_integrity.py`
- Status: **COMPLETE**

### Principle: Provenance-First Outputs

- Principle (Design.md): claims/conclusions must be traceable.
- Current implementation:
  - Claim evidence schema: `core/schemas/claim.py` (`ClaimEvidence`).
  - Execution trace with per-step hashes and final hash: `core/mcp/trace.py`.
  - Trace capture in MCP orchestrator: `services/orchestrator/mcp_orchestrator.py`.
- Test references:
  - Orchestrator and trace behavior covered by `tests/test_orchestrator_e2e.py`, `tests/test_orchestrator_service.py`, `tests/test_orchestrator_service_expanded.py`.
- Status: **COMPLETE**

### Principle: Local-First Execution

- Principle (Design.md): local/self-hostable execution prioritized.
- Current implementation:
  - Local runner exists: `run_minimal_e2e.py`.
  - Python-local dependency model via `requirements.txt` and `pyproject.toml`.
  - Top-level `infra/` layer described in docs is not present in current workspace.
- Status: **PARTIAL**

### Required explicit checks

- Any service calls another directly?
  - Domain services: no cross-domain imports detected by `tests/test_architecture_isolation.py`.
  - Orchestrator implementation `services/orchestrator/service.py` directly instantiates and calls domain services; this is a non-MCP execution path.
- Any legacy method names exist?
  - Canonical contract tests enforce absence (`extract_claims`, etc.) in `tests/test_mcp_contract_enforcement.py`, `tests/test_mcp_contract_integrity.py`.
  - `run_minimal_e2e.py` runtime assertion `validate_no_legacy_methods()` passes in latest terminal run.
- Any bypass paths exist?
  - Yes. `services/orchestrator/service.py` is a direct-service orchestration path alongside MCP path (`services/orchestrator/mcp_orchestrator.py`).

## 3. Capability Matrix (from CAPABILITIES.md)

| Capability | Design Intent | Current Implementation | Status |
|---|---|---|---|
| Ingestion | Parse papers and produce structured chunks | `services/ingestion/service.py`, `services/ingestion/pdf_service.py`, `services/ingestion/pdf_loader.py` with tests (`tests/test_ingestion_service.py`, `tests/test_pdf_services_lightweight.py`) | COMPLETE |
| Extraction (Strong + Weak Tier) | Extract claims with context + quantitative evidence | Strong/legacy rules in `services/extraction/service.py`; Weak Tier in `services/extraction/weak_claim_validator.py` and integration/tests in `tests/test_weak_claim_extraction.py` | PARTIAL |
| Normalization | Canonicalize metrics and numeric values | `services/normalization/service.py` with broad tests (`tests/test_normalization_service.py`, `tests/test_normalization_comprehensive.py`) | COMPLETE |
| Belief synthesis | Construct belief state from normalized claims | `services/belief/service.py`, MCP wrapper `services/belief/tool.py`, tests (`tests/test_belief_service.py`, `tests/test_belief_tool.py`) | PARTIAL |
| Contradiction detection | Detect contradictions/consensus across claims | `services/contradiction/service.py`, `services/contradiction/tool.py`, tests (`tests/test_contradiction_service.py`, `tests/test_contradiction_engine.py`) | PARTIAL |
| Cross-paper identity resolution | Resolve equivalent claims/entities across papers | No dedicated identity-resolution service/module in current workspace | NOT IMPLEMENTED |
| Clustering | Group literature into coherent clusters | No clustering service/module in current workspace root; only capability/design text references | NOT IMPLEMENTED |
| Hypothesis Agent | Generate structured hypotheses with critique loop | Schemas/validators exist (`core/schemas/hypothesis.py`, `core/validators/hypothesis_validator.py`), no runtime agent implementation | NOT IMPLEMENTED |
| Critic Agent | Adversarial critique of hypotheses | No runtime critic agent implementation in current workspace root | NOT IMPLEMENTED |
| Multimodal linking | Link extracted tables/figures to claims | Table/PDF extraction primitives exist (`services/ingestion/table_extractor.py`, `services/ingestion/pdf_service.py`), no end-to-end multimodal linking layer | PARTIAL |
| Proposal layer | Produce proposal artifacts from validated hypotheses | No proposal/artifact generation service in current workspace | NOT IMPLEMENTED |

## 4. Brutal 82-Paper Audit Summary

### Recorded metrics (from prior brutal audit session record)

- Total papers: `82`
- Deterministic: `77.8%`
- Zero-extraction: `61.7%`
- Misbindings: `0`
- Normalization yield: `7.8%`
- Weak Tier yield lift vs prior baseline: `+7.2%`
- `CONTEXT_MISSING` reduction after Weak Tier: `-11.3%`

### Required fields with current recoverability status

- Valid PDFs: **NOT RECOVERABLE FROM CURRENT REPO ARTIFACTS**
- Total claims extracted: **NOT RECOVERABLE FROM CURRENT REPO ARTIFACTS**
- Total normalized: **NOT RECOVERABLE FROM CURRENT REPO ARTIFACTS**
- Pipeline errors (exact count): **NOT RECOVERABLE FROM CURRENT REPO ARTIFACTS**

Reason: audit scripts/outputs referenced in prior sessions are not present in current tracked workspace/git history snapshot.

### Technical interpretation

- `CONTEXT_MISSING` dominates because strong-tier extraction requires explicit context binding (dataset/metric predicates), and many quantitative statements in papers are context-implicit.
- Normalization yield is low when extracted claims are sparse and when extracted text does not satisfy canonical metric/value binding constraints.
- Weak Tier improved recall (`+7.2%` yield lift and `-11.3% CONTEXT_MISSING`) but did not eliminate high zero-extraction rate (`61.7%`).
- Historical deterministic rate (`77.8%`) is below full determinism target. Current canonical E2E determinism is passing on the active single-paper harness.

## 5. Determinism & Contract Integrity

- Canonical method enforcement:
  - Enforced by `tests/test_mcp_contract_enforcement.py` and `tests/test_mcp_contract_integrity.py`.
  - Runtime check in `run_minimal_e2e.py` (`validate_no_legacy_methods`) passes in latest run.
- Contract test suite:
  - MCP contract and wrapper behavior: `tests/test_mcp_contract_enforcement.py`, `tests/test_mcp_contract_integrity.py`.
  - Architecture isolation: `tests/test_architecture_isolation.py`.
- `extract_claims` bug resolution status:
  - Current extraction contract expects `ClaimExtractor.extract(...)`; legacy `extract_claims` is tested as absent.
- Current determinism status:
  - Canonical E2E harness reports 5/5 identical hashes and registry isolation pass (latest terminal run exit `0`).
- Known nondeterministic causes:
  - Historical brutal audit reported deterministic rate `77.8%`; unresolved for full-corpus condition in current repository state because those audit artifacts are absent.
- OPEN ISSUE:
  - Full-corpus determinism remains **OPEN ISSUE** due missing reproducible brutal-audit artifacts and contradiction-stage exclusion in current canonical harness.

## 6. Extraction Engine — Current Topology

- Strong Tier (explicit context):
  - Implemented in `services/extraction/service.py` via structural/performance/efficiency extraction paths.
  - Requires clearer metric/context binding and predicate patterns.
- Weak Tier (delta-based quantitative claims):
  - Implemented in `services/extraction/weak_claim_validator.py` and invoked from extractor when `include_weak=True`.
  - Accepts quantitative deltas + measurable properties; rejects hedged/compound patterns.
- Rejection logic:
  - `services/extraction/schemas.py` defines `NoClaimReason` values (`context_missing`, `no_metric`, `compound_metric`, `hedged_statement`, etc.).
- Known bottlenecks:
  - High historical `context_missing` burden in brutal audit record.
  - Real-paper canonical E2E sample currently yields zero extracted/normalized claims.
  - `services/extraction/context_stitcher.py` exists but is not integrated into `ClaimExtractor` execution path.

Explicit statement: extraction remains tuned toward ML-style claim patterns (metric lexicons, benchmark-oriented predicates, and explicit quantitative framing in `services/extraction/service.py` and `services/extraction/weak_claim_validator.py`).

## 7. Known Gaps vs Design

### Not Yet Implemented (Per Design.md)

- Contextual Mapping (Phase B clustering): **NOT IMPLEMENTED** as a dedicated clustering component.
- Cross-paper identity resolution: **NOT IMPLEMENTED**.
- Consensus scoring layer (design-level capability beyond basic contradiction outputs): **PARTIAL/NOT IMPLEMENTED AS DEDICATED MODULE**.
- Hypothesis Agent runtime: **NOT IMPLEMENTED**.
- Critic Agent runtime: **NOT IMPLEMENTED**.
- Multimodal linking layer (tables/figures to claims end-to-end): **PARTIAL**.
- Proposal layer: **NOT IMPLEMENTED**.

## 8. Risk Assessment

- Over-constrained extraction:
  - Strong-tier context requirements can reject valid quantitative claims when context is implicit.
- Domain bias:
  - Extraction heuristics and metric lexicons are benchmark/ML oriented, reducing portability to non-ML phrasing.
- Context inference weakness:
  - Weak Tier improves recall but cannot fully substitute missing context propagation; context stitcher is not integrated.
- Determinism edge cases:
  - Historical full-corpus deterministic rate (`77.8%`) indicates unresolved corpus-level variance despite single-harness pass.
- Weak Tier false positives:
  - Weak Tier relies on regex acceptance for quantitative deltas; risk exists for semantically weak but numerically formatted statements.

## 9. System Maturity Rating

**Classification: Architectural Prototype**

Justification:
- MCP contracts, deterministic tooling interfaces, and broad unit/integration tests are present.
- Core extraction/normalization/belief/contradiction services exist, but canonical E2E currently excludes contradiction stage.
- Multiple design-locked capabilities (clustering, identity resolution, agent runtimes, proposal layer) are not implemented.
- Historical brutal audit metrics indicate major extraction and determinism gaps at corpus scale.

## 10. Next Required Milestone (Engineering, Not Vision)

**Restore and validate the full 5-step canonical MCP pipeline (`ingestion -> extraction -> normalization -> belief -> contradiction`) by fixing the belief→contradiction payload contract and re-enabling contradiction in `run_minimal_e2e.py`.**

This is the immediate blocker for architecture-to-function parity and for trustworthy end-to-end regression gating.

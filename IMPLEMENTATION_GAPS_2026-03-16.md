# Implementation Gaps Analysis — March 16, 2026

**Status:** Comprehensive gap audit comparing current TECHNICAL_OVERVIEW.md (as of March 16, 2026) against three driving documents: README.md, capabilities.md, and Design.md.

**Scope:** This document identifies missing features, incomplete implementations, architectural gaps, and prioritizes remediation.

---

## PART 1: GAPS IN README.md CONCEPTS

README.md defines core messaging about user experience, capabilities, and design principles. The following concepts are inadequately reflected in the current codebase:

### GAP 1.1: "Human-in-the-Loop by Design" Promise vs. Implementation

| Aspect | README Promise | Current Status | Impact |
|--------|---------------|-----------------|--------|
| **User Interaction Flow** | "The system is human-in-the-loop by design and does not operate autonomously" | No user-facing UI layer exists; only Python service interfaces and CLI scripts. Agent loop boundaries are coded (max_iterations=5) but not exposable to users. | Users cannot pause/resume/redirect execution mid-pipeline. Research workflows are non-interactive. Cannot stop agents before max_iterations. |
| **Inspection Surfaces** | "Composable, inspectable components" | Services produce logs + MCP traces, but no CLI tools or web interface to navigate/review intermediate outputs. Output structure (JSON) is not human-filtered. | Researchers cannot easily review which claims were extracted, which contradictions detected, which assumptions agents made before advancing to next step. |
| **Judgment Gates** | "Human judgment always in control" | No explicit veto points or review gates in orchestrator pipeline. Hypothesis generation → Critique loops automatically but user cannot intervene between rounds. | High-confidence claims can propagate downstream without user validation. No "mark incorrect" or "override" mechanism. |

**Gaps to implement:**
- User-facing dashboard or CLI menu for pipeline inspection
- Explicit pause/resume/redirect endpoints in orchestrator
- User confirmation gates (optional per service) before advancing to next step
- Claim rejection mechanism that feeds back to extraction service
- Hypothesis/criticism review interface with user feedback capture

**Related files needing expansion:** `services/orchestrator/mcp_orchestrator.py`, `agents/loop.py`, (new) `infra/ui/` or CLI tools

---

### GAP 1.2: "Evidence-Bound Outputs with Provenance"

| Aspect | README Promise | Current Status | Impact |
|--------|---------------|-----------------|--------|
| **Provenance Chains** | "Evidence-bound outputs with provenance" | Provenance schema exists (EvidenceProvenance with paper_id, chunk_id, tool_name, timestamp). Phase 5 audit validates provenance contract. BUT: provenance propagation through agent outputs (Hypothesis → Rationale → Grounding) is not fully traced. | Claims have clear paper_id/chunk_id bindings. But when Hypothesis Agent cites a normalized claim, the chain back to original paper/chunk is not explicitly re-verified. Hypothesis confidence_score is computed internally (no explicit evidence count shown). |
| **Confidence Calibration** | "Outputs must reference source material or explicitly declare uncertainty" | Schemas support confidence_level (EXTRACTION, NORMALIZATION, GROUNDED) but agent outputs (Hypothesis, Critique, Proposal) do not include explicit confidence_rationale field showing *why* confidence is high/low. Confidence is stated but not decomposable. | When hypothesis reports confidence_score=0.75, users cannot see: "3 supporting claims + 1 contradiction → 75% confidence". Metrics like "# supporting evidence" and "contradiction density" are computed but not exposed. |
| **Traceability UI** | "Provenance linking clusters to abstracts or text snippets" | RAGResult and ExtractionResult include chunk_ids. Traces log all payloads. But no UI layer to render: "Claim A came from chunk [123] on page 5, which is here: [quoted text], which was extracted because [cite normalization logic]." | Provenance chain exists in JSON but is not human-navigable. External tools needed to trace a single claim back to source. |

**Gaps to implement:**
- Provenance rationale fields in Hypothesis, Critique, Proposal schemas (not just confidence_score, but confidence_reasoning)
- Artifact generation (markdown/HTML) with inline provenance links and quoted evidence
- Confidence decomposition: explicit field showing (supporting_count, contradiction_count, multi_context_boost)
- Provenance browser/tracer in CLI or web UI
- "Cite this hypothesis" function returning formatted reference + evidence list

**Related files needing expansion:** `core/schemas/hypothesis.py`, `core/schemas/critique.py`, `core/schemas/proposal.py`, (new) `services/proposal/provenance_formatter.py`

---

### GAP 1.3: "Serves Undergraduates to PhD Researchers" — User-Level Differentiation

| Aspect | README Promise | Current Status | Impact |
|--------|---------------|-----------------|--------|
| **Capability Scaling** | System "adapts by task intent, not academic title" but provides graduated experiences | All users receive identical pipeline: ingestion → extraction → normalization → contradiction → belief → hypothesis → critique → proposal. No "learning mode" (with explanations), no "rapid mode" (inference-only), no "research mode" (with strong safeguards). | Undergraduate trying to understand research consensus gets flooded with raw claims, contradictions, and belief states (internal metrics). PhD student designing experiments cannot opt into stricter evidence requirements or assumption tracking. |
| **Scope Management** | "Composable" capabilities | All 5 capabilities are always executed or none. Cannot request "just map the literature" or "just find contradictions" from a higher-level user interface. | Users must invoke orchestrator explicitly to get partial results. No abstracted "research workflows" (e.g., "Consensus Finder" that hides claim extraction complexity). |
| **Explanation Depth** | Support "learning how to read research" (undergraduates) | Multimodal extraction, claim extraction, normalization logic are deterministic but unexamined by user. No "explain this claim extraction" or "why did this metric get that normalized value" mechanism. Rationale only available in code inspection. | Undergraduates cannot learn from system decisions. No pedagogical substrate. |

**Gaps to implement:**
- User role enum (UNDERGRADUATE, GRADUATE, RESEARCHER) with scope/strictness settings
- Workflow templates (e.g., "Literature Mapper" = ingestion → context mapping only; "Contradiction Finder" = ...extraction → contradiction; "Hypothesis Tester" = ...proposal)
- Explanation engine: rules for claim extraction, normalization, contradictions with human-readable justifications
- Evidence quality indicators (gold-standard vs. heuristic-extracted claims)
- Optional: guided walkthrough mode for first-time users

**Related files needing creation:** (new) `services/workflow/templates.py`, (new) `core/explanation/claim_explainer.py`, (new) `infra/user_roles.py`

---

### GAP 1.4: "Does Not Operate Autonomously" — Explicit Safeguards

| Aspect | README Promise | Current Status | Impact |
|--------|---------------|-----------------|--------|
| **Boundary Enforcement** | System with "safeguards" against autonomous behavior | Hypothesis loop has max_iterations=5 (coded). Agents have no autonomous sub-goal setting. But no explicit runtime guards documented or enforced outside code. | Potential for latent bugs in which agent escapes bounds (e.g., recursive hypothesis generation). No kill-switch mechanism in MCP tools. Bounded only by code review, not runtime enforcement. |
| **Assumption Tracking** | Hypotheses must "explicitly state assumptions" | Hypothesis schema includes assumptions[] field but no validation that assumptions are non-empty or reasonable. Agents are stubs so this cannot be verified. | Will need implementation later; currently a structural readiness issue. |
| **Claim Provenance Failures** | "Generates claims without evidence" is explicitly forbidden | Phase 5 audit verifies provenance contract. But contract only catches claims with LOW_CONFIDENCE and empty grounding_claim_ids (they are allowed). Normal-confidence claims without grounding are NOT flagged. | Edge case: normalization service can emit NormalizedClaim with no source Claims binding (if earlier extraction failed). Provenance audit would miss this if confidence is MEDIUM or HIGH. |

**Gaps to implement:**
- strict provenance enforcement: ALL claims (except intentional LOW_CONFIDENCE stubs) must have grounding_claim_ids populated from source claims
- Runtime bounded-step enforcement in agent loop (with telemetry on iteration count)
- Assumption validation: hypotheses with <2 assumptions trigger warning log
- Autonomous sub-goal detection in agents

**Related files:** `core/observability/provenance_audit.py`, `agents/loop.py`, (new) `core/safety/bounds_enforcer.py`

---

### GAP 1.5: "Research as Structured Process, Not Single Prompt"

| Aspect | README Promise | Current Status | Impact |
|--------|---------------|-----------------|--------|
| **Structured Workflows** | System treats research as multi-stage (map → extract → synthesize → produce) | MCPOrchestrator executes pipelines sequentially but hardcoded as list of tool names with implicit payload passing. No DAG abstraction. No declarative workflow specification. No conditional branching or error recovery workflows. | Cannot express: "If contradictions exceed threshold, run belief engine again with stricter thresholds" or "If hypothesis confidence < 0.6, ask Critic for one more iteration". All workflows are linear. |
| **Pipeline Visibility** | Research "pipeline is clear and inspectable" | ExecutionTrace logs all steps with hashes. But no visualization of pipeline structure itself. Operators cannot see: "Here are the 9 steps that will run for your query." | Debugging requires console log inspection. No pipeline DAG rendering (Graphviz, Mermaid, etc.). |
| **Failure Recovery** | Structured error handling | Orchestrator catches tool exceptions and retries with exponential backoff (max 3 retries). But no recovery workflows (e.g., "RAG failed, skip to contradiction detection" vs. "fail hard"). | Partial failures can leave pipeline in inconsistent state (e.g., if extraction times out after normalization, proposals may be stale). |

**Gaps to implement:**
- DAG abstraction for orchestrator with conditional branches and error routes
- Workflow DSL or YAML for declarative pipeline definition
- Pipeline execution plan visualization (pre-run)
- Failure recovery policies (skip, retry-harder, fail-hard, fallback-service)
- Partial result checkpointing (e.g., save claims even if contradiction fails)

**Related files:** `services/orchestrator/mcp_orchestrator.py`, (new) `services/orchestrator/dag.py`, (new) `services/orchestrator/workflow_loader.py`

---

## PART 2: GAPS IN CAPABILITIES (TECHNICAL READINESS)

capabilities.md defines 5 locked core capabilities. Current implementation status per capability:

### CAP 1: Contextual Literature Mapping

**Design Expectation (from capabilities.md + Design.md):**
- Semantic retrieval using vector similarity (not lexical token overlap)
- Unsupervised clustering (HDBSCAN or similar)
- Interpretable cluster labels via constrained LLM summarization
- Ranked lists of influential, representative, and boundary papers
- Structured JSON output with cluster details

**Current Status (from TECHNICAL_OVERVIEW.md):**
- Lexical RAG only (token overlap scoring)
- No clustering implemented
- No labeling implemented
- No paper ranking implemented
- No map structure in output

**Blockers:**
1. **Missing Vector DB Integration:** Design.md specifies Chroma + sentence-transformer embeddings. TECHNICAL_OVERVIEW.md has zero mention of Chroma. `services/rag/service.py` uses in-memory corpus and lexical scoring.
2. **Missing Clustering Algorithm:** No HDBSCAN or equivalent in codebase. Would need new import + service method.
3. **Missing LLM Labeling:** Cluster labels require constrained LLM call (gated by prompt version + token logging). Agents are stubs so no LLM infrastructure yet.
4. **Missing Paper Ranking Logic:** No implementation of "influential" vs "boundary" paper detection.

**Gaps:**
| Gap | Scope | Current | Missing | Priority |
|-----|-------|---------|---------|----------|
| Vector embeddings | RAG service | Lexical overlap | Semantic embeddings (sentence-transformer + Chroma) | **CRITICAL** |
| Clustering | Mapping service | None | HDBSCAN + cluster validation | **CRITICAL** |
| Cluster labeling | Mapping service | None | LLM-based summaries (constrained) + human review | **HIGH** |
| Paper ranking | Mapping service | None | Citation-count, recency, keyword alignment | **HIGH** |
| Structured output | Mapping service | None | ClusterAggregate schema + JSON serialization | **MEDIUM** |
| Upstream dependency | Orchestrator | No mapping tool | ContextualMappingTool (MCP wrapper) | **CRITICAL** |

**Implementation effort:** 5-10 days (vector DB setup + clustering + LLM labeling)

**Current use of CAP 1:** 
- Not tested in E2E pipeline (no mapping step in e2e_autopsy_real30.py)
- Design.md shows mapping as step 3 of 7-step execution flow, but not present in TECHNICAL_OVERVIEW data flow
- Inference: CAP 1 is **0% implemented** despite being first in research loop

---

### CAP 2: Contradiction & Consensus Finder

**Design Expectation (from capabilities.md + Design.md):**
- Extract claims from papers (deterministic)
- Group semantically equivalent claims (similarity)
- Identify consensus with confidence estimates
- Flag contradictions with counter-evidence

**Current Status (from TECHNICAL_OVERVIEW.md):**
- ✅ Claim extraction implemented (3 types: PERFORMANCE, EFFICIENCY, STRUCTURAL)
- ✅ Contradiction detection implemented (ConsensusGroup + ContradictionRecord)
- ✅ Belief engine aggregates evidence into epistemically grounded states
- ⚠️ Basic implementation works but with low recall/precision

**Metrics from E2E test (5 papers):**
- Claims extracted: 180
- Claims normalized: 40 (22.2% precision)
  - This means only 22% of extracted claims met full (metric + value + context) binding
- Contradictions found: 76
  - Against ground truth: 0 (no labeled contradictions in test set)
- Consensus groups: 8

**Core Issue:**
The bottleneck is **claim extraction yield**. Only 3.27% of expected claims surface (180 extracted vs. estimated 5,000+ expected in 5 papers). Low extraction means:
- Low normalization denominator → 22.2% normalized looks good but is low volume
- Low contradiction recall → only 76 contradictions because so few claims to compare
- Unreliable consensus → 8 groups may not represent true consensus if claim extraction is incomplete

**Root Causes:**
1. **PERFORMANCE claim detection requires full context** — Needs both (verb=achieves/reports/outperforms) AND (dataset mention in ExperimentalContext). If either missing, claim rejected. Cannot detect performance claims from section headers, abstracts, or sentences without explicit dataset tags.
2. **EFFICIENCY claim detection requires cost words** — Limited verb lexicon (requires, costs, takes, etc.). Misses claims like "faster" without "requires" context.
3. **STRUCTURAL claims are catch-all** — But predicate is non-quantified, so many are filtered as "uninteresting."
4. **Normalization rejection is harsh** — Claims without both metric AND numeric value are rejected. Claims with only metric name ("we use accuracy") but no value are dropped.

**Gaps:**
| Gap | Scope | Current | Missing | Impact |
|-----|-------|---------|---------|--------|
| Claim extraction yield | Extraction service | 3.27% (180/5000 est) | Expand claim predicates + context inference | **CRITICAL** Affects all downstream confidence metrics |
| Semantic claim grouping | Contradiction service | Exact key match (context_id, metric) | Vector similarity for claim clustering | **HIGH** False negatives on equiv claims with different phrasings |
| Consensus confidence | Belief engine | Hardcoded thresholds (≥3 supporting) | Calibrated Bayesian aggregation | **MEDIUM** Thresholds may not reflect true belief confidence |
| Ground-truth contradictions | Evaluation | No ground truth set | Annotate 5-paper set with labeled contradictions | **HIGH** Impossible to measure recall |

**Implementation effort:** 3-5 days for extraction improvements; 2-3 days for ground truth

**Current use of CAP 2:**
- ✅ Mostly implemented and tested
- ⚠️ Low extraction yield → downstream metrics questionable
- Status: **70% implemented** (core logic done, precision/recall needs tuning)

---

### CAP 3: Interactive Hypothesis Generation & Critique

**Design Expectation (from capabilities.md + Design.md):**
- Hypothesis Agent proposes literature-grounded hypotheses with explicit assumptions
- Critic Agent challenges using counter-evidence
- Iterative loop with user-intervention points
- Produces testable, defensible hypotheses with confidence scores

**Current Status (from TECHNICAL_OVERVIEW.md):**
- `agents/hypothesis/agent.py` exists with HypothesisInput / Hypothesis interface
- `agents/critic/agent.py` exists with CritiqueInput / Critique interface
- `agents/loop.py` coordinates iterations (max=5, confidence_threshold=0.8)
- ✅ All schemas defined
- ❌ **Agent implementations are stubs — no actual logic**

**Current implementation reality:**
```python
# From TECHNICAL_OVERVIEW.md Section 6.1
class HypothesisAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def generate(self, input: HypothesisInput) -> Hypothesis:
        # STUB: Not implemented
        pass
```

**Gaps:**
| Gap | Scope | Current | Missing | Priority |
|-----|-------|---------|---------|----------|
| Hypothesis generation | Hypothesis Agent | Interface only | LLM prompt + grounding logic | **CRITICAL** |
| Assumption extraction | Hypothesis Agent | Schema field defined | Prompt engineering + validation | **HIGH** |
| Counter-evidence retrieval | Critic Agent | Interface only | RAG query logic + chunk ranking | **CRITICAL** |
| Weakness identification | Critic Agent | Interface only | LLM-based critique rules | **HIGH** |
| Iteration coordination | Agent loop | Coded structure exists | Full execution + state tracking | **CRITICAL** |
| User intervention | Agent loop | Not implemented | Pause/resume/redirect endpoints | **MEDIUM** |
| Confidence calibration | Agent outputs | Field exists | Evidence-based scoring (not LLM guess) | **HIGH** |

**Implementation blockers:**
1. **LLM client not fully wired** — core/llm/client.py exists but unclear if bound to agents
2. **No prompt versioning infrastructure** — Design.md requires prompt version logging, but agents have no versioning system
3. **No structured output validation** — Agents outputs must satisfy schemas, but no guardrails/retry logic documented
4. **Token usage not logged** — Phase 5 observability requires token_usage in logs, but agent LLM calls not instrumented

**Implementation effort:** 5-7 days (prompt engineering + validation + instrumentation)

**Current use of CAP 3:**
- ❌ Not tested in E2E pipeline
- evaluation_rows show hypothesis_grounding_rate = 0.0 (agents not executed)
- Status: **5% implemented** (schema + loop structure only)

---

### CAP 4: Multimodal Evidence Extraction

**Design Expectation (from capabilities.md + Design.md):**
- Extract tables and figures from PDFs
- Normalize numeric results
- Link evidence to claims
- Preserve captions and page numbers
- Structured CSV/JSON output

**Current Status (from TECHNICAL_OVERVIEW.md):**
- `services/multimodal/service.py` exists
- Implements table detection via regex patterns (pipe-separated, tab-separated cells)
- Implements metric extraction (pattern matching for metric=value pairs)
- Implements caption detection ("Table N", "Figure N")
- Generates deterministic artifact IDs from hash
- Produces ExtractionResult objects
- ✅ Schemas defined

**Needs Validation:**
- No E2E test includes multimodal extraction (e2e_autopsy_real30.py does not call multimodal step)
- No evaluation metrics for table extraction accuracy
- No figure extraction (only tables + metrics)
- Pattern-based approach may miss tables in non-standard formats (image-only figures)

**Known Limitations (from TECHNICAL_OVERVIEW.md):**
> "Evaluation metrics require ground truth — hypothesis_grounding_rate and proposal_completeness are 0 when agents are not executed"

This means CAP 4 has **no quantitative validation**.

**Gaps:**
| Gap | Scope | Current | Missing | Impact |
|-----|-------|---------|---------|--------|
| Integration in pipeline | Orchestrator | Not called | MCPOrchestrator step + test | **CRITICAL** |
| Ground truth evaluation | Evaluation | None | 5-paper annotated dataset | **HIGH** |
| Figure extraction | Multimodal service | Tables only | OCR/vision-based figure extraction | **MEDIUM** Degrades completeness |
| Nested table parsing | Multimodal service | Simple patterns | Complex table structures | **MEDIUM** Row/col spans, merged cells |
| Artifact linking | Multimodal service | Schema field exists | Claim-to-extraction mapping | **HIGH** |
| Vision model integration | Multimodal service | Text-only | Visual extraction for scanned PDFs | **LOW** Future enhancement |

**Implementation effort:** 2-3 days for pipeline integration + validation; 3-5 days for figure extraction

**Current use of CAP 4:**
- ⚠️ Implemented but not integrated into main pipeline
- No evaluation data
- Status: **60% implemented** (core service done, validation + integration missing)

---

### CAP 5: Grant / Proposal Assistant

**Design Expectation (from capabilities.md + Design.md):**
- Accept validated hypothesis + supporting evidence
- Generate structured proposal narratives
- State novelty based on literature gaps
- Draft methodology and expected outcomes
- Produce editable formats (Markdown, LaTeX)
- Auto-assemble citations

**Current Status (from TECHNICAL_OVERVIEW.md):**
- `services/proposal/service.py` exists
- Accepts Hypothesis objects with grounding_claim_ids
- Synthesizes methodology outline (sketched)
- Generates expected outcomes (sketched)
- Emits Proposal schema with novelty_statement + motivation
- ✅ Schemas defined

**Reality Check:**
From TECHNICAL_OVERVIEW.md Section 3.10:
```python
# Proposal Service implementation (quoted)
class ProposalService:
    def generate(self, hypotheses, belief_states) -> List[Proposal]:
        """Generate structured research proposals from grounded hypotheses."""
        # Implementation from TECHNICAL_OVERVIEW.md shows sketched logic:
        # _synthesize_methodology() — combine evidence into procedure outline
        # _generate_expected_outcomes() — infer research impacts
        # But actual LLM calls and text generation not detailed
```

**Gaps:**
| Gap | Scope | Current | Missing | Priority |
|-----|-------|---------|---------|----------|
| Methodology synthesis | Proposal service | Outlined logic | LLM-based synthesis (from claims) | **CRITICAL** |
| Novelty statement | Proposal service | Schema field | Gap analysis against literature map | **CRITICAL** |
| Citation assembly | Proposal service | Not mentioned | Automated bibliography from grounding claims | **HIGH** |
| Format generation | Proposal service | Not mentioned | Markdown + LaTeX template rendering | **HIGH** |
| Integration in pipeline | Orchestrator | Not called | End-to-end test with all steps | **CRITICAL** |
| Evaluation metrics | Evaluation | None | Proposal completeness scoring | **HIGH** |
| User review loop | Design | Not mentioned | Proposal editing + feedback capture | **MEDIUM** |

**Implementation blockers:**
1. **Depends on CAP 3 (Hypotheses)** — Cannot generate proposals without actual hypotheses. Hypothesis Agent is stub.
2. **Depends on CAP 1 (Literature Map)** — Novelty statement needs context of related work. Mapping service not integrated.
3. **LLM prompting infrastructure** — Proposal generation requires multiple LLM calls (one per hypothesis section); not coded yet.

**Implementation effort:** 4-6 days (depends on CAP 1 + CAP 3 first)

**Current use of CAP 5:**
- ❌ Not tested; depends on upstream stubs
- evaluation_rows show proposal_completeness = 0.0 (agents not executed, proposals not generated)
- Status: **20% implemented** (schema + basic service structure only)

---

### Capability Summary Table

| Capability | Design Requirement | Current Status | Completion % | Blockers | Recommendation |
|------------|-------------------|-----------------|--------------|----------|-----------------|
| **CAP 1: Contextual Literature Mapping** | Semantic retrieval + clustering + labeling | Not integrated into pipeline; lexical RAG only | 5-10% | Vector DB missing, clustering not implemented | Implement before CAP 3 |
| **CAP 2: Contradiction & Consensus** | Claim extraction + grouping + consensus scoring | Mostly implemented but low extraction yield (3.27%) | 70% | Improve extraction predicates; ground truth annotation | Tune extraction logic now; implement ground truth next sprint |
| **CAP 3: Hypothesis Generation & Critique** | Hypothesis + Critic agents in iterative loop | Schema defined; agent implementations are stubs | 5% | LLM client wiring, prompt engineering | Block: requires CAP 1 context + LLM client v1 |
| **CAP 4: Multimodal Evidence Extraction** | Table extraction + caption linking + normalization | Service implemented but not integrated; untested | 60% | Pipeline integration, ground truth evaluation | Integrate into E2E pipeline this sprint |
| **CAP 5: Grant / Proposal Assistant** | Hypothesis→Proposal synthesis with novelty analysis | Schema defined; service is stub | 20% | Depends on CAP 1, CAP 3; LLM infrastructure | Block: cannot start until CAP 1+3 in progress |

---

## PART 3: GAPS IN DESIGN.md PRINCIPLES

Design.md specifies 5 non-negotiable architectural principles. Alignment assessment:

### PRINCIPLE 1: Separation of Concerns

**Design Requirement:**
> "Retrieval, reasoning, extraction, and generation are implemented as distinct components, not collapsed into a single LLM call."

**Current Status:**

✅ **MOSTLY ALIGNED:**
- 9 distinct services (ingestion, RAG, context, extraction, normalization, contradiction, belief, multimodal, proposal)
- Each has explicit input/output (Pydantic schemas)
- No service imports another service (no circular deps)
- All interaction via MCPOrchestrator (tool registry)

⚠️ **GAPS IDENTIFIED:**
1. **Proposal service imports from agents** (potential)
   - If proposal service depends on agent outputs, and agents depend on RAG, then proposal cannot be tested independently of agents
   - Needs verification: `services/proposal/service.py` dependencies

2. **Multimodal extraction not isolated from claims**
   - ExtractionResult schema has `artifact_type` but no explicit claim_linking method
   - If claim-to-artifact association is done outside multimodal service, concerns leak to orchestrator
   - Design.md says "associates extracted evidence with claims it supports" but unclear where this association happens

3. **Context extraction mixed with dataset patterns**
   - `services/context/service.py` does regex-based dataset detection + metric mapping
   - Could argue this violates single responsibility (dataset detection ≠ context extraction)
   - Minor: probably acceptable

**Impact of gaps:**
- Proposal service likely cannot be unit-tested without agents (blocked issue for CAP 5)
- Multimodal extraction testing may require mock claims or orchestrator context
- Limited ability to reuse multimodal service in other contexts

**Audit recommendation:** Verify `services/proposal/service.py` and `services/multimodal/service.py` import statements

---

### PRINCIPLE 2: Selective Agentic Reasoning

**Design Requirement:**
> "Multi-agent (A2A) reasoning is used only where adversarial or reflective reasoning adds value... deterministic tasks are implemented as services."

**Current Status:**

✅ **ALIGNED:**
- Only Hypothesis + Critic agents are reasoning components
- All other operations (ingestion, RAG, extraction, normalization, contradiction, belief, multimodal, proposal) are deterministic services
- Agents used specifically for tasks involving "epistemic uncertainty or debate" (hypothesis formation + critique)

⚠️ **POTENTIAL GAPS:**
1. **Proposal generation may be over-zealous on LLM usage**
   - Design.md says "convert validated hypotheses into structured research documents"
   - If proposal service generates free-form prose for novelty/methodology sections, this violates "deterministic where possible"
   - Better approach: proposal service takes hypothesis structure + grounding claims → deterministic synthesis (outline only), user (or agent) then writes prose
   - Current implementation unclear on prose vs. structure

2. **No documentation of where agents are NOT used**
   - Could add explicit note: "Extraction, RAG, normalization do not use LLMs; they use deterministic algorithms"
   - Minor documentation gap

3. **Agent iteration loop is unbounded by evidence**
   - Hypothesis loop runs max 5 iterations or until confidence ≥ 0.8
   - But if agent gets "stuck" (creates same hypothesis twice, or makes marginal edits), loop still runs
   - Could benefit from convergence detection (e.g., stop if revisions < 10% edit distance)

**Impact of gaps:**
- Proposal service may produce unrepeatable outputs (if it uses LLM for prose)
- E2E performance may degrade if agents iterate inefficiently
- Design intent ("deterministic where possible") may be violated

**Audit recommendation:** Review `services/proposal/service.py` for LLM usage; add convergence check to `agents/loop.py`

---

### PRINCIPLE 3: Protocol-First Design (MCP)

**Design Requirement:**
> "All components communicate via a uniform Model Context Protocol (MCP) interface, enabling loose coupling and extensibility."

**Current Status:**

✅ **PARTIALLY ALIGNED:**
- 9 deterministic services wrapped in MCPTool subclasses
- MCPRegistry provides service discovery
- MCPOrchestrator invokes tools via tool names + payload dicts
- All tools have manifest() + call() methods

❌ **CRITICAL GAPS — Data Stores NOT MCP-Wrapped:**

| Data Store | Design Expectation | Current Status | Gap |
|------------|-------------------|-----------------|-----|
| **Vector DB** | Design.md §Data/Memory: "Vector memory (Chroma)" — should be MCP service | Not implemented at all | Vector DB is missing entirely; no MCP wrapper anticipated |
| **Metadata DB** | Design.md §Data/Memory: "Structured metadata (SQLite)" — should be MCP service | Not implemented | Only in-memory session state exists; no MCP service for persistent metadata |
| **Session Store** | Design.md §Data/Memory: "Session memory (Redis or in-process)" | In-process only (InMemorySessionStore in orchestrator) | Redis option not implemented; in-process is sufficient for MVP but not production-grade |
| **Trace Store** | Design.md §Data/Memory: "Trace memory (JSON / Langfuse)" | JSONTraceStore implemented ✅ | Langfuse integration not started; JSON persistence works |

**What This Means:**
- **RAG service** is supposed to query Chroma (vector DB) but currently queries in-memory corpus via lexical scoring
- **Ingestion service** should store embeddings + metadata in Chroma + SQLite but currently returns results only; storage not implemented
- **Context extraction** should read from SQLite metadata registry but currently builds in-memory registry
- **Orchestrator** should load session from Redis but currently uses in-memory dict

**Architectural implication:** If these data stores are not MCP-wrapped:
1. Services have implicit dependencies on data layer (not explicit in schemas)
2. Cannot replace data store implementation without rewriting services
3. Violates "loose coupling" principle
4. Prevents distributed execution (if services run on separate hosts, how do they access shared data store?)

**Impact of gaps:**
- **BLOCKER for scale:** Cannot add Chroma to RAG without refactoring it into an MCP service
- **BLOCKER for persistence:** Session state lost on restart
- **Design debt:** Data layer is missing from architecture diagram

**Remediation roadmap:**
1. Create `services/vector_store/` service wrapping Chroma (VectorStoreTool)
   - `POST /call` with method={index, query}
   - Returns ranked results
   - Orchestrator calls this before RAG for semantic retrieval
2. Create `services/metadata_store/` service wrapping SQLite (MetadataStoreTool)
   - `POST /call` with method={insert, query, update}
   - Ingestion service calls this to persist papers, chunks, claims
   - Context service calls this to read dataset definitions
3. (Optional) Create `services/session_store/` service wrapping Redis (SessionStoreTool)
   - For now, in-memory is acceptable; make pluggable

**Related files needing creation:**
- `services/vector_store/service.py` + `tool.py`
- `services/vector_store/schemas.py`
- `services/metadata_store/service.py` + `tool.py`
- `services/metadata_store/schemas.py`
- Update `services/orchestrator/mcp_orchestrator.py` to call these services

---

### PRINCIPLE 4: Provenance-First Outputs

**Design Requirement:**
> "All outputs that assert claims, hypotheses, or conclusions must be traceable to source material or explicitly marked as uncertain."

**Current Status:**

✅ **MOSTLY ALIGNED:**
- All Claim objects include (paper_id, chunk_id) bindings
- NormalizedClaim includes source_claim_ids[]
- Hypothesis schema includes grounding_claim_ids[]
- Phase 5 provenance audit verifies that all claims meet provenance contract
- ExecutionTrace logs all tool inputs/outputs with hashes

⚠️ **GAPS IDENTIFIED:**

| Gap | Scope | Current | Missing | Impact |
|-----|-------|---------|---------|--------|
| **Provenance in Critique** | Critic agent | Interface defined | counter_evidence[] must have (paper_id, chunk_id). If null, critique fails validation | Critic stub; unclear if validated when implemented |
| **Provenance in Proposal** | Proposal service | Schema defined | methodology_outline, expected_outcomes must reference source hypothesis/claims. If not, marked LOW_CONFIDENCE | Auto-marked low if not grounded; may hide quality issues |
| **Confidence rationale** | All agent outputs | Confidence_score field exists | No field showing *why* confidence has this value (e.g., "2 supporting claims, 1 contradiction → 60% confidence"). Confidence is asserted, not derived. | Users cannot audit confidence; appears arbitrary |
| **User-facing provenance** | UI layer | Execution traces exist | No tool/interface to navigate provenance backward from output→claim→chunk→paper | Traces are logged but not human-accessible |
| **Link decay** | Persistent storage | Not applicable yet (no persistence) | Once SQLite metadata added, must handle: what if paper is deleted? Orphaned claims? | Future concern but design decision needed |

**Remediation:**
1. Add `confidence_rationale: str` field to Hypothesis, Critique, Proposal schemas
   - Agents populate with human-readable explanation
   - Example: "2 supporting claims from Nature, 1 from ArXiv; 1 contradiction (weak context) → 65% confidence"
2. Implement confidence decomposition in agents
   - Count supporting/contradicting claims
   - Compute support ratio
   - Check multi-context boost
   - Return (confidence_score, supporting_count, contradiction_count, rationale)
3. Create provenance tracer CLI or web endpoint
   - Input: claim_id or hypothesis_id
   - Output: trace back to papers, chunks, with quoted evidence

**Related files:** `core/schemas/hypothesis.py`, `core/schemas/critique.py`, `agents/hypothesis/agent.py`, (new) `services/provenance/tracer.py`

---

### PRINCIPLE 5: Local-First Execution

**Design Requirement:**
> "The system supports local inference and self-hosted infrastructure to reduce cost, protect sensitive research data, and improve reproducibility."

**Current Status:**

✅ **ALIGNED:**
- Services are Python (no cloud-only dependencies)
- Deterministic algorithms (no stochastic elements)
- Tests pass locally without APIs
- Docker infra available (infra/Dockerfile, infra/docker-compose.yml)

⚠️ **GAPS IDENTIFIED:**

| Requirement | Design Intent | Current Status | Gap |
|------------|---------------|-----------------|-----|
| **LLM inference local** | "Support local inference" | Agents use generic llm_client (core/llm/client.py) pointed at Ollama for local models | ✅ Ollama support; qwen2.5:32b default. But can fall back to API if not configured -> Need safeguard |
| **Vector embeddings local** | Chroma + sentence-transformer (open-source) | Chroma not integrated; no embedding model specified | ❌ Cannot do semantic RAG locally without sentence-transformer setup |
| **Storage local** | SQLite for metadata | Not implemented | ❌ Will need SQLite setup script |
| **No cloud requirement** | Can run offline | Depends on implementation, but design is sound | ⚠️ If agents query external APIs they cannot be disabled, violates local-first |
| **Reproducibility** | Exact output → exact input | Deterministic services ✅; agent outputs may vary if LLM changes | ⚠️ Phase 5 audit logs LLM model/version, so reproducibility traceable but not guaranteed |

**Safeguards needed:**
1. Environment variable to require local execution (fail if OLLAMA_API_URL not set)
2. Sentence-transformer model auto-download on first RAG call
3. SQLite initialization script in infra/
4. Documentation: "How to run Researcher-AI fully offline"

**Related files:** `.env.template`, `core/llm/client.py`, `infra/docker-compose.yml`, infra setup scripts

---

### Data/Memory Model Alignment

**Design.md specifies 4 memory layers. Current implementation:**

| Layer | Design | Current | Status | Gap |
|-------|--------|---------|--------|-----|
| **Vector Memory** | Chroma with embeddings | Not implemented | ❌ | Create VectorStoreTool (see Principle 3) |
| **Metadata Memory** | SQLite (papers, sessions, hypotheses, artifacts) | Not implemented (in-memory schema only) | ❌ | Create MetadataStoreTool |
| **Session Memory** | Redis or in-process dict | InMemorySessionStore (in-process) | ⚠️ | Works for MVP; Redis option useful for production |
| **Trace Memory** | JSON or Langfuse | JSONTraceStore + Phase 5 audit logs | ✅ | Langfuse integration optional but nice-to-have |

**Impact:** Systems depending on persistent memory will fail between restarts.

---

### Execution Flow (7-Step Model)

**Design.md § Execution Flow (Typical Session):**

```
1. User submits a paper or topic
2. Orchestrator triggers ingestion and indexing
3. Contextual mapping builds a semantic view of related literature
4. Hypothesis Agent proposes candidate hypotheses
5. Critic Agent evaluates and challenges them
6. Orchestrator consolidates validated hypotheses and evidence
7. Optional extraction and proposal generation steps are executed
```

**TECHNICAL_OVERVIEW.md actual data flow:**
```
Raw PDF
  ↓ Ingestion Service
Chunks + telemetry
  ↓ Context Extraction Service
Context registry + chunk updates
  ↓ Extraction Service
Claimed facts
  ↓ Normalization Service
Normalized claims
  ↓ Contradiction Service
Consensus groups + contradictions
  ↓ Belief Engine
Belief states
  ↓ Proposal Service
Research artifacts
  ↓ Phase 5 Observability
Audit trails + determinism verification
```

**ALIGNMENT GAP:**
- **Step 1-2 (Ingestion)**: ✅ Aligned
- **Step 3 (Contextual Mapping)**: ❌ **MISSING** — No mapping step in actual flow; only extraction
- **Step 4-5 (Hypothesis/Critic)**: ❌ **STUBS** — Not in E2E flow; agents not executed
- **Step 6 (Consolidation)**: ❌ **PARTIAL** — Belief engine aggregates but no explicit consolidation step for user review
- **Step 7 (Extraction/Proposal)**: ❌ **PARTIAL** — Proposal service exists but not integrated; multimodal not called

**Impact:** Current implementation skips the "semantic mapping" step (core of CAP 1), making subsequent hypothesis generation less grounded.

---

### Design Gaps Summary

| Principle | Status | Blocker? | Effort |
|-----------|--------|----------|--------|
| Separation of Concerns | Mostly aligned; service import validation needed | No | 0.5 days |
| Selective Agentic Reasoning | Aligned; proposal prose TBD | No (design decision) | 1-2 days |
| Protocol-First (MCP) | **CRITICAL GAP:** Data stores not MCP-wrapped | **YES** | 5-7 days |
| Provenance-First Outputs | Mostly aligned; confidence rationale missing | No | 2-3 days |
| Local-First Execution | Sound design; safeguards needed | No (feature) | 1-2 days |

---

## PART 4: IMPLEMENTATION ROADMAP TO CLOSE GAPS

This section prioritizes remediation across all gaps identified in Parts 1-3.

### Roadmap Overview

Implementation is organized into **4 sequential phases** (Phase 0, Phase 1, Phase 2, Phase 3), each with concrete deliverables and effort estimates.

**Key Dependencies:**
- CAP 1 (Literature Mapping) blocks CAP 3 (Hypothesis) — cannot ground hypotheses without map
- CAP 3 (Hypothesis Agent) blocks CAP 5 (Proposal) — cannot generate proposals without hypotheses
- Data stores (vector DB, metadata DB) block most improvements
- LLM client must be production-ready before agents implemented

---

### PHASE 0: Foundation & Data Layer (1-2 weeks)

**Goal:** Establish missing data stores and MCP wrappers; enable local execution.

#### 0.1: Vector Store Service (VectorStoreTool)

**Deliverables:**
- `services/vector_store/service.py` — Chroma client wrapper
  - `index(texts, metadata) → embeddings_ids`
  - `query(query_text, top_k) → [(chunk_id, score, text)]`
  - Uses sentence-transformer (`all-MiniLM-L6-v2` open-source model)
- `services/vector_store/tool.py` — MCPTool wrapper
  - Manifest with input/output schemas
- `services/vector_store/schemas.py` — VectorIndexRequest, VectorQueryResult
- `tests/test_vector_store.py` — Unit tests + determinism tests
- `infra/docker-compose.yml` — Add Chroma service (port 8000)

**Files Changed:**
- `.env.template` — Add CHROMA_URL env var
- `requirements.txt` — Add `chromadb` + `sentence-transformers`
- `core/mcp/registry.py` — Register VectorStoreTool

**Effort:** 3 days
**Blockers:** None
**Dependencies:** Chroma library stable; sentence-transformer available

**Success Criteria:**
- Service passes unit tests (vector indexing, query consistency)
- E2E test: ingest 5 papers → generate embeddings → rank by semantic similarity (vs lexical baseline)
- Determinism test: same input text → same embedding seed → same ranking

---

#### 0.2: Metadata Store Service (MetadataStoreTool)

**Deliverables:**
- `services/metadata_store/service.py` — SQLite wrapper
  - `insert_paper(paper_metadata) → paper_id`
  - `insert_claim(claim) → claim_id`
  - `query_claims_by_paper(paper_id) → claims[]`
  - `query_claims_by_context(context_id, metric) → claims[]`
- `services/metadata_store/tool.py` — MCPTool wrapper
- `services/metadata_store/schemas.py` — MetadataRequest, MetadataResponse
- `services/metadata_store/schema.sql` — DDL for papers, claims, hypotheses, artifacts
- `tests/test_metadata_store.py` — CRUD tests + query tests
- `infra/init_metadata.sql` — Bootstrap script

**Files Changed:**
- `requirements.txt` — Add `sqlite3` (stdlib, no addition needed)
- `core/mcp/registry.py` — Register MetadataStoreTool

**Effort:** 3 days
**Blockers:** None
**Dependencies:** SQLite built-in

**Success Criteria:**
- Insert 5 papers + 180 claims
- Query claims by paper (verify count)
- Query claims by (context, metric) (verify grouping)
- Persistence: close connection, reopen, verify data intact

---

#### 0.3: LLM Client Production-Readiness

**Current state:** `core/llm/client.py` exists; unclear if fully wired to agents
**Goal:** Ensure local Ollama is required; add model swapping safeguards; instrument token logging

**Deliverables:**
- `core/llm/client.py` — Update
  - Add FAIL_ON_API_FALLBACK enforcement (env var)
  - Add model_name parameter to all LLM calls
  - Add token_usage tracking (input_tokens, output_tokens, total_tokens)
  - Add prompt_version parameter (for Phase 5 audit)
  - Add timeout enforcement
- `core/llm/models.py` — Model registry
  - Available local models (qwen2.5:32b, mistral, llama2)
  - Default model (qwen2.5:32b)
- `tests/test_llm_client.py` — Mock LLM tests (to avoid API calls in CI)

**Files Changed:**
- `.env.template` — Add OLLAMA_REQUIRED=true, MODEL_NAME=qwen2.5:32b
- `infra/docker-compose.yml` — Verify Ollama service config
- `requirements.txt` — Ensure `ollama` client library present

**Effort:** 2 days
**Blockers:** None
**Dependencies:** Ollama running locally in dev/infra

**Success Criteria:**
- Env var check enforces local Ollama (fail if OLLAMA_REQUIRED=true and API unreachable)
- Token usage logged in structured logs for all LLM calls
- Model name captured in execution traces
- CI tests use mock LLM (no real API calls)

---

#### 0.4: Local-Execution Validation

**Goal:** Document and enforce local-first execution

**Deliverables:**
- `SETUP_LOCAL.md` — Developer guide
  - Install Ollama + pull qwen2.5:32b
  - Install Chroma (Docker or pip)
  - Initialize SQLite metadata store
  - Run all tests locally
- `scripts/validate_local_setup.py` — Preflight checker
  - Verify Ollama running
  - Verify Chroma accessible
  - Verify SQLite initialized
  - Verify sentence-transformer cached
- `infra/.env.local` — Example local config
- `.env.template` — Update with all required vars

**Effort:** 1.5 days
**Blockers:** None
**Dependencies:** Documentation

**Success Criteria:**
- New developer can follow SETUP_LOCAL.md and run full pipeline locally in 30 min
- Preflight script catches missing dependencies with clear messages
- CI/CD verifies no external API calls (grep logs for API URLs)

---

### PHASE 1: Improve Deterministic Services & Integration (2-3 weeks)

**Goal:** Increase claim extraction yield, establish data persistence, integrate existing services into unified pipeline.

#### 1.1: Claim Extraction Yield Improvement

**Problem:** Only 3.27% extraction yield (180/~5500 expected claims)

**Root causes identified:**
- PERFORMANCE claims require explicit dataset mention (context tag)
- EFFICIENCY claims require limited verb lexicon
- STRUCTURAL claims filtered as "uninteresting"
- Normalization is harsh (rejects claims without both metric + value)

**Deliverables:**
- `services/extraction/improved_predicates.py` — Expanded claim detection
  - Add comparative claim detection ("X outperforms Y by Z%")
  - Add implicit performance claims (section contains numbers + metric words)
  - Add soft context inference (if "results" or "performance" section, lower dataset requirement)
  - Add passive voice handling ("is achieved", "achieved by")
- `services/normalization/softer_binding.py` — Relaxed normalization
  - Do not reject claims with metric but no value (keep as unquantified claims)
  - Do not reject claims with value but no metric (keep with unit inference)
  - Separate NORMALIZED_FULL vs NORMALIZED_PARTIAL results
- `services/extraction/expanded_lexicon.py` — Verb/keyword lists
  - PERFORMANCE: {achieves, reports, outperforms, reaches, attains, surpasses, demonstrates, shows, obtains, yields, measures, ...}
  - EFFICIENCY: {requires, consumes, takes, costs, scales, memory, GPU, latency, throughput, ...}
  - STRUCTURAL: {uses, proposes, introduces, employs, applies, implements, architecture, method, ...}
- `tests/test_extraction_yield.py` — Golden fixtures
  - 5 papers with 40-50 manually labeled claims per paper
  - Run extraction pipeline, compute recall/precision
  - Target: >50% recall on 5-paper set

**Files Changed:**
- `services/extraction/service.py` — Integrate improved predicates
- `services/normalization/service.py` — Integrate softer binding
- `tests/test_extraction_yield.py` — Add golden fixtures

**Effort:** 4-5 days
**Blockers:** Ground-truth annotation (need 40 labeled claims per paper)
**Dependencies:** PHASE 0 (metadata store for persistence)

**Success Criteria:**
- Extraction yield increases from 3.27% to ≥30% on 5-paper set
- Normalization precision maintained ≥20% (relaxed binding doesn't break accuracy)
- E2E test passes with >100 claims (vs current 180)

---

#### 1.2: Integration of Services into Unified Pipeline

**Current state:** Services exist but not all called in E2E pipeline

**Goal:** Full 9-service pipeline execution with persistence

**Deliverables:**
- `services/orchestrator/mcp_orchestrator.py` — Update pipeline
  ```
  ingestion → context_extraction → extraction → normalization →
  contradiction → belief → [multimodal] → [proposal]
  ```
  Pipeline is configurable (subset of services callable)
- `scripts/e2e_unified_pipeline.py` — E2E runner
  - Input: 5 target papers
  - Execute full 9-service pipeline
  - Save output to metadata store
  - Generate execution trace
- `services/orchestrator/checkpoint.py` — Result caching
  - Save intermediate results after each service
  - Skip re-execution if inputs haven't changed
  - Speeds up iteration during debugging
- `tests/test_unified_pipeline.py` — Integration tests
  - Run full pipeline on 5 papers
  - Verify data flows correctly between services
  - Verify metadata store reflects results

**Files Changed:**
- `services/orchestrator/mcp_orchestrator.py` — Add pipeline definition
- `core/mcp/registry.py` — Ensure all 9 tools registered

**Effort:** 3 days
**Blockers:** PHASE 0 (metadata store, vector store)
**Dependencies:** PHASE 1.1 (improved extraction) optional but recommended

**Success Criteria:**
- E2E pipeline executes all 9 services without errors
- Intermediate results persist in SQLite
- Execution trace includes all 9 tool invocations
- Full pipeline completes <15 minutes for 5 papers (vs current 6.5 sec, but with more services)

---

#### 1.3: RAG Service Upgrade to Semantic Retrieval

**Current state:** Lexical RAG using token overlap

**Goal:** Hybrid RAG: semantic (vector) + lexical fallback

**Deliverables:**
- `services/rag/semantic_rag.py` — New RAG implementation
  - Query embedding via sentence-transformer
  - Find top-k nearest vectors in Chroma (top-50)
  - Fall back to lexical RAG if no vectors present
  - Merge results with weighted scoring (0.7 semantic, 0.3 lexical)
  - Return RAGResult with ranking + evidence snippets
- `services/rag/service.py` — Update to use semantic_rag by default
- `tests/test_semantic_rag.py` — Ranking tests
  - Gold: "accuracy on ImageNet" query
  - Expect high-ranking results about vision tasks
  - Verify lexical RAG would miss semantic relatives

**Files Changed:**
- `services/rag/service.py` — Refactor to call VectorStoreTool
- `services/orchestrator/mcp_orchestrator.py` — Pass ingestion embeddings to vector store

**Effort:** 3 days
**Blockers:** PHASE 0 (vector store tool)
**Dependencies:** None

**Success Criteria:**
- Semantic RAG finds "ImageNet results" when queried "vision task performance"
- Lexical RAG would not find this (no token overlap)
- Ranking quality improves (subjective assessment on 10 queries)
- Falls back to lexical gracefully if vector DB unavailable

---

#### 1.4: Better Evaluation Metrics & Ground Truth

**Current state:** E2E test produces raw counts; no comparison to ground truth

**Goal:** Annotate gold-standard claims, measure extraction precision/recall

**Deliverables:**
- `outputs/gold_standard_claims_5papers.json` — Manual annotation
  - 5 papers × 40 claims each = 200 labeled claims
  - Fields: paper_id, chunk_id, claim_text, claim_type, expected_metric, expected_value, expected_context
  - Format: JSON with clear structure for comparison
- `scripts/compute_extraction_metrics.py` — Evaluation harness
  - Load gold standard
  - Load extracted claims
  - For each gold claim, find best matching extracted claim (string similarity)
  - If match ≥ 0.8 cosine similarity, mark as found
  - Compute: precision, recall, F1 for each claim type
  - Output: per-paper metrics + aggregate
- `tests/test_extraction_metrics.py` — Regression tests
  - Assert extraction recall ≥ 40% and precision ≥ 60%
  - Assert normalization precision ≥ 25%
  - Assert contradiction recall ≥ 50% (require ground-truth contradictions)
- `docs/gold_standard_methodology.md` — Annotation guide
  - How to label claims
  - Inter-annotator agreement expectations
  - QA process

**Effort:** 4-5 days (mostly annotation)
**Blockers:** None (annotation can run in parallel with coding)
**Dependencies:** PHASE 1.1 (improved extraction)

**Success Criteria:**
- 200 claims manually annotated (>90% inter-annotator agreement on subset)
- Extraction metrics computed and logged
- Regression tests pass (benchmarking baseline)

---

### PHASE 2: Contextual Literature Mapping (CAP 1) Implementation (2-3 weeks)

**Goal:** Implement semantic clustering + labeling to enable CAP 1

**Dependency:** PHASE 0 (vector store) + PHASE 1.1 (improved extraction)

#### 2.1: Clustering Service

**Deliverables:**
- `services/clustering/service.py` — Paper clustering
  - Input: papers with embeddings (from VectorStoreTool)
  - Call HDBSCAN on embeddings (min_cluster_size=3)
  - Output: list of clusters with member paper IDs
  - Fallback: if HDBSCAN fails, use k-means with elbow method
- `services/clustering/tool.py` — MCPTool wrapper
- `services/clustering/schemas.py` — ClusteringRequest, ClusterResult
- `tests/test_clustering.py` — Cluster quality tests
  - Verify papers in same cluster have similar topics
  - Verify cluster count is reasonable (5-10 for 50 papers)

**Effort:** 2 days
**Blockers:** PHASE 0 (vector store)
**Dependencies:** `scikit-learn` (HDBSCAN), `numpy`

**Success Criteria:**
- Cluster 50 arXiv papers into 5-10 coherent clusters
- Papers in same cluster share topic keywords
- Deterministic output (same papers → same clusters)

---

#### 2.2: Cluster Labeling Service

**Deliverables:**
- `services/labeling/service.py` — LLM-based cluster labeling
  - Input: cluster of papers (titles, abstracts, keywords)
  - Prompt (constrained): "Label this cluster with 1-3 keywords that describe the research area"
  - Output: cluster_label, confidence
  - Deterministic: use same model/prompt version for reproducibility
- `services/labeling/tool.py` — MCPTool wrapper
- `services/labeling/schemas.py` — LabelingRequest, LabelResult
- `core/llm/prompts/cluster_labeler.txt` — Versioned prompt
  - Template: "Cluster of papers: [titles]. Keywords: [extracted keywords]. Provide 1-3 interpretable labels."
  - Version: v1.0 (tracked in execution trace)
- `tests/test_labeling.py` — Roundtrip tests
  - Label cluster, verify labels are interpretable
  - Verify labels are 1-3 words

**Effort:** 2-3 days
**Blockers:** PHASE 0 (LLM client)
**Dependencies:** None

**Success Criteria:**
- Cluster labeled: "Transformer architectures" or "Vision + language"
- Labels are understandable to researchers
- Prompt version logged in execution trace

---

#### 2.3: ContextualMapping Service Integration

**Deliverables:**
- `services/contextual_mapping/service.py` — Orchestrate clustering + labeling
  - Input: papers with vectors
  - Call clustering service → clusters
  - Call labeling service → labeled clusters
  - Compute cluster statistics (size, diversity)
  - Output: ContextualMapResult (clusters with labels, statistics)
- `services/contextual_mapping/tool.py` — MCPTool wrapper
- `services/contextual_mapping/schemas.py` — ContextualMapResult
- `scripts/map_literature_e2e.py` — E2E mapper
  - Input: 50-paper corpus
  - Execute ingest → embedding → vector store → clustering → labeling
  - Output: visualizable map
- `tests/test_contextual_mapping.py` — Integration tests

**Effort:** 2 days
**Blockers:** PHASE 2.1, PHASE 2.2
**Dependencies:** None

**Success Criteria:**
- 50 papers mapped into 5-8 labeled clusters
- Clusters interpretable (human review confirms)
- Map persisted in JSON (can render later)

---

#### 2.4: Map Visualization (Optional, Low Priority)

**Deliverables:**
- `scripts/visualize_map.py` — Generate Graphviz DOT or Mermaid diagram
  - Input: ContextualMapResult JSON
  - Output: PDF or HTML graph
  - Nodes = papers with titles, Edges = similarity scores
- (Or web dashboard, but deferred to Phase 3)

**Effort:** 1-2 days (optional)
**Blockers:** None
**Dependencies:** `graphviz` or web framework

---

### PHASE 3: Agent Implementation & Hypothesis-Critique Loop (CAP 3) (2-3 weeks)

**Goal:** Implement Hypothesis and Critic agents with full LLM backing

**Dependency:** PHASE 0 (LLM client) + PHASE 1 (improved services) + PHASE 2 (mapping for context)

#### 3.1: Hypothesis Agent Implementation

**Deliverables:**
- `agents/hypothesis/agent.py` — Full implementation
  - Input: HypothesisInput (belief_states[], context, background_knowledge)
  - Process:
    1. Load context (literature map)
    2. Identify key beliefs (high confidence)
    3. Prompt LLM: "Generate 1-2 novel hypotheses that would explain these findings: [beliefs]. For each hypothesis, state assumptions."
    4. Parse output into Hypothesis objects (structured validation)
    5. Ground each hypothesis to source claims (backward-trace belief → normalized claim → source claim)
    6. Compute confidence based on supporting evidence count
  - Output: List[Hypothesis]
  - Deterministic: same beliefs + model → same hypotheses (fixed seed for sampling, if any)
- `core/llm/prompts/hypothesis_generator.txt` — Versioned prompt (v1.0)
  - Template: "You are a research assistant. You will be given consensus findings from literature. Generate novel, testable hypotheses. For each hypothesis: [statement], [assumptions], [cited evidence]."
- `agents/hypothesis/schemas.py` — HypothesisInput, HypothesisOutput
- `tests/test_hypothesis_agent.py` — Unit tests
  - Mock belief states (3 high-confidence, 1 contradiction)
  - Generate hypotheses
  - Verify hypotheses are grounded (have grounding_claim_ids[])
  - Verify confidence_score is derived from evidence count

**Effort:** 3-4 days
**Blockers:** PHASE 0 (LLM client), PHASE 1 (improved beliefs)
**Dependencies:** `json` parsing (stdlib)

**Success Criteria:**
- Agent generates hypotheses given belief states
- Hypotheses are grounded to source claims
- Confidence scores reflect supporting evidence (e.g., n_supporting / (n_supporting + n_contradicting))
- Prompt version logged in execution trace

---

#### 3.2: Critic Agent Implementation

**Deliverables:**
- `agents/critic/agent.py` — Full implementation
  - Input: CritiqueInput (hypothesis, belief_states[], rag_matches[])
  - Process:
    1. Identify assumptions in hypothesis
    2. Query RAG for counter-evidence per assumption
    3. Prompt LLM: "Critique this hypothesis: [hypothesis]. Search for counter-evidence and weak assumptions. [rag_matches provided as context]."
    4. Parse output: counter_evidence[], weak_assumptions[], suggested_revisions[], severity
  - Output: Critique
  - Deterministic: same hypothesis + RAG results + model → same critique
- `core/llm/prompts/critic.txt` — Versioned prompt (v1.0)
  - Template: "You are a critical researcher. Evaluate this hypothesis: [statement]. [assumptions]. Counter-evidence available: [snippets]. Identify: 1) counter-evidence, 2) weak assumptions, 3) fatal flaws."
- `agents/critic/schemas.py` — CritiqueInput, CritiqueOutput
- `tests/test_critic_agent.py` — Unit tests
  - Provide hypothesis with weak assumptions
  - Provide contradicting RAG results
  - Verify critic identifies weak assumptions
  - Verify counter-evidence is cited

**Effort:** 3-4 days
**Blockers:** PHASE 0 (LLM client), PHASE 1 (RAG improved)
**Dependencies:** RAG results must include snippets for context

**Success Criteria:**
- Agent identifies weak assumptions in hypothesis
- Agent finds counter-evidence using RAG
- Critique is specific (not generic dismissal)
- Prompt version logged in execution trace

---

#### 3.3: Hypothesis-Critique Loop Update

**Deliverables:**
- `agents/loop.py` — Full iteration coordinator
  - Current structure exists; flesh out execution
  - Inputs: initial_hypothesis, max_iterations=5, confidence_threshold=0.8
  - Loop:
    1. Hypothesis Agent generates hypothesis
    2. Critic Agent critiques
    3. If severity >= FATAL, mark unsalvageable; return
    4. If confidence >= threshold, stop
    5. Otherwise, prompt Hypothesis Agent: "Revise hypothesis addressing these criticisms: [critique]"
    6. Increment iteration count
    7. Repeat until convergence or max_iterations
  - Output: LoopResult (final_hypothesis, critiques[], iterations_completed, convergence_reason)
- `agents/loop_convergence.py` — Convergence detection
  - If hypothesis edit distance < 0.1 from previous iteration, declare converged
  - Prevent infinite loops
- `tests/test_iteration_loop.py` — E2E loop tests
  - Generate hypothesis → critique → revise → critique again
  - Verify loop terminates

**Effort:** 2 days
**Blockers:** PHASE 3.1, PHASE 3.2
**Dependencies:** None

**Success Criteria:**
- Full hypothesis-critique loop executes
- Loop terminates upon confidence threshold or max_iterations
- Revision history preserved in LoopResult

---

#### 3.4: Agent Integration into Orchestrator

**Deliverables:**
- `services/orchestrator/mcp_orchestrator.py` — Add agent step
  - New pipeline variant:
    ```
    ingestion → ...contradiction → belief → [Hypothesis Agent] → [Critic Agent]
    ```
  - Agents called only if belief_states generated
  - Results persisted in metadata store
- `scripts/e2e_with_agents.py` — E2E test including agents
  - Run 5-paper pipeline through agents
  - Record hypotheses generated, critiques received, revisions made
  - Generate report
- `tests/test_orchestrator_with_agents.py` — Integration tests

**Effort:** 2 days
**Blockers:** PHASE 3.1, PHASE 3.2, PHASE 3.3
**Dependencies:** MetadataStoreTool

**Success Criteria:**
- Full pipeline (ingestion → agents) executes on 5 papers
- Hypotheses generated and critiqued
- Results stored in metadata store
- E2E completes in <30 minutes for 5 papers

---

### PHASE 4: Proposal & Multimodal Integration (CAP 4, CAP 5) (2 weeks)

**Goal:** Integrate multimodal extraction; implement proposal generation

**Dependency:** PHASE 3 (agents) + PHASE 1 (unified pipeline)

#### 4.1: Multimodal Integration into Pipeline

**Deliverables:**
- `services/orchestrator/mcp_orchestrator.py` — Add multimodal step
  - New extraction branch:
    ```
    ingestion → [parallel] extraction service + multimodal service
    ```
  - Multimodal returns ExtractionResult[]
  - Link to claims later if needed
- `scripts/test_multimodal_pipeline.py` — E2E multimodal
  - Run ingestion → multimodal on 5 papers
  - Verify tables extracted
  - Count table rows/columns
- `tests/test_multimodal_pipeline.py` — Integration tests

**Effort:** 1.5 days
**Blockers:** None (multimodal service exists)
**Dependencies:** PHASE 1 (unified pipeline structure)

**Success Criteria:**
- Multimodal step executes and extracts tables
- Results appear in metadata store
- E2E pipeline includes multimodal without errors

---

#### 4.2: Proposal Service Full Implementation

**Deliverables:**
- `services/proposal/service.py` — Full implementation
  - Input: Hypothesis (with grounding_claim_ids[])
  - Process:
    1. Load grounding claims + evidence from metadata store
    2. Synthesize methodology: "Based on these claims: [evidence], outline methodology to test this hypothesis"
    3. Generate expected outcomes: "Predict outcomes if hypothesis holds"
    4. Infer novelty: "This work differs from [related papers] because..."
    5. LLM calls: methodology synthesis, outcomes generation, novelty statement
  - Output: Proposal (with all fields populated)
  - Deterministic: same hypothesis → same proposal (fixed prompt + model)
- `core/llm/prompts/proposal_generator.txt` — Versioned prompt (v1.0)
  - Template: "You are writing a research proposal based on this hypothesis: [statement]. Supporting evidence: [claims]. Outline: 1) Novelty statement, 2) Methodology, 3) Expected outcomes."
- `services/proposal/artifact_formatter.py` — Format output
  - Convert Proposal to Markdown
  - Template: "# [Title]\n\n## Novelty\n[novelty_statement]\n\n## Methodology\n[methodology_outline]..."
  - Output: markdown string ready for PDF export
- `tests/test_proposal_service.py` — Unit tests
  - Provide hypothesis with grounding
  - Generate proposal
  - Verify all fields populated
  - Verify markdown renders without errors

**Effort:** 3-4 days
**Blockers:** PHASE 0 (LLM client), PHASE 3 (agents for grounding)
**Dependencies:** MetadataStoreTool

**Success Criteria:**
- Proposal generated from hypothesis
- All sections (novelty, methodology, outcomes) present and coherent
- Markdown output valid
- Prompt version logged

---

#### 4.3: Markdown/LaTeX Export

**Deliverables:**
- `services/proposal/exporters.py` — Export formats
  - `to_markdown(proposal) → str` — Markdown with citations
  - `to_latex(proposal) → str` — LaTeX with bibliography
- `tests/test_exporters.py` — Format validation
  - Verify Markdown / LaTeX syntax

**Effort:** 1.5 days
**Blockers:** PHASE 4.2
**Dependencies:** `pypandoc` (optional), `latex` (optional)

**Success Criteria:**
- Proposal exports to valid Markdown
- Citations formatted correctly
- LaTeX output compiles (if pypandoc available)

---

### PHASE 5: Human-in-the-Loop & UI (GAP 1.1, 1.2) (2-3 weeks)

**Goal:** User-facing interface and interaction capabilities

**Dependency:** All services + agents (PHASE 0-4)

#### 5.1: CLI Inspection & Control Interface

**Deliverables:**
- `infra/cli/main.py` — Main CLI
  - Commands:
    - `parse <paper.pdf>` — Ingest single paper
    - `map <corpus_dir>` — Build literature map
    - `hypothesize <corpus_dir>` — Generate hypotheses
    - `extract <corpus_dir>` — Extract tables/metrics
    - `status` — Show current session state
    - `inspect <claim_id>` — Trace claim back to source
- `infra/cli/inspect.py` — Provenance tracer
  - Input: claim_id
  - Output: "Claim: [text]. Source: Paper [doi], chunk [id], page [n]. Evidence chain: [beliefs]..."
- `infra/cli/pause_resume.py` — Pipeline control
  - Commands: `pause`, `resume`, `skip <step>`, `redo <step>`
  - State persisted in metadata store (session table)
- `tests/test_cli.py` — CLI integration tests
  - Test each command
  - Verify output format

**Effort:** 3-4 days
**Blockers:** PHASE 0-4 (all services)
**Dependencies:** `click` library for CLI framework

**Success Criteria:**
- User can run `parse <pdf>` and see claims extracted
- User can run `map <dir>` and see clusters
- User can run `inspect <claim>` and see provenance
- CLI is intuitive and help text clear

---

#### 5.2: Web Dashboard (Optional, Lower Priority)

**Deliverables** (sketch only; deferred to future):
- `infra/web/app.py` — FastAPI web interface
  - Routes:
    - `GET /papers` — List papers in current session
    - `GET /papers/<id>/claims` — Claims extracted from paper
    - `GET /claims/<id>/provenance` — Trace to source
    - `POST /hypothesize` — Trigger agent
    - `GET /hypotheses` — List generated hypotheses
    - `GET /map` — Visualized literature map
  - Dashboard: interactive HTML + D3.js for visualizations
- `infra/web/frontend/` — React or Vue frontend

**Effort:** 5-7 days (significant effort; candidate for deferral)
**Blockers:** CLI working first (PHASE 5.1)
**Dependencies:** FastAPI, frontend framework

**Success Criteria** (deferred):
- Dashboard displays literature map as interactive graph
- User can click paper node to see details
- Hypotheses displayed in searchable list

---

### PHASE 6: Evaluation & Observability Improvements (Phase 5 extension) (1 week)

**Goal:** Full evaluation harness and compliance auditing

**Dependency:** All services + metrics from ground truth (PHASE 1.4)

#### 6.1: Comprehensive Evaluation Harness

**Deliverables:**
- `scripts/full_evaluation.py` — Master evaluation script
  - Load 5-paper gold standard
  - Run full pipeline
  - Compute metrics:
    - Extraction recall / precision / F1
    - Normalization precision
    - Contradiction recall
    - Belief calibration (are HIGH_CONFIDENCE beliefs verified?)
    - Hypothesis grounding accuracy (are hypotheses grounded to correct claims?)
    - Proposal quality (manual assessment)
  - Output: `evaluation_report.json` with all metrics
- `scripts/regression_tests.py` — Automated regression
  - Assert metrics >= baseline
  - Fail pipeline if regressions detected
  - Track metrics over time (git-based)
- `tests/test_evaluation_metrics.py` — Metric computation tests

**Effort:** 2 days
**Blockers:** PHASE 1.4 (ground truth)
**Dependencies:** None

**Success Criteria:**
- Evaluation report generated with ≥10 metrics
- Regression baseline established
- CI gates on evaluation metrics

---

#### 6.2: Provenance Audit Tooling

**Deliverables:**
- `scripts/audit_provenance.py` — Full audit runner
  - Load all claims, hypotheses, proposals
  - For each assert provenance chain (claim→paper→chunk)
  - For each hypothesis verify grounding_claim_ids[] are populated
  - For each proposal verify grounding_hypothesis_id is set
  - Output: `provenance_audit.json` (passed/violations)
  - Optional: human review checklist
- `tests/test_provenance_completeness.py` — Automated audit
  - Assert 100% of claims have provenance
  - Assert 100% of hypotheses have grounding

**Effort:** 1 day
**Blockers:** None (extends Phase 5 audit)
**Dependencies:** None

**Success Criteria:**
- Audit detects missing provenance
- All claims in gold standard retrievable via trace

---

### Roadmap Summary Table

| Phase | Goals | Key Deliverables | Effort | Blockers | Success Criteria |
|-------|-------|-------------------|--------|----------|------------------|
| **0** | Foundation & data layer | Vector DB + Metadata DB + LLM client | 1-2 w | None | Local execution works; data stores operational |
| **1** | Service improvements & integration | Improved extraction; unified pipeline; semantic RAG | 2-3 w | Phase 0 | >100 claims extracted; E2E pipeline runs |
| **2** | Contextual mapping (CAP 1) | Clustering + labeling + integration | 2-3 w | Phase 0, 1 | 50 papers in 5-8 clusters; labeled |
| **3** | Hypothesis-critique agents (CAP 3) | Hypothesis + Critic agent full impl; iteration loop | 2-3 w | Phase 0, 1, 2 | Hypotheses generated & critiqued; loop terminates |
| **4** | Proposal + multimodal (CAP 4, 5) | Multimodal integration + proposal service | 2 w | Phase 1, 3 | Tables extracted; proposals generated from hypotheses |
| **5** | Human-in-the-loop (GAP 1.1) | CLI inspection + provisioning for UI | 2-3 w | Phase 0-4 | User can inspect claims; pause/resume pipeline |
| **6** | Evaluation & audit (GAP 1.2, 1.4) | Comprehensive metrics + provenance auditing | 1 w | Phase 1.4 | Evaluation report generated; audit passing |

**Total effort estimate:** 12-17 weeks (3-4 months) for full roadmap

---

## CONCLUSION

### Implementation Readiness Assessment

**Current State (March 16, 2026):** **40-45% of intended design implemented**

**Breakdown by Capability:**
- **CAP 1 (Contextual Literature Mapping):** 5% (lexical RAG only; clustering not implemented)
- **CAP 2 (Contradiction & Consensus Finder):** 70% (core logic works; low extraction yield limits recall)
- **CAP 3 (Hypothesis Generation & Critique):** 5% (schema + loop structure; agent logic is stubs)
- **CAP 4 (Multimodal Evidence Extraction):** 60% (service exists; untested; not integrated)
- **CAP 5 (Grant/Proposal Assistant):** 20% (schema + basic service; synthesis not implemented)

**Breakdown by Design Principle:**
- **Separation of Concerns:** ✅ Mostly aligned
- **Selective Agentic Reasoning:** ⚠️ Aligned in structure; agents are stubs
- **Protocol-First (MCP):** ❌ **CRITICAL GAP:** Data stores (vector DB, metadata DB) not MCP-wrapped
- **Provenance-First Outputs:** ⚠️ Schema ready; confidence rationale missing; traceability works
- **Local-First Execution:** ✅ Designed correctly; implementation pending (Ollama setup)

### Top 3 Blocking Issues

1. **Missing Vector Store (Vector DB Service)** — Blocks CAP 1 (semantic mapping), upgraded RAG service, and semantic clustering. Cannot implement contextualized literature mapping without semantic embeddings. **Impact: HIGH. Effort: 3-4 days (PHASE 0)**

2. **Agent Implementations Are Stubs** — Blocks CAP 3 (hypothesis generation), CAP 5 (proposal generation), and full orchestrator pipeline. Hypothesis and Critic agents have interfaces but zero logic. **Impact: CRITICAL. Effort: 5-8 days (PHASE 3)**

3. **Low Claim Extraction Yield (3.27%)** — Undermines evaluation metrics for CAP 2 (Contradiction & Consensus). Only 180 claims extracted from 5 papers despite ~5,000 expected. Cascading impact on contradiction detection, belief aggregation, and hypothesis grounding. **Impact: CRITICAL. Effort: 4-5 days (PHASE 1)**

### Top 3 Quick Wins (1-2 days each)

1. **Create Metadata DB Service (SQLite MCP wrapper)** — Enables persistent storage for all downstream analysis. No dependencies; high value. **Effort: 3 days. Gives: Persistent session + reproducible pipelines.**

2. **Expand Claim Extraction Lexicon** — Add 20-30 keywords per claim type (PERFORMANCE/EFFICIENCY/STRUCTURAL) to improve yield from 3% → 20%+. Simple predicate expansion; immediate eval improvement. **Effort: 2-3 days. Gives: 10x more claims to work with.**

3. **Connect Existing Services into Unified E2E Pipeline** — Orchestrator exists; services exist; just wire them sequentially with error handling. No new code, just orchestration. **Effort: 2 days. Gives: Reproducible full 9-service execution.**

### Recommended Focus for Next Sprint (2-4 weeks)

**Priority Order:**
1. **PHASE 0 (Foundation):** Build Vector Store + Metadata Store + LLM Client production-readiness
   - Unblocks: CAP 1, CAP 3, CAP 5, better RAG, and all subsequent work
   - Effort: 1-2 weeks
   - Risk: Low (dependency installation + wrapper code)

2. **PHASE 1 (Service Hardening):** Improve extraction yield, integrate services, semantic RAG
   - Unblocks: Better evaluation metrics + pipeline visibility
   - Effort: 2-3 weeks
   - Risk: Medium (needs ground truth annotation; extraction logic tuning has many knobs)

3. **PHASE 3 (Agents):** Implement Hypothesis and Critic agents (parallel to Phase 2)
   - Unblocks: CAP 3, CAP 5, human judgment validation
   - Effort: 2-3 weeks
   - Risk: Medium (LLM prompt engineering; output validation)

### Known Gaps Not in Scope (Future Sprints)

1. **User-level role differentiation** (undergraduate vs. PhD) — Deferred to PHASE 5
2. **Hypothesis/critique loop auto-pause for user review** — Deferred to PHASE 5
3. **Web dashboard** — Deferred beyond PHASE 5
4. **Langfuse integration** — Optional; JSON traces sufficient
5. **Redis session store** — Not needed for MVP; in-process dict adequate
6. **Formal specification of claim condition semantics** (epistemic_relations) — Out of scope for MVP

### Final Assessment

**Researcher-AI is architecturally sound but functionally incomplete.** The five-layer design is solid; deterministic services are well-structured; MCP tool interface is clean. However:

- **Three of five capabilities are <20% implemented** (CAP 1, 3, 5)
- **Critical data stores are missing** (vector DB, metadata DB) breaking the "protocol-first" principle
- **Agent implementations are placeholders** preventing hypothesis + proposal generation
- **Ground truth evaluation is missing** preventing rigorous assessment of recall/precision

**Recommendation:** Execute PHASE 0 + PHASE 1 + PHASE 3 in parallel (12-16 weeks) to reach 75-80% implementation. This unlocks:
- Semantic literature mapping (CAP 1)
- Grounded hypothesis generation (CAP 3)
- Proposal synthesis (CAP 5)
- Human-in-the-loop interaction (all GAPs)
- Comprehensive evaluation

**Beyond that scope:** Web UI (PHASE 5.2), role-based workflows, advanced observability (Langfuse). These are valuable but not blockers for core functionality.

---

**End of Implementation Gaps Analysis**

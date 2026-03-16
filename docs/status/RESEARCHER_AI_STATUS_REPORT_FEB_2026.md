# RESEARCHER-AI STATUS REPORT (FEB 2026)

## 1. Executive Overview

### 1.1 System claim baseline (DESIGN.md + CAPABILITIES.md + README.md)
Researcher-AI is defined as a protocol-first, modular, evidence-bound research system with:
- deterministic MCP tool services,
- selective agentic reasoning only for epistemic tasks,
- orchestrator control without embedded heavy reasoning,
- provenance-first outputs,
- local-first, inspectable execution.

The capability contract defines five locked capabilities:
1. Contextual Literature Mapping
2. Contradiction & Consensus Finder
3. Interactive Hypothesis Generation & Critique
4. Multimodal Evidence Extraction
5. Grant / Proposal Assistant

### 1.2 What was validated in this cycle
Validated artifact set:
- `outputs/brutal_150_audit.json`
- `outputs/brutal_150_summary.md`
- `outputs/determinism_diffs/*`
- weak-tier extraction implementation (`services/extraction/service.py`)
- context stitcher integration test coverage (`tests/test_weak_claim_extraction.py`)

Validation scope: 150-paper real arXiv corpus audit (3 runs/paper in script design; 149 valid papers processed due to 1 skipped PDF parse-hang).

### 1.3 Hard-gate outcomes (measured)
- Determinism: **86.58%** (129 deterministic / 149 valid) → **FAIL** against 95% warning threshold and 100% strict gate
- Zero extraction: **26.67%** (40 / 150) → **PASS** against <40%
- Normalization yield: **5.05%** (28 normalized / 554 extracted) → **FAIL** against ≥10%
- Misbindings: **27** (`ambiguous_numeric_binding`) → **FAIL** for zero-risk target
- Papers processed: **149/150** valid (1 corrupted/skipped)

### 1.4 Architectural health vs functional health
- **Architectural health:** The pipeline layers execute in the designed sequence with schema-constrained interfaces, explicit risk flags, and persisted audit outputs.
- **Functional/scientific health:** Claim normalization and determinism are below required scientific quality thresholds.

**Explicit finding:** The system is architecturally sound but scientifically incomplete.

---

## 2. Architectural Compliance (Phase A Review)

This section maps measured outcomes to DESIGN.md architectural principles.

### 2.1 Deterministic services
- **Design intent:** Deterministic tool execution, stable outputs for identical inputs.
- **Audit result:** **Not met** at target level.
- **Evidence:**
  - Determinism rate: 86.57718120805369% (reported as 86.58%)
  - Deterministic papers: 129/149 valid
  - Nondeterministic papers: 20/149 valid
  - `outputs/determinism_diffs`: 20 files
  - Dominant diff error signature: `'ConsensusGroup' object has no attribute 'get'` on run_1/run_2/run_3 (20 papers × 3 entries)
- **Interpretation:** Determinism failures are dominated by consistent pipeline error behavior in contradiction-stage handling, not minor hash jitter.

### 2.2 Tool replaceability (MCP modularity)
- **Design intent:** Services are independently callable and replaceable through MCP contract boundaries.
- **Audit result:** **Structurally met, quality-limited**.
- **Evidence:** Full staged outputs were produced (`audit.json`, `summary.md`, diff snapshots) without collapsing into a monolithic call path.
- **Constraint:** Replaceability is architecturally preserved, but replacement urgency is high for contradiction serialization robustness.

### 2.3 Orchestrator non-reasoning
- **Design intent:** Orchestrator coordinates graph execution; reasoning remains outside orchestration.
- **Audit result:** **Met in observed run model**.
- **Evidence:** Brutal audit is an explicit deterministic task graph execution (ingestion → extraction → normalization → belief → contradiction), with no free-form orchestrator reasoning field in output artifacts.

### 2.4 Schema boundaries
- **Design intent:** Structured schema IO at each stage.
- **Audit result:** **Partially met**.
- **Evidence:**
  - Rejections are schema-classified (`NoClaimReason`, `NoNormalizationReason`) and counted.
  - Contradiction stage emits object-attribute mismatch errors (`ConsensusGroup` as object used like dict), indicating schema handling bug at one stage boundary.

### 2.5 Provenance integrity
- **Design intent:** Evidence-linked claims and traceable outputs.
- **Audit result:** **Met in extraction path; constrained by low normalized volume**.
- **Evidence:** Claim extraction and normalization counters are preserved per paper; run outputs contain per-paper structured records and per-run errors. Low normalization volume (28 total normalized claims) limits downstream provenance utility for epistemic synthesis.

### 2.6 State isolation
- **Design intent:** Run-level isolation, no hidden mutable global contamination.
- **Audit result:** **Partially met**.
- **Evidence:**
  - Successful deterministic subset (129 papers) indicates stable behavior in most runs.
  - Repeated identical error pattern across 20 papers suggests deterministic failure mode in a specific stage, not random cross-run state bleed.

### 2.7 Registry integrity
- **Design intent:** Tool registry remains coherent and inspectable.
- **Audit result:** **Met functionally with downstream type-handling defect**.
- **Evidence:** Pipeline executes to completion across corpus with aggregate outputs and risk flags; failure signatures are localized rather than registry-wide collapse.

### 2.8 Fail-fast behavior
- **Design intent:** Explicit failure reporting over silent degradation.
- **Audit result:** **Met**.
- **Evidence:**
  - `total_pipeline_errors = 63` surfaced in report.
  - 1 parse-hang paper explicitly marked and skipped.
  - Determinism diffs persisted for all nondeterministic papers.
  - No silent suppression of failure counts.

---

## 3. Capability Evaluation vs CAPABILITIES.md

### 3.A Structured Claim Extraction
- **Measured output:**
  - Avg extracted claims/paper: **3.6933333333333334** (reported 3.69)
  - Zero extraction rate: **26.666666666666668%** (reported 26.67)
  - Total extracted claims: **554**
- **Rejection profile evidence:**
  - `context_missing`: **237,762**
  - `table_fragment_rejected`: **5,949**
  - `no_predicate`: **2,637**
- **Tier-4 weak claim path:** active (`_extract_weak_tier`) with `WeakClaimValidator` and context stitcher call.
- **Assessment:** **Partially achieved**.

### 3.B Normalization & Metric Binding
- **Measured output:**
  - Avg normalized claims/paper: **0.18666666666666668** (reported 0.19)
  - Total normalized claims: **28**
  - Normalization yield: **5.054151624548736%** (reported 5.05)
- **Rejection profile evidence:**
  - `missing_metric`: **1,428**
  - `missing_value`: **123**
  - `ambiguous_numeric_binding`: **27**
- **Assessment:** **Bottlenecked**.

### 3.C Belief Synthesis
- **Measured condition:** Structurally callable in audit path; no catastrophic stage disablement reported.
- **Limitation evidence:** Belief/epistemic depth constrained by only 28 normalized claims over 150-paper corpus.
- **Assessment:** **Underfed but operational**.

### 3.D Epistemic Relations
- **Measured condition:** Stage executes where upstream data is available; contradiction-stage error appears on 20 papers.
- **Evidence:** Determinism diffs show 20 papers with repeated contradiction-stage attribute mismatch.
- **Assessment:** **Architecturally valid, data-limited and error-constrained**.

---

## 4. Brutal 150 Domain Breakdown

Per-domain metrics from `outputs/brutal_150_summary.md` / `outputs/brutal_150_audit.json`:

| Domain | Papers | Determinism % | Avg Extracted | Avg Normalized | Zero Extraction % |
|---|---:|---:|---:|---:|---:|
| astro-ph.* | 8 | 87.50 | 1.125 | 0.000 | 50.00 |
| chem.* | 8 | 100.00 | 1.000 | 0.250 | 50.00 |
| cond-mat.* | 7 | 85.71 | 3.286 | 0.143 | 28.57 |
| cs.AI | 7 | 85.71 | 5.286 | 0.571 | 42.86 |
| cs.CL | 7 | 85.71 | 7.857 | 0.571 | 28.57 |
| cs.CV | 8 | 87.50 | 6.125 | 0.375 | 12.50 |
| cs.DB | 7 | 71.43 | 1.429 | 0.286 | 42.86 |
| cs.DC | 7 | 71.43 | 4.286 | 0.000 | 28.57 |
| cs.LG | 8 | 87.50 | 3.750 | 0.375 | 12.50 |
| cs.NI | 8 | 75.00 | 6.375 | 0.125 | 25.00 |
| cs.RO | 7 | 85.71 | 3.714 | 0.143 | 14.29 |
| cs.SE | 8 | 75.00 | 2.250 | 0.000 | 25.00 |
| econ.* | 8 | 75.00 | 2.250 | 0.000 | 37.50 |
| eess.* | 7 | 100.00 | 4.429 | 0.000 | 28.57 |
| math.* | 7 | 100.00 | 1.143 | 0.000 | 28.57 |
| physics.* | 8 | 100.00 | 2.125 | 0.250 | 12.50 |
| q-bio.* | 7 | 85.71 | 5.571 | 0.286 | 14.29 |
| q-fin.* | 8 | 75.00 | 3.000 | 0.125 | 25.00 |
| stat.* | 7 | 85.71 | 5.286 | 0.286 | 14.29 |
| stat.ML | 8 | 100.00 | 4.250 | 0.000 | 12.50 |

### Worst determinism domains (required highlights)
- `cs.DB`: **71.43%** (5/7 deterministic)
- `cs.DC`: **71.43%** (5/7 deterministic)
- `econ.*`: **75.00%** (6/8 deterministic)
- `q-fin.*`: **75.00%** (6/8 deterministic)

### Why these domains destabilize extraction (evidence-bounded)
Observed in audit artifacts:
- Lower-determinism domains overlap strongly with papers present in `determinism_diffs/*` error set.
- The dominant failure signature in those diffs is contradiction-stage object access mismatch (`ConsensusGroup` attribute error), which propagates as non-deterministic outcome labeling for affected papers.
- Additional extraction stress is visible through high zero-extraction percentages in some low-determinism domains (`cs.DB` 42.86%, `econ.*` 37.50%).

---

## 5. Failure Mode Analysis

### 5.1 Determinism Failures
- Corpus nondeterministic papers: **20** (plus 1 skipped/corrupted paper; total non-deterministic flag count in paper records = 21)
- Determinism rate over valid papers: **86.58%**
- Diff-file count: **20**
- Dominant error pattern from diffs:
  - 20 × `run_1: 'ConsensusGroup' object has no attribute 'get'`
  - 20 × `run_2: 'ConsensusGroup' object has no attribute 'get'`
  - 20 × `run_3: 'ConsensusGroup' object has no attribute 'get'`

Evidence conclusion:
- The primary measured determinism failure driver is contradiction-stage type mismatch handling.

Requested candidate causes check (explicit):
- Regex ordering variance: **not evidenced in diff files**
- Set iteration instability: **not evidenced in diff files**
- Floating normalization drift: **not evidenced in diff files**
- Weak-tier pattern collision: **not evidenced as dominant in diff files**

### 5.2 Context Missing Explosion
- `context_missing` extraction rejections: **237,762** (largest rejection class by wide margin)
- Supporting profile:
  - `table_fragment_rejected`: 5,949
  - `no_predicate`: 2,637

Operational explanation from implementation + metrics:
- Weak-tier extraction now permits context inference but still gates on measurable/metric context signal.
- The observed rejection distribution shows inline/nearby context remains absent for many candidate spans.
- This remains the dominant blocker to broad extraction coverage.

### 5.3 Normalization Bottleneck
- Yield: **5.05%** vs gate **10%**
- Total normalized claims: **28** from **554** extracted
- Root evidence:
  - `missing_metric`: **1,428** (dominant)
  - `missing_value`: **123**
  - `ambiguous_numeric_binding`: **27**

Conclusion:
- Normalization underperformance is metric-context binding constrained, not extraction-volume constrained alone.

### 5.4 Misbindings
- `ambiguous_numeric_binding`: **27**
- Relative position: low absolute count but non-zero
- Risk interpretation:
  - Non-zero misbinding means epistemic relation outputs can be contaminated by wrong metric-value linkage.
  - Must reach zero before high-stakes downstream proposal automation.

---

## 6. Context Stitcher Assessment

### 6.1 Intended objective
Context stitcher was integrated to carry paragraph-level dataset/metric context into weak-tier extraction, reducing context-missing rejections for weak numerical statements.

### 6.2 Implementation status (Tier 4)
Confirmed in `services/extraction/service.py`:
- `_extract_weak_tier` imports and calls `stitch_context(...)`
- uses `get_inferred_dataset(...)`
- checks `has_inferred_performancy_context(...)`
- writes inferred metric into `metric_explicit`

Confirmed in test coverage:
- `tests/test_weak_claim_extraction.py::test_weak_tier_uses_paragraph_dataset_context`
- asserts weak claim subject can inherit dataset context (`ImageNet`) from prior chunk.

### 6.3 Measured impact in current audit
- Extraction coverage gate passed: zero extraction **26.67%** (<40%).
- Normalization remained low: **5.05%**.
- `context_missing` remains extremely high: **237,762**.

### 6.4 Direct assessment
It improved extraction marginally but did not fix metric binding.

---

## 7. Scientific Readiness Assessment

Against original system vision:
- ML benchmark parser: **No** (normalization yield and metric binding remain insufficient)
- Domain-general scientific extractor: **Not yet** (coverage and determinism vary materially by domain)
- Robust epistemic engine: **Structurally yes, data-insufficient in practice**

Explicit status:
- The architecture is production-grade.
- The science layer is still underpowered.

---

## 8. Phase B Readiness Decision (Contextual Mapping + Clustering)

Preconditions vs measured values:
- If normalization yield <10% → sparse clustering inputs: **Current = 5.05%** (true)
- If determinism <95% → loop noise amplification risk: **Current = 86.58%** (true)

Options:
- **Option A:** Fix normalization + determinism first
- **Option B:** Proceed immediately with known sparsity and instability
- **Option C:** Hybrid thresholded progression

**Recommendation: Option C (Hybrid)**
- Raise normalization yield to **≥8%** and determinism to **≥95%** before broad clustering rollout.
- Rationale: avoids full stop while reducing sparse/noisy inputs that would degrade cluster quality and downstream agent loops.

---

## 9. Technical Roadmap Forward

### Track 1 — Determinism Hardening
1. Fix contradiction-stage `ConsensusGroup` object access path (`.get` misuse).
2. Enforce canonical ordering before serialization across all tool outputs.
3. Add deterministic hash-freeze tests per tool boundary.
4. Add corpus-level deterministic replay check in CI for sampled papers.

### Track 2 — Normalization Expansion
1. Expand metric ontology and metric alias resolution breadth.
2. Propagate context across paragraph windows into normalization pre-binding.
3. Add weak-weak claim aggregation pass before normalization.
4. Pull table-linked metric extraction forward to reduce `missing_metric` dominance.

### Track 3 — Domain Calibration
1. Add domain priors for metric lexicon expansion (e.g., econ/q-fin/cs.DB variants).
2. Add section-aware extraction weighting (Methods/Results/Abstract distinctions).
3. Add per-domain rejection dashboards and threshold alerts.

---

## 10. Explicit Exit Criteria

The following measurable goals are required before full Phase B expansion:
1. Determinism ≥ **98%**
2. Misbindings = **0**
3. Zero extraction ≤ **20%**
4. Normalization yield ≥ **10%**
5. Avg normalized claims ≥ **0.4/paper**

Current status against criteria:
- Determinism: 86.58% (not met)
- Misbindings: 27 (not met)
- Zero extraction: 26.67% (not met for this stricter criterion)
- Normalization yield: 5.05% (not met)
- Avg normalized: 0.187/paper (not met)

---

## 11. Appendix

### 11.1 Full Brutal 150 summary table (headline metrics)

| Metric | Value |
|---|---:|
| Total papers requested | 150 |
| Valid papers processed | 149 |
| Corrupted/skipped papers | 1 |
| Deterministic papers (valid set) | 129 |
| Nondeterministic papers (valid set) | 20 |
| Determinism % (valid set) | 86.58 |
| Total extracted claims | 554 |
| Total normalized claims | 28 |
| Avg extracted per paper | 3.693 |
| Avg normalized per paper | 0.187 |
| Zero extraction count | 40 |
| Zero extraction % | 26.67 |
| Zero normalization count | 128 |
| Zero normalization % | 85.33 |
| Normalization yield % | 5.05 |
| Total misbindings | 27 |
| Total pipeline errors | 63 |
| Runtime mean (ms) | 270.912 |
| Runtime std dev (ms) | 130.517 |
| Runtime min (ms) | 42.662 |
| Runtime max (ms) | 676.124 |

### 11.2 Determinism histogram

#### Paper outcome histogram (n=150)
| Outcome | Count | Share % |
|---|---:|---:|
| Deterministic papers | 129 | 86.00 |
| Non-deterministic papers | 20 | 13.33 |
| Corrupted/skipped papers | 1 | 0.67 |

#### Domain determinism-bin histogram (n=20 domains)
| Determinism bin | Domain count |
|---|---:|
| 100% | 5 |
| 90–99.99% | 0 |
| 80–89.99% | 9 |
| 70–79.99% | 6 |
| <70% | 0 |

### 11.3 Top rejection reasons (ranked)

| Rank | Layer | Reason | Count |
|---:|---|---|---:|
| 1 | extraction | context_missing | 237762 |
| 2 | extraction | table_fragment_rejected | 5949 |
| 3 | extraction | no_predicate | 2637 |
| 4 | normalization | missing_metric | 1428 |
| 5 | normalization | missing_value | 123 |
| 6 | extraction | no_number | 120 |
| 7 | extraction | compound_metric | 81 |
| 8 | extraction | hedged_statement | 57 |
| 9 | normalization | ambiguous_numeric_binding | 27 |
| 10 | extraction | non_claim | 12 |
| 11 | extraction | object_missing | 3 |
| 12 | extraction | non_performance_numeric | 3 |

### 11.4 Domain performance matrix
(identical to Section 4 for review convenience)

| Domain | Papers | Determinism % | Avg Extracted | Avg Normalized | Zero Extraction % |
|---|---:|---:|---:|---:|---:|
| astro-ph.* | 8 | 87.50 | 1.125 | 0.000 | 50.00 |
| chem.* | 8 | 100.00 | 1.000 | 0.250 | 50.00 |
| cond-mat.* | 7 | 85.71 | 3.286 | 0.143 | 28.57 |
| cs.AI | 7 | 85.71 | 5.286 | 0.571 | 42.86 |
| cs.CL | 7 | 85.71 | 7.857 | 0.571 | 28.57 |
| cs.CV | 8 | 87.50 | 6.125 | 0.375 | 12.50 |
| cs.DB | 7 | 71.43 | 1.429 | 0.286 | 42.86 |
| cs.DC | 7 | 71.43 | 4.286 | 0.000 | 28.57 |
| cs.LG | 8 | 87.50 | 3.750 | 0.375 | 12.50 |
| cs.NI | 8 | 75.00 | 6.375 | 0.125 | 25.00 |
| cs.RO | 7 | 85.71 | 3.714 | 0.143 | 14.29 |
| cs.SE | 8 | 75.00 | 2.250 | 0.000 | 25.00 |
| econ.* | 8 | 75.00 | 2.250 | 0.000 | 37.50 |
| eess.* | 7 | 100.00 | 4.429 | 0.000 | 28.57 |
| math.* | 7 | 100.00 | 1.143 | 0.000 | 28.57 |
| physics.* | 8 | 100.00 | 2.125 | 0.250 | 12.50 |
| q-bio.* | 7 | 85.71 | 5.571 | 0.286 | 14.29 |
| q-fin.* | 8 | 75.00 | 3.000 | 0.125 | 25.00 |
| stat.* | 7 | 85.71 | 5.286 | 0.286 | 14.29 |
| stat.ML | 8 | 100.00 | 4.250 | 0.000 | 12.50 |

---

## Metric Cross-Check Notes

Manual consistency checks performed against `outputs/brutal_150_audit.json`:
- Determinism % = 129 / 149 × 100 = 86.577181... → 86.58
- Zero extraction % = 40 / 150 × 100 = 26.666666... → 26.67
- Normalization yield % = 28 / 554 × 100 = 5.054151... → 5.05
- Avg extracted/paper = 554 / 150 = 3.693333...
- Avg normalized/paper = 28 / 150 = 0.186666...

No conflicting percentages were retained in this report.
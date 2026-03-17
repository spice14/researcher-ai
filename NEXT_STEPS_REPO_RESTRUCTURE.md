# ScholarOS Next Steps (Repo Analysis + Restructure Plan)

Date: 2026-03-15

This plan is based on the current repository state and aligned with:

- `Design.md`
- `capabilities.md`
- `README.md`
- `IMPLEMENTATION_PLAN.md`

## 1) Current State Summary

## Implemented well

- Core schema + validator foundation is in place (`core/schemas`, `core/validators`).
- MCP primitives and service tool wrappers are present (`core/mcp`, `services/*/tool.py`).
- Deterministic services exist for ingestion, extraction, normalization, contradiction, belief, RAG, context.
- Test suite is substantial and includes architecture/MCP contract checks (`tests/test_architecture_isolation.py`, `tests/test_mcp_contract_enforcement.py`, `tests/test_mcp_contract_integrity.py`).

## Gaps vs target architecture

- Missing `agents/` layer (Hypothesis + Critic runtime implementations are not present).
- Missing `infra/` layer (Docker compose, env templates, reproducible local stack wiring).
- Missing proposal/artifact service (Capability 5 not implemented as a service module).
- Mixed orchestration paths: MCP orchestrator exists, but legacy direct orchestration path also exists (`services/orchestrator/service.py`), which risks architecture drift.
- Generated and audit artifacts are in-repo (`htmlcov`, `.coverage`, `outputs/*`) and should be separated from source-of-truth code/docs.

## 2) Priority Next Steps (Execution Order)

## Step 1: Lock architecture boundaries (1-2 days)

- Make MCP orchestration the only production path.
- Mark `services/orchestrator/service.py` as legacy/deprecated and route all active flows through `services/orchestrator/mcp_orchestrator.py`.
- Add a guard test to fail if any new direct cross-service orchestration path is introduced.

## Step 2: Implement missing Proposal capability (3-4 days)

- Add `services/proposal/`:
  - `service.py`
  - `tool.py`
  - `README.md`
- Ensure schema-first behavior with provenance/citation requirements.
- Add tests: schema compliance, empty-input failure mode, reference completeness checks.

## Step 3: Implement agent runtime layer (1-2 weeks)

- Add `agents/hypothesis/` and `agents/critic/` plus shared loop module.
- Enforce bounded iteration and structured outputs only.
- Ensure every agent output references evidence IDs and passes validators.
- Add tests for loop bounds, schema validity, and grounding presence.

## Step 4: Add infra reproducibility layer (3-5 days)

- Add `infra/` with:
  - `docker-compose.yml`
  - `.env.template`
  - service wiring notes
- Ensure local-first execution for vector store + metadata store.

## Step 5: Raise quality gates (ongoing)

- Increase coverage in weakest areas (extraction/context/normalization).
- Add determinism gating for end-to-end runs as a merge requirement.
- Preserve strict MCP method-name contract checks.

## 3) Repo Restructuring Plan

Target structure (incremental, no risky big-bang move):

```text
ScholarOS/
├── core/
├── services/
│   ├── ingestion/
│   ├── rag/
│   ├── context/
│   ├── extraction/
│   ├── normalization/
│   ├── contradiction/
│   ├── belief/
│   ├── proposal/              # add
│   └── orchestrator/
├── agents/                    # add
│   ├── hypothesis/
│   ├── critic/
│   └── loop.py
├── infra/                     # add
│   ├── docker/
│   └── config/
├── scripts/
├── tests/
├── docs/
└── outputs/                   # runtime artifacts only (not source docs)
```

Restructure rules:

- Keep core architecture docs (`README.md`, `Design.md`, `capabilities.md`, `IMPLEMENTATION_PLAN.md`) at repo root.
- Move historical status reports to `docs/status/`.
- Keep `scripts/` for reproducible utility commands only; archive one-off experiments under `docs/archive/` or remove.
- Keep all generated artifacts out of commits by default.

## 4) Files/Dirs to Remove or Stop Tracking

## Remove generated artifacts from git history moving forward

- `htmlcov/`
- `.coverage`
- `.pytest_cache/`
- all `__pycache__/` directories

## Runtime outputs (keep local, do not track)

- `outputs/brutal_150_audit.json`
- `outputs/brutal_150_metadata.json`
- `outputs/brutal_150_summary.md`
- `outputs/determinism_diffs/`

## Candidate archive/move (not immediate delete)

- `SYSTEM_STATUS_2026_02.md` -> move to `docs/status/`
- `docs/RESEARCHER_AI_STATUS_REPORT_FEB_2026.md` -> move to `docs/status/`
- legacy orchestration module `services/orchestrator/service.py` -> keep temporarily with deprecation notice, then remove after MCP-only cutover is validated.

## 5) Hygiene Actions to Apply Immediately

1. Update `.gitignore` to include coverage, caches, and runtime outputs.
2. Add `docs/status/` and move dated status reports there.
3. Add a short deprecation note in `services/orchestrator/README.md` describing MCP-only direction.
4. Add a CI check that fails if generated artifact folders are staged.
5. Add a CI check for deterministic service pipeline smoke test.

## 6) Suggested 3-Sprint Delivery Plan

## Sprint A

- MCP-only orchestration cutover
- Proposal service scaffold + tests
- `.gitignore` and status-doc reorganization

## Sprint B

- Hypothesis agent implementation + tests
- Critic agent implementation + tests
- Bounded loop orchestration integration

## Sprint C

- `infra/` docker/env setup
- Determinism and coverage hardening
- Remove deprecated orchestration path after green CI window

## Definition of Done for this plan

- `agents/`, `infra/`, and `services/proposal/` exist and are tested.
- Legacy direct orchestration path is removed or fully disabled.
- Generated artifacts are no longer tracked.
- CI enforces MCP contracts, determinism smoke test, and minimum coverage threshold.

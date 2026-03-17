# ScholarOS

**ScholarOS** is an agentic research assistant designed to accelerate and strengthen academic research by automating the most time-consuming and cognitively demanding stages of the research lifecycle—without sacrificing rigor, traceability, or human judgment.

Unlike generic AI chatbots or paper summarizers, ScholarOS treats **research as a structured process**, not a single prompt.

---

## Why ScholarOS Exists

Academic research is slow not because researchers lack intelligence, but because the workflow is inherently high-friction:

- Literature is massive, fragmented, and often contradictory
- Understanding a field requires synthesis, not linear reading
- Hypotheses fail due to unseen counter-evidence, not lack of creativity
- Extracting evidence from papers is manual and error-prone
- Turning ideas into formal artifacts (proposals, drafts) is repetitive and costly

Most AI tools optimize for **text generation**.  
ScholarOS is built to support **research thinking**.

---

## What ScholarOS Does

ScholarOS provides a **one-stop research assistance system** that supports researchers across disciplines and experience levels—from undergraduates to PhD scholars.

At a high level, it enables users to:

- Map and understand research landscapes
- Identify consensus, disagreement, and open questions
- Generate and critically evaluate hypotheses
- Extract structured evidence from papers
- Produce formal research artifacts with provenance

The system is **human-in-the-loop by design** and does not operate autonomously.

---

## Core Capabilities

ScholarOS is built around **five locked core capabilities**, each addressing a critical research bottleneck:

1. **Contextual Literature Mapping**  
   Builds a semantic, clustered overview of related work instead of flat paper lists.

2. **Contradiction & Consensus Finder**  
   Identifies where literature agrees, disagrees, or remains inconclusive.

3. **Interactive Hypothesis Generation & Critique**  
   Uses selective multi-agent reasoning to propose and challenge hypotheses.

4. **Multimodal Evidence Extraction**  
   Converts tables, metrics, and figures from PDFs into structured data.

5. **Grant / Proposal Assistant**  
   Transforms validated hypotheses into proposal-ready research artifacts.

A detailed explanation of each capability is available in  
**`capabilities.md`**.

---

## System Architecture (High Level)

ScholarOS uses a **hybrid architecture**:

- A central **Orchestrator** coordinates execution
- **Deterministic tool services** handle ingestion, retrieval, mapping, extraction, and drafting
- **Selective multi-agent reasoning** is used only where adversarial critique improves outcomes
- All components communicate via a uniform **Model Context Protocol (MCP)** interface

This design avoids monolithic agents while preserving modularity, debuggability, and extensibility.

A full technical breakdown is available in  
**`Design.md`**.

---

## Design Principles

- Research-first, not AI-first
- Evidence-bound outputs with provenance
- Selective agentic reasoning
- Local-first and self-hostable
- Composable, inspectable components
- Human judgment always in control

---

## Intended Users

ScholarOS is designed to be useful across the research spectrum:

- **Undergraduates** learning how to read and reason about research
- **Graduate students** synthesizing literature and designing studies
- **PhD researchers** stress-testing hypotheses and preparing proposals

The system adapts by task intent, not academic title.

---

## Project Status

**Active Development**

- Core architecture and capability definitions are locked
- Environment setup and service scaffolding are in progress
- Initial focus: literature mapping → hypothesis generation → critique loop

The project is currently optimized for **local development and experimentation**.

---

## Repository Structure (High Level)

ScholarOS/
├─ README.md
├─ capabilities.md
├─ Design.md
├─ services/ # Deterministic MCP tool services
├─ agents/ # Hypothesis and Critic agents
├─ infra/ # Docker and infrastructure configs
├─ tests/
└─ docs/

## Non-Goals

ScholarOS explicitly does not aim to:

- Replace researchers or advisors
- Operate autonomously without oversight
- Generate claims without evidence
- Execute experiments automatically
- Optimize for conversational fluency over correctness

## Contributing

This project prioritizes clarity, correctness, and reproducibility.

Contributions are welcome, especially in:

- Literature mapping and clustering
- Evidence extraction and provenance tracking
- Agent reasoning and critique strategies
- Developer tooling and observability

Please open an issue before submitting major changes.

## License

License information will be added as the project stabilizes.

## Summary

ScholarOS is an agentic research system that supports how researchers actually think—by mapping literature, exposing disagreement, stress-testing ideas, extracting evidence, and producing real research artifacts with full traceability.

It is designed to accelerate research without eroding scientific rigor.

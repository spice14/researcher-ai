# ScholarOS — Core Capabilities

This document defines the **core functional capabilities** of **ScholarOS**.

These capabilities are **intentionally locked** for the initial system build.  
They represent the highest-impact, longest-duration pain points in real research workflows and form a coherent, end-to-end research assistance loop.

ScholarOS is not designed to answer isolated questions.  
It is designed to **support the structure of research thinking**: understanding a field, identifying disagreement, forming and testing hypotheses, extracting evidence, and producing formal research artifacts.

---

## Design Intent

Each capability adheres to the following principles:

- **Research-first, not AI-first**: Capabilities mirror how researchers actually work.
- **Evidence-bound**: Outputs must reference source material or explicitly declare uncertainty.
- **Composable**: Capabilities can be used independently or chained together.
- **Role-agnostic**: Useful to undergraduates, graduate students, and PhD researchers.
- **Inspectable**: Inputs, outputs, and assumptions are transparent.

---

## Capability 1: Contextual Literature Mapping

### Description

Contextual Literature Mapping builds a **structured, semantic overview** of the research landscape surrounding a paper, topic, or research question.

Rather than returning a flat list of “related papers,” this capability identifies **conceptual groupings**, highlights major directions in the field, and positions the input paper within that structure.

This capability answers the question:

> _“What does this research space look like, and where does this work belong?”_

### What It Does

- Retrieves semantically related papers using vector similarity
- Clusters papers into conceptually coherent groups
- Labels clusters with interpretable, human-readable summaries
- Identifies influential, representative, and boundary papers
- Produces a structured map of the surrounding literature

### Inputs

- A research paper (PDF, DOI, or arXiv ID), **or**
- A topic description or abstract

### Outputs

- Clustered literature map (structured JSON)
- Cluster labels with representative papers
- Ranked list of related and boundary papers
- Provenance linking clusters to abstracts or text snippets

### Pain Points Addressed

- Difficulty orienting in a new research area
- Manual discovery of related work
- Inability to see how papers relate at a conceptual level

### Non-Goals

- Does not evaluate correctness or quality of results
- Does not summarize each paper in detail
- Does not perform citation-based ranking alone

---

## Capability 2: Contradiction & Consensus Finder

### Description

Contradiction & Consensus Finder analyzes **claims and results across multiple papers** to identify where the literature agrees, where it disagrees, and where evidence is weak or inconclusive.

Scientific disagreement is often implicit and fragmented across papers.  
This capability makes it explicit and structured.

This capability answers the question:

> _“What do researchers actually agree on, and what is still contested?”_

### What It Does

- Extracts claims, findings, and conclusions from papers
- Groups semantically equivalent claims across sources
- Identifies consensus supported by converging evidence
- Flags contradictions supported by conflicting results
- Associates each claim with supporting and opposing evidence

### Inputs

- A set of papers (typically from Literature Mapping)
- Optional focus question or claim of interest

### Outputs

- Structured claim clusters
- Consensus summaries with confidence estimates
- Contradiction reports with cited counter-evidence
- Explicit uncertainty markers where evidence is insufficient

### Pain Points Addressed

- Hidden disagreement in the literature
- Overreliance on single influential papers
- Difficulty identifying genuinely open research problems

### Non-Goals

- Does not resolve contradictions
- Does not perform statistical meta-analysis
- Does not judge which side is “correct”

---

## Capability 3: Interactive Hypothesis Generation & Critique

### Description

This capability supports **hypothesis formation as an iterative, adversarial process**, rather than a one-shot generation task.

It uses a selective multi-agent design:

- A **Hypothesis Agent** proposes literature-grounded hypotheses
- A **Critic Agent** actively challenges them using counter-evidence

This mirrors real research practice: ideas improve through critique, not unchecked generation.

This capability answers the question:

> _“Is this hypothesis novel, defensible, and worth pursuing?”_

### What It Does

- Generates testable hypotheses grounded in existing literature
- Explicitly states assumptions behind each hypothesis
- Searches for counter-examples and conflicting findings
- Produces structured critiques and revisions
- Iterates until confidence thresholds or user intervention

### Inputs

- Literature map and consensus/contradiction outputs
- Optional constraints (scope, feasibility, domain focus)

### Outputs

- Structured hypotheses with:
  - Rationale and assumptions
  - Supporting citations
  - Known risks and counter-evidence
  - Confidence scores
- Revision history showing how critique shaped the hypothesis

### Pain Points Addressed

- Weak or under-challenged hypotheses
- Late discovery of fatal flaws
- Confirmation bias during idea formation

### Non-Goals

- Does not assert hypotheses are correct
- Does not replace experimental validation
- Does not generate speculative claims without evidence

---

## Capability 4: Multimodal Evidence Extraction

### Description

Multimodal Evidence Extraction converts **non-textual research artifacts**—tables, figures, metrics, and captions—into structured, machine-readable data while preserving their context.

Research papers often encode their most important evidence outside of plain text.  
This capability surfaces that evidence explicitly.

This capability answers the question:

> _“What concrete results does this paper actually report?”_

### What It Does

- Extracts tables and numeric results from PDFs
- Preserves links to original captions and page locations
- Normalizes extracted data into structured formats (CSV/JSON)
- Associates extracted evidence with claims it supports

### Inputs

- Research paper PDFs
- Optional page or section constraints

### Outputs

- Structured tables with metadata
- Extracted metrics linked to methods and claims
- Provenance mapping back to source documents

### Pain Points Addressed

- Manual extraction of results for comparison
- Difficulty verifying reported metrics
- Barriers to reproducibility and meta-analysis

### Non-Goals

- Does not rerun experiments
- Does not infer missing data
- Does not interpret results beyond extraction

---

## Capability 5: Grant / Proposal Assistant

### Description

The Grant / Proposal Assistant converts **validated hypotheses and supporting evidence** into structured research artifacts suitable for funding, submission, or formal review.

This capability is intentionally positioned **after hypothesis critique**, ensuring that generated proposals are grounded in defensible ideas.

This capability answers the question:

> _“How do I turn this idea into a formal, fundable research proposal?”_

### What It Does

- Converts hypotheses into proposal-ready narratives
- Articulates novelty based on literature gaps
- Drafts methodology and expected outcomes
- Automatically assembles citations and references
- Produces editable drafts (Markdown / LaTeX)

### Inputs

- Selected hypothesis
- Supporting and opposing evidence
- Optional funding or submission constraints

### Outputs

- Structured proposal drafts
- Explicit novelty and motivation sections
- Evidence-backed methodology outlines
- Fully cited reference lists

### Pain Points Addressed

- Proposal writing overhead
- Translating ideas into formal documents
- Repetitive administrative writing

### Non-Goals

- Does not guarantee funding success
- Does not replace domain expertise
- Does not remove the need for peer review

---

## Capability Integration

The five capabilities form a **closed research loop**:

# ScholarOS: End-to-End Conversion Plan

**From Research Prototype to Production-Grade, Enterprise-Ready, Local-First Agentic AI Platform**

Version: 2.0
Date: 2026-03-22
Status: Approved for Execution

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Target Architecture](#3-target-architecture)
4. [Phase 1 — Ingestion Unification](#4-phase-1--ingestion-unification)
5. [Phase 2 — Structured Knowledge Layer](#5-phase-2--structured-knowledge-layer)
6. [Phase 3 — Graph Construction & Evidence Linking](#6-phase-3--graph-construction--evidence-linking)
7. [Phase 4 — Retrieval Upgrade](#7-phase-4--retrieval-upgrade)
8. [Phase 5 — Agent Runtime](#8-phase-5--agent-runtime)
9. [Phase 6 — Capability Implementation](#9-phase-6--capability-implementation)
10. [Phase 7 — Observability & Evaluation](#10-phase-7--observability--evaluation)
11. [Phase 8 — Research Reasoning Loop](#11-phase-8--research-reasoning-loop)
12. [Local Model Stack](#12-local-model-stack)
13. [Execution Order & Dependencies](#13-execution-order--dependencies)
14. [Risk Register](#14-risk-register)
15. [Acceptance Criteria](#15-acceptance-criteria)

---

## 1. Executive Summary

ScholarOS is a local-first research reasoning engine that transforms academic papers into structured, evidence-bound knowledge and enables iterative scientific reasoning over that knowledge. It is **not** a RAG chatbot. It is **not** a summarization tool. It is a system where bounded AI agents operate on structured, reliable knowledge to produce grounded research artifacts.

This plan converts the current prototype — which has functional but disconnected ingestion pipelines, a flat text-chunk retrieval system, and early-stage agent loops — into a production-grade platform with:

- **Structure-first, source-agnostic ingestion** fusing HTML and PDF into canonical `ResearchDocument` representations
- **Graph-based knowledge** with claims, evidence items, citation links, and support/contradiction edges
- **Multi-index, trust-aware retrieval** replacing the current single-vector cosine search
- **Bounded agent runtime** where agents reason over structured schemas, never raw text
- **Five core capabilities**: Literature Mapping, Consensus/Contradiction Detection, Hypothesis Generation & Critique, Multimodal Evidence Extraction, Proposal Generation

The core architectural insight driving this plan:

> **The system will not be "agentic" because of agents. It will be agentic because agents operate on structured, reliable knowledge.**

Ingestion is not "step 1" — it is the **ground truth layer for everything**. If ingestion produces flat text chunks with no structure, no tables, no references, and no provenance, then every downstream capability degrades to "GPT writing essays."

---

## 2. Current State Assessment

### 2.1 What Works

| Component                                                          | Status           | Location                                                                                         |
| ------------------------------------------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------ |
| PDF text extraction (PyMuPDF + pdfminer fallback)                  | Functional       | `services/ingestion/pdf_loader.py`                                                               |
| Sentence-aware chunking (1000 char, 100 overlap)                   | Functional       | `services/ingestion/service.py`                                                                  |
| Telemetry extraction (metrics/datasets/units)                      | Functional       | `services/ingestion/service.py`                                                                  |
| Embedding (sentence-transformers / Ollama / hash fallback)         | Functional       | `services/embedding/service.py`                                                                  |
| Vector store (Chroma + in-memory fallback)                         | Functional       | `services/vectorstore/service.py`                                                                |
| RAG retrieval (semantic + lexical fallback)                        | Functional       | `services/rag/service.py`                                                                        |
| HTML extraction (ArXiv, PMC, ACL, Generic)                         | Functional (POC) | `html_ingestion_poc/ingestion/html_extractor.py`                                                 |
| Source resolution (arXiv, PMC, DOI, URL)                           | Functional (POC) | `html_ingestion_poc/ingestion/source_resolver.py`                                                |
| Metadata enrichment (Semantic Scholar, OpenAlex, Crossref)         | Functional (POC) | `html_ingestion_poc/ingestion/metadata_enrichment.py`                                            |
| MCP tool interface (14 tools)                                      | Functional       | `services/*/tool.py`                                                                             |
| DAG orchestrator                                                   | Functional       | `services/orchestrator/`                                                                         |
| Schema layer (14 Pydantic models)                                  | Functional       | `core/schemas/`                                                                                  |
| Claim extraction → normalization → contradiction → belief pipeline | Functional       | `services/extraction/`, `services/normalization/`, `services/contradiction/`, `services/belief/` |

### 2.2 Critical Failures

These are not feature gaps — they are architectural breaks that silently corrupt downstream results.

#### F1: Table Extraction Disconnected

`table_extractor.py` works correctly in isolation, but `pdf_service.py` never calls `extract_tables_from_pdf()`. Tables are silently dropped from all ingested documents. **Impact**: Evidence Extraction capability is impossible.

#### F2: Bridge Destroys Structure

`ResearchDocument.to_ingestion_result()` passes only `raw_text` to `IngestionService.ingest_text()`, discarding sections, tables, figures, and references. The HTML pipeline's structural advantage is completely nullified at the integration point. **Impact**: All structure gained from HTML parsing is lost.

#### F3: Two Divergent Sentence Segmenters

`service.py` contains an inline sentence boundary detector (simple). `sentence_segmenter.py` contains a superior implementation with 30+ abbreviation protections. The PDF ingestion path uses the weaker one. **Impact**: Chunk boundaries split mid-sentence, corrupting claim extraction.

#### F4: In-Memory Vector Store Filter Bug

`_matches_filter()` in `vectorstore/service.py` does not handle Chroma's `$in` operator. When the system falls back to in-memory storage, multi-source RAG queries return zero results. **Impact**: Multi-paper retrieval silently fails in development/testing.

#### F5: HTMLExtractor Dispatch Bug

Line 702 of `html_extractor.py` calls `self._get_strategy(resolved.identifier_type)` instead of `self._get_strategy(resolved)`. URL-based routing never activates. DOIs resolving to arxiv.org still use `GenericHTMLExtractor`. **Impact**: Publisher-specific structure extraction fails for DOI-resolved papers.

#### F6: Tables Excluded from Raw Text

`_build_raw_text()` in `html_extractor.py` excludes tables from text assembly. Table content is never embedded, never searchable, never retrievable. **Impact**: Quantitative evidence invisible to retrieval.

#### F7: PaperStore Disconnected from RAG

`paper_store.py` writes to filesystem (Markdown + JSON). This storage is completely disconnected from Chroma, SQLite, and the embedding pipeline. Papers ingested via HTML never enter the retrieval system. **Impact**: HTML-ingested papers are invisible to all downstream capabilities.

#### F8: Sequential Ollama Embedding

The Ollama embedding path makes O(n) sequential HTTP calls per document. A 50-chunk paper takes 50 round trips. **Impact**: Embedding latency scales linearly; unusable for batch ingestion.

### 2.3 Architectural Gaps

| Gap                    | Description                                                                      |
| ---------------------- | -------------------------------------------------------------------------------- |
| No unified ingestion   | PDF and HTML pipelines produce different outputs with no merge point             |
| No source fusion       | System chooses one source; cannot combine HTML structure with PDF coverage       |
| No graph layer         | Claims exist but are not linked into citation/evidence/contradiction graphs      |
| No trust scoring       | All chunks treated equally regardless of extraction confidence                   |
| No structured chunking | Chunks are positional text slices, not section-aware semantic units              |
| No figure handling     | Figures extracted by HTML pipeline but never processed or linked                 |
| No OCR                 | Scanned PDFs produce empty text; no fallback                                     |
| Flat retrieval         | Single cosine-similarity vector search with no re-ranking or multi-index support |
| No federated retrieval | Cannot discover related papers from external sources during analysis             |

---

## 3. Target Architecture

```
Identifier (DOI / arXiv ID / PMCID / URL / local PDF)
  |
  v
Source Resolver
  |
  v
+-------------------+     +-------------------+
| HTML Extractor    |     | PDF Extractor     |
| (publisher-aware) |     | (PyMuPDF + OCR)   |
+-------------------+     +-------------------+
          |                         |
          v                         v
     Quality Scoring + Source Fusion
                    |
                    v
          ResearchDocument (canonical truth)
                    |
                    v
          Structured Chunking (section-aware)
                    |
      +-------------+-------------+
      |             |             |
      v             v             v
  Embedding    Graph Build    Metadata Store
  + Vector     (claims,       (SQLite)
    Store      evidence,
  (Chroma)     citations)
      |             |             |
      +-------------+-------------+
                    |
                    v
          Multi-Index Retrieval (trust-aware)
                    |
                    v
          Agent Runtime (Planner → Executor → Critic → Synthesizer)
                    |
                    v
          Capabilities (1-5)
                    |
                    v
          Observability (traces, provenance, determinism audit)
```

### 3.1 Architectural Principles

1. **Structure-first, source-agnostic**: The system constructs the most accurate structured representation from all available sources. It does not "choose HTML or PDF" — it fuses them.

2. **Agents only for reasoning**: Agents operate exclusively on structured schemas. Parsing, extraction, chunking, and retrieval are deterministic services. Agents never see raw text.

3. **Evidence-bound**: Every claim, hypothesis, and proposal traces back to specific text spans in specific papers. No floating assertions.

4. **Local-first**: All core processing runs locally. External APIs (Semantic Scholar, OpenAlex, Crossref) are used only for metadata enrichment, never for core reasoning.

5. **Deterministic where possible**: Given identical inputs, services produce identical outputs. Only agent LLM calls introduce non-determinism, and those are bounded, logged, and versioned.

6. **No service imports another service**: All data flows through the orchestrator via MCP tool invocations. This eliminates hidden state and enables full traceability.

---

## 4. Phase 1 — Ingestion Unification

**Goal**: Produce a single, high-quality `ResearchDocument` from any input source (DOI, arXiv ID, PMCID, URL, local PDF) by fusing HTML and PDF extraction.

**Precondition**: None. This is the foundation.

**Duration estimate removed per project guidelines — scope defined by deliverables below.**

### 4.1 Promote Source Resolver to Production

**Current state**: `html_ingestion_poc/ingestion/source_resolver.py` (274 lines) resolves identifiers to `ResolvedSource` objects with `html_url`, `pdf_url`, `api_urls`.

**Actions**:

1. Move `source_resolver.py` from `html_ingestion_poc/ingestion/` to `services/ingestion/source_resolver.py`
2. Add PDF-path resolution for local files: if input is a filesystem path, set `pdf_url = file:///path` and skip HTML resolution
3. Add arXiv HTML URL pattern: `https://arxiv.org/html/{arxiv_id}` (now available for most papers)
4. Add timeout configuration (current hardcoded 10s per API call)
5. Add `ResolvedSource.available_sources -> List[str]` property listing which sources were found

**Schema**:

```python
class ResolvedSource(BaseModel):
    identifier: str           # Original input
    identifier_type: str      # "arxiv", "pmc", "doi", "url", "local_pdf"
    html_url: Optional[str]
    pdf_url: Optional[str]
    api_urls: Dict[str, str]  # {"semantic_scholar": url, "openalex": url, ...}
    resolved_at: datetime
```

### 4.2 Fix HTML Extraction Bugs

**Actions**:

1. **Fix dispatch bug** (F5): Change `_get_strategy(resolved.identifier_type)` to `_get_strategy(resolved)` so URL-based routing activates for DOI-resolved papers
2. **Fix table inclusion** (F6): Modify `_build_raw_text()` to include table content as markdown within section text, preserving position
3. **Fix PMC nested paragraphs**: Change `recursive=False` to `recursive=True` in PMC section paragraph extraction
4. **Fix relative figure URLs**: Resolve `img.get("src")` against the base URL of the document
5. **Add ACL full-text support**: ACL landing pages have no full text — detect this and mark `quality_score` accordingly so PDF fallback triggers
6. **Activate publisher stubs**: Implement Nature, Science, Springer, PMLR extractors (currently stubs)

### 4.3 Fix PDF Extraction Bugs

**Actions**:

1. **Unify sentence segmenter** (F3): Replace the inline segmenter in `service.py` with `sentence_segmenter.py`'s `SentenceSegmenter` class
2. **Integrate table extraction** (F1): Have `pdf_service.py` call `extract_tables_from_pdf()` and attach results to output
3. **Fix spaceless text repair**: The `_repair_spaceless_text()` function in `pdf_loader.py` mangles acronyms (e.g., "BERT" → "B E R T"). Add an acronym-preservation pass
4. **Fix arXiv header stripping**: Broaden the pattern match in `_strip_arxiv_header()` to handle variant header formats
5. **Remove 200-page cap**: The pdfminer fallback silently truncates at 200 pages. Replace with a configurable limit
6. **Add content-addressed chunk IDs**: Replace positional `{source_id}_chunk_{index}` with `sha256(source_id + text)[:12]` for idempotent re-ingestion

### 4.4 Build Source Fusion Layer

This is the critical new component. It merges HTML and PDF extractions into a single best-possible `ResearchDocument`.

**Location**: `services/ingestion/source_fusion.py`

**Algorithm**:

```
1. Resolve source → get html_url, pdf_url
2. Extract HTML → ResearchDocument_html (if html_url available)
3. Extract PDF  → ResearchDocument_pdf  (if pdf_url available)
4. Score each source independently:
   - section_score:    count(sections with >100 chars) / expected_sections
   - table_score:      count(tables) / expected_tables (from metadata)
   - reference_score:  count(references) / expected_references (from metadata)
   - figure_score:     count(figures)
   - text_coverage:    len(raw_text) / expected_length
   - metadata_score:   count(non-empty metadata fields) / total_fields
5. Conflict detection (CRITICAL — must run before merge):
   a. Section conflict: both sources have same section but text differs by >30%
      → flag, keep both with source labels, downgrade confidence
   b. Table conflict: same table position but different cell values
      → keep source with higher table_score, mark other as "unverified"
   c. Reference conflict: different reference counts
      → take the longer list, log delta
   d. Metadata conflict: different titles, authors, or abstracts
      → prefer metadata-enriched source, flag discrepancy
6. Merge strategy:
   a. If only one source available → use it
   b. If both available, no conflicts:
      - Take sections from higher section_score source
      - Take tables from higher table_score source
      - Take references from higher reference_score source
      - Take figures from source that has them
      - For raw_text: use longer version if delta > 20%
      - Metadata: non-destructive merge (fill empty fields)
   c. If both available, WITH conflicts:
      - Apply conflict resolution per type (above)
      - Downgrade overall quality_score by (conflict_count * 0.05)
      - Set extraction_provenance.has_conflicts = True
      - Store conflict details in extraction_provenance.conflict_log
7. Output: single ResearchDocument with provenance + conflict report
```

**Conflict output schema**:

```python
class FusionConflict(BaseModel):
    conflict_type: str          # "section_text", "table_data", "metadata", "reference_count"
    location: str               # Section title or table index
    html_value_summary: str     # Brief description of HTML version
    pdf_value_summary: str      # Brief description of PDF version
    resolution: str             # "html_preferred", "pdf_preferred", "both_kept", "flagged"
    confidence_impact: float    # How much this conflict reduces overall confidence
```

**Quality thresholds** (per publisher):

| Publisher | Min Sections | Min Tables | Min References | Min Text Length |
| --------- | ------------ | ---------- | -------------- | --------------- |
| arXiv     | 4            | 0          | 10             | 2000            |
| PMC       | 5            | 1          | 15             | 3000            |
| ACL       | 4            | 1          | 15             | 2000            |
| Generic   | 2            | 0          | 0              | 1000            |

If the fused document falls below thresholds, log a warning with specific deficiencies. If conflicts were detected, include them in the warning.

### 4.5 Fix the Bridge (F2)

**Current state**: `ResearchDocument.to_ingestion_result()` flattens everything to `raw_text` and discards structure.

**Action**: Replace `to_ingestion_result()` with a proper pipeline integration:

```python
class ResearchDocument:
    def to_structured_chunks(self) -> List[StructuredChunk]:
        """Convert sections, tables, figures into typed chunks with provenance."""
        chunks = []
        for section in self.sections:
            chunks.extend(self._chunk_section(section))
        for table in self.tables:
            chunks.append(self._table_to_chunk(table))
        for figure in self.figures:
            chunks.append(self._figure_to_chunk(figure))
        return chunks
```

The old `to_ingestion_result()` method that calls `IngestionService.ingest_text()` with flat `raw_text` must be **removed**, not deprecated.

### 4.6 Connect PaperStore to RAG Pipeline (F7)

**Current state**: `paper_store.py` writes to filesystem. Nothing reaches Chroma or embedding.

**Action**: After source fusion produces a `ResearchDocument`:

1. Generate structured chunks via `to_structured_chunks()`
2. Embed all chunks via `EmbeddingService`
3. Store embeddings in Chroma via `VectorStoreService`
4. Store paper metadata in SQLite via `MetadataStoreService`
5. Optionally persist Markdown/JSON to filesystem for human inspection

The filesystem store becomes a **cache/export layer**, not the primary store.

### 4.7 Phase 1 Deliverables

- [ ] Source resolver promoted to `services/ingestion/`
- [ ] All 6 HTML extraction bugs fixed
- [ ] All 6 PDF extraction bugs fixed
- [ ] Source fusion layer implemented with quality scoring
- [ ] Bridge replaced with `to_structured_chunks()`
- [ ] PaperStore connected to embedding + Chroma + SQLite pipeline
- [ ] End-to-end test: arXiv ID → fused ResearchDocument → structured chunks → embedded → retrievable
- [ ] End-to-end test: local PDF → ResearchDocument → structured chunks → embedded → retrievable

---

## 5. Phase 2 — Structured Knowledge Layer

**Goal**: Replace flat text chunks with typed, section-aware semantic units that preserve document structure.

**Precondition**: Phase 1 complete (source fusion producing `ResearchDocument`).

### 5.1 Structured Chunk Schema

Replace the current `IngestionChunk` (text + positional metadata) with:

```python
class StructuredChunk(BaseModel):
    chunk_id: str                    # Content-addressed: sha256(source_id + text)[:12]
    source_id: str                   # Paper identifier
    chunk_type: ChunkType            # SECTION_TEXT, TABLE, FIGURE_CAPTION, ABSTRACT, REFERENCE_LIST
    text: str                        # Chunk content
    section_title: Optional[str]     # "3.2 Experimental Setup"
    section_path: List[str]          # ["3 Methods", "3.2 Experimental Setup"]
    page_numbers: List[int]          # Source pages (may span pages)
    start_char: int                  # Position in source document
    end_char: int
    extraction_source: str           # "html", "pdf", "fused"
    extraction_confidence: float     # 0.0-1.0 quality score
    table_data: Optional[TableData]  # Structured table if chunk_type == TABLE
    figure_url: Optional[str]        # If chunk_type == FIGURE_CAPTION
```

```python
class ChunkType(str, Enum):
    ABSTRACT = "abstract"
    SECTION_TEXT = "section_text"
    TABLE = "table"
    FIGURE_CAPTION = "figure_caption"
    REFERENCE_LIST = "reference_list"
    EQUATION = "equation"
    APPENDIX = "appendix"
```

### 5.2 Section-Aware Chunking

**Current state**: `_sentence_chunks()` in `service.py` chunks by character count (1000 chars, 100 overlap) with no awareness of section boundaries.

**New approach**:

1. Chunk within sections — never cross section boundaries
2. If a section exceeds `max_chunk_size`, split at sentence boundaries using the unified `SentenceSegmenter`
3. Tables become their own chunks (type `TABLE`) regardless of size
4. Abstracts become a single chunk (type `ABSTRACT`)
5. Figure captions become their own chunks (type `FIGURE_CAPTION`)
6. Reference lists are chunked separately (type `REFERENCE_LIST`)
7. Each chunk carries its `section_path` for hierarchical context

**Location**: `services/ingestion/structured_chunker.py`

```python
class StructuredChunker:
    def __init__(self, max_chunk_size: int = 1000, chunk_overlap: int = 100):
        self._segmenter = SentenceSegmenter()
        self._max_size = max_chunk_size
        self._overlap = chunk_overlap

    def chunk(self, doc: ResearchDocument) -> List[StructuredChunk]:
        chunks = []
        chunks.append(self._abstract_chunk(doc))
        for section in doc.sections:
            chunks.extend(self._section_chunks(section, doc.source_id))
        for table in doc.tables:
            chunks.append(self._table_chunk(table, doc.source_id))
        for figure in doc.figures:
            chunks.append(self._figure_chunk(figure, doc.source_id))
        if doc.references:
            chunks.extend(self._reference_chunks(doc.references, doc.source_id))
        return chunks
```

### 5.3 Claim System (Core Intelligence Unit)

The claim is the **primary unit of intelligence** in ScholarOS — not the chunk, not the embedding, not the paper. Every downstream capability (consensus detection, hypothesis generation, proposal grounding) operates on claims. If the claim representation is wrong, everything above it is wrong.

This section defines the complete claim system: schema, extraction pipeline, normalization, and clustering.

#### 5.3.1 Claim Schema

```python
class Claim(BaseModel):
    claim_id: str                           # Content-addressed: sha256(canonical_text + source_id)[:12]
    source_id: str                          # Paper that contains this claim
    chunk_id: str                           # StructuredChunk this claim was extracted from

    # Core claim structure (subject-relation-object, not free text)
    canonical_text: str                     # Normalized claim text
    original_text: str                      # Exact text as it appeared in the source
    subject: str                            # What entity is being described ("BERT", "ResNet-50")
    relation: str                           # What is being asserted ("achieves", "outperforms", "requires")
    object: str                             # The assertion value ("94.2% accuracy", "less memory")

    # Conditions that scope the claim (without these, contradictions are fake)
    conditions: ClaimConditions
    claim_type: ClaimType                   # PERFORMANCE, EFFICIENCY, STRUCTURAL, METHODOLOGICAL, LIMITATION

    # Provenance
    section_context: str                    # "Results" / "Methods" / "Discussion" / "Abstract"
    section_path: List[str]                 # Full hierarchical path
    page_numbers: List[int]
    extraction_method: str                  # "rule_based", "llm_extracted", "table_parsed"
    extraction_confidence: float            # 0.0-1.0

    # Evidence linkage (populated by evidence linking engine, not at extraction time)
    evidence_ids: List[str] = []
    supporting_chunk_ids: List[str] = []

    # Temporal
    extracted_at: datetime
    paper_year: Optional[int]               # Publication year of source paper

class ClaimConditions(BaseModel):
    """Conditions that scope a claim. Two claims about 'accuracy' are only
    comparable if their conditions overlap. Without this, contradiction
    detection produces false positives."""
    dataset: Optional[str]                  # "ImageNet", "GLUE", "SQuAD"
    metric: Optional[str]                   # "accuracy", "F1", "BLEU"
    method: Optional[str]                   # "fine-tuning", "zero-shot", "few-shot"
    baseline: Optional[str]                 # What is being compared against
    scale: Optional[str]                    # "7B parameters", "100K samples"
    additional: Dict[str, str] = {}         # Catch-all for domain-specific conditions
```

#### 5.3.2 Multi-Source Claim Extraction Pipeline

Claims are extracted from **three distinct sources**, each requiring different logic:

**A. Text-based extraction** (from `SECTION_TEXT` and `ABSTRACT` chunks):

```
1. Sentence segmentation (using unified SentenceSegmenter)
2. Claim sentence detection:
   - Pattern matching: sentences containing metrics, comparisons, assertions
   - Patterns: "achieves X%", "outperforms", "improves by", "requires N",
     "we find that", "results show", "our method"
   - Section-aware weighting: Results/Conclusions sentences weighted higher
     than Introduction/Related Work
3. Subject-relation-object extraction:
   - Rule-based first: regex patterns for "X achieves Y on Z"
   - LLM fallback: for complex or ambiguous sentences, use local LLM
     with structured output constraint (must return Claim schema)
4. Condition extraction:
   - Detect dataset mentions (known dataset list + NER)
   - Detect metric mentions (known metric list + unit detection)
   - Detect method/baseline mentions from surrounding context
5. Confidence scoring:
   - Rule-based extraction: 0.8-0.95 (high confidence patterns)
   - LLM extraction: 0.5-0.8 (depends on output validation)
   - Deductions: -0.1 if no conditions detected, -0.1 if from Introduction
```

**B. Table-based extraction** (from `TABLE` chunks):

```
1. Parse table structure: headers, rows, columns
2. Identify table type:
   - Results table: headers contain metric names (Accuracy, F1, BLEU, etc.)
   - Comparison table: rows are methods/models, columns are metrics
   - Configuration table: skip (no claims)
3. For each data cell in a results/comparison table:
   - Subject = row header (model/method name)
   - Relation = "achieves" (or "reports" for passive)
   - Object = cell value + column header (metric)
   - Conditions.dataset = from table caption or column sub-header
   - Conditions.metric = column header
   - Conditions.method = row header or table context
4. Bold/underlined values → mark as "best result" in claim metadata
5. Confidence: 0.9 (tables are explicit, low ambiguity)
```

**C. Caption-based extraction** (from `FIGURE_CAPTION` chunks):

```
1. Detect quantitative captions: "Figure 3 shows that X outperforms Y"
2. Extract claims using same text pipeline as (A) but with higher
   confidence for figure-backed assertions (evidence is visual)
3. Link to figure_url for provenance
4. Confidence: 0.7-0.85 (captions summarize, may oversimplify)
```

**Location**: `services/extraction/claim_extractor.py`

#### 5.3.3 Claim Normalization

Different papers phrase the same claim differently. Without normalization, contradiction detection produces duplicate clusters and misses real conflicts.

```
"BERT achieves 94.2% accuracy on SQuAD"
"Our model reaches 94.2 accuracy (SQuAD v2)"
"Accuracy of 94.2% was obtained using BERT"
→ All normalize to the same canonical form
```

**Normalization pipeline**:

```
1. Canonicalize subject: resolve aliases → canonical entity name
   - "our model" / "the proposed method" → resolve from paper title/abstract
   - "BERT-large" / "BERT (large)" → "BERT-large"
   - Maintain an alias registry (grows as papers are ingested)

2. Canonicalize metric: normalize metric names
   - "acc" / "accuracy" / "top-1 accuracy" → "accuracy"
   - "F-score" / "F1" / "F-measure" → "f1"
   - Maintain a metric synonym table

3. Canonicalize dataset: normalize dataset names
   - "SQuAD v2" / "SQuAD 2.0" / "SQuADv2" → "squad_v2"
   - "ImageNet-1K" / "ILSVRC-2012" → "imagenet_1k"
   - Maintain a dataset synonym table

4. Normalize value: standardize numeric values
   - "94.2%" → 0.942
   - "12.3 BLEU" → 12.3
   - Preserve original string for display

5. Generate canonical_text from normalized components:
   - "{subject} {relation} {value} {metric} on {dataset} [{method}]"
```

**Location**: `services/normalization/claim_normalizer.py` (extends existing `services/normalization/`)

#### 5.3.4 Claim Clustering

After normalization, group semantically equivalent claims for cross-paper analysis:

```
1. Embedding-based clustering:
   - Embed canonical_text of each claim
   - Cluster using HDBSCAN (already available) with min_cluster_size=2
   - Each cluster = a "claim topic" (e.g., "BERT accuracy on SQuAD")

2. Condition-aware refinement:
   - Within each embedding cluster, split by conditions
   - Claims about the same metric on DIFFERENT datasets → separate sub-clusters
   - Claims about the same metric on the SAME dataset → same sub-cluster
   - This prevents false contradictions

3. Output: ClaimCluster objects
```

```python
class ClaimCluster(BaseModel):
    cluster_id: str
    canonical_topic: str              # "accuracy on squad_v2"
    claims: List[str]                 # claim_ids in this cluster
    condition_signature: str          # Hash of shared conditions (dataset + metric)
    consensus_score: float            # Agreement ratio within cluster
    has_contradiction: bool
    paper_count: int                  # Number of distinct papers
    value_range: Optional[Tuple[float, float]]  # Min/max reported values
```

### 5.4 ResearchDocument Schema Finalization

Promote `html_ingestion_poc/models/research_document.py` to `core/schemas/research_document.py` with these additions:

```python
class ResearchDocument(BaseModel):
    source_id: str
    title: str
    authors: List[str]
    abstract: str
    sections: List[Section]
    tables: List[Table]
    figures: List[Figure]
    references: List[Reference]
    metadata: DocumentMetadata
    extraction_provenance: ExtractionProvenance  # NEW: which source contributed what
    quality_scores: QualityScores               # NEW: per-dimension quality metrics

class ExtractionProvenance(BaseModel):
    html_source: Optional[str]        # URL used for HTML extraction
    pdf_source: Optional[str]         # URL or path used for PDF extraction
    fusion_strategy: str              # "html_only", "pdf_only", "merged"
    section_source: str               # "html" or "pdf"
    table_source: str
    reference_source: str
    enrichment_apis: List[str]        # ["semantic_scholar", "openalex"]
    has_conflicts: bool = False       # Whether source fusion detected conflicts
    conflict_log: List[FusionConflict] = []  # Detailed conflict records
    extracted_at: datetime

class QualityScores(BaseModel):
    section_score: float
    table_score: float
    reference_score: float
    figure_score: float
    text_coverage: float
    overall: float                    # Weighted composite
```

### 5.5 Phase 2 Deliverables

- [ ] `StructuredChunk` schema defined in `core/schemas/`
- [ ] `StructuredChunker` implemented with section-aware splitting
- [ ] `ResearchDocument` promoted to `core/schemas/` with provenance, quality scores, and conflict log
- [ ] `Claim` schema defined with subject-relation-object structure and `ClaimConditions`
- [ ] Multi-source claim extraction implemented (text, table, caption pipelines)
- [ ] Claim normalization pipeline (subject/metric/dataset canonicalization, value standardization)
- [ ] Claim clustering with condition-aware refinement
- [ ] Metric synonym table and dataset synonym table seeded with common entries
- [ ] Old `IngestionChunk` → `StructuredChunk` migration path (backward-compatible read)
- [ ] Test: document with 5 sections + 3 tables → structured chunks preserve section boundaries and table integrity
- [ ] Test: results table with 5 rows × 3 metrics → 15 claims extracted with correct conditions
- [ ] Test: 3 papers about same topic → claims cluster correctly by condition signature

---

## 6. Phase 3 — Graph Construction & Evidence Linking

**Goal**: Build a knowledge graph from structured chunks, claims, and citations that enables cross-paper reasoning. Critically, this phase also implements the **Evidence Linking Engine** (connecting claims to their supporting evidence with concrete alignment logic) and the **Belief State Layer** (tracking system confidence in each claim over time).

These three components — graph, evidence linking, belief state — must be designed together. If designed independently, they will fracture: the graph won't know which edges carry weight, retrieval won't know which claims to trust, and agents won't know what the system currently believes.

**Precondition**: Phase 2 complete (structured chunks with section context + claim system).

### 6.1 Graph Schema

```python
# Nodes
class PaperNode(BaseModel):
    paper_id: str
    title: str
    year: int
    venue: Optional[str]
    ingested_at: datetime

class ClaimNode(BaseModel):
    claim_id: str
    paper_id: str
    canonical_text: str
    claim_type: ClaimType
    conditions: ClaimConditions
    section_context: str            # "Results" / "Methods" / "Discussion"
    extraction_confidence: float

class EvidenceNode(BaseModel):
    evidence_id: str
    paper_id: str
    chunk_id: str
    evidence_type: str              # "table_cell", "text_span", "figure_reference"
    content: str
    normalized_value: Optional[float]  # Standardized numeric value if applicable
    normalized_metric: Optional[str]   # Canonical metric name
    confidence: float

# Edges
class CitationEdge(BaseModel):
    citing_paper_id: str
    cited_paper_id: str
    citation_context: str           # Text around the citation
    citation_intent: str            # "supports", "extends", "contradicts", "background"

class SupportEdge(BaseModel):
    evidence_id: str
    claim_id: str
    alignment_method: str           # "exact_match", "metric_match", "semantic_match"
    strength: float                 # 0.0-1.0

class ContradictionEdge(BaseModel):
    claim_a_id: str
    claim_b_id: str
    contradiction_type: str         # "direct", "conditional", "methodological"
    condition_overlap: float        # How much the conditions actually overlap (0.0-1.0)
    resolution: Optional[str]       # "different_datasets", "different_metrics", etc.
```

### 6.2 Evidence Linking Engine

This is where most systems fail. "Link claims to evidence" is easy to say and hard to implement correctly. The evidence linking engine must connect extracted claims to their concrete supporting data — not via LLM guessing, but via deterministic alignment.

**Location**: `services/graph/evidence_linker.py`

#### 6.2.1 Table → Claim Alignment

```
Input: Claim + List[StructuredChunk where chunk_type == TABLE]

Algorithm:
1. For each TABLE chunk, parse structured table data (headers, rows, cells)
2. Match claim.conditions against table context:
   a. claim.conditions.metric → match against column headers
      - Use metric synonym table (e.g., "acc" matches "Accuracy" column)
   b. claim.conditions.dataset → match against table caption or row headers
      - Use dataset synonym table
   c. claim.subject → match against row headers (model names)
3. If match found:
   a. Extract the specific cell value
   b. Compare cell value against claim.object (the claimed value)
   c. If values match (within tolerance ±0.5%): strength = 0.95
   d. If values close but not exact: strength = 0.7, flag discrepancy
   e. If values conflict: create ContradictionEdge instead
4. Create SupportEdge with alignment_method = "exact_match"

Example:
  Claim: "BERT achieves 94.2% accuracy on SQuAD"
  Table row: | BERT | 94.2 | 87.1 | 91.3 |
  Table headers: | Model | Accuracy | F1 | EM |
  → Match: column "Accuracy", row "BERT", value 94.2
  → SupportEdge(strength=0.95, alignment_method="exact_match")
```

#### 6.2.2 Metric Normalization for Alignment

```python
class MetricNormalizer:
    """Normalize metric values for cross-paper comparison."""

    def normalize(self, value_str: str, metric: str) -> Optional[float]:
        """
        Convert metric strings to comparable floats.

        "94.2%" → 0.942 (for percentage metrics)
        "12.3"  → 12.3  (for absolute metrics like BLEU)
        "1.2B"  → 1_200_000_000 (for parameter counts)
        "3.2ms" → 0.0032 (for latency, normalize to seconds)
        """
        # Strip units, detect scale, normalize to canonical form
        ...

    def values_agree(self, v1: float, v2: float, metric: str) -> bool:
        """
        Determine if two values represent agreement or contradiction.

        For percentage metrics: agree if |v1 - v2| < 0.005
        For absolute metrics: agree if |v1 - v2| / max(v1, v2) < 0.02
        For count metrics: agree if v1 == v2
        """
        ...
```

#### 6.2.3 Text Span → Claim Alignment

For non-tabular evidence (text spans that support or reference a claim):

```
1. For each claim, retrieve the surrounding context (±2 sentences)
2. Check for explicit evidence markers:
   - "as shown in Table 3" → link to Table 3 chunk
   - "our results (Figure 2)" → link to Figure 2 chunk
   - "consistent with [Smith et al.]" → link to citation
3. For claims extracted from Results sections:
   - Automatically link to all tables in the same section
   - Weight by proximity (same paragraph > same section > same paper)
4. Create SupportEdge with alignment_method = "semantic_match"
   and lower strength (0.5-0.7) than exact table matches
```

#### 6.2.4 Cross-Paper Evidence Alignment

When the same claim topic exists across multiple papers:

```
1. Identify claims in the same ClaimCluster (from 5.3.4)
2. For each pair of claims with overlapping conditions:
   a. Compare normalized values
   b. If values agree → SupportEdge between their evidence nodes
   c. If values disagree → ContradictionEdge
   d. If conditions partially overlap → flag as "conditional"
      and record which conditions differ
3. Critical: do NOT create contradiction edges between claims
   with non-overlapping conditions (different datasets = not a contradiction)
```

### 6.3 Belief State Layer

The belief state tracks what the system currently "believes" about each claim, based on accumulated evidence. This is what makes ScholarOS a **dynamic reasoning system** instead of a static pipeline.

**Location**: `services/graph/belief_engine.py`

```python
class BeliefState(BaseModel):
    claim_id: str
    canonical_text: str

    # Evidence accounting
    supporting_evidence: List[str]       # evidence_ids that support this claim
    contradicting_evidence: List[str]    # evidence_ids that contradict this claim
    supporting_paper_count: int          # Distinct papers supporting
    contradicting_paper_count: int       # Distinct papers contradicting

    # Computed belief metrics
    confidence: float                    # 0.0-1.0, computed from evidence
    stability: BeliefStability           # HIGH, MEDIUM, UNSTABLE
    epistemic_status: EpistemicStatus    # HIGH_CONFIDENCE, MEDIUM, SUPPORTED, WEAKLY_SUPPORTED, CONTESTED

    # Temporal
    first_seen: datetime                 # When this claim first entered the system
    last_updated: datetime               # Last time evidence changed
    paper_year_range: Tuple[int, int]    # Oldest and newest paper supporting this claim
    trend: BeliefTrend                   # STRENGTHENING, STABLE, WEAKENING, SUPERSEDED

class BeliefStability(str, Enum):
    HIGH = "high"           # >3 supporting, <20% contradiction, stable for >2 updates
    MEDIUM = "medium"       # 2-3 supporting, <40% contradiction
    UNSTABLE = "unstable"   # Recent contradictions added, or flip-flopping

class BeliefTrend(str, Enum):
    STRENGTHENING = "strengthening"  # Recent papers increasingly support
    STABLE = "stable"                # No significant change
    WEAKENING = "weakening"          # Recent papers increasingly contradict
    SUPERSEDED = "superseded"        # Newer method/result has replaced this claim
```

**Belief computation algorithm**:

```
def compute_belief(claim_id, evidence_edges, contradiction_edges):
    support_count = count(support_edges where claim_id matches)
    contradict_count = count(contradiction_edges where claim_id matches)
    total = support_count + contradict_count

    if total == 0:
        return BeliefState(confidence=0.5, stability=UNSTABLE, status=WEAKLY_SUPPORTED)

    support_ratio = support_count / total
    confidence = support_ratio * evidence_quality_weight(supporting_evidence)

    # Temporal adjustment: recent evidence counts more
    recency_weight = compute_recency_weight(evidence_timestamps)
    confidence *= recency_weight

    # Stability: has the belief been fluctuating?
    stability = compute_stability(belief_history)

    # Trend: is the belief getting stronger or weaker over time?
    trend = compute_trend(evidence_timestamps, support_values)

    # Epistemic status thresholds (from existing system)
    if support_count >= 3 and support_ratio >= 0.75 and contradict_count / total < 0.2:
        status = HIGH_CONFIDENCE
    elif support_count >= 2 and support_ratio >= 0.60:
        status = MEDIUM
    elif support_ratio >= 0.75:
        status = SUPPORTED
    elif support_ratio >= 0.40:
        status = WEAKLY_SUPPORTED
    else:
        status = CONTESTED

    return BeliefState(
        confidence=confidence,
        stability=stability,
        epistemic_status=status,
        trend=trend,
        ...
    )
```

### 6.4 Graph Construction Pipeline

**Location**: `services/graph/service.py`

```
Input: ResearchDocument + List[StructuredChunk] + List[Claim]
                                    |
                                    v
                    1. Extract citation edges from references
                       (match references to known paper_ids)
                                    |
                                    v
                    2. Run Evidence Linking Engine (6.2):
                       - Table → Claim alignment
                       - Text span → Claim alignment
                       - Cross-paper evidence alignment
                                    |
                                    v
                    3. Build support/contradiction edges
                       (from evidence linking + ContradictionService)
                                    |
                                    v
                    4. Compute/update BeliefState for each affected claim
                       (6.3 algorithm)
                                    |
                                    v
                    5. Propagate belief changes:
                       - If claim belief changed significantly (>0.1 delta):
                         → mark dependent hypotheses for re-evaluation
                         → update cluster consensus scores
                                    |
                                    v
Output: Updated KnowledgeGraph + BeliefStates + change notifications
```

### 6.5 Citation Resolution

**Current state**: `ResearchDocument.references` contains parsed reference objects, but they are not linked to known papers in the system.

**Action**:

1. For each reference in a `ResearchDocument`, attempt to match against papers already in the system by:
   - DOI exact match
   - arXiv ID exact match
   - Title fuzzy match (Levenshtein distance < 0.15)
   - Author + year match
2. For matched references, create `CitationEdge` records
3. For unmatched references, store as `PendingReference` for future resolution when the cited paper is ingested
4. When a new paper is ingested, check all `PendingReference` records for matches — this is how the citation graph grows retroactively

### 6.6 Storage

The graph is stored in SQLite alongside existing metadata. The schema is designed for **graph-style queries** (multi-hop traversal, neighborhood lookup), not just relational convenience.

```sql
-- Nodes are existing tables (papers, claims)
-- New tables for edges and beliefs:

CREATE TABLE citation_edges (
    citing_paper_id TEXT NOT NULL,
    cited_paper_id TEXT NOT NULL,
    citation_context TEXT,
    citation_intent TEXT,
    PRIMARY KEY (citing_paper_id, cited_paper_id)
);
CREATE INDEX idx_citation_cited ON citation_edges(cited_paper_id);

CREATE TABLE evidence_nodes (
    evidence_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    content TEXT,
    normalized_value REAL,
    normalized_metric TEXT,
    confidence REAL NOT NULL
);
CREATE INDEX idx_evidence_paper ON evidence_nodes(paper_id);
CREATE INDEX idx_evidence_chunk ON evidence_nodes(chunk_id);

CREATE TABLE support_edges (
    evidence_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    alignment_method TEXT NOT NULL,
    strength REAL NOT NULL,
    PRIMARY KEY (evidence_id, claim_id)
);
CREATE INDEX idx_support_claim ON support_edges(claim_id);

CREATE TABLE contradiction_edges (
    claim_a_id TEXT NOT NULL,
    claim_b_id TEXT NOT NULL,
    contradiction_type TEXT NOT NULL,
    condition_overlap REAL,
    resolution TEXT,
    PRIMARY KEY (claim_a_id, claim_b_id)
);
CREATE INDEX idx_contradiction_a ON contradiction_edges(claim_a_id);
CREATE INDEX idx_contradiction_b ON contradiction_edges(claim_b_id);

CREATE TABLE belief_states (
    claim_id TEXT PRIMARY KEY,
    confidence REAL NOT NULL,
    stability TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    trend TEXT NOT NULL,
    supporting_count INTEGER NOT NULL,
    contradicting_count INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    paper_year_min INTEGER,
    paper_year_max INTEGER
);

CREATE TABLE belief_history (
    claim_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    confidence REAL NOT NULL,
    trigger_paper_id TEXT,          -- What paper caused this update
    PRIMARY KEY (claim_id, timestamp)
);

CREATE TABLE pending_references (
    reference_id TEXT PRIMARY KEY,
    citing_paper_id TEXT NOT NULL,
    title TEXT,
    authors TEXT,
    year INTEGER,
    doi TEXT,
    arxiv_id TEXT,
    resolved BOOLEAN DEFAULT FALSE
);
```

SQLite is sufficient for the local-first architecture at thousands of nodes. The indexes above are designed for the specific graph query patterns needed: "find all evidence supporting claim X," "find all claims contradicting claim Y," "get belief history for claim Z."

### 6.7 Phase 3 Deliverables

- [ ] Graph schema defined in `core/schemas/graph.py`
- [ ] Evidence Linking Engine implemented with table→claim, text→claim, and cross-paper alignment
- [ ] `MetricNormalizer` with synonym tables for metrics, datasets, and model names
- [ ] `BeliefState` computation with confidence, stability, and trend tracking
- [ ] `belief_history` table tracking belief changes over time
- [ ] `GraphService` implemented with citation resolution and edge construction
- [ ] SQLite tables created with indexes optimized for graph traversal
- [ ] Pending reference resolution (retroactive citation graph growth)
- [ ] Belief change propagation (significant changes flag dependent hypotheses)
- [ ] Test: paper with results table → claims extracted → evidence linked → belief computed
- [ ] Test: 3 papers, 2 agree on metric, 1 disagrees → correct support/contradiction edges + belief reflects majority
- [ ] Test: new paper ingested → pending references resolved → citation graph updated → beliefs recomputed
- [ ] MCP tool: `graph_query` for traversal queries
- [ ] MCP tool: `belief_query` for current belief state of any claim

---

## 7. Phase 4 — Retrieval Upgrade

**Goal**: Replace single-vector cosine search with multi-index, trust-aware retrieval that leverages document structure and graph relationships.

**Precondition**: Phase 3 complete (graph with citation and evidence edges).

### 7.1 Fix Existing Bugs

1. **Fix in-memory `$in` filter** (F4): Implement `$in` operator support in `_matches_filter()`:

   ```python
   def _matches_filter(metadata: Dict, where: Dict) -> bool:
       for key, value in where.items():
           if isinstance(value, dict) and "$in" in value:
               if metadata.get(key) not in value["$in"]:
                   return False
           elif metadata.get(key) != value:
               return False
       return True
   ```

2. **Fix sequential Ollama embedding** (F8): Batch embedding requests instead of one-at-a-time HTTP calls:
   ```python
   # Current: O(n) sequential calls
   # Target: batch endpoint or parallel async calls with concurrency limit
   ```

### 7.2 Claim-First Multi-Index Retrieval

**The fundamental shift**: The primary retrieval unit is the **claim**, not the chunk. Chunks are evidence containers. Claims are what the system reasons about.

**Current state**: `query → vector search → chunks → hope for relevance`

**Target**: `query → claims → evidence → documents (with belief context)`

```
Query
  |
  v
Query Analysis (detect: is this about a claim, evidence, or topic?)
  |
  +---> [Claim Index] embed query → cosine search over claim embeddings
  |           → top-K claims with belief states
  |           → for each claim: retrieve linked evidence (support_edges)
  |           → for each claim: retrieve linked papers (paper_ids)
  |
  +---> [Evidence Index] BM25 over table cells, metrics, datasets
  |           → direct evidence retrieval for quantitative queries
  |           → "accuracy on ImageNet" → TABLE chunks from Results
  |
  +---> [Chunk Index] cosine similarity over chunk embeddings
  |           → fallback for broad/topical queries
  |           → section-type boosting (query about methods → boost Methods chunks)
  |
  +---> [Graph Index] traverse from matched claims:
  |           → citation neighborhood (what cites this? what does it cite?)
  |           → contradiction neighborhood (what disagrees?)
  |           → claim cluster siblings (other claims in same cluster)
  |
  v
Reciprocal Rank Fusion (k=60)
  |
  v
Belief-Aware Re-ranking
  |
  v
Retrieval Result (claims + evidence + chunks + belief context)
```

**Location**: `services/rag/claim_first_retriever.py`

**Return type**:

```python
class RetrievalResult(BaseModel):
    """Claim-first retrieval returns claims with their evidence context,
    not isolated text fragments."""
    claims: List[ClaimWithContext]        # Primary results
    supporting_chunks: List[StructuredChunk]  # Evidence backing the claims
    related_papers: List[PaperSummary]   # Papers these claims come from
    graph_context: Optional[GraphNeighborhood]  # Surrounding graph structure

class ClaimWithContext(BaseModel):
    claim: Claim
    belief_state: BeliefState            # Current system belief
    evidence: List[EvidenceNode]         # Linked evidence
    source_chunk: StructuredChunk        # Original chunk
    relevance_score: float               # How relevant to the query
```

### 7.3 Belief-Aware Re-ranking

Re-ranking uses the belief state — not just extraction quality — to surface the most reliable results:

```python
def rerank_score(claim: ClaimWithContext, semantic_score: float) -> float:
    belief = claim.belief_state

    # Base: semantic relevance
    score = semantic_score * 0.35

    # Belief confidence: how much does the system trust this claim?
    score += belief.confidence * 0.25

    # Evidence density: claims backed by more evidence rank higher
    evidence_density = min(len(claim.evidence) / 5.0, 1.0)
    score += evidence_density * 0.15

    # Stability: stable beliefs > unstable beliefs
    stability_bonus = {"high": 0.15, "medium": 0.10, "unstable": 0.0}
    score += stability_bonus.get(belief.stability, 0.0)

    # Recency: newer claims get a small boost (research moves forward)
    if belief.trend == "strengthening":
        score += 0.05
    elif belief.trend == "superseded":
        score -= 0.10

    # Contradiction awareness: contested claims are INTERESTING, not bad
    # — surface them but mark clearly
    if belief.epistemic_status == "CONTESTED":
        score += 0.05  # Boost: the user should see contested claims

    return score
```

This is fundamentally different from the v1 trust scoring. It uses the **belief state** (which evolves over time) not just static extraction quality.

### 7.4 Structured Query Support

The `QueryRequest` schema gains claim-first filters:

```python
class QueryRequest(BaseModel):
    query: str
    top_k: int = 10
    source_ids: Optional[List[str]] = None

    # Structural filters
    chunk_types: Optional[List[ChunkType]] = None    # Filter by TABLE, ABSTRACT, etc.
    section_filter: Optional[str] = None              # "Methods", "Results", etc.

    # Claim-first filters
    claim_types: Optional[List[ClaimType]] = None     # PERFORMANCE, STRUCTURAL, etc.
    min_belief_confidence: float = 0.0                # Minimum belief score
    belief_status_filter: Optional[List[str]] = None  # ["HIGH_CONFIDENCE", "CONTESTED"]
    condition_filter: Optional[ClaimConditions] = None # Match claims with specific conditions

    # Graph expansion
    include_graph_context: bool = False                # Expand via graph edges
    include_contradictions: bool = False               # Also return contradicting claims
    graph_hops: int = 1                                # How many hops in graph traversal

    # Retrieval mode
    retrieval_mode: str = "claim_first"                # "claim_first", "evidence_first", "chunk_fallback"
```

### 7.5 Phase 4 Deliverables

- [ ] In-memory `$in` filter bug fixed
- [ ] Ollama embedding batching implemented
- [ ] Claim embedding index (separate from chunk embedding index)
- [ ] Evidence index (BM25 over table cells, metrics, datasets)
- [ ] Claim-first retriever implemented with `RetrievalResult` output
- [ ] Graph-based retrieval (citation neighborhood, contradiction neighborhood)
- [ ] Reciprocal rank fusion across all indices
- [ ] Belief-aware re-ranking using `BeliefState`
- [ ] `QueryRequest` extended with claim-first filters
- [ ] Test: query "accuracy on ImageNet" returns claims with belief states + TABLE evidence
- [ ] Test: query about contested topic returns claims from both sides with "CONTESTED" status
- [ ] Test: claim-first retrieval outperforms chunk-only retrieval on relevance benchmark

---

## 8. Phase 5 — Agent Runtime

**Goal**: Establish a bounded, observable agent runtime where agents operate exclusively on structured schemas, powered by LangGraph for orchestration and Nemotron for efficient agentic inference.

**Precondition**: Phase 4 complete (multi-index retrieval with trust scoring).

### 8.1 Framework: LangGraph

The agent runtime is built on **LangGraph** (from LangChain). LangGraph is selected over other agentic frameworks because:

- **Cyclical graph support**: The hypothesis-critique loop is inherently a cycle with conditional exits — LangGraph is built for exactly this pattern (unlike CrewAI which is more linear role-based orchestration)
- **Fine-grained state control**: Each node in the graph receives and returns typed state, matching our structured schema approach (AgentInput → AgentOutput)
- **Conditional branching**: `IF critique.severity >= FATAL: reject` maps directly to LangGraph's conditional edges
- **No retrieval opinions**: Unlike LlamaIndex, LangGraph doesn't impose a retrieval strategy — our claim-first retrieval system plugs in cleanly as a tool
- **Ollama-native**: Works with local models via LangChain's Ollama integration
- **Observable**: Built-in support for execution traces, state snapshots, and streaming

**Frameworks evaluated and rejected**:

| Framework | Why Not |
|---|---|
| AutoGen | Conversational multi-agent focus; our system is task-driven with structured I/O, not chat |
| CrewAI | Role-based but opinionated orchestration; lacks the cyclical graph control we need for critique loops |
| LlamaIndex | RAG-centric — overlaps and conflicts with our custom claim-first retrieval system |
| Semantic Kernel | Microsoft-ecosystem tied; less community support for Ollama/local-first setups |
| Google ADK | See detailed evaluation below |

**Google ADK evaluation** (`google/adk-python` reviewed):

ADK has genuinely strong features — native MCP tool support, `LoopAgent` with bounded `max_iterations`, an `escalate` exit mechanism, built-in dev UI, and A2A protocol for inter-agent communication. It also includes a `LangGraphAgent` wrapper. However, it does not fit ScholarOS for these specific reasons:

| ADK Feature | ScholarOS Reality |
|---|---|
| `LangGraphAgent` — wraps a compiled LangGraph graph inside ADK | Source code marks it `"Currently a concept implementation"` — not production-grade |
| Ollama model support | Requires `google-adk[extensions]` → LiteLLM as intermediary (`ollama/model-name` format). LangGraph uses LangChain's direct Ollama integration — fewer dependency layers. |
| `LlmAgent` multi-agent routing | Model-mediated: the coordinator LLM decides which sub-agent to invoke. Our routing must be **deterministic** (Python checks `critique.severity >= FATAL`), not model-driven. |
| `LoopAgent` escalate exit | Coarser than LangGraph typed `add_conditional_edges` — the critic agent sets an `escalate` flag vs our explicit three-way route (accept/reject/revise) with schema-checked thresholds. |
| Session management, artifact store, A2A protocol | Cloud-scale features for deployed multi-turn services. ScholarOS is local-first batch processing — this is overhead without benefit. |
| Deploy to Vertex AI / Cloud Run | Local-first. Not relevant. |
| Built-in dev UI (`adk web`) | Useful for debugging — the one ADK feature worth revisiting if we need an agent inspector later. |

**When ADK would be the right choice**: If ScholarOS were a cloud-hosted, multi-user, multi-turn research assistant with agents collaborating remotely via A2A. For a local research reasoning engine with deterministic, schema-driven control flow, LangGraph gives more control with fewer abstractions.

**Architecture**:

```
LangGraph StateGraph
  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
  │ Planner │ ──> │ Executor │ ──> │  Critic  │ ──> │ Synthesizer  │
  └─────────┘     └──────────┘     └──────────┘     └──────────────┘
       │                │               │  │                │
       v                v               │  v                v
    Decompose        Execute            │ Challenge       Combine
    task into        each step          │ results with    into final
    sub-tasks        against            │ counter-        artifact
                     structured         │ evidence
                     knowledge          │
                                        └──> LOOP (conditional edge)
                                             back to Hypothesis Agent
                                             if critique.confidence < threshold
```

Each agent node is a LangGraph node that:
1. Receives typed `AgentState` (extends `TypedDict`)
2. Calls Ollama (`nemotron-3-nano:30b` for agent orchestration) via LangChain
3. Returns updated state with provenance tracking
4. Conditional edges control flow (accept/reject/revise)

**Agent model**: `nemotron-3-nano:30b` — NVIDIA's MoE model with 30B total / 3B active parameters. Specifically designed for agentic tasks with native tool-calling and thinking mode. Only ~4-6 GB VRAM, allowing it to co-reside with the knowledge models (`qwen3:32b` for claim extraction).

**Constraints** (from `AGENTS.md`):

- Agents operate ONLY on structured schemas — never raw text
- Every statement must trace to evidence or assumptions
- Iteration loops MUST be bounded (configurable `max_iterations`, default 10)
- Prompts are versioned and served via prompt registry
- LangGraph orchestrator controls flow — agents are nodes, not autonomous processes

### 8.2 Agent Schemas

```python
class AgentInput(BaseModel):
    task_id: str
    task_type: str                              # "hypothesis", "critique", "synthesis", "plan"
    context: AgentContext

class AgentContext(BaseModel):
    claims: List[NormalizedClaim]                # Grounded claims from the knowledge base
    evidence: List[EvidenceRecord]              # Supporting evidence
    contradictions: List[ContradictionRecord]    # Known disagreements
    graph_context: Optional[GraphContext]        # Relevant graph neighborhood
    retrieval_results: List[RAGMatch]           # Retrieved chunks for this task
    constraints: Dict[str, Any]                 # Task-specific parameters

class AgentOutput(BaseModel):
    task_id: str
    result: Dict[str, Any]                      # Task-specific structured output
    provenance: List[ProvenanceEntry]           # What evidence was used
    confidence: float                           # Self-assessed confidence
    iteration: int                              # Which iteration produced this
    trace_id: str                               # Link to execution trace
```

### 8.3 Prompt Registry

All agent prompts are managed through a **prompt registry** — a structured store of versioned prompt templates loaded at runtime, never hardcoded inline.

```
prompts/
├── registry.yaml              # Master index: prompt_id → file, version, schema
├── extraction/
│   ├── claim_extract_v1.yaml
│   └── table_interpret_v1.yaml
├── reasoning/
│   ├── hypothesis_v2.yaml
│   ├── critique_v3.yaml
│   └── synthesis_v1.yaml
├── retrieval/
│   └── query_rewrite_v1.yaml
└── capability/
    ├── consensus_v1.yaml
    └── proposal_v1.yaml
```

Each prompt file follows a standard schema:

```yaml
# prompts/reasoning/hypothesis_v2.yaml
id: hypothesis_v2
version: 2
description: Generate testable hypothesis from grounded claims
input_schema: AgentContext
output_schema: Hypothesis
model_requirements:
  min_context: 8192
  structured_output: true
template: |
  Given the following grounded claims and evidence...
  {claims}

  And the following contradictions...
  {contradictions}

  Generate a testable hypothesis that:
  1. Is falsifiable
  2. Cites specific claim_ids as grounding
  3. Identifies assumptions explicitly
  4. Proposes a concrete test methodology

  Output as JSON matching the Hypothesis schema.
tests:
  - input_fixture: hypothesis_basic_input.json
    expected_keys: [hypothesis_text, claim_ids, assumptions, test_methodology]
```

The registry loader (`core/llm/prompt_registry.py`) provides:

```python
class PromptRegistry:
    """Loads, validates, and serves versioned prompts from the prompts/ directory."""

    def get(self, prompt_id: str, version: Optional[int] = None) -> PromptTemplate:
        """Return the prompt template. Latest version if version is None."""

    def render(self, prompt_id: str, context: dict, version: Optional[int] = None) -> str:
        """Render a prompt with variables substituted."""

    def list_prompts(self) -> List[PromptMeta]:
        """List all registered prompts with their versions and descriptions."""
```

Every prompt invocation is logged with: `prompt_id`, `prompt_version`, `input_hash`, `output_hash`, `model`, `token_count`, `latency_ms`.

### 8.4 Hypothesis-Critique Loop

The existing agent loop in `services/agent_loop/` is replaced by a LangGraph `StateGraph`:

```python
from langgraph.graph import StateGraph, END

class ResearchState(TypedDict):
    task: AgentInput
    sub_tasks: List[SubTask]
    intermediate_results: List[AgentOutput]
    hypothesis: Optional[Hypothesis]
    critiques: List[Critique]
    iteration: int
    max_iterations: int
    final_artifact: Optional[ResearchArtifact]

graph = StateGraph(ResearchState)

# Nodes
graph.add_node("planner", planner_node)           # Decompose into sub-tasks
graph.add_node("executor", executor_node)          # Execute against structured knowledge
graph.add_node("hypothesis", hypothesis_node)      # Synthesize findings into hypothesis
graph.add_node("critic", critic_node)              # Challenge with counter-evidence
graph.add_node("synthesizer", synthesizer_node)    # Combine into final artifact

# Edges
graph.set_entry_point("planner")
graph.add_edge("planner", "executor")
graph.add_edge("executor", "hypothesis")
graph.add_edge("hypothesis", "critic")

# Conditional loop: critique → accept/reject/revise
graph.add_conditional_edges("critic", route_critique, {
    "accept": "synthesizer",       # confidence >= threshold
    "reject": END,                 # severity >= FATAL
    "revise": "hypothesis",        # else → loop back
})
graph.add_edge("synthesizer", END)
```

**Flow**:
1. **Planner** decomposes the research question into sub-tasks
2. **Executor** queries structured knowledge (claim-first retrieval + graph) for each sub-task
3. **Hypothesis Agent** synthesizes findings into a hypothesis
4. **LOOP** (max_iterations=3, configurable):
   - **Critic** challenges the hypothesis with counter-evidence from multi-index retrieval
   - `route_critique` conditional edge:
     - `critique.severity >= FATAL` → reject hypothesis, log reason, END
     - `critique.confidence >= threshold` → accept → **Synthesizer**
     - else → revise → loop back to **Hypothesis Agent**
5. **Synthesizer** combines accepted hypothesis + evidence into final artifact

### 8.5 Phase 5 Deliverables

- [ ] LangGraph dependency added; `services/agent_loop/` refactored to LangGraph `StateGraph`
- [ ] `AgentInput` / `AgentOutput` / `AgentContext` / `ResearchState` schemas defined
- [ ] Prompt registry (`core/llm/prompt_registry.py`) implemented with YAML loading
- [ ] Planner node implemented (task decomposition)
- [ ] Executor node using multi-index claim-first retrieval
- [ ] Critic node querying counter-evidence from graph
- [ ] Synthesizer node implemented
- [ ] `route_critique` conditional edge with bounded iteration (max_iterations configurable)
- [ ] `nemotron-3-nano:30b` configured as agent model via LangChain Ollama integration
- [ ] Full prompt registry logging (prompt_id, version, input hash, output hash, tokens, latency)
- [ ] LangGraph execution traces integrated with Phase 7 observability
- [ ] Test: research question → decomposition → evidence gathering → hypothesis → critique → final artifact

---

## 9. Phase 6 — Capability Implementation

**Goal**: Implement the five core capabilities on top of the structured knowledge + agent runtime foundation.

**Precondition**: Phases 1-5 complete.

### 9.1 Capability 1: Literature Mapping

**What it does**: Given a seed paper or research question, discover and map the landscape of related work into thematic clusters.

**Implementation**:

1. **Seed expansion**: From a paper's references + citation graph, identify the set of related papers already in the system
2. **Federated discovery** (iterative, not one-shot):
   ```
   Round 1: Query Semantic Scholar + OpenAlex with seed paper title/abstract
            → retrieve top-50 related papers (metadata only, not full text)
            → deduplicate against existing corpus (by DOI, arXiv ID, title match)
            → score relevance (semantic similarity to seed)
            → select top-20 for ingestion

   Round 2: From Round 1 papers' references, identify frequently-cited papers
            not yet in the corpus (citation count > threshold)
            → retrieve metadata for these "hub" papers
            → score and select top-10 for ingestion

   Round 3 (optional): From Round 2, identify papers that cite the seed paper
            (forward citations via Semantic Scholar API)
            → these represent the "impact zone" of the seed work
            → select top-10 for ingestion

   Termination: Stop when:
            - max_papers reached (configurable, default 40)
            - relevance scores drop below threshold
            - all rounds complete
   ```
3. **Auto-ingest with prioritization**: Discovered papers enter the ingestion pipeline (Phase 1) but are prioritized:
   - Papers with full HTML available → ingest immediately
   - PDF-only papers → ingest in batch
   - Metadata-only papers (no accessible full text) → store metadata, mark as "stub" in graph
4. **Clustering**: Use HDBSCAN over paper embeddings (existing `MappingService`) to identify thematic clusters
5. **Labeling**: Use local LLM to generate cluster labels from representative abstracts (existing implementation)
6. **Gap detection**: Identify clusters with few papers or missing key topics — these are literature gaps
7. **Boundary paper detection**: Papers that bridge two or more clusters (high similarity to multiple cluster centroids) are marked as "boundary papers" — these often represent methodological innovations

**Existing code to build on**: `services/mapping/service.py` (clustering + labeling already implemented)

**New requirements**:

- Federated paper discovery service (`services/discovery/service.py`) with iterative expansion
- Relevance scoring and deduplication against existing corpus
- Citation-based hub detection (frequently-cited papers in the reference graph)
- Forward citation retrieval (papers that cite the seed)
- Auto-ingestion trigger with priority queue
- Stub paper nodes for metadata-only entries (partial graph coverage)

**MCP tool**: `literature_map` — input: seed paper ID or query string + max_papers → output: `ClusterMap` with gap annotations, boundary papers, and stub indicators

### 9.2 Capability 2: Consensus & Contradiction Detection

**What it does**: Across a corpus of papers, identify where claims agree, disagree, or conditionally diverge. This is where the claim system (5.3), evidence linking engine (6.2), and belief state (6.3) come together to produce the system's signature output.

**Implementation**:

1. **Claim collection**: Gather all claims from relevant papers (from claim index, not re-extraction)
2. **Claim clustering**: Group into `ClaimCluster` objects by condition signature (5.3.4)
3. **Within-cluster analysis**:
   - For each cluster: compute agreement ratio from belief states
   - Identify the dominant position (majority of claims support which value?)
   - Identify outliers (claims that disagree with the dominant position)
   - Check condition overlap: are the disagreeing claims actually about the same thing?
4. **Contradiction classification** (the hard part — most systems skip this):
   - **Direct contradiction**: Same conditions (dataset + metric + method), different values
     - Example: Paper A says "94.2% on SQuAD", Paper B says "91.1% on SQuAD" for the same model
   - **Conditional divergence**: Different conditions explain the difference
     - Example: Paper A used SQuAD v1, Paper B used SQuAD v2 — not a real contradiction
   - **Methodological contradiction**: Same goal, incompatible approaches
     - Example: Paper A says "dropout helps," Paper B says "dropout hurts" — check conditions
   - **Temporal supersession**: Newer result replaces older one
     - Example: Paper A (2022) reports 90%, Paper B (2024) reports 95% — not contradiction, progress
5. **Consensus scoring**: Per-cluster confidence weighted by:
   - Number of independent sources (not just papers — check for author overlap)
   - Evidence quality (table-backed claims > text-only claims)
   - Belief stability (stable beliefs count more)
   - Recency (recent papers weighted slightly higher)
6. **Web expansion**: For low-confidence clusters (consensus_score < 0.6), trigger federated discovery (9.1) to find additional papers that might resolve the ambiguity

**What's missing from current implementation**:

- Cross-paper comparison at scale (current implementation is pairwise, needs to work across N papers via claim clusters)
- Condition-aware contradiction classification (current system creates false contradictions when conditions differ)
- Trust-weighted consensus using belief states
- Web-expanded evidence gathering for weak consensus zones

**Output**:

```python
class ConsensusReport(BaseModel):
    topic: str
    paper_count: int
    claim_clusters: List[ClaimClusterReport]
    overall_consensus: float             # 0.0-1.0 across all clusters
    contested_zones: List[ContestedZone] # Clusters where consensus is low
    recommendations: List[str]           # "More evidence needed for X"

class ClaimClusterReport(BaseModel):
    cluster: ClaimCluster
    consensus_score: float
    dominant_position: str               # The majority claim
    supporting_papers: List[str]
    contradicting_papers: List[str]
    contradiction_type: Optional[str]    # "direct", "conditional", "methodological", "temporal"
    condition_analysis: str              # Explanation of why claims differ (if they do)
    belief_states: List[BeliefState]     # Current beliefs for each claim in cluster
```

**MCP tool**: `consensus_report` — input: list of paper IDs + topic filter → output: `ConsensusReport` with condition-aware contradiction classification and belief states

### 9.3 Capability 3: Hypothesis Generation & Critique

**What it does**: Generate novel, testable hypotheses grounded in the knowledge base, then iteratively refine them through adversarial critique.

**Implementation**: This is the core agent loop from Phase 5, section 8.4.

**Unique requirements**:

- Hypotheses must cite specific `claim_ids` as grounding — no floating assertions
- Counter-evidence retrieval must use the graph (not just vector similarity) to find relevant contradictions
- Each iteration must produce a structured diff showing what changed and why
- Final hypothesis includes: falsifiability statement, required experimental setup, expected outcomes with confidence intervals

**MCP tool**: `generate_hypothesis` — input: research question + corpus scope → output: `Hypothesis` with full provenance chain

### 9.4 Capability 4: Multimodal Evidence Extraction

**What it does**: Extract structured evidence from tables, figures, and equations in papers.

**Implementation**:

1. **Table extraction**: Already implemented in `services/ingestion/table_extractor.py` (pdfplumber) — needs integration (Phase 1 fixes this)
2. **Table structuring**: Parse extracted tables into `TableData` (headers, rows, cell types) using local LLM for ambiguous cases
3. **Figure extraction**: HTML pipeline extracts figure URLs and captions. For PDF-only papers, use multimodal model (`qwen3-vl:32b`) to describe figures
4. **Equation extraction**: Extract LaTeX from HTML sources, render descriptions for PDF sources
5. **Evidence linking**: Connect extracted evidence to claims — if a table shows "accuracy = 94.2% on ImageNet", link that to claims about ImageNet accuracy

**Local model usage**:

- `granite3.2-vision:2b` — Table, chart, and infographic extraction (primary — optimized for document understanding)
- `qwen3-vl:32b` — Complex figure description and layout analysis (loaded on-demand for difficult cases)
- `qwen3:32b` — Text structuring for ambiguous table formats

**MCP tool**: `extract_evidence` — input: paper ID + evidence types → output: `List[EvidenceRecord]` with structured data

### 9.5 Capability 5: Proposal Generation

**What it does**: Generate a structured research proposal grounded in the knowledge base findings.

**Implementation**:

1. **Input assembly**: Collect from previous capabilities:
   - Literature map with gaps (Capability 1)
   - Consensus/contradiction report (Capability 2)
   - Accepted hypothesis (Capability 3)
   - Evidence records (Capability 4)
2. **Section generation**: Using local LLM with structured prompts:
   - Novelty statement (grounded in literature gaps)
   - Methodology outline (grounded in successful experimental setups from the corpus)
   - Expected outcomes (grounded in existing evidence with predicted improvements)
   - Risk analysis (grounded in known contradictions and failure modes)
3. **Citation generation**: All claims in the proposal link back to specific papers and chunks
4. **Output formats**: Markdown and LaTeX

**Existing code**: `services/proposal/service.py` already generates proposals but needs upgrading to use structured inputs from Capabilities 1-4 instead of free-form text.

**MCP tool**: `generate_proposal` — input: hypothesis ID + literature map ID → output: `Proposal` with citations and evidence

### 9.6 Capability Dependency Graph

```
Capability 1 (Literature Mapping)
       |
       v
Capability 2 (Consensus/Contradiction)  <--- can run independently too
       |
       v
Capability 3 (Hypothesis Gen/Critique)  <--- requires 1 + 2
       |
       +-------> Capability 4 (Evidence Extraction)  <--- can run independently too
       |                    |
       v                    v
Capability 5 (Proposal Generation)  <--- requires 1 + 2 + 3 + 4
```

Capabilities 1, 2, and 4 can be invoked independently. Capability 3 requires 1 and 2. Capability 5 requires all four.

### 9.7 Phase 6 Deliverables

- [ ] Federated paper discovery service
- [ ] Literature mapping with gap detection
- [ ] Cross-paper consensus detection at scale
- [ ] Trust-weighted consensus scoring
- [ ] Hypothesis generation with full provenance
- [ ] Counter-evidence retrieval via graph
- [ ] Multimodal evidence extraction (tables, figures, equations)
- [ ] Evidence-to-claim linking
- [ ] Proposal generation with structured inputs and citations
- [ ] All 5 MCP tools registered and functional
- [ ] End-to-end test: 10 papers → literature map → consensus report → hypothesis → evidence → proposal

---

## 10. Phase 7 — Observability & Evaluation

**Goal**: Ensure every pipeline step is traceable, auditable, and measurable.

**Precondition**: Can begin in parallel with Phase 3+ (observability infrastructure is orthogonal).

### 10.1 Structured Logging

Every service call logs:

```json
{
  "trace_id": "uuid",
  "service": "ingestion",
  "operation": "ingest",
  "input_hash": "sha256",
  "output_hash": "sha256",
  "duration_ms": 1234,
  "status": "success",
  "metadata": {
    "source_type": "arxiv",
    "chunk_count": 42,
    "fusion_strategy": "merged"
  }
}
```

**Existing infrastructure**: `core/observability/phase5.py`, `metrics_collector.py`, `provenance_audit.py` — these provide the foundation but need integration with the new structured pipeline.

### 10.2 Provenance Chain

Every output artifact must be traceable back to source documents:

```
Proposal → Hypothesis → Claims → Chunks → ResearchDocument → Source (DOI/URL/PDF)
    |           |            |        |
    v           v            v        v
 trace_id   claim_ids    chunk_ids  source_id
```

The provenance chain is stored in the execution trace (JSON files in `.local/traces/`) and can be queried via MCP tool.

### 10.3 Determinism Verification

For deterministic services (everything except LLM calls):

```python
def verify_determinism(service, input_data, n_runs=3):
    """Run service n times, verify identical output hashes."""
    hashes = set()
    for _ in range(n_runs):
        output = service.process(input_data)
        hashes.add(hash_output(output))
    assert len(hashes) == 1, f"Non-deterministic: {len(hashes)} distinct outputs"
```

Run determinism verification as part of CI for all deterministic services.

### 10.4 Evaluation Framework

#### Ingestion Quality Metrics

| Metric                        | Measurement                                            | Target           |
| ----------------------------- | ------------------------------------------------------ | ---------------- |
| Section extraction accuracy   | Manual annotation on 30-paper corpus                   | >90%             |
| Table extraction completeness | Tables found / tables in document                      | >85%             |
| Reference extraction accuracy | Parsed refs / actual refs                              | >90%             |
| Chunk boundary quality        | % of chunks that don't split mid-sentence              | >95%             |
| Fusion improvement            | Quality score (fused) vs Quality score (single source) | >10% improvement |

#### Retrieval Quality Metrics

| Metric            | Measurement                                                  | Target |
| ----------------- | ------------------------------------------------------------ | ------ |
| Recall@10         | Relevant chunks in top 10 / total relevant                   | >80%   |
| MRR               | Mean reciprocal rank of first relevant result                | >0.7   |
| Trust calibration | Correlation between trust score and human relevance judgment | >0.6   |

#### Agent Quality Metrics

| Metric                 | Measurement                                               | Target |
| ---------------------- | --------------------------------------------------------- | ------ |
| Groundedness           | % of hypothesis claims traceable to evidence              | 100%   |
| Critique effectiveness | % of critiques that identify genuine weaknesses           | >70%   |
| Convergence rate       | % of hypothesis loops that converge within max_iterations | >80%   |

#### End-to-End Metrics

| Metric                  | Measurement                                            | Target                  |
| ----------------------- | ------------------------------------------------------ | ----------------------- |
| Pipeline success rate   | % of papers that complete full ingestion without error | >95%                    |
| Provenance completeness | % of proposal claims with full provenance chain        | 100%                    |
| Round-trip latency      | Time from paper submission to proposal generation      | <5 min for single paper |

### 10.5 Evaluation Corpus

Leverage and extend the existing 30-paper test corpus from `html_ingestion_poc/evaluation/ingestion_integrity_test.py`:

- 7 publisher types (arXiv, PMC, ACL, Nature, Science, Springer, generic)
- 13 metrics per paper
- Cross-validation (HTML vs PDF for same papers)

Extend to:

- 50 papers covering all publisher types
- Add ground-truth annotations for: section boundaries, table contents, reference lists, key claims
- Automate regression testing against this corpus

### 10.6 Phase 7 Deliverables

- [ ] Structured logging integrated into all services
- [ ] Provenance chain tracking from source to output
- [ ] Determinism verification in CI for all deterministic services
- [ ] Evaluation framework with automated metrics collection
- [ ] 50-paper annotated test corpus
- [ ] Dashboard for monitoring pipeline health metrics
- [ ] MCP tool: `provenance_query` — trace any output back to its sources

---

## 11. Phase 8 — Research Reasoning Loop

**Goal**: Transform ScholarOS from a static pipeline (ingest → retrieve → generate) into a **dynamic reasoning system** that evolves its knowledge as new papers enter the corpus. This is the phase that separates "very advanced RAG + graph" from "self-updating research reasoning system."

**Precondition**: Phases 1-5 complete (ingestion, claims, graph, retrieval, agents). Phase 7 (observability) should be active to track state changes.

### 11.1 The Core Loop

When a new paper is ingested, the system does not just "add nodes." It **reasons about what changed**:

```
New Paper Ingested
       |
       v
  Extract Claims (Phase 2)
       |
       v
  Link Evidence (Phase 3)
       |
       v
  Update Graph Edges
       |
       v
  Recompute Belief States for ALL affected claims
       |
       v
  Detect Belief Changes (delta > threshold)
       |
       +---> [Belief Strengthened] Update consensus scores in affected clusters
       |
       +---> [Belief Weakened] Flag for attention, update cluster
       |
       +---> [New Contradiction Detected] Create ContradictionEdge,
       |     update both claims' belief states, notify
       |
       +---> [Claim Superseded] Mark old claim trend = SUPERSEDED,
       |     update dependent hypotheses
       |
       v
  Propagate to Dependent Artifacts:
       - Hypotheses grounded in changed claims → mark for re-evaluation
       - Consensus reports including changed clusters → mark stale
       - Literature maps → flag if new paper changes cluster structure
       |
       v
  Log all state changes with trigger_paper_id
```

**Location**: `services/reasoning/state_update_engine.py`

### 11.2 Belief Update Mechanism

```python
class StateUpdateEngine:
    """Handles the ripple effects of new knowledge entering the system."""

    def on_paper_ingested(self, paper_id: str, claims: List[Claim]) -> StateUpdateReport:
        """Called after a new paper completes ingestion + claim extraction."""
        affected_claims = []
        belief_changes = []
        new_contradictions = []

        for claim in claims:
            # 1. Find existing claims in the same cluster
            cluster = self._find_matching_cluster(claim)
            if cluster is None:
                # New claim topic — create new cluster
                self._create_cluster(claim)
                continue

            # 2. Run evidence linking for this claim against existing evidence
            evidence_links = self._evidence_linker.link(claim)

            # 3. Check for contradictions with existing claims in cluster
            for existing_claim_id in cluster.claims:
                existing = self._claim_store.get(existing_claim_id)
                if self._is_contradiction(claim, existing):
                    edge = ContradictionEdge(
                        claim_a_id=claim.claim_id,
                        claim_b_id=existing.claim_id,
                        contradiction_type=self._classify_contradiction(claim, existing),
                        condition_overlap=self._compute_condition_overlap(claim, existing),
                    )
                    self._graph.add_edge(edge)
                    new_contradictions.append(edge)

            # 4. Add claim to cluster
            cluster.claims.append(claim.claim_id)

            # 5. Recompute belief state for ALL claims in the affected cluster
            for cid in cluster.claims:
                old_belief = self._belief_store.get(cid)
                new_belief = self._belief_engine.compute(cid)
                if abs(new_belief.confidence - old_belief.confidence) > 0.1:
                    belief_changes.append(BeliefChange(
                        claim_id=cid,
                        old_confidence=old_belief.confidence,
                        new_confidence=new_belief.confidence,
                        trigger_paper_id=paper_id,
                    ))
                self._belief_store.update(cid, new_belief)
                self._belief_history.append(cid, new_belief, paper_id)

        # 6. Propagate to dependent artifacts
        self._propagate_changes(belief_changes, new_contradictions)

        return StateUpdateReport(
            paper_id=paper_id,
            claims_added=len(claims),
            belief_changes=belief_changes,
            new_contradictions=new_contradictions,
            hypotheses_flagged=self._flagged_hypotheses,
        )
```

### 11.3 Temporal Reasoning

Research is time-dependent. The system must understand that:

- A 2024 result showing 95% accuracy **supersedes** a 2020 result showing 90% on the same task
- Methods evolve: "state-of-the-art" is a moving target
- Older results are not "wrong" — they were correct in their context but may no longer be the best known

**Implementation**:

```python
class TemporalAnalyzer:
    def detect_supersession(self, claim: Claim, cluster: ClaimCluster) -> Optional[str]:
        """Detect if a new claim supersedes an older one."""
        if claim.conditions.metric is None or claim.conditions.dataset is None:
            return None

        # Find claims with same conditions but from earlier papers
        older_claims = [
            c for c in cluster.claims
            if c.paper_year and claim.paper_year
            and c.paper_year < claim.paper_year
            and self._conditions_match(c, claim)
        ]

        if not older_claims:
            return None

        # Check if the new claim represents improvement
        for old in older_claims:
            if self._is_improvement(claim, old):
                # Mark old claim as superseded
                old_belief = self._belief_store.get(old.claim_id)
                old_belief.trend = BeliefTrend.SUPERSEDED
                self._belief_store.update(old.claim_id, old_belief)
                return f"Supersedes {old.claim_id} ({old.paper_year})"

        return None

    def compute_recency_weight(self, claim: Claim) -> float:
        """More recent claims get a slight weight boost, but not overwhelming."""
        if claim.paper_year is None:
            return 1.0
        current_year = 2026
        age = current_year - claim.paper_year
        # Sigmoid decay: recent papers (0-2 years) ≈ 1.0, old papers (10+ years) ≈ 0.7
        return 0.7 + 0.3 / (1 + (age / 3) ** 2)
```

### 11.4 Hypothesis Memory

In v1, hypotheses were ephemeral: generate → critique → output → gone. In a dynamic system, hypotheses are **persistent, tracked, and updated**:

```python
class StoredHypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    status: HypothesisStatus           # ACTIVE, STRENGTHENED, WEAKENED, INVALIDATED, SUPERSEDED
    grounding_claim_ids: List[str]     # Claims this hypothesis rests on
    confidence: float
    created_at: datetime
    last_evaluated: datetime

    # Revision history
    revisions: List[HypothesisRevision]
    critique_history: List[str]        # critique_ids

    # Dependency tracking
    dependent_beliefs: List[str]       # belief claim_ids that affect this hypothesis
    invalidation_conditions: List[str] # What would kill this hypothesis

class HypothesisStatus(str, Enum):
    ACTIVE = "active"                  # Currently valid
    STRENGTHENED = "strengthened"       # New evidence supports it
    WEAKENED = "weakened"              # New evidence undermines it
    INVALIDATED = "invalidated"        # Grounding claims contradicted
    SUPERSEDED = "superseded"          # Better hypothesis exists

class HypothesisRevision(BaseModel):
    revision_id: str
    timestamp: datetime
    trigger: str                       # "new_paper", "belief_change", "user_request"
    trigger_paper_id: Optional[str]
    changes: str                       # What changed and why
    old_confidence: float
    new_confidence: float
```

**When belief changes propagate to hypotheses**:

```
1. StateUpdateEngine detects belief change for claim X
2. Query: which hypotheses have claim X in grounding_claim_ids?
3. For each affected hypothesis:
   a. If grounding claim's belief weakened significantly:
      → status = WEAKENED, trigger re-evaluation
   b. If grounding claim's belief strengthened:
      → status = STRENGTHENED, update confidence
   c. If grounding claim is now CONTESTED:
      → flag hypothesis, schedule Critic Agent review
   d. If grounding claim is SUPERSEDED:
      → status = SUPERSEDED if no other grounding remains
4. Log revision with trigger_paper_id
```

### 11.5 System State Dashboard

The reasoning loop generates events that should be visible:

```python
class SystemState(BaseModel):
    """Snapshot of the system's current knowledge state."""
    total_papers: int
    total_claims: int
    total_belief_states: int

    # Health indicators
    claims_high_confidence: int
    claims_contested: int
    claims_weakly_supported: int

    # Recent activity
    recent_belief_changes: List[BeliefChange]     # Last N changes
    recent_contradictions: List[ContradictionEdge] # Newly detected
    hypotheses_needing_review: List[str]           # Flagged for re-evaluation

    # Trends
    knowledge_growth_rate: float                   # Claims per paper (avg)
    contradiction_rate: float                      # New contradictions per paper (avg)
    belief_stability: float                        # % of beliefs that are STABLE
```

**MCP tool**: `system_state` — returns current `SystemState` snapshot

### 11.6 Phase 8 Deliverables

- [ ] `StateUpdateEngine` implemented with full belief propagation
- [ ] Belief update triggered automatically on paper ingestion
- [ ] Belief change history tracked in `belief_history` table
- [ ] Contradiction detection during ingestion (not just batch)
- [ ] `TemporalAnalyzer` with supersession detection and recency weighting
- [ ] `StoredHypothesis` with persistent status, revision history, and dependency tracking
- [ ] Hypothesis status automatically updated when grounding beliefs change
- [ ] `SystemState` dashboard MCP tool
- [ ] Test: ingest paper that contradicts existing claim → belief updates → hypothesis flagged
- [ ] Test: ingest paper with newer results → old claim marked SUPERSEDED → trend updated
- [ ] Test: hypothesis grounding claim weakened → hypothesis status = WEAKENED with revision log

---

## 12. Local Model Stack

All LLM operations run locally via Ollama. No cloud API dependencies for core reasoning.

### 12.1 Model Selection

**Hardware**: NVIDIA GeForce RTX 5090 — 32 GB GDDR7 VRAM.

With 32 GB available, the system runs larger models as defaults and can load multiple models concurrently (reasoning + embedding) without swapping.

| Model                    | Role              | Parameters       | VRAM     | Use Case                                                                               |
| ------------------------ | ----------------- | ---------------- | -------- | -------------------------------------------------------------------------------------- |
| `qwen3:32b`              | Knowledge reasoning | 32B            | ~20 GB   | Claim extraction, evidence linking, cluster labeling. Heavy knowledge work requiring deep understanding. Supports tool-calling and thinking mode natively. |
| `nemotron-3-nano:30b`    | Agent runtime     | 30B total / 3B active (MoE) | ~4-6 GB | Agent orchestration: planner, executor, critic, synthesizer nodes in LangGraph. Specifically designed for agentic tasks with native tool-calling and configurable thinking budget. Hybrid Mamba-Transformer architecture. |
| `qwen3-vl:32b`           | Multimodal        | 32B              | ~20 GB   | Figure description, table interpretation from images, layout analysis. Vision + thinking + tools. |
| `granite3.2-vision:2b`   | Document OCR      | 2B               | ~1.5 GB  | Table, chart, and infographic extraction from PDFs. Specifically designed for visual document understanding. Co-resident with agent model. |
| `qwen3-embedding:0.6b`   | Embedding         | 0.6B             | ~0.5 GB  | Dense vector embeddings (via Ollama). Built on Qwen3 foundation, strong semantic capture. |
| `bge-m3`                 | Embedding (alt)   | 567M             | ~0.5 GB  | Multi-functional embeddings (dense + sparse + ColBERT). Multilingual. Fallback option.  |
| `all-MiniLM-L6-v2`       | Embedding (test)  | 22M              | ~0.1 GB  | Lightweight fallback (384-dim, via sentence-transformers). Testing and offline use.     |
| `deepseek-ocr:3b`        | OCR               | 3B               | ~2 GB    | Token-efficient OCR for scanned PDFs. Loaded on-demand, not resident.                  |

**Model role separation**:
- **Knowledge work** (`qwen3:32b`): Claim extraction, evidence linking, hypothesis content generation — tasks requiring deep text understanding and structured output quality. Loaded during ingestion and knowledge-building phases.
- **Agent orchestration** (`nemotron-3-nano:30b`): Planner task decomposition, executor tool-calling, critic counter-evidence queries, synthesizer output assembly — tasks requiring fast, reliable tool use and reasoning chains. Loaded during agent runtime (Phase 5 capabilities). Only 3B active parameters means it runs ~5x faster than the 32B knowledge model.

**Concurrency notes**:
- `nemotron-3-nano:30b` (~4-6 GB) + `granite3.2-vision:2b` (~1.5 GB) + `qwen3-embedding:0.6b` (~0.5 GB) = ~6-8 GB total — all three can remain co-resident during agent runtime.
- `qwen3:32b` (~20 GB) + `qwen3-embedding:0.6b` (~0.5 GB) = ~20.5 GB — both fit during ingestion.
- `qwen3:32b` and `nemotron-3-nano:30b` can co-reside (~24-26 GB total) for workflows where agents need to invoke knowledge extraction within a single research session.
- `qwen3-vl:32b` (~20 GB) requires swapping out other large models. Used on-demand for complex figure interpretation.
- During a full research session: `nemotron-3-nano:30b` (agent orchestration, always loaded) calls `qwen3:32b` (claim extraction, loaded on-demand) and `granite3.2-vision:2b` (table extraction, co-resident).

**Why these models over alternatives**:
- `nemotron-3-nano:30b` for agents over `qwen3:32b`: Nemotron's MoE architecture activates only 3B parameters per token — ~5x faster inference for tool-calling loops where latency matters more than raw knowledge depth. Built specifically for agentic workflows with native tool-calling. Frees VRAM for co-residency with knowledge model.
- `qwen3:32b` for knowledge over `deepseek-r1:32b`: qwen3 has native tool-calling + thinking mode; deepseek-r1 is stronger at pure reasoning chains but lacks structured output control needed for claim extraction.
- `qwen3:32b` over `cogito:32b`: qwen3 has broader benchmark coverage and established Ollama ecosystem support.
- `qwen3-vl:32b` over `gemma3:27b` (vision): qwen3-vl supports thinking mode for complex figure interpretation; gemma3 vision is capable but lacks thinking chain.
- `granite3.2-vision:2b` added as dedicated document model: unlike general-purpose vision models, it's optimized specifically for tables, charts, infographics — exactly our evidence extraction use case. Small enough to co-load.
- `qwen3-embedding:0.6b` over `nomic-embed-text`: built on Qwen3 foundation with stronger semantic understanding; same VRAM footprint.
- `bge-m3` as alternative: provides multi-functional retrieval (dense + sparse + ColBERT) which could benefit claim-first retrieval if claim indices need hybrid search.

### 12.2 Model Upgrade Path

| Current                  | Upgrade                             | Benefit                                                              |
| ------------------------ | ----------------------------------- | -------------------------------------------------------------------- |
| `qwen3:32b`              | `qwen3.5:35b`                       | Unified multimodal + reasoning in one model (vision+tools+thinking). Eliminates model swapping for multimodal tasks. Tight on VRAM (~22 GB) but feasible. |
| `qwen3-vl:32b`           | `qwen3.5:35b`                       | Same — qwen3.5 unifies both roles, replacing separate reasoning and vision models. |
| `nemotron-3-nano:30b`    | `nemotron-3-super:120b`             | 120B total / 12B active MoE. Stronger multi-agent reasoning with 1M-token context. ~10-15 GB VRAM (FP8). Feasible if co-residency with knowledge model is not required. |
| `qwen3-embedding:0.6b`   | `qwen3-embedding:4b` or `:8b`       | Larger embedding models with stronger semantic capture. 4B (~3 GB) feasible alongside agent model; 8B (~5 GB) tight. |
| `granite3.2-vision:2b`   | `glm-ocr`                           | More capable document OCR for complex layouts with tool-calling support. |
| `deepseek-ocr:3b`        | `glm-ocr`                           | GLM-OCR handles complex document understanding beyond basic OCR.     |
| `bge-m3`                 | `snowflake-arctic-embed2`           | Frontier multilingual embedding with stronger English performance.   |

### 12.3 Prompt Management

All prompts are managed through the **prompt registry** (see section 8.3):

1. **Registry-based**: All prompts live in `prompts/` as versioned YAML files, loaded by `core/llm/prompt_registry.py`
2. **Versioned**: Each prompt file declares an explicit version; the registry can serve specific or latest versions
3. **Logged**: Every invocation records `prompt_id`, `prompt_version`, `input_hash`, `output_hash`, `model`, `token_count`, `latency_ms`
4. **Tested**: Each prompt YAML includes `tests:` with input fixtures and expected output keys for regression testing
5. **Never inline**: No prompt strings in service code — agents call `registry.render(prompt_id, context)`

### 12.4 Fallback Strategy

```
Ollama qwen3-embedding:0.6b (local, preferred)
  → Ollama bge-m3 (local, alternative — dense+sparse+ColBERT)
    → sentence-transformers all-MiniLM-L6-v2 (local, fallback, 384-dim)
      → hash-based pseudo-embeddings (deterministic, testing only)
```

For LLM reasoning:

```
Agent runtime: Ollama nemotron-3-nano:30b (agentic tasks, tool-calling)
Knowledge work: Ollama qwen3:32b (claim extraction, evidence linking)
  → No fallback — if Ollama is down, agent operations fail with clear error
  → Deterministic services continue to work without LLM
```

This is intentional: the system should fail loudly rather than silently degrade reasoning quality.

---

## 13. Execution Order & Dependencies

```
Phase 1: Ingestion Unification
  ├── 1.1 Promote source resolver
  ├── 1.2 Fix HTML extraction bugs (6 items)
  ├── 1.3 Fix PDF extraction bugs (6 items)
  ├── 1.4 Build source fusion layer (with conflict detection)
  ├── 1.5 Fix the bridge
  ├── 1.6 Connect PaperStore to RAG pipeline
  └── 1.7 End-to-end tests
         |
         v
Phase 2: Structured Knowledge Layer + Claim System
  ├── 2.1 Define StructuredChunk schema
  ├── 2.2 Implement section-aware chunking
  ├── 2.3 Build full Claim System (schema + extraction + normalization + clustering)
  ├── 2.4 Finalize ResearchDocument schema
  └── 2.5 Migration path for old chunks
         |
         v
Phase 3: Graph + Evidence Linking + Belief ───────────┐
  ├── 3.1 Define graph schema                          |
  ├── 3.2 Build Evidence Linking Engine                |
  │       (table→claim, text→claim, cross-paper)      |
  ├── 3.3 Build Belief State layer                     |  Phase 7: Observability
  ├── 3.4 Implement citation resolution                |  (can start in parallel
  ├── 3.5 Graph construction pipeline                  |   from Phase 3 onward)
  └── 3.6 SQLite storage (graph-query optimized)       |  ├── 7.1 Structured logging
         |                                             |  ├── 7.2 Provenance chain
         v                                             |  ├── 7.3 Determinism verification
Phase 4: Claim-First Retrieval                         |  ├── 7.4 Evaluation framework
  ├── 4.1 Fix existing bugs (2 items)                  |  └── 7.5 Test corpus
  ├── 4.2 Claim-first multi-index retrieval            |
  ├── 4.3 Belief-aware re-ranking                      |
  └── 4.4 Structured query support                     |
         |                                             |
         v                                             |
Phase 5: Agent Runtime (LangGraph + nemotron-3-nano)   |
  ├── 5.1 LangGraph StateGraph + agent schemas         |
  ├── 5.2 Prompt registry                              |
  ├── 5.3 Agent nodes (planner/executor/critic/synth)  |
  └── 5.4 Hypothesis-critique loop (conditional edges) |
         |                                             |
         v                                             |
Phase 6: Capability Implementation                     |
  ├── 6.1 Literature Mapping (iterative discovery)     |
  ├── 6.2 Consensus/Contradiction (condition-aware)    |
  ├── 6.3 Hypothesis Generation                        |
  ├── 6.4 Evidence Extraction                          |
  └── 6.5 Proposal Generation                         |
         |                                             |
         v                                             |
Phase 8: Research Reasoning Loop ──────────────────────┘
  ├── 8.1 State Update Engine (belief propagation)
  ├── 8.2 Temporal Reasoning (supersession detection)
  ├── 8.3 Hypothesis Memory (persistent, tracked)
  └── 8.4 System State Dashboard
```

### Critical Path

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 8
```

Every phase depends on the previous one. Phase 7 (Observability) is parallelizable from Phase 3 onward. Phase 8 (Reasoning Loop) depends on Phases 1-6 being functional — it is the capstone that makes the system dynamic.

### Implementation Priority Within Each Phase

Within each phase, items are listed in dependency order. Items at the same level can be parallelized:

**Phase 1 parallelism**:

- 1.1, 1.2, 1.3 can run in parallel (no dependencies between source resolver promotion, HTML fixes, and PDF fixes)
- 1.4 depends on 1.2 + 1.3
- 1.5 depends on 1.4
- 1.6 depends on 1.5

**Phase 3 parallelism**:

- 3.1 (graph schema) must come first
- 3.2 (evidence linking) and 3.4 (citation resolution) can run in parallel
- 3.3 (belief state) depends on 3.2
- 3.5 (construction pipeline) depends on 3.2 + 3.3 + 3.4

---

## 14. Risk Register

| Risk | Impact | Likelihood | Mitigation |
| ---- | ------ | ---------- | ---------- |
| Source fusion produces lower quality than single source for some publishers | Capability degradation | Medium | Per-publisher quality thresholds + conflict detection + fallback to best single source |
| Source fusion merges conflicting data confidently | Incorrect structured data | High | Conflict detection layer (4.4) downgrades confidence, logs conflicts, preserves both versions |
| Claim extraction produces false claims from ambiguous text | Poisoned graph | High | Multi-confidence extraction (rule-based=high, LLM=lower), validation before graph entry |
| Evidence linking creates false table→claim alignments | Incorrect contradiction/consensus | Medium | Metric synonym table validation, human-inspectable alignment logs, confidence thresholds |
| Belief state oscillates on contested topics | Unstable system behavior | Medium | Stability tracking in BeliefState, hysteresis (require >0.1 delta to trigger change) |
| Graph construction too slow for large corpora (>1000 papers) | Performance | Medium | Batch processing + incremental graph updates |
| Local LLM quality insufficient for hypothesis/critique | Quality | Medium | nemotron-3-nano:30b (agentic) + qwen3:32b (knowledge) with thinking mode + structured output validation + upgrade paths (nemotron-3-super, qwen3.5:35b) |
| Claim normalization merges claims that shouldn't be merged | False consensus | Medium | Condition-aware clustering (5.3.4) splits by conditions, not just semantics |
| Breaking changes to existing services during Phase 1 bug fixes | Regression | High | Run existing test suite before and after each fix; no behavior change for correct inputs |
| Sentence segmenter unification changes chunk boundaries | Invalidates existing embeddings | High | Re-embed all documents after unification; version chunk IDs |
| External API rate limits during federated discovery | Slow literature mapping | Medium | Cache API responses; respect rate limits; degrade to local-only corpus |
| Publisher HTML format changes break extractors | Silent quality drop | Medium | Evaluation corpus detects regressions; fallback to PDF |
| Hypothesis memory grows unbounded | Storage + noise | Low | Archive hypotheses older than configurable threshold; status=INVALIDATED claims auto-archived |

---

## 15. Acceptance Criteria

The conversion is complete when ALL of the following are true:

### Foundation (Phases 1-2)

- [ ] Any identifier (DOI, arXiv ID, PMCID, URL, local PDF) produces a `ResearchDocument` with sections, tables, references, and provenance
- [ ] Source fusion demonstrably improves quality over single-source extraction on the evaluation corpus
- [ ] All chunks are typed (`StructuredChunk`) with section context, not positional text slices
- [ ] No information loss at any pipeline stage (tables, figures, references all preserved through to embedding)

### Claim System (Phase 2)

- [ ] Claims extracted from text, tables, and captions with subject-relation-object structure
- [ ] Claims carry conditions (dataset, metric, method, baseline) — not just free text
- [ ] Claim normalization produces canonical forms that are comparable across papers
- [ ] Claim clustering groups semantically equivalent claims by condition signature
- [ ] Results table with 5 rows × 3 metrics → 15 claims extracted with correct conditions

### Knowledge & Evidence (Phases 3-4)

- [ ] Citation graph links papers via parsed references (with retroactive resolution)
- [ ] Evidence Linking Engine connects claims to table cells, text spans, and figures via deterministic alignment
- [ ] Table→claim alignment uses metric synonym tables, not LLM guessing
- [ ] Contradictions are condition-aware: claims with non-overlapping conditions are NOT marked as contradictions
- [ ] Every claim has a `BeliefState` with confidence, stability, and trend
- [ ] Retrieval is claim-first: `query → claims → evidence → documents`
- [ ] Query "accuracy on ImageNet" returns claims with belief states + TABLE evidence, not random text spans

### Reasoning (Phases 5-6)

- [ ] All 5 capabilities are functional and produce structured, evidence-bound output
- [ ] Every claim in a generated hypothesis traces back to specific chunks in specific papers
- [ ] Critique agent finds real counter-evidence via graph traversal, not hallucinated objections
- [ ] Generated proposals cite specific evidence with provenance chains
- [ ] Agent loops converge within bounded iterations (default 3)
- [ ] Consensus reports include condition-aware contradiction classification (direct vs. conditional vs. temporal)

### Dynamic System (Phase 8)

- [ ] New paper ingestion triggers automatic belief recomputation for affected claims
- [ ] Belief changes propagate to dependent hypotheses (flagged for re-evaluation)
- [ ] Temporal reasoning detects when newer results supersede older claims
- [ ] Hypotheses are persistent: tracked, versioned, and updated when grounding beliefs change
- [ ] System state dashboard shows knowledge health (contested zones, unstable beliefs, stale hypotheses)
- [ ] System produces **better outputs as corpus grows** — not just more outputs

### Quality (Phase 7)

- [ ] Every pipeline step produces a structured log entry with trace ID
- [ ] Any output artifact can be traced back to its source documents via provenance chain
- [ ] Deterministic services produce identical output for identical input (verified in CI)
- [ ] Evaluation corpus of 50 papers with automated regression metrics
- [ ] Pipeline success rate >95% across evaluation corpus

### Architecture

- [ ] No service imports another service (all flow through orchestrator + MCP)
- [ ] All prompts served through prompt registry (YAML-based, no inline strings)
- [ ] All core processing runs locally (no cloud API dependencies for reasoning)
- [ ] System fails loudly on LLM unavailability rather than silently degrading
- [ ] Claims are the primary unit of intelligence — not chunks, not embeddings

---

_This document is the authoritative execution plan for the ScholarOS enterprise conversion. All implementation work should reference this plan for scope, sequencing, and acceptance criteria._

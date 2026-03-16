# Structured Source-First Ingestion Pipeline

## Overview

The structured ingestion pipeline prioritizes HTML sources over PDF for academic paper extraction. HTML provides native document structure (headings, sections, tables, references) that PDF extraction must reconstruct heuristically.

**Architecture principle:** HTML first, PDF fallback, metadata enrichment always.

## Source Resolution Hierarchy

```
Input identifier
    │
    ├─ arXiv ID (2401.12345)
    │   → HTML: arxiv.org/html/{id}
    │   → PDF:  arxiv.org/pdf/{id}.pdf
    │
    ├─ PMC ID (PMC1234567)
    │   → HTML: ncbi.nlm.nih.gov/pmc/articles/{id}/
    │   → PDF:  ncbi.nlm.nih.gov/pmc/articles/{id}/pdf/
    │
    ├─ ACL ID (2023.acl-long.1)
    │   → HTML: aclanthology.org/{id}/
    │   → PDF:  aclanthology.org/{id}.pdf
    │
    ├─ DOI (10.xxxx/...)
    │   → Resolve via doi.org redirect
    │   → Check OpenAlex for arXiv cross-listing (Phase 2)
    │   → HTML: publisher landing page
    │   → PDF:  if available via open access
    │
    └─ URL (https://...)
        → Direct HTML fetch
```

### arXiv Priority via OpenAlex (Phase 2)

When a DOI is resolved, the pipeline queries OpenAlex to check if the paper has an arXiv cross-listing. If found, arXiv HTML is preferred over the publisher page because:

- arXiv HTML (LaTeXML) has the most consistent DOM structure
- No paywall or access restrictions
- Rich semantic markup (equations, theorems, proofs)

## Publisher-Specific HTML Strategies

| Publisher | DOM Signature | Strategy | Key Selectors |
|-----------|--------------|----------|---------------|
| arXiv     | `article.ltx_document` | ArxivHTMLExtractor | `h1.ltx_title`, `section.ltx_section`, `figure.ltx_table` |
| PMC       | `div.tsec` | PMCHTMLExtractor | `h1.content-title`, `div.table-wrap`, `div.ref-list` |
| ACL       | `div#acl-abstract` | ACLHTMLExtractor | `h2#title`, `meta[name=citation_author]` |
| Nature    | `div.c-article-body` | GenericHTMLExtractor | `meta[name=citation_title]`, heading-based sections |
| IEEE      | `div.abstract-text` | GenericHTMLExtractor | meta tags, heading-based sections |
| Springer  | `section[data-title]` | GenericHTMLExtractor | meta tags, heading-based sections |
| Elsevier  | `div.Abstracts` | GenericHTMLExtractor | meta tags, heading-based sections |
| ICLR/OR   | `div#note_content` | GenericHTMLExtractor | OpenReview-specific layout |

### DOM Signature Detection (Phase 4)

The `dom_signatures` module identifies publisher identity from HTML structure alone, without relying on URL patterns. This handles:

- Proxied or cached pages (institutional proxies)
- URL redirects that obscure the publisher
- Custom publisher domains

## HTML Quality Validation (Phase 3)

After HTML extraction, the pipeline validates quality before accepting:

| Threshold | Minimum | Purpose |
|-----------|---------|---------|
| Word count | 500 | Ensures substantive content extracted |
| Section count | 3 | Validates structural parsing success |

If thresholds fail, the pipeline falls back to PDF extraction.

## Pipeline Flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  Resolve ID │ ──► │ HTML Extract │ ──► │ Quality Check │ ──► │ Dual Source  │
│  (URLs)     │     │ (publisher)  │     │ (word/section)│     │ Verification │
└─────────────┘     └──────────────┘     └───────────────┘     └──────────────┘
                          │                     │ fail                │
                          │ fail                ▼                     │
                          │              ┌──────────────┐             │
                          └─────────────►│ PDF Fallback │◄────────────┘
                                         └──────────────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │    Enrich    │
                                            │    (APIs)    │
                                            └──────────────┘
```

### Dual-Source Verification (Solution 5)

After HTML passes structural quality checks, the pipeline performs a quick PDF probe and applies:

- Compute `HTML_word_count` from extracted HTML document
- Compute `PDF_word_count` using fast PDF text extraction on first pages (no full parsing)
- Decision rule:

```
if HTML_word_count < 0.4 * PDF_word_count:
    use PDF
else:
    use HTML
```

This catches partial/landing HTML pages that look structurally valid but miss major content.

## Output Format

All extraction normalizes to `ResearchDocument`:

```python
ResearchDocument(
    id="sha256_hash",
    title="Paper Title",
    authors=["Author 1", "Author 2"],
    abstract="...",
    sections=[Section(title="Introduction", level=1, content="...")],
    tables=[Table(markdown="| ... |", caption="Table 1", rows=5, cols=3)],
    figures=[Figure(caption="Figure 1", url="figs/fig_001.png")],
    references=[Reference(raw="...", title="...", doi="...")],
    source_type=SourceType.ARXIV_HTML,
    source_url="https://arxiv.org/html/2401.12345",
    raw_text="Full text...",
    metadata={"doi": "10.xxx", "year": 2024, "venue": "NeurIPS"},
)
```

### Bridge Methods

`ResearchDocument` provides backward-compatible conversion to existing pipeline schemas:

- `to_extraction_result()` → ExtractionResult (dataclass used by existing extractors)
- `to_ingestion_result()` → IngestionResult (Pydantic schema used by services/ingestion)
- `to_markdown()` → Full paper as Markdown string

## Asset Download (Phase 5)

The `AssetDownloader` retrieves figure images referenced in HTML:

- Downloads to `papers/{paper_id}/figures/fig_001.png`
- Resolves relative URLs against source page
- Skips assets > 20 MB
- Rate-limited (0.5s between requests)
- Rewrites `Figure.url` to local paths

## Metadata Enrichment

Three academic APIs (all free, unauthenticated):

| Provider | Priority | Data Available |
|----------|----------|---------------|
| Semantic Scholar | 1 (richest) | title, authors, abstract, year, venue, citations, references, DOI, arXiv ID |
| OpenAlex | 2 | title, authors, DOI, year, venue, citations, OA URL |
| Crossref | 3 | title, authors, DOI, year, venue, citations, abstract |

**Merge rule:** Missing fields are filled; existing fields are NOT overwritten.

## Evaluation Tools

### 40-Paper Benchmark (Phase 6)

```bash
# Full benchmark (40 papers, 10 publishers)
python -m researcher_ai.evaluation.ingestion_integrity_test

# Quick mode (10 papers)
python -m researcher_ai.evaluation.ingestion_integrity_test --quick
```

### Source Comparison (Phase 7)

Compares HTML vs PDF extraction for the same papers:

```bash
python -m researcher_ai.evaluation.source_comparison
```

Metrics: word count ratio, section recovery, table recovery, keyword overlap.

### Benchmark Report (Phase 8)

Generates Markdown report from JSON results:

```bash
# Run benchmark + comparison first, then:
python -m researcher_ai.evaluation.generate_benchmark_report
# Output: reports/source_integrity_benchmark.md
```

### Performance Profiling (Phase 9)

```bash
python -m researcher_ai.evaluation.profile_ingestion
python -m researcher_ai.evaluation.profile_ingestion --papers 3
```

Measures per-stage latency: resolution, HTML fetch, PDF fallback, enrichment.

## Module Reference

| Module | Purpose |
|--------|---------|
| `researcher_ai.ingestion.paper_ingestor` | Top-level orchestrator |
| `researcher_ai.ingestion.source_resolver` | ID → URL resolution + arXiv priority |
| `researcher_ai.ingestion.html_extractor` | Publisher-specific HTML parsing |
| `researcher_ai.ingestion.pdf_fallback` | PDF extraction via PyMuPDF/Docling |
| `researcher_ai.ingestion.metadata_enrichment` | Academic API enrichment |
| `researcher_ai.ingestion.research_document` | Canonical paper model |
| `researcher_ai.ingestion.dom_signatures` | Publisher detection from DOM |
| `researcher_ai.ingestion.asset_downloader` | Figure/image download |
| `researcher_ai.evaluation.ingestion_integrity_test` | 40-paper benchmark |
| `researcher_ai.evaluation.source_comparison` | HTML vs PDF comparison |
| `researcher_ai.evaluation.generate_benchmark_report` | Report generator |
| `researcher_ai.evaluation.profile_ingestion` | Performance profiling |

## HTML vs PDF Trade-offs

| Aspect | HTML | PDF |
|--------|------|-----|
| Structure | Native headings, sections | Heuristic reconstruction |
| Tables | Clean HTML → markdown | Visual layout parsing |
| Equations | MathML / LaTeX in DOM | Image-only or OCR |
| Figures | `<img>` with captions | Page-level image extraction |
| References | Structured links | Regex-based parsing |
| Availability | Limited publishers | Universal |
| Consistency | Varies by publisher | Varies by extractor |

**Recommendation:** Use HTML when available (arXiv, PMC); PDF for everything else.

# Structured Source-First Paper Ingestion Pipeline

## Overview

The `html_ingestion_poc/` module implements a **source-first** paper ingestion pipeline
that prioritizes structured HTML sources over PDF extraction. The resolution hierarchy:

1. **HTML** from publisher (arXiv, PMC, ACL Anthology, generic)
2. **PDF fallback** via PyMuPDF/Docling (when HTML unavailable or insufficient)
3. **Metadata enrichment** from free academic APIs (Semantic Scholar, OpenAlex, Crossref)

All sources normalize to a canonical `ResearchDocument` that bridges into the existing
researcher-ai pipeline via `to_extraction_result()` and `to_ingestion_result()`.

## Architecture

```
identifier (arXiv ID / DOI / PMC ID / URL)
        │
        ▼
  SourceResolver  ──→  ResolvedSource
        │               (html_url, pdf_url, api_urls)
        ▼
  HTMLExtractor   ──→  ArxivHTMLExtractor
        │               PMCHTMLExtractor
        │               ACLHTMLExtractor
        │               GenericHTMLExtractor
        │
        │  (if HTML fails or yields <100 chars)
        ▼
  PDFFallback     ──→  PyMuPDFExtractor / DoclingExtractor
        │
        ▼
  MetadataEnricher ──→  Semantic Scholar API
        │                OpenAlex API
        │                Crossref API
        ▼
  ResearchDocument  ──→  PaperStore (local filesystem)
        │
        ├──→ to_extraction_result()    → ExtractionResult (existing pipeline)
        ├──→ to_ingestion_result()     → IngestionResult with chunks
        └──→ to_markdown()             → human-readable render
```

## Components

### ResearchDocument (`models/research_document.py`)
Canonical paper representation. All ingestion paths normalize here.
- Pydantic BaseModel with full validation
- Sub-models: Section, Reference, Figure, Table
- Bridge methods for existing pipeline compatibility
- Stable ID generation from identifiers

### SourceResolver (`ingestion/source_resolver.py`)
Identifier → URLs. Detects type via regex patterns:
- arXiv: `\d{4}\.\d{4,5}(v\d+)?`
- PMC: `PMC\d{5,9}`
- ACL: `\d{4}.(acl|emnlp|naacl|...)-...`
- DOI: `10.\d{4,9}/...`
- Falls back to URL or UNKNOWN

### HTMLExtractor (`ingestion/html_extractor.py`)
Publisher-specific DOM parsing using BeautifulSoup + lxml:
- **ArxivHTMLExtractor**: LaTeXML selectors (`ltx_title`, `ltx_abstract`, sections, `ltx_table`, `ltx_figure`)
- **PMCHTMLExtractor**: JATS-rendered selectors (`content-title`, `tsec`, `table-wrap`, `fig`)
- **ACLHTMLExtractor**: Anthology landing pages (title, authors, abstract via meta tags)
- **GenericHTMLExtractor**: Readability heuristics (headings, article/main elements, meta tags)

### MetadataEnricher (`ingestion/metadata_enrichment.py`)
Free academic API integration:
- **Semantic Scholar**: Richest data (authors, abstract, refs, citation count, DOI)
- **OpenAlex**: Good coverage by DOI or title search
- **Crossref**: DOI-based, includes full bibliographic metadata
- Priority: S2 > OpenAlex > Crossref. Fills empty fields without overwriting.

### PDFFallback (`ingestion/pdf_fallback.py`)
Reuses existing extractors when HTML is unavailable:
- Downloads PDF via rate-limited HTTP
- Invokes PyMuPDFExtractor (default) or DoclingExtractor
- Converts ExtractionResult → ResearchDocument

### PaperIngestor (`ingestion/paper_ingestor.py`)
Top-level orchestrator:
- Resolve → HTML → PDF fallback → Enrich
- File-based JSON cache (configurable)
- Graceful degradation at every stage

### PaperStore (`storage/paper_store.py`)
Structured filesystem storage:
```
papers/{id}/
  paper.md        — markdown rendering
  metadata.json   — full Pydantic model
  tables.json     — structured tables
  figures/        — figure metadata
```

## Usage

```python
from html_ingestion_poc.ingestion.paper_ingestor import PaperIngestor

ingestor = PaperIngestor(cache_dir=Path("cache"))

# Ingest by arXiv ID
doc = ingestor.ingest("2401.12345")

# Ingest by DOI
doc = ingestor.ingest("10.1038/s41586-021-03819-2")

# Bridge to existing pipeline
extraction_result = doc.to_extraction_result()
ingestion_result = doc.to_ingestion_result()
```

## Running the Integrity Test

```bash
# Quick mode — 10 papers
python -m html_ingestion_poc.evaluation.ingestion_integrity_test --quick

# Full mode — 30 papers across 7 publishers
python -m html_ingestion_poc.evaluation.ingestion_integrity_test

# Generate markdown report from results
python -m html_ingestion_poc.evaluation.generate_benchmark_report
```

## Rate Limiting

All HTTP requests use a 1 req/sec rate limit with polite User-Agent headers.
API requests use 10-second timeouts with graceful degradation.

## Dependencies

- `httpx` — async-capable HTTP client
- `beautifulsoup4` + `lxml` — HTML parsing
- `pydantic` — data validation
- Existing: `pymupdf` (PyMuPDFExtractor), optionally `docling`

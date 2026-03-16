# Ingestion Integrity Benchmark Report

**Generated:** 2026-03-15 20:53 UTC
**Papers tested:** 10
**Successful:** 10
**Failed:** 0
**Success rate:** 100.0%
**Total time:** 32.8s

## Results by Category

| Category | Tested | Passed | Failed | Rate | Avg Time |
|----------|--------|--------|--------|------|----------|
| acl | 2 | 2 | 0 | 100% | 1.6s |
| arxiv | 3 | 3 | 0 | 100% | 4.4s |
| doi | 1 | 1 | 0 | 100% | 3.2s |
| metadata | 1 | 1 | 0 | 100% | 3.2s |
| pdf_fallback | 1 | 1 | 0 | 100% | 0.0s |
| pmc | 2 | 2 | 0 | 100% | 5.0s |

## Per-Paper Results

| # | ID | Category | Status | Source | Words | Sections | Tables | Refs | Time |
|---|-------|----------|--------|--------|-------|----------|--------|------|------|
| 1 | `2401.02385` | arxiv | ✅ | arxiv_html | 1439 | 10 | 7 | 47 | 4.16s |
| 2 | `2310.06825` | arxiv | ✅ | arxiv_html | 1938 | 9 | 6 | 29 | 4.48s |
| 3 | `2305.10601` | arxiv | ✅ | arxiv_html | 8039 | 14 | 7 | 44 | 4.61s |
| 4 | `PMC7029158` | pmc | ✅ | pmc_html | 7914 | 20 | 1 | 21 | 4.95s |
| 5 | `PMC6993921` | pmc | ✅ | pmc_html | 29275 | 416 | 73 | 249 | 4.97s |
| 6 | `2023.acl-long.1` | acl | ✅ | acl_html | 234 | 0 | 0 | 0 | 1.71s |
| 7 | `2023.emnlp-main.1` | acl | ✅ | acl_html | 193 | 0 | 0 | 0 | 1.53s |
| 8 | `10.1038/s41586-021-03819-2` | doi | ✅ | publisher_html | 14818 | 54 | 0 | 6 | 3.16s |
| 9 | `2401.02385` | pdf_fallback | ✅ | arxiv_html | 1439 | 10 | 7 | 47 | 0.04s |
| 10 | `10.1038/s41586-023-06747-5` | metadata | ✅ | publisher_html | 17807 | 81 | 0 | 6 | 3.23s |

## Content Quality Summary

- **Total words extracted:** 83,096
- **Average words/paper:** 8,309
- **Total sections:** 614
- **Total tables:** 101
- **Total references:** 449
- **Papers with title:** 10/10
- **Papers with abstract (>50 chars):** 10/10
- **Papers with sections:** 8/10

## Pipeline Architecture

```
Identifier → SourceResolver → ResolvedSource
                                    │
                          ┌─────────┴──────────┐
                     HTMLExtractor         PDFFallback
                     (arxiv/pmc/acl/       (pymupdf/
                      generic)              docling)
                          └─────────┬──────────┘
                                    │
                          MetadataEnricher
                          (S2 / OpenAlex / Crossref)
                                    │
                          ResearchDocument
                                    │
                   ┌────────────────┼────────────────┐
              to_markdown()    to_ingestion_result()  PaperStore
```

# Ingestion 50-Paper Benchmark Report (v2)

## 1. Overall Performance

| Metric | Value |
|------ | -----:|
| Dataset candidates | 66 |
| Papers processed | 50 |
| Successful ingestions | 50 |
| Failures | 0 |
| Success rate | 100.00% |
| Average ingestion time | 1.3781 seconds |

## 2. Dataset Validation

- initial candidates considered: 66
- invalid/unusable removed: 4
- final validated dataset size: 62
- entries with primary accessible source: 62

Dataset composition by identifier type:

| Identifier type | Count |
|------ | -----:|
| arxiv | 30 |
| pmc | 20 |
| acl | 8 |
| url | 4 |

## 3. Source Accessibility

- HTML accessible entries: 40
- PDF accessible entries: 62
- OA mirror used during validation: 0

Ingestion source selection (successful papers):

| Source selected | Count |
|------ | -----:|
| pdf_pymupdf | 21 |
| pmc_html | 19 |
| arxiv_html | 10 |

## 4. Resolver Accuracy

- exact expected-source match: 43/50 (86.00%)
- source-family match (html/pdf): 43/50 (86.00%)

Top mismatches (expected vs selected):

| Paper ID | Expected | Selected |
|------ | ------ | ------ |
| 2304.01196 | arxiv_html | pdf_pymupdf |
| 2308.12950 | arxiv_html | pdf_pymupdf |
| 2312.00752 | arxiv_html | pdf_pymupdf |
| 2401.13601 | arxiv_html | pdf_pymupdf |
| 2403.04652 | arxiv_html | pdf_pymupdf |
| 2309.05519 | arxiv_html | pdf_pymupdf |
| PMC7970379 | pmc_html | pdf_pymupdf |

## 5. Retry and Switching

- papers requiring retry: 0
- papers ingested using alternate identifier: 0

Switch reason distribution (benchmark summary):

| reason | count |
|------ | -----:|
| none | 29 |
| manual_fallback | 16 |
| ratio | 4 |
| ref_guard | 1 |

## 6. Performance Profiling

| Stage | Avg time (s) |
|------ | -----:|
| resolve stage | 0.0000 |
| HTML extraction | 0.2761 |
| PDF probe | 0.6407 |
| PDF extraction | 0.4484 |
| metadata enrichment | 0.0000 |
| total ingestion | 1.3781 |

## 7. Logging Audit

DUAL_SOURCE_SWITCH entries parsed from benchmark log:

| switch_reason | count |
|------ | -----:|
| ratio | 4 |
| ref_guard | 1 |

## 8. Optional HTML-vs-PDF Comparison

- comparison records with word_count_ratio: 18
- average word_count_ratio: 746.3433

## 9. Publisher Composition (Validated Dataset)

| Publisher | Count |
|------ | -----:|
| arXiv | 30 |
| PubMed Central | 20 |
| ACL Anthology | 8 |
| PMLR/ICML | 4 |


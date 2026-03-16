# Ingestion 50-Paper Benchmark Report

## 1. Overall Performance

| Metric | Value |
|------ | -----:|
| Total papers | 50 |
| Successful ingestions | 28 |
| Failures | 22 |
| Success rate | 56.00% |
| Average ingestion time | 1.1016 seconds |

## 2. Source Selection Distribution

| Source | Count | % |
|------ | -----:| --:|
| pdf_pymupdf | 9 | 32.14% |
| pmc_html | 9 | 32.14% |
| arxiv_html | 5 | 17.86% |
| publisher_html | 5 | 17.86% |

Switch reasons:

| reason | count |
|------ | -----:|
| none | 19 |
| manual_fallback | 9 |

## 3. Publisher Reliability

| Publisher | Papers | HTML success | PDF fallback | Avg ingestion time |
|------ | -----:| -----:| -----:| -----:|
| ACL Anthology | 5 | 0 | 3 | 1.5192s |
| Elsevier | 5 | 0 | 0 | 1.5644s |
| IEEE | 5 | 0 | 0 | 1.6621s |
| Nature/Science | 5 | 3 | 0 | 0.4850s |
| NeurIPS/ICML/ICLR | 5 | 2 | 0 | 0.8874s |
| PubMed Central | 10 | 9 | 1 | 0.3215s |
| Springer | 5 | 0 | 0 | 1.2350s |
| arXiv | 10 | 5 | 5 | 1.5101s |

## 4. Structural Extraction Quality

- total words extracted: 339240
- total tables extracted: 62
- total figures extracted: 287
- total references extracted: 919
- average sections per paper: 78.6071

## 5. HTML vs PDF Comparison

- papers with both sources: 18
- avg word ratio (HTML/PDF): 746.3433
- avg reference overlap: 0.2778
- avg section overlap: 0.0014
- avg table overlap: 0.4444

## 6. Performance Profiling

| Stage | Avg time (s) |
|------ | -----:|
| resolve stage | 0.1047 |
| HTML extraction | 0.5180 |
| PDF probe | 0.0000 |
| PDF extraction | 0.1263 |
| metadata enrichment | 0.3465 |
| total ingestion | 1.1016 |

## 7. Failure Analysis

- publisher_block: 2
  - paper_ids: 10.1126/science.abq2594, 10.1126/science.aaa8415
- html_parse_failure: 17
  - paper_ids: 2005.14165, 2103.00020, 2203.02155, 2307.09288, 2305.14314, 10.1126/science.abq2594, 10.1126/science.aaa8415, 10.1007/s00521-020-05348-3, 10.1007/s10489-021-02547-0, 10.1007/s11042-021-10795-3, 10.1007/s11227-020-03488-w, 10.1007/s13042-021-01450-8, 10.1109/TPAMI.2021.3114613, 10.1109/TNNLS.2020.3038445, 10.1109/JIOT.2021.3071497, 10.1109/ACCESS.2020.3021021, 10.1016/j.artint.2020.103395
- missing_references: 12
  - paper_ids: 2005.14165, 2103.00020, 2203.02155, 2307.09288, 2305.14314, PMC7440596, PMC7970379, 2020.acl-main.703, 2021.acl-long.353, 2022.acl-long.1, https://proceedings.mlr.press/v139/radford21a.html, https://proceedings.mlr.press/v202/liu23f.html
- missing_sections: 1
  - paper_ids: PMC7970379
- missing_tables: 18
  - paper_ids: 2005.14165, 2103.00020, 2203.02155, 2307.09288, 2305.14314, PMC7239045, PMC7440596, PMC7543892, PMC7685680, PMC7970379, 2020.acl-main.703, 2021.acl-long.353, 2022.acl-long.1, https://proceedings.mlr.press/v139/radford21a.html, https://proceedings.mlr.press/v202/liu23f.html, 10.1038/s41586-021-03819-2, 10.1038/s41586-020-2649-2, 10.1038/s41586-019-1666-5

## 8. Decision Rule Evaluation

- ratio sample count: 11
- ratio mean: 1424.6629
- ratio median: 1004.6667
- ratio min: 0.5012
- ratio max: 6280.3333
- heuristic false positives: 0
- heuristic false negatives: 0

## 9. Logging Audit (DUAL_SOURCE_SWITCH)

| switch_reason | count |
|------ | -----:|
| ratio | 3 |

## 10. Visualization Artifacts

- source selection bar chart: reports/figures/source_selection_bar_chart.png
- source distribution: reports/figures/source_distribution.png
- ingestion time distribution: reports/figures/timing_histogram.png
- section count distribution: reports/figures/section_count_distribution.png
- ratio distribution: reports/figures/ratio_distribution.png

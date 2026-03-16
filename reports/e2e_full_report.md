# Researcher-AI E2E Test Report — Phase 0–4

**Run date:** 2026-03-16T13:19:35.355882+00:00  
**Papers tested:** 25  
**Pipeline:** ingestion → extraction → normalization → belief → contradiction

---

## Summary

| Metric | Value |
|--------|-------|
| Total papers | 25 |
| ✅ Full success | 19 (76.0%) |
| ⚠️ Partial success | 6 (24.0%) |
| ❌ Failed | 0 |
| Total chunks ingested | 20974 |
| Total claims extracted | 655 |
| Total normalized claims | 131 |
| Total contradictions found | 182 |
| Total pipeline time | 18361.0 ms |
| Avg time per paper | 734.4 ms |

---

## Per-Paper Results

| # | Paper ID | Type | Outcome | Chunks | Claims | Normalized | Contradictions | Total ms | Notes |
|---|----------|------|---------|--------|--------|------------|---------------|----------|-------|
| 1 | `10.1038_s41586-021-03819-2` | integrity | ✅ success | 1045 | 37 | 7 | 8 | 738.8 |  |
| 2 | `10.1038_s41586-023-06747-5` | integrity | ✅ success | 945 | 23 | 2 | 0 | 755.1 |  |
| 3 | `2023.acl-long.1` | integrity | ⚠️ partial_success | 8 | 1 | 0 | 0 | 10.3 |  |
| 4 | `2023.emnlp-main.1` | integrity | ⚠️ partial_success | 9 | 1 | 0 | 0 | 9.5 |  |
| 5 | `2305.10601` | integrity | ✅ success | 679 | 13 | 1 | 0 | 462.8 |  |
| 6 | `2310.06825` | integrity | ✅ success | 185 | 7 | 1 | 0 | 173.4 |  |
| 7 | `2401.02385` | integrity | ⚠️ partial_success | 299 | 4 | 0 | 0 | 187.9 |  |
| 8 | `PMC6993921` | integrity | ✅ success | 2750 | 33 | 4 | 4 | 2993.9 |  |
| 9 | `PMC7029158` | integrity | ✅ success | 365 | 18 | 2 | 0 | 367.0 |  |
| 10 | `1706.03762` | cached_json | ✅ success | 160 | 25 | 4 | 3 | 180.3 |  |
| 11 | `1810.04805` | cached_json | ✅ success | 228 | 37 | 8 | 6 | 227.9 |  |
| 12 | `2005.14165` | cached_json | ✅ success | 1719 | 71 | 23 | 76 | 1600.6 |  |
| 13 | `2020.acl-main.703` | cached_json | ✅ success | 351 | 35 | 7 | 0 | 308.4 |  |
| 14 | `2021.acl-long.353` | cached_json | ✅ success | 601 | 21 | 6 | 2 | 491.2 |  |
| 15 | `2021.naacl-main.10` | cached_json | ✅ success | 503 | 15 | 4 | 3 | 417.4 |  |
| 16 | `2022.acl-long.1` | cached_json | ⚠️ partial_success | 579 | 20 | 0 | 0 | 438.7 |  |
| 17 | `2022.emnlp-main.43` | cached_json | ⚠️ partial_success | 625 | 19 | 0 | 0 | 476.2 |  |
| 18 | `2023.acl-long.16` | cached_json | ⚠️ partial_success | 620 | 11 | 0 | 0 | 455.9 |  |
| 19 | `2103.00020` | cached_json | ✅ success | 1759 | 61 | 20 | 44 | 1481.6 |  |
| 20 | `2203.02155` | cached_json | ✅ success | 1450 | 35 | 9 | 1 | 1275.9 |  |
| 21 | `2204.02311` | cached_json | ✅ success | 2327 | 92 | 23 | 33 | 2005.9 |  |
| 22 | `2205.01068` | cached_json | ✅ success | 879 | 20 | 2 | 0 | 685.6 |  |
| 23 | `2206.07682` | cached_json | ✅ success | 754 | 22 | 3 | 0 | 638.9 |  |
| 24 | `2210.11610` | cached_json | ✅ success | 683 | 27 | 3 | 1 | 503.4 |  |
| 25 | `2211.01786` | cached_json | ✅ success | 1451 | 7 | 2 | 1 | 1474.4 |  |

---

## Step-by-Step Timing (ms)

| Paper ID | Ingestion | Extraction | Normalization | Belief | Contradiction |
|----------|-----------|------------|---------------|--------|---------------|
| `10.1038_s41586-021-03819-2` | 129.2 | 595.5 | 13.7 | 0.2 | 0.1 |
| `10.1038_s41586-023-06747-5` | 144.2 | 601.5 | 9.2 | 0.1 | 0.0 |
| `2023.acl-long.1` | 1.9 | 7.9 | 0.5 | 0.0 | 0 |
| `2023.emnlp-main.1` | 1.9 | 7.0 | 0.6 | 0.0 | 0 |
| `2305.10601` | 79.4 | 377.0 | 6.3 | 0.1 | 0.0 |
| `2310.06825` | 30.7 | 138.6 | 4.0 | 0.1 | 0.0 |
| `2401.02385` | 35.4 | 150.4 | 2.1 | 0.0 | 0 |
| `PMC6993921` | 596.7 | 2381.8 | 14.3 | 0.7 | 0.3 |
| `PMC7029158` | 74.1 | 285.7 | 7.0 | 0.1 | 0.1 |
| `1706.03762` | 33.6 | 137.1 | 9.2 | 0.2 | 0.1 |
| `1810.04805` | 42.9 | 171.8 | 12.8 | 0.2 | 0.1 |
| `2005.14165` | 337.6 | 1238.2 | 24.0 | 0.3 | 0.5 |
| `2020.acl-main.703` | 58.3 | 237.4 | 12.4 | 0.2 | 0.1 |
| `2021.acl-long.353` | 96.4 | 386.3 | 8.3 | 0.2 | 0.1 |
| `2021.naacl-main.10` | 113.0 | 299.7 | 4.3 | 0.1 | 0.1 |
| `2022.acl-long.1` | 85.3 | 344.6 | 8.7 | 0.0 | 0 |
| `2022.emnlp-main.43` | 86.4 | 381.3 | 8.6 | 0.0 | 0 |
| `2023.acl-long.16` | 85.1 | 365.4 | 5.4 | 0.0 | 0 |
| `2103.00020` | 320.5 | 1142.2 | 18.4 | 0.3 | 0.3 |
| `2203.02155` | 247.3 | 1017.3 | 11.0 | 0.2 | 0.1 |
| `2204.02311` | 388.7 | 1585.5 | 31.1 | 0.3 | 0.3 |
| `2205.01068` | 138.9 | 539.6 | 6.9 | 0.1 | 0.0 |
| `2206.07682` | 122.4 | 508.5 | 7.9 | 0.1 | 0.0 |
| `2210.11610` | 89.2 | 404.0 | 10.0 | 0.1 | 0.1 |
| `2211.01786` | 309.6 | 1162.5 | 2.1 | 0.1 | 0.1 |

---

## Detailed Per-Paper Step Output

### `10.1038_s41586-021-03819-2`

- **Outcome:** success
- **Total time:** 738.8 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 129.2 ms
- Chunks: `1045`

#### ✅ Extraction
- Status: `success`
- Duration: 595.5 ms
- Claims Extracted: `37`
- Discarded Claims: `1009`

#### ✅ Normalization
- Status: `success`
- Duration: 13.7 ms
- Normalized Claims: `7`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `ACCURACY`
- Consensus Strength: `3.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `8`
- Consensus Groups: `2`

### `10.1038_s41586-023-06747-5`

- **Outcome:** success
- **Total time:** 755.1 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 144.2 ms
- Chunks: `945`

#### ✅ Extraction
- Status: `success`
- Duration: 601.5 ms
- Claims Extracted: `23`
- Discarded Claims: `927`

#### ✅ Normalization
- Status: `success`
- Duration: 9.2 ms
- Normalized Claims: `2`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `SCORE`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2023.acl-long.1`

- **Outcome:** partial_success
- **Total time:** 10.3 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 1.9 ms
- Chunks: `8`

#### ✅ Extraction
- Status: `success`
- Duration: 7.9 ms
- Claims Extracted: `1`
- Discarded Claims: `7`

#### ✅ Normalization
- Status: `success`
- Duration: 0.5 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2023.emnlp-main.1`

- **Outcome:** partial_success
- **Total time:** 9.5 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 1.9 ms
- Chunks: `9`

#### ✅ Extraction
- Status: `success`
- Duration: 7.0 ms
- Claims Extracted: `1`
- Discarded Claims: `8`

#### ✅ Normalization
- Status: `success`
- Duration: 0.6 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2305.10601`

- **Outcome:** success
- **Total time:** 462.8 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 79.4 ms
- Chunks: `679`

#### ✅ Extraction
- Status: `success`
- Duration: 377.0 ms
- Claims Extracted: `13`
- Discarded Claims: `667`

#### ✅ Normalization
- Status: `success`
- Duration: 6.3 ms
- Normalized Claims: `1`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `SOLVE_COUNT`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2310.06825`

- **Outcome:** success
- **Total time:** 173.4 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 30.7 ms
- Chunks: `185`

#### ✅ Extraction
- Status: `success`
- Duration: 138.6 ms
- Claims Extracted: `7`
- Discarded Claims: `178`

#### ✅ Normalization
- Status: `success`
- Duration: 4.0 ms
- Normalized Claims: `1`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `COMPRESSION_RATIO`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2401.02385`

- **Outcome:** partial_success
- **Total time:** 187.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 35.4 ms
- Chunks: `299`

#### ✅ Extraction
- Status: `success`
- Duration: 150.4 ms
- Claims Extracted: `4`
- Discarded Claims: `295`

#### ✅ Normalization
- Status: `success`
- Duration: 2.1 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `PMC6993921`

- **Outcome:** success
- **Total time:** 2993.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 596.7 ms
- Chunks: `2750`

#### ✅ Extraction
- Status: `success`
- Duration: 2381.8 ms
- Claims Extracted: `33`
- Discarded Claims: `2734`

#### ✅ Normalization
- Status: `success`
- Duration: 14.3 ms
- Normalized Claims: `4`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.7 ms
- Belief State Present: `True`
- Belief Metric: `REDUCTION_RATE`
- Consensus Strength: `4.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.3 ms
- Contradictions: `4`
- Consensus Groups: `1`

### `PMC7029158`

- **Outcome:** success
- **Total time:** 367.0 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 74.1 ms
- Chunks: `365`

#### ✅ Extraction
- Status: `success`
- Duration: 285.7 ms
- Claims Extracted: `18`
- Discarded Claims: `353`

#### ✅ Normalization
- Status: `success`
- Duration: 7.0 ms
- Normalized Claims: `2`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `REDUCTION_RATE`
- Consensus Strength: `2.0`
- Qualitative Confidence: `medium`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `0`
- Consensus Groups: `1`

### `1706.03762`

- **Outcome:** success
- **Total time:** 180.3 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 33.6 ms
- Chunks: `160`

#### ✅ Extraction
- Status: `success`
- Duration: 137.1 ms
- Claims Extracted: `25`
- Discarded Claims: `135`

#### ✅ Normalization
- Status: `success`
- Duration: 9.2 ms
- Normalized Claims: `4`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `BLEU`
- Consensus Strength: `3.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `3`
- Consensus Groups: `1`

### `1810.04805`

- **Outcome:** success
- **Total time:** 227.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 42.9 ms
- Chunks: `228`

#### ✅ Extraction
- Status: `success`
- Duration: 171.8 ms
- Claims Extracted: `37`
- Discarded Claims: `193`

#### ✅ Normalization
- Status: `success`
- Duration: 12.8 ms
- Normalized Claims: `8`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `F1`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `6`
- Consensus Groups: `1`

### `2005.14165`

- **Outcome:** success
- **Total time:** 1600.6 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 337.6 ms
- Chunks: `1719`

#### ✅ Extraction
- Status: `success`
- Duration: 1238.2 ms
- Claims Extracted: `71`
- Discarded Claims: `1659`

#### ✅ Normalization
- Status: `success`
- Duration: 24.0 ms
- Normalized Claims: `23`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.3 ms
- Belief State Present: `True`
- Belief Metric: `F1`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.5 ms
- Contradictions: `76`
- Consensus Groups: `2`

### `2020.acl-main.703`

- **Outcome:** success
- **Total time:** 308.4 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 58.3 ms
- Chunks: `351`

#### ✅ Extraction
- Status: `success`
- Duration: 237.4 ms
- Claims Extracted: `35`
- Discarded Claims: `317`

#### ✅ Normalization
- Status: `success`
- Duration: 12.4 ms
- Normalized Claims: `7`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `ROUGE`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2021.acl-long.353`

- **Outcome:** success
- **Total time:** 491.2 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 96.4 ms
- Chunks: `601`

#### ✅ Extraction
- Status: `success`
- Duration: 386.3 ms
- Claims Extracted: `21`
- Discarded Claims: `581`

#### ✅ Normalization
- Status: `success`
- Duration: 8.3 ms
- Normalized Claims: `6`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `REDUCTION_RATE`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `2`
- Consensus Groups: `1`

### `2021.naacl-main.10`

- **Outcome:** success
- **Total time:** 417.4 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 113.0 ms
- Chunks: `503`

#### ✅ Extraction
- Status: `success`
- Duration: 299.7 ms
- Claims Extracted: `15`
- Discarded Claims: `488`

#### ✅ Normalization
- Status: `success`
- Duration: 4.3 ms
- Normalized Claims: `4`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `SCORE`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `3`
- Consensus Groups: `1`

### `2022.acl-long.1`

- **Outcome:** partial_success
- **Total time:** 438.7 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 85.3 ms
- Chunks: `579`

#### ✅ Extraction
- Status: `success`
- Duration: 344.6 ms
- Claims Extracted: `20`
- Discarded Claims: `559`

#### ✅ Normalization
- Status: `success`
- Duration: 8.7 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2022.emnlp-main.43`

- **Outcome:** partial_success
- **Total time:** 476.2 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 86.4 ms
- Chunks: `625`

#### ✅ Extraction
- Status: `success`
- Duration: 381.3 ms
- Claims Extracted: `19`
- Discarded Claims: `607`

#### ✅ Normalization
- Status: `success`
- Duration: 8.6 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2023.acl-long.16`

- **Outcome:** partial_success
- **Total time:** 455.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 85.1 ms
- Chunks: `620`

#### ✅ Extraction
- Status: `success`
- Duration: 365.4 ms
- Claims Extracted: `11`
- Discarded Claims: `609`

#### ✅ Normalization
- Status: `success`
- Duration: 5.4 ms
- Normalized Claims: `0`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.0 ms
- Belief State Present: `False`
- Belief Metric: `None`
- Consensus Strength: `None`
- Qualitative Confidence: `None`

#### ⏭️ Contradiction
- Status: `skipped`
- Duration: 0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2103.00020`

- **Outcome:** success
- **Total time:** 1481.6 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 320.5 ms
- Chunks: `1759`

#### ✅ Extraction
- Status: `success`
- Duration: 1142.2 ms
- Claims Extracted: `61`
- Discarded Claims: `1702`

#### ✅ Normalization
- Status: `success`
- Duration: 18.4 ms
- Normalized Claims: `20`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.3 ms
- Belief State Present: `True`
- Belief Metric: `ACCURACY`
- Consensus Strength: `5.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.3 ms
- Contradictions: `44`
- Consensus Groups: `3`

### `2203.02155`

- **Outcome:** success
- **Total time:** 1275.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 247.3 ms
- Chunks: `1450`

#### ✅ Extraction
- Status: `success`
- Duration: 1017.3 ms
- Claims Extracted: `35`
- Discarded Claims: `1420`

#### ✅ Normalization
- Status: `success`
- Duration: 11.0 ms
- Normalized Claims: `9`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.2 ms
- Belief State Present: `True`
- Belief Metric: `ACCURACY`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `1`
- Consensus Groups: `2`

### `2204.02311`

- **Outcome:** success
- **Total time:** 2005.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 388.7 ms
- Chunks: `2327`

#### ✅ Extraction
- Status: `success`
- Duration: 1585.5 ms
- Claims Extracted: `92`
- Discarded Claims: `2245`

#### ✅ Normalization
- Status: `success`
- Duration: 31.1 ms
- Normalized Claims: `23`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.3 ms
- Belief State Present: `True`
- Belief Metric: `ACCURACY`
- Consensus Strength: `7.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.3 ms
- Contradictions: `33`
- Consensus Groups: `4`

### `2205.01068`

- **Outcome:** success
- **Total time:** 685.6 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 138.9 ms
- Chunks: `879`

#### ✅ Extraction
- Status: `success`
- Duration: 539.6 ms
- Claims Extracted: `20`
- Discarded Claims: `861`

#### ✅ Normalization
- Status: `success`
- Duration: 6.9 ms
- Normalized Claims: `2`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `PERPLEXITY`
- Consensus Strength: `1.0`
- Qualitative Confidence: `low`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.0 ms
- Contradictions: `0`
- Consensus Groups: `0`

### `2206.07682`

- **Outcome:** success
- **Total time:** 638.9 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 122.4 ms
- Chunks: `754`

#### ✅ Extraction
- Status: `success`
- Duration: 508.5 ms
- Claims Extracted: `22`
- Discarded Claims: `733`

#### ✅ Normalization
- Status: `success`
- Duration: 7.9 ms
- Normalized Claims: `3`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `PERPLEXITY`
- Consensus Strength: `3.0`
- Qualitative Confidence: `high`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.0 ms
- Contradictions: `0`
- Consensus Groups: `1`

### `2210.11610`

- **Outcome:** success
- **Total time:** 503.4 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 89.2 ms
- Chunks: `683`

#### ✅ Extraction
- Status: `success`
- Duration: 404.0 ms
- Claims Extracted: `27`
- Discarded Claims: `658`

#### ✅ Normalization
- Status: `success`
- Duration: 10.0 ms
- Normalized Claims: `3`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `ACCURACY`
- Consensus Strength: `2.0`
- Qualitative Confidence: `medium`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `1`
- Consensus Groups: `1`

### `2211.01786`

- **Outcome:** success
- **Total time:** 1474.4 ms

#### ✅ Ingestion
- Status: `success`
- Duration: 309.6 ms
- Chunks: `1451`

#### ✅ Extraction
- Status: `success`
- Duration: 1162.5 ms
- Claims Extracted: `7`
- Discarded Claims: `1446`

#### ✅ Normalization
- Status: `success`
- Duration: 2.1 ms
- Normalized Claims: `2`
- Failed Normalizations: `0`

#### ✅ Belief
- Status: `success`
- Duration: 0.1 ms
- Belief State Present: `True`
- Belief Metric: `BLEU`
- Consensus Strength: `2.0`
- Qualitative Confidence: `medium`

#### ✅ Contradiction
- Status: `success`
- Duration: 0.1 ms
- Contradictions: `1`
- Consensus Groups: `1`

---

*Generated by Researcher-AI E2E Harness*
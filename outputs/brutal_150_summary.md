# Brutal 150 Audit Summary

## Architecture Gates
- Determinism %: 86.58%
- Misbindings total: 27
- Pipeline errors: 63

## Yield
- Avg extracted: 3.693
- Avg normalized: 0.187
- Zero extraction %: 26.67%
- Zero normalization %: 85.33%

## Rejection Profile

### Top 15 Extraction Rejection Reasons
- context_missing: 237762
- table_fragment_rejected: 5949
- no_predicate: 2637
- no_number: 120
- compound_metric: 81
- hedged_statement: 57
- non_claim: 12
- object_missing: 3
- non_performance_numeric: 3

### Top 15 Normalization Rejection Reasons
- missing_metric: 1428
- missing_value: 123
- ambiguous_numeric_binding: 27

## Domain Breakdown
- astro-ph.*: papers=8, determinism_rate=87.50%, avg_extracted=1.125, avg_normalized=0.000, zero_extraction_rate=50.00%
- chem.*: papers=8, determinism_rate=100.00%, avg_extracted=1.000, avg_normalized=0.250, zero_extraction_rate=50.00%
- cond-mat.*: papers=7, determinism_rate=85.71%, avg_extracted=3.286, avg_normalized=0.143, zero_extraction_rate=28.57%
- cs.AI: papers=7, determinism_rate=85.71%, avg_extracted=5.286, avg_normalized=0.571, zero_extraction_rate=42.86%
- cs.CL: papers=7, determinism_rate=85.71%, avg_extracted=7.857, avg_normalized=0.571, zero_extraction_rate=28.57%
- cs.CV: papers=8, determinism_rate=87.50%, avg_extracted=6.125, avg_normalized=0.375, zero_extraction_rate=12.50%
- cs.DB: papers=7, determinism_rate=71.43%, avg_extracted=1.429, avg_normalized=0.286, zero_extraction_rate=42.86%
- cs.DC: papers=7, determinism_rate=71.43%, avg_extracted=4.286, avg_normalized=0.000, zero_extraction_rate=28.57%
- cs.LG: papers=8, determinism_rate=87.50%, avg_extracted=3.750, avg_normalized=0.375, zero_extraction_rate=12.50%
- cs.NI: papers=8, determinism_rate=75.00%, avg_extracted=6.375, avg_normalized=0.125, zero_extraction_rate=25.00%
- cs.RO: papers=7, determinism_rate=85.71%, avg_extracted=3.714, avg_normalized=0.143, zero_extraction_rate=14.29%
- cs.SE: papers=8, determinism_rate=75.00%, avg_extracted=2.250, avg_normalized=0.000, zero_extraction_rate=25.00%
- econ.*: papers=8, determinism_rate=75.00%, avg_extracted=2.250, avg_normalized=0.000, zero_extraction_rate=37.50%
- eess.*: papers=7, determinism_rate=100.00%, avg_extracted=4.429, avg_normalized=0.000, zero_extraction_rate=28.57%
- math.*: papers=7, determinism_rate=100.00%, avg_extracted=1.143, avg_normalized=0.000, zero_extraction_rate=28.57%
- physics.*: papers=8, determinism_rate=100.00%, avg_extracted=2.125, avg_normalized=0.250, zero_extraction_rate=12.50%
- q-bio.*: papers=7, determinism_rate=85.71%, avg_extracted=5.571, avg_normalized=0.286, zero_extraction_rate=14.29%
- q-fin.*: papers=8, determinism_rate=75.00%, avg_extracted=3.000, avg_normalized=0.125, zero_extraction_rate=25.00%
- stat.*: papers=7, determinism_rate=85.71%, avg_extracted=5.286, avg_normalized=0.286, zero_extraction_rate=14.29%
- stat.ML: papers=8, determinism_rate=100.00%, avg_extracted=4.250, avg_normalized=0.000, zero_extraction_rate=12.50%

## Runtime Distribution
- mean: 270.912 ms
- std dev: 130.517 ms
- min: 42.662 ms
- max: 676.124 ms

## Risk Flags
- WARNING: Determinism below threshold: 86.58% < 95%
- CRITICAL: Misbinding count > 0: 27
- WARNING: Normalization yield low: 5.05% < 10%

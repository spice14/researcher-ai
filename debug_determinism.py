#!/usr/bin/env python
"""Debug non-determinism in pipeline execution.

Runs pipeline twice and compares outputs to identify source of variance.
"""

import json
import hashlib
from pathlib import Path
from core.mcp.registry import MCPRegistry
from services.orchestrator.mcp_orchestrator import MCPOrchestrator
from services.ingestion.tool import IngestionTool
from services.extraction.tool import ExtractionTool
from services.normalization.tool import NormalizationTool
from services.belief.tool import BeliefTool
from services.ingestion.pdf_loader import extract_pages_from_pdf


def setup_registry():
    """Initialize registry with tools."""
    registry = MCPRegistry()
    registry.register(IngestionTool())
    registry.register(ExtractionTool())
    registry.register(NormalizationTool())
    registry.register(BeliefTool())
    return registry


def hash_output(data: dict) -> str:
    """Deterministic hash of output dict (same as harness)."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()


def run_once(paper_path, run_num):
    """Execute pipeline once and return full output."""
    registry = setup_registry()
    
    pdf_pages = extract_pages_from_pdf(str(paper_path))
    raw_text = "\n".join(page.text for page in pdf_pages)
    
    orchestrator = MCPOrchestrator(registry)
    pipeline = ["ingestion", "extraction", "normalization", "belief"]
    initial_payload = {
        "raw_text": raw_text,
        "source_id": str(paper_path.stem)
    }
    
    trace = orchestrator.execute_pipeline(pipeline, initial_payload)
    result = trace.final_output
    
    # Build the same structure as harness
    output = {
        "extracted_claims": len(result.get("claims", [])),
        "normalized_claims": len(result.get("normalized_claims", [])),
        "contradictions": len(result.get("contradictions", [])),
        "consensus_groups": len(result.get("consensus_groups", [])),
        "trace_entries": len(trace.entries),
        "final_output_hash": trace.final_output_hash,
        "trace_duration_ms": trace.duration_ms,
        "full_output": result
    }
    
    return {
        "run": run_num,
        "output": output,
        "trace_hash": trace.final_output_hash,
        "harness_hash": hash_output(output),
    }


if __name__ == "__main__":
    paper = Path("data/real_paper_arxiv.pdf")
    
    print("[*] Running pipeline 3 times with fresh registries\n")
    
    results = []
    for i in range(1, 4):
        result = run_once(paper, i)
        results.append(result)
        print(f"Run {i}:")
        print(f"  trace.final_output_hash: {result['trace_hash'][:16]}...")
        print(f"  harness_hash:            {result['harness_hash'][:16]}...")
    
    # Check if trace hashes are deterministic
    trace_hashes = [r['trace_hash'] for r in results]
    harness_hashes = [r['harness_hash'] for r in results]
    
    print(f"\nTrace hashes deterministic? {len(set(trace_hashes)) == 1}")
    print(f"Harness hashes deterministic? {len(set(harness_hashes)) == 1}")
    
    if len(set(harness_hashes)) > 1:
        print(f"\n[✗] Harness hash is non-deterministic!")
        print(f"\nDifference between Run 1 and Run 2 outputs:")
        
        # Check trace_duration_ms
        if results[0]['output']['trace_duration_ms'] != results[1]['output']['trace_duration_ms']:
            print(f"  trace_duration_ms differs: {results[0]['output']['trace_duration_ms']} vs {results[1]['output']['trace_duration_ms']}")
        
        # Check full_output for non-deterministic objects
        print(f"\nFull output Run 1 keys: {results[0]['output']['full_output'].keys()}")
        print(f"Full output Run 2 keys: {results[1]['output']['full_output'].keys()}")
        
        # Deep check
        for key in results[0]['output']['full_output'].keys():
            val1 = results[0]['output']['full_output'].get(key)
            val2 = results[1]['output']['full_output'].get(key)
            if val1 != val2:
                print(f"\n  Key '{key}' differs:")
                print(f"    Type: {type(val1).__name__}")
                if isinstance(val1, (int, float)):
                    print(f"    Values: {val1} vs {val2}")
                elif isinstance(val1, dict):
                    print(f"    Dict size: {len(val1)} vs {len(val2)}")
                elif isinstance(val1, list):
                    print(f"    List size: {len(val1)} vs {len(val2)}")
                else:
                    print(f"    Value 1: {str(val1)[:50]}")
                    print(f"    Value 2: {str(val2)[:50]}")
    else:
        print(f"\n[✓] All hashes are deterministic!")


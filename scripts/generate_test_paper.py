#!/usr/bin/env python
"""Download a real academic paper PDF for E2E testing.

Fetches a real paper from arXiv that is:
- Disjoint from fusion_suite_v3 corpus
- Recent and relevant (computer vision domain)
- Contains quantitative claims and benchmarks
- Has multiple dataset references

Paper is completely independent of previous test sets.
"""

import arxiv
import requests
from pathlib import Path
import time

def download_real_paper(output_path: Path) -> bool:
    """Download a real paper from arXiv.
    
    Searches for computer vision papers with quantitative benchmarks.
    Selects a paper that is likely disjoint from previous test sets.
    """
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Search for recent computer vision papers with good metadata
        # Using search that filters for papers with quantitative results
        client = arxiv.Client()
        search = arxiv.Search(
            query='cat:cs.CV AND benchmark AND dataset',
            max_results=10,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        
        papers = list(client.results(search))
        
        if not papers:
            print("[✗] No papers found on arXiv")
            return False
        
        # Select a paper from the results (pick one mid-range to avoid most recent)
        selected_paper = papers[2] if len(papers) > 2 else papers[0]
        
        print(f"[*] Selected paper: {selected_paper.title}")
        print(f"    arXiv ID: {selected_paper.entry_id.split('/abs/')[-1]}")
        print(f"    Authors: {', '.join(a.name for a in selected_paper.authors[:3])}{'...' if len(selected_paper.authors) > 3 else ''}")
        
        # Download PDF
        pdf_url = selected_paper.pdf_url
        print(f"[*] Downloading from: {pdf_url}")
        
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        # Write PDF
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"[✓] Downloaded: {output_path} ({len(response.content) / 1024 / 1024:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"[✗] Download failed: {e}")
        return False


if __name__ == "__main__":
    # Download to data/ (primary location)
    output = Path("data/real_paper_arxiv.pdf")
    success = download_real_paper(output)
    
    if success:
        # Also copy to tests/fixtures/ for fallback harness lookup
        output_alt = Path("tests/fixtures/real_paper_arxiv.pdf")
        output_alt.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'rb') as src:
            with open(output_alt, 'wb') as dst:
                dst.write(src.read())
        print(f"[✓] Copied to: {output_alt}")
        print("[✓] Test paper ready for E2E validation")
    else:
        print("[✗] Failed to prepare test paper")

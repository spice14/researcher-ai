#!/usr/bin/env python
"""Build a reproducible brutal 150-paper real corpus from arXiv.

Phase 1:
- Query arXiv API across balanced domains
- Deterministically sample with fixed seed
- Download PDFs
- Validate PDFs using PyMuPDF + /Root + page count checks
- Emit metadata JSON with exactly 150 valid papers
"""

from __future__ import annotations

import json
import random
import re
import time
from http import HTTPStatus
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise RuntimeError("PyMuPDF is required. Install with: pip install pymupdf") from exc


ARXIV_API = "http://export.arxiv.org/api/query"
TARGET_TOTAL = 150
MIN_PER_DOMAIN = 5
SEED = 20260201
REQUEST_TIMEOUT = 45
MAX_RESULTS_PER_DOMAIN = 120
MAX_HTTP_RETRIES = 12
MIN_SECONDS_BETWEEN_REQUESTS = 6.0
OUTPUT_DIR = Path("outputs")
DATA_DIR = Path("data/brutal_150")
METADATA_PATH = OUTPUT_DIR / "brutal_150_metadata.json"
LAST_REQUEST_TS = 0.0


DOMAIN_CATEGORY_MAP: Dict[str, List[str]] = {
    "cs.LG": ["cs.LG"],
    "cs.AI": ["cs.AI"],
    "cs.CL": ["cs.CL"],
    "cs.CV": ["cs.CV"],
    "cs.RO": ["cs.RO"],
    "cs.NI": ["cs.NI"],
    "cs.DC": ["cs.DC"],
    "cs.DB": ["cs.DB"],
    "cs.SE": ["cs.SE"],
    "stat.ML": ["stat.ML"],
    "physics.*": ["physics.gen-ph", "physics.app-ph", "physics.data-an", "physics.bio-ph"],
    "cond-mat.*": ["cond-mat.mtrl-sci", "cond-mat.stat-mech", "cond-mat.quant-gas", "cond-mat.soft"],
    "astro-ph.*": ["astro-ph.CO", "astro-ph.GA", "astro-ph.SR", "astro-ph.IM"],
    "math.*": ["math.OC", "math.PR", "math.ST", "math.NA"],
    "q-bio.*": ["q-bio.BM", "q-bio.GN", "q-bio.NC", "q-bio.QM"],
    "q-fin.*": ["q-fin.ST", "q-fin.RM", "q-fin.MF", "q-fin.CP"],
    "eess.*": ["eess.AS", "eess.IV", "eess.SP", "eess.SY"],
    "econ.*": ["econ.EM", "econ.GN", "econ.TH"],
    "stat.*": ["stat.AP", "stat.CO", "stat.ME", "stat.TH"],
    "chem.*": ["physics.chem-ph", "cond-mat.mtrl-sci"],
}


@dataclass(frozen=True)
class ArxivPaper:
    arxiv_id: str
    title: str
    category: str
    published_date: str
    pdf_url: str
    domain: str


def _request_with_retry(url: str) -> requests.Response:
    """HTTP GET with explicit retry/backoff for arXiv rate limits.

    Retries on:
    - 429 (Too Many Requests)
    - 5xx server errors
    - transient request exceptions
    """
    global LAST_REQUEST_TS
    last_error: Optional[Exception] = None
    last_status: Optional[int] = None

    for attempt in range(1, MAX_HTTP_RETRIES + 1):
        try:
            now = time.time()
            elapsed = now - LAST_REQUEST_TS
            if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
                time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)

            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "ScholarOS-brutal150/1.0"},
            )
            LAST_REQUEST_TS = time.time()
            last_status = response.status_code

            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                retry_after = response.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after else (attempt * 15.0)
                print(f"  [RATE LIMIT] 429 received; retrying in {sleep_s:.1f}s (attempt {attempt}/{MAX_HTTP_RETRIES})")
                time.sleep(sleep_s)
                continue

            if response.status_code >= 500:
                sleep_s = attempt * 5.0
                print(f"  [SERVER] {response.status_code}; retrying in {sleep_s:.1f}s (attempt {attempt}/{MAX_HTTP_RETRIES})")
                time.sleep(sleep_s)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_HTTP_RETRIES:
                break
            sleep_s = attempt * 5.0
            print(f"  [HTTP ERROR] {exc}; retrying in {sleep_s:.1f}s (attempt {attempt}/{MAX_HTTP_RETRIES})")
            time.sleep(sleep_s)

    if last_error:
        raise last_error
    raise RuntimeError(f"Request failed after {MAX_HTTP_RETRIES} retries (last status={last_status})")


def _iso_date_window(years_back: int) -> str:
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=365 * years_back)
    return f"{start.strftime('%Y%m%d%H%M')} TO {now.strftime('%Y%m%d%H%M')}"


def _build_query(categories: List[str], years_back: int) -> str:
    cat_expr = " OR ".join(f"cat:{cat}" for cat in categories)
    date_expr = _iso_date_window(years_back)
    return f"({cat_expr}) AND submittedDate:[{date_expr}]"


def _extract_arxiv_id(id_url: str) -> str:
    raw = id_url.rsplit("/", 1)[-1]
    return raw.strip()


def _pdf_filename(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_") + ".pdf"


def _fetch_domain_candidates(domain: str, categories: List[str], years_back: int) -> List[ArxivPaper]:
    query = _build_query(categories, years_back)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": MAX_RESULTS_PER_DOMAIN,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urlencode(params)}"

    response = _request_with_retry(url)

    root = ElementTree.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers: List[ArxivPaper] = []
    for entry in root.findall("atom:entry", ns):
        id_text = entry.findtext("atom:id", default="", namespaces=ns)
        title_text = entry.findtext("atom:title", default="", namespaces=ns)
        published_text = entry.findtext("atom:published", default="", namespaces=ns)
        cat_nodes = entry.findall("atom:category", ns)

        arxiv_id = _extract_arxiv_id(id_text)
        if not arxiv_id:
            continue

        cat_terms = [c.attrib.get("term", "") for c in cat_nodes if c.attrib.get("term")]
        primary_cat = cat_terms[0] if cat_terms else (categories[0] if categories else "unknown")
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        papers.append(
            ArxivPaper(
                arxiv_id=arxiv_id,
                title=" ".join(title_text.split()),
                category=primary_cat,
                published_date=published_text,
                pdf_url=pdf_url,
                domain=domain,
            )
        )

    return papers


def _validate_pdf(pdf_path: Path) -> bool:
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return False

    raw_bytes = pdf_path.read_bytes()
    if b"/Root" not in raw_bytes:
        return False

    try:
        doc = fitz.open(pdf_path)
        try:
            if doc.page_count < 1:
                return False
        finally:
            doc.close()
    except Exception:
        return False

    return True


def _download_pdf(paper: ArxivPaper, out_dir: Path) -> Optional[Path]:
    out_path = out_dir / _pdf_filename(paper.arxiv_id)

    if out_path.exists() and _validate_pdf(out_path):
        return out_path

    if out_path.exists():
        out_path.unlink(missing_ok=True)

    response = _request_with_retry(paper.pdf_url)
    out_path.write_bytes(response.content)

    if not _validate_pdf(out_path):
        out_path.unlink(missing_ok=True)
        return None

    return out_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)

    print("[1/5] Fetching arXiv candidates per domain...")
    pool_by_domain: Dict[str, List[ArxivPaper]] = {}
    for domain, cats in DOMAIN_CATEGORY_MAP.items():
        recent = _fetch_domain_candidates(domain, cats, years_back=2)
        if len(recent) < MIN_PER_DOMAIN:
            older = _fetch_domain_candidates(domain, cats, years_back=5)
            by_id = {p.arxiv_id: p for p in recent}
            for p in older:
                by_id.setdefault(p.arxiv_id, p)
            merged = list(by_id.values())
            recent = merged
            print(f"  [WARN] {domain}: <{MIN_PER_DOMAIN} in last 2y, expanded to 5y window")

        if len(recent) < MIN_PER_DOMAIN:
            raise RuntimeError(f"Domain {domain} has only {len(recent)} candidates; need at least {MIN_PER_DOMAIN}")

        rng.shuffle(recent)
        pool_by_domain[domain] = recent
        print(f"  [OK] {domain}: {len(recent)} candidates")
        time.sleep(0.2)

    print("[2/5] Selecting balanced 150-paper candidate plan...")
    pointer_by_domain = {d: 0 for d in DOMAIN_CATEGORY_MAP}
    used_ids = set()
    selected_plan: List[ArxivPaper] = []
    domain_counts = {d: 0 for d in DOMAIN_CATEGORY_MAP}

    # Pass A: satisfy minimum per domain
    for domain in DOMAIN_CATEGORY_MAP:
        while domain_counts[domain] < MIN_PER_DOMAIN:
            pool = pool_by_domain[domain]
            while pointer_by_domain[domain] < len(pool) and pool[pointer_by_domain[domain]].arxiv_id in used_ids:
                pointer_by_domain[domain] += 1
            if pointer_by_domain[domain] >= len(pool):
                raise RuntimeError(f"Exhausted candidates while satisfying minimum quota for {domain}")
            candidate = pool[pointer_by_domain[domain]]
            pointer_by_domain[domain] += 1
            used_ids.add(candidate.arxiv_id)
            selected_plan.append(candidate)
            domain_counts[domain] += 1

    # Pass B: fill to target in deterministic round-robin over shuffled domains
    domain_cycle = list(DOMAIN_CATEGORY_MAP.keys())
    rng.shuffle(domain_cycle)
    cycle_idx = 0
    while len(selected_plan) < TARGET_TOTAL:
        domain = domain_cycle[cycle_idx % len(domain_cycle)]
        cycle_idx += 1

        pool = pool_by_domain[domain]
        while pointer_by_domain[domain] < len(pool) and pool[pointer_by_domain[domain]].arxiv_id in used_ids:
            pointer_by_domain[domain] += 1
        if pointer_by_domain[domain] >= len(pool):
            continue

        candidate = pool[pointer_by_domain[domain]]
        pointer_by_domain[domain] += 1
        used_ids.add(candidate.arxiv_id)
        selected_plan.append(candidate)
        domain_counts[domain] += 1

        if cycle_idx > 50000:
            raise RuntimeError("Could not assemble 150 unique candidates with available pools")

    print(f"  [OK] Planned candidates: {len(selected_plan)}")

    print("[3/5] Downloading + validating PDFs (strict)...")
    valid_papers: List[dict] = []
    accepted_ids = set()

    # We'll keep drawing replacements until exactly 150 valid
    domain_replacement_order = list(DOMAIN_CATEGORY_MAP.keys())
    rep_idx = 0

    def next_replacement() -> ArxivPaper:
        nonlocal rep_idx
        searched = 0
        while searched < len(domain_replacement_order) * 200:
            domain = domain_replacement_order[rep_idx % len(domain_replacement_order)]
            rep_idx += 1
            searched += 1
            pool = pool_by_domain[domain]
            while pointer_by_domain[domain] < len(pool) and pool[pointer_by_domain[domain]].arxiv_id in used_ids:
                pointer_by_domain[domain] += 1
            if pointer_by_domain[domain] < len(pool):
                candidate = pool[pointer_by_domain[domain]]
                pointer_by_domain[domain] += 1
                used_ids.add(candidate.arxiv_id)
                return candidate
        raise RuntimeError("Unable to find replacement candidate while enforcing 150 valid PDFs")

    queue: List[ArxivPaper] = list(selected_plan)
    q_idx = 0
    while len(valid_papers) < TARGET_TOTAL:
        if q_idx < len(queue):
            paper = queue[q_idx]
            q_idx += 1
        else:
            paper = next_replacement()

        try:
            out_path = _download_pdf(paper, DATA_DIR)
            if out_path is None:
                print(f"  [INVALID] {paper.arxiv_id} ({paper.domain}) failed validation; replacing")
                continue

            if paper.arxiv_id in accepted_ids:
                continue

            accepted_ids.add(paper.arxiv_id)
            valid_papers.append(
                {
                    "arxiv_id": paper.arxiv_id,
                    "domain": paper.domain,
                    "title": paper.title,
                    "published_date": paper.published_date,
                    "file_path": str(out_path).replace("\\", "/"),
                }
            )
            if len(valid_papers) % 10 == 0:
                print(f"  [PROGRESS] {len(valid_papers)}/{TARGET_TOTAL} valid PDFs")

        except Exception as exc:
            print(f"  [ERROR] {paper.arxiv_id} download/validation failed: {exc}")
            continue

    print("[4/5] Building metadata index...")
    domain_final_counts: Dict[str, int] = {d: 0 for d in DOMAIN_CATEGORY_MAP}
    for p in valid_papers:
        domain_final_counts[p["domain"]] = domain_final_counts.get(p["domain"], 0) + 1

    for domain, count in domain_final_counts.items():
        if count < MIN_PER_DOMAIN:
            raise RuntimeError(f"Domain quota not met after validation: {domain} has {count} (<{MIN_PER_DOMAIN})")

    metadata = {
        "total_papers": len(valid_papers),
        "domains": domain_final_counts,
        "papers": sorted(valid_papers, key=lambda x: x["arxiv_id"]),
    }

    if metadata["total_papers"] < TARGET_TOTAL:
        raise RuntimeError(f"Corpus build failed: expected {TARGET_TOTAL}, got {metadata['total_papers']}")

    print("[5/5] Writing outputs...")
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("\n[DONE] Brutal 150 corpus built")
    print(f"  Metadata: {METADATA_PATH}")
    print(f"  PDFs dir: {DATA_DIR}")
    print(f"  Total valid PDFs: {metadata['total_papers']}")


if __name__ == "__main__":
    main()

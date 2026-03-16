#!/usr/bin/env python3
"""Batch evaluation pipeline: Download arXiv PDFs and run Phase 0-3.

Downloads 25 diverse arXiv papers, runs each through the full pipeline:
  Phase 0-1: Ingestion → Context → Extraction → Normalization
  Phase 2:   Belief → Contradiction
  Phase 3:   Hypothesis → Critique → Loop

Produces a JSON results file and markdown report in archive/.

Usage:
    python scripts/batch_eval_pipeline.py
"""

import json
import logging
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm.client import OllamaClient
from services.ingestion.pdf_service import PDFIngestionService
from services.context.tool import ContextTool
from services.extraction.tool import ExtractionTool
from services.normalization.tool import NormalizationTool
from services.belief.tool import BeliefTool
from services.contradiction.tool import ContradictionTool

from agents.hypothesis.agent import HypothesisAgent, HypothesisInput
from agents.critic.agent import CriticAgent, CritiqueInput
from agents.loop import HypothesisCritiqueLoop, LoopConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_eval")

# ---------------------------------------------------------------------------
# Paper corpus — 25 diverse arXiv papers across domains
# ---------------------------------------------------------------------------
PAPERS = [
    # CS / ML
    {"arxiv_id": "1706.03762", "title": "Attention Is All You Need", "domain": "CS/ML"},
    {"arxiv_id": "1810.04805", "title": "BERT: Pre-training of Deep Bidirectional Transformers", "domain": "CS/NLP"},
    {"arxiv_id": "2005.14165", "title": "Language Models are Few-Shot Learners (GPT-3)", "domain": "CS/ML"},
    {"arxiv_id": "1512.03385", "title": "Deep Residual Learning for Image Recognition", "domain": "CS/CV"},
    {"arxiv_id": "1406.2661", "title": "Generative Adversarial Networks", "domain": "CS/ML"},
    {"arxiv_id": "2010.11929", "title": "An Image is Worth 16x16 Words (ViT)", "domain": "CS/CV"},
    {"arxiv_id": "2203.15556", "title": "Training Compute-Optimal Large Language Models (Chinchilla)", "domain": "CS/ML"},
    {"arxiv_id": "1301.3781", "title": "Efficient Estimation of Word Representations (Word2Vec)", "domain": "CS/NLP"},
    # Physics
    {"arxiv_id": "1207.7214", "title": "Observation of a new boson (Higgs) at CMS", "domain": "Physics/HEP"},
    {"arxiv_id": "1602.03837", "title": "Observation of Gravitational Waves (LIGO)", "domain": "Physics/GW"},
    {"arxiv_id": "1609.04747", "title": "Neural Message Passing for Quantum Chemistry", "domain": "Physics/QC"},
    # Biology / Medicine
    {"arxiv_id": "2307.08691", "title": "Med-PaLM 2: Towards Expert-Level Medical QA", "domain": "Bio/Med"},
    {"arxiv_id": "2203.02155", "title": "InstructGPT: Training language models to follow instructions", "domain": "CS/RLHF"},
    # Math / Statistics
    {"arxiv_id": "1412.6980", "title": "Adam: A Method for Stochastic Optimization", "domain": "Math/Opt"},
    {"arxiv_id": "1502.03167", "title": "Batch Normalization", "domain": "CS/ML"},
    # Robotics / RL
    {"arxiv_id": "1509.06461", "title": "Continuous control with deep reinforcement learning (DDPG)", "domain": "CS/RL"},
    {"arxiv_id": "1707.06347", "title": "Proximal Policy Optimization Algorithms (PPO)", "domain": "CS/RL"},
    # More diverse ML
    {"arxiv_id": "1706.01427", "title": "Convolutional Sequence to Sequence Learning", "domain": "CS/NLP"},
    {"arxiv_id": "1409.1556", "title": "Very Deep Convolutional Networks (VGGNet)", "domain": "CS/CV"},
    {"arxiv_id": "1505.04597", "title": "U-Net: Convolutional Networks for Biomedical Segmentation", "domain": "Bio/CV"},
    {"arxiv_id": "1803.05457", "title": "Universal Language Model Fine-tuning (ULMFiT)", "domain": "CS/NLP"},
    {"arxiv_id": "2106.09685", "title": "LoRA: Low-Rank Adaptation of Large Language Models", "domain": "CS/ML"},
    {"arxiv_id": "2112.10752", "title": "High-Resolution Image Synthesis with Latent Diffusion", "domain": "CS/CV"},
    {"arxiv_id": "1710.10903", "title": "Graph Attention Networks", "domain": "CS/ML"},
    {"arxiv_id": "2302.13971", "title": "LLaMA: Open and Efficient Foundation Language Models", "domain": "CS/ML"},
]

PDF_DIR = Path("outputs/batch_eval")
RESULTS_PATH = Path("outputs/batch_eval/results.json")


@dataclass
class PaperResult:
    arxiv_id: str
    title: str
    domain: str
    pdf_downloaded: bool = False
    pdf_path: str = ""
    # Phase 0-1
    num_chunks: int = 0
    num_pages: int = 0
    num_contexts: int = 0
    num_claims: int = 0
    num_normalized_claims: int = 0
    # Phase 2
    num_contradictions: int = 0
    num_consensus_groups: int = 0
    # Phase 3
    hypothesis_generated: bool = False
    hypothesis_statement: str = ""
    hypothesis_confidence: float = 0.0
    loop_iterations: int = 0
    loop_stopped_reason: str = ""
    final_confidence: float = 0.0
    # Timing
    ingestion_ms: float = 0.0
    extraction_ms: float = 0.0
    agent_ms: float = 0.0
    total_ms: float = 0.0
    # Errors
    error: str = ""
    phase_reached: str = ""


def download_pdf(arxiv_id: str, dest_dir: Path) -> Optional[Path]:
    """Download a PDF from arXiv. Returns path or None."""
    filename = f"{arxiv_id.replace('.', '_')}.pdf"
    dest = dest_dir / filename

    # Reuse existing download
    if dest.exists() and dest.stat().st_size > 10000:
        logger.info("Reusing cached PDF: %s", dest)
        return dest

    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    logger.info("Downloading %s -> %s", url, dest)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ResearcherAI/1.0 (batch-eval)"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()

        if len(data) < 5000:
            logger.warning("Downloaded file too small (%d bytes), skipping %s", len(data), arxiv_id)
            return None

        dest.write_bytes(data)
        logger.info("Downloaded %s (%d KB)", arxiv_id, len(data) // 1024)
        return dest
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        logger.error("Failed to download %s: %s", arxiv_id, exc)
        return None


def run_pipeline_for_paper(
    paper: Dict[str, str],
    pdf_path: Path,
    ollama_client: OllamaClient,
    hyp_agent: HypothesisAgent,
    critic_agent: CriticAgent,
) -> PaperResult:
    """Run the full Phase 0-3 pipeline for a single paper."""
    result = PaperResult(
        arxiv_id=paper["arxiv_id"],
        title=paper["title"],
        domain=paper["domain"],
        pdf_downloaded=True,
        pdf_path=str(pdf_path),
    )
    total_start = time.time()

    try:
        # Phase 0: Ingestion
        t0 = time.time()
        source_id = f"arxiv_{paper['arxiv_id'].replace('.', '_')}"
        ingestion_svc = PDFIngestionService()
        ing_result = ingestion_svc.ingest_pdf(str(pdf_path), source_id=source_id)
        result.num_chunks = len(ing_result.chunks)
        result.num_pages = int(ing_result.metadata.get("total_pages", 0))
        result.ingestion_ms = (time.time() - t0) * 1000
        result.phase_reached = "ingestion"
        logger.info("[%s] Ingestion: %d chunks, %d pages", paper["arxiv_id"], result.num_chunks, result.num_pages)

        if result.num_chunks == 0:
            result.error = "No chunks extracted from PDF"
            return result

        # Prepare chunk dicts (limit to 80 for perf)
        chunks = [
            {
                "chunk_id": c.chunk_id,
                "source_id": c.source_id,
                "text": c.text,
                "page": c.page,
                "start_char": c.start_char,
                "end_char": c.end_char,
                "text_hash": c.text_hash,
                "context_id": c.context_id,
                "numeric_strings": c.numeric_strings,
                "unit_strings": c.unit_strings,
                "metric_names": c.metric_names,
            }
            for c in ing_result.chunks[:80]
        ]

        # Phase 0: Context extraction
        ctx_result = ContextTool().call({"chunks": chunks})
        result.num_contexts = ctx_result.get("contexts_created", 0)
        result.phase_reached = "context"
        logger.info("[%s] Context: %d contexts", paper["arxiv_id"], result.num_contexts)

        # Phase 1: Claim extraction
        t1 = time.time()
        ext_result = ExtractionTool().call({
            "source_id": source_id,
            "chunks": ctx_result["chunks"],
        })
        claims = ext_result.get("claims", [])
        result.num_claims = len(claims)
        result.phase_reached = "extraction"
        logger.info("[%s] Extraction: %d claims", paper["arxiv_id"], result.num_claims)

        if result.num_claims == 0:
            result.error = "No claims extracted"
            result.extraction_ms = (time.time() - t1) * 1000
            result.total_ms = (time.time() - total_start) * 1000
            return result

        # Phase 1: Normalization
        norm_result = NormalizationTool().call({"claims": claims})
        norm_claims = norm_result.get("normalized_claims", [])
        result.num_normalized_claims = len(norm_claims)
        result.extraction_ms = (time.time() - t1) * 1000
        result.phase_reached = "normalization"
        logger.info("[%s] Normalization: %d normalized claims", paper["arxiv_id"], result.num_normalized_claims)

        # Phase 2: Belief
        belief_result = BeliefTool().call({"normalized_claims": norm_claims})
        result.phase_reached = "belief"

        # Phase 2: Contradiction
        contra_result = ContradictionTool().call({
            "belief_state": {"claims": norm_claims},
        })
        result.num_contradictions = len(contra_result.get("contradictions", []))
        result.num_consensus_groups = len(contra_result.get("consensus_groups", []))
        result.phase_reached = "contradiction"
        logger.info(
            "[%s] Contradiction: %d contradictions, %d consensus",
            paper["arxiv_id"], result.num_contradictions, result.num_consensus_groups,
        )

        # Phase 3: Agent loop
        t3 = time.time()
        hyp_input = HypothesisInput(
            claims=claims[:8],
            contradictions=contra_result.get("contradictions", []),
            consensus_groups=contra_result.get("consensus_groups", []),
            constraints=f"Analyze key findings from: {paper['title']}",
        )

        loop = HypothesisCritiqueLoop(
            hypothesis_agent=hyp_agent,
            critic_agent=critic_agent,
            config=LoopConfig(max_iterations=2, confidence_threshold=0.9),
        )
        loop_result = loop.run(hyp_input)

        if loop_result.final_hypothesis:
            result.hypothesis_generated = True
            result.hypothesis_statement = loop_result.final_hypothesis.statement[:300]
            result.hypothesis_confidence = loop_result.final_hypothesis.confidence_score or 0.0
            result.final_confidence = result.hypothesis_confidence
        result.loop_iterations = loop_result.iterations_completed
        result.loop_stopped_reason = loop_result.stopped_reason
        result.agent_ms = (time.time() - t3) * 1000
        result.phase_reached = "phase3_complete"
        logger.info(
            "[%s] Phase 3: %d iterations, reason=%s, confidence=%.2f",
            paper["arxiv_id"], result.loop_iterations, result.loop_stopped_reason,
            result.final_confidence,
        )

    except Exception as exc:
        result.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        logger.error("[%s] Pipeline failed at %s: %s", paper["arxiv_id"], result.phase_reached, exc)
        traceback.print_exc()

    result.total_ms = (time.time() - total_start) * 1000
    return result


def generate_markdown_report(results: List[PaperResult], run_time_s: float) -> str:
    """Generate a markdown report from pipeline results."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    completed = [r for r in results if r.phase_reached == "phase3_complete"]
    failed = [r for r in results if r.error]
    downloaded = [r for r in results if r.pdf_downloaded]

    # Aggregate stats
    total_chunks = sum(r.num_chunks for r in results)
    total_claims = sum(r.num_claims for r in results)
    total_norm = sum(r.num_normalized_claims for r in results)
    total_contradictions = sum(r.num_contradictions for r in results)
    total_consensus = sum(r.num_consensus_groups for r in results)
    avg_confidence = 0.0
    hyp_generated = [r for r in results if r.hypothesis_generated]
    if hyp_generated:
        avg_confidence = sum(r.final_confidence for r in hyp_generated) / len(hyp_generated)

    lines = [
        f"# Batch Evaluation Report — {now}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Papers attempted | {len(results)} |",
        f"| PDFs downloaded | {len(downloaded)} |",
        f"| Full pipeline completed | {len(completed)} |",
        f"| Errors encountered | {len(failed)} |",
        f"| Total run time | {run_time_s:.1f}s |",
        f"| Total chunks | {total_chunks:,} |",
        f"| Total claims extracted | {total_claims:,} |",
        f"| Total normalized claims | {total_norm:,} |",
        f"| Total contradictions | {total_contradictions:,} |",
        f"| Total consensus groups | {total_consensus:,} |",
        f"| Hypotheses generated | {len(hyp_generated)} |",
        f"| Avg final confidence | {avg_confidence:.3f} |",
        "",
        "## Environment",
        "",
        "- **Model**: qwen2.5:32b (100% GPU)",
        "- **GPU**: NVIDIA RTX 5090, 32GB VRAM",
        "- **Pipeline**: Phase 0 (Ingestion) → Phase 1 (Extraction/Normalization) → Phase 2 (Belief/Contradiction) → Phase 3 (Hypothesis-Critique Loop)",
        "- **Loop config**: max_iterations=2, confidence_threshold=0.9",
        "",
        "## Per-Paper Results",
        "",
        "| # | Paper | Domain | Chunks | Claims | Norm | Contra | Hyp? | Confidence | Loop Stop | Time(s) | Error |",
        "|---|-------|--------|--------|--------|------|--------|------|------------|-----------|---------|-------|",
    ]

    for i, r in enumerate(results, 1):
        hyp_mark = "✅" if r.hypothesis_generated else "❌"
        err = r.error[:40] if r.error else ""
        lines.append(
            f"| {i} | {r.title[:45]} | {r.domain} | {r.num_chunks} | {r.num_claims} | "
            f"{r.num_normalized_claims} | {r.num_contradictions} | {hyp_mark} | "
            f"{r.final_confidence:.2f} | {r.loop_stopped_reason} | {r.total_ms / 1000:.1f} | {err} |"
        )

    lines.extend([
        "",
        "## Phase Timing Breakdown",
        "",
        "| Paper | Ingestion (s) | Extraction (s) | Agent (s) | Total (s) |",
        "|-------|---------------|----------------|-----------|-----------|",
    ])

    for r in results:
        lines.append(
            f"| {r.title[:35]} | {r.ingestion_ms / 1000:.2f} | "
            f"{r.extraction_ms / 1000:.2f} | {r.agent_ms / 1000:.2f} | "
            f"{r.total_ms / 1000:.2f} |"
        )

    # Phase 3 detail
    lines.extend([
        "",
        "## Phase 3 Agent Outputs",
        "",
    ])
    for r in results:
        if r.hypothesis_generated:
            lines.extend([
                f"### {r.title}",
                f"- **Confidence**: {r.final_confidence:.3f}",
                f"- **Iterations**: {r.loop_iterations}",
                f"- **Stop reason**: {r.loop_stopped_reason}",
                f"- **Hypothesis**: {r.hypothesis_statement}",
                "",
            ])

    # Failure analysis
    if failed:
        lines.extend([
            "## Failure Analysis",
            "",
        ])
        for r in failed:
            lines.extend([
                f"- **{r.title}** ({r.arxiv_id}): Phase reached: {r.phase_reached}, Error: {r.error}",
            ])
        lines.append("")

    lines.extend([
        "## Observations",
        "",
        f"- {len(completed)}/{len(results)} papers completed the full Phase 0-3 pipeline.",
        f"- Average claims per paper: {total_claims / max(len(downloaded), 1):.1f}",
        f"- Average normalized claims per paper: {total_norm / max(len(downloaded), 1):.1f}",
        f"- Average contradictions per paper: {total_contradictions / max(len(downloaded), 1):.1f}",
        f"- Average hypothesis confidence: {avg_confidence:.3f}",
        "",
    ])

    return "\n".join(lines)


def main():
    run_start = time.time()
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Check Ollama
    client = OllamaClient()
    if not client.is_available():
        logger.error("Ollama not available — cannot run Phase 3")
        sys.exit(1)
    logger.info("Ollama available, model: %s", os.environ.get("OLLAMA_MODEL", "qwen2.5:32b"))

    # Initialize agents (reuse across papers)
    hyp_agent = HypothesisAgent(client=client)
    critic_agent = CriticAgent(client=client)

    # Check for existing attention paper
    existing_attention = Path("outputs/smoke/attention_is_all_you_need.pdf")

    results: List[PaperResult] = []

    for i, paper in enumerate(PAPERS, 1):
        logger.info("=" * 60)
        logger.info("Paper %d/%d: %s (%s)", i, len(PAPERS), paper["title"], paper["arxiv_id"])
        logger.info("=" * 60)

        # Handle special case: reuse existing Attention PDF
        if paper["arxiv_id"] == "1706.03762" and existing_attention.exists():
            pdf_path = existing_attention
        else:
            pdf_path = download_pdf(paper["arxiv_id"], PDF_DIR)

        if pdf_path is None:
            r = PaperResult(
                arxiv_id=paper["arxiv_id"],
                title=paper["title"],
                domain=paper["domain"],
                error="PDF download failed",
            )
            results.append(r)
            continue

        # Rate limit for arXiv courtesy (3s between downloads)
        if i < len(PAPERS):
            time.sleep(1)

        result = run_pipeline_for_paper(paper, pdf_path, client, hyp_agent, critic_agent)
        results.append(result)

        # Save intermediate results
        RESULTS_PATH.write_text(json.dumps(
            [asdict(r) for r in results],
            indent=2,
            default=str,
        ))
        logger.info("Intermediate results saved (%d/%d papers)", i, len(PAPERS))

    total_time = time.time() - run_start

    # Final JSON
    RESULTS_PATH.write_text(json.dumps(
        [asdict(r) for r in results],
        indent=2,
        default=str,
    ))
    logger.info("Results JSON saved to %s", RESULTS_PATH)

    # Markdown report
    report_md = generate_markdown_report(results, total_time)
    report_path = Path("archive") / f"BATCH_EVAL_{len(results)}_PAPERS_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md)
    logger.info("Report saved to %s", report_path)

    # Print summary
    completed = len([r for r in results if r.phase_reached == "phase3_complete"])
    failed = len([r for r in results if r.error])
    print(f"\n{'=' * 60}")
    print(f"BATCH EVALUATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Papers: {len(results)} | Completed: {completed} | Failed: {failed}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Report: {report_path}")
    print(f"Results JSON: {RESULTS_PATH}")


if __name__ == "__main__":
    main()

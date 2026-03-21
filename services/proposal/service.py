"""Proposal Service — deterministic research artifact generation.

Purpose:
- Convert validated hypotheses + supporting evidence into structured
  research proposals with provenance.
- Produce Markdown-formatted output with canonical sections.
- Assemble citation lists from the evidence chain.

This is a deterministic service: no LLM calls in this implementation.
Section content is assembled from structured inputs (claims, critiques,
hypothesis metadata). A future version may add constrained LLM calls
per section with prompt versioning and token logging.

Inputs/Outputs:
- Input: ProposalRequest
- Output: ProposalResult

Schema References:
- services.proposal.schemas
- core.schemas.proposal (Phase 1 core schema)

Failure Modes:
- Empty hypothesis statement → ValueError
- No supporting claims → warning, generates minimal proposal
- No paper references → warning, references section empty

Testing Strategy:
- Deterministic output for identical inputs
- Schema validation of all outputs
- Edge cases: empty claims, empty critiques, missing references
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from services.proposal.schemas import (
    ProposalRequest,
    ProposalResult,
    ProposalSection,
    SectionDraft,
)


def _deterministic_id(seed: str) -> str:
    """Generate a deterministic proposal ID from seed string."""
    h = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"proposal_{h}"


class ProposalService:
    """Proposal generation from structured inputs.

    Assembles proposal sections from hypothesis, claims, critiques
    and references. Supports optional LLM-backed generation and LaTeX export.
    """

    def __init__(self, llm_client=None) -> None:
        self._llm = llm_client

    def generate(self, request: ProposalRequest) -> ProposalResult:
        """Generate a structured proposal from validated hypothesis and evidence.

        Args:
            request: ProposalRequest with hypothesis, claims, critiques, references

        Returns:
            ProposalResult with ordered sections and assembled Markdown

        Raises:
            ValueError: If hypothesis_id or statement is empty
        """
        if not request.hypothesis_id:
            raise ValueError("hypothesis_id is required")
        if not request.statement:
            raise ValueError("statement is required")

        warnings: List[str] = []

        if not request.supporting_claims:
            warnings.append("no supporting claims provided; proposal will be minimal")
        if not request.paper_references:
            warnings.append("no paper references provided; references section will be empty")

        proposal_id = _deterministic_id(
            f"{request.hypothesis_id}:{request.statement}"
        )

        sections = [
            self._build_novelty(request),
            self._build_motivation(request),
            self._build_methodology(request),
            self._build_expected_outcomes(request),
            self._build_references(request),
        ]

        # LLM-backed generation (if requested and available)
        if request.use_llm and self._llm is not None:
            sections = self._build_sections_with_llm(request, sections)

        full_markdown = self._assemble_markdown(proposal_id, request, sections)
        references = self._collect_references(request)

        # LaTeX export
        latex_output = None
        if request.export_format == "latex":
            from services.proposal.latex_renderer import render_proposal
            latex_output = render_proposal(
                title=request.statement[:120],
                sections=[{"heading": s.heading, "content": s.content} for s in sections],
                references=references,
                evidence_tables=request.evidence_tables or [],
            )

        return ProposalResult(
            proposal_id=proposal_id,
            hypothesis_id=request.hypothesis_id,
            sections=sections,
            full_markdown=full_markdown,
            references=references,
            warnings=warnings,
            latex_output=latex_output,
            evidence_tables=request.evidence_tables or [],
        )

    def _build_sections_with_llm(self, request: ProposalRequest, fallback_sections: list) -> list:
        """Attempt LLM-backed section generation; fall back to deterministic on failure."""
        from services.proposal.llm_sections import LLMSectionGenerator
        gen = LLMSectionGenerator(self._llm)

        try:
            novelty_content = gen.generate_novelty(
                request.statement,
                request.supporting_claims,
                request.critiques,
            )
            fallback_sections[0] = SectionDraft(
                section=fallback_sections[0].section,
                heading=fallback_sections[0].heading,
                content=novelty_content,
                citations_used=fallback_sections[0].citations_used,
            )
        except Exception:
            pass

        try:
            method_content = gen.generate_methodology(
                request.statement,
                request.assumptions,
                {"independent": [], "dependent": []},
                request.evidence_tables,
            )
            fallback_sections[2] = SectionDraft(
                section=fallback_sections[2].section,
                heading=fallback_sections[2].heading,
                content=method_content,
                citations_used=fallback_sections[2].citations_used,
            )
        except Exception:
            pass

        return fallback_sections

    def _build_novelty(self, req: ProposalRequest) -> SectionDraft:
        """Build the novelty statement section."""
        lines = [f"**Hypothesis:** {req.statement}"]
        if req.rationale:
            lines.append(f"\n{req.rationale}")

        # Identify gaps from critiques
        if req.critiques:
            gaps = []
            for critique in req.critiques:
                for wa in critique.get("weak_assumptions", []):
                    gaps.append(f"- {wa}")
            if gaps:
                lines.append("\n**Identified gaps addressed:**")
                lines.extend(gaps)

        citations = self._extract_claim_paper_ids(req.supporting_claims)

        return SectionDraft(
            section=ProposalSection.NOVELTY,
            heading="Novelty Statement",
            content="\n".join(lines),
            citations_used=citations,
        )

    def _build_motivation(self, req: ProposalRequest) -> SectionDraft:
        """Build the motivation section from supporting evidence."""
        lines = []

        if req.supporting_claims:
            lines.append("This proposal is motivated by the following empirical evidence:")
            lines.append("")
            for claim in req.supporting_claims:
                subject = claim.get("subject", "")
                predicate = claim.get("predicate", "")
                obj = claim.get("object_raw", "")
                metric = claim.get("metric_canonical", "")
                ctx = claim.get("context_id", "")
                claim_line = f"- {subject} {predicate} {obj}"
                if metric:
                    claim_line += f" (metric: {metric})"
                if ctx and ctx != "ctx_unknown":
                    claim_line += f" [context: {ctx}]"
                lines.append(claim_line)
        else:
            lines.append("Motivation grounded in the stated hypothesis.")

        if req.assumptions:
            lines.append("\n**Key assumptions:**")
            for assumption in req.assumptions:
                lines.append(f"- {assumption}")

        citations = self._extract_claim_paper_ids(req.supporting_claims)

        return SectionDraft(
            section=ProposalSection.MOTIVATION,
            heading="Motivation",
            content="\n".join(lines),
            citations_used=citations,
        )

    def _build_methodology(self, req: ProposalRequest) -> SectionDraft:
        """Build methodology outline from hypothesis and critique revisions."""
        lines = ["**Proposed approach:**", ""]
        lines.append(f"1. Validate the hypothesis: *{req.statement}*")

        # Incorporate suggested revisions from critiques
        step = 2
        if req.critiques:
            for critique in req.critiques:
                for revision in critique.get("suggested_revisions", []):
                    lines.append(f"{step}. {revision}")
                    step += 1

        if req.known_risks:
            lines.append(f"\n**Risk mitigation:**")
            for risk in req.known_risks:
                lines.append(f"- {risk}")

        # Extract metrics to evaluate from claims
        metrics = set()
        for claim in req.supporting_claims:
            m = claim.get("metric_canonical", "")
            if m:
                metrics.add(m)
        if metrics:
            lines.append(f"\n**Evaluation metrics:** {', '.join(sorted(metrics))}")

        return SectionDraft(
            section=ProposalSection.METHODOLOGY,
            heading="Methodology Outline",
            content="\n".join(lines),
            citations_used=[],
        )

    def _build_expected_outcomes(self, req: ProposalRequest) -> SectionDraft:
        """Build expected outcomes section."""
        lines = ["Based on the supporting evidence, we expect:"]
        lines.append("")

        if req.supporting_claims:
            for claim in req.supporting_claims:
                subject = claim.get("subject", "")
                metric = claim.get("metric_canonical", "")
                obj = claim.get("object_raw", "")
                if metric and obj:
                    lines.append(f"- {subject}: {metric} consistent with {obj}")
                elif subject:
                    lines.append(f"- Confirmation of {subject} behavior")
        else:
            lines.append("- Empirical validation of the stated hypothesis")

        if req.known_risks:
            lines.append("\n**Potential failure modes:**")
            for risk in req.known_risks:
                lines.append(f"- {risk}")

        return SectionDraft(
            section=ProposalSection.EXPECTED_OUTCOMES,
            heading="Expected Outcomes",
            content="\n".join(lines),
            citations_used=[],
        )

    def _build_references(self, req: ProposalRequest) -> SectionDraft:
        """Build references section from paper references."""
        lines = []

        if req.paper_references:
            for i, ref in enumerate(req.paper_references, 1):
                title = ref.get("title", "Untitled")
                authors = ref.get("authors", [])
                doi = ref.get("doi", "")
                paper_id = ref.get("paper_id", "")

                author_str = ", ".join(authors) if authors else "Unknown"
                line = f"[{i}] {author_str}. *{title}*."
                if doi:
                    line += f" DOI: {doi}"
                if paper_id:
                    line += f" ({paper_id})"
                lines.append(line)
        else:
            lines.append("*No references provided.*")

        return SectionDraft(
            section=ProposalSection.REFERENCES,
            heading="References",
            content="\n".join(lines),
            citations_used=[r.get("paper_id", "") for r in req.paper_references if r.get("paper_id")],
        )

    def _assemble_markdown(
        self,
        proposal_id: str,
        req: ProposalRequest,
        sections: List[SectionDraft],
    ) -> str:
        """Assemble all sections into a single Markdown document."""
        lines = [
            f"# Research Proposal",
            f"",
            f"**Proposal ID:** {proposal_id}",
            f"**Hypothesis ID:** {req.hypothesis_id}",
            f"",
            f"---",
            f"",
        ]

        for section in sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        return "\n".join(lines)

    def _collect_references(self, req: ProposalRequest) -> List[Dict]:
        """Collect deduplicated reference list."""
        seen = set()
        refs = []
        for ref in req.paper_references:
            pid = ref.get("paper_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                refs.append(ref)
            elif not pid:
                refs.append(ref)
        return refs

    def _extract_claim_paper_ids(self, claims: List[Dict]) -> List[str]:
        """Extract unique paper_ids from claims."""
        seen = set()
        result = []
        for claim in claims:
            pid = claim.get("paper_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                result.append(pid)
        return result

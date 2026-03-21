"""Consolidation service — merges all analysis outputs into a structured summary.

Takes hypothesis-critique loop result, belief states, literature clusters,
and contradiction data, and produces a coherent analysis summary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.consolidation.schemas import ConsolidationRequest, ConsolidationResult


class ConsolidationService:
    """Consolidates multi-phase analysis into a structured summary."""

    def consolidate(self, request: ConsolidationRequest) -> ConsolidationResult:
        key_findings = []
        evidence_gaps = []

        # Extract hypothesis findings
        hypothesis_status = "none"
        confidence_assessment = "No analysis available"

        if request.hypothesis:
            hyp = request.hypothesis
            statement = hyp.get("statement", "No hypothesis")
            confidence = hyp.get("qualitative_confidence", "unknown")
            hypothesis_status = f"validated (confidence: {confidence})"
            key_findings.append(f"Hypothesis: {statement}")

            # Risks as evidence gaps
            for risk in hyp.get("known_risks", []):
                evidence_gaps.append(f"Risk: {risk}")

            confidence_assessment = (
                f"Hypothesis confidence: {confidence}. "
                f"Based on {len(request.claims)} claims, "
                f"{len(request.contradictions)} contradictions, "
                f"{len(request.clusters)} literature clusters."
            )

        # Extract belief findings
        for belief in request.beliefs:
            if isinstance(belief, dict):
                metric = belief.get("metric_canonical", belief.get("metric", ""))
                status = belief.get("status", "")
                if metric and status:
                    key_findings.append(f"Belief: {metric} is {status}")

        # Extract cluster findings
        for cluster in request.clusters:
            if isinstance(cluster, dict):
                label = cluster.get("label", "")
                count = cluster.get("paper_count", 0)
                if label:
                    key_findings.append(f"Literature cluster: {label} ({count} papers)")

        # Extract contradiction findings
        for contradiction in request.contradictions:
            if isinstance(contradiction, dict):
                claim_a = contradiction.get("claim_a", "")
                claim_b = contradiction.get("claim_b", "")
                if claim_a and claim_b:
                    evidence_gaps.append(f"Contradiction between {claim_a} and {claim_b}")

        # Build summary
        summary_parts = []
        if request.hypothesis:
            summary_parts.append(
                f"Analysis of {len(request.claims)} claims across "
                f"{len(request.clusters)} literature clusters."
            )
        if key_findings:
            summary_parts.append(f"Found {len(key_findings)} key findings.")
        if evidence_gaps:
            summary_parts.append(f"Identified {len(evidence_gaps)} evidence gaps or contradictions.")

        summary = " ".join(summary_parts) if summary_parts else "No analysis data available."

        return ConsolidationResult(
            summary=summary,
            key_findings=key_findings,
            evidence_gaps=evidence_gaps,
            confidence_assessment=confidence_assessment,
            hypothesis_status=hypothesis_status,
            cluster_count=len(request.clusters),
            claim_count=len(request.claims),
            contradiction_count=len(request.contradictions),
        )

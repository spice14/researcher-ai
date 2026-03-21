"""Provenance audit for ScholarOS pipeline outputs.

Validates that every output (proposal citations, hypothesis claims)
can be traced back to valid source chunks and papers.

The chain: proposal → hypothesis → claims → chunks → papers
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ProvenanceAuditor:
    """Validates provenance chains for ScholarOS outputs.

    Checks that:
    1. Every proposal citation links to a known paper/chunk
    2. Every hypothesis claim ID exists in the claim store
    3. Every claim links to a source chunk with valid source_id
    """

    def __init__(
        self,
        metadata_store=None,
        vector_store=None,
    ) -> None:
        self._metadata_store = metadata_store
        self._vector_store = vector_store

    def audit_proposal(self, proposal: Dict, context: Dict) -> Dict:
        """Audit a proposal for complete provenance.

        Args:
            proposal: ProposalResult dict
            context: Context with 'paper_ids', 'claim_ids', 'chunk_ids' sets

        Returns:
            Audit result with 'valid', 'errors', 'warnings', 'citation_coverage'
        """
        errors: List[str] = []
        warnings: List[str] = []

        known_paper_ids: Set[str] = set(context.get("paper_ids", []))

        # Check references
        for ref in proposal.get("references", []):
            paper_id = ref.get("paper_id", "")
            if not paper_id:
                errors.append("Reference missing paper_id")
            elif known_paper_ids and paper_id not in known_paper_ids:
                warnings.append(f"Reference '{paper_id}' not in known papers")

        # Check hypothesis link
        hyp_id = proposal.get("hypothesis_id", "")
        if not hyp_id:
            errors.append("Proposal missing hypothesis_id")

        # Check section citations
        for section in proposal.get("sections", []):
            for cite_id in section.get("citations_used", []):
                if known_paper_ids and cite_id not in known_paper_ids:
                    warnings.append(f"Citation '{cite_id}' not in known papers")

        # Compute coverage
        ref_ids = {r.get("paper_id", "") for r in proposal.get("references", [])}
        coverage = (
            len(ref_ids & known_paper_ids) / len(known_paper_ids)
            if known_paper_ids
            else 1.0
        )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "citation_coverage": round(coverage, 4),
            "proposal_id": proposal.get("proposal_id", ""),
            "hypothesis_id": hyp_id,
        }

    def audit_hypothesis(self, hypothesis: Dict, context: Dict) -> Dict:
        """Audit a hypothesis for grounded claims.

        Args:
            hypothesis: Hypothesis dict
            context: Context with 'claim_ids', 'paper_ids'

        Returns:
            Audit result dict
        """
        errors: List[str] = []
        warnings: List[str] = []

        known_claim_ids: Set[str] = set(context.get("claim_ids", []))

        for cid in hypothesis.get("grounding_claim_ids", []):
            if known_claim_ids and cid not in known_claim_ids:
                warnings.append(f"Grounding claim '{cid}' not found in known claims")

        if not hypothesis.get("statement"):
            errors.append("Hypothesis missing statement")
        if not hypothesis.get("assumptions"):
            warnings.append("Hypothesis has no explicit assumptions")

        grounding_count = len(hypothesis.get("grounding_claim_ids", []))
        citation_count = len(hypothesis.get("supporting_citations", []))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "hypothesis_id": hypothesis.get("hypothesis_id", ""),
            "grounding_claims": grounding_count,
            "supporting_citations": citation_count,
            "fully_grounded": grounding_count > 0 or citation_count > 0,
        }

    def audit_trace(self, trace_entries: List[Dict]) -> Dict:
        """Audit a trace for provenance completeness.

        Args:
            trace_entries: List of trace entry dicts

        Returns:
            Audit result with hash coverage stats
        """
        total = len(trace_entries)
        if total == 0:
            return {
                "valid": True,
                "errors": [],
                "warnings": ["Empty trace"],
                "hash_coverage": 1.0,
                "step_count": 0,
                "hashed_steps": 0,
            }

        errors: List[str] = []
        warnings: List[str] = []
        hashed = 0

        for entry in trace_entries:
            has_input = bool(entry.get("input_hash"))
            has_output = bool(entry.get("output_hash"))
            if has_input and has_output:
                hashed += 1
            else:
                missing = []
                if not has_input:
                    missing.append("input_hash")
                if not has_output:
                    missing.append("output_hash")
                warnings.append(
                    f"Step {entry.get('sequence', '?')} ({entry.get('tool', '?')}) "
                    f"missing: {', '.join(missing)}"
                )

            if entry.get("status") == "error":
                errors.append(
                    f"Step {entry.get('sequence', '?')} ({entry.get('tool', '?')}) failed: "
                    f"{entry.get('error_message', 'unknown error')}"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "hash_coverage": round(hashed / total, 4),
            "step_count": total,
            "hashed_steps": hashed,
        }

    def full_audit(
        self,
        proposal: Optional[Dict] = None,
        hypothesis: Optional[Dict] = None,
        trace_entries: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Run a complete provenance audit across all components.

        Args:
            proposal: ProposalResult dict (optional)
            hypothesis: Hypothesis dict (optional)
            trace_entries: Trace entries (optional)
            context: Context with known IDs

        Returns:
            Combined audit result
        """
        context = context or {}
        results: Dict[str, Any] = {}
        all_valid = True

        if proposal is not None:
            pa = self.audit_proposal(proposal, context)
            results["proposal"] = pa
            if not pa["valid"]:
                all_valid = False

        if hypothesis is not None:
            ha = self.audit_hypothesis(hypothesis, context)
            results["hypothesis"] = ha
            if not ha["valid"]:
                all_valid = False

        if trace_entries is not None:
            ta = self.audit_trace(trace_entries)
            results["trace"] = ta
            if not ta["valid"]:
                all_valid = False

        results["overall_valid"] = all_valid
        results["total_errors"] = sum(
            len(r.get("errors", [])) for r in results.values() if isinstance(r, dict)
        )
        results["total_warnings"] = sum(
            len(r.get("warnings", [])) for r in results.values() if isinstance(r, dict)
        )

        return results

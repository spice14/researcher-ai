"""Provenance browser for ScholarOS CLI.

Traces backward from outputs (proposals, hypotheses) through claims,
chunks, and papers to provide full provenance chains.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ProvenanceInspector:
    """Browse and trace provenance chains in ScholarOS outputs.

    Traces: proposal → hypothesis → claims → chunks → papers.
    """

    def __init__(
        self,
        metadata_store=None,
        trace_store=None,
    ) -> None:
        self._metadata_store = metadata_store
        self._trace_store = trace_store

    def trace_session(self, session_id: str) -> List[Dict]:
        """Return the full trace for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of trace entries with tool, input_hash, output_hash, duration_ms
        """
        if self._trace_store is None:
            return []

        try:
            trace = self._trace_store.load(session_id)
            if trace is None:
                return []
            return [
                {
                    "sequence": e.sequence,
                    "tool": e.tool,
                    "phase": e.phase,
                    "status": e.status,
                    "input_hash": e.input_hash,
                    "output_hash": e.output_hash,
                    "duration_ms": e.duration_ms,
                    "error_message": e.error_message,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in trace.entries
            ]
        except Exception:
            return []

    def trace_proposal(self, proposal: Dict) -> Dict:
        """Trace a proposal back to its source evidence chain.

        Args:
            proposal: ProposalResult dict

        Returns:
            Provenance chain: {proposal_id, hypothesis_id, claim_ids, paper_ids, chunk_ids}
        """
        chain: Dict[str, Any] = {
            "proposal_id": proposal.get("proposal_id"),
            "hypothesis_id": proposal.get("hypothesis_id"),
            "sections": len(proposal.get("sections", [])),
            "evidence_tables": len(proposal.get("evidence_tables", [])),
            "references": [r.get("paper_id") for r in proposal.get("references", [])],
        }
        return chain

    def trace_hypothesis(self, hypothesis: Dict) -> Dict:
        """Trace a hypothesis to its supporting claims.

        Args:
            hypothesis: Hypothesis dict

        Returns:
            Provenance chain: {hypothesis_id, claims, paper_ids}
        """
        chain: Dict[str, Any] = {
            "hypothesis_id": hypothesis.get("hypothesis_id"),
            "statement": hypothesis.get("statement", "")[:100],
            "confidence_score": hypothesis.get("confidence_score"),
            "grounding_claim_ids": hypothesis.get("grounding_claim_ids", []),
            "supporting_citations": hypothesis.get("supporting_citations", []),
            "iteration_number": hypothesis.get("iteration_number", 1),
        }
        return chain

    def get_paper_claims(self, paper_id: str) -> List[Dict]:
        """Get all claims extracted from a paper.

        Args:
            paper_id: Paper identifier

        Returns:
            List of ClaimRecord dicts
        """
        if self._metadata_store is None:
            return []

        try:
            claims = self._metadata_store.get_claims(paper_id)
            return [
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "subject": c.subject,
                    "predicate": c.predicate,
                    "object_value": c.object_value,
                    "confidence_level": c.confidence_level,
                }
                for c in claims
            ]
        except Exception:
            return []

    def list_sessions(self) -> List[Dict]:
        """List recent sessions from the trace store.

        Returns:
            List of session summary dicts
        """
        if self._trace_store is None:
            return []

        try:
            import os
            import json
            trace_dir = getattr(self._trace_store, "_base_dir", "outputs/traces")
            sessions = []
            if os.path.isdir(trace_dir):
                for fname in sorted(os.listdir(trace_dir))[-20:]:
                    if fname.endswith(".json"):
                        fpath = os.path.join(trace_dir, fname)
                        try:
                            with open(fpath) as f:
                                data = json.load(f)
                            sessions.append({
                                "session_id": data.get("session_id"),
                                "started_at": data.get("started_at"),
                                "step_count": len(data.get("entries", [])),
                                "final_output_hash": data.get("final_output_hash"),
                            })
                        except Exception:
                            pass
            return sessions
        except Exception:
            return []

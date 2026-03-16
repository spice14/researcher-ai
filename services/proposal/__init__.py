"""Proposal service — research artifact generation from validated hypotheses."""

from services.proposal.service import ProposalService
from services.proposal.tool import ProposalTool
from services.proposal.schemas import (
    ProposalRequest,
    ProposalResult,
    ProposalSection,
    SectionDraft,
)

__all__ = [
    "ProposalService",
    "ProposalTool",
    "ProposalRequest",
    "ProposalResult",
    "ProposalSection",
    "SectionDraft",
]

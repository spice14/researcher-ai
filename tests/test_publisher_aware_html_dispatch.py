"""Unit tests for publisher-aware HTML strategy dispatch."""

from __future__ import annotations

from researcher_ai.ingestion.html_extractor import (
    ACLHTMLExtractor,
    ArxivHTMLExtractor,
    GenericHTMLExtractor,
    HTMLExtractor,
    NatureHTMLExtractor,
    PMCHTMLExtractor,
    PMLRHTMLExtractor,
    ScienceHTMLExtractor,
    SpringerHTMLExtractor,
)
from researcher_ai.ingestion.source_resolver import IdentifierType, ResolvedSource


def _resolved(id_type: IdentifierType, html_url: str) -> ResolvedSource:
    return ResolvedSource(
        identifier="test-id",
        identifier_type=id_type,
        html_url=html_url,
    )


def test_dispatch_arxiv_domain_uses_arxiv_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://arxiv.org/html/1706.03762"))
    assert isinstance(strategy, ArxivHTMLExtractor)


def test_dispatch_pmc_domain_uses_pmc_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"))
    assert isinstance(strategy, PMCHTMLExtractor)


def test_dispatch_acl_domain_uses_acl_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://aclanthology.org/2023.acl-long.1/"))
    assert isinstance(strategy, ACLHTMLExtractor)


def test_dispatch_pmlr_domain_uses_pmlr_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://proceedings.mlr.press/v139/radford21a.html"))
    assert isinstance(strategy, PMLRHTMLExtractor)


def test_dispatch_nature_domain_uses_nature_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://www.nature.com/articles/s41586-023-00000-0"))
    assert isinstance(strategy, NatureHTMLExtractor)


def test_dispatch_springer_domain_uses_springer_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://link.springer.com/article/10.1007/s00134-024-12345-6"))
    assert isinstance(strategy, SpringerHTMLExtractor)


def test_dispatch_science_domain_uses_science_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://www.science.org/doi/10.1126/science.abc1234"))
    assert isinstance(strategy, ScienceHTMLExtractor)


def test_dispatch_unknown_domain_uses_generic_strategy():
    extractor = HTMLExtractor()
    strategy = extractor._get_strategy(_resolved(IdentifierType.URL, "https://example.org/paper"))
    assert isinstance(strategy, GenericHTMLExtractor)

"""Structured Source-First Paper Ingestion POC.

Ingestion hierarchy:
  1. Structured HTML source (arXiv / PMC / ACL Anthology)
  2. Scholarly metadata APIs (OpenAlex / Crossref / Semantic Scholar)
  3. PDF download + extraction (PyMuPDF / Docling)

All pipelines normalize output to ResearchDocument.
"""

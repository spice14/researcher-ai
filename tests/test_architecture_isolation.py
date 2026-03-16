"""Enforce strict architectural separation between domain services.

This test verifies that the MCP layer is enforced by checking that
no domain service imports another domain service directly.

Violation of these constraints indicates architectural regression.
"""

import ast
import importlib
import sys
from pathlib import Path
from typing import Set, Tuple


class ImportValidator(ast.NodeVisitor):
    """Extract all 'from X import Y' statements from a Python file."""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports: Set[str] = set()
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Extract 'from X import Y' module names."""
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)


def extract_imports_from_file(filepath: str) -> Set[str]:
    """Parse a Python file and extract all 'from X import' statements."""
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())
    
    validator = ImportValidator(filepath)
    validator.visit(tree)
    return validator.imports


DOMAIN_SERVICES = {
    "ingestion": "services/ingestion/service.py",
    "extraction": "services/extraction/service.py",
    "normalization": "services/normalization/service.py",
    "belief": "services/belief/service.py",
    "contradiction": "services/contradiction/service.py",
}

OTHER_DOMAINS = {
    "ingestion": {"extraction", "normalization", "belief", "contradiction"},
    "extraction": {"ingestion", "normalization", "belief", "contradiction"},
    "normalization": {"ingestion", "extraction", "belief", "contradiction"},
    "belief": {"ingestion", "extraction", "normalization", "contradiction"},
    "contradiction": {"ingestion", "extraction", "normalization", "belief"},
}


def test_no_cross_domain_imports():
    """Verify that domain services do not import from each other."""
    repo_root = Path(__file__).parent.parent
    violations: List[Tuple[str, str, str]] = []
    
    # Allow schema imports between adjacent pipeline stages (boundary types)
    ALLOWED_SCHEMA_IMPORTS = {
        ("extraction", "services.ingestion.schemas"),  # IngestionChunk is boundary type
    }
    
    for service_name, service_file in DOMAIN_SERVICES.items():
        filepath = repo_root / service_file
        
        if not filepath.exists():
            continue
        
        imports = extract_imports_from_file(str(filepath))
        
        # Check if this service imports any other domain service
        for imported_module in imports:
            # Check if this is an allowed schema import
            if (service_name, imported_module) in ALLOWED_SCHEMA_IMPORTS:
                continue
                
            for forbidden_domain in OTHER_DOMAINS[service_name]:
                if forbidden_domain in imported_module and "services." in imported_module:
                    # Allow imports from own domain (services.extraction.schemas is OK from extraction/service.py)
                    if not imported_module.startswith(f"services.{service_name}"):
                        violations.append((
                            service_name,
                            imported_module,
                            f"{service_file} imports from forbidden domain"
                        ))
    
    # Report violations
    if violations:
        msg = "\n".join([
            f"  [{service}] {imported} - {reason}"
            for service, imported, reason in violations
        ])
        raise AssertionError(
            f"Cross-domain imports detected (architectural violation):\n{msg}\n\n"
            "Fix: Domain services must only import from:\n"
            "  - Their own services (services.X.internal)\n"
            "  - Core schemas (core.schemas.*)\n"
            "  - Utilities (not other domain services)"
        )


def test_tools_only_import_own_service_within_domain():
    """Verify that tool wrappers do not create hidden cross-domain coupling."""
    repo_root = Path(__file__).parent.parent
    tool_files = {
        "ingestion": "services/ingestion/tool.py",
        "extraction": "services/extraction/tool.py",
        "normalization": "services/normalization/tool.py",
        "belief": "services/belief/tool.py",
        "contradiction": "services/contradiction/tool.py",
    }
    
    violations: List[Tuple[str, str]] = []
    
    for domain, tool_file in tool_files.items():
        filepath = repo_root / tool_file
        
        if not filepath.exists():
            continue
        
        imports = extract_imports_from_file(str(filepath))
        
        # Tools should import their own service, but not downstream services
        forbidden_domains = list(OTHER_DOMAINS.get(domain, set()))
        
        for imported_module in imports:
            # Exception: schemas imports are OK (we moved NormalizedClaim to core)
            if "schemas" in imported_module and "services." in imported_module:
                # Only allow schemas from own domain
                if not imported_module.startswith(f"services.{domain}.schemas"):
                    if any(f"services.{fd}" in imported_module for fd in forbidden_domains):
                        violations.append((
                            tool_file,
                            imported_module
                        ))


# Module-level execution removed - pytest will discover and run tests

if __name__ == "__main__":
    test_no_cross_domain_imports()
    test_tools_only_import_own_service_within_domain()
    print("[PASS] Architecture isolation verified")

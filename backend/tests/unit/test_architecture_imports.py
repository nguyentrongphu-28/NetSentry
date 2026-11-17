from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_MODULES = {
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "netmiko",
    "paramiko",
    "ollama",
    "requests",
}

APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"
DOMAIN_DIR = APP_DIR / "domain"
RULES_DIR = APP_DIR / "rules"


def _extract_imported_modules(file_path: Path) -> list[str]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                modules.append(root_pkg)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                modules.append(root_pkg)

    return modules


def test_domain_and_rules_no_forbidden_imports():
    """Verify clean architecture boundaries: no forbidden infrastructure libraries in domain or rules."""
    target_files = list(DOMAIN_DIR.rglob("*.py")) + list(RULES_DIR.rglob("*.py"))
    assert len(target_files) > 0, "No python files found in domain or rules!"

    violations: list[str] = []

    for py_file in target_files:
        imported = _extract_imported_modules(py_file)
        for mod in imported:
            if mod in FORBIDDEN_MODULES:
                violations.append(f"{py_file.relative_to(APP_DIR)} imports forbidden module '{mod}'")

    assert not violations, f"Architectural import violations found:\n" + "\n".join(violations)


def test_domain_only_standard_library():
    """Verify app/domain only imports from Python standard library."""
    domain_files = list(DOMAIN_DIR.rglob("*.py"))
    assert len(domain_files) > 0

    allowed_domain_roots = {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "app",  # internal domain imports
    }

    violations: list[str] = []
    for py_file in domain_files:
        imported = _extract_imported_modules(py_file)
        for mod in imported:
            if mod not in allowed_domain_roots:
                violations.append(f"{py_file.name} imports non-standard/forbidden root: '{mod}'")

    assert not violations, f"Domain standard-library violations found:\n" + "\n".join(violations)

"""Architecture tests enforcing clean architecture boundaries and import restrictions."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_FRAMEWORK_MODULES = {
    "fastapi",
    "pydantic",
    "starlette",
    "uvicorn",
}

FORBIDDEN_IN_CORE_MODULES = {
    "fastapi",
    "pydantic",
    "starlette",
    "uvicorn",
    "sqlalchemy",
    "netmiko",
    "paramiko",
    "ollama",
    "requests",
}

APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"
DOMAIN_DIR = APP_DIR / "domain"
RULES_DIR = APP_DIR / "rules"
SERVICES_DIR = APP_DIR / "services"
FACTORIES_DIR = APP_DIR / "factories"
CONNECTORS_DIR = APP_DIR / "connectors"
REPOSITORIES_DIR = APP_DIR / "repositories"
CORE_DIR = APP_DIR / "core"
API_DIR = APP_DIR / "api"


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


def _extract_full_imported_paths(file_path: Path) -> list[str]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    paths: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                paths.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                paths.append(node.module)

    return paths


def test_core_layers_no_forbidden_imports():
    """Verify that domain, rules, services, factories, connectors, repositories, and core do not import forbidden modules."""
    target_files = (
        list(DOMAIN_DIR.rglob("*.py"))
        + list(RULES_DIR.rglob("*.py"))
        + list(SERVICES_DIR.rglob("*.py"))
        + list(FACTORIES_DIR.rglob("*.py"))
        + list(CONNECTORS_DIR.rglob("*.py"))
        + list(REPOSITORIES_DIR.rglob("*.py"))
        + list(CORE_DIR.rglob("*.py"))
    )
    assert len(target_files) > 0, "No python files found in target architecture directories!"

    violations: list[str] = []

    for py_file in target_files:
        imported = _extract_imported_modules(py_file)
        # connectors may import netmiko/paramiko
        is_connector = CONNECTORS_DIR in py_file.parents or py_file.parent == CONNECTORS_DIR
        for mod in imported:
            if mod in FORBIDDEN_FRAMEWORK_MODULES:
                violations.append(f"{py_file.relative_to(APP_DIR)} imports forbidden framework module '{mod}'")
            elif mod in FORBIDDEN_IN_CORE_MODULES and not is_connector:
                violations.append(f"{py_file.relative_to(APP_DIR)} imports forbidden library '{mod}'")

    assert not violations, "Architectural import violations found:\n" + "\n".join(violations)


def test_netmiko_and_paramiko_only_in_connectors():
    """Verify that netmiko and paramiko are strictly isolated to app/connectors/."""
    all_app_files = list(APP_DIR.rglob("*.py"))
    assert len(all_app_files) > 0

    violations: list[str] = []

    for py_file in all_app_files:
        is_connector = CONNECTORS_DIR in py_file.parents or py_file.parent == CONNECTORS_DIR
        imported = _extract_imported_modules(py_file)
        for mod in imported:
            if mod in {"netmiko", "paramiko"} and not is_connector:
                violations.append(
                    f"{py_file.relative_to(APP_DIR)} imports '{mod}' outside app/connectors/"
                )

    assert not violations, "Network library boundary violations found:\n" + "\n".join(violations)


def test_sqlite3_only_in_repositories():
    """Verify that sqlite3 is strictly isolated to app/repositories/."""
    all_app_files = list(APP_DIR.rglob("*.py"))
    assert len(all_app_files) > 0

    violations: list[str] = []

    for py_file in all_app_files:
        is_repo = REPOSITORIES_DIR in py_file.parents or py_file.parent == REPOSITORIES_DIR
        imported = _extract_imported_modules(py_file)
        for mod in imported:
            if mod == "sqlite3" and not is_repo:
                violations.append(
                    f"{py_file.relative_to(APP_DIR)} imports 'sqlite3' outside app/repositories/"
                )

    assert not violations, "SQLite boundary violations found:\n" + "\n".join(violations)


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

    assert not violations, "Domain standard-library violations found:\n" + "\n".join(violations)


def test_api_layer_does_not_call_repositories_directly():
    """Verify app/api only calls app/services, never app/repositories directly."""
    api_files = list(API_DIR.rglob("*.py"))
    assert len(api_files) > 0

    violations: list[str] = []
    for py_file in api_files:
        imported_paths = _extract_full_imported_paths(py_file)
        for path in imported_paths:
            if path.startswith("app.repositories") or path == "app.repositories":
                violations.append(f"{py_file.relative_to(APP_DIR)} imports repository directly: '{path}'")

    assert not violations, "API layer calling repository directly:\n" + "\n".join(violations)


def test_services_layer_does_not_import_repository_implementations():
    """Verify app/services only depends on domain interfaces, not concrete repositories."""
    service_files = list(SERVICES_DIR.rglob("*.py"))
    assert len(service_files) > 0

    violations: list[str] = []
    for py_file in service_files:
        imported_paths = _extract_full_imported_paths(py_file)
        for path in imported_paths:
            if path.startswith("app.repositories") or path == "app.repositories":
                violations.append(f"{py_file.relative_to(APP_DIR)} imports concrete repository: '{path}'")

    assert not violations, "Services importing concrete repositories:\n" + "\n".join(violations)

"""
sharingan.dependencies — Project dependency scanner.

Scans a project directory for dependency files (package.json,
requirements.txt, pyproject.toml) and maps detected packages to
Sharingan registry library IDs for auto-extraction.
"""

from __future__ import annotations

import json
import re
import tomllib  # stdlib in Python 3.11+
from pathlib import Path
from typing import Dict, List, Tuple


def _get_registry() -> dict:
    """Load the Sharingan registry.json file."""
    from sharingan.config import get_registry_path
    registry_path = get_registry_path()
    if not registry_path.exists():
        return {}
    with open(registry_path, "r") as f:
        return json.load(f)


def _normalize_package_name(name: str) -> str:
    """Normalize a package name per PEP 503 (lowercase, hyphens to underscores)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def clean_version(version_str: str) -> str:
    """Remove semver modifiers like ^, ~, >=, ==, etc."""
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_str)
    if match:
        return match.group(1)
    return version_str.strip('^~=><! ')


def _parse_pep508(dep_string: str) -> Tuple[str, str]:
    """Parse a PEP 508 dependency string like 'fastapi>=0.115.0' into (name, version)."""
    match = re.match(r'^([A-Za-z0-9][\w.-]*)', dep_string.strip())
    if not match:
        return ("", "latest")
    name = match.group(1)
    rest = dep_string[match.end():]
    ver_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', rest)
    version = ver_match.group(1) if ver_match else "latest"
    return (name, version)


def parse_package_json(path: Path) -> Dict[str, str]:
    """Parse a package.json file for npm dependencies."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            deps.update(dev_deps)
            return deps
    except Exception:
        return {}


def parse_requirements_txt(path: Path) -> Dict[str, str]:
    """Parse a requirements.txt file for Python dependencies."""
    if not path.exists():
        return {}
    deps = {}
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                name, ver = _parse_pep508(line)
                if name:
                    deps[name] = ver
    except Exception:
        pass
    return deps


def parse_pyproject_toml(path: Path) -> Dict[str, str]:
    """Parse a pyproject.toml file for Python dependencies.

    Handles both PEP 621 format ([project].dependencies) and
    Poetry format ([tool.poetry.dependencies]).
    """
    if not path.exists():
        return {}
    deps = {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        # PEP 621 format: [project] dependencies = ["fastapi>=0.115"]
        for dep_str in data.get("project", {}).get("dependencies", []):
            name, ver = _parse_pep508(dep_str)
            if name:
                deps[name] = ver

        # Poetry format: [tool.poetry.dependencies] fastapi = "^0.115"
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for name, ver_spec in poetry_deps.items():
            if name.lower() == "python":
                continue
            if isinstance(ver_spec, str):
                deps[name] = clean_version(ver_spec)
            elif isinstance(ver_spec, dict):
                deps[name] = clean_version(ver_spec.get("version", "latest"))
    except Exception:
        pass
    return deps


def _find_dep_files(start: Path, filename: str, max_up: int = 5) -> list[Path]:
    """Search upward from start dir, then shallowly downward for monorepos."""
    found = []
    # Upward search — find nearest ancestor with the file
    current = start.resolve()
    home = Path.home().resolve()
    for _ in range(max_up):
        candidate = current / filename
        if candidate.exists():
            found.append(candidate)
            break
        parent = current.parent
        if parent == current or current == home:
            break
        current = parent

    # Shallow downward search for monorepo patterns
    for subdir_name in ["apps", "packages", "services", "libs"]:
        mono = start / subdir_name
        if mono.exists() and mono.is_dir():
            for child in mono.iterdir():
                if child.is_dir():
                    candidate = child / filename
                    if candidate.exists():
                        found.append(candidate)
    return found


def scan_project_dependencies(project_dir: Path) -> List[Tuple[str, str]]:
    """Scan the project directory for dependencies and map them to Sharingan libraries.

    Searches upward for dependency files (handles subdirectory invocations)
    and downward into monorepo patterns (apps/*, packages/*).

    Returns:
        List of tuples: (library_id, version)
    """
    registry = _get_registry()
    libraries = registry.get("libraries", {})

    # Build package name → library ID mappings
    npm_to_lib = {}
    pypi_to_lib = {}
    for lib_id, lib in libraries.items():
        if pkg := lib.get("npm_package"):
            npm_to_lib[pkg] = lib_id
        if pkg := lib.get("pypi_package"):
            pypi_to_lib[_normalize_package_name(pkg)] = lib_id

    detected: dict[str, str] = {}  # lib_id → version (dedup)

    # ── JavaScript / TypeScript ──
    for pkg_json_path in _find_dep_files(project_dir, "package.json"):
        npm_deps = parse_package_json(pkg_json_path)
        for pkg, ver in npm_deps.items():
            if pkg in npm_to_lib:
                lib_id = npm_to_lib[pkg]
                if lib_id not in detected:
                    detected[lib_id] = clean_version(ver)

    # ── Python ──
    for req_path in _find_dep_files(project_dir, "requirements.txt"):
        py_deps = parse_requirements_txt(req_path)
        for pkg, ver in py_deps.items():
            norm = _normalize_package_name(pkg)
            if norm in pypi_to_lib:
                lib_id = pypi_to_lib[norm]
                if lib_id not in detected:
                    detected[lib_id] = clean_version(ver)

    for pyproj_path in _find_dep_files(project_dir, "pyproject.toml"):
        py_deps = parse_pyproject_toml(pyproj_path)
        for pkg, ver in py_deps.items():
            norm = _normalize_package_name(pkg)
            if norm in pypi_to_lib:
                lib_id = pypi_to_lib[norm]
                if lib_id not in detected:
                    detected[lib_id] = clean_version(ver)

    return list(detected.items())

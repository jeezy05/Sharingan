import json
from pathlib import Path

from sharingan.config import get_libraries_dir, get_cache_dir
from sharingan.discover import load_registry

def _find_installed_libraries() -> set[str]:
    """Get the set of library IDs that are actually installed/cached locally."""
    installed = set()
    for d in (get_libraries_dir(), get_cache_dir() / "libraries"):
        if d.exists():
            for child in d.iterdir():
                if child.is_dir():
                    installed.add(child.name)
    return installed

def _parse_package_json(path: Path) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            deps = list(data.get("dependencies", {}).keys())
            deps.extend(list(data.get("devDependencies", {}).keys()))
            return deps
    except Exception:
        return []

def _parse_pyproject_toml(path: Path) -> list[str]:
    deps = []
    try:
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
            # PEP 621
            raw_deps = data.get("project", {}).get("dependencies", [])
            # Poetry
            poetry_deps = list(data.get("tool", {}).get("poetry", {}).get("dependencies", {}).keys())
            
            for dep in raw_deps + poetry_deps:
                pkg = dep.split(">")[0].split("=")[0].split("<")[0].split("~")[0].strip()
                if pkg and pkg != "python":
                    deps.append(pkg)
    except Exception:
        pass
    return deps

def _parse_requirements_txt(path: Path) -> list[str]:
    deps = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg = line.split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip()
                    if pkg:
                        deps.append(pkg)
    except Exception:
        pass
    return deps

def scan_project_dependencies(directory: str = ".") -> str:
    """Scans the given directory for dependencies and cross-references with Sharingan."""
    base = Path(directory).resolve()
    
    found_deps = []
    if (base / "package.json").exists():
        found_deps.extend(_parse_package_json(base / "package.json"))
    if (base / "pyproject.toml").exists():
        found_deps.extend(_parse_pyproject_toml(base / "pyproject.toml"))
    if (base / "requirements.txt").exists():
        found_deps.extend(_parse_requirements_txt(base / "requirements.txt"))
        
    if not found_deps:
        return "No package.json, pyproject.toml, or requirements.txt found in the given directory."
        
    registry = load_registry()
    # Map npm/pypi package names to Sharingan library IDs
    pkg_to_id = {}
    for lib in registry.get("libraries", {}).values():
        if lib.get("npm_package"):
            pkg_to_id[lib["npm_package"].lower()] = lib["id"]
        if lib.get("pypi_package"):
            pkg_to_id[lib["pypi_package"].lower()] = lib["id"]
        # Fallback to id
        pkg_to_id[lib["id"].lower()] = lib["id"]

    installed_locally = _find_installed_libraries()
    
    available = []
    missing = []
    
    for dep in set(found_deps):
        dep_lower = dep.lower()
        if dep_lower in pkg_to_id:
            lib_id = pkg_to_id[dep_lower]
            if lib_id in installed_locally:
                available.append(lib_id)
            else:
                missing.append(dep)
        else:
            missing.append(dep)
            
    # Format the strict routing instructions
    lines = ["# Dependency Routing Instructions\n"]
    
    if available:
        lines.append("**✅ Available locally via Sharingan:**")
        for lib in sorted(set(available)):
            lines.append(f"- `{lib}`: Use the `ask_sharingan` tool to fetch deterministic documentation.")
        lines.append("")
    
    if missing:
        lines.append("**❌ Missing from Sharingan (Requires Web Search):**")
        lines.append("The following libraries are NOT installed in Sharingan. You MUST use your standard `search_web` or web scraping tools to find documentation for them:")
        lines.append(", ".join(sorted(set(missing))[:20]) + ("..." if len(missing) > 20 else ""))
        
    return "\n".join(lines)

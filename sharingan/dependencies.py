import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def get_registry() -> dict:
    """Load the Sharingan registry.json file."""
    registry_path = Path(__file__).parent / "data" / "registry.json"
    if not registry_path.exists():
        return {}
    with open(registry_path, "r") as f:
        return json.load(f)

def clean_version(version_str: str) -> str:
    """Remove semver modifiers like ^, ~, >=, ==, etc."""
    # Match basic semver: numbers dot numbers dot numbers
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_str)
    if match:
        return match.group(1)
    return version_str.strip('^~=>< ')

def parse_package_json(path: Path) -> Dict[str, str]:
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
    if not path.exists():
        return {}
    deps = {}
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = re.split(r'[=<>~]+', line, 1)
                if len(parts) == 2:
                    deps[parts[0].strip()] = parts[1].strip()
                else:
                    deps[parts[0].strip()] = "latest"
    except Exception:
        pass
    return deps

def parse_pyproject_toml(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    deps = {}
    try:
        with open(path, "r") as f:
            content = f.read()
            # Handle key = "value" (Poetry style)
            for line in content.splitlines():
                match = re.match(r'^([\w\-\_]+)\s*=\s*"([^"]+)"', line.strip())
                if match:
                    deps[match.group(1)] = match.group(2)
            
            # Handle array dependencies (PEP 621 style) e.g., "networkx>=3.2",
            array_matches = re.finditer(r'"([\w\-\_]+)(>=|<=|==|~=|>|<)?([^"]*)"', content)
            for match in array_matches:
                pkg = match.group(1)
                ver = match.group(3) if match.group(3) else "latest"
                if pkg and pkg not in deps:
                    deps[pkg] = ver
    except Exception:
        pass
    return deps

def scan_project_dependencies(project_dir: Path) -> List[Tuple[str, str]]:
    """
    Scans the project directory for dependencies and maps them to Sharingan libraries.
    Returns a list of tuples: (library_id, version)
    """
    registry = get_registry()
    libraries = registry.get("libraries", {})
    
    npm_to_lib = {lib["npm_package"]: lib_id for lib_id, lib in libraries.items() if lib.get("npm_package")}
    pypi_to_lib = {lib["pypi_package"]: lib_id for lib_id, lib in libraries.items() if lib.get("pypi_package")}
    
    detected = []
    
    # Check JS/TS
    package_json = project_dir / "package.json"
    if package_json.exists():
        npm_deps = parse_package_json(package_json)
        for pkg, ver in npm_deps.items():
            if pkg in npm_to_lib:
                clean_ver = clean_version(ver)
                detected.append((npm_to_lib[pkg], clean_ver))
                
    # Check Python
    req_txt = project_dir / "requirements.txt"
    pyproject = project_dir / "pyproject.toml"
    py_deps = {}
    if req_txt.exists():
        py_deps.update(parse_requirements_txt(req_txt))
    if pyproject.exists():
        py_deps.update(parse_pyproject_toml(pyproject))
        
    for pkg, ver in py_deps.items():
        if pkg in pypi_to_lib:
            clean_ver = clean_version(ver)
            detected.append((pypi_to_lib[pkg], clean_ver))
            
    return detected

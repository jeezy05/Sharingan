import json
import os
import shutil
import ssl
import urllib.request
from pathlib import Path

# Paths
registry_path = Path("sharingan/data/registry.json")
graphs_repo_path = Path("/Users/jaipradeepawasthi/Documents/EyesofMadara/Sharingan-Graphs/graphs")
local_cache_path = Path.home() / ".sharingan" / "libraries"

# The 15 libraries
libraries_to_fix = [
    "zarr", "taichi", "warp", "pymc", "equinox", "ibis", "narwhals",
    "marimo", "pyomo", "simpy", "awkward", "lonboard", "quantlib",
    "kfr", "scanpy"
]

def get_pypi_version(package_name: str) -> str:
    """Fetch the latest version of a package from PyPI."""
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode())
            return data["info"]["version"]
    except Exception as e:
        print(f"Failed to fetch PyPI version for {package_name}: {e}")
        return "main"

def fix_versions():
    # 1. Load registry
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    for lib in libraries_to_fix:
        if lib not in registry["libraries"]:
            continue
            
        entry = registry["libraries"][lib]
        
        # If it's already fixed, skip
        if entry.get("latest_version") != "main":
            continue
            
        pypi_pkg = entry.get("pypi_package") or lib
        
        # For non-python packages like kfr (C++), just default to a specific version or skip
        if lib == "kfr":
            latest_version = "6.0.2"
        elif lib == "warp":
            latest_version = "1.0.2" # warp-lang
        else:
            latest_version = get_pypi_version(pypi_pkg)
            
        if latest_version == "main":
            continue
            
        print(f"[{lib}] Correcting 'main' -> '{latest_version}'")
        
        # 2. Update registry
        entry["latest_version"] = latest_version
        if "tracked_versions" in entry:
            entry["tracked_versions"] = [
                latest_version if v == "main" else v 
                for v in entry["tracked_versions"]
            ]
            
        # 3. Rename folder in Sharingan-Graphs repo
        repo_main_dir = graphs_repo_path / lib / "main"
        repo_new_dir = graphs_repo_path / lib / latest_version
        if repo_main_dir.exists():
            repo_main_dir.rename(repo_new_dir)
            print(f"  -> Renamed repo folder: {repo_new_dir}")
            
        # 4. Rename folder in local ~/.sharingan/libraries/
        local_main_dir = local_cache_path / lib / "versions" / "main"
        local_new_dir = local_cache_path / lib / "versions" / latest_version
        if local_main_dir.exists():
            local_main_dir.rename(local_new_dir)
            print(f"  -> Renamed local cache folder: {local_new_dir}")

    # Save registry
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        print("Updated registry.json")

if __name__ == "__main__":
    fix_versions()

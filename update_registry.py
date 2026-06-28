import json
import shutil
from pathlib import Path

registry_path = Path("sharingan/data/registry.json")
cache_path = Path.home() / ".sharingan" / "libraries"

with open(registry_path, "r", encoding="utf-8") as f:
    registry = json.load(f)

# Update marimo
if "marimo" in registry["libraries"]:
    registry["libraries"]["marimo"]["docs_config"] = {
        "type": "html",
        "base_url": "https://docs.marimo.io",
        "docs_path": None,
        "extra_paths": []
    }

# Update lonboard
if "lonboard" in registry["libraries"]:
    registry["libraries"]["lonboard"]["docs_config"] = {
        "type": "html",
        "base_url": "https://developmentseed.org/lonboard/latest",
        "docs_path": None,
        "extra_paths": []
    }

with open(registry_path, "w", encoding="utf-8") as f:
    json.dump(registry, f, indent=2)

# Delete poisoned cache
for lib in ["marimo", "lonboard"]:
    lib_path = cache_path / lib
    if lib_path.exists():
        shutil.rmtree(lib_path)
        print(f"Deleted poisoned cache for {lib}")

print("Updated registry.json for HTML scraping.")

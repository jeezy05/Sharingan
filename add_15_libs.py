import json
from pathlib import Path

# The 15 libraries identified from the image
LIBRARIES = [
    {
        "id": "zarr",
        "name": "Zarr",
        "category": "scientific-computing",
        "repo": "zarr-developers/zarr-python",
        "pypi": "zarr",
        "docs_url": "https://zarr.readthedocs.io/",
        "tags": ["scientific", "hpc", "storage", "arrays"]
    },
    {
        "id": "taichi",
        "name": "Taichi",
        "category": "high-performance-compute",
        "repo": "taichi-dev/taichi",
        "pypi": "taichi",
        "docs_url": "https://docs.taichi-lang.org/",
        "tags": ["graphics", "simulation", "gpu", "metal", "cuda"]
    },
    {
        "id": "warp",
        "name": "NVIDIA Warp",
        "category": "high-performance-compute",
        "repo": "NVIDIA/warp",
        "pypi": "warp-lang",
        "docs_url": "https://nvidia.github.io/warp/",
        "tags": ["nvidia", "gpu", "simulation", "physics"]
    },
    {
        "id": "pymc",
        "name": "PyMC",
        "category": "probabilistic",
        "repo": "pymc-devs/pymc",
        "pypi": "pymc",
        "docs_url": "https://www.pymc.io/",
        "tags": ["bayesian", "statistics", "inference"]
    },
    {
        "id": "equinox",
        "name": "Equinox",
        "category": "jax-ecosystem",
        "repo": "patrick-kidger/equinox",
        "pypi": "equinox",
        "docs_url": "https://docs.kidger.site/equinox/",
        "tags": ["jax", "neural-networks", "deep-learning"]
    },
    {
        "id": "ibis",
        "name": "Ibis",
        "category": "modern-data-stack",
        "repo": "ibis-project/ibis",
        "pypi": "ibis-framework",
        "docs_url": "https://ibis-project.org/",
        "tags": ["dataframe", "sql", "analytics"]
    },
    {
        "id": "narwhals",
        "name": "Narwhals",
        "category": "modern-data-stack",
        "repo": "narwhals-dev/narwhals",
        "pypi": "narwhals",
        "docs_url": "https://narwhals-dev.github.io/narwhals/",
        "tags": ["dataframe", "compatibility", "polars", "pandas"]
    },
    {
        "id": "marimo",
        "name": "Marimo",
        "category": "modern-data-stack",
        "repo": "marimo-team/marimo",
        "pypi": "marimo",
        "docs_url": "https://docs.marimo.io/",
        "tags": ["notebook", "reactive", "reproducible"]
    },
    {
        "id": "pyomo",
        "name": "Pyomo",
        "category": "optimization",
        "repo": "Pyomo/pyomo",
        "pypi": "Pyomo",
        "docs_url": "https://pyomo.readthedocs.io/",
        "tags": ["optimization", "algebraic-modeling", "linear-programming"]
    },
    {
        "id": "simpy",
        "name": "SimPy",
        "category": "simulation",
        "repo": "simpy/simpy",
        "pypi": "simpy",
        "docs_url": "https://simpy.readthedocs.io/",
        "tags": ["discrete-event", "simulation", "logistics"]
    },
    {
        "id": "awkward",
        "name": "Awkward Array",
        "category": "array-computing",
        "repo": "scikit-hep/awkward",
        "pypi": "awkward",
        "docs_url": "https://awkward-array.org/",
        "tags": ["arrays", "json", "physics", "hep"]
    },
    {
        "id": "lonboard",
        "name": "Lonboard",
        "category": "geospatial",
        "repo": "developmentseed/lonboard",
        "pypi": "lonboard",
        "docs_url": "https://developmentseed.org/lonboard/latest/",
        "tags": ["geospatial", "gpu", "visualization", "maps"]
    },
    {
        "id": "quantlib",
        "name": "QuantLib-Python",
        "category": "quantitative-finance",
        "repo": "lballabio/QuantLib",
        "pypi": "QuantLib",
        "docs_url": "https://quantlib-python-docs.readthedocs.io/",
        "tags": ["finance", "derivatives", "pricing"]
    },
    {
        "id": "kfr",
        "name": "Kfr",
        "category": "audio-signal",
        "repo": "kfrlib/kfr",
        "pypi": None,
        "docs_url": "https://kfrlib.com/",
        "tags": ["dsp", "audio", "cpp", "python"]
    },
    {
        "id": "scanpy",
        "name": "Scanpy / AnnData",
        "category": "bioinformatics",
        "repo": "scverse/scanpy",
        "pypi": "scanpy",
        "docs_url": "https://scanpy.readthedocs.io/",
        "tags": ["bioinformatics", "single-cell", "genomics", "rna-seq"]
    }
]

def update_registry():
    registry_path = Path("sharingan/data/registry.json")
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    for lib in LIBRARIES:
        lib_id = lib["id"]
        
        # Default docs configuration assuming standard GitHub Markdown
        # Some of these might need manual tweaks if their docs are in a different folder (e.g., 'docs' vs 'doc' vs root)
        docs_config = {
            "type": "github_markdown",
            "repo": lib["repo"],
            "branch": "main",
            "docs_path": "docs",
            "extra_paths": []
        }
        
        registry["libraries"][lib_id] = {
            "id": lib_id,
            "name": lib["name"],
            "category": lib["category"],
            "language": "python",
            "repo_url": f"https://github.com/{lib['repo']}",
            "docs_url": lib["docs_url"],
            "npm_package": None,
            "pypi_package": lib["pypi"],
            "latest_version": "main",  # We can just extract from main branch directly if no explicit tag is set
            "tracked_versions": ["main"],
            "tags": lib["tags"],
            "node_type": "library",
            "docs_config": docs_config
        }
        
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    print(f"Successfully added {len(LIBRARIES)} libraries to {registry_path}")

if __name__ == "__main__":
    update_registry()

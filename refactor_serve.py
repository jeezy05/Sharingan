import re

with open("sharingan/serve.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import for get_cache_dir
content = content.replace(
    "from sharingan.config import get_indexes_dir, get_libraries_dir, migrate_legacy_data",
    "from sharingan.config import get_indexes_dir, get_libraries_dir, get_cache_dir, migrate_legacy_data"
)

# Add helper function
helper = """
def _find_library_dir(lib_id: str) -> Path | None:
    # Check cache first
    p = get_cache_dir() / "libraries" / lib_id
    if p.exists(): return p
    # Fallback to local extraction
    p = get_libraries_dir() / lib_id
    if p.exists(): return p
    return None

def _get_all_library_dirs() -> list[Path]:
    dirs = []
    if get_libraries_dir().exists():
        dirs.extend([d for d in get_libraries_dir().iterdir() if d.is_dir()])
    cache_libs = get_cache_dir() / "libraries"
    if cache_libs.exists():
        dirs.extend([d for d in cache_libs.iterdir() if d.is_dir()])
    return dirs
"""
content = content.replace("\n@mcp.tool()\ndef list_libraries() -> str:", helper + "\n@mcp.tool()\ndef list_libraries() -> str:")

# Fix list_libraries
content = re.sub(
    r'libraries_dir = get_libraries_dir\(\)\n    if not libraries_dir.exists\(\):\n        return "No libraries extracted yet. Please run \'sharingan extract <lib>\' first."\n    \n    results = \[\]\n    for lib_dir in sorted\(libraries_dir.iterdir\(\)\):',
    r'dirs = _get_all_library_dirs()\n    if not dirs:\n        return "No libraries extracted yet. Please run \'sharingan extract <lib>\' first."\n    \n    results = []\n    for lib_dir in sorted(dirs, key=lambda d: d.name):',
    content
)

# Fix search_symbols
content = re.sub(
    r'symbols_path = libraries_dir / lib_id / "versions" / ver / "symbols.json"',
    r'lib_dir = _find_library_dir(lib_id)\n        symbols_path = lib_dir / "versions" / ver / "symbols.json" if lib_dir else Path("does_not_exist")',
    content
)
# Fix unused libraries_dir in search_symbols
content = content.replace("libraries_dir = get_libraries_dir()\n    results = []", "results = []")

# Fix get_symbol_details
content = re.sub(
    r'lib_dir = get_libraries_dir\(\) / lib_id',
    r'lib_dir = _find_library_dir(lib_id)',
    content
)

# Fix get_neighbors
content = re.sub(
    r'lib_dir = get_libraries_dir\(\) / lib_id',
    r'lib_dir = _find_library_dir(lib_id)',
    content
)

with open("sharingan/serve.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored serve.py")

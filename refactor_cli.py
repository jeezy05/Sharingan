import re

with open("sharingan/cli.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add get_cache_dir to imports
content = content.replace(
    "from sharingan.config import get_data_dir, get_indexes_dir, get_libraries_dir",
    "from sharingan.config import get_data_dir, get_indexes_dir, get_libraries_dir, get_cache_dir"
)

# Helper for CLI
helper = """
def _find_library_dir(lib_id: str) -> Path | None:
    p = get_cache_dir() / "libraries" / lib_id
    if p.exists(): return p
    p = get_libraries_dir() / lib_id
    if p.exists(): return p
    return None
"""

content = content.replace("def info(", helper + "\n@main.command()\n@click.argument(\"library\")\ndef info(")

# Fix info command
content = re.sub(
    r'lib_dir = get_libraries_dir\(\) / source\.library_id',
    r'lib_dir = _find_library_dir(source.library_id)\n    if not lib_dir:\n        lib_dir = Path("does_not_exist")',
    content
)

# Fix query command symbols_path
content = re.sub(
    r'symbols_path = \(\n            get_libraries_dir\(\) / lib_id / "versions" / ver / "symbols\.json"\n        \)',
    r'lib_dir = _find_library_dir(lib_id)\n        symbols_path = lib_dir / "versions" / ver / "symbols.json" if lib_dir else Path("does_not_exist")',
    content
)

# Fix build command
content = re.sub(
    r'libraries_dir = get_libraries_dir\(\)\n\n    build_indexes\(\n        libraries_dir=libraries_dir,\n        indexes_dir=indexes_dir,\n    \)',
    r'build_indexes([get_libraries_dir(), get_cache_dir() / "libraries"], indexes_dir)',
    content
)

with open("sharingan/cli.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored cli.py")

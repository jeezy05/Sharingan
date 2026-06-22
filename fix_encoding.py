import re
import glob

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix write_text(something) -> write_text(something, encoding="utf-8")
    # Only if it doesn't already have encoding
    new_content = re.sub(
        r'\.write_text\(([^,)]+)\)',
        r'.write_text(\1, encoding="utf-8")',
        content
    )
    
    # Fix open(path) -> open(path, encoding="utf-8")
    new_content = re.sub(
        r'open\(([^,)]+)\)',
        r'open(\1, encoding="utf-8")',
        new_content
    )
    
    # Fix open(path, "r") -> open(path, "r", encoding="utf-8")
    new_content = re.sub(
        r'open\(([^,)]+),\s*(["\'][rwaw+]+["\'])\)',
        r'open(\1, \2, encoding="utf-8")',
        new_content
    )
    
    # Revert rb/wb which shouldn't have encoding
    new_content = re.sub(
        r'open\(([^,)]+),\s*(["\'][rw]b["\']),\s*encoding="utf-8"\)',
        r'open(\1, \2)',
        new_content
    )

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {filepath}")

for f in glob.glob("sharingan/*.py"):
    fix_file(f)

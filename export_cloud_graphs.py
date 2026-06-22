import os
import tarfile
import json
from pathlib import Path

# Paths
local_libs = Path.home() / ".sharingan" / "libraries"
export_dir = Path("Sharingan-Graphs/graphs")
export_dir.mkdir(parents=True, exist_ok=True)

for lib_dir in local_libs.iterdir():
    if not lib_dir.is_dir(): continue
    
    lib_id = lib_dir.name
    versions_dir = lib_dir / "versions"
    if not versions_dir.exists(): continue
    
    for ver_dir in versions_dir.iterdir():
        if not ver_dir.is_dir(): continue
        
        version = ver_dir.name
        print(f"Compressing {lib_id} v{version}...")
        
        # Create output dir: Sharingan-Graphs/graphs/nextjs/15.3.2/
        out_dir = export_dir / lib_id / version
        out_dir.mkdir(parents=True, exist_ok=True)
        
        tar_path = out_dir / "graph.tar.gz"
        
        # Compress the contents of the version directory
        with tarfile.open(tar_path, "w:gz") as tar:
            # We want the contents of ver_dir to be at the root of the tar
            for item in ver_dir.iterdir():
                tar.add(item, arcname=item.name)
                
print("Finished exporting all libraries to Sharingan-Graphs/graphs/")

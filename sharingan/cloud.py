"""
sharingan.cloud - Cloud CDN downloader for Sharingan Knowledge Graphs.
"""

import httpx
import shutil
import tarfile
from pathlib import Path
from rich.console import Console

from sharingan.config import get_cache_dir

console = Console(stderr=True)

# We will use a mock/public GitHub repo for the MVP CDN
# When a real CDN is set up, this URL will change to https://api.sharingan.dev/v1/
CDN_BASE_URL = "https://raw.githubusercontent.com/jeezy05/Sharingan-Graphs/main/graphs"

async def download_cloud_graph(library_id: str, version: str) -> bool:
    """Download the pre-computed knowledge graph from the cloud CDN.
    
    Returns True if downloaded and extracted successfully.
    """
    url = f"{CDN_BASE_URL}/{library_id}/{version}/graph.tar.gz"
    
    cache_dir = get_cache_dir() / "libraries" / library_id / "versions" / version
    if cache_dir.exists():
        console.print(f"[green]✓ Cloud graph for {library_id} v{version} already cached.[/]")
        return True
        
    cache_dir.mkdir(parents=True, exist_ok=True)
    tar_path = cache_dir / "graph.tar.gz"
    
    console.print(f"[cyan]Downloading {library_id} v{version} from Cloud CDN...[/]")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            
            if response.status_code == 404:
                console.print(f"[yellow]⚠ {library_id} v{version} is not available on the Cloud CDN.[/]")
                shutil.rmtree(cache_dir, ignore_errors=True)
                return False
                
            response.raise_for_status()
            
            with open(tar_path, "wb") as f:
                f.write(response.content)
                
        # Extract the tar
        with tarfile.open(tar_path, "r:gz") as tar:
            # We must be careful to avoid directory traversal attacks from malicious tars,
            # but since we control the CDN, a simple extractall is fine for now.
            tar.extractall(path=cache_dir)
            
        # Clean up the tar file
        tar_path.unlink()
        
        # Rebuild indexes since we added a new library
        from sharingan.build import build_indexes
        from sharingan.config import get_libraries_dir, get_indexes_dir
        
        console.print("[cyan]Rebuilding global indexes...[/]")
        build_indexes(
            [get_libraries_dir(), get_cache_dir() / "libraries"], 
            get_indexes_dir()
        )
        
        console.print(f"[green]✓ Successfully downloaded and cached {library_id} v{version}[/]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Failed to download {library_id} v{version}: {e}[/]")
        shutil.rmtree(cache_dir, ignore_errors=True)
        return False

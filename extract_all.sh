#!/bin/bash

# ---------------------------------------------------------
# ENFORCE LOCAL OLLAMA CONFIGURATION
# ---------------------------------------------------------
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="qwen2.5:3b"
unset OLLAMA_API_KEY
# ---------------------------------------------------------

# Array of all 15 library IDs added to the registry
LIBRARIES=(
    "zarr"
    "taichi"
    "warp"
    "pymc"
    "equinox"
    "ibis"
    "narwhals"
    "marimo"
    "pyomo"
    "simpy"
    "awkward"
    "lonboard"
    "quantlib"
    "kfr"
    "scanpy"
)

echo "Starting bulk extraction of ${#LIBRARIES[@]} high-impact libraries using local Ollama (qwen2.5:3b)..."
echo "This will take some time, but --update will skip any already processed pages."
echo "========================================================================="

# Loop through each library and run the extraction
for lib in "${LIBRARIES[@]}"; do
    echo "========================================================================="
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] 🚀 Starting extraction for: $lib"
    echo "========================================================================="
    
    # Run sharingan extract command
    # --update  : skips pages that have already been extracted successfully
    # --local   : completely bypasses the Cloud CDN check so it doesn't falsely skip libraries
    # --backend : strictly uses the ollama engine
    python3 -m sharingan extract "$lib" --backend ollama --update --local
    
    # Check if extraction was successful
    if [ $? -eq 0 ]; then
        echo "✅ Successfully extracted: $lib"
    else
        echo "❌ Failed to extract: $lib"
        echo "Continuing to next library..."
    fi
    
    echo ""
done

echo "🎉 All extractions completed!"

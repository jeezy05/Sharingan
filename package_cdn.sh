#!/bin/bash

# Configuration
SHARINGAN_DIR="$HOME/.sharingan"
TARGET_REPO="$HOME/Documents/EyesofMadara/Sharingan-Graphs"
GRAPHS_DIR="$TARGET_REPO/graphs"
INDEXES_DIR="$TARGET_REPO/indexes"

echo "=========================================================="
echo "📦 Packaging local Sharingan extractions for Cloud CDN"
echo "=========================================================="

# Create the target repository structure
mkdir -p "$GRAPHS_DIR"
mkdir -p "$INDEXES_DIR"

# 1. Package each library into graph.tar.gz
echo "Packaging libraries..."
for lib_dir in "$SHARINGAN_DIR/libraries"/*; do
    if [ -d "$lib_dir" ]; then
        lib_name=$(basename "$lib_dir")
        
        for version_dir in "$lib_dir/versions"/*; do
            if [ -d "$version_dir" ]; then
                version_name=$(basename "$version_dir")
                
                # Create the target directory in the repo
                target_version_dir="$GRAPHS_DIR/$lib_name/$version_name"
                mkdir -p "$target_version_dir"
                
                echo "  -> Compressing $lib_name v$version_name..."
                
                # We need to compress the contents of the version directory (excluding the cache directory)
                # into graph.tar.gz inside the target repo
                tar -czf "$target_version_dir/graph.tar.gz" \
                    -C "$version_dir" \
                    --exclude="cache" \
                    .
            fi
        done
    fi
done

# 2. Copy the global search indexes
echo "Copying global indexes..."
if [ -d "$SHARINGAN_DIR/indexes" ]; then
    cp -r "$SHARINGAN_DIR/indexes/"* "$INDEXES_DIR/"
    echo "  -> Indexes copied successfully."
else
    echo "  -> No global indexes found to copy."
fi

echo "=========================================================="
echo "✅ All packages successfully exported to:"
echo "   $TARGET_REPO"
echo ""
echo "Next Steps:"
echo "1. cd $TARGET_REPO"
echo "2. git init (if not already a repo)"
echo "3. git add ."
echo "4. git commit -m \"Update CDN knowledge graphs\""
echo "5. git push origin main"
echo "=========================================================="

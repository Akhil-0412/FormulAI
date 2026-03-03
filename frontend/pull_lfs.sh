#!/bin/bash
echo "Installing Git LFS for Vercel Image Fetching..."
curl -sLO https://github.com/git-lfs/git-lfs/releases/download/v3.4.0/git-lfs-linux-amd64-v3.4.0.tar.gz
tar -xzf git-lfs-linux-amd64-v3.4.0.tar.gz
export PATH=$PATH:$(pwd)/git-lfs-3.4.0

git lfs install
git remote set-url origin https://github.com/Akhil-0412/FormulAI.git
# Force Git to read attributes from HEAD instead of index since Vercel does a sparse/shallow clone
export GIT_ATTR_SOURCE=HEAD
git config lfs.fetchexclude ""

git fetch origin main
git lfs fetch origin main
git lfs checkout
echo "Restored all image assets successfully!"

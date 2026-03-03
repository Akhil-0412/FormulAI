#!/bin/bash
echo "Installing Git LFS for Vercel Image Fetching..."
curl -sLO https://github.com/git-lfs/git-lfs/releases/download/v3.4.0/git-lfs-linux-amd64-v3.4.0.tar.gz
tar -xzf git-lfs-linux-amd64-v3.4.0.tar.gz
export PATH=$PATH:$(pwd)/git-lfs-3.4.0

git lfs install
git remote set-url origin https://github.com/Akhil-0412/FormulAI.git
git fetch origin main
git lfs pull origin main
echo "Restored all image assets successfully!"

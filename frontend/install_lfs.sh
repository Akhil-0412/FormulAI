#!/bin/bash
# Download and install Git LFS binary
curl -sLO https://github.com/git-lfs/git-lfs/releases/download/v3.4.0/git-lfs-linux-amd64-v3.4.0.tar.gz
tar -xzf git-lfs-linux-amd64-v3.4.0.tar.gz
./git-lfs-3.4.0/install.sh

# Re-inject the GitHub context for Vercel's shallow clone
git lfs install
git remote set-url origin https://github.com/Akhil-0412/FormulAI.git
git pull origin main
git lfs fetch origin main
git lfs checkout
echo "LFS Pull Complete!"

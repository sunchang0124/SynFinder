#!/usr/bin/env bash
# Publish SynFinder to a Hugging Face Space, giving a public URL anyone can use.
#
# One-off setup:
#   1. Create a free account at https://huggingface.co/join
#   2. Make a token (write scope) at https://huggingface.co/settings/tokens
#   3. export HF_TOKEN=hf_xxxxxxxx
#   4. ./deploy/to_huggingface.sh <your-hf-username>
#
# Re-run any time to push the latest version.
set -euo pipefail

USER="${1:-}"
SPACE="${2:-synfinder}"
[ -z "$USER" ] && { echo "usage: $0 <hf-username> [space-name]" >&2; exit 1; }
[ -z "${HF_TOKEN:-}" ] && { echo "set HF_TOKEN first (see the header of this script)" >&2; exit 1; }

HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$(command -v python3 || command -v python)}"

"$PY" - "$USER" "$SPACE" "$HERE" <<'PYEOF'
import os, shutil, sys, tempfile, pathlib
from huggingface_hub import HfApi

user, space, root = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
repo_id = f"{user}/{space}"
api = HfApi(token=os.environ["HF_TOKEN"])

api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
print(f"space ready: https://huggingface.co/spaces/{repo_id}")

with tempfile.TemporaryDirectory() as tmp:
    stage = pathlib.Path(tmp)
    for item in ("src", "web", "catalog"):
        shutil.copytree(root / item, stage / item)
    for item in ("Dockerfile", "pyproject.toml"):
        shutil.copy(root / item, stage / item)
    # the Space's README carries the front-matter that configures it
    shutil.copy(root / "deploy" / "space_README.md", stage / "README.md")
    api.upload_folder(folder_path=str(stage), repo_id=repo_id,
                      repo_type="space", commit_message="Deploy SynFinder")

print(f"\nbuilding. live shortly at: https://huggingface.co/spaces/{repo_id}")
PYEOF

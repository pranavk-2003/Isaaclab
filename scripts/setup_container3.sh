#!/usr/bin/env bash
# Installs this repo's packages into the isaac-lab-3 container. Run after every container recreation:
#   docker exec isaac-lab-3 bash /workspace/learnings/scripts/setup_container3.sh
set -euo pipefail
PYTHON=/opt/isaaclab-venv/bin/python
uv pip install --python "$PYTHON" -q xacro 'moviepy<2' imageio-ffmpeg  # needed by --video; the recorder imports the moviepy 1.x API
uv pip install --python "$PYTHON" -q -e /workspace/learnings/source/doosan_lab
echo "[setup_container3] done"

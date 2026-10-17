#!/usr/bin/env bash
# Reinstalls this repo's pip packages. Run after every container recreation:
#   docker exec isaac-lab-base bash /workspace/learnings/scripts/setup_container.sh
set -euo pipefail
cd /workspace/isaaclab
./isaaclab.sh -p -m pip install -q xacro
./isaaclab.sh -p -m pip install -q -e /workspace/learnings/source/doosan_lab
echo "[setup_container] done"

#!/usr/bin/env bash
set -euo pipefail

# Isaac Lab's X11 forwarding needs these; SSH and IDE terminals leave them unset.
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$(ls /run/user/"$(id -u)"/.mutter-Xwaylandauth.* 2>/dev/null | head -1)}"

cd "$HOME/pranav_ws/IsaacLab"
python3 docker/container.py start base \
  --files "$HOME/pranav_ws/Isaac_lab_learnings/docker/learnings.override.yaml"

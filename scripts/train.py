"""Run Isaac Lab's rsl_rl train.py with the Doosan tasks registered.

Takes the same arguments as IsaacLab/scripts/reinforcement_learning/rsl_rl/train.py:

    ./isaaclab.sh -p /workspace/learnings/scripts/train.py --task Doosan-Reach-A0509-v0 --headless

The upstream script is patched in memory at its extension-template marker, so there is no copy to keep in sync.
"""

import os
import sys

SCRIPT = os.path.join(os.environ.get("ISAACLAB_PATH", "/workspace/isaaclab"), "scripts/reinforcement_learning/rsl_rl/train.py")
MARKER = "# PLACEHOLDER: Extension template (do not remove this comment)"

source = open(SCRIPT).read()
assert MARKER in source, f"marker comment not found in {SCRIPT}; Isaac Lab changed?"
source = source.replace(MARKER, "import doosan_lab.tasks  # noqa: F401")

sys.path.insert(0, os.path.dirname(SCRIPT))  # for cli_args
sys.argv[0] = SCRIPT
exec(compile(source, SCRIPT, "exec"), {"__name__": "__main__", "__file__": SCRIPT})

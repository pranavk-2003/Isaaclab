"""Open a USD file in the Isaac Sim GUI.

    isaaclab -p /workspace/learnings/scripts/view_usd.py --visualizer kit --usd /workspace/learnings/assets/a0509_ag95/a0509_ag95.usda

Runs until the window is closed; --frames N stops after N updates (for a headless check).
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation
from isaaclab.sim import SimulationCfg

parser = argparse.ArgumentParser(description="Open a USD file in the GUI.")
parser.add_argument("--usd", required=True, help="USD path inside the container.")
parser.add_argument("--frames", type=int, default=0, help="Stop after this many updates (0: run until the window closes).")
add_launcher_args(parser)
args = parser.parse_args()

with launch_simulation(SimulationCfg(), args):
    import omni.kit.app
    import omni.usd

    omni.usd.get_context().open_stage(args.usd)
    app = omni.kit.app.get_app()
    frames = 0
    while app.is_running() and (args.frames == 0 or frames < args.frames):
        app.update()
        frames += 1
    print(f"[view_usd] opened {args.usd}: {omni.usd.get_context().get_stage().GetRootLayer().identifier}, {frames} updates")

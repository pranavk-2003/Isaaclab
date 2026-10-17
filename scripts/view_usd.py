"""Open a USD file in the Isaac Sim GUI.

    ./isaaclab.sh -p /workspace/learnings/scripts/view_usd.py --usd /workspace/learnings/assets/a0509_ag95/a0509_ag95.usda
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Open a USD file in the GUI.")
parser.add_argument("--usd", required=True, help="USD path inside the container.")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app

import omni.usd  # noqa: E402

omni.usd.get_context().open_stage(args.usd)
while app.is_running():
    app.update()
app.close()

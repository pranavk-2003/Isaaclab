"""Sweep each arm joint through +-A and back, one at a time, and print how the gripper moves.

    ./isaaclab.sh -p /workspace/learnings/scripts/sweep_joints.py                 # GUI, stays open at the end
    ./isaaclab.sh -p /workspace/learnings/scripts/sweep_joints.py --headless      # numbers only

No ground plane by default: with the base at z=0 the gripper hits the floor once joint_2 leans past ~44 deg.
Self-collisions are off, so links passing through each other are expected.
"""

import argparse
import math

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Sweep each A0509 arm joint through +-A and back.")
parser.add_argument("--amplitude_deg", type=float, default=60.0)
parser.add_argument("--period", type=float, default=6.0, help="Seconds per joint for one full -A..+A cycle.")
parser.add_argument("--ground", action="store_true", help="Add the ground plane (default: none, so the floor cannot block a joint).")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_CFG

DT = 1.0 / 120.0
AXES = "xyz"


def dominant(v: torch.Tensor) -> str:
    """The largest component of a displacement, like '+y'."""
    i = int(v.abs().argmax())
    return f"{'+' if v[i] >= 0 else '-'}{AXES[i]}"


def main():
    sim = SimulationContext(sim_utils.SimulationCfg(dt=DT, device=args_cli.device))
    sim.set_camera_view([1.8, -1.8, 1.4], [0.2, 0.0, 0.5])
    if args_cli.ground:
        sim_utils.GroundPlaneCfg().func("/World/defaultGroundPlane", sim_utils.GroundPlaneCfg())
    light = sim_utils.DomeLightCfg(intensity=3000.0, color=(0.75, 0.75, 0.75))
    light.func("/World/Light", light)

    cfg = DOOSAN_A0509_AG95_CFG.copy()
    cfg.prim_path = "/World/Robot"
    robot = Articulation(cfg=cfg)
    sim.reset()

    arm_ids, _ = robot.find_joints("joint_[1-6]")
    base = robot.find_bodies("ag95_base_link")[0][0]
    pad = robot.find_bodies("left_finger_pad")[0][0]
    default = robot.data.default_joint_pos.clone()
    robot.write_joint_state_to_sim(default, torch.zeros_like(default))
    robot.reset()
    z_axis = torch.tensor([0.0, 0.0, 1.0], device=sim.device)

    def points():
        """TCP (grasp point, 0.19 m along the approach axis) and the left pad origin, in the world frame."""
        p, q = robot.data.body_pos_w[0], robot.data.body_quat_w[0]
        return p[base] + 0.19 * quat_apply(q[base], z_axis), p[pad].clone()

    amp = math.radians(args_cli.amplitude_deg)
    steps = int(args_cli.period / DT)
    rows, ok = [], True
    tcp0, pad0 = points()
    print(f"[INFO] start pose: TCP {[round(v, 3) for v in tcp0.tolist()]} | sweeping each joint +-{args_cli.amplitude_deg:.0f} deg over {args_cli.period:.0f} s")

    for j, jid in enumerate(arm_ids):
        print(f"[SWEEP] joint_{j + 1}: positive, then negative, then back")
        at_plus = at_minus = None
        reached_plus = reached_minus = 0.0
        for k in range(steps):
            target = default.clone()
            target[:, jid] += amp * math.sin(2 * math.pi * k / steps)
            robot.set_joint_position_target(target)
            robot.write_data_to_sim()
            sim.step()
            robot.update(DT)
            q = (robot.data.joint_pos[0, jid] - default[0, jid]).item()
            if k == steps // 4:
                at_plus, reached_plus = points(), q
            if k == 3 * steps // 4:
                at_minus, reached_minus = points(), q
        d_tcp = at_plus[0] - at_minus[0]
        d_pad = at_plus[1] - at_minus[1]
        moved = max(d_tcp.norm().item(), d_pad.norm().item())
        reached = min(reached_plus, -reached_minus) / amp
        finite = bool(torch.isfinite(robot.data.joint_pos).all())
        ok &= finite and moved > 1e-3 and reached > 0.9
        rows.append((j + 1, reached_plus, reached_minus, d_tcp, d_pad, moved, reached))

    print(f"DATA joint   reached(+)  reached(-)   TCP moves (+ minus -)            direction   pad moves            direction")
    for j, rp, rm, dt_, dp, moved, reached in rows:
        print(f"DATA joint_{j}   {math.degrees(rp):+7.1f} deg {math.degrees(rm):+7.1f} deg   {[round(v, 3) for v in dt_.tolist()]!s:<30} {dominant(dt_):>5}      "
              f"{[round(v, 3) for v in dp.tolist()]!s:<22} {dominant(dp):>5}")
    print("[INFO] joint_6 turns the gripper about its own approach axis, so the TCP stays put and only the pad moves.")
    print(f"GATE 1.5 joint sweep (numbers): {'PASS' if ok else 'FAIL'} (every joint reached >=90% of +-{args_cli.amplitude_deg:.0f} deg and moved something)")

    if not args_cli.headless:
        print("[INFO] done. The window stays open: look around, then close it.")
        while simulation_app.is_running():
            sim.step()
            robot.update(DT)

    del robot
    sim.clear_all_callbacks()
    sim.clear_instance()


if __name__ == "__main__":
    main()
    simulation_app.close()

"""Measure the AG95: opening vs joint angle, pad parallelism, and squeeze force per N m of drive torque.

    isaaclab -p /workspace/learnings/scripts/measure_gripper.py

Virtual work: the driver applies torque tau through a small angle dq while the pads close by dW (total opening change),
so the squeeze force between the pads is  F = tau / |dW/dq|.
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description="Measure the AG95 geometry and squeeze force per torque.")
parser.add_argument("--gap0", type=float, default=0.0952,
                    help="Gap between the pad inner faces at q=0, measured from the collision meshes (m).")
parser.add_argument("--force", type=float, default=100.0, help="Target squeeze force for the suggestion (N); AG95: 45-160 N.")
add_launcher_args(parser)
args_cli = parser.parse_args()

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply_inverse, quat_conjugate, quat_error_magnitude, quat_mul

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_CFG

DT = 1.0 / 120.0
Q_MAX = 0.93  # driven joint range 0..0.93 rad


def run_test(sim_cfg):
    sim = SimulationContext(sim_cfg)
    sim_utils.create_prim("/World/Origin0", "Xform")
    robot = Articulation(cfg=DOOSAN_A0509_AG95_CFG.replace(prim_path="/World/Origin0/Robot"))
    sim.reset()
    dt = sim.get_physics_dt()

    grip_ids, _ = robot.find_joints([".*_knuckle_joint", ".*_finger_joint"])
    base = robot.find_bodies("ag95_base_link")[0][0]
    left = robot.find_bodies("left_finger_pad")[0][0]
    right = robot.find_bodies("right_finger_pad")[0][0]
    default = robot.data.default_joint_pos.torch.clone()

    def pose_at(q: float):
        """Set all six gripper joints to q; return pad positions and orientations in the gripper frame."""
        state = default.clone()
        state[:, grip_ids] = q
        robot.write_joint_position_to_sim_index(position=state)
        robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(state))
        robot.set_joint_position_target_index(target=state)
        robot.write_data_to_sim()
        sim.step()
        robot.update(dt)
        p, quat = robot.data.body_pos_w.torch[0], robot.data.body_quat_w.torch[0]
        pl = quat_apply_inverse(quat[base], p[left] - p[base])
        pr = quat_apply_inverse(quat[base], p[right] - p[base])
        rot_l = quat_mul(quat_conjugate(quat[base]), quat[left])
        rot_r = quat_mul(quat_conjugate(quat[base]), quat[right])
        return pl, pr, rot_l, rot_r

    pl0, pr0, rl0, rr0 = pose_at(0.0)
    w0 = (pl0[0] - pr0[0]).item()  # pad-origin separation along the closing axis (x)
    print(f"[INFO] pad origins at q=0 (gripper frame): left {[round(v, 4) for v in pl0.tolist()]} right {[round(v, 4) for v in pr0.tolist()]}")
    print(f"[INFO] gap between pad faces at q=0: {args_cli.gap0 * 1000:.1f} mm (from the collision meshes)")
    print("DATA   q[rad]  gap[mm]  L.x[mm]  R.x[mm]  L.z[mm]  tilt_L[deg]  tilt_R[deg]  y-offset[mm]")
    rows = []
    for q in torch.linspace(0.0, Q_MAX, 11).tolist():
        pl, pr, rl, rr = pose_at(q)
        w = (pl[0] - pr[0]).item()
        gap = args_cli.gap0 - (w0 - w)  # the pads translate without rotating
        tilt_l = torch.rad2deg(quat_error_magnitude(rl.unsqueeze(0), rl0.unsqueeze(0))).item()
        tilt_r = torch.rad2deg(quat_error_magnitude(rr.unsqueeze(0), rr0.unsqueeze(0))).item()
        rows.append((q, gap, tilt_l, tilt_r))
        print(f"DATA   {q:6.3f}  {gap * 1000:7.1f}  {pl[0].item() * 1000:7.1f}  {pr[0].item() * 1000:7.1f}  {pl[2].item() * 1000:7.1f}"
              f"  {tilt_l:10.2f}  {tilt_r:10.2f}  {(pl[1].item() - pr[1].item()) * 1000:9.2f}")

    # dW/dq by central difference, where small objects are held
    def gap_at(q):
        pl, pr, _, _ = pose_at(q)
        return args_cli.gap0 - (w0 - (pl[0] - pr[0]).item())

    d = 0.01
    for q in (0.3, 0.5, 0.7):
        slope = (gap_at(q + d) - gap_at(q - d)) / (2 * d)  # m per rad (negative: closing)
        print(f"[INFO] at q={q}: d(gap)/dq = {slope * 1000:.1f} mm/rad -> squeeze force per N m of drive torque = {1 / abs(slope):.1f} N/(N m)")
    slope = (gap_at(0.5 + d) - gap_at(0.5 - d)) / (2 * d)
    tau = args_cli.force * abs(slope)
    limit = robot.data.joint_effort_limits.torch[0, robot.find_joints("left_outer_knuckle_joint")[0][0]].item()
    print(f"[INFO] for {args_cli.force:.0f} N of squeeze (AG95 range 45-160 N) the driver torque limit should be about {tau:.2f} N m "
          f"(the config allows {limit:.1f} N m = {limit / abs(slope):.0f} N)")
    print(f"[INFO] gap that a 40 mm cube needs: {40:.0f} mm -> driven joint about "
          f"{min(rows, key=lambda r: abs(r[1] - 0.040))[0]:.2f} rad (nearest sample)")
    max_tilt = max(max(r[2], r[3]) for r in rows)
    print(f"GATE 1.4b pads stay parallel: {'PASS' if max_tilt < 5.0 else 'FAIL'} (max pad tilt {max_tilt:.2f} deg over the full stroke, limit 5 deg)")

    del robot  # release the articulation before the simulation closes (D8)
    sim.clear_instance()


def main():
    sim_cfg = sim_utils.SimulationCfg(dt=DT, device=args_cli.device)
    with launch_simulation(sim_cfg, args_cli):
        run_test(sim_cfg)


if __name__ == "__main__":
    main()

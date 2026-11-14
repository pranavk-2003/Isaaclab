"""Spawn N copies of the A0509 + AG95 and test that they behave.

Three tests, each with a pass/fail line:
  1.3a hold      - start pose commanded, nothing should move
  1.3b step      - all six arm joints commanded +0.3 rad: must settle, not overshoot, stay inside velocity limits
  1.3c gripper   - drive ONE gripper joint; the five mimic joints must follow it

    isaaclab -p /workspace/learnings/scripts/spawn_robot.py
    isaaclab -p /workspace/learnings/scripts/spawn_robot.py --cfg high_pd
    isaaclab -p /workspace/learnings/scripts/spawn_robot.py --gravity
    isaaclab -p /workspace/learnings/scripts/spawn_robot.py --visualizer kit              # with the GUI

Pattern follows IsaacLab/scripts/tutorials/01_assets/run_articulation.py.
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description="Spawn the A0509 + AG95 and test hold / step response / gripper mimic.")
parser.add_argument("--num_robots", type=int, default=4)
parser.add_argument("--cfg", choices=["base", "high_pd"], default="base")
parser.add_argument("--gravity", action="store_true", help="Let the robot's own links feel gravity (default: off).")
parser.add_argument("--tol", type=float, default=0.01, help="Joint position tolerance in rad.")
parser.add_argument("--step", type=float, default=0.3, help="Size of the arm step response in rad.")
add_launcher_args(parser)
args_cli = parser.parse_args()

import math

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_CFG, DOOSAN_A0509_AG95_HIGH_PD_CFG

DT = 1.0 / 120.0
SPACING = 2.0  # metres between robots
ARM_VEL_LIMITS = torch.tensor([math.pi] * 3 + [2 * math.pi] * 3)  # rad/s, from the A0509 URDF
GRIPPER_TARGET = 0.5  # rad, inside the driven joint's 0..0.93 range


def drive(robot: Articulation, sim: SimulationContext, target: torch.Tensor, seconds: float):
    """Command `target` for `seconds`. Returns joint positions and velocities, each (steps, robots, joints)."""
    dt = sim.get_physics_dt()
    pos, vel = [], []
    for _ in range(int(seconds / dt)):
        robot.set_joint_position_target_index(target=target)
        robot.write_data_to_sim()
        sim.step()
        robot.update(dt)
        pos.append(robot.data.joint_pos.torch.clone())
        vel.append(robot.data.joint_vel.torch.clone())
    return torch.stack(pos), torch.stack(vel)


def reset_joints(robot: Articulation, pos: torch.Tensor):
    robot.write_joint_position_to_sim_index(position=pos)
    robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(pos))


def report(name: str, ok: bool, detail: str) -> bool:
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'} ({detail})")
    return ok


def run_test(sim_cfg):
    sim = SimulationContext(sim_cfg)
    sim.set_camera_view([2.5, 2.5, 2.0], [0.0, 0.0, 0.7])

    sim_utils.GroundPlaneCfg().func("/World/defaultGroundPlane", sim_utils.GroundPlaneCfg())
    light = sim_utils.DomeLightCfg(intensity=3000.0, color=(0.75, 0.75, 0.75))
    light.func("/World/Light", light)
    origins = [[SPACING * i, 0.0, 0.0] for i in range(args_cli.num_robots)]
    for i, origin in enumerate(origins):
        sim_utils.create_prim(f"/World/Origin{i}", "Xform", translation=origin)

    cfg = (DOOSAN_A0509_AG95_CFG if args_cli.cfg == "base" else DOOSAN_A0509_AG95_HIGH_PD_CFG).replace(
        prim_path="/World/Origin.*/Robot"
    )
    if args_cli.gravity:
        cfg.spawn.rigid_props.disable_gravity = False
    robot = Articulation(cfg=cfg)

    sim.reset()
    origins_t = torch.tensor(origins, device=sim.device)
    print(f"[INFO] cfg={args_cli.cfg} gravity={'ON' if args_cli.gravity else 'off'} | fixed base: {robot.is_fixed_base}"
          f" | {robot.num_joints} joints | {robot.num_bodies} bodies")

    # Default state, shifted to each robot's origin.
    root_pose = robot.data.default_root_pose.torch.clone()
    root_pose[:, :3] += origins_t
    robot.write_root_pose_to_sim_index(root_pose=root_pose)
    robot.write_root_velocity_to_sim_index(root_velocity=robot.data.default_root_vel.torch.clone())
    robot.write_joint_position_to_sim_index(position=robot.data.default_joint_pos.torch.clone())
    robot.write_joint_velocity_to_sim_index(velocity=robot.data.default_joint_vel.torch.clone())
    robot.reset()

    arm_ids, _ = robot.find_joints("joint_[1-6]")
    grip_ids, grip_names = robot.find_joints([".*_knuckle_joint", ".*_finger_joint"])
    driven_id = robot.find_joints("left_outer_knuckle_joint")[0][0]
    default = robot.data.default_joint_pos.torch.clone()
    dt = sim.get_physics_dt()
    results = []

    # 1.3a hold
    pos, vel = drive(robot, sim, default, 5.0)
    err = (pos - default)[:, :, arm_ids].abs().max().item()
    results.append(report("1.3a hold", err == err and err < args_cli.tol,
                          f"max arm error {err:.5f} rad over 5 s, tolerance {args_cli.tol}"))

    # 1.3b step response
    target = default.clone()
    target[:, arm_ids] += args_cli.step
    pos, vel = drive(robot, sim, target, 3.0)
    to_target = pos[:, :, arm_ids] - target[:, arm_ids]  # (steps, robots, 6); >0 means past the target
    err_t = to_target.abs().amax(dim=(1, 2))  # worst joint at each step
    final_err = err_t[-1].item()
    late = (err_t >= args_cli.tol).nonzero()
    settle = (late[-1].item() + 1) * dt if len(late) else 0.0
    overshoot = max(to_target.max().item(), 0.0)
    speed_ratio = (vel[:, :, arm_ids].abs().amax(dim=(0, 1)).cpu() / ARM_VEL_LIMITS).max().item()
    ok = final_err == final_err and final_err < args_cli.tol and overshoot < 0.05 and speed_ratio <= 1.05
    results.append(report("1.3b step", ok,
                          f"final error {final_err:.5f} rad | settles in {settle:.2f} s | overshoot {overshoot:.4f} rad"
                          f" (limit 0.05) | peak speed {speed_ratio * 100:.0f}% of the velocity limit"))

    # 1.3c gripper mimic
    reset_joints(robot, default)
    robot.reset()
    target = default.clone()
    target[:, driven_id] = GRIPPER_TARGET
    pos, _ = drive(robot, sim, target, 2.0)
    final = pos[-1, 0]  # robot 0
    driven = final[driven_id].item()
    print("[INFO] gripper joints after commanding left_outer_knuckle_joint to "
          f"{GRIPPER_TARGET} rad:")
    followers_ok = True
    for jid, jname in zip(grip_ids, grip_names):
        gap = abs(final[jid].item() - driven)
        followers_ok &= gap < 0.03
        print(f"         {jname:<28} {final[jid].item():+.4f} rad   (gap to driven joint {gap:.4f})")
    results.append(report("1.3c gripper", followers_ok and abs(driven - GRIPPER_TARGET) < 0.02,
                          f"driven joint reached {driven:.4f} (target {GRIPPER_TARGET}); all followers within 0.03 rad of it"))

    # Gripper position and direction at the start pose (robot 0).
    reset_joints(robot, default)
    robot.reset()
    drive(robot, sim, default, 0.5)
    link6 = robot.find_bodies("link_6")[0][0]
    gbase = robot.find_bodies("ag95_base_link")[0][0]
    p = robot.data.body_pos_w.torch[0] - origins_t[0]
    q = robot.data.body_quat_w.torch[0]
    z = torch.tensor([0.0, 0.0, 1.0], device=sim.device)
    approach = quat_apply(q[gbase], z)
    print(f"[INFO] gap link_6 -> gripper base: {(p[gbase] - p[link6]).norm().item():.4f} m (expected 0.0045)")
    print(f"[INFO] gripper approach axis (+Z): {[round(v, 3) for v in approach.tolist()]}  (straight down = [0, 0, -1])")
    print(f"[INFO] tcp (grasp_link) estimate : {[round(v, 4) for v in (p[gbase] + 0.19 * approach).tolist()]}")

    print(f"SUMMARY: {'ALL PASS' if all(results) else 'SOMETHING FAILED'} "
          f"(cfg={args_cli.cfg}, gravity={'ON' if args_cli.gravity else 'off'})")

    # Release the articulation before the simulation closes, as env.close() does; otherwise Kit hangs on shutdown.
    del robot
    sim.clear_instance()


def main():
    sim_cfg = sim_utils.SimulationCfg(dt=DT, device=args_cli.device)
    with launch_simulation(sim_cfg, args_cli):
        run_test(sim_cfg)


if __name__ == "__main__":
    main()

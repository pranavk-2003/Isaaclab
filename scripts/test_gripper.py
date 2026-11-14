"""Grasp-and-lift test for the A0509 + AG95.

N robots run in parallel, each with its own 4 cm / 50 g cube on a support, at a random small offset and yaw.
Per trial:   settle (gripper open)  ->  close  ->  lift the tool 0.2 m  ->  hold 5 s.
A trial is HELD if the cube rose >= 0.15 m and did not slip more than 10 mm inside the gripper.
Gate 1.4: at least 19 of 20 trials held.

    isaaclab -p /workspace/learnings/scripts/test_gripper.py
    isaaclab -p /workspace/learnings/scripts/test_gripper.py --friction 0.3
    isaaclab -p /workspace/learnings/scripts/test_gripper.py --num_trials 5

The arm is moved with differential IK (pattern: IsaacLab/scripts/tutorials/05_controllers/run_diff_ik.py).
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description="Grasp-and-lift test for the A0509 + AG95.")
parser.add_argument("--num_trials", type=int, default=20)
parser.add_argument("--mass", type=float, default=0.05, help="Cube mass in kg.")
parser.add_argument("--friction", type=float, default=1.0, help="Friction of the cube and the support (pads: see the USD).")
parser.add_argument("--seed", type=int, default=0)
add_launcher_args(parser)
args_cli = parser.parse_args()

import torch

from isaaclab_physx.sim.schemas import PhysxRigidBodyCfg

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, RigidObject, RigidObjectCfg
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.sim import SimulationContext
from isaaclab.utils.math import quat_apply, quat_apply_inverse, subtract_frame_transforms

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_CFG

DT = 1.0 / 120.0
CUBE = 0.04  # edge length, m
Q_OPEN, Q_CLOSE = 0.0, 0.93  # driven joint: fully open / fully closed (the cube stops the pads at ~0.56)
LIFT = 0.20  # m
T_SETTLE, T_CLOSE, T_LIFT, T_HOLD = 0.5, 1.0, 2.0, 5.0  # s
MIN_RISE, MAX_SLIP = 0.15, 0.010  # m

# The pads slide forward as they close, so the support top must sit below the closed pads' bottom edge:
# 0.4359 (ag95_base_link z) - 0.1741 (pad origin) - 0.0252 (pad bottom) = 0.2366, minus 5 mm of clearance.
SUPPORT_TOP = 0.2316
SUPPORT_X = 0.367  # support centred under the gripper (ag95_base_link x at the start pose)


def smoothstep(x: torch.Tensor) -> torch.Tensor:
    x = x.clamp(0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def run_test(sim_cfg):
    torch.manual_seed(args_cli.seed)
    sim = SimulationContext(sim_cfg)
    sim.set_camera_view([1.3, -1.3, 0.8], [0.37, 0.0, 0.3])
    n = args_cli.num_trials

    sim_utils.GroundPlaneCfg().func("/World/defaultGroundPlane", sim_utils.GroundPlaneCfg())
    light = sim_utils.DomeLightCfg(intensity=3000.0, color=(0.75, 0.75, 0.75))
    light.func("/World/Light", light)
    cols = 5
    origins = [[2.0 * (i % cols), 2.0 * (i // cols), 0.0] for i in range(n)]
    sim_utils.create_prim("/World/envs", "Xform")  # 3.0 treats /World/envs/env_.* as the per-robot instance boundary
    for i, o in enumerate(origins):
        sim_utils.create_prim(f"/World/envs/env_{i}", "Xform", translation=o)
    origins_t = torch.tensor(origins, device=sim.device)

    def spawn_each(spawn_cfg, name, **kwargs):
        # A regex parent such as env_.* also matches prims spawned earlier, so each spawn would nest inside the last.
        for i in range(n):
            spawn_cfg.func(f"/World/envs/env_{i}/{name}", spawn_cfg, **kwargs)

    material = sim_utils.RigidBodyMaterialCfg(
        static_friction=args_cli.friction, dynamic_friction=args_cli.friction, restitution=0.0
    )
    support = sim_utils.CuboidCfg(  # no rigid_props: a static collider
        size=(0.30, 0.30, 0.20),
        collision_props=sim_utils.CollisionPropertiesCfg(),
        physics_material=material,
        visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.35, 0.35, 0.40)),
    )
    spawn_each(support, "Support", translation=(SUPPORT_X, 0.0, SUPPORT_TOP - 0.10))

    cube_spawn = sim_utils.CuboidCfg(
        size=(CUBE, CUBE, CUBE),
        rigid_props=PhysxRigidBodyCfg(),
        mass_props=sim_utils.MassPropertiesCfg(mass=args_cli.mass),
        collision_props=sim_utils.CollisionPropertiesCfg(),
        physics_material=material,
        visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.85, 0.15, 0.10)),
    )
    spawn_each(cube_spawn, "Cube")
    cube = RigidObject(cfg=RigidObjectCfg(prim_path="/World/envs/env_.*/Cube", spawn=None))  # spawned above

    spawn_each(DOOSAN_A0509_AG95_CFG.spawn, "Robot")
    robot = Articulation(cfg=DOOSAN_A0509_AG95_CFG.replace(prim_path="/World/envs/env_.*/Robot", spawn=None))

    sim.reset()

    arm_ids, _ = robot.find_joints("joint_[1-6]")
    driven_id = robot.find_joints("left_outer_knuckle_joint")[0]
    base = robot.find_bodies("ag95_base_link")[0][0]
    left = robot.find_bodies("left_finger_pad")[0][0]
    jac_idx = base - 1 if robot.is_fixed_base else base  # a fixed base has no jacobian row of its own
    jac_joint_ids = [j + robot.num_base_dofs for j in arm_ids]  # jacobian columns start with the floating-base DoFs
    default = robot.data.default_joint_pos.torch.clone()
    zeros6 = torch.zeros(n, 6, device=sim.device)

    ik = DifferentialIKController(
        DifferentialIKControllerCfg(command_type="pose", use_relative_mode=False, ik_method="dls"),
        num_envs=n,
        device=sim.device,
    )

    def ee_pose_in_base():
        ee, root = robot.data.body_pose_w.torch[:, base], robot.data.root_pose_w.torch
        return subtract_frame_transforms(root[:, 0:3], root[:, 3:7], ee[:, 0:3], ee[:, 3:7])

    # Robot at the start pose, gripper open, cube at a random offset and yaw.
    root_pose = robot.data.default_root_pose.torch.clone()
    root_pose[:, :3] += origins_t
    robot.write_root_pose_to_sim_index(root_pose=root_pose)
    robot.write_root_velocity_to_sim_index(root_velocity=robot.data.default_root_vel.torch.clone())
    robot.write_joint_position_to_sim_index(position=default)
    robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(default))
    robot.set_joint_position_target_index(target=default)
    robot.reset()
    sim.step()
    robot.update(DT)

    dx = (torch.rand(n, device=sim.device) * 2 - 1) * 0.008  # along the closing axis
    dy = (torch.rand(n, device=sim.device) * 2 - 1) * 0.005  # along the pad width
    yaw = (torch.rand(n, device=sim.device) * 2 - 1) * 0.1745  # +-10 deg
    base_pos, base_quat = robot.data.body_pos_w.torch[:, base], robot.data.body_quat_w.torch[:, base]
    cube_pos = base_pos + quat_apply(base_quat, torch.stack([dx, dy, torch.zeros_like(dx)], dim=1))
    cube_pos[:, 2] = origins_t[:, 2] + SUPPORT_TOP + CUBE / 2 + 0.0002  # resting on the support
    cube_quat = torch.stack([torch.zeros_like(yaw), torch.zeros_like(yaw), torch.sin(yaw / 2), torch.cos(yaw / 2)], dim=1)  # (x, y, z, w)
    cube.write_root_pose_to_sim_index(root_pose=torch.cat([cube_pos, cube_quat], dim=1))
    cube.write_root_velocity_to_sim_index(root_velocity=zeros6)
    cube.reset()
    print(f"[INFO] {n} trials | cube {CUBE * 1000:.0f} mm / {args_cli.mass * 1000:.0f} g | friction cube+support {args_cli.friction}"
          f" (pads: from the USD) | squeeze limit {robot.data.joint_effort_limits.torch[0, robot.find_joints('left_outer_knuckle_joint')[0][0]].item():.1f} N m")

    ee_pos0, ee_quat0 = ee_pose_in_base()
    t_close, t_lift, t_hold = T_SETTLE, T_SETTLE + T_CLOSE, T_SETTLE + T_CLOSE + T_LIFT
    total = int((t_hold + T_HOLD) / DT)
    rel_grasp = rise0 = None
    torque_sum = torch.zeros(n, device=sim.device)
    torque_steps = 0
    min_pad_gap = torch.full((n,), 1.0, device=sim.device)

    for k in range(total):
        t = k * DT
        lift = smoothstep(torch.tensor((t - t_lift) / T_LIFT)).item() * LIFT
        cmd = torch.cat([ee_pos0 + torch.tensor([0.0, 0.0, lift], device=sim.device), ee_quat0], dim=1)
        ik.set_command(cmd)
        pos_b, quat_b = ee_pose_in_base()
        jac = robot.data.body_link_jacobian_w.torch[:, jac_idx, :, jac_joint_ids]
        robot.set_joint_position_target_index(
            target=ik.compute(pos_b, quat_b, jac, robot.data.joint_pos.torch[:, arm_ids]), joint_ids=arm_ids
        )
        robot.set_joint_position_target_index(
            target=torch.full((n, 1), Q_OPEN if t < t_close else Q_CLOSE, device=sim.device), joint_ids=driven_id
        )
        robot.write_data_to_sim()
        cube.write_data_to_sim()
        sim.step()
        robot.update(DT)
        cube.update(DT)

        b_pos, b_quat = robot.data.body_pos_w.torch[:, base], robot.data.body_quat_w.torch[:, base]
        cube_in_gripper = quat_apply_inverse(b_quat, cube.data.root_pos_w.torch - b_pos)
        if k == int(t_close / DT) - 1:
            rise0 = cube.data.root_pos_w.torch[:, 2].clone()  # cube height before anything has touched it
        if k == int(t_lift / DT) - 1:
            rel_grasp = cube_in_gripper.clone()  # where the cube sits in the gripper once it is grasped
        if t >= t_hold:
            torque_sum += robot.data.applied_torque.torch[:, driven_id[0]]
            torque_steps += 1

    slip = (cube_in_gripper - rel_grasp).norm(dim=1)
    rise = cube.data.root_pos_w.torch[:, 2] - rise0
    q_held = robot.data.joint_pos.torch[:, driven_id[0]]
    torque = torque_sum / max(torque_steps, 1)
    held = (rise > MIN_RISE) & (slip < MAX_SLIP)

    print(f"{'trial':>5} {'result':>6} {'rise[mm]':>9} {'slip[mm]':>9} {'driven q':>9} {'torque[N m]':>12}  offsets dx/dy[mm] yaw[deg]")
    for i in range(n):
        print(f"{i:5d} {'HELD' if held[i] else 'DROP':>6} {rise[i].item() * 1000:9.1f} {slip[i].item() * 1000:9.2f} "
              f"{q_held[i].item():9.3f} {torque[i].item():12.2f}  {dx[i].item() * 1000:+6.1f} {dy[i].item() * 1000:+5.1f} {torch.rad2deg(yaw[i]).item():+6.1f}")
    nheld = int(held.sum().item())
    print(f"[INFO] mean squeeze torque while holding {torque[held].mean().item() if nheld else float('nan'):.2f} N m "
          f"-> about {torque[held].mean().item() * 9.5 if nheld else float('nan'):.0f} N between the pads (9.5 N per N m, scripts/measure_gripper.py)")
    print(f"[INFO] held-cube slip: mean {slip[held].mean().item() * 1000 if nheld else float('nan'):.2f} mm, worst {slip[held].max().item() * 1000 if nheld else float('nan'):.2f} mm")
    need = max(1, round(0.95 * n))
    print(f"GATE 1.4c grasp-and-lift: {'PASS' if nheld >= need else 'FAIL'} ({nheld}/{n} held, need {need})")

    del robot, cube  # release the articulation before the simulation closes (D8)
    sim.clear_instance()


def main():
    sim_cfg = sim_utils.SimulationCfg(dt=DT, device=args_cli.device)
    with launch_simulation(sim_cfg, args_cli):
        run_test(sim_cfg)


if __name__ == "__main__":
    main()

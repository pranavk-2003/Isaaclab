"""Gripper mimic probe through the reach task, so it runs on any physics backend the task supports.

    isaaclab -p /workspace/learnings/scripts/probe_gripper_physics.py                          # Isaac Sim PhysX
    isaaclab -p /workspace/learnings/scripts/probe_gripper_physics.py physics=newton_mjwarp    # Newton

Newton fills its model from InteractiveScene, so the standalone scripts that spawn prims by hand cannot run on it.
This builds the reach task, commands only the driven gripper joint, and checks that the five mimic followers track it
(the same pass criterion as GATE 1.3c in spawn_robot.py). The arm holds its default pose.
"""

import argparse
import sys

from isaaclab.app import add_launcher_args, launch_simulation

from isaaclab_tasks.utils import resolve_task_config, setup_preset_cli

import doosan_lab.tasks  # noqa: F401  (registers the Doosan-* tasks)

TARGET = 0.5  # rad, inside the driven joint's 0..0.93 range
SECONDS = 2.0

parser = argparse.ArgumentParser(description="Gripper mimic probe on the reach task.")
parser.add_argument("--task", default="Doosan-Reach-A0509-v0")
parser.add_argument("--num_envs", type=int, default=4)
add_launcher_args(parser)
args_cli, hydra_args = setup_preset_cli(parser)
sys.argv = [sys.argv[0]] + hydra_args


def probe(env_cfg):
    import gymnasium as gym
    import torch

    env = gym.make(args_cli.task, cfg=env_cfg)
    env.reset()
    base = env.unwrapped
    robot = base.scene["robot"]
    grip_ids, grip_names = robot.find_joints([".*_knuckle_joint", ".*_finger_joint"])
    driven = robot.find_joints("left_outer_knuckle_joint")[0][0]
    target = robot.data.default_joint_pos.torch.clone()
    target[:, driven] = TARGET
    zero_action = torch.zeros(base.num_envs, base.action_manager.total_action_dim, device=base.device)
    for _ in range(int(SECONDS / base.step_dt)):
        robot.set_joint_position_target_index(target=target)
        env.step(zero_action)
    final = robot.data.joint_pos.torch[0]
    print(f"PROBE physics: {type(base.cfg.sim.physics).__name__} | {robot.num_joints} joints, {robot.num_bodies} bodies, fixed base: {robot.is_fixed_base}")
    ok = abs(final[driven].item() - TARGET) < 0.02
    for jid, name in zip(grip_ids, grip_names):
        gap = abs(final[jid].item() - final[driven].item())
        ok &= gap < 0.03
        print(f"PROBE   {name:<28} {final[jid].item():+.4f} rad  (gap to driven joint {gap:.4f})")
    print(f"PROBE gripper mimic: {'PASS' if ok else 'FAIL'} (driven reached {final[driven].item():.4f}, target {TARGET})")
    del robot, base
    env.close()


def main():
    env_cfg, _ = resolve_task_config(args_cli.task, None)
    env_cfg.scene.num_envs = args_cli.num_envs
    with launch_simulation(env_cfg, args_cli):
        probe(env_cfg)


if __name__ == "__main__":
    main()

"""Evaluate a reach policy, with the policy's MEAN action and with SAMPLED actions (as during training).

    ./isaaclab.sh -p /workspace/learnings/scripts/eval_reach.py --headless                 # latest checkpoint
    ./isaaclab.sh -p /workspace/learnings/scripts/eval_reach.py --headless --checkpoint /path/model_300.pt

Every target is held for 4 s (120 policy steps at 30 Hz). Metrics cover the last second of each target:
  pos_err / ori_err   how far the gripper is from the target
  jitter              std of the gripper position over that second (mm): how much it trembles
  joint_speed         RMS arm joint speed (rad/s)
  action_wiggle       RMS change of the commanded action from one step to the next
GATE 2.2 uses the deterministic (mean-action) numbers.
"""

import argparse
import sys

from isaaclab.app import AppLauncher

RSL_DIR = "/workspace/isaaclab/scripts/reinforcement_learning/rsl_rl"
sys.path.insert(0, RSL_DIR)
import cli_args  # isort: skip

parser = argparse.ArgumentParser(description="Evaluate a reach policy: mean action vs sampled action.")
parser.add_argument("--task", type=str, default="Doosan-Reach-A0509-Play-v0")
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--num_envs", type=int, default=256)
parser.add_argument("--episodes", type=int, default=2, help="12 s episodes = 3 targets each, per environment.")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
simulation_app = AppLauncher(args_cli).app

import importlib.metadata as metadata
import os

import gymnasium as gym
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.math import euler_xyz_from_quat

from isaaclab_rl.rsl_rl import (
    RslRlBaseRunnerCfg,
    RslRlVecEnvWrapper,
    handle_deprecated_rsl_rl_cfg,
    handle_deprecated_rsl_rl_checkpoint,
)

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

import doosan_lab.tasks  # noqa: F401  (registers the Doosan-* tasks)

installed_version = metadata.version("rsl-rl-lib")
TARGET_STEPS = 120  # a new target every 4 s at 30 Hz (the task's resampling_time_range)
WINDOW = 30  # the last second of each target


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg, agent_cfg: RslRlBaseRunnerCfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, installed_version)
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    log_root = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    if args_cli.checkpoint:
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        resume_path = get_checkpoint_path(log_root, agent_cfg.load_run, agent_cfg.load_checkpoint)
    print(f"[INFO] checkpoint: {resume_path}")

    env = RslRlVecEnvWrapper(gym.make(args_cli.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(handle_deprecated_rsl_rl_checkpoint(resume_path, installed_version))
    mean_policy = runner.get_inference_policy(device=env.unwrapped.device)  # deterministic: the mean action
    actor = runner.alg.actor

    def sampled_policy(obs):  # mean action plus noise with the learned std, as in training
        return actor(obs, stochastic_output=True)

    base = env.unwrapped
    robot = base.scene["robot"]
    command = base.command_manager.get_term("ee_pose")
    arm_ids = robot.find_joints("joint_[1-6]")[0]
    ee = robot.find_bodies("ag95_base_link")[0][0]
    n = base.num_envs
    results = {}

    @torch.inference_mode()  # covers env.reset() too: inference tensors cannot be updated outside it
    def run(policy):
        obs, _ = env.reset()
        windows = {"pos_err": [], "ori_err": [], "jitter": [], "joint_speed": [], "action_wiggle": [], "target": []}
        buf = {"pos_err": [], "ori_err": [], "ee": [], "vel": [], "act": []}
        for k in range(args_cli.episodes * 360):
            actions = policy(obs)
            obs, _, _, _ = env.step(actions)
            # skip the last step of each 360-step episode: the env resets there and the gripper jumps to its start pose
            if k % TARGET_STEPS >= TARGET_STEPS - WINDOW and k % 360 != 359:
                buf["pos_err"].append(command.metrics["position_error"].clone())
                buf["ori_err"].append(command.metrics["orientation_error"].clone())
                buf["ee"].append(robot.data.body_pos_w[:, ee].clone())
                buf["vel"].append(robot.data.joint_vel[:, arm_ids].clone())
                buf["act"].append(actions.clone())
            if k % TARGET_STEPS == TARGET_STEPS - 1 and buf["ee"]:
                ee_pos = torch.stack(buf["ee"])  # (window, envs, 3)
                act = torch.stack(buf["act"])
                cmd = command.command  # (envs, 7): target position (base frame) + quaternion
                windows["target"].append(torch.cat([cmd[:, :3], euler_xyz_from_quat(cmd[:, 3:7])[2].unsqueeze(1) % (2 * torch.pi)], dim=1))
                windows["pos_err"].append(torch.stack(buf["pos_err"]).mean(0))
                windows["ori_err"].append(torch.stack(buf["ori_err"]).mean(0))
                windows["jitter"].append(ee_pos.std(0).norm(dim=1) * 1000.0)  # mm
                windows["joint_speed"].append(torch.stack(buf["vel"]).pow(2).mean(dim=(0, 2)).sqrt())
                windows["action_wiggle"].append((act[1:] - act[:-1]).pow(2).mean(dim=(0, 2)).sqrt())
                buf = {key: [] for key in buf}
        return {key: torch.cat(value) for key, value in windows.items()}  # target: (windows*envs, 4) = x, y, z, yaw

    for label, policy in (("mean action", mean_policy), ("sampled action", sampled_policy)):
        results[label] = run(policy)

    print(f"\nEVAL {n} environments x {args_cli.episodes * 3} targets each = {n * args_cli.episodes * 3} settled windows (last 1 s of each target)")
    print(f"EVAL {'':16} {'pos_err[mm]':>22} {'ori_err[rad]':>22} {'jitter[mm]':>12} {'joint_speed':>12} {'action_wiggle':>14}")
    print(f"EVAL {'':16} {'mean / p95 / worst':>22} {'mean / p95 / worst':>22} {'mean':>12} {'rad/s':>12} {'rms':>14}")
    for label, r in results.items():
        pe, oe = r["pos_err"] * 1000.0, r["ori_err"]
        p95 = lambda x: torch.quantile(x, 0.95).item()  # noqa: E731
        print(f"EVAL {label:16} {pe.mean().item():7.1f} /{p95(pe):6.1f} /{pe.max().item():6.1f} {oe.mean().item():8.3f} /{p95(oe):6.3f} /{oe.max().item():6.3f}"
              f" {r['jitter'].mean().item():12.2f} {r['joint_speed'].mean().item():12.4f} {r['action_wiggle'].mean().item():14.4f}")
    d = results["mean action"]
    order = torch.argsort(d["pos_err"], descending=True)[:8]
    print("EVAL hardest targets for the mean-action policy (position in the robot base frame, yaw in rad):")
    for i in order.tolist():
        x, y, z, yaw = d["target"][i].tolist()
        print(f"EVAL   error {d['pos_err'][i].item() * 1000:5.1f} mm / {d['ori_err'][i].item():.3f} rad   at x={x:.2f} y={y:+.2f} z={z:.2f} yaw={yaw:.2f}")
    t = d["target"]
    for name, col, lo, hi in (("x", 0, 0.35, 0.60), ("y", 1, -0.2, 0.2), ("z", 2, 0.25, 0.50), ("yaw", 3, 1.5708, 4.7124)):
        edges = torch.linspace(lo, hi, 4)
        row = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (t[:, col] >= a) & (t[:, col] <= b)
            row.append(f"{a:.2f}..{b:.2f}: {d['pos_err'][m].mean().item() * 1000:5.1f} mm")
        print(f"EVAL   mean position error by {name:3} third:  " + "   ".join(row))
    ok = d["pos_err"].mean().item() < 0.02 and d["ori_err"].mean().item() < 0.1
    print(f"GATE 2.2 reach (mean action): {'PASS' if ok else 'FAIL'} (mean position error {d['pos_err'].mean().item() * 1000:.1f} mm < 20, "
          f"mean orientation error {d['ori_err'].mean().item():.3f} rad < 0.1)")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()

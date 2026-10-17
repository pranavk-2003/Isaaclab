# Notice

This is an independent learning project. It is not affiliated with, endorsed by, or sponsored by NVIDIA, Doosan Robotics
or DH-Robotics. Product and company names belong to their owners.

## Adapted from NVIDIA Isaac Lab (BSD-3-Clause)

Copyright (c) 2022-2026, The Isaac Lab Project Developers. https://github.com/isaac-sim/IsaacLab

Parts of this repository follow or adapt code from Isaac Lab, which is released under the BSD-3-Clause license:

- `source/doosan_lab/doosan_lab/tasks/reach/agents/rsl_rl_ppo_cfg.py` (copied from the UR10 reach agent config)
- `source/doosan_lab/doosan_lab/tasks/reach/reach_env_cfg.py` (extends `ReachEnvCfg`; follows the UR10 reach config)
- `source/doosan_lab/doosan_lab/assets/doosan.py` (follows `isaaclab_assets/robots/universal_robots.py`)
- `scripts/spawn_robot.py`, `scripts/sweep_joints.py`, `scripts/test_gripper.py` (follow the tutorials in `scripts/tutorials/`)
- `scripts/eval_reach.py` (follows `scripts/reinforcement_learning/rsl_rl/play.py`)
- `scripts/train.py`, `scripts/play.py` read Isaac Lab's own scripts at run time; no Isaac Lab code is copied.

## Not included

Robot assets (Doosan A0509 and DH AG95 meshes, USD or URDF files) are NOT part of this repository and are not
redistributed. `third_party/` and `assets/` are git-ignored; see the README for how to obtain them.

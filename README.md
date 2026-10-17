# Doosan A0509 + DH AG95 in Isaac Lab

A step-by-step learning project that takes one robot arm with a two-finger gripper from URDF to a simulated, trained and
evaluated manipulation policy in **NVIDIA Isaac Lab**. Every step has a measurable pass/fail gate, and every
non-obvious choice is written down with its evidence.

**Roadmap:** RL reach → RL lift with cameras → teleop + Isaac Lab Mimic → imitation learning → SmolVLA (vision-language-action)
→ Cosmos Reason → GR00T → real robot.

Everything runs on a single consumer GPU (RTX 4070 SUPER, 12 GB) inside the Isaac Lab 2.3.2 Docker container
(Isaac Sim 5.1.0). This is an independent project; see [NOTICE.md](NOTICE.md).

## Status

| Phase | What | State |
|---|---|---|
| 0 | Workspace, container mount, extension package | done |
| 1 | Digital twin of the A0509 + AG95: composition, articulation config, grasp test, joint sweep, URDF-from-scratch comparison | done |
| 2 | Reach with PPO, joint-position actions | done: **4.5 mm** mean position error, 0.033 rad orientation error |
| 2.3 | Reach with differential-IK actions, compared against joint-position actions | next |
| 3 – 9 | Lift + cameras, teleop + Mimic, BC, SmolVLA, Cosmos Reason, GR00T, real robot | planned, see [PLAN.md](PLAN.md) |

## Results so far

| Test | Result |
|---|---|
| Grasp and lift a 4 cm / 50 g cube, random offset and yaw | 20/20 trials held, about 100 N squeeze |
| +0.3 rad step on all six arm joints | settles in 0.35 s, 0.0015 rad overshoot (gravity on: 0.042 rad sag with the same gains) |
| Reach policy, best of 15 checkpoints, mean action over 6144 settled targets | 4.5 mm mean, 9.9 mm 95th percentile |

## Lessons worth knowing

Full detail and evidence in [DECISIONS.md](DECISIONS.md).

- **Isaac Lab's URDF converter drops `<mimic>` joints by default.** `convert_mimic_joints_to_normal_joints=False` is passed to
  the importer's `set_parse_mimic`, so the followers become ordinary joints. `tools/urdf_to_usda.py --mimic` keeps them.
- **Never speed-cap the followers of a mimic joint.** Capping the five passive gripper joints made the linkage explode;
  limit only the driven joint.
- **PPO is not monotonic.** The reach policy peaked around iteration 450 and was worse by 700. Evaluate checkpoints
  instead of taking the last one.
- **The "vibration" at the target is exploration noise.** The mean action holds still (`scripts/eval_reach.py`).
- A `SceneEntityCfg` shared between manager terms fails on its second use, and standalone scripts must release their
  articulations before `app.close()` or Kit hangs on shutdown.

## Getting started

**Requirements:** an NVIDIA GPU, Docker, and the Isaac Lab 2.3.2 container (`isaac-lab-base`). Robot meshes and USD files
are **not included** in this repository.

1. **Get the robot descriptions** into `third_party/` (git-ignored):
   [`doosan-robot2`](https://github.com/DoosanRobotics/doosan-robot2) at branch `jazzy`, commit
   `e5e2d7f4fe11865b9ddf4ad658362bc8e73296e0`, and
   [`dh_ag95_gripper_ros2`](https://github.com/ian-chuang/dh_ag95_gripper_ros2) at commit
   `fc4f80fdfb3acae5626df4359aec1401cb71a9a3`.
2. **Start the container** with `scripts/start_container.sh` (edit the paths for your machine), then install the
   extension inside it:
   ```bash
   docker exec isaac-lab-base bash /workspace/learnings/scripts/setup_container.sh
   ```
3. **Build the robot USD** from the public URDFs, inside the container from `/workspace/isaaclab`:
   ```bash
   mkdir -p /workspace/learnings/assets/urdf_build
   ./isaaclab.sh -p -c "import sys, xacro; sys.argv = ['xacro', '/workspace/learnings/tools/ag95_top.xacro', '-o', '/workspace/learnings/assets/urdf_build/ag95.urdf']; xacro.main()"
   ./isaaclab.sh -p /workspace/learnings/tools/build_urdf.py
   ./isaaclab.sh -p /workspace/learnings/tools/urdf_to_usda.py --mimic --out /workspace/learnings/assets/urdf_build/a0509_ag95_from_urdf_mimic.usda
   ```
   If you already have A0509 and AG95 USD files, `tools/compose_a0509_ag95.py` composes and validates them instead.
4. **Point the config at your USD:** set `A0509_AG95_USD` in `source/doosan_lab/doosan_lab/assets/doosan.py`.
5. **Run the gates, then train and evaluate:**
   ```bash
   ./isaaclab.sh -p /workspace/learnings/scripts/spawn_robot.py --headless
   ./isaaclab.sh -p /workspace/learnings/scripts/test_gripper.py --headless
   ./isaaclab.sh -p /workspace/learnings/scripts/train.py --task Doosan-Reach-A0509-v0 --headless --num_envs 1024
   ./isaaclab.sh -p /workspace/learnings/scripts/eval_reach.py --headless
   ```

The results above were measured with the composed asset. The URDF-built asset has not been run through every gate yet;
`scripts/compare_assets.py` shows where the two differ.

## Repository layout

| Path | What |
|---|---|
| [PLAN.md](PLAN.md) | the gated plan, phase by phase |
| [PROGRESS.md](PROGRESS.md) | the log of gates passed, with numbers |
| [DECISIONS.md](DECISIONS.md) | every non-obvious choice with its evidence (D1 – D14) |
| [COOKBOOK.md](COOKBOOK.md) | concepts, reading lists and checklists for each phase |
| `source/doosan_lab/` | the installable Isaac Lab extension: articulation config and the reach task |
| `tools/` | asset pipeline: xacro expansion, URDF merge, URDF → single USD, USD composition and validation |
| `scripts/` | robot, gripper and joint-sweep tests, the grasp test, training, playback and evaluation |
| `docker/` | the compose override that mounts this repo into the Isaac Lab container |

## License

BSD-3-Clause, see [LICENSE](LICENSE). Parts adapt NVIDIA Isaac Lab (also BSD-3-Clause); see [NOTICE.md](NOTICE.md).

# Doosan A0509 + DH AG95 in Isaac Lab

A step-by-step learning project that takes one robot arm with a two-finger gripper from URDF to a simulated, trained and
evaluated manipulation policy in **NVIDIA Isaac Lab**. Every step has a measurable pass/fail gate, and every
non-obvious choice is written down with its evidence.

**Roadmap:** RL reach → RL lift with cameras → teleop + Isaac Lab Mimic → imitation learning → SmolVLA (vision-language-action)
→ Cosmos Reason → GR00T → real robot.

Everything runs on a single consumer GPU (RTX 4070 SUPER, 12 GB) inside NVIDIA's Isaac Lab 3.0.0 Docker image
(Isaac Sim 6.2.0). The first phases were built on Isaac Lab 2.3.2 / Isaac Sim 5.1.0 and re-run on 3.0; both sets of numbers
are below. This is an independent project; see [NOTICE.md](NOTICE.md).

## Status

| Phase | What | State |
|---|---|---|
| 0 | Workspace, container mount, extension package | done |
| 1 | Digital twin of the A0509 + AG95: composition, articulation config, grasp test, joint sweep, URDF-from-scratch comparison | done, reproduced on 3.0 |
| 2 | Reach with PPO, joint-position actions | done: **4.9 mm** mean position error on 3.0 (4.5 mm on 2.3.2) |
| M | Migration to Isaac Lab 3.0 / Isaac Sim 6.2, with a Newton physics probe | done: moved to 3.0; train on Newton, validate on PhysX (D16 in [DECISIONS.md](DECISIONS.md)) |
| 2.3 | Reach with differential-IK actions, compared against joint-position actions | next |
| 3 – 9 | Lift + cameras, teleop + Mimic, BC, SmolVLA, Cosmos Reason, GR00T, real robot | planned, see [PLAN.md](PLAN.md) |

## Results so far

| Test | Isaac Lab 2.3.2 | Isaac Lab 3.0 |
|---|---|---|
| Grasp and lift a 4 cm / 50 g cube, random offset and yaw | 20/20 held, about 100 N squeeze | 20/20 held, about 100 N (also on the asset built from the public URDFs) |
| +0.3 rad step on all six arm joints | settles in 0.35 s, 0.0015 rad overshoot | identical |
| Reach policy, best checkpoint, mean action over 6144 settled targets | 4.5 mm mean, 0.033 rad | 4.9 mm / 0.043 rad (seed 2), 5.3 mm / 0.039 rad (seed 1) |
| Reach training, 1024 envs, PhysX | 0.61 s per iteration | 0.63 s per iteration (about 7 min for 700 iterations) |
| Reach training, 1024 envs, Newton | n/a | 0.21 s per iteration; the policy works on PhysX at 11 mm (4 mm transfer gap) |

## Lessons worth knowing

Full detail and evidence in [DECISIONS.md](DECISIONS.md).

- **Upgrading Isaac Lab can break a trained policy without any error.** Quaternions changed from (w, x, y, z) to
  (x, y, z, w). The reach policy observes the commanded pose, so a 2.3.2 checkpoint on 3.0 went from 4.5 mm to 76 mm error
  and passed no gate, with no warning. Reordering the observation columns restores it (`scripts/eval_reach.py --legacy_quat_obs`).
- **Newton's speed comes from a CUDA graph.** The same reach task trains 3x faster on Newton, but with the graph switched off
  Newton is 9x slower than with it, and slower than PhysX. PhysX's 32 solver iterations (needed by the gripper linkage)
  cost it about 45% of its time.
- **Spawning with a regex parent nests prims.** `/World/envs/env_.*/Robot` also matches prims spawned earlier, so each
  spawn can land inside the previous one. Spawn into concrete per-env paths, then bind the asset with `spawn=None`.
- **The 3.0 URDF importer keeps `<mimic>` joints** (as `NewtonMimicAPI`, which PhysX reads) and ignores
  `convert_mimic_joints_to_normal_joints`. It also leaves the base floating; `fix_root_link=True` on the spawn config fixes it.
  On 2.3.2 the default silently dropped the mimic joints.
- **Never speed-cap the followers of a mimic joint.** Capping the five passive gripper joints made the linkage explode;
  limit only the driven joint.
- **PPO is not monotonic.** The reach policy peaked around iteration 250-450 and got worse afterwards on both stacks: 2x
  worse by iteration 700 on 2.3.2, 8x worse on the first 3.0 seed (the second was only evaluated to 450, where it was 2x worse).
  Evaluate checkpoints instead of taking the last one.
- **Differential-IK actions need observation normalization under RL exploration.** Random actions make the arm thrash
  (joint speeds of hundreds of rad/s); without normalization PPO produced NaN within about 20 iterations.
- **The "vibration" at the target is exploration noise.** The mean action holds still (`scripts/eval_reach.py`).
- Standalone scripts must release their articulations before the simulation closes, or Kit can hang on shutdown.

## Getting started

**Requirements:** an NVIDIA GPU (12 GB is enough for everything here, but it is below Isaac Sim's published 16 GB minimum;
a first launch compiles shaders for a few minutes), driver 580 or newer, Docker with the NVIDIA Container Toolkit, and about
50 GB of disk. Robot meshes and USD files are **not included** in this repository.

1. **Get the robot descriptions** into `third_party/` (git-ignored):
   [`doosan-robot2`](https://github.com/DoosanRobotics/doosan-robot2) at branch `jazzy`, commit
   `e5e2d7f4fe11865b9ddf4ad658362bc8e73296e0`, and
   [`dh_ag95_gripper_ros2`](https://github.com/ian-chuang/dh_ag95_gripper_ros2) at commit
   `fc4f80fdfb3acae5626df4359aec1401cb71a9a3`.
2. **Start the container** (pulls `nvcr.io/nvidia/isaac-lab:3.0.0` from NVIDIA's registry; you may need `docker login nvcr.io` first) and install the extension
   into it. The compose file mounts this repo at `/workspace/learnings`. For the GUI, run it from a desktop terminal where
   `$DISPLAY` and `$XAUTHORITY` are set; headless runs need neither.
   ```bash
   docker compose -f docker/isaaclab3.compose.yaml up -d
   docker exec isaac-lab-3 bash /workspace/learnings/scripts/setup_container3.sh   # repeat after any container recreation
   docker exec -it isaac-lab-3 bash
   ```
   Inside the container, once per shell:
   ```bash
   source /opt/isaaclab-venv/bin/activate && cd /workspace/learnings
   isaaclab list_envs | grep Doosan        # the four Doosan tasks
   ```
3. **Build the robot USD** from the public URDFs:
   ```bash
   mkdir -p assets/urdf_build
   isaaclab -p -c "import sys, xacro; sys.argv = ['xacro', 'tools/ag95_top.xacro', '-o', 'assets/urdf_build/ag95.urdf']; xacro.main()"
   isaaclab -p tools/build_urdf.py
   isaaclab -p tools/urdf_to_usda.py --mimic --out assets/urdf_build/a0509_ag95_from_urdf_mimic_3.0.usda
   ```
   If you already have A0509 and AG95 USD files, `tools/compose_a0509_ag95.py` composes and validates them instead.
4. **Point the config at your USD:** set `A0509_AG95_USD` in `source/doosan_lab/doosan_lab/assets/doosan.py`. The scripts
   `spawn_robot.py` and `test_gripper.py` also take `--usd <file>` to test another asset (this fixes a floating base for you).
5. **Run the gates, then train and evaluate:**
   ```bash
   isaaclab -p scripts/spawn_robot.py
   isaaclab -p scripts/test_gripper.py
   isaaclab train --rl_library rsl_rl --task Doosan-Reach-A0509-v0 --num_envs 1024 --max_iterations 700 physics=newton_mjwarp
   isaaclab -p scripts/eval_reach.py --checkpoint logs/rsl_rl/reach_a0509/<run>/model_250.pt
   bash scripts/validate_policy.sh logs/rsl_rl/reach_a0509/<run>/model_250.pt
   isaaclab play --rl_library rsl_rl --task Doosan-Reach-A0509-Play-v0 --num_envs 4 --checkpoint <model.pt> --visualizer kit --real-time
   ```
   `play ... --video --video_length 540` records an MP4. The Newton viewer is `physics=newton_mjwarp --visualizer newton_gl`.

**Two-engine workflow (D16).** While a task has no contact, train on Newton (about 3x faster, no Kit) and validate on PhysX.
`validate_policy.sh` evaluates a checkpoint on both engines back to back and its exit status follows the PhysX gate only. The
task configs default to PhysX, so any command without `physics=...` (evaluation included) is validation-grade. Contact tasks
train on Newton only after a scripted grasp passes there (PLAN.md, 3.1).

The grasp and reach results above were measured with the composed asset. The URDF-built asset passes the same grasp and
hold/step/mimic gates on 3.0; `scripts/compare_assets.py` shows where the two differ.

## Repository layout

| Path | What |
|---|---|
| [PLAN.md](PLAN.md) | the gated plan, phase by phase |
| [PROGRESS.md](PROGRESS.md) | the log of gates passed, with numbers |
| [DECISIONS.md](DECISIONS.md) | every non-obvious choice with its evidence (D1 – D16) |
| [COOKBOOK.md](COOKBOOK.md) | concepts, reading lists and checklists for each phase |
| `source/doosan_lab/` | the installable Isaac Lab extension: articulation config and the reach tasks |
| `tools/` | asset pipeline: xacro expansion, URDF merge, URDF → single USD, USD composition and validation |
| `scripts/` | robot, gripper and joint-sweep tests, the grasp test, a physics-backend gripper probe, reach evaluation |
| `docker/` | the compose file for the Isaac Lab 3.0 container, mounted onto this repo |

## License

BSD-3-Clause, see [LICENSE](LICENSE). Parts adapt NVIDIA Isaac Lab (also BSD-3-Clause); see [NOTICE.md](NOTICE.md).

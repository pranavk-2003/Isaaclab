# Decisions

One entry per decision: **what / why / alternatives considered / date**.

## D1 — Robot: Doosan A0509 (2026-10-17)
- **Why:** a real A0509 will be available for sim-to-real. A digital twin that matches the real robot makes every phase count towards Phase 9.
- **Alternatives:** SO-101 (open source, GR00T-friendly, but no real one available); UR10e (best Isaac Lab support, including `Isaac-Deploy-*-UR10e` sim-to-real reference tasks, but no real UR available). Dropped both. The UR10e deploy tasks are still the **reference template** for sim-to-real choices.

## D2 — Gripper: DH AG95, from existing reference USDs (2026-10-17)
- **Why:** it's the gripper on the target arm. Existing A0509 and AG95 USDs are reused: copied into `assets/` (git-ignored, not redistributed), originals never edited.
- **Evidence the asset is sound:** the AG95 USD couples the linkage with 5 `PhysxMimicJointAPI` joints (gearing −1) driven by `left_outer_knuckle_joint`, the same approach as Isaac Sim's Robotiq 2F-85. Verified under load in PLAN 1.4.
- **Learning path kept:** building from URDF is still done as exercise 1.6 and compared against the reference asset.
- **Alternatives:** building from URDF as the main path (the URDF loop closure exists only in Gazebo fragments, so it needs mimic setup by hand), or a simplified parallel jaw (fallback only, with user approval).

## D3 — Sim POC model order: BC → SmolVLA → GR00T (2026-10-17)
- **Why:** SmolVLA trains on 12 GB and gives a working VLA proof of concept by early 2027. GR00T fine-tuning needs a big GPU that isn't guaranteed yet. BC first proves the dataset is learnable.
- **Alternatives:** GR00T straight away (blocked on GPU); ACT (no language conditioning, so it isn't a VLA).

## D4 — Separate Python envs for Isaac Sim vs. model stacks (2026-10-17)
- **Why:** Isaac Sim's bundled Python and torch pin versions that conflict with LeRobot / Cosmos / GR00T. A policy-server harness (PLAN 5.4) decouples them.

## D5 — Hand-written extension instead of `isaaclab.sh --new` (2026-10-17)
- **Why:** the template generator is an interactive TUI that an agent can't drive. We mirror its layout manually.

## D6 — Building from scratch is part of the point (2026-10-17)
- The user prefers learning by building. When a ready-made shortcut exists, use it for the critical path only if it was explicitly chosen, and keep the DIY path as an exercise with a comparison.

## D7 — Robot links are gravity-compensated (2026-10-18)
- **What:** `disable_gravity=True` on the robot's own rigid bodies in `DOOSAN_A0509_AG95_CFG`. Objects the robot touches still feel gravity.
- **Why:** a real Doosan controller compensates its own weight, so a commanded pose is simply held. Measured with `scripts/spawn_robot.py --gravity`: with gravity on, the arm sags 0.042 rad under the same gains (hold test fails), the tool tip drops 2.8 cm and the gripper tilts ~4 deg. Gravity-off passes with 0.00000 rad error and a 0.35 s settle on the +0.3 rad step.
- **Alternatives:** gravity on with much higher stiffness (wastes effort fighting a problem the real robot does not have). Same choice Isaac Lab makes for the UR10e.
- **Decided by:** Claude, delegated by Pranav.

## D8 — Scripts must tear the simulation down in order before closing the app (2026-10-18)
- **What:** hand-written scripts end with `del robot; sim.clear_all_callbacks(); sim.clear_instance()` before `simulation_app.close()`.
- **Why:** without it Kit's shutdown blocks forever on the live PhysX view. Reproduced with Isaac Lab's own cartpole (hung >150 s, exit 124); with the cleanup it exits in ~4 s. RL scripts are unaffected because `env.close()` does exactly this (`manager_based_env.py` ~L524).

## D9 — Mimic followers must not be speed-capped; only the driver is (2026-10-18)
- **What:** `gripper_passive.velocity_limit_sim = 100.0`; `gripper_drive.velocity_limit_sim = 2.1` (the AG95's URDF limit).
- **Why:** with 2.1 on the followers, commanding the driven joint to 0.5 rad sent it to its 0.93 limit and a follower to 2.49 rad (limit 1.116), peak 226 rad/s. A follower must move exactly as fast as its leader. Single-variable sweep: raising only the follower limit fixes it (gap 0.000); driver damping, driver stiffness, dt 1/240 and 64 solver iterations did not. Driver 2.1 + followers 100 passes at a realistic peak of 2.3 rad/s; the reverse fails.
- **Lesson:** the AG95 USD was not broken. The fault was copying the UR10e config's habit of limiting passive joints.
- **Open:** the finger-pad physics material in the USD points at a missing prim, so the pads have default friction. To be fixed in step 1.4 (grasp test).

## D10 — Gripper squeeze force: driver effort limit 10.5 N m (~100 N) (2026-10-18)
- **What:** `gripper_drive.effort_limit_sim = 10.5` (was 50). Pad friction 1.0, bound to the pads in the composed USD (`PAD_FRICTION` in `tools/compose_a0509_ag95.py`).
- **Why:** `scripts/measure_gripper.py` (virtual work, F = tau / |d gap/dq|) gives ~9.5 N of squeeze per N m of drive torque (d gap/dq = -105 mm/rad at q=0.5). The old 50 N m allowed ~474 N, about 3x the AG95's 160 N maximum. 100 N is the middle of its 45-160 N range.
- **Measured geometry (gripper frame = ag95_base_link, approach +Z):** pads close along X; gap 95.2 mm at q=0 (open) to 1.7 mm at q=0.93; pads stay parallel (0.00 deg tilt over the full stroke); a 40 mm object needs q ~ 0.56. The pads slide forward from z=159 to 175 mm as they close, so an object is held at z ~ 0.17, about 20 mm BEHIND the grasp_link TCP (z=0.19), which sits just beyond the pad tips (pads: z 0.150-0.184).
- **Why friction 1.0:** typical for rubber on a smooth object. The real pad material is unknown; revisit when the real gripper is available.
- **Also found:** the finger pads were bound to a physics material prim that is not in the file, so they had PhysX's default friction. Fixed by `bind_pad_friction()`; validator check 8 guards it.

## D11 — Pin Doosan's `jazzy` branch; ROS 2 is Jazzy (2026-10-18)
- **What:** `third_party/doosan-robot2` is pinned to branch `jazzy`, commit `e5e2d7f4fe11865b9ddf4ad658362bc8e73296e0`. `third_party/dh_ag95_gripper_ros2` stays on `humble` (`fc4f80f...`): that repo has no Jazzy branch, and we only use its description xacro, which does not depend on the ROS distro.
- **Why:** the target stack is ROS 2 Jazzy (Isaac Sim ships a `jazzy` ROS 2 bridge). I first pinned `humble` by mistake. Checked: ignoring line endings, `a0509.urdf` and the arm meshes are IDENTICAL on both branches, so nothing built so far changes. The driver, ros2_control plugins and emulator version do differ, and those matter in Phase 9.
- **Watch out:** Isaac Lab's `docker/Dockerfile.ros2` installs `ros-humble-*` on Ubuntu 22.04 (`jammy`). Not usable for a Jazzy stack as it stands.

## D12 — Converting a URDF with <mimic> joints in Isaac Lab: pass convert_mimic_joints_to_normal_joints=True (2026-10-18)
- **What:** `tools/urdf_to_usda.py --mimic` converts the URDF to ONE flattened `.usda` and keeps the five gripper mimic joints.
- **Why:** `UrdfConverterCfg.convert_mimic_joints_to_normal_joints` (default False, documented as "convert mimic joints to normal joints") is passed straight to the importer's `set_parse_mimic(...)` (`urdf_converter.py` ~L150). So the default tells the importer NOT to parse `<mimic>`: the followers silently become ordinary PD-driven joints. Measured: default conversion -> 0 mimic joints, followers with stiffness 1.745 and the URDF's own limits; `True` -> 5 mimic joints. `scripts/tools/convert_urdf.py` does not expose the flag, so the CLI always drops mimic joints.
- **Evidence it is then the same robot as the reference asset:** with the flag, all five followers match the reference asset exactly: reference `left_outer_knuckle_joint`, **gearing -1.0**, offset 0, limits (-10.657, 63.942) deg. The URDF multiplier +1 becomes PhysX gearing -1 because PhysX defines a mimic as `follower + gearing * reference = 0` (so gearing -1 means "same angle"). Total body mass is identical in both (22.283 kg) and both use convexHull colliders.
- **Flatten:** `stage.Flatten()` composes layers/references/payloads into one layer. Use `make_instanceable=False` for a clean single file; flattening instanceable prototypes is what leaves dangling `Looks/material_*` bindings in a single file.

## D13 — Reach task design for the A0509 + AG95 (2026-10-18)
- **Asset:** the composed asset (option A, chosen by Pranav), tracked body `ag95_base_link`; the fingertip point `grasp_link` is only a frame there (no rigid body), 0.19 m further along the approach axis.
- **Four changes from the UR10 template** (`tasks/reach/reach_env_cfg.py`): (1) actions, observations and the joint-velocity penalty restricted to `joint_[1-6]` (we have 12 joints; six are gripper joints); (2) joint reset by **offset** (+-0.3 rad), not by scale, because joint_1/2/4/6 default to 0 and 0 x anything = 0; (3) tracked body and target ranges: x 0.35-0.60, y +-0.20, z 0.25-0.50 for the BASE link, so the fingertips (0.19 m lower when pointing down) stay above the table; (4) orientation: gripper-down is roll=pi, pitch=0 (measured at the start pose: roll=pi, pitch=0, yaw=pi, approach axis (0,0,-1)); only yaw is free, and since a two-finger gripper is symmetric under 180 deg the yaw range is half a circle around the start: (pi/2, 3pi/2).
- **Time step:** sim dt 1/120 with decimation 4 keeps the template's 30 Hz policy rate, and keeps physics at the 120 Hz the mimic gripper was validated at (the template uses dt 1/60, decimation 2).
- **Pitfall found:** one `SceneEntityCfg` object shared by several terms fails on the second use ("joint_names and joint_ids are not consistent"), because Isaac Lab resolves these objects in place. Use a fresh object per term (`arm_joints()`).
- **Launching:** `scripts/train.py` / `play.py` read Isaac Lab's rsl_rl scripts and replace the template marker comment with `import doosan_lab.tasks`, so there is no copy to keep in sync.
- **Cost:** 1024 envs = 0.61 s/iteration, peak 3.1 GB GPU memory; 1500 iterations ~ 15 min.

## D14 — Evaluate checkpoints, don't trust "latest"; reach baseline = model_450 (2026-10-18)
- **Protocol:** `scripts/eval_reach.py` runs the policy's MEAN action (deterministic, what you deploy) on 1024 envs x 6 targets and measures the last second of each 4 s target: position/orientation error, tremble, joint speed. The first version of the script was wrong in two ways, both found by checking one number against another: (1) tensors created under `torch.inference_mode()` cannot be updated outside it (put the reset inside too); (2) the env resets on the last step of every 360-step episode, and that jump landed inside the measurement window (7.1 mm -> 4.7 mm, tremble 13.4 -> 0.00 mm once skipped).
- **Finding:** PPO training is not monotonic. Mean-action error by checkpoint: it100 10.4 mm, 200 6.6, 300 5.2, **450 4.5**, 600 4.6, 650 6.1, 700 9.8. The training curves agree (position error flat ~0.0093 from 300 to 650, then 0.0124 at 700; mean action std grew back 0.115 -> 0.126; reward 0.871 -> 0.804; adaptive learning rate swung 5e-5..3.9e-4). Likely causes (not yet tested): KL-adaptive learning-rate schedule, no observation normalization, small batch. Plateau from ~300; nothing gained after ~450.
- **Decision:** the Phase 2 baseline policy is `model_450` (copied to `outputs/reach_run1/`). Gate 2.2 passes on it: 4.5 mm and 0.033 rad on the mean. Single worst targets exceed 20 mm / 0.1 rad (31 mm / 0.162 rad): the gate is on the mean. Hard targets are the far/high corner of the range (x=0.60, y=+-0.2, z=0.50): mean error by third rises from 8.7 to 12.2 mm in x and 8.6 to 11.9 mm in z.
- **Vibration after reaching:** exploration noise, not the policy. Mean action: 0.00 mm tremble, 0.0001 rad/s; sampled action (training): 6.9 mm, 0.52 rad/s. Training adds Gaussian noise (std 0.13 x action scale 0.5 ~ 4 deg of target jitter per joint per step); deployment and play.py use the mean.

## D15 — Isaac Lab 3.0.0 / Isaac Sim 6.2.0 in a prebuilt container, side by side with 2.3.2 (APPROVED by Pranav 2026-11-14; proposed 2026-11-07)
- **What:** Isaac Lab **3.0.0** (tag `v3.0.0`, commit `e3f7d9ff`, 2026-10-19) on Isaac Sim **6.2.0** (Kit 110.4.0), run from NVIDIA's prebuilt image **`nvcr.io/nvidia/isaac-lab:3.0.0`** under our own Compose project `isaaclab3` (container `isaac-lab-3`, file `docker/isaaclab3.compose.yaml`). Nothing is installed on the host. The `isaac-lab-base` container and image (2.3.2 / 5.1.0) stay untouched as the fallback and the source of the baseline numbers until D16.
- **Stack inside the image** (from the `v3.0.0` `pyproject.toml` and `Dockerfile.base`): Python 3.12, torch 2.11.0 + CUDA 13.0, Warp 1.17.0, Newton 1.6.1, rsl-rl-lib 5.5.1 (2.3.2 pinned 5.0.1), uv 0.12.9; packages in a venv at `/opt/isaaclab-venv`; runs as uid/gid 1000 (same uid as the host user, so the repo bind mount is writable).
- **Requirements checked against this machine:**

  | | Required / published | This machine |
  |---|---|---|
  | NVIDIA driver | ≥ 580.65.06 (Isaac Lab install docs); Kit validated on R580 580.95.05 and R595 595.58.03; Isaac Sim 6.2 "tested" on 595.58.03 | 580.178.04: OK (R580, newer than 580.95.05) |
  | OS | Ubuntu 22.04+ (22.04 deprecated in Isaac Sim 6.2) | 24.04: OK |
  | Isaac Sim min spec | 32 GB RAM, RTX 4080 16 GB VRAM | 30 GB RAM, 12 GB VRAM: **below**; measured in M.1 |
  | Docker / toolkit | Engine ≥ 26.0, Compose ≥ 2.25, NVIDIA Container Toolkit | 29.8.1, 5.5.1, 1.20.0: OK |
- **Size (measured from registry manifests, no pull):** the amd64 image is 16.7 GB compressed; 10.65 GB of that is the `isaac-sim:6.2.0` base. On disk: about 45–50 GB (estimate: Isaac Sim 6.x layers expand about 3x; UNVERIFIED until the pull). Allow about 65 GB free during the pull. Free disk: 288 GB.
- **Why this route:**
  - It installs the least: one `docker pull`, with no host Python, uv or Kit, and no image build.
  - A Kit process that hangs during GPU startup can be removed with `docker kill`; on the host it can't be killed.
  - The image is the published 3.0.0 build, so it matches the `v3.0.0` checkout we read for APIs.
- **Two hazards, and how this route avoids them:** Isaac Lab's `docker/container.py` names the image and the container `isaac-lab-base`, and runs Compose from a folder called `docker`. In both checkouts that gives the same Compose project (`docker`) and the same `docker_*` volume names. So running 3.0's `container.py` without care would (1) recreate our 2.3.2 container from the new image, and (2) on `stop`, run `docker compose down --volumes`, which deletes the shared volumes, including the 2.3.2 training logs. Our compose file therefore sets `name: isaaclab3` and `container_name: isaac-lab-3`, and bind-mounts the training logs to a host folder.
- **Alternatives considered:**
  - **Build the image from `release/3.0.0`** (`COMPOSE_PROJECT_NAME=isaaclab3 ./docker/container.py start base --suffix 3`): pulls `isaac-sim:6.2.0` (10.65 GB compressed) and builds the venv locally. It picks up the 5 commits after the tag (a camera-pose fix with PhysX Fabric, a joint-friction write fix), but the build takes longer and is one more thing to maintain. It's the fallback if the camera fix matters in Phase 3.
  - **Host install with uv** (Isaac Lab's recommended route): `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv run --extra isaacsim isaaclab ...` inside `~/pranav_ws/IsaacLab3`. It installs uv in `~/.local/bin`, plus a project `.venv` and `~/.cache/uv` (size UNVERIFIED, likely 20–30 GB with Isaac Sim). Kit would run on the host. Rejected: Pranav asked to install nothing that isn't needed.
  - **Kit-less image** `nvcr.io/nvidia/isaac-lab:3.0.0-kitless` (5.9 GB compressed): Newton and OV PhysX only. It has no Isaac Sim PhysX, so it can't reproduce the 2.3.2 baselines, and no Kit GUI or Kit cameras. Not needed, because the full image also contains Newton.
  - **Any other Isaac Sim version**: the 3.0.0 pins say `isaacsim==6.2.0.0`, and the install docs say "Isaac Sim 5.1 and older are unsupported".
- **Docs warning:** the web migration guide at `.../IsaacLab/main/...` documents the development branch, not 3.0.0. It says `isaaclab.sh` and `--headless` are removed, but in 3.0.0 `isaaclab.sh` still exists (it is deprecated, prints a warning, and is removed in 3.1) and `--headless` still works. Use the `v3.0.0` docs (`https://isaac-sim.github.io/IsaacLab/v3.0.0/`) or `~/pranav_ws/IsaacLab3/docs/`.
- **Open:** (1) pull and run the image (pulled 2026-11-14); (2) done 2026-11-14: `~/pranav_ws/IsaacLab3` is at `v3.0.0`, matching the image; (3) after the pull, confirm the NGC image carries the `rsl-rl` and `mimic` extras (`Dockerfile.base` installs them, but whether the NGC build used the same extras is UNVERIFIED).

## D16 — Move the project to Isaac Lab 3.0 / Isaac Sim 6.2 (DRAFT: evidence so far, 2026-11-14; decided at M.7)
- **Status:** not decided. This collects what M.3–M.6 found so far; the decision and the final diff table are written at M.7.
- **Gates reproduced on 3.0 (PhysX, composed asset, same numbers as 2.3.2):** grasp 20/20 at about 100 N (`test_gripper.py`); hold, step (settles 0.35 s, 0.0015 rad overshoot) and gripper mimic (`spawn_robot.py`); pad parallelism and 9.5 N per N m (`measure_gripper.py`); joint sweep (`sweep_joints.py`); asset validator 12/12. The 2.3.2 reach checkpoint `model_450` gives 4.6 mm / 0.034 rad (2.3.2: 4.5 / 0.033) once the quaternion order is fixed (next item).
- **Silent break: quaternions are now (x, y, z, w).** The reach policy observes the commanded pose, so a 2.3.2 checkpoint on 3.0 sees a permuted target orientation: 75.9 mm / 1.86 rad (gate FAIL), with no error or warning. Reordering observation columns 15:19 (`eval_reach.py --legacy_quat_obs`) restores it. A policy trained on 3.0 learns the new order. Hand-built quaternions in scripts must change too (`test_gripper.py` cube yaw).
- **Spawning gotcha:** spawning with a regex parent such as `/World/envs/env_.*/Robot` matches prims spawned earlier, so each spawn nests inside the previous one (the robot ended up under the cube). Symptoms: "Expected 1 prims, found 101" and a PhysX patch-buffer overflow. Spawn into concrete per-env paths, then bind the asset class with `spawn=None` (`test_gripper.py`).
- **URDF importer 3.0:** `convert_mimic_joints_to_normal_joints` is "no longer supported" (D12's workaround is obsolete), but the mimic joints are kept, written as `NewtonMimicAPI` / `newton:mimicJoint`. PhysX reads that schema (Isaac Sim 6.2's PhysX schema plugin defines `NewtonMimicAPI`), so the gripper gate and the 20/20 grasp pass on the URDF-built asset. Differences from the composed asset: floating base (`fix_base=True` is not honoured), 17 bodies instead of 19, no 4.5 mm link_6-to-gripper offset. Link positions agree to 0.5 mm.
- **Actuators and schemas:** `effort_limit_sim` / `velocity_limit_sim` became `joint_effort_limit` / `joint_velocity_limit` (aliases removed in 3.1); `RigidBodyPropertiesCfg` / `ArticulationRootPropertiesCfg` became `PhysxRigidBodyCfg` / `PhysxArticulationCfg` fragments, and `CollisionPropertiesCfg` / `MassPropertiesCfg` became `UsdPhysicsCollisionCfg` / `MassCfg` (old ones removed in 3.2). Values unchanged; behaviour identical in every gate above.
- **Reach MDP pinned to 2.3.2:** 3.0's reach base task ends on success, adds a +10 success reward and an action penalty, and defaults to Newton. `A0509ReachEnvCfg` removes those and selects PhysX, so results stay comparable (`reach_env_cfg.py`).
- **IK-Rel reach (Phase 2.3):** 3.0 ships no IK-Rel reach for RL. With random exploration the arm thrashes (joint speed up to 370 rad/s against a pi limit) and PPO without observation normalization went NaN within about 20 iterations, at action scale 0.5 and 0.05 alike; the environment itself stayed finite for 3000 random steps. With normalization on, 30 iterations ran clean. The IK-Rel runner config therefore turns it on; the joint-position run did not have it, so that comparison is not strictly like-for-like.
- **Still open for M.7:** retrain one reach run on 3.0 and compare with 2.3.2 (M.6); Newton probe (M.5); fix the floating base in the URDF build; remaining deprecations from our code: `set_joint_position_target_index` (3.0's own tutorials still use it); framework-internal warnings are not ours.

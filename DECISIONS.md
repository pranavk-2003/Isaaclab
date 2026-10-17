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

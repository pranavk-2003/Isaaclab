# Doosan A0509 + AG95 — Isaac Lab learning plan

**Companion:** `COOKBOOK.md` is the learning guide (concepts, reading, checklists); this file is the step-by-step spec with gates. **Pranav runs every command and writes all the code; the agent monitors, verifies and teaches (§0).**

**Goal:** learn the NVIDIA physical-AI stack (Isaac Lab → RL → teleop/Mimic → imitation/VLA → Cosmos → GR00T) end to end on **one** robot: the Doosan A0509 with a DH Robotics AG95 gripper. A real A0509 will be available later for sim-to-real.

**Milestones:** Phase 5 ends with a working VLA (SmolVLA) in sim, plus write-up #1. Phase 6 adds a working VLM (Cosmos Reason), plus write-up #2. Those two phases need **no big GPU**. GR00T (Phase 7) is the upgrade once a big GPU is available.

Written 2026-10-17 against **Isaac Lab 2.3.2 / Isaac Sim 5.1.0** (docker image `isaac-lab-base`), RTX 4070 SUPER 12 GB, 30 GB RAM, 16 cores.

---

## 0. How to use this plan — **Pranav drives, the agent is the companion**

> **Update 2026-10-18:** the working mode is now *pair programming*: the agent drafts each file one small step at a time, explains it, and Pranav reviews and decides before the next step (see `CLAUDE.md`). Where this section says Pranav writes all the code, read it as "Pranav reviews and understands all of it".

**The user (Pranav) runs every command and writes every line of code.** The agent does not build things for the user. Its job is to guide, watch, check and teach. Read the steps below as *"what Pranav does, with the agent alongside"*.

### What the agent DOES
- **Before a step:** explain what the step is for (link the matching COOKBOOK chapter), and give the exact command(s) to run, one at a time, each in its own code block. Say what output to expect and how long it takes.
- **While a step runs, monitor it, read-only:**
  - read the user's terminal (the terminal-reading tool, if available)
  - tail logs (`docker exec isaac-lab-base tail ...`)
  - check `nvidia-smi`, `docker ps`, TensorBoard event files, generated files
  - grep the Isaac Lab source to check APIs
  - report what it sees: progress, anomalies, VRAM, error causes
- **After a step:** check the gate against the real output and tell the user PASS/FAIL with the evidence. Then *suggest* the `PROGRESS.md` line, the commit message and the notes for the user to write.
- **When the user writes code:** review it, catch bugs, point to the Isaac Lab reference (file:line), and explain *why*. Give hints first. Give full solutions only if the user asks or has been stuck for a while.
- **When something fails:** diagnose from logs and source, explain the cause, and propose the fix as a command or diff for the user to apply.

### What the agent DOES NOT do (unless the user explicitly says so for that specific action)
- It doesn't run commands that change state: no training, installs, container start/stop, file creation, git commits, or `docker cp`.
- It doesn't write or edit files in this repo (code, configs, PROGRESS/notes/DECISIONS). It proposes the content and the user writes it.
- It doesn't skip ahead, and it doesn't do a step "quickly" to save time. The doing *is* the learning.
- A one-off "you do it" from the user applies to **that action only**, not to the rest of the session.

### Ground rules for both
1. **One step at a time, in order.** Every step has a **Gate**. Don't start the next step until the current gate passes and is logged in `PROGRESS.md` with real numbers or output.
2. **Verify APIs against the local source, not memory.** Isaac Lab changes quickly. Before using any class or function, grep `~/pranav_ws/IsaacLab/source` for it. The reference files named in each step are the source of truth.
3. **Never edit `~/pranav_ws/IsaacLab/` or the original reference USDs** (copy them into `assets/`, nothing else). All code goes in `Isaac_lab_learnings/`, no exceptions. The container mount uses an override file in *this* repo.
4. **If a gate fails 3 times in a row, pause.** Write down what was tried in `PROGRESS.md`, step back, and re-read the concept. Don't paper over it by relaxing the gate.
5. **Teach, don't just do.** After each phase, the user writes `notes/NN_<phase>.md` (what was built, key concepts with file:line pointers, what went wrong, the numbers). The agent reviews it and asks the COOKBOOK self-check questions.
6. **Commit after every passed gate** (`git commit -m "P<phase>.<step>: <what> — gate passed"`).
7. **Check versions when a phase starts.** For Phases 5–8, the agent looks up the *current* SmolVLA / Cosmos Reason / GR00T release (context7 or web search; read-only) and tells the user. Don't trust model names in this file. Record the choice in `DECISIONS.md`.
8. **Record every non-obvious choice in `DECISIONS.md`** (one entry per decision: what, why, alternatives).

Throughout the plan, "write X", "run Y" and "create Z" are **instructions for the user**. 👤 marks steps that need the user's eyes in the GUI, or teleop.

### Command conventions

```bash
# Run anything inside the container (from host):
docker exec -it isaac-lab-base bash -lc 'cd /workspace/isaaclab && ./isaaclab.sh -p <script> <args>'
# Paths inside container:
#   Isaac Lab:        /workspace/isaaclab
#   This repo:        /workspace/learnings        (after Phase 0)
#   Training logs:    /workspace/isaaclab/logs    (docker volume, NOT on host — copy out with `docker cp`)
```

- Train **headless** (`--headless`). Open the GUI only for visual gates (and add `--enable_cameras` whenever a camera is in the scene).
- Start every new task with `--num_envs 1024`. Raise it only after a smoke run shows VRAM headroom (`nvidia-smi` on the host).
- **Known-good baseline** (2026-10-17): `Isaac-Reach-Franka-v0`, 1024 envs, 100 iterations, 0.19 s/iteration, position error 0.26 → 0.13 m. If this breaks, the environment is broken, not your code.

---

## Phase 0 — Workspace and container (≈ 0.5 day)

### 0.1 Repo skeleton
Create this structure in `~/pranav_ws/Isaac_lab_learnings/` and `git init`:

```
Isaac_lab_learnings/
├── PLAN.md  CLAUDE.md  PROGRESS.md  DECISIONS.md  COOKBOOK.md
├── docker/learnings.override.yaml
├── scripts/setup_container.sh         # idempotent: pip installs inside the container
├── third_party/                       # vendored robot descriptions (gitignored, pinned commits)
├── assets/                            # generated URDF/USD (gitignored except build scripts)
├── tools/                             # asset build scripts
├── source/doosan_lab/                 # pip-installable Isaac Lab extension
│   ├── pyproject.toml                 # name = "doosan_lab"
│   └── doosan_lab/
│       ├── __init__.py                # imports tasks so gym registrations run
│       ├── assets/doosan.py           # ArticulationCfg(s)
│       └── tasks/{reach,lift,stack}/  # one package per task
├── scripts/                           # test / train / eval scripts of our own
└── notes/                             # per-phase learning notes
```
`.gitignore`: `third_party/`, `assets/**/*.usd*`, `assets/**/*.urdf` (keep the scripts that generate them), `outputs/`, `*.hdf5`, `wandb/`, `__pycache__/`.

**Why hand-write the extension and not use `isaaclab.sh --new`?** The template generator is an interactive TUI (InquirerPy) that an agent can't drive. Copy the layout from `IsaacLab/tools/template/templates/` (`external/` + `extension/`) by hand instead.

**Gate:** `git log` shows the first commit, and the tree matches the structure above.

### 0.2 Mount the repo into the container (without editing Isaac Lab)
`docker/learnings.override.yaml`:
```yaml
services:
  isaac-lab-base:
    volumes:
      - type: bind
        source: ~/pranav_ws/Isaac_lab_learnings
        target: /workspace/learnings
```
Recreate the container with the override. `container.py` supports `--files`. `stop` removes the container, but the logs/data volumes survive.
```bash
cd ~/pranav_ws/IsaacLab
./docker/container.sh stop base
./docker/container.sh start base --files ~/pranav_ws/Isaac_lab_learnings/docker/learnings.override.yaml
```
X11 forwarding is already enabled in `docker/.container.cfg`.
**From now on, always start the container with the `--files` flag.** Put that command in `scripts/start_container.sh`.

**Gate:** `docker exec isaac-lab-base ls /workspace/learnings/PLAN.md` succeeds.

### 0.3 Container setup script
Anything pip-installed into the container is **lost when the container is recreated**. So `scripts/setup_container.sh`, run inside the container, must be idempotent and do this:
```bash
cd /workspace/isaaclab
./isaaclab.sh -p -m pip install -q xacro
./isaaclab.sh -p -m pip install -q -e /workspace/learnings/source/doosan_lab
```
Note: `python -m xacro` does NOT work with this pip package. Call it like this:
`./isaaclab.sh -p -c "import sys,xacro; sys.argv=['xacro','IN.xacro','-o','OUT.urdf']; xacro.main()"` (verified 2026-10-17).

**Gate:** `./isaaclab.sh -p -c "import doosan_lab, xacro; print('ok')"` prints `ok`.

### 0.4 👤 GUI check
Run `scripts/tutorials/00_sim/create_empty.py` **without** `--headless`. **Gate:** the user confirms an Isaac Sim window opens on the desktop. If it doesn't, fix X11 first (try `xhost +local:` on the host). Every visual gate later depends on this.

---

## Phase 1 — The A0509 + AG95 digital twin (≈ 3–5 days)

**Learn first** (user reads, ~1–2 h, see COOKBOOK ch.1):
- `IsaacLab/docs/source/how-to/import_new_asset.rst`, `tutorials/01_assets/add_new_robot.rst`, `run_articulation.rst`, `overview/core-concepts/actuators.rst`
- `IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/universal_robots.py` in full. Its `UR10e_ROBOTIQ_2F_85_CFG` (arm + mimic-joint gripper with driven/passive actuator groups) is the model for our config.

**Strategy (decided 2026-10-17, see D2):**
- **1A is the critical path:** use existing A0509 and AG95 USD files (the *reference USDs*; not included in this repo). **1B is the learning exercise:** build the same robot from the public URDFs and compare.
- **The reference USDs are read-only.** Only copy them; never edit the originals.

### 1.1 Copy the reference assets (read-only source)
Copy the A0509 and AG95 USD folders into `assets/a0509/` and `assets/ag95/` (git-ignored). Record where they came from in
`assets/SOURCE.md`. Copy **only** those two folders.

What to check in them:
- `a0509/a0509.usda`: the default prim and up axis; the link names; whether `root_joint` is a fixed joint carrying
  `PhysicsArticulationRootAPI` (fixed base); joint limits, which USD stores in **degrees**; any rigid body with a tiny
  mass (a first suspect if the solver jitters).
- `ag95/ag95.usda`: it should have **no articulation root**, since it is meant to be attached to an arm. One driven joint,
  `left_outer_knuckle_joint`; the other five follow it through `PhysxMimicJointAPI`, which replaces the 4-bar loop
  closure (the same approach as Isaac Sim's Robotiq 2F-85). `ag95_base_link/grasp_link` is the TCP frame.
- If the folders contain ROS 2 OmniGraph control layers, keep them unreferenced: Isaac Lab drives the joints directly,
  and ROS graphs would fight it.

**Gate:** both folders are copied, `assets/SOURCE.md` is written, and the originals are unchanged.

### 1.2 Compose `a0509_ag95.usda` with a script: `tools/compose_a0509_ag95.py`
This is the USD composition lesson. Use `pxr` (run it with `./isaaclab.sh -p`).
1. Create a new stage with `defaultPrim = "Robot"`, up axis Z, metersPerUnit 1.
2. Under `/Robot`, **reference** `assets/a0509/a0509.usda` (prim path `/World/a0509`) and `assets/ag95/ag95.usda` (prim path `/World/ag95`). Don't flatten-copy.
3. Remove or deactivate the gripper's own fixed `gripper_base_joint` if it points at a non-existent parent. Add a `PhysicsFixedJoint` from `a0509/link_6` (or `tool0`; check which one the flange actually is, see the note below) to `ag95/ag95_base_link`.
4. Make sure there is exactly **one** articulation root (the arm's `root_joint`) and that the gripper bodies join that articulation.
5. Rewrite the mimic `referenceJoint` relationships if the referenced paths changed (they point at `/World/ag95/joints/...`).
6. Save to `assets/a0509_ag95/a0509_ag95.usda`.

**Flange note:**
- In the Doosan URDF, the `joint_6` axis is link_6 **+Z**, so the flange normal is link_6 +Z.
- Check whether `tool0` in the USD carries an extra rotation before attaching to it.
- So attach to `link_6` with an identity offset *unless* the GUI check shows otherwise. Record the final transform in `DECISIONS.md`.

**Gate:**
- `pxr` validation: the script prints the articulation root count (= 1), the movable joint count (6 arm + 6 gripper revolute), and the mimic joint count (= 5). All mimic `referenceJoint` targets resolve.
- 👤 Opened in Isaac Sim, then Play: the robot stands still, and the gripper is flush on the flange, pointing along the flange normal.

### 1.3 `ArticulationCfg`: `doosan_lab/assets/doosan.py` → `DOOSAN_A0509_AG95_CFG`
Copy the structure of `UR10e_ROBOTIQ_2F_85_CFG`:
- `spawn = sim_utils.UsdFileCfg(usd_path=<composed usda>, activate_contact_sensors=True, rigid_props=..., articulation_props=ArticulationRootPropertiesCfg(enabled_self_collisions=False, solver_position_iteration_count=16+, solver_velocity_iteration_count=1))`.
- `init_state.joint_pos`: a "ready" pose clear of singularities, with the gripper pointing down. Start from `joint_1=0, joint_2=0, joint_3=1.57, joint_4=0, joint_5=1.57, joint_6=0` → **check in the GUI** and adjust. Isaac Lab uses **radians**, even though the USD limits are in degrees.
- Actuators (`ImplicitActuatorCfg`):
  - `shoulder` = `joint_[1-3]`: effort 194/194/163 N·m, velocity 3.1416 rad/s, stiffness ≈ 800–1000, damping ≈ 40–80.
  - `wrist` = `joint_[4-6]`: effort 50, velocity 6.2832, stiffness ≈ 400, damping ≈ 20–40.
  - `gripper_drive` = `left_outer_knuckle_joint`.
  - `gripper_passive` = the 5 mimic joints: stiffness 0, damping ≈ 0, so the mimic constraint does the work (same pattern as the UR10e+2F-85 cfg). **Verify** that Isaac Lab doesn't override the mimic behaviour with drive gains.
- Also export `DOOSAN_A0509_AG95_HIGH_PD_CFG` (gravity off, stiffer gains) for IK tasks, like Franka's `FRANKA_PANDA_HIGH_PD_CFG`.

**Gate:**
- `scripts/spawn_robot.py` spawns 4 robots, holds the init pose for 10 s, and reports max arm joint error < 0.01 rad.
- It prints `robot.data.joint_names` and `body_names` (log them).

### 1.4 Gripper verification test: `scripts/test_gripper.py`
The user expects the AG95 asset to work, and the mimic setup looks right. This test **proves** it and gives us numbers.

The test:
1. Open and close 10 times.
2. Then spawn a 4 cm, 50 g cube between the fingers, close, lift the arm 0.2 m, and hold for 5 s.

Measure:
- whether any NaN or explosion occurs (joint velocity > 50 rad/s)
- whether the finger pads stay parallel (angle between pad normals < 5°)
- whether the cube is still held after 5 s
- opening width at open and at closed (should be ≈ 95 mm → 0)

**Gate:** ≥ 19/20 holds with no NaN. Log the numbers in `PROGRESS.md`.

**If it fails:**
- First tune `gripper_drive` stiffness/effort and the pad friction (physics material on the finger pads, static/dynamic friction ≈ 1.0).
- Then try the mimic `naturalFrequency`/`dampingRatio`.
- Ask the user before considering any simplified-gripper fallback.

### 1.5 Joint sweep and sanity
`scripts/sweep_joints.py` moves each arm joint through ±80 % of its range, one at a time, in the GUI.

**Gate:**
- 👤 no glitches, and every joint's direction matches its name.
- Log the TCP (`grasp_link`) position at the init pose.

### 1.6 Learning exercise: build it yourself from URDF and compare
Not on the critical path, but **do it**. This is where you learn what a ready-made asset hides from you. Timebox: 1–2 days.
1. Vendor the URDFs, pinned:
   - `git clone https://github.com/DoosanRobotics/doosan-robot2.git` @ `e5e2d7f4fe11865b9ddf4ad658362bc8e73296e0` (branch `jazzy`)
   - `git clone https://github.com/ian-chuang/dh_ag95_gripper_ros2.git` @ `fc4f80fdfb3acae5626df4359aec1401cb71a9a3`
   - put both in `third_party/`
2. Write `tools/build_urdf.py`:
   - The arm URDF is `dsr_description2/urdf/a0509.urdf` (plain URDF). **Its `tool0` link is commented out**, so attach to `link_6`.
   - Expand the AG95 macro: copy `dh_ag95_macro.xacro`, write a top xacro that includes it by relative path, and call `dh_ag95_gripper prefix="" parent="link_6"`. Don't use `dh_ag95.urdf.xacro`, since it needs ros2_control and `$(find)`.
   - Run xacro via `./isaaclab.sh -p -c "import sys,xacro; sys.argv=['xacro','IN','-o','OUT']; xacro.main()"` (`python -m xacro` doesn't work).
   - Merge the two URDFs, drop `<gazebo>`/`<transmission>`/`<ros2_control>`, and rewrite `package://` to absolute container paths.
3. Convert: `scripts/tools/convert_urdf.py IN.urdf OUT.usd --fix-base --headless`. Don't use `--merge-joints`.
4. Write `scripts/compare_assets.py` to diff your USD against the reference one: joint names, axes, limits (degrees vs radians!), link masses and inertias, mimic gearing and sign, drive gains, collision approximations.

**Facts:** the URDF has 5 `<mimic>` tags (multiplier **+1**), but the PhysX mimic joints in the USD use gearing **−1**. Find out why: PhysX mimic sign convention vs. URDF convention. The 2 loop-closing joints exist only as `<gazebo>` fragments and get dropped.

**Gate:** `notes/01b_urdf_vs_source.md` with the comparison table and the 3 most surprising differences.

Then write `notes/01_assets.md`: USD composition (references, defaultPrim), articulation roots, implicit vs explicit actuators, mimic joints, units.

---

## Phase 2 — Reach with RL (≈ 2–3 days)

**Learn first:** Isaac Lab docs → "Manager-based environments" and the `reach` tutorial. Read:
- `isaaclab_tasks/manager_based/manipulation/reach/reach_env_cfg.py` (the full MDP)
- `.../reach/config/ur_10/joint_pos_env_cfg.py` (a robot-specific override — copy this pattern)
- `.../deploy/reach/config/ur_10e/` (NVIDIA's **sim-to-real-minded** version: compare its observations, noise and action scaling with the plain one. This will matter for the real A0509.)

### 2.1 Task `doosan_lab/tasks/reach/`
- Subclass `ReachEnvCfg`. Robot = `DOOSAN_A0509_AG95_CFG`.
- End-effector body: use `grasp_link` if it appears in `robot.data.body_names`. Otherwise use `ag95_base_link` with a 0.19 m offset along +Z. **Print `body_names` once and log it.**
- Set the command ranges to the A0509's reachable workspace (900 mm reach). Start with a box in front of the robot: x 0.35–0.65, y −0.3–0.3, z 0.15–0.5 m. Orientation: gripper pointing down ± small yaw.
- Register `Doosan-Reach-A0509-v0` and `Doosan-Reach-A0509-Play-v0`. Agent: `rsl_rl` PPO cfg copied from the UR10 reach agent.

### 2.2 Train
```bash
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py --task Doosan-Reach-A0509-v0 --headless --num_envs 1024 --max_iterations 1500
```
`train.py` only finds our task if `doosan_lab` is imported. If registration doesn't happen, add `--external_callback` or a tiny wrapper script that imports `doosan_lab` and then runs `train.py`. Check `train.py`'s args in this version.

**Gate:**
- Final `Metrics/ee_pose/position_error` < **0.02 m** and `orientation_error` < **0.1 rad**.
- 👤 `play.py --task Doosan-Reach-A0509-Play-v0 --video` produces a video where the arm visibly tracks targets.
- Save TensorBoard curves as PNG in `notes/`.

### 2.3 Experiment (the actual learning)
Train a second variant, `Doosan-Reach-A0509-IK-Rel-v0`, with `DifferentialInverseKinematicsActionCfg` (relative pose actions, using the `HIGH_PD` cfg), copying from Franka's `ik_rel_env_cfg.py` in the `lift` config. Compare against joint-position actions:
- sample efficiency (iterations to reach 0.02 m)
- final error
- smoothness

Write the comparison in `notes/02_reach.md`. The IK-Rel variant is the one teleop and Mimic need in Phase 4.

---

## Phase 3 — Lift with RL + wrist camera (≈ 4–7 days)

**Learn first:** `manipulation/lift/lift_env_cfg.py` and `lift/config/franka/joint_pos_env_cfg.py`, `ik_rel_env_cfg.py`. Also read `lift/mdp/rewards.py`: the reward shaping is the lesson here.

### 3.1 Task `doosan_lab/tasks/lift/`
- Subclass `LiftEnvCfg`. Cube 4–5 cm (the AG95 opens 95 mm), spawned randomly on the table in front.
- Gripper action: `BinaryJointPositionActionCfg` on `left_outer_knuckle_joint` (the mimics follow; see 1.4).
- Register `Doosan-Lift-Cube-A0509-v0` (joint pos) and `Doosan-Lift-Cube-A0509-IK-Rel-v0`.

**Gate:**
- Joint-pos variant: success (cube lifted and tracking the goal, read from the metrics/`object_goal_tracking` reward) ≥ **80 %** over 100 eval episodes.
- 👤 Video looks like a real grasp, not the cube being pushed or flicked.

If it's stuck after 3 reward-tuning attempts, stop and ask. Grasp RL is genuinely hard, and that's a finding worth writing down, not a failure.

### 3.2 Cameras
Add a **wrist camera** (`TiledCameraCfg`, RGB 128×128, mounted on `ag95_base_link` looking along +Z) and a **fixed third-person camera** (front-left of the table, RGB 128×128). Expose both as observation terms in a separate `ObservationGroup` called `images`. RL doesn't use it; it's for demo recording.

**Gate:** a script saves 10 frames per camera to `outputs/cam_check/`, and 👤 the user confirms the views make sense. Measure the VRAM cost of cameras at 64 envs and log it.

`notes/03_lift.md`: the reward terms and why each exists, the tuning history, and the camera VRAM cost.

---

## Phase 4 — Teleop demos → Isaac Lab Mimic (≈ 4–6 days)

**Learn first:** Isaac Lab docs → "Teleoperation and Imitation Learning" and the Isaac Lab Mimic overview. Read:
- `source/isaaclab_mimic/isaaclab_mimic/envs/franka_stack_ik_rel_mimic_env_cfg.py` and `franka_stack_ik_rel_mimic_env.py` (copy these)
- `manipulation/stack/config/franka/stack_ik_rel_env_cfg.py` and `stack_ik_rel_visuomotor_env_cfg.py`
- `scripts/tools/record_demos.py`, `scripts/imitation_learning/isaaclab_mimic/{annotate_demos,generate_dataset}.py`

### 4.1 Task: `Doosan-Stack-Cube-A0509-IK-Rel-v0` (+ `-Visuomotor` variant with the 3.2 cameras)
Pick cube A and place it on cube B. That's two subtasks (grasp A, then stack on B), which is the simplest structure Mimic is designed for. Copy the stack env, but use **2 cubes**, not 3. Include the subtask observation terms (`grasp_1`, `stack_1`-style signals) that `annotate_demos.py --auto` needs.

Then create the Mimic env cfg plus a Mimic env class for the A0509 (copy the Franka ones): the end-effector frame, the subtask configs, and the `get_robot_eef_pose` / `target_eef_pose_to_action` / `action_to_target_eef_pose` methods.

**Gate:** a scripted or random rollout runs. The success term fires when the cube is placed correctly by hand (write a small test that teleports cube A onto B and checks the success term).

### 4.2 👤 Record demos
```bash
./isaaclab.sh -p scripts/tools/record_demos.py --task Doosan-Stack-Cube-A0509-IK-Rel-Visuomotor-v0 --teleop_device keyboard --dataset_file /workspace/learnings/datasets/raw.hdf5 --num_demos 15 --enable_cameras
```
A SpaceMouse is much easier than the keyboard, if available. The user records about 15 successful demos. **Prepare a one-page key cheat sheet first** (read the keyboard device class for the bindings).

**Gate:** `replay_demos.py` replays ≥ 10 successful demos.

### 4.3 Annotate and generate
`annotate_demos.py --auto` → `generate_dataset.py --generation_num_trials 1000` (headless, `--num_envs` as VRAM allows).

**Gate:**
- ≥ **1000 successful** generated demos (log the generation success rate).
- 👤 a spot check of 5 replays looks natural.
- The dataset includes both camera streams.

`notes/04_mimic.md`: how Mimic transforms subtask segments relative to object poses, and why the success rate is what it is.

---

## Phase 5 — Imitation learning: BC baseline → SmolVLA (≈ 1–2 weeks)  ✅ milestone: VLA proof of concept

### 5.1 State-based BC baseline (robomimic)
`scripts/imitation_learning/robomimic/train.py --task <stack IK-Rel task> --algo bc --dataset ...`, then `robust_eval.py` / `play.py`.

**Gate:** ≥ **60 %** success over 50 sim rollouts. This proves the dataset is learnable before moving on to vision.

### 5.2 Convert the dataset to LeRobot format: `tools/hdf5_to_lerobot.py`
GR00T needs this too, so build it carefully.
- Check the current LeRobot dataset version and API.
- Map:
  - state = 6 arm joints + gripper
  - action = the IK-Rel action vector, or joint targets (pick one and record it in `DECISIONS.md`)
  - images = wrist and front cameras
  - task = the language instruction `"stack the red cube on the green cube"`

**Gate:** LeRobot loads the dataset, and one episode's video plus action plot looks right.

### 5.3 Train a VLA locally
Train **SmolVLA** (≈ 450 M params, chosen because it fits in 12 GB). Check the current recommended LeRobot recipe. Use a **separate** Python env or container from Isaac Sim's, to avoid dependency conflicts; e.g. a `lerobot` conda env on the host, or a second container.

**Gate:** the training loss converges, and the checkpoint is saved.

### 5.4 Closed-loop evaluation harness: `scripts/eval_policy_server.py`
The policy runs as a small server (ZMQ or HTTP) in the LeRobot env. Isaac Lab runs the env and sends observations (images + state + instruction), then gets actions back. **Reuse this harness for GR00T** in Phase 7.

**Gate:** ≥ 50 rollouts are logged with a success rate, whatever it turns out to be. That's the **"working VLA POC in sim"**. Record a video.

### 5.5 Write-up #1: "VLA / WAM landscape and what we learned" (2–4 pages)
Cover GR00T N1.x, π0/π0.5, SmolVLA, OpenVLA and world-action models. Include our numbers (BC vs SmolVLA), and what would change on real hardware. Save it to `writeups/01_vla_landscape.md`.

---

## Phase 6 — Cosmos Reason as a VLM in the loop (≈ 3–5 days)  ✅ milestone: write-up #2

### 6.1 Run Cosmos Reason locally
Check the current release (Cosmos-Reason1-7B or newer). It needs **4-bit quantization or vLLM with a small context** to fit in 12 GB, so verify the VRAM use. Use a separate env from Isaac Sim's.

### 6.2 Use it as a success detector
Make MP4s of 50 rollouts with `scripts/tools/hdf5_to_mp4.py` (25 successes, 25 failures, taken from Phase 5 evaluations). Ask Cosmos Reason "Did the robot place the red cube on the green cube? Answer yes/no and explain."

**Gate:** accuracy against the ground-truth success term, reported with a confusion matrix. There's no threshold: it's a study.

### 6.3 Optional: use it as a planner
Give it the front-camera image plus "which cube should be picked first to build a stack ordered by color X?" and send the answer to the policy as the language instruction.

### 6.4 Write-up #2: "Cosmos (Reason / Predict / Transfer): what it is, what it does for us"
Include the 6.2 results. Cover Transfer from reading plus Isaac Lab's existing `franka_stack_ik_rel_visuomotor_cosmos_*` configs and `scripts/tools/cosmos/`. **Don't** run Transfer locally: it needs a big GPU.

---

## Phase 7 — GR00T (needs a big GPU; start when one is available)

1. Check the current Isaac-GR00T release, fine-tuning hardware needs, and the **custom embodiment / modality config** docs.
2. Write the A0509 modality config: state/action keys matching the LeRobot dataset from 5.2, plus the camera keys.
3. Fine-tune on the Phase 4 dataset on the big GPU. Record the GPU type, hours and hyperparameters in `DECISIONS.md`.
4. Run GR00T inference behind the **same** harness as 5.4. Check whether 12 GB is enough for local inference; if not, run inference on the big GPU too.

**Gate:** success rate over ≥ 50 rollouts, compared with SmolVLA and BC in one table, plus a video.

## Phase 8 — Optional extensions (pick by interest)
- **Cosmos Transfer** visual augmentation of the Mimic dataset (needs a big GPU). Does it improve the visuomotor policy under lighting or texture randomization?
- **Domain randomization** of lighting, textures and camera pose (Replicator / event terms), to test policy robustness. Prepares for the real robot.
- **Newton physics backend** (if the installed Isaac Lab version supports it). Compare stability against PhysX on the gripper test from 1.4.

## Phase 9 — Sim-to-real on the real A0509 (when access arrives)

> **ROS distro: Jazzy** (the target stack; use the `isaacsim.ros2.bridge/jazzy` bridge that ships with Isaac Sim). Use Doosan's `jazzy` branch. Isaac Lab's own `docker --profile ros2` installs **Humble on Ubuntu 22.04**: do not use it as-is.
Kept short on purpose, because it depends on the hardware setup at the time.
- Port the `deploy/reach` ideas: observation noise, action limits, actuator randomization.
- Interface: Doosan ROS 2 driver (`doosan-robot2`, `dsr_hardware2`) plus the AG95 ROS 2 driver. The policy node runs at the trained control rate.
- Order: reach (joint targets, slow, with e-stop at hand) → lift → stack.
- Measure the real wrist camera's intrinsics and extrinsics with hand-eye calibration and match them in sim **before** collecting any real data.

**Safety gate (non-negotiable):** first motions run at ≤ 10 % speed, with the workspace limits enforced *outside* the policy, a person on the e-stop, and a dry run with the arm in simulation/emulator mode (`install_emulator.sh` in doosan-robot2).

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| AG95 mimic gripper slips or jitters under grasp load | Low–Medium | Phase 1.4 test; tune drive, friction and mimic params |
| Accidentally modifying the original reference USDs | Low | Copy-only rule; check in gate 1.1 |
| `grasp_link` dropped by importer | Medium | Body offset on `ag95_base_link` (2.1) |
| Grasp RL doesn't converge | Medium | It's a learning finding. Phase 4+ doesn't depend on RL lift: Mimic uses teleop demos |
| VRAM limits with cameras | Medium | Fewer envs, 128×128 (or 84×84) images, cameras only in the visuomotor variants |
| Isaac Sim and LeRobot/Cosmos dependency clashes | High if mixed | Separate envs + policy-server harness (5.4) |
| No big GPU for GR00T | Medium | Phases 5–6 reach a working VLA without one |
| Container recreated → pip installs lost | Certain | `scripts/setup_container.sh` |
| Training logs live in a docker volume | Certain | `docker cp isaac-lab-base:/workspace/isaaclab/logs/... ./outputs/` for anything worth keeping |

## Timeline (part-time, ~1–2 days/week; adjust in PROGRESS.md)
| Target | Milestone |
|---|---|
| End Oct 2026 | Phase 0–1 done (twin + gripper verified) |
| Mid Nov | Phase 2 done (reach) |
| Early Dec | Phase 3–4 done (lift, 1000 Mimic demos) |
| Early Jan 2027 | Phase 5 done → **VLA POC + write-up #1** (target: January 2027) |
| Late Jan | Phase 6 done → **write-up #2** |
| When GPU available | Phase 7 (GR00T) |
| When robot available | Phase 9 |

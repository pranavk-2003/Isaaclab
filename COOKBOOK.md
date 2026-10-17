# The A0509 Cookbook
### Learning the NVIDIA physical-AI stack by building one robot, end to end

> **How this relates to the other files:** `PLAN.md` is the *execution spec* (exact steps and gates, written for an agent). This cookbook is the *human* version: what each thing is, why it exists, what to read, what to build with your own hands, and how to know you've actually understood it. Each chapter maps to a PLAN phase.

**How to work through a chapter**
1. **🧠 Concepts:** read them first. Don't skip them; they're short.
2. **📖 Read:** the listed docs and source files, in order. Paths are relative to `~/pranav_ws/IsaacLab/` unless stated. Read the source, not just the docs: Isaac Lab's real documentation is its code.
3. **🛠 Build:** you type every command and write every file. The agent is your companion: it gives you the next command, watches your terminal and logs while things run, checks gates, reviews your code, and explains failures. It doesn't run anything that changes state unless you ask for that one thing.
4. **✅ Checklist:** tick boxes in this file as you go (`[x]`), and commit.
5. **🧪 Self-check:** answer out loud or in `notes/`. If you can't, re-read before moving on.
6. **⚠️ Pitfalls:** read them *before* you start building.

**Working with the agent:** good prompts:
- *"Start P1.2, what do I run?"*
- *"I've started training, watch it."*
- *"Review `doosan.py`."*
- *"Gate check 2.2."*
- *"Quiz me on Chapter 1."*
- *"Hint only."*

**Legend:** 🔬 = deep-dive (optional but valuable) · 👤 = needs your eyes in the GUI

---

## Chapter 0 — Map of the territory

### 🧠 Concepts: what each piece of the stack is

| Layer | What it is | Where it shows up in this project |
|---|---|---|
| **OpenUSD** | Pixar's scene description format. Everything in Omniverse is a USD *stage*: a tree of *prims* with *properties*, assembled from *layers* via composition (references, payloads, sublayers, variants). | Ch.1: you compose the robot USD yourself. |
| **Omniverse Kit** | The app framework (extensions, UI, the update loop). Isaac Sim is a Kit app. | Every time you launch `isaaclab.sh -p`, Kit boots underneath. |
| **PhysX 5** | NVIDIA's GPU physics engine. Simulates articulations (robots), rigid bodies, contacts, and many envs in parallel on the GPU. | Every chapter. Gripper stability (Ch.1) is a PhysX lesson. |
| **RTX renderer** | Ray-traced rendering for cameras. | Ch.4 cameras; the VRAM cost comes from here. |
| **Isaac Sim** | The robotics simulator built on Kit + PhysX + RTX: importers (URDF/MJCF), sensors, robot assets, ROS bridges. | The engine under Isaac Lab. |
| **Isaac Lab** | A robot-learning framework on top of Isaac Sim: vectorized environments, managers, RL/IL integrations, teleop, Mimic. | Where you'll spend most of your time. |
| **OmniGraph** | Node-graph visual scripting inside Kit (e.g. ROS 2 publishers/subscribers). | ROS 2 control graphs that ship with some robot USDs. We deliberately *don't* load these (Ch.1). |
| **Replicator** | Synthetic data generation: randomize scenes, render, and annotate (segmentation, depth, bounding boxes). | Ch.4 / Phase 8 domain randomization. |
| **Warp** | A Python framework for writing GPU kernels (CUDA without writing CUDA). | Isaac Lab uses it internally. 🔬 Phase 8. |
| **Newton** | A new open-source GPU physics engine built on Warp (NVIDIA, Google DeepMind and Disney Research). Experimental in Isaac Lab. | 🔬 Phase 8: compare against PhysX. See `docs/source/experimental-features/newton-physics-integration/`. |
| **Isaac Lab Mimic** | Turns a few human demos into thousands of synthetic demos. | Ch.5. |
| **LeRobot** | Hugging Face's robot-learning library and dataset format (Parquet + MP4). It's the lingua franca for VLAs. | Ch.6, Ch.8. |
| **Cosmos** | NVIDIA's *world foundation models*: **Predict** (generate future video), **Transfer** (turn sim renders/depth/segmentation into photoreal video), **Reason** (a VLM that reasons about physics and video). | Ch.7. |
| **GR00T N1.x** | NVIDIA's open foundation *VLA* model for robots: language + images + robot state in, actions out. | Ch.8. |

**The data flywheel you're building** (this is the mental model to keep):
```
 asset (USD) ─► env (Isaac Lab) ─► policy via RL ───────────────────────────┐
                     │                                                       │
                     └─► teleop demos ─► Mimic (×100) ─► [Cosmos Transfer] ─► dataset ─► BC / SmolVLA / GR00T ─► eval in sim ─► real robot
                                                                                                  ▲
                                                                     Cosmos Reason judges success ┘
```

### 📖 Read
- `README.md` (Isaac Lab root): the overview.
- `docs/source/overview/core-concepts/task_workflows.rst`: **manager-based vs direct** envs. Remember this distinction.
- `docs/source/overview/environments.rst`: skim the list of built-in tasks to see what's possible.
- `docs/source/deployment/docker.rst`: how your container works.

### 🛠 Build (PLAN Phase 0)
- Repo skeleton, container mount, setup script, GUI check. Follow PLAN 0.1–0.4.
- Run `scripts/tutorials/00_sim/create_empty.py` and `spawn_prims.py` **with the GUI**. Click around the Stage tree on the right: that tree *is* USD.

### ✅ Checklist
- [ ] I can start the container with my repo mounted (`scripts/start_container.sh`)
- [ ] `setup_container.sh` runs cleanly after a fresh container
- [ ] The GUI opens; I ran `spawn_prims.py` and found the spawned prims in the Stage panel
- [ ] I ran a headless training (Franka reach) and found its logs in `/workspace/isaaclab/logs`
- [ ] I opened TensorBoard on those logs (`tensorboard --logdir` inside the container, then open in the host browser; the container uses host networking)

### 🧪 Self-check
1. What's the difference between Isaac Sim and Isaac Lab, in one sentence?
2. Why do training logs disappear from the host unless you copy them? (Hint: `docker-compose.yaml` volumes.)
3. Manager-based vs direct env: when would you choose direct?

### ⚠️ Pitfalls
- Recreating the container wipes pip installs. That's why `setup_container.sh` exists.
- The first launch is slow (shader cache). It isn't hung.

---

## Chapter 1 — USD and the robot asset (PLAN Phase 1)

### 🧠 Concepts
**USD composition.** A stage is built from layers. A *reference* pulls another file's prim tree in under one of your prims *without copying it*; your edits live in your layer as *overrides* ("opinions"). This is how you'll combine the arm and gripper without touching the original files. Stronger layers win: **LIVRPS** (Local, Inherits, VariantSets, References, Payloads, Specializes) is the strength order.

**Physics schemas on prims.** USD is just data until physics *APIs* are applied:
- `PhysicsRigidBodyAPI` + `PhysicsMassAPI`: a link that has mass and moves.
- `PhysicsCollisionAPI`: has collision geometry (often a simplified convex hull, not the visual mesh).
- `PhysicsRevoluteJoint` / `PhysicsFixedJoint`: connect `body0` → `body1` with local frames `localPos0/localRot0` and `localPos1/localRot1`.
- `PhysicsDriveAPI`: a PD controller on a joint (stiffness = P, damping = D, `maxForce` = effort limit).
- **`PhysicsArticulationRootAPI`**: marks a tree of bodies + joints as one *articulation*. PhysX then solves it in *reduced coordinates* (joint space), which is much more stable and accurate for robots than a pile of maximal-coordinate joints. **One robot = one articulation root.** In the A0509 USD it sits on the fixed `root_joint`, which also fixes the base to the world.
- `PhysxMimicJointAPI`: makes one joint follow another (`q_follower = gearing·q_ref + offset`). This is how the AG95's 4-bar linkage (one motor, many joints) is modelled. A URDF can't express kinematic loops, so the loop is replaced by mimic coupling.

**Units.** USD angular joint limits and drive targets are in **degrees**. Isaac Lab APIs use **radians**. This bites everyone once.

**Actuator models in Isaac Lab** (`docs/source/overview/core-concepts/actuators.rst`):
- `ImplicitActuatorCfg`: the PD runs *inside* PhysX (stable, fast, idealized).
- Explicit actuators (`IdealPDActuatorCfg`, `DCMotorCfg`, network-based actuators): Isaac Lab computes torques in Python. These let you model motor saturation, delays and so on. That's crucial for sim-to-real on legged robots, and less so for a position-controlled cobot.
- "Driven" vs "passive" joint groups: on a mimic gripper, only the driver gets gains; the followers get stiffness 0.

**`ArticulationCfg`** is Isaac Lab's Python description of "spawn this USD, start in this joint pose, and drive these joints with these actuators". Everything downstream refers to the robot through it.

### 📖 Read (in order)
1. `docs/source/tutorials/00_sim/spawn_prims.rst`
2. `docs/source/tutorials/01_assets/run_articulation.rst` + `scripts/tutorials/01_assets/run_articulation.py`
3. `docs/source/tutorials/01_assets/add_new_robot.rst` + `scripts/tutorials/01_assets/add_new_robot.py`
4. `docs/source/how-to/import_new_asset.rst`
5. `docs/source/overview/core-concepts/actuators.rst`
6. `source/isaaclab_assets/isaaclab_assets/robots/universal_robots.py`: **read it all.** Look at how `UR10e_ROBOTIQ_2F_85_CFG` splits the gripper into `gripper_drive` / `gripper_finger` / `gripper_passive`.
7. `source/isaaclab/isaaclab/assets/articulation/articulation_cfg.py` and `articulation_data.py`: what you can read back from a robot (`joint_pos`, `body_pos_w`, ...).
8. Open `assets/ag95/ag95.usda` in a text editor (read-only!). Find `left_outer_knuckle_joint` and one mimic joint. You now know what `PhysxMimicJointAPI` looks like in practice.
9. 🔬 OpenUSD "Composition arcs" docs (openusd.org) → references vs payloads.

### 🛠 Build
1. **Copy the reference USDs** (PLAN 1.1). Copy only; never edit the originals.
2. **Compose the robot by script** (PLAN 1.2): a `pxr` script that references arm and gripper and adds a fixed joint `link_6 → ag95_base_link`. Write it yourself. This is *the* USD exercise.
   - Hint: `Usd.Stage.CreateNew`, `prim.GetReferences().AddReference(path, primPath)`, `UsdPhysics.FixedJoint.Define`, `joint.CreateBody0Rel().SetTargets([...])`.
3. Open the result in the GUI, press Play, and look. 👤
4. **Write `DOOSAN_A0509_AG95_CFG`** (PLAN 1.3) by copying the UR10e+2F-85 pattern.
5. **Gripper test** (PLAN 1.4): open/close, grasp a cube, lift, hold.
6. **Joint sweep** (PLAN 1.5).
7. **Build it again from URDF** (PLAN 1.6) and diff it against the reference asset. Write down every difference you find and *why* it exists.

### ✅ Checklist
- [ ] Copied `a0509/` and `ag95/` into `assets/`; the originals are unchanged
- [ ] I can explain every prim under `/World/ag95/joints` in the AG95 usda
- [ ] My compose script produces one articulation root, 5 mimic joints, and a correctly attached gripper 👤
- [ ] `DOOSAN_A0509_AG95_CFG` spawns 4 robots that hold pose (error < 0.01 rad)
- [ ] Gripper test: ≥ 19/20 holds, numbers logged
- [ ] Joint sweep looks right 👤
- [ ] URDF → USD built myself; comparison table in `notes/01b_urdf_vs_source.md`
- [ ] `notes/01_assets.md` written

### 🧪 Self-check
1. Why does a robot need exactly one articulation root? What happens if the gripper ends up in a *second* articulation?
2. The URDF mimic multiplier is +1, but the USD gearing is −1. Why can both be "correct"?
3. Implicit vs explicit actuator: which would you use to model the real A0509's torque limits plus a 4 ms command delay?
4. What does `--merge-joints` do in the URDF converter, and why did we avoid it?
5. Why is a link with mass 1e-6 kg dangerous in a physics solver?

### ⚠️ Pitfalls
- Degrees vs radians (again).
- A gripper with collision meshes overlapping the flange explodes on Play. Check the collisions view (eye icon → Show by type → Physics → Colliders).
- Never load the `graphs/*_control.usda` layers: ROS OmniGraph nodes would try to drive the joints too.
- If the robot sags under gravity, your drive stiffness is too low, or `disable_gravity` is set inconsistently.

---

## Chapter 2 — Isaac Lab environments and your first RL policy (PLAN Phase 2)

### 🧠 Concepts
**An environment = a scene + an MDP.** In manager-based envs you describe the MDP declaratively as config classes, and *managers* execute them each step:

| Manager | Answers the question | Example term |
|---|---|---|
| `SceneCfg` | What exists? | robot, table, cube, lights, sensors |
| `ActionManager` | How does the policy's output move the robot? | `JointPositionActionCfg`, `DifferentialInverseKinematicsActionCfg` |
| `ObservationManager` | What does the policy see? | joint pos/vel, command, last action |
| `RewardManager` | What's good? | `-position_error`, `-action_rate` |
| `TerminationManager` | When does an episode end? | time-out |
| `EventManager` | What gets randomized, and when? | reset joint pos, randomize mass at startup |
| `CommandManager` | What's the goal? | random target pose for the end effector |
| `CurriculumManager` | How does difficulty change over training? | ramp the action-rate penalty |

**Vectorization.** One `env.step()` steps *N* copies at once on the GPU (`--num_envs 1024`). Every tensor has a leading `num_envs` dimension. This is why RL in Isaac Lab is fast.

**Decimation.** The physics `dt` (e.g. 1/120 s) is smaller than the control `dt`. `decimation = 2` means the policy acts at 60 Hz. **Remember this number for the real robot.**

**PPO in one paragraph.** The policy (actor) outputs a Gaussian over actions, and a critic estimates the value. We collect rollouts from all envs, compute advantages (GAE: how much better an action was than expected), and update the actor to increase the probability of good actions, *clipped* so it can't change too much per update. `rsl_rl` is the PPO implementation tuned for Isaac Lab. Watch: mean reward ↑, episode length, the task metrics (position error ↓), and the action noise std (it should shrink as the policy gets confident).

**Action spaces matter.** Joint-position actions: the policy outputs joint offsets (simple and robust). Differential IK actions: the policy outputs an end-effector delta pose and IK maps it to joints. That's more transferable across robots, and it's what teleop and Mimic use.

**Registration.** `gym.register(id="Doosan-Reach-A0509-v0", entry_point="isaaclab.envs:ManagerBasedRLEnv", kwargs={"env_cfg_entry_point": ..., "rsl_rl_cfg_entry_point": ...})`. Scripts find your task by this ID, but only if your package was imported.

### 📖 Read
1. `docs/source/tutorials/03_envs/create_manager_base_env.rst` → `create_manager_rl_env.rst` → `register_rl_env_gym.rst` → `run_rl_training.rst` → `configuring_rl_training.rst`
2. `docs/source/overview/reinforcement-learning/rl_existing_scripts.rst`, `rl_frameworks.rst`
3. `source/isaaclab_tasks/isaaclab_tasks/manager_based/manipulation/reach/reach_env_cfg.py`: **the whole MDP on one page.** Read every term.
4. `.../reach/mdp/rewards.py`: how rewards are plain functions of `env`.
5. `.../reach/config/ur_10/joint_pos_env_cfg.py`: how a robot-specific task overrides the generic one. **This is your template.**
6. `.../deploy/reach/config/ur_10e/` + `docs/source/policy_deployment/02_gear_assembly/gear_assembly_policy.rst`: NVIDIA's sim-to-real-minded version. Note what they changed and why.
7. `scripts/reinforcement_learning/rsl_rl/train.py`: how a script loads a task, wraps it, and trains.
8. `docs/source/tutorials/05_controllers/run_diff_ik.rst`: differential IK.

### 🛠 Build
1. Create `doosan_lab/tasks/reach/`: a `joint_pos_env_cfg.py` subclassing `ReachEnvCfg`, `agents/rsl_rl_ppo_cfg.py`, and `__init__.py` with `gym.register`.
2. Set the end-effector body to `grasp_link` (check that it exists in `body_names`) and set command ranges to the A0509's workspace.
3. Smoke-train for 50 iterations. Check VRAM. Then do the full train (≈ 1500 iterations).
4. `play.py --video` 👤
5. Make the IK-Rel variant and compare it against joint-pos (PLAN 2.3).
6. 🔬 Change **one** reward weight (e.g. 10× the action-rate penalty), retrain, and describe what changed in the behaviour.

### ✅ Checklist
- [ ] My task appears in `gym.registry` after `import doosan_lab`
- [ ] Training runs; TensorBoard shows reward rising and position error falling
- [ ] Position error < 0.02 m, orientation error < 0.1 rad
- [ ] Video recorded 👤
- [ ] Joint-pos vs IK-Rel comparison in `notes/02_reach.md`
- [ ] The reward-weight experiment is documented
- [ ] I can list every term in `reach_env_cfg.py` and what it does without looking

### 🧪 Self-check
1. What are the physics dt, decimation and policy rate of your task? Compute the policy Hz.
2. Why does the reach task penalize `action_rate`? What happens on a real robot without it?
3. What is the observation vector size, and what makes it up?
4. Why might IK-Rel generalize better to the real A0509 than joint-pos?
5. In the `deploy/reach` UR10e config, name two changes made "for the real robot".

### ⚠️ Pitfalls
- The task isn't found → `doosan_lab` wasn't imported before `gym.make`.
- Reward goes up but the error doesn't go down → you're tracking the wrong body, or the command frame is wrong.
- OOM → halve `num_envs`.

---

## Chapter 3 — Grasping, sensors and cameras (PLAN Phase 3)

### 🧠 Concepts
**Why grasping is hard for RL.** The reward is sparse (the cube only moves once the grasp works), contact physics is discontinuous, and there are many local optima (pushing or flicking the cube). Isaac Lab's lift task solves this with **reward shaping**: reach the object → lift it → track the goal, with each stage gated by the previous one. Read the reward functions, because they're a lesson in shaping.

**Binary gripper actions.** The policy outputs a sign (open/close), and a `BinaryJointPositionAction` maps it to joint targets. This is far easier to learn than continuous finger control, and it matches how the real AG95 is usually commanded.

**Sensors in Isaac Lab:**
- `ContactSensor`: forces on bodies (needs `activate_contact_sensors=True`).
- `FrameTransformer`: the pose of one frame relative to another (e.g. TCP in the robot base frame).
- `Camera` / `TiledCamera`: RGB, depth or segmentation. `TiledCamera` renders all envs' cameras into one big texture, which is much faster for many envs.
- Cameras cost VRAM and time, which is why RL here stays state-based and cameras are only for demos and VLAs.

**Privileged vs deployable observations.** In sim, the policy can see the exact cube pose. A real robot can't. State-based RL is fine for learning, but the policy you deploy must be built on observations you *can* get on hardware (camera images, or a pose estimator).

### 📖 Read
1. `.../manipulation/lift/lift_env_cfg.py` and `.../lift/mdp/rewards.py`, `observations.py`, `terminations.py`
2. `.../lift/config/franka/joint_pos_env_cfg.py`, `ik_rel_env_cfg.py`
3. `docs/source/tutorials/04_sensors/add_sensors_on_robot.rst` + `scripts/tutorials/04_sensors/run_usd_camera.py`
4. `docs/source/overview/core-concepts/sensors/camera.rst`, `contact_sensor.rst`, `frame_transformer.rst`
5. `docs/source/how-to/estimate_how_many_cameras_can_run.rst` and `save_camera_output.rst`

### 🛠 Build
1. A lift task for the A0509 (PLAN 3.1). Train, then watch the video carefully: is it really grasping? 👤
2. If it's stuck: plot each reward term separately in TensorBoard to see which stage it fails at.
3. Add the wrist and front cameras in a separate observation group (PLAN 3.2). Save frames. Measure VRAM at 16/64/256 envs.

### ✅ Checklist
- [ ] Lift success ≥ 80 % over 100 episodes
- [ ] I can explain each lift reward term and its gating
- [ ] Wrist and front camera frames saved and checked 👤
- [ ] VRAM table for cameras × num_envs in `notes/03_lift.md`

### 🧪 Self-check
1. Draw the lift reward as a function of the stage reached (reach / grasp / lift / goal).
2. Why is the object's pose a "privileged" observation?
3. Why use `TiledCamera` rather than `Camera` for many envs?
4. If the policy pushes the cube instead of grasping it, which reward term would you change?

### ⚠️ Pitfalls
- Finger pad friction too low makes the cube slip. Set the physics material.
- Forgetting `--enable_cameras` makes cameras silently produce nothing.

---

## Chapter 4 — Teleoperation, datasets and Isaac Lab Mimic (PLAN Phase 4)

### 🧠 Concepts
**Why demos at all?** For long-horizon, contact-rich tasks, RL is slow and fragile. Humans can demonstrate in minutes. But behaviour cloning needs *hundreds to thousands* of demos, which nobody wants to record by hand.

**Isaac Lab Mimic (based on MimicGen).**
1. You record ~10–20 demos.
2. Each demo is split into **subtasks** (grasp A, place A on B), with boundaries found from *subtask signals* (e.g. "is the cube grasped?").
3. Each subtask segment is expressed as end-effector poses **relative to the object it interacts with**.
4. For a new random scene, Mimic takes a source segment, transforms it to the new object pose, interpolates between segments, and executes it in sim.
5. Only successful generated demos are kept.

Result: ~1000 demos from ~15. This is why the IK-Rel action space matters: Mimic reasons in end-effector space.

**SkillGen** (newer, in the same docs) adds motion planning between segments for better collision-free stitching.

**Dataset format.** Isaac Lab writes HDF5: `data/demo_N/{actions, obs/*, states/*, initial_state}`. robomimic reads it directly. VLAs want the **LeRobot** format, so you'll write a converter in Ch.5.

### 📖 Read
1. `docs/source/overview/imitation-learning/teleop_imitation.rst`: **the main guide; follow it with Franka first.**
2. `docs/source/overview/imitation-learning/augmented_imitation.rst` and `skillgen.rst`
3. `source/isaaclab_mimic/isaaclab_mimic/envs/franka_stack_ik_rel_mimic_env_cfg.py` and `franka_stack_ik_rel_mimic_env.py`: what *you* must implement for the A0509.
4. `.../manipulation/stack/config/franka/stack_ik_rel_env_cfg.py`, `stack_ik_rel_visuomotor_env_cfg.py`
5. `scripts/tools/record_demos.py`, `replay_demos.py`; `scripts/imitation_learning/isaaclab_mimic/annotate_demos.py`, `generate_dataset.py`
6. 🔬 MimicGen paper (Mandlekar et al., CoRL 2023).

### 🛠 Build
1. **Warm-up (half a day): do the full pipeline with Franka first**, exactly as in `teleop_imitation.rst`. You'll learn the tools without your own bugs in the way.
2. Build the A0509 two-cube stack task + Mimic env (PLAN 4.1).
3. Make a keyboard (or SpaceMouse) cheat sheet, then record ~15 demos 👤 (PLAN 4.2).
4. Annotate → generate 1000 (PLAN 4.3). Spot-check the replays 👤

### ✅ Checklist
- [ ] Franka Mimic pipeline done end to end (warm-up)
- [ ] A0509 stack task: the success term verified with a teleport test
- [ ] Mimic env methods implemented (eef pose ↔ action conversions)
- [ ] ≥ 10 good human demos recorded 👤
- [ ] ≥ 1000 generated demos; generation success rate logged
- [ ] `notes/04_mimic.md` explains the object-relative transform with a diagram

### 🧪 Self-check
1. Why must the subtask segment be expressed relative to the *object* rather than the world?
2. What makes the generation success rate low, and how would you raise it?
3. What's inside one HDF5 demo? (Open it with `h5py` and print the tree.)
4. What does `annotate_demos.py --auto` need from your env?

### ⚠️ Pitfalls
- Teleop at too high a speed gives jerky demos, and jerky demos make worse generated demos. Go slow.
- Inconsistent grasps across your source demos confuse Mimic. Be boringly consistent.

---

## Chapter 5 — Imitation learning and VLAs (PLAN Phase 5) ✅ VLA POC

### 🧠 Concepts
**Behaviour cloning (BC):** supervised learning from observation to action. A good baseline, but it suffers from *compounding errors*: small mistakes take the robot to states the demos never showed. Fixes: more and diverse data (Mimic!), action chunking, and history (RNN, transformer).

**Policy families, roughly from oldest to newest:**
- **BC-RNN** (robomimic): BC plus memory.
- **ACT**: a transformer that predicts *chunks* of future actions. Chunking reduces compounding error.
- **Diffusion Policy / flow matching**: model the *distribution* of actions (multi-modal: "go left OR right around the obstacle"), refined from noise.
- **VLA (Vision-Language-Action)**: take a pretrained vision-language model (VLM), add an action output, and fine-tune on robot data. Language becomes the task interface ("stack the red cube on the green cube").

**The VLAs to know** (versions change; check current ones):

| Model | Core idea |
|---|---|
| **OpenVLA** | 7B Llama-2-based VLM; actions as discrete tokens. |
| **π0 / π0.5** (Physical Intelligence) | A VLM backbone plus a *flow-matching action expert* that outputs continuous action chunks. |
| **SmolVLA** (Hugging Face) | A small VLM (~450M total) plus a flow-matching action expert. **Fits a 12 GB GPU.** |
| **GR00T N1.x** (NVIDIA) | "System 2" VLM for understanding plus a "System 1" diffusion-transformer action head; embodiment-specific state/action encoders. Ch.8. |
| **World Action Models (WAMs)** | Models that jointly predict future observations (video) *and* actions, using world modelling as the training signal. An active research area; cover it in write-up #1. |

**The LeRobot dataset format:** episodes as Parquet tables (state, action, timestamps, task string) plus MP4 videos per camera, and `meta/` describing features. Both SmolVLA and GR00T fine-tune from it.

**Why a policy server?** Isaac Sim's bundled Python pins its own torch and CUDA libraries, and VLA stacks pin theirs. Run the policy in its own env behind a socket: the sim sends observations and receives actions. This is also exactly how you'll run it on the real robot.

### 📖 Read
1. `docs/source/overview/imitation-learning/teleop_imitation.rst` → the robomimic training section
2. `scripts/imitation_learning/robomimic/train.py`, `play.py`, `robust_eval.py`
3. The LeRobot docs: dataset format v-current, and the SmolVLA fine-tuning guide (check the current version)
4. Papers (skim the abstract, figures and method; full reads are 🔬):
   - Diffusion Policy (Chi et al., 2023)
   - ACT / ALOHA (Zhao et al., 2023)
   - π0 (Black et al., 2024)
   - SmolVLA (Hugging Face, 2025)
   - OpenVLA (Kim et al., 2024)

### 🛠 Build
1. BC baseline with robomimic (PLAN 5.1).
2. HDF5 → LeRobot converter (PLAN 5.2). Write it yourself; you'll reuse it for GR00T.
3. Set up a separate `lerobot` env and fine-tune SmolVLA (PLAN 5.3).
4. Policy server + Isaac Lab eval client (PLAN 5.4). 50 rollouts, a video. **🎉 VLA proof of concept.**
5. Write-up #1 (PLAN 5.5).

### ✅ Checklist
- [ ] BC ≥ 60 % success in sim
- [ ] The LeRobot dataset loads; one episode visualized correctly
- [ ] SmolVLA fine-tuned (loss curve saved)
- [ ] Policy-server eval harness working
- [ ] SmolVLA closed-loop success rate over 50 rollouts + video
- [ ] Write-up #1 done → saved in `writeups/`

### 🧪 Self-check
1. Explain compounding error and two ways to fight it.
2. Why does action chunking help?
3. Flow matching vs discrete action tokens: what's the trade-off?
4. If BC hits 60 % but SmolVLA hits 20 %, list 3 likely causes.
5. Why do the state and action normalization statistics matter for VLAs?

### ⚠️ Pitfalls
- Mismatched action definitions between the dataset and the eval harness (delta vs absolute, IK-Rel vs joint) give garbage behaviour that *looks* like a bad model.
- Mismatched camera names or image sizes between training and eval.
- Mismatched control frequency between the dataset and the eval.

---

## Chapter 6 — Cosmos (PLAN Phase 6) ✅ write-up #2

### 🧠 Concepts
**World Foundation Models (WFMs)** are generative models of how the physical world evolves. Cosmos is NVIDIA's family:
- **Cosmos Predict**: given video (+ text/actions), generate the future. Uses: a world simulator, policy evaluation, synthetic data.
- **Cosmos Transfer**: conditional generation from structure (segmentation, depth, edges, blur) to photoreal video. Use: **make sim data look real** while keeping the same motion, closing the visual sim-to-real gap. Isaac Lab already has hooks for it: `franka_stack_ik_rel_visuomotor_cosmos_*` configs and `scripts/tools/cosmos/`.
- **Cosmos Reason**: a VLM trained for physical common sense and embodied reasoning over video. Uses: success detection, data curation, high-level planning, critiquing.

**Where they fit:** Transfer improves *data*; Reason improves *judgement* (labels, planning, curation); Predict is a *simulator made of neural networks*.

### 📖 Read
1. Cosmos docs and model cards (check current versions; NVIDIA's GitHub and Hugging Face)
2. `scripts/tools/cosmos/cosmos_prompt_gen.py`, `transfer1_templates.json`
3. `source/isaaclab_tasks/.../stack/config/franka/stack_ik_rel_visuomotor_cosmos_env_cfg.py` and the matching mimic cfg: what extra observations (segmentation, depth) does Cosmos Transfer need?
4. The Cosmos WFM paper (NVIDIA, 2025): skim §1–3.

### 🛠 Build
1. Run Cosmos Reason locally (quantized) in a separate env (PLAN 6.1). Log VRAM.
2. Success detector over 50 eval videos; confusion matrix (PLAN 6.2).
3. 🔬 Planner experiment (PLAN 6.3).
4. Write-up #2 (PLAN 6.4).

### ✅ Checklist
- [ ] Cosmos Reason runs on 12 GB (method + VRAM noted)
- [ ] Success-detector accuracy and confusion matrix
- [ ] I can explain Predict vs Transfer vs Reason in one sentence each
- [ ] I know which observations the Cosmos visuomotor config adds, and why
- [ ] Write-up #2 done → saved in `writeups/`

### 🧪 Self-check
1. Which Cosmos model would you use to make 1000 Mimic demos look like your real lab? What inputs does it need?
2. Where can a VLM success detector fail silently?
3. Why is "world model as a policy evaluator" attractive, and what's the catch?

---

## Chapter 7 — GR00T (PLAN Phase 7, when a big GPU is available)

### 🧠 Concepts
- **Architecture (N1 family):** a pretrained VLM (System 2) encodes images and language; a diffusion-transformer action head (System 1) generates continuous action chunks via flow matching, conditioned on the VLM features plus robot state. **Embodiment-specific** projectors map each robot's state and action to and from a shared space. That's how one model serves many robots.
- **Training data pyramid:** web and human video (bottom), synthetic sim data (middle, including Isaac Lab and Cosmos-generated data), real robot data (top).
- **Fine-tuning for a new robot:** define a *modality config* (which state keys, action keys and cameras; normalization), point it at a LeRobot dataset, and fine-tune (often the action head plus projectors, with the VLM frozen).

### 📖 Read
1. The Isaac-GR00T GitHub README, the fine-tuning guide and the "new embodiment" guide (current version)
2. The GR00T N1 paper (NVIDIA, 2025): §2 architecture, §3 data
3. Your Ch.5 LeRobot converter: GR00T consumes the same format.

### 🛠 Build
1. A modality config for the A0509 + AG95 + 2 cameras.
2. Fine-tune on the big GPU; log the cost and time.
3. Run it behind the *same* policy server; 50 rollouts.
4. One table: BC vs SmolVLA vs GR00T.

### ✅ Checklist
- [ ] The modality config matches the dataset (keys, dims, normalization)
- [ ] Fine-tune finished; GPU, hours and hyperparameters in `DECISIONS.md`
- [ ] GR00T closed-loop success over 50 rollouts + video
- [ ] Comparison table + a short addendum to write-up #1

### 🧪 Self-check
1. What exactly is embodiment-specific in GR00T, and what's shared?
2. Why freeze the VLM during fine-tuning?
3. Your GR00T success rate is below SmolVLA's. Give 3 hypotheses and how you'd test each.

---

## Chapter 8 — Sim-to-real on the A0509 (PLAN Phase 9)

### 🧠 Concepts
- **The reality gap** has three parts: dynamics (friction, motor response, latency), perception (images look different), and embodiment (calibration offsets).
- **Tools:** domain randomization (mass, friction, gains, lighting, textures, camera pose), observation noise, action-rate limits, matching the control frequency, system identification (measure the real robot and fit the sim to it), and photoreal augmentation (Cosmos Transfer).
- **Camera calibration:** intrinsics (lens) plus hand-eye extrinsics (camera → flange). Match both in sim *before* collecting data.
- **Safety:** workspace limits and velocity limits enforced *outside* the policy, a human on the e-stop, and a dry run in the emulator first.

### 📖 Read
1. `docs/source/policy_deployment/index.rst`, `01_io_descriptors/io_descriptors_101.rst`, `02_gear_assembly/gear_assembly_policy.rst`
2. `.../deploy/` tasks (reach and gear assembly for the UR10e): compare them with your tasks line by line
3. `doosan-robot2` README: the emulator (`install_emulator.sh`) and the ROS 2 control interfaces
4. 🔬 The "Domain Randomization" paper (Tobin et al., 2017)

### ✅ Checklist
- [ ] Emulator dry run of the reach policy
- [ ] Real reach at ≤ 10 % speed with an e-stop person 👤
- [ ] Wrist camera calibrated; sim camera matched
- [ ] Real lift → real stack
- [ ] Sim vs real success table + video

---

## Appendix A — Command cheat sheet
```bash
# start container with repo mounted (after Phase 0)
~/pranav_ws/Isaac_lab_learnings/scripts/start_container.sh
docker exec -it isaac-lab-base bash          # shell inside
cd /workspace/isaaclab && bash /workspace/learnings/scripts/setup_container.sh

# train / play
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py --task <ID> --headless --num_envs 1024
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play.py  --task <ID>-Play --num_envs 16 --video

# list our tasks
./isaaclab.sh -p -c "import gymnasium as gym, doosan_lab; print([k for k in gym.registry if 'Doosan' in k])"

# tensorboard (host browser → http://localhost:6006)
./isaaclab.sh -p -m tensorboard.main --logdir logs/rsl_rl --port 6006

# copy logs out of the docker volume
docker cp isaac-lab-base:/workspace/isaaclab/logs/rsl_rl/<exp> ~/pranav_ws/Isaac_lab_learnings/outputs/

# demos
./isaaclab.sh -p scripts/tools/record_demos.py --task <ID> --teleop_device keyboard --dataset_file <f.hdf5> --num_demos 15
./isaaclab.sh -p scripts/tools/replay_demos.py --task <ID> --dataset_file <f.hdf5>
./isaaclab.sh -p scripts/tools/hdf5_to_mp4.py ...
```
Check each script's `--help`. Flags change between versions.

## Appendix B — Debugging playbook
| Symptom | First suspects |
|---|---|
| Robot explodes on Play | overlapping collisions, a joint frame mismatch, tiny masses, too-high gains |
| Robot sags | stiffness too low, wrong actuator regex, gravity settings |
| Gripper won't close fully | mimic gearing sign, drive maxForce, joint limits in degrees vs radians |
| Cube slips | friction material, grip effort, contact offset |
| Reward ↑ but task ✗ | reward hacking: watch the video, plot individual terms |
| Task not found | package not imported before `gym.make` |
| OOM | `num_envs`, cameras, image resolution |
| Policy great in train, bad in play | Play cfg differs (randomization off/on), obs normalization not loaded |
| VLA bad in eval | action definition, camera keys, normalization stats, control Hz mismatch |

## Appendix C — Glossary
**Articulation**: a robot solved in joint space. **Prim**: a node in the USD tree. **Layer**: a USD file contributing opinions. **Decimation**: physics steps per policy step. **GAE**: generalized advantage estimation. **TCP**: tool centre point. **Subtask signal**: Mimic's marker for when a subtask ends. **Action chunk**: a sequence of future actions predicted at once. **Embodiment**: a specific robot's body (kinematics, sensors, action space). **WFM**: world foundation model. **Domain randomization**: varying sim parameters so the policy treats reality as just another variation.

## Appendix D — Reading list for the write-ups
**Write-up #1 (VLA/WAM):**
- GR00T N1
- π0 / π0.5
- SmolVLA
- OpenVLA
- Diffusion Policy
- ACT
- RT-2 (the historical anchor)
- one WAM / video-action paper of your choice

**Write-up #2 (Cosmos):**
- the Cosmos WFM paper
- the Cosmos Transfer and Reason model cards
- the Isaac Lab Cosmos visuomotor configs
- your Phase 6 results

Check that each of these is still current when you write. This field moves monthly.

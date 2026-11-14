# Progress log

Format: `YYYY-MM-DD | step | PASS/FAIL | evidence (numbers, paths, commit)`.

## Pre-plan checks (2026-10-17, done during planning)
- 2026-10-17 | env | PASS | Container `isaac-lab-base` (Isaac Lab 2.3.2, Isaac Sim 5.1.0) starts; torch 2.7.0+cu128, CUDA available.
- 2026-10-17 | env | PASS | `Isaac-Reach-Franka-v0`, 1024 envs, 100 iters: 0.19 s/iter, position_error 0.256 → 0.133 m.
- 2026-10-17 | env | PASS | the reference AG95 USD has 5 PhysxMimicJointAPI joints driven by left_outer_knuckle_joint; A0509 USD has a fixed root_joint carrying ArticulationRootAPI.
- 2026-10-17 | env | PASS | The AG95 xacro macro expands standalone with pip `xacro` inside the container (13 joints, 5 mimic, 2 loop joints only in `<gazebo>`).
- Note: the container was started with plain `docker start` (no repo mount yet). Phase 0.2 recreates it.

## Phase 0 — DONE
- [x] 0.1 Repo skeleton
- [x] 0.2 Container mount: `/workspace/learnings` visible; 17 `docker_*` volumes kept (we removed the container with `docker rm`, not `container.sh stop`, which runs `down --volumes`). `start_container.sh` sets DISPLAY/XAUTHORITY itself (GNOME/Wayland terminals lack them).
- [x] 0.3 Setup script: `doosan_lab 0.1.0` editable install + `xacro 2.1.1`; import path is the mounted source
- [x] 0.4 GUI check: `create_empty.py` + `run_articulation.py` ran with the window; first launch 93 s (shader compile)

## Phase 1 — A0509 + AG95 digital twin (1.1-1.5 DONE; 1.6 exercise pending)
- [x] 1.1 Copy the reference USDs: copies byte-identical; originals unchanged
- [x] 1.2 Compose `a0509_ag95.usda`: 12/12 validator checks PASS: 1 articulation root, 6+6 revolute, 5 mimic, one connected tree, authored poses agree with joint frames (0.000 mm; the old file fails at 1060 mm), pad colliders bind a friction-1.0 material. 👤 GUI: Pranav confirmed the gripper sits on the flange before pressing Play.
- [x] 1.3 ArticulationCfg + spawn gate: 1.3a hold 0.00000 rad | 1.3b step +0.3 rad settles in 0.35 s, overshoot 0.0015 rad, peak 79 % of velocity limit | 1.3c commanding 0.5 rad puts all six gripper joints at +0.5000. Gravity ON for comparison: arm sags 0.042 rad (fails).
- [x] 1.4 Gripper verification: 20/20 held (4 cm, 50 g, random offset/yaw), lift 197-199 mm, slip <= 0.11 mm, squeeze 10.5 N m ~ 100 N. Pranav's own 5-trial GUI run: 5/5. Negative control: 5 kg -> 18/20, 15 kg and 25 kg -> 0/20 (sim grip capacity is far below the ideal 200 N x mu; do not plan on > ~2 kg).
- [x] 1.5 Joint sweep: numbers PASS (all six joints reached >= 59.4 deg of +-60; joint_2 stops at 43.7 deg if the ground plane is present, because the gripper hits the floor). 👤 visual: Pranav confirmed all six joints match the expected directions and the gripper stays attached.
- [ ] 1.6 Build-from-URDF exercise + compare notes (`notes/01b_urdf_vs_source.md`)
- Open items: `notes/01_assets.md` not written; the provenance note `SOURCE.md` was removed when the asset folders were moved up (provenance is in DECISIONS.md D2); visual materials of the gripper bind to a missing path (cosmetic).

## Phase 2 — Reach with RL (2.1, 2.2 DONE)
- [x] 2.1 Reach task `Doosan-Reach-A0509-v0` (+ `-Play-v0`): registers, builds, trains. Smoke: 256 envs / 30 it OK; 1024 envs = 0.61 s/it, peak 3.1 GB GPU, so 1500 it ~ 15 min. Fixed on the way: shared SceneEntityCfg ("joint_names and joint_ids not consistent"). 👤 GUI (16 envs, live training): Pranav confirmed scene, targets, gripper stability all as expected. At iteration 176/300 with only 16 envs: position_error 0.2275 (= the do-nothing baseline ~0.2), action std 1.01, i.e. not learning yet, as expected for 16 envs. Decisions: DECISIONS.md D13.
- [x] 2.2 Reach trained (1024 envs; stopped by Pranav at ~iteration 700 of 1500) and evaluated with `scripts/eval_reach.py` (mean action, 1024 envs x 6 targets = 6144 settled windows). **Best checkpoint model_450: mean position error 4.5 mm (limit 20), orientation 0.033 rad (limit 0.1); p95 9.9 mm / 0.068 rad; worst 31 mm / 0.162 rad.** Latest (model_700) is WORSE: 9.8 mm / 0.068 rad. Trend by checkpoint: it100 10.4 mm, 200 6.6, 300 5.2, 450 4.5, 600 4.6, 650 6.1, 700 9.8. Mean action holds perfectly still (0.00 mm tremble); the vibration Pranav saw is exploration noise (sampled actions: 6.9 mm tremble, 0.52 rad/s joint speed). Saved in `outputs/reach_run1/`. See DECISIONS D14.
- [ ] 2.3 Joint-pos vs IK-Rel comparison + notes/02_reach.md (on 3.0, after M.7)

## Phase M — Isaac Lab 3.0.0 / Isaac Sim 6.2.0, then re-baseline Phases 0–2 (2.3 parked until M.7)
Old (2.3.2) numbers in brackets are the comparison column.
- [ ] M.0 Read + decide: D15 approved (written 2026-11-07 as PROPOSED)
- [ ] M.1 Image pulled, `isaac-lab-3` up; Cartpole + `Isaac-Reach-Franka` on `isaacsim_physx`: __ s/iter [0.19], peak VRAM __ GB, first launch __ s; launcher that works: __
- [ ] M.2 Newton probe: PhysX vs Newton table (s/iter, VRAM, Kit-less?); verdict: __
- [ ] M.3 Extension ported: `isaaclab list_envs` shows the Doosan tasks; reach builds at 16 envs; quaternion report reviewed
- [ ] M.4 R0.1 Branch `isaaclab-3`
- [ ] M.4 R0.2 Mount: `/workspace/learnings` visible in `isaac-lab-3`
- [ ] M.4 R0.3 Setup script: `import doosan_lab, xacro` ok
- [ ] M.4 R0.4 👤 GUI (`--viz kit`): first launch __ s [93 s]
- [ ] M.5 R1.2 Validator __/12 [12/12]; 👤 flange
- [ ] M.5 R1.3 Hold __ rad [0.00000]; step settle __ s [0.35], overshoot __ rad [0.0015], peak __ % [79]; gripper joints at 0.5 [+0.5000 x6]
- [ ] M.5 R1.4 Grasp __/20 [20/20], lift __ mm [197–199], slip __ mm [≤0.11]; 5/15/25 kg __/__/__ [18/0/0]; Newton probe: __
- [ ] M.5 R1.5 Sweep ≥ __ deg [59.4]; 👤 directions
- [ ] M.5 R1.6 URDF with new importer: mimic joints __ [5, gearing −1]; D12 amended; `notes/01b_urdf_vs_source.md`
- [ ] M.6 R2.1 Reach trains: __ s/iter [0.61], __ GB [3.1]
- [ ] M.6 R2.2 model_450 on 3.0: __ mm / __ rad [4.5 / 0.033]; new run best checkpoint __ (__ mm / __ rad)
- [ ] M.7 Decision D16; return to 2.3

## Phase 3
- [ ] 3.1 Lift (success __ %)
- [ ] 3.2 Cameras + notes/03

## Phase 4
- [ ] 4.1 Stack task + Mimic env
- [ ] 4.2 👤 Demos recorded (__ successful)
- [ ] 4.3 Mimic generation (__ demos, __ % gen success) + notes/04

## Phase 5
- [ ] 5.1 BC baseline (__ %)
- [ ] 5.2 LeRobot conversion
- [ ] 5.3 SmolVLA trained
- [ ] 5.4 Eval harness + SmolVLA closed-loop (__ %)
- [ ] 5.5 Write-up #1

## Phase 6
- [ ] 6.1 Cosmos Reason running locally (VRAM __ GB)
- [ ] 6.2 Success detector accuracy (__ %)
- [ ] 6.4 Write-up #2

## Phase 7+ — when resources allow

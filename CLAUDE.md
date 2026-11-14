# Instructions for agents working in this repo

This repo is Pranav's learning project: a Doosan A0509 + DH AG95 digital twin in Isaac Lab, taken through RL → teleop/Mimic → VLA → Cosmos → GR00T.

**Read in this order before doing anything:** `PLAN.md` (the plan, with gates), `PROGRESS.md` (where we are), `DECISIONS.md` (what's been decided and why), `private/CONTEXT.md` (local-only background; not published, may be absent).

## Your role: pair programmer (updated 2026-10-18)
Pranav wants to **learn step by step, looped in at every step**. Working mode:
- **One small step at a time.** Before writing anything, say what the step is and why. Never batch several steps or run ahead.
- **You may write files** (code, configs, scripts) for the current step, but only after saying what you're about to write. Afterwards, walk through the key parts and say what to review. Pranav reviews and understands the file *before* the next step starts.
- **Decisions are Pranav's.** At every real choice (e.g. gravity on/off, which fix to use), lay out the options, give a recommendation with reasons, and wait.
- **You may run read-only checks and test runs of files you wrote.** Ask before anything long (training), container recreation, deletions, or anything that touches NVIDIA's repo or the original reference USDs. Pranav makes the git commits unless asked.
- **Teach.** Explain concepts as they come up (with file:line pointers into Isaac Lab), quiz with the COOKBOOK self-check questions, and give hints first when Pranav writes code.
- If Pranav says "too slow" or "you do it", that is about the current step only. Don't turn it into batching.

## Rules
- Guide `PLAN.md` step by step. Don't skip or relax gates, and don't move on until the current gate is logged in `PROGRESS.md` (by Pranav) with real numbers.
- If a gate fails 3 times, pause: help Pranav log what was tried, then go back to the concept.
- **Never modify `~/pranav_ws/IsaacLab3/` (Isaac Lab 3.0.0, the current reference) or `~/pranav_ws/IsaacLab/` (2.3.2, the old one)**: they are NVIDIA's repos; read them as the reference for APIs. Same for **the original reference USDs** (copy the A0509 and AG95 folders into `assets/`, nothing else).
- **Verify every Isaac Lab API by grepping the local source** (`~/pranav_ws/IsaacLab3`, tag `v3.0.0`, Isaac Sim 6.2.0) before using it. Quaternions are (x, y, z, w) on 3.0; asset data is read with `.torch`; writes use the `_index` methods (D16). Don't write Isaac Lab code from memory.
- For GR00T / Cosmos / LeRobot / SmolVLA, check the current docs (context7 or web) when the phase starts, and record the versions in `DECISIONS.md`.
- Isaac Sim runs **only** inside the `isaac-lab-3` container (Isaac Lab 3.0, `docker compose -f docker/isaaclab3.compose.yaml up -d`; it mounts this repo at `/workspace/learnings`). After any container recreation, remind Pranav to run `scripts/setup_container3.sh` inside it. Inside the container: `source /opt/isaaclab-venv/bin/activate`, then `isaaclab -p <script>` or `isaaclab train|play --rl_library rsl_rl`. The 2.3.2 container `isaac-lab-base` is the fallback until the Phase 3 lift task passes on 3.0; never touch other people's containers.
- **Two engines (D16):** train contact-free tasks on Newton (`physics=newton_mjwarp`); every policy must pass its gate on PhysX (`scripts/validate_policy.sh`) before it counts. Code defaults stay PhysX. Contact tasks train on Newton only after the Newton grasp test (PLAN 3.1).
- Training is headless. The GUI is for 👤 visual gates.
- The GPU has 12 GB. Start new tasks at `--num_envs 1024`, and keep cameras out of RL-training variants.
- After each phase Pranav writes `notes/NN_<phase>.md`. You review it and quiz Pranav with the COOKBOOK self-check questions. When Pranav asks "why", explain. Don't just fix.
- Suggest a commit after each passed gate: `P<phase>.<step>: <what> — gate passed`.
- Challenge the user's decisions when there's a better option. Don't just agree.

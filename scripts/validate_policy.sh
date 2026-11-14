#!/usr/bin/env bash
# Evaluate a reach checkpoint on PhysX (the gate) and on Newton (for comparison), back to back.
# Exit status follows the PhysX gate only: a policy trained on Newton still has to pass on PhysX (D16, option B).
#
#   docker exec isaac-lab-3 bash /workspace/learnings/scripts/validate_policy.sh /workspace/learnings/logs/rsl_rl/reach_a0509/<run>/model_250.pt
set -uo pipefail
CKPT=${1:?usage: validate_policy.sh <checkpoint.pt> [num_envs]}
ENVS=${2:-256}
source /opt/isaaclab-venv/bin/activate
cd /workspace/learnings
status=1
for engine in isaacsim_physx newton_mjwarp; do
  out=$(isaaclab -p scripts/eval_reach.py --checkpoint "$CKPT" --num_envs "$ENVS" physics=$engine 2>&1)
  echo "== $engine"
  echo "$out" | grep "^EVAL \(mean\|sampled\)" | sed 's/^EVAL //'
  echo "$out" | grep "^GATE"
  if [ "$engine" = isaacsim_physx ] && echo "$out" | grep -q "^GATE 2.2 reach (mean action): PASS"; then status=0; fi
done
echo "PhysX gate: $([ $status -eq 0 ] && echo PASS || echo FAIL)"
exit $status

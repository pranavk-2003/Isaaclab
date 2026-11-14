"""Sample efficiency of training runs, read from their TensorBoard logs (CPU only, no simulator).

    python scripts/compare_runs.py LABEL=RUN_DIR [LABEL=RUN_DIR ...] [--threshold 0.02]

For each run: the first iteration where the training position error is at or below the threshold, on the raw series and on a
10-iteration moving average, plus the error at a few fixed iterations. The training metric is measured with exploration noise
on, so it is only for comparing learning speed; use scripts/eval_reach.py for the final error of a checkpoint.
"""

import argparse

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

TAG = "Metrics/ee_pose/position_error"
CHECK_AT = (50, 100, 200, 300, 450)

parser = argparse.ArgumentParser()
parser.add_argument("runs", nargs="+", help="LABEL=RUN_DIR")
parser.add_argument("--threshold", type=float, default=0.02, help="Position error in metres.")
args = parser.parse_args()


def first_at_or_below(steps, values, threshold):
    return next((s for s, v in zip(steps, values) if v <= threshold), None)


print(f"{'run':<28} {'first <= ' + str(args.threshold) + ' m (raw)':>22} {'(10-it average)':>16}  " + "  ".join(f"it{c:>3}" for c in CHECK_AT))
for item in args.runs:
    label, path = item.split("=", 1)
    ea = EventAccumulator(path, size_guidance={"scalars": 0})
    ea.Reload()
    series = ea.Scalars(TAG)
    steps = [e.step for e in series]
    values = [e.value for e in series]
    avg = [sum(values[max(0, i - 9) : i + 1]) / len(values[max(0, i - 9) : i + 1]) for i in range(len(values))]
    raw, smooth = first_at_or_below(steps, values, args.threshold), first_at_or_below(steps, avg, args.threshold)
    at = {s: v for s, v in zip(steps, values)}
    cells = "  ".join(f"{at[c] * 1000:5.0f}" if c in at else "    -" for c in CHECK_AT)
    print(f"{label:<28} {str(raw if raw is not None else 'never'):>22} {str(smooth if smooth is not None else 'never'):>16}  {cells}")
print("(error columns: training position error in mm at that iteration)")

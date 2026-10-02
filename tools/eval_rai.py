"""Score our scene boundaries against the human labels of the RAI scene dataset.
usage: python tools/eval_rai.py [videos e.g. 1,2,3] [threads] [extra exe args...]
GT file: one line per scene "start end" (1-indexed, inclusive).
Boundary = 0-indexed first frame of every scene except the first."""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate import prf, load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
TOLS = (25, 50, 125)  # frames @25 fps = 1 s, 2 s, 5 s


def gt_boundaries(i):
    rows = [list(map(int, l.split())) for l in
            open(os.path.join(ROOT, "data", "RAIDataset", f"scenes_{i}.txt")) if l.strip()]
    return [r[0] - 1 for r in rows[1:]], len(rows)


def run_video(i, threads=8, extra=(), env=None):
    raw = os.path.join(ROOT, "data", f"rai_{i}_160x90.raw")
    out = subprocess.run([EXE, raw, "160", "90", "scenes", str(threads), *extra],
                         cwd=ROOT, capture_output=True, text=True, check=True,
                         env={**os.environ, **(env or {})}).stdout
    shots = int(re.search(r"shots=(\d+)", out).group(1))
    pred = load(os.path.join(ROOT, "results", f"scenes_{threads}.txt"))
    return shots, [p for p in pred if p > 0], len(pred)


def evaluate(videos, threads=8, extra=(), verbose=True, env=None):
    agg = {t: [0, 0, 0] for t in TOLS}       # matched-pred, n_pred, n_true
    for i in videos:
        gt, n_gt_scenes = gt_boundaries(i)
        shots, pred, n_pred_scenes = run_video(i, threads, extra, env)
        line = f"video {i:>2}: shots={shots:>4} scenes pred/true={n_pred_scenes:>3}/{n_gt_scenes:<3}"
        for t in TOLS:
            P, R, F = prf(pred, gt, t)
            tp = round(P * len(pred))
            agg[t][0] += tp; agg[t][1] += len(pred); agg[t][2] += len(gt)
            line += f" | tol{t}: F1={F:.2f}"
        if verbose:
            print(line)
    res = {}
    for t, (tp, npred, ntrue) in agg.items():
        P = tp / npred if npred else 0
        R = tp / ntrue if ntrue else 0
        res[t] = (P, R, 2 * P * R / (P + R) if P + R else 0)
    return res


if __name__ == "__main__":
    vids = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "1,2,3,4,5,6,7,8,9,10").split(",")]
    thr = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    r = evaluate(vids, thr, sys.argv[3:])
    for t, (P, R, F) in r.items():
        print(f"pooled tol={t:>3} frames ({t/25:.0f}s): P={P:.3f} R={R:.3f} F1={F:.3f}")

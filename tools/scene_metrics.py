"""Scene-boundary metrics for the RAI dataset.  One implementation, used by every script.

Ground truth: data/RAIDataset/scenes_<i>.txt, one "start end" line per scene,
1-indexed inclusive.  Internally everything is 0-indexed frames; a boundary is the
first frame of every scene except the first."""
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 25
TOLS = {"1s": 25, "2s": 50, "5s": 125}


def load_gt(i):
    rows = [tuple(map(int, l.split())) for l in
            open(os.path.join(ROOT, "data", "RAIDataset", f"scenes_{i}.txt")) if l.strip()]
    scenes = [(a - 1, b) for a, b in rows]            # 0-indexed, [start, end)
    return scenes, [s for s, _ in scenes[1:]]


def n_matched(pred, truth, tol):
    """Maximum one-to-one matching of predictions to truths within +-tol frames.
    Two-pointer sweep over the sorted lists; optimal for 1-D interval matching."""
    pred, truth = sorted(pred), sorted(truth)
    i = j = tp = 0
    while i < len(pred) and j < len(truth):
        d = pred[i] - truth[j]
        if abs(d) <= tol:
            tp += 1; i += 1; j += 1
        elif d < 0:
            i += 1
        else:
            j += 1
    return tp


def prf_from_counts(tp, npred, ntrue):
    p = tp / npred if npred else 0.0
    r = tp / ntrue if ntrue else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def counts(pred, truth):
    """{tol_name: (tp, npred, ntrue)} for one video."""
    return {k: (n_matched(pred, truth, t), len(pred), len(truth)) for k, t in TOLS.items()}


def pooled(count_list, tol):
    """Micro-average: add up tp / npred / ntrue over videos, then P, R, F1."""
    tp = sum(c[tol][0] for c in count_list)
    npd = sum(c[tol][1] for c in count_list)
    nt = sum(c[tol][2] for c in count_list)
    return prf_from_counts(tp, npd, nt)


def macro_f1(count_list, tol):
    return float(np.mean([prf_from_counts(*c[tol])[2] for c in count_list]))


def miou(pred_starts, gt_scenes, n_frames):
    """Symmetric intersection-over-union measure M_iou of Baraldi et al. (ACM MM 2015),
    computed in frames: for every ground-truth scene take the best IoU with a detected scene,
    average; do the same for detected scenes against ground truth; average the two."""
    starts = sorted(set([0] + list(pred_starts)))
    det = list(zip(starts, starts[1:] + [n_frames]))

    def iou(a, b):
        inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
        return inter / ((a[1] - a[0]) + (b[1] - b[0]) - inter)

    g = np.mean([max(iou(s, d) for d in det) for s in gt_scenes])
    d = np.mean([max(iou(x, s) for s in gt_scenes) for x in det])
    return float(0.5 * (g + d))


def bootstrap_ci(count_list, tol, n_boot=2000, seed=0):
    """95% interval of pooled F1 when whole VIDEOS are resampled with replacement."""
    rng = np.random.default_rng(seed)
    m = len(count_list)
    fs = []
    for _ in range(n_boot):
        idx = rng.integers(0, m, m)
        fs.append(pooled([count_list[i] for i in idx], tol)[2])
    return float(np.percentile(fs, 2.5)), float(np.percentile(fs, 97.5))


def random_baseline(npred_per_video, truth_per_video, n_frames, reps=500, seed=0):
    """Expected pooled counts of uniformly random boundaries (same number as ours)."""
    rng = np.random.default_rng(seed)
    out = {k: [0.0, 0, 0] for k in TOLS}
    for npred, truth, nf in zip(npred_per_video, truth_per_video, n_frames):
        for k, t in TOLS.items():
            tps = [n_matched(rng.integers(1, nf, npred).tolist(), truth, t) for _ in range(reps)]
            out[k][0] += float(np.mean(tps)); out[k][1] += npred; out[k][2] += len(truth)
    return {k: prf_from_counts(*v) for k, v in out.items()}

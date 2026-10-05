"""Step 2: richer classical features, evaluated with leave-one-video-out (LOVO).

For every feature set and every video v: scene parameters are chosen ONLY on the other 9 videos
(maximising pooled F1 at 2 s) and then scored on v.  Pooled over the 10 held-out videos this is
an honest estimate; no video is ever scored with parameters tuned on it.

Pre-declared main method: global + spatial-grid + edge-orientation, 3 keyframes per shot ("full").
All other rows are ablations; picking the best of them afterwards would be optimistic.

usage: python tools/scene_cv.py          -> results/scene_cv.md, results/scene_cv.json"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L      # noqa: E402
import scene_metrics as M  # noqa: E402

# name: (keyframe source, klo, khi, block weights (global, spatial colour, edge))
FEATURES = {
    "legacy: mean global hist (old method)":        ("legacy", 0, 1, (1, 0, 0)),
    "global hist, 1 keyframe":                       ("kf", 2, 3, (1, 0, 0)),
    "global hist, 3 keyframes":                      ("kf", 1, 4, (1, 0, 0)),
    "spatial 3x3 colour grid, 3 keyframes":          ("kf", 1, 4, (0, 1, 0)),
    "edge orientation 3x3, 3 keyframes":             ("kf", 1, 4, (0, 0, 1)),
    "spatial + edge, 3 keyframes":                   ("kf", 1, 4, (0, 1, 1)),
    "FULL: global + spatial + edge, 3 keyframes":    ("kf", 1, 4, (1, 1, 1)),
    "global + spatial + edge, 5 keyframes":          ("kf", 0, 5, (1, 1, 1)),
}
MAIN = "FULL: global + spatial + edge, 3 keyframes"

GRID = [dict(tau=tau, lam_new=r * tau, mu=mu, lam_scene=ls, max_phases=mp)
        for tau, r, mu, ls, mp in itertools.product(
            (0.02, 0.04, 0.07, 0.10, 0.15, 0.20, 0.30, 0.45), (0.5, 1.0),
            (0.01, 0.03, 0.08), (0.03, 0.10, 0.40, 0.80, 1.50, 3.00, 6.00), (4, 8))]


def task(args):
    fname, v = args
    src, klo, khi, w = FEATURES[fname]
    c = L.load_cache(v)
    kf = L.legacy_kf(c) if src == "legacy" else c["kf"]
    truth = M.load_gt(v)[1]
    res = []
    for p in GRID:
        pred = L.run_scenes(c, kf, klo, khi, w, p)
        res.append(M.counts(pred, truth))
    return fname, v, res


def main():
    os.makedirs(L.CACHE, exist_ok=True)
    for v in L.VIDEOS:
        L.build_cache(v)
    jobs = [(f, v) for f in FEATURES for v in L.VIDEOS]
    table = {f: {v: None for v in L.VIDEOS} for f in FEATURES}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for k, (f, v, res) in enumerate(ex.map(task, jobs)):
            table[f][v] = res
            if (k + 1) % 10 == 0:
                print(f"  {k+1}/{len(jobs)} tasks", flush=True)

    def pooled_over(f, cfg, vids, tol):
        return M.pooled([table[f][v][cfg] for v in vids], tol)

    summary, picks = {}, {}
    for f in FEATURES:
        held = []
        chosen = []
        for v in L.VIDEOS:
            train = [u for u in L.VIDEOS if u != v]
            scores = [pooled_over(f, c, train, "2s")[2] for c in range(len(GRID))]
            best = int(np.argmax(scores))
            chosen.append(best)
            held.append(table[f][v][best])
        # optimistic reference: choose on all 10 and score on the same 10
        allsc = [pooled_over(f, c, L.VIDEOS, "2s")[2] for c in range(len(GRID))]
        ib = int(np.argmax(allsc))
        insample = [table[f][v][ib] for v in L.VIDEOS]
        summary[f] = dict(held=held, insample=insample, in_cfg=GRID[ib])
        picks[f] = chosen

    # baselines
    caches = {v: L.load_cache(v) for v in L.VIDEOS}
    truth = {v: M.load_gt(v)[1] for v in L.VIDEOS}
    allc = [M.counts(caches[v]["starts"][1:].tolist(), truth[v]) for v in L.VIDEOS]
    uni = []
    for v in L.VIDEOS:
        n = len(M.load_gt(v)[0]); nf = caches[v]["nframes"]
        uni.append(M.counts([nf * k // n for k in range(1, n)], truth[v]))

    out = ["# Scene segmentation: richer classical features, leave-one-video-out", "",
           "Parameters (tau, lam_new, mu, lam_scene, max_phases; "
           f"{len(GRID)} combinations) are chosen on 9 videos and scored on the 10th. Pooled over all 10 held-out "
           "videos (116 true boundaries). 95% interval resamples whole videos.", "",
           "| features | F1 @1 s | F1 @2 s | F1 @5 s | P / R @2 s | predicted / true scenes | F1@2 s 95% interval |",
           "|---|---|---|---|---|---|---|"]
    js = {}
    ntrue_sc = sum(len(M.load_gt(v)[0]) for v in L.VIDEOS)
    for f in FEATURES:
        h = summary[f]["held"]
        P, R, F2 = M.pooled(h, "2s")
        lo, hi = M.bootstrap_ci(h, "2s")
        npred = sum(c["2s"][1] for c in h) + len(L.VIDEOS)      # + first scene of each video
        tag = "**" if f == MAIN else ""
        out.append(f"| {tag}{f}{tag} | {M.pooled(h,'1s')[2]:.3f} | {tag}{F2:.3f}{tag} | {M.pooled(h,'5s')[2]:.3f} | "
                   f"{P:.2f} / {R:.2f} | {npred} / {ntrue_sc} | {lo:.2f} - {hi:.2f} |")
        js[f] = dict(f1_1s=M.pooled(h, "1s")[2], f1_2s=F2, f1_5s=M.pooled(h, "5s")[2], P2=P, R2=R,
                     ci2=[lo, hi], pred_scenes=npred,
                     insample_f1_2s=M.pooled(summary[f]["insample"], "2s")[2])
    for name, cl in (("baseline: every detected cut = boundary", allc),
                     ("baseline: evenly spaced, true #scenes", uni)):
        P, R, F2 = M.pooled(cl, "2s")
        lo, hi = M.bootstrap_ci(cl, "2s")
        out.append(f"| *{name}* | {M.pooled(cl,'1s')[2]:.3f} | {F2:.3f} | {M.pooled(cl,'5s')[2]:.3f} | "
                   f"{P:.2f} / {R:.2f} | - | {lo:.2f} - {hi:.2f} |")
        js[name] = dict(f1_1s=M.pooled(cl, "1s")[2], f1_2s=F2, f1_5s=M.pooled(cl, "5s")[2], P2=P, R2=R, ci2=[lo, hi])
    out += ["", "## Optimistic reference (parameters chosen on all 10 videos, scored on the same 10 - do NOT quote)", "",
            "| features | F1 @2 s in-sample | F1 @2 s held-out | gap |", "|---|---|---|---|"]
    for f in FEATURES:
        a, b = js[f]["insample_f1_2s"], js[f]["f1_2s"]
        out.append(f"| {f} | {a:.3f} | {b:.3f} | {a-b:+.3f} |")
    out += ["", "## Parameter stability across folds (main method)", ""]
    ch = picks[MAIN]
    for key in ("tau", "lam_scene", "mu", "max_phases"):
        vals = [GRID[c][key] for c in ch]
        out.append(f"- {key}: " + ", ".join(str(x) for x in vals))
    open(os.path.join(M.ROOT, "results", "scene_cv.md"), "w", encoding="utf-8").write("\n".join(out))
    json.dump(js, open(os.path.join(M.ROOT, "results", "scene_cv.json"), "w"), indent=1)
    print("\n".join(out))


if __name__ == "__main__":
    main()

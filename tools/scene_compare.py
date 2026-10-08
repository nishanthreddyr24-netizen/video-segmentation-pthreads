"""Classical scene-detection comparison under one protocol (leave-one-video-out):
  DP      : our simplified Liu et al. shot-thread dynamic programme (C code)
  Spectral: spectral clustering of the shot-similarity matrix with a temporal kernel
            (the simple baseline of Baraldi et al. 2015, which matched or beat two published
            classical methods on BBC Planet Earth)
Parameters are chosen on 9 videos by pooled F1@2 s and scored on the 10th.
usage: python tools/scene_compare.py   -> results/scene_compare.md / .json"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.linalg import eigh
from sklearn.cluster import KMeans

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L       # noqa: E402
import scene_metrics as M   # noqa: E402
from scene_cv import FEATURES, GRID  # noqa: E402

ROWS = ["legacy: mean global hist (old method)", "global hist, 1 keyframe",
        "FULL: global + spatial + edge, 3 keyframes"]
SGRID = [dict(r=r, tau=t, sig=s) for r, t, s in itertools.product(
    (0.04, 0.06, 0.08, 0.10, 0.13, 0.17, 0.22), (20, 40, 80, 160), (0.5, 1.0, 2.0))]


def dist_matrix(kf, klo, khi, w):
    """ns x ns shot distance: weighted blocks of cell-wise chi-square, min over keyframe pairs
    (same definition as the C code)."""
    kf = kf[:, klo:khi]
    ns, K = kf.shape[:2]
    D = np.zeros((ns, ns))
    for blk in range(3):
        if w[blk] <= 0:
            continue
        o, nc, nb = L.OFF[blk], L.NCELLS[blk], L.BINS[blk]
        X = kf[:, :, o:o + nc * nb].reshape(ns, K, nc, nb).astype(np.float64)
        Db = np.zeros((ns, ns))
        for i in range(ns):
            a = X[i][:, None, None]                      # K,1,1,c,b
            s = a + X[None]                              # K,ns,K,c,b
            num = (a - X[None]) ** 2
            chi = 0.5 * np.where(s > 1e-9, num / np.where(s > 1e-9, s, 1), 0).sum(-1).mean(-1)
            Db[i] = chi.min(axis=(0, 2))
        D += w[blk] * Db
    return D / sum(w)


def spectral_scenes(D, centres_s, p):
    ns = D.shape[0]
    k = int(min(max(2, round(p["r"] * ns)), ns - 1))
    sig = p["sig"] * np.median(D[np.triu_indices(ns, 1)]) + 1e-9
    dt = centres_s[:, None] - centres_s[None, :]
    W = np.exp(-(D ** 2) / (2 * sig ** 2)) * np.exp(-(dt ** 2) / (2 * p["tau"] ** 2))
    np.fill_diagonal(W, 0)
    deg = W.sum(1) + 1e-12
    Ls = np.eye(ns) - W / np.sqrt(deg[:, None] * deg[None, :])
    _, vec = eigh(Ls, subset_by_index=[0, k - 1])
    vec /= np.linalg.norm(vec, axis=1, keepdims=True) + 1e-12
    lab = KMeans(k, n_init=5, random_state=0).fit_predict(vec)
    return [i for i in range(1, ns) if lab[i] != lab[i - 1]]      # first shot of each new scene


def _feat(v, fname):
    src, klo, khi, w = FEATURES[fname]
    c = L.load_cache(v)
    kf = L.legacy_kf(c) if src == "legacy" else c["kf"]
    return c, kf, klo, khi, w


def dp_task(args):
    fname, v = args
    c, kf, klo, khi, w = _feat(v, fname)
    return fname, v, [L.run_scenes(c, kf, klo, khi, w, p) for p in GRID]


def sp_task(args):
    fname, v = args
    c, kf, klo, khi, w = _feat(v, fname)
    D = dist_matrix(kf, klo, khi, w)
    centres = (c["starts"] + c["ends"]) / 2.0 / M.FPS
    return fname, v, [[int(c["starts"][i]) for i in spectral_scenes(D, centres, p)] for p in SGRID]


def lovo(preds, ncfg, gts, nfr):
    """preds[v][cfg] = predicted scene-start frames. Returns held-out counts, mean M_iou, #scenes."""
    held, mi, npred = [], [], 0
    cnt = {v: [M.counts(preds[v][c], gts[v][1]) for c in range(ncfg)] for v in L.VIDEOS}
    for v in L.VIDEOS:
        train = [u for u in L.VIDEOS if u != v]
        sc = [M.pooled([cnt[u][c] for u in train], "2s")[2] for c in range(ncfg)]
        b = int(np.argmax(sc))
        held.append(cnt[v][b])
        mi.append(M.miou(preds[v][b], gts[v][0], nfr[v]))
        npred += len(preds[v][b]) + 1
    return held, float(np.mean(mi)), npred


def main():
    for v in L.VIDEOS:
        L.build_cache(v)
    gts = {v: M.load_gt(v) for v in L.VIDEOS}
    caches = {v: L.load_cache(v) for v in L.VIDEOS}
    nfr = {v: caches[v]["nframes"] for v in L.VIDEOS}
    rows = {}
    with ProcessPoolExecutor(max_workers=8) as ex:
        for kind, task, ncfg in (("DP (shot-thread)", dp_task, len(GRID)),
                                 ("Spectral clustering", sp_task, len(SGRID))):
            res = {f: {} for f in ROWS}
            for f, v, out in ex.map(task, [(f, v) for f in ROWS for v in L.VIDEOS]):
                res[f][v] = out
            for f in ROWS:
                held, mi, npred = lovo(res[f], ncfg, gts, nfr)
                rows[(kind, f)] = (held, mi, npred)
                print(kind, "|", f, round(M.pooled(held, "2s")[2], 3), flush=True)
    base = {}
    for name, pr in (("every detected cut = boundary", {v: caches[v]["starts"][1:].tolist() for v in L.VIDEOS}),
                     ("evenly spaced, true #scenes",
                      {v: [nfr[v] * k // len(gts[v][0]) for k in range(1, len(gts[v][0]))] for v in L.VIDEOS})):
        base[name] = ([M.counts(pr[v], gts[v][1]) for v in L.VIDEOS],
                      float(np.mean([M.miou(pr[v], gts[v][0], nfr[v]) for v in L.VIDEOS])))
    ntrue = sum(len(gts[v][0]) for v in L.VIDEOS)
    out = ["# Classical scene detection: DP vs spectral clustering, leave-one-video-out", "",
           f"Parameters chosen on 9 videos (DP: {len(GRID)} combinations; spectral: {len(SGRID)}), scored on the 10th. "
           "Pooled over 10 held-out videos (116 boundaries). M_iou is the mean per-video symmetric IoU measure "
           "of Baraldi et al. (2015).", "",
           "| method | features | F1 @1 s | F1 @2 s | F1 @5 s | F1@2 s interval | M_iou | pred / true scenes |",
           "|---|---|---|---|---|---|---|---|"]
    js = {}
    for (kind, f), (held, mi, npred) in rows.items():
        lo, hi = M.bootstrap_ci(held, "2s")
        out.append(f"| {kind} | {f} | {M.pooled(held,'1s')[2]:.3f} | {M.pooled(held,'2s')[2]:.3f} | "
                   f"{M.pooled(held,'5s')[2]:.3f} | {lo:.2f}-{hi:.2f} | {mi:.3f} | {npred} / {ntrue} |")
        js[f"{kind} | {f}"] = dict(f1_1s=M.pooled(held, "1s")[2], f1_2s=M.pooled(held, "2s")[2],
                                  f1_5s=M.pooled(held, "5s")[2], ci2=[lo, hi], miou=mi, pred=npred)
    for name, (held, mi) in base.items():
        lo, hi = M.bootstrap_ci(held, "2s")
        out.append(f"| *baseline* | *{name}* | {M.pooled(held,'1s')[2]:.3f} | {M.pooled(held,'2s')[2]:.3f} | "
                   f"{M.pooled(held,'5s')[2]:.3f} | {lo:.2f}-{hi:.2f} | {mi:.3f} | - |")
        js["baseline | " + name] = dict(f1_2s=M.pooled(held, "2s")[2], miou=mi)
    open(os.path.join(M.ROOT, "results", "scene_compare.md"), "w", encoding="utf-8").write("\n".join(out))
    json.dump(js, open(os.path.join(M.ROOT, "results", "scene_compare.json"), "w"), indent=1)
    print("\n".join(out))


if __name__ == "__main__":
    main()

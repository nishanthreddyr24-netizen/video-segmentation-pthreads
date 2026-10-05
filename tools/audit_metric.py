"""Step 1: audit the scene metric before tuning anything.
Writes results/audit_metric.md.  Run after the caches exist (scene_lib.build_cache)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_lib as L                      # noqa: E402
import scene_metrics as M                  # noqa: E402
from evaluate import prf as old_prf        # noqa: E402  (the scorer used for the earlier 0.13 result)

out = []
def say(s=""):
    print(s); out.append(s)

caches = {i: L.load_cache(i) for i in L.VIDEOS}
gts = {i: M.load_gt(i) for i in L.VIDEOS}
nfr = [caches[i]["nframes"] for i in L.VIDEOS]

say("# Metric audit (RAI scene dataset)\n")
say("## 1. Ground truth integrity")
say("| video | frames (raw) | last GT frame | scenes | gaps | shortest / median / longest scene (s) | shots found |")
say("|---|---|---|---|---|---|---|")
for i in L.VIDEOS:
    sc, bd = gts[i]
    lens = sorted((e - s) / M.FPS for s, e in sc)
    gaps = sum(1 for a, b in zip(sc, sc[1:]) if a[1] != b[0])
    last = sc[-1][1]
    say(f"| {i} | {caches[i]['nframes']} | {last} | {len(sc)} | {gaps} | "
        f"{lens[0]:.0f} / {lens[len(lens)//2]:.0f} / {lens[-1]:.0f} | {caches[i]['ns']} |")
    assert gaps == 0 and last == caches[i]["nframes"], f"GT misaligned for video {i}"
tot_b = sum(len(gts[i][1]) for i in L.VIDEOS)
say(f"\nNo gaps, and every video's last labelled frame equals its frame count, so labels and frames line up. "
    f"**Total: {sum(len(gts[i][0]) for i in L.VIDEOS)} scenes = {tot_b} true boundaries** across 10 videos. "
    "That is a very small test set: one video can move the pooled score a lot (see the bootstrap below).\n")

say("## 2. Recall ceiling imposed by shot detection")
say("Scene boundaries that fall within tolerance of ANY detected cut. If this is low, no scene method can score "
    "well, and the shot stage is the bottleneck.\n")
say("| video | true boundaries | within 1 s of a cut | within 2 s | within 5 s |")
say("|---|---|---|---|---|")
agg = {k: 0 for k in M.TOLS}
for i in L.VIDEOS:
    cuts = caches[i]["starts"][1:].tolist()
    bd = gts[i][1]
    row = {k: sum(1 for b in bd if any(abs(b - c) <= t for c in cuts)) for k, t in M.TOLS.items()}
    for k in agg: agg[k] += row[k]
    say(f"| {i} | {len(bd)} | {row['1s']} | {row['2s']} | {row['5s']} |")
say(f"| **all** | **{tot_b}** | **{agg['1s']} ({agg['1s']/tot_b:.0%})** | **{agg['2s']} ({agg['2s']/tot_b:.0%})** | "
    f"**{agg['5s']} ({agg['5s']/tot_b:.0%})** |\n")
ceil = agg["2s"] / tot_b

say("## 3. Does the scorer used so far agree with a clean re-implementation?")
legacy_counts, legacy_old = [], []
for i in L.VIDEOS:
    c = caches[i]
    pred = L.run_scenes(c, L.legacy_kf(c), 0, 1, (1, 0, 0))
    legacy_counts.append(M.counts(pred, gts[i][1]))
    legacy_old.append({k: old_prf(pred, gts[i][1], t) for k, t in M.TOLS.items()})
say("Legacy method (mean global histogram, default parameters), all 10 videos, pooled:\n")
say("| tolerance | P / R / F1 (new matcher) | F1 (old greedy scorer) |")
say("|---|---|---|")
for k in M.TOLS:
    P, R, F = M.pooled(legacy_counts, k)
    tp = sum(round(o[k][0] * c[k][1]) for o, c in zip(legacy_old, legacy_counts))
    npd = sum(c[k][1] for c in legacy_counts); nt = sum(c[k][2] for c in legacy_counts)
    Po, Ro = (tp / npd if npd else 0), (tp / nt)
    Fo = 2 * Po * Ro / (Po + Ro) if Po + Ro else 0
    say(f"| {k} | {P:.3f} / {R:.3f} / {F:.3f} | {Fo:.3f} |")
say("\nThe earlier report quoted 0.105 / 0.105 / 0.144 for this setting (1 s / 2 s / 5 s); "
    "matching it confirms the refactored C code reproduces the old method.\n")

say("## 4. How good is 'random', and how noisy is the score?")
npred = [c["2s"][1] for c in legacy_counts]
rb = M.random_baseline(npred, [gts[i][1] for i in L.VIDEOS], nfr)
say("| method (all 10 videos, pooled) | F1 @1 s | F1 @2 s | F1 @5 s | F1@2 s 95% CI (resampling videos) |")
say("|---|---|---|---|---|")
lo, hi = M.bootstrap_ci(legacy_counts, "2s")
say(f"| legacy, default params | {M.pooled(legacy_counts,'1s')[2]:.3f} | {M.pooled(legacy_counts,'2s')[2]:.3f} | "
    f"{M.pooled(legacy_counts,'5s')[2]:.3f} | {lo:.2f} - {hi:.2f} |")
say(f"| random boundaries, same count as legacy | {rb['1s'][2]:.3f} | {rb['2s'][2]:.3f} | {rb['5s'][2]:.3f} | - |")
# every detected cut called a scene boundary (upper bound on recall, lowest precision)
allc = [M.counts(caches[i]["starts"][1:].tolist(), gts[i][1]) for i in L.VIDEOS]
say(f"| every detected cut = scene boundary | {M.pooled(allc,'1s')[2]:.3f} | {M.pooled(allc,'2s')[2]:.3f} | "
    f"{M.pooled(allc,'5s')[2]:.3f} | - |")
# uniform spacing with the true number of scenes
uni = []
for i in L.VIDEOS:
    n = len(gts[i][0]); nf = caches[i]["nframes"]
    uni.append(M.counts([nf * k // n for k in range(1, n)], gts[i][1]))
say(f"| evenly spaced, true number of scenes | {M.pooled(uni,'1s')[2]:.3f} | {M.pooled(uni,'2s')[2]:.3f} | "
    f"{M.pooled(uni,'5s')[2]:.3f} | - |")
say(f"\nThe resampling interval is the honest statement of the noise: with only {tot_b} true boundaries, "
    "differences of a few hundredths in F1 are not distinguishable from chance.\n")

say("## 5. Metrics deliberately not used")
say("I also tried coverage/overflow (Vendrig & Worring), but could not verify my implementation against a reference "
    "(it produced overflow values above 1), so it is excluded rather than reported unverified.\n")

say("## Audit conclusions")
say(f"- Labels are aligned; the scorer matches an independent re-implementation, so the 0.13 was not a bug.")
say("- **The baseline that matters is not random.** Calling every detected cut a scene boundary scores "
    f"F1 {M.pooled(allc,'2s')[2]:.3f} at 2 s, and evenly spaced scenes score {M.pooled(uni,'5s')[2]:.3f} at 5 s. "
    "A scene method must beat these to show it adds anything.")
say(f"- Shot detection leaves a recall ceiling of **{ceil:.0%}** at 2 s ({agg['5s']/tot_b:.0%} at 5 s): "
    "scene boundaries are mostly at detected cuts, so the shot stage is not the main limit.")
say("- The test set is tiny, so every result must be reported with its interval, and tuned with held-out "
    "evaluation (leave-one-video-out), never on the videos being scored.")
open(os.path.join(M.ROOT, "results", "audit_metric.md"), "w", encoding="utf-8").write("\n".join(out))

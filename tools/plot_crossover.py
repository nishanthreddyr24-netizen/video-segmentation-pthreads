"""Crossover study: at what job size does a FIXED number of threads beat a pure sequential loop?
usage: python tools/plot_crossover.py  -> results/os_study/crossover.png, crossover.md, crossover_summary.json"""
import csv
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "results", "os_study")
rows = list(csv.DictReader(open(os.path.join(D, "crossover.csv"))))
mn = defaultdict(dict)
md_ = defaultdict(dict)
for r in rows:
    mn[int(r["frames"])][r["config"]] = float(r["min_s"])
    md_[int(r["frames"])][r["config"]] = float(r["median_s"])
Ns = sorted(n for n in mn if n > 0)
Ps = sorted({int(c[1:]) for n in mn for c in mn[n] if c.startswith("P")})
FB = 160 * 90 * 3
col = {2: "#60a5fa", 4: "#2563eb", 8: "#7c3aed", 12: "#dc2626"}

# fixed cost of a parallel run: zero frames of work, P workers
O = {P: mn[0][f"P{P}"] for P in Ps}
t1 = np.mean([mn[n]["seq"] / n for n in Ns if n >= 1024])            # sequential seconds per frame at large sizes
S_inf = {P: np.mean([mn[n]["seq"] / mn[n][f"P{P}"] for n in Ns if n >= 4096]) for P in Ps}
model_N = {P: O[P] / (t1 * (1 - 1 / S_inf[P])) for P in Ps}


def crossing(P, thr=1.0):
    """smallest N from which the speedup stays above thr for every larger N"""
    sp = [(n, mn[n]["seq"] / mn[n][f"P{P}"]) for n in Ns]
    for i in range(len(sp)):
        if all(s > thr for _, s in sp[i:]):
            return sp[i][0]
    return None


fig, ax = plt.subplots(1, 3, figsize=(16, 4.9))
a = ax[0]
for P in Ps:
    a.plot(Ns, [mn[n]["seq"] / mn[n][f"P{P}"] for n in Ns], "o-", ms=3, color=col[P], label=f"{P} workers")
    c = crossing(P)
    if c:
        a.axvline(c, color=col[P], lw=0.6, ls=":")
a.axhline(1, color="k", lw=1)
a.set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="speedup vs pure sequential loop", title="Break-even for a fixed worker count")
a.legend(fontsize=8)
a = ax[1]
a.plot(Ns, [N / mn[N]["seq"] for N in Ns], "k--", label="sequential")
for P in Ps:
    a.plot(Ns, [N / mn[N][f"P{P}"] for N in Ns], "o-", ms=3, color=col[P], label=f"{P} workers")
a.set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="throughput, frames/s", title="Throughput against job size")
a.legend(fontsize=8)
a = ax[2]
a.bar([str(P) for P in Ps], [O[P] * 1e6 for P in Ps], color=[col[P] for P in Ps])
a.set(xlabel="workers", ylabel="microseconds", title="Fixed cost of one parallel run (0 frames of work)")
for i, P in enumerate(Ps):
    a.text(i, O[P] * 1e6, f"{O[P] * 1e6:.0f}", ha="center", va="bottom", fontsize=8)
fig.suptitle("Crossover study (Device 2, 160x90 frames, best of 25 interleaved rounds; sequential = no thread created)", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(D, "crossover.png"), dpi=140)

md = ["| workers | fixed cost O(P) | break-even (first size from which threads win) | sequential work there | data there | 2x from | 90% of best speedup from | model prediction N* | best speedup |", "|---|---|---|---|---|---|---|---|---|"]
summ = {}
for P in Ps:
    c1 = crossing(P)
    c2 = crossing(P, 2.0)
    best = max(mn[n]["seq"] / mn[n][f"P{P}"] for n in Ns)
    c9 = next((n for n in Ns if all(mn[m]["seq"] / mn[m][f"P{P}"] >= 0.9 * best for m in Ns if m >= n)), None)
    md.append(f"| {P} | {O[P] * 1e6:.0f} us | {c1 if c1 else 'not reached'} frames | {mn[c1]['seq'] * 1e3:.2f} ms | {c1 * FB / 1e6:.2f} MB | {c2 or '-'} frames | {c9 or '-'} frames | {model_N[P]:.0f} frames | {best:.2f}x |" if c1 else
              f"| {P} | {O[P] * 1e6:.0f} us | not reached | - | - | - | - | {model_N[P]:.0f} | {best:.2f}x |")
    summ[P] = dict(fixed_cost_us=O[P] * 1e6, breakeven_frames=c1, two_x_frames=c2, ninety_pct_frames=c9, model_frames=model_N[P], best_speedup=best,
                   work_ms_at_breakeven=(mn[c1]["seq"] * 1e3 if c1 else None))
open(os.path.join(D, "crossover.md"), "w").write("\n".join(md) + f"\n\nSequential time per frame at large sizes: {t1 * 1e6:.1f} us. Model: N* = O(P) / (t1 x (1 - 1/S)), S = speedup at large sizes.\n")
json.dump(dict(t1_us=t1 * 1e6, per_P=summ), open(os.path.join(D, "crossover_summary.json"), "w"), indent=1)
print("\n".join(md))

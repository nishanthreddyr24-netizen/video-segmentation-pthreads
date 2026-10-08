"""Break-even (crossover) analysis: at what amount of data does threading beat sequential?
Reads sweep CSVs written by `osbench sweep` (format of tools/osbench.c):
    <dir>/sweep_<res>.csv      e.g. sweep_160.csv, sweep_32.csv
Writes <dir>/breakeven.png and <dir>/breakeven.md.   usage: python tools/plot_breakeven.py [dir]"""
import collections
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "os_study")
PCOL = {2: "#93c5fd", 4: "#3b82f6", 8: "#1d4ed8", 16: "#1e1b4b"}


def load(fn):
    d = collections.defaultdict(dict)
    res = None
    for l in open(fn):
        r = l.strip().split(",")
        if not r or r[0] == "os" or len(r) < 13:
            continue
        res = r[1]
        d[int(r[2])][(r[4], int(r[5]))] = float(r[6])
    return res, d


files = [f for f in sorted(glob.glob(os.path.join(D, "sw_win_*.csv"))) if "winhigh" not in f] or sorted(glob.glob(os.path.join(D, "sweep_*.csv")))
if not files:
    sys.exit("no sweep_*.csv in " + D)
files = sorted(files, key=lambda f: int("".join(c for c in os.path.basename(f) if c.isdigit()) or 0))
fig, axs = plt.subplots(1, len(files), figsize=(5.2 * len(files), 4.4), squeeze=False)
md = ["| frame size | threads first beat sequential at | sequential work then | >=2x from | >=4x from | best speedup (best worker count) |",
      "|---|---|---|---|---|---|"]
for ax, fn in zip(axs[0], files):
    res, d = load(fn)
    Ns = sorted(n for n in d if ("seq", 1) in d[n])
    for P in (2, 4, 8, 16):
        y = [d[n][("seq", 1)] / d[n][("A", P)] if ("A", P) in d[n] else np.nan for n in Ns]
        ax.plot(Ns, y, "o-", ms=3, color=PCOL[P], label=f"A, {P} workers")
    best = [max(d[n][("seq", 1)] / t for (m, P), t in d[n].items() if m == "A") for n in Ns]
    ax.plot(Ns, best, "k--", lw=1.5, label="A, best worker count")
    ax.axhline(1.0, color="red", lw=1)
    ax.set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="speedup vs sequential",
           title=f"Break-even, {res}")
    ax.legend(fontsize=7.5)

    def first(th):
        for n, b in zip(Ns, best):
            if b >= th:
                return n
        return None

    f1, f2, f4 = first(1.0), first(2.0), first(4.0)
    work = f"{d[f1][('seq', 1)] * 1e3:.2f} ms" if f1 else "-"
    md.append(f"| {res} | {f1 if f1 else 'not in range'} frames | {work} | {f2 or '-'} | {f4 or '-'} | "
              f"{max(best):.2f}x |")
fig.tight_layout()
fig.savefig(os.path.join(D, "breakeven.png"), dpi=140)
open(os.path.join(D, "breakeven.md"), "w").write("\n".join(md) + "\n\n'best worker count' picks, for each size, the worker count that happened to be fastest; "
                                                  "a fixed worker count does worse on small inputs.\n")
print("\n".join(md))

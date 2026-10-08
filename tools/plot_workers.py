"""Worker-thread level analysis.   usage: python tools/plot_workers.py [dir]
Reads <dir>/workers.csv (per-worker rows from `osstudy workers`) and <dir>/cpu_topology.csv.
Writes <dir>/workers.png and <dir>/workers.md.

For each configuration (CPU set, number of workers) it shows, per worker thread:
  - frames processed        (does dynamic chunk scheduling balance the load?)
  - busy time               (first chunk start -> last chunk end)
  - kernel share of its CPU time
  - how many different logical CPUs it ran on, and the share of chunks started on P vs E cores
"""
import csv
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "os_study")
topo = {int(r["logical"]): int(r["efficiency_class"]) for r in csv.DictReader(open(os.path.join(D, "cpu_topology.csv")))}
isP = lambda c: topo.get(c, 0) > 0

runs = defaultdict(lambda: defaultdict(list))        # (set,P) -> run -> [worker rows]
for r in csv.DictReader(open(os.path.join(D, "workers.csv"))):
    runs[(r["set"], int(r["P"]))][int(r["run"])].append(r)

cfgs = list(runs)
median_run = {}
for c in cfgs:                                       # representative run = the one with median wall time
    walls = sorted((float(v[0]["wall_s"]), k) for k, v in runs[c].items())
    median_run[c] = walls[len(walls) // 2][1]

NAME = {"all": "all 12 CPUs", "p8": "P-cores+HT", "core8": "1 thread/core", "p4": "4 P-cores", "e4": "4 E-cores",
        "c1": "ONE CPU", "c2": "2 P-cores", "c3": "3 P-cores"}
fig, ax = plt.subplots(2, 2, figsize=(14, 9))
md = ["| config | wall (median run, s) | frames/worker min-max | load imbalance (max/mean frames) | chunks started on P / E cores | distinct CPUs per worker (mean) | kernel share of CPU time |",
      "|---|---|---|---|---|---|---|"]
pos, labels = 0, []
for c in cfgs:
    rows = sorted(runs[c][median_run[c]], key=lambda r: int(r["worker"]))
    fr = np.array([int(r["frames"]) for r in rows], float)
    busy = np.array([float(r["busy_s"]) for r in rows])
    usr = np.array([float(r["user_s"]) for r in rows])
    ker = np.array([float(r["kernel_s"]) for r in rows])
    p_ch = e_ch = 0
    ncpu = []
    for r in rows:
        used = dict(tuple(map(int, kv.split(":"))) for kv in r["cpus"].split(";") if kv)
        ncpu.append(len(used))
        for cpu, n in used.items():
            if isP(cpu):
                p_ch += n
            else:
                e_ch += n
    x = np.arange(len(rows)) + pos
    ax[0, 0].bar(x, fr, color="#2563eb")
    ax[0, 1].bar(x, busy * 1e3, color="#059669")
    ax[1, 0].bar(x, 100 * ker / (usr + ker + 1e-12), color="#d97706")
    ax[1, 1].bar(x, ncpu, color="#7c3aed")
    labels.append((pos + len(rows) / 2 - 0.5, f"{NAME.get(c[0], c[0])}\n{c[1]} workers"))
    tot = p_ch + e_ch
    md.append(f"| {NAME.get(c[0], c[0])}, {c[1]} workers | {float(rows[0]['wall_s']):.3f} | {int(fr.min())}-{int(fr.max())} | "
              f"{fr.max() / fr.mean():.2f} | {100 * p_ch / tot:.0f}% / {100 * e_ch / tot:.0f}% | {np.mean(ncpu):.1f} | "
              f"{100 * ker.sum() / (usr.sum() + ker.sum() + 1e-12):.0f}% |")
    pos += len(rows) + 1.5
for a, t, yl in ((ax[0, 0], "Frames processed per worker thread", "frames"), (ax[0, 1], "Busy time per worker (first chunk to last chunk)", "ms"),
                 (ax[1, 0], "Kernel share of each worker's CPU time", "%"), (ax[1, 1], "Distinct logical CPUs each worker ran on", "CPUs")):
    a.set_title(t, fontsize=11)
    a.set_ylabel(yl)
    a.set_xticks([p for p, _ in labels])
    a.set_xticklabels([l for _, l in labels], fontsize=7)
fig.suptitle("Worker-level analysis: dynamic chunk scheduling (4 chunks per worker), one bar per worker thread", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(D, "workers.png"), dpi=140)
open(os.path.join(D, "workers.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))

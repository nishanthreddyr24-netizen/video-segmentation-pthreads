"""Figures + tables for the OS-level study.   usage: python tools/plot_osstudy.py [dir]
Reads <dir>/cpu_topology.csv, cpuspeed.csv, scale_<set>.csv   (default results/os_study)
Writes <dir>/os_study.png, os_study_table.md, os_study_summary.txt"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "os_study")
SETS = {"all": "all 12 CPUs", "p8": "P-cores, 8 threads (HT)", "p4": "P-cores, 1 thread each (4)",
        "e4": "E-cores (4)", "core8": "1 thread per core (4P + 4E)",
        "c1": "ONE logical CPU", "c2": "2 P-cores", "c3": "3 P-cores"}
COL = {"all": "#2563eb", "p8": "#059669", "p4": "#7c3aed", "e4": "#d97706", "core8": "#dc2626", "c1": "#111827", "c2": "#0891b2", "c3": "#65a30d"}
VCOL = {"full": "#2563eb", "compute": "#059669", "io": "#d97706", "mmap": "#7c3aed"}


def rd(name):
    p = os.path.join(D, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


topo = {int(r["logical"]): r for r in rd("cpu_topology.csv")}
cs = {int(r["cpu"]): float(r["fps"]) * (float(r["median_s"]) / float(r["min_s"]) if os.environ.get("OS_STAT") == "min" else 1.0)
      for r in rd("cpuspeed.csv")}
scale = {}
for s in SETS:
    for r in rd(f"scale_{s}.csv"):
        scale[(s, r["variant"], int(r["P"]))] = r


def fps(s, v, P):
    r = scale.get((s, v, P))
    if not r:
        return np.nan
    f = float(r["fps"])
    if os.environ.get("OS_STAT") == "min":          # best-of-N estimate (robust mode)
        f *= float(r["median_s"]) / float(r["min_s"])
    return f


lines = []
# baseline for speedups: ONE worker on ONE performance core, other work idle  (set p4, P=1)
base = fps("p4", "full", 1)
fig, ax = plt.subplots(2, 2, figsize=(12.5, 9))

a = ax[0, 0]
cpus = sorted(cs)
cols = ["#2563eb" if int(topo[c]["efficiency_class"]) > 0 else "#d97706" for c in cpus]
a.bar([str(c) for c in cpus], [cs[c] / 1000 for c in cpus], color=cols)
a.set(xlabel="logical CPU the single worker is pinned to", ylabel="frames / s (thousand)",
      title="Speed of one thread on each logical CPU")
a.text(0.02, 0.95, "blue = P-core thread, orange = E-core", transform=a.transAxes, va="top", fontsize=9)
if cs:
    p_best = max(cs[c] for c in cpus if int(topo[c]["efficiency_class"]) > 0)
    e_best = max(cs[c] for c in cpus if int(topo[c]["efficiency_class"]) == 0)
    lines.append(f"Single-thread speed: best P-core thread {p_best:.0f} fps, best E-core {e_best:.0f} fps "
                 f"-> P is {p_best/e_best:.2f}x faster than E.")

a = ax[0, 1]
Ps = list(range(1, 13))
for s in SETS:
    y = [fps(s, "full", P) / base for P in Ps]
    if not np.all(np.isnan(y)):
        a.plot(Ps, y, "o-", color=COL[s], ms=4, label=SETS[s])
a.plot(Ps, Ps, ":", color="gray", label="ideal")
a.set(xlabel="workers", ylabel="speedup vs 1 worker on 1 P-core", title="Scaling inside each CPU set (full workload)")
a.legend(fontsize=7.5)

a = ax[1, 0]
for v in VCOL:
    y = [fps("all", v, P) / 1000 for P in Ps]
    if not np.all(np.isnan(y)):
        a.plot(Ps, y, "o-", color=VCOL[v], ms=4, label=v)
a.set(xlabel="workers (all 12 CPUs)", ylabel="throughput, thousand frames/s (log scale)",
      title="What limits scaling? full / compute only / read only / mmap", yscale="log")
a.legend(fontsize=8, title="variant")

a = ax[1, 1]
for v in ("full", "mmap"):
    ys = []
    for P in Ps:
        r = scale.get(("all", v, P))
        ys.append(100 * float(r["cpu_sys_s"]) / (float(r["cpu_user_s"]) + float(r["cpu_sys_s"]) + 1e-12) if r else np.nan)
    if not np.all(np.isnan(ys)):
        a.plot(Ps, ys, "o-", color=VCOL[v], ms=4, label=v)
a.set(xlabel="workers (all 12 CPUs)", ylabel="kernel share of CPU time, %", title="Time spent inside the OS kernel")
a.legend(fontsize=8)
fig.suptitle("OS-level study: chunked pthreads on a hybrid CPU (4 P-cores with hyper-threading + 4 E-cores)", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(D, "os_study.png"), dpi=140)

# table
hdr = ["workers"] + [f"{s}" for s in SETS]
rows = []
for P in Ps:
    rows.append([P] + [("" if np.isnan(fps(s, "full", P)) else f"{fps(s, 'full', P)/base:.2f}") for s in SETS])
with open(os.path.join(D, "os_study_table.md"), "w") as f:
    f.write("Speedup of the full workload vs one worker on one P-core (baseline %.0f fps)\n\n" % base)
    f.write("| " + " | ".join(hdr) + " |\n|" + "---|" * len(hdr) + "\n")
    for r in rows:
        f.write("| " + " | ".join(map(str, r)) + " |\n")
    f.write("\nVariant comparison, all 12 CPUs, frames/s\n\n| workers | full | compute | io | mmap |\n|---|---|---|---|---|\n")
    for P in Ps:
        f.write(f"| {P} | " + " | ".join(f"{fps('all', v, P):.0f}" for v in VCOL) + " |\n")
for s in SETS:
    ys = [fps(s, "full", P) / base for P in Ps]
    if not np.all(np.isnan(ys)):
        lines.append(f"{SETS[s]}: best speedup {np.nanmax(ys):.2f}x at {int(np.nanargmax(ys))+1} workers")
for v in VCOL:
    ys = [fps("all", v, P) / 1000 for P in Ps]
    if not np.all(np.isnan(ys)):
        lines.append(f"variant {v}: {ys[0]:.1f}k frames/s with 1 worker, {ys[-1]:.1f}k with 12 workers (best {np.nanmax(ys):.1f}k)")
open(os.path.join(D, "os_study_summary.txt"), "w").write("\n".join(lines))
print("\n".join(lines))

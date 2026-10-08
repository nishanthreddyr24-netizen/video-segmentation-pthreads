"""Turn results/study_raw.csv into the main figure + table.
Outputs: results/main_study.png, results/main_study_table.csv, results/main_study_table.md"""
import csv
import os
from collections import defaultdict
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.environ.get("STUDY_DIR") or os.path.join(ROOT, "results")

C_A, C_B, C_ID, C_AM = "#2563eb", "#d97706", "#6b7280", "#059669"

# ---- load: median seconds per (video, arch, workers) ------------------------
raw = defaultdict(list)
frames = {}
for r in csv.DictReader(open(os.path.join(RES, "study_raw.csv"))):
    raw[(r["video"], r["arch"], int(r["workers"]))].append(float(r["seconds"]))
    frames[r["video"]] = int(r["frames"])
STAT = min if os.environ.get("STUDY_STAT") == "min" else median      # best-of-N when measured on a busy machine
med = {k: STAT(v) for k, v in raw.items()}
BASE = "seqP" if any(k[1] == "seqP" for k in med) else "seq"   # pinned-to-P-core baseline if measured
videos = sorted({k[0] for k in med})
W = sorted({k[2] for k in med if k[1] == "a"})


def speedups(arch, vids):
    return np.array([[med[(v, BASE, 1)] / med[(v, arch, w)] for w in W] for v in vids])


SA = speedups("a", videos)                       # videos x workers
mean_s, lo_s, hi_s = SA.mean(0), SA.min(0), SA.max(0)
fps = np.array([[frames[v] / med[(v, "a", w)] for w in W] for v in videos]).mean(0)
fps_seq = np.mean([frames[v] / med[(v, BASE, 1)] for v in videos])
eff = mean_s / np.array(W)
Wf = np.array(W, float)
kf = np.where(Wf > 1, (1 / mean_s - 1 / Wf) / (1 - 1 / Wf), np.nan)     # Karp-Flatt

# Amdahl least-squares fit of the serial fraction s = 1-p on the measured means
grid = np.linspace(0, 0.5, 5001)
sse = [((1 / (s + (1 - s) / Wf) - mean_s) ** 2).sum() for s in grid]
s_fit = grid[int(np.argmin(sse))]
amdahl = 1 / (s_fit + (1 - s_fit) / Wf)

# B (short comparison): only recorded for the BBB video
SB = np.array([med[("bbb", BASE, 1)] / med[("bbb", "b", w)] for w in W]) if ("bbb", "b", 1) in med else None
SA_bbb = np.array([med[("bbb", BASE, 1)] / med[("bbb", "a", w)] for w in W])

# ---- figure -----------------------------------------------------------------
fig, ax = plt.subplots(2, 2, figsize=(12, 8.5))
a = ax[0, 0]
for row in SA:
    a.plot(W, row, color=C_A, alpha=.18, lw=1)
a.fill_between(W, lo_s, hi_s, color=C_A, alpha=.12, label="min-max over 11 videos")
a.plot(W, mean_s, "o-", color=C_A, lw=2.2, label="A: data parallel (mean of 11 videos)")
a.plot(W, Wf, ":", color=C_ID, label="ideal (linear)")
a.plot(W, amdahl, "--", color=C_AM, label=f"Amdahl fit, serial fraction = {s_fit:.3f}")
if SB is not None:
    a.plot(W, SB, "s--", color=C_B, lw=1.5, ms=4, label="B: pipeline (Big Buck Bunny only)")
a.axvline(8, color="k", lw=.6, alpha=.4); a.text(8.1, 0.6, "8 physical\ncores", fontsize=8)
a.set(xlabel="number of workers (threads)", ylabel="speedup vs single-threaded baseline",
      title="Speedup", xlim=(1, 12), ylim=(0, 12.5))
a.legend(fontsize=8, loc="upper left")

a = ax[0, 1]
a.plot(W, fps / 1000, "o-", color=C_A, lw=2.2)
a.axhline(fps_seq / 1000, color=C_ID, ls=":", label=f"single-threaded baseline ({'pinned to a P-core' if BASE == 'seqP' else 'unpinned'}, {fps_seq/1000:.1f}k fps)")
a.set(xlabel="number of workers (threads)", ylabel="throughput, thousand frames / s",
      title="Throughput (mean of 11 videos)", xlim=(1, 12), ylim=(0, None))
a.legend(fontsize=8)

a = ax[1, 0]
a.plot(W, eff * 100, "o-", color=C_A, lw=2.2)
a.axhline(100, color=C_ID, ls=":")
a.set(xlabel="number of workers (threads)", ylabel="parallel efficiency, % (speedup / workers)",
      title="Efficiency", xlim=(1, 12), ylim=(0, 110))

a = ax[1, 1]
a.plot(W[1:], kf[1:] * 100, "o-", color=C_A, lw=2.2)
a.axhline(s_fit * 100, color=C_AM, ls="--", label="constant serial fraction (Amdahl fit)")
a.set(xlabel="number of workers (threads)", ylabel="Karp-Flatt serial fraction, %",
      title="Karp-Flatt metric: rising = overhead / contention", xlim=(1, 12), ylim=(0, None))
a.legend(fontsize=8)
fig.suptitle("Main study - Architecture A (chunk-based data parallelism, pthreads)", fontsize=13)
fig.tight_layout()
fig.savefig(os.path.join(RES, "main_study.png"), dpi=140)

# ---- table ------------------------------------------------------------------
t_mean = np.array([[med[(v, "a", w)] for w in W] for v in videos]).mean(0)
rows = [[w, round(t, 4), round(fps_w), round(s, 2), round(lo, 2), round(hi, 2),
         round(e * 100), None if np.isnan(k) else round(k * 100, 1)]
        for w, t, fps_w, s, lo, hi, e, k in zip(W, t_mean, fps, mean_s, lo_s, hi_s, eff, kf)]
hdr = ["workers", "mean_seconds", "frames_per_s", "speedup", "speedup_min", "speedup_max",
       "efficiency_pct", "karp_flatt_pct"]
with open(os.path.join(RES, "main_study_table.csv"), "w", newline="") as f:
    csv.writer(f).writerows([hdr] + rows)
with open(os.path.join(RES, "main_study_table.md"), "w") as f:
    f.write("| " + " | ".join(hdr) + " |\n|" + "---|" * len(hdr) + "\n")
    for r in rows:
        f.write("| " + " | ".join("" if x is None else str(x) for x in r) + " |\n")
print(open(os.path.join(RES, "main_study_table.md")).read())
print(f"baseline sequential ({BASE}): {fps_seq:.0f} frames/s; Amdahl-fit serial fraction {s_fit:.4f}")
if BASE == "seqP":
    un = np.array([[med[(v, "seq", 1)] / med[(v, "a", w)] for w in W] for v in videos]).mean(0)
    ratio = np.mean([med[(v, "seq", 1)] / med[(v, "seqP", 1)] for v in videos])
    print(f"unpinned baseline is {ratio:.2f}x the pinned one; speedup at {W[-1]} workers: pinned {mean_s[-1]:.2f}x vs unpinned {un[-1]:.2f}x")
if SB is not None:
    print("B on BBB speedups:", np.round(SB, 2).tolist())
    print("A on BBB speedups:", np.round(SA_bbb, 2).tolist())

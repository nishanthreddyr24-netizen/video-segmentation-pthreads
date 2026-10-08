"""Figures and tables for the three studies the report centres on:
  readeff.png / readeff.md   how to read frames efficiently (Device 2)
  datasize.png / datasize.md throughput and speedup as the data size grows, both devices
  overhead.png / overhead.md fixed cost of a parallel run, chunk overhead, OS primitives, both devices
usage: python tools/plot_phase2.py"""
import collections
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda *p: os.path.join(ROOT, *p)
OUT = R("results", "os_study")
D1, D2 = R("results", "os_analysis"), R("results", "os_study", "device2")
C1, C2 = "#2563eb", "#dc2626"

# ------------------------------------------------------------------ 1 read efficiency (device 2)
rp = os.path.join(OUT, "readeff.csv")
if os.path.exists(rp):
    rows = list(csv.DictReader(open(rp)))
    N = 6000
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["variant"]][int(r["P"])] = r
    best = lambda v, P: N / float(by[v][P]["min_s"])
    ksh = lambda v, P: 100 * float(by[v][P]["cpu_sys_s"]) / (float(by[v][P]["cpu_user_s"]) + float(by[v][P]["cpu_sys_s"]) + 1e-12)
    label = {"full": "fread, 1 frame/call (current)", "fb4": "fread, 4 frames/call", "fb16": "fread, 16 frames/call", "fb64": "fread, 64 frames/call",
             "rf1": "ReadFile (sequential hint), 1/call", "rf16": "ReadFile (sequential hint), 16/call", "mmap": "memory-mapped",
             "mmappf": "memory-mapped + prefetch", "compute": "no file access (ceiling)"}
    show = [v for v in label if v in by]
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    cm = plt.get_cmap("tab10")
    a = ax[0, 0]
    for i, v in enumerate(show):
        a.plot(sorted(by[v]), [best(v, P) / 1000 for P in sorted(by[v])], "o-", ms=3, color=cm(i), ls="--" if v == "compute" else "-", label=label[v])
    a.set(xlabel="workers", ylabel="throughput, thousand frames/s (best of rounds)", title="Throughput by read strategy")
    a.legend(fontsize=7)
    a = ax[0, 1]
    P1 = [v for v in show if 1 in by[v]]
    a.barh(range(len(P1)), [best(v, 1) / 1000 for v in P1], color=[cm(show.index(v)) for v in P1])
    a.set_yticks(range(len(P1))); a.set_yticklabels([label[v] for v in P1], fontsize=7)
    a.set(xlabel="thousand frames/s, ONE worker", title="One worker: how much does the read path cost?")
    a = ax[1, 0]
    P8 = [v for v in show if 8 in by[v]]
    a.barh(range(len(P8)), [best(v, 8) / 1000 for v in P8], color=[cm(show.index(v)) for v in P8])
    a.set_yticks(range(len(P8))); a.set_yticklabels([label[v] for v in P8], fontsize=7)
    a.set(xlabel="thousand frames/s, 8 workers", title="Eight workers")
    a = ax[1, 1]
    for i, v in enumerate(show):
        if v == "compute":
            continue
        a.plot(sorted(by[v]), [ksh(v, P) for P in sorted(by[v])], "o-", ms=3, color=cm(i), label=label[v])
    a.set(xlabel="workers", ylabel="kernel share of CPU time, %", title="Time spent inside the OS kernel")
    a.legend(fontsize=6)
    fig.suptitle("Read efficiency (Device 2, 160x90 frames, 6000 frames, best of 12 interleaved rounds)", fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "readeff.png"), dpi=140)
    md = ["| read strategy | 1 worker (fps) | 4 workers | 8 workers | 12 workers | kernel share at 8 workers | best / ceiling at 8 |", "|---|---|---|---|---|---|---|"]
    for v in show:
        ceil = best("compute", 8) if "compute" in by and 8 in by["compute"] else float("nan")
        md.append(f"| {label[v]} | {best(v,1):.0f} | {best(v,4):.0f} | {best(v,8):.0f} | {best(v,12):.0f} | {ksh(v,8):.0f}% | {100*best(v,8)/ceil:.0f}% |")
    for v in ("io", "rfio16"):
        if v in by:
            md.append(f"| (read only, no compute) {v} | {best(v,1):.0f} | {best(v,4):.0f} | {best(v,8):.0f} | {best(v,12):.0f} | {ksh(v,8):.0f}% | - |")
    open(os.path.join(OUT, "readeff.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


# ------------------------------------------------------------------ 2 data size (both devices)
def sweep(path):
    t = collections.defaultdict(dict)
    if not os.path.exists(path):
        return None
    for l in open(path):
        r = l.strip().split(",")
        if len(r) >= 13 and r[0] != "os":
            t[int(r[2])][(r[4], int(r[5]))] = float(r[6])
    return t


fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
md = ["| device | frame size | frames | data (MB) | sequential fps | threaded fps (best P) | speedup | best P |", "|---|---|---|---|---|---|---|---|"]
for k, (res, w, h) in enumerate((("160", 160, 90), ("32", 32, 18))):
    for dev, d, col in ((1, D1, C1), (2, D2, C2)):
        t = sweep(os.path.join(d, f"sw_win_{res}.csv"))
        if not t:
            continue
        Ns = sorted(n for n in t if ("seq", 1) in t[n])
        seqf = [n / t[n][("seq", 1)] for n in Ns]
        parf = [max(n / v for (m, P), v in t[n].items() if m == "A") for n in Ns]
        ax[k].plot(Ns, seqf, "--", color=col, label=f"Device {dev} sequential")
        ax[k].plot(Ns, parf, "o-", ms=3.5, color=col, label=f"Device {dev} threaded (best worker count)")
        for n in Ns:
            if n in (1, 8, 64, 1024, 4096, 16384):
                bp = max(((n / v), P) for (m, P), v in t[n].items() if m == "A")
                md.append(f"| {dev} | {w}x{h} | {n} | {n * w * h * 3 / 1e6:.2f} | {n / t[n][('seq', 1)]:.0f} | {bp[0]:.0f} | {bp[0] * t[n][('seq', 1)] / n:.2f}x | {bp[1]} |")
    ax[k].set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="throughput, frames/s", title=f"{w}x{h} frames")
    ax[k].legend(fontsize=7)
a = ax[2]
for dev, d, col in ((1, D1, C1), (2, D2, C2)):
    t = sweep(os.path.join(d, "sw_win_160.csv"))
    if not t:
        continue
    Ns = sorted(n for n in t if ("seq", 1) in t[n])
    a.plot(Ns, [max(t[n][("seq", 1)] / v for (m, P), v in t[n].items() if m == "A") for n in Ns], "o-", ms=3.5, color=col, label=f"Device {dev}")
a.axhline(1, color="k", lw=0.8)
a.set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="speedup vs sequential (160x90)", title="Break-even")
a.legend(fontsize=8)
fig.suptitle("Data-size study: throughput and speedup as the job grows (Windows)", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "datasize.png"), dpi=140)
open(os.path.join(OUT, "datasize.md"), "w").write("\n".join(md) + "\n")

# ------------------------------------------------------------------ 3 overhead (both devices)
def acload(path):
    if not os.path.exists(path):
        return None
    d = collections.defaultdict(dict)
    for l in open(path):
        r = l.strip().split(",")
        if len(r) >= 10 and r[0] != "os":
            d[(int(r[1]), int(r[2]), int(r[3]))] = dict(total=float(r[6]), par=float(r[7]), thr=float(r[8]), seq=float(r[9]), redundant=int(r[5]))
    return d


def prims(path):
    return {l.split(",")[0]: float(l.split(",")[1]) for l in open(path) if "," in l} if os.path.exists(path) else {}


fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
md = ["| device | fixed cost of one parallel run (a + b x workers, us) | create+join 1 thread (us) | create+join 8 threads (us) | fopen+fclose (us) | mutex uncontended (ns) |", "|---|---|---|---|---|---|"]
for dev, d, col in ((1, D1, C1), (2, D2, C2)):
    ac = acload(os.path.join(d, "ac_win.csv"))
    pr = prims(os.path.join(d, "prims_win.csv"))
    fit = "-"
    if ac:
        Ps = sorted({P for (n, P, c) in ac if n == 0 and c == 4})
        ys = [ac[(0, P, 4)]["total"] * 1e6 for P in Ps]
        ax[0].plot(Ps, ys, "o-", color=col, label=f"Device {dev}")
        if len(Ps) > 1:
            b, a_ = np.polyfit(Ps, ys, 1)
            fit = f"{a_:.0f} + {b:.0f} x P"
            ax[0].plot(Ps, [a_ + b * P for P in Ps], ":", color=col)
        # chunk-count study at 1024 frames, 8 workers
        cs = sorted({c for (n, P, c) in ac if n == 1024 and P == 8})
        if cs:
            ax[1].plot(cs, [ac[(1024, 8, c)]["seq"] / ac[(1024, 8, c)]["total"] for c in cs], "o-", color=col, label=f"Device {dev}")
    md.append(f"| {dev} | {fit} | {pr.get('thread_create_join_us', float('nan')):.0f} | {pr.get('spawn_join_8_threads_us', float('nan')):.0f} | "
              f"{pr.get('fopen_fclose_us', float('nan')):.0f} | {pr.get('mutex_uncontended_ns', float('nan')):.0f} |")
ax[0].set(xlabel="workers", ylabel="microseconds", title="Fixed cost of one parallel run (zero frames of work)")
ax[0].legend(fontsize=8)
ax[1].set(xscale="log", xlabel="chunks per worker", ylabel="speedup vs sequential", title="Chunk count (1024 frames, 8 workers)")
ax[1].legend(fontsize=8)
keys = [("thread_create_join_us", "create+join\n1 thread (us)"), ("spawn_join_8_threads_us", "create+join\n8 threads (us)"), ("fopen_fclose_us", "fopen+fclose (us)"), ("condvar_handoff_us", "condvar\nhandoff (us)")]
w = 0.35
for i, (dev, d, col) in enumerate(((1, D1, C1), (2, D2, C2))):
    pr = prims(os.path.join(d, "prims_win.csv"))
    ax[2].bar(np.arange(len(keys)) + (i - 0.5) * w, [pr.get(k, np.nan) for k, _ in keys], w, color=col, label=f"Device {dev}")
ax[2].set_xticks(range(len(keys))); ax[2].set_xticklabels([l for _, l in keys], fontsize=7.5)
ax[2].set(title="OS primitive costs (Windows)", ylabel="microseconds")
ax[2].legend(fontsize=8)
fig.suptitle("Overhead study", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "overhead.png"), dpi=140)
open(os.path.join(OUT, "overhead.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))

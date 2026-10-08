"""Two-device comparison: device 1 = zhaymn's laptop (results/os_analysis), device 2 = this laptop.
usage: python tools/plot_devices.py [dev2_dir] [out_dir]
Writes <out_dir>/devices.png and devices.md"""
import collections
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D1 = os.path.join(ROOT, "results", "os_analysis")
D2 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "os_study", "device2")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(D2)
DEV = {1: "Device 1 (i5-13450HX, 6P+4E, 16 threads)", 2: "Device 2 (i5-12450HX, 4P+4E, 12 threads)"}
COL = {(1, "win"): "#2563eb", (1, "lin"): "#93c5fd", (2, "win"): "#dc2626", (2, "lin"): "#fca5a5"}
Ps = [2, 4, 6, 8, 12, 16]


def sweep(d, name):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    t = collections.defaultdict(dict)
    for l in open(p):
        r = l.strip().split(",")
        if len(r) < 13 or r[0] == "os":
            continue
        t[int(r[2])][(r[4], int(r[5]))] = float(r[6])
    return t


def best(t, n):
    s = t[n].get(("seq", 1))
    return max(s / v for (m, P), v in t[n].items() if m == "A") if s else np.nan


def first_win(t):
    for n in sorted(t):
        if ("seq", 1) in t[n] and best(t, n) > 1:
            return n, t[n][("seq", 1)]
    return None, None


def prims(d, name):
    p = os.path.join(d, name)
    return {l.split(",")[0]: float(l.split(",")[1]) for l in open(p) if "," in l} if os.path.exists(p) else {}


def ac_fit(d, name):
    """overhead of one parallel run with zero frames of work vs worker count: a + b*P (microseconds)"""
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return None
    pts = collections.defaultdict(list)
    for l in open(p):
        r = l.strip().split(",")
        if len(r) < 10 or r[0] == "os" or int(r[1]) != 0 or int(r[3]) != 4:
            continue
        pts[int(r[2])].append(float(r[6]) * 1e6)
    if len(pts) < 2:
        return None
    x = np.array(sorted(pts))
    y = np.array([np.median(pts[k]) for k in x])
    b, a = np.polyfit(x, y, 1)
    return a, b


fig, ax = plt.subplots(2, 2, figsize=(13, 9))
md = ["| quantity | Device 1 Win | Device 1 Linux | Device 2 Win | Device 2 Linux |", "|---|---|---|---|---|"]
data = {}
for dev, d in ((1, D1), (2, D2)):
    for osn, tag in (("win", "win"), ("lin", "lin")):
        data[(dev, tag)] = {res: sweep(d, f"sw_{tag}_{res}.csv") for res in ("160", "32")}
for k, (res, a) in enumerate((("160", ax[0, 0]), ("32", ax[0, 1]))):
    for (dev, tag), dd in data.items():
        t = dd.get(res)
        if not t:
            continue
        Ns = sorted(n for n in t if ("seq", 1) in t[n])
        a.plot(Ns, [best(t, n) for n in Ns], "o-" if tag == "win" else "s--", ms=3.5, color=COL[(dev, tag)],
               label=f"{DEV[dev].split(' (')[0]} {'Windows' if tag == 'win' else 'Linux (WSL2)'}")
    a.axhline(1, color="k", lw=0.8)
    a.set(xscale="log", yscale="log", xlabel="frames in the job", ylabel="speedup vs sequential (best worker count)",
          title=f"Break-even, {'160x90' if res == '160' else '32x18'} frames")
    a.legend(fontsize=7.5)
a = ax[1, 0]
for (dev, tag), dd in data.items():
    t = dd.get("160")
    if t and 4096 in t and ("seq", 1) in t[4096]:
        a.plot(Ps, [t[4096][("seq", 1)] / t[4096][("A", P)] for P in Ps], "o-" if tag == "win" else "s--", ms=4,
               color=COL[(dev, tag)], label=f"{DEV[dev].split(' (')[0]} {'Win' if tag == 'win' else 'Linux'}")
a.axvline(12, color="#2563eb", lw=0.6, ls=":"); a.text(12.1, 0.5, "dev1: 12 P-threads", fontsize=7, rotation=90)
a.axvline(8, color="#dc2626", lw=0.6, ls=":"); a.text(8.1, 0.5, "dev2: 8 P-threads", fontsize=7, rotation=90)
a.set(xlabel="workers", ylabel="speedup vs sequential", title="Scaling at 4096 frames of 160x90")
a.legend(fontsize=7.5)
a = ax[1, 1]
keys = [("thread_create_join_us", "create+join\n1 thread (us)"), ("spawn_join_8_threads_us", "create+join\n8 threads (us)"),
        ("fopen_fclose_us", "fopen+fclose (us)"), ("condvar_handoff_us", "condvar\nhandoff (us)"), ("mutex_uncontended_ns", "mutex\nuncontended (ns)")]
pr = {(1, "win"): prims(D1, "prims_win.csv"), (1, "lin"): prims(D1, "prims_lin.csv"),
      (2, "win"): prims(D2, "prims_win.csv"), (2, "lin"): prims(D2, "prims_lin.csv")}
w = 0.2
for i, ((dev, tag), p) in enumerate(pr.items()):
    a.bar(np.arange(len(keys)) + (i - 1.5) * w, [p.get(k, np.nan) for k, _ in keys], w, color=COL[(dev, tag)],
          label=f"dev{dev} {tag}")
a.set_xticks(range(len(keys)))
a.set_xticklabels([l for _, l in keys], fontsize=7.5)
a.set(yscale="log", title="OS primitive costs (log scale)")
a.legend(fontsize=7.5)
fig.suptitle("Same harness (zhaymn's osbench), two laptops", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "devices.png"), dpi=140)

cells = lambda f: [f(dev, tag) for dev in (1, 2) for tag in ("win", "lin")]
for res, nm in (("160", "160x90"), ("32", "32x18")):
    md.append("| first size where threads win (" + nm + ") | " + " | ".join(
        (lambda t: "-" if not t or first_win(t)[0] is None else f"{first_win(t)[0]} frames ({first_win(t)[1]*1e3:.2f} ms of work)")(
            data[(dev, tag)].get(res)) for dev in (1, 2) for tag in ("win", "lin")) + " |")
md.append("| speedup at 4096 frames, best worker count (160x90) | " + " | ".join(
    (lambda t: "-" if not t or 4096 not in t else f"{best(t, 4096):.2f}x")(data[(dev, tag)].get("160")) for dev in (1, 2) for tag in ("win", "lin")) + " |")
for k, lab in keys:
    md.append(f"| {lab.replace(chr(10), ' ')} | " + " | ".join(f"{pr[(dev, tag)].get(k, float('nan')):.2f}" for dev in (1, 2) for tag in ("win", "lin")) + " |")
fits = {(dev, tag): ac_fit(d, f"ac_{tag}.csv") for dev, d in ((1, D1), (2, D2)) for tag in ("win", "lin")}
md.append("| fixed cost of one parallel run: a + b*P (us) | " + " | ".join(
    "-" if not fits[(dev, tag)] else f"{fits[(dev, tag)][0]:.0f} + {fits[(dev, tag)][1]:.0f}*P" for dev in (1, 2) for tag in ("win", "lin")) + " |")
open(os.path.join(OUT, "devices.md"), "w").write("\n".join(md) + "\n")
print("\n".join(md))

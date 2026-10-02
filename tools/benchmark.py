"""Runs experiments 1-4 and 6, writes results/*.csv and results/*.png.
Timing = median of REPS runs after one warm-up (file cache warm)."""
import csv
import os
import re
import statistics as st
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
RES = os.path.join(ROOT, "results")
REPS = 5
CORES = os.cpu_count()
BBB = os.path.join(ROOT, "data", "bbb_160x90.raw")
PAT = re.compile(r"parallel-stage=([\d.]+)s threshold=([\d.]+)s total=([\d.]+)s")


def run(raw, w, h, mode, t, extra=None):
    cmd = [EXE, raw, str(w), str(h), mode, str(t)] + ([str(extra)] if extra else [])
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    p, th, tot = map(float, PAT.search(out).groups())
    return p, th, tot


def median_total(*a):
    run(*a)                                    # warm-up
    return st.median(run(*a)[2] for _ in range(REPS))


def write(name, header, rows):
    with open(os.path.join(RES, name), "w", newline="") as f:
        csv.writer(f).writerows([header] + rows)


def amdahl(p, P):
    return 1 / ((1 - p) + p / P)


def main():
    threads = sorted({1, 2, 4, 8, CORES})
    # ---- E1/E4: speedup vs threads, A and B, plus sequential baseline ----
    t_seq = median_total(BBB, 160, 90, "seq", 1)
    rows, sp = [], {"a": [], "b": []}
    for mode in ("a", "b"):
        for t in threads:
            tt = median_total(BBB, 160, 90, mode, t)
            sp[mode].append(t_seq / tt)
            rows.append([mode, t, round(tt, 4), round(t_seq / tt, 3),
                         round(t_seq / tt / t, 3)])
    write("e1_speedup.csv", ["arch", "threads", "seconds", "speedup", "efficiency"], rows)
    print("seq baseline", round(t_seq, 3), "s")
    for r in rows:
        print(r)

    # fit Amdahl's p to Architecture A's best measured speedup at P=4
    s4 = sp["a"][threads.index(4)]
    p_fit = (1 - 1 / s4) / (1 - 1 / 4)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(threads, threads, "k:", label="ideal")
    ax[0].plot(threads, [amdahl(min(p_fit, 0.999), t) for t in threads], "g--",
               label=f"Amdahl fit (p={p_fit:.3f})")
    ax[0].plot(threads, sp["a"], "o-", label="A: chunked")
    ax[0].plot(threads, sp["b"], "s-", label="B: pipeline")
    ax[0].set(xlabel="threads", ylabel="speedup vs sequential",
              title="E1/E4  Speedup (Big Buck Bunny 160x90, 14315 frames)")
    ax[0].legend()
    ax[1].plot(threads, [s / t for s, t in zip(sp["a"], threads)], "o-", label="A")
    ax[1].plot(threads, [s / t for s, t in zip(sp["b"], threads)], "s-", label="B")
    ax[1].set(xlabel="threads", ylabel="efficiency (speedup / threads)",
              title="Efficiency")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "e1_speedup.png"), dpi=130)

    # ---- E2: chunk granularity at 8 threads (chunks = cpt x threads) -----
    rows = []
    for cpt in (1, 4, 16, 64, 256):
        rows.append([cpt, round(median_total(BBB, 160, 90, "a", 8, cpt), 4)])
    write("e2_chunks.csv", ["chunks_per_thread", "seconds"], rows)
    print("E2", rows)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.semilogx([r[0] for r in rows], [r[1] for r in rows], "o-")
    ax.set(xlabel="chunks per thread (8 threads)", ylabel="seconds",
           title="E2  Chunk granularity")
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "e2_chunks.png"), dpi=130)

    # ---- E3: resolution scaling (1500 frames each) ------------------------
    rows = []
    for w, h in ((160, 90), (320, 180), (640, 360), (1280, 720)):
        raw = os.path.join(ROOT, "data", f"res_{w}x{h}.raw")
        ts = median_total(raw, w, h, "seq", 1)
        row = [f"{w}x{h}", round(ts, 4)]
        for mode in ("a", "b"):
            row.append(round(ts / median_total(raw, w, h, mode, 8), 3))
        rows.append(row)
    write("e3_resolution.csv", ["res", "seq_seconds", "speedupA_8t", "speedupB_8t"], rows)
    print("E3", rows)
    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.plot([r[0] for r in rows], [r[2] for r in rows], "o-", label="A (8 threads)")
    ax.plot([r[0] for r in rows], [r[3] for r in rows], "s-", label="B (8 threads)")
    ax.set(xlabel="resolution", ylabel="speedup", title="E3  Resolution scaling")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "e3_resolution.png"), dpi=130)

    # ---- E6: scene layer, serial fraction vs number of shots -------------
    rows = []
    for n in (1000, 10000, 100000, 1000000):
        for t in (1, 4, 8):
            out = subprocess.run([EXE, "scenebench", str(n), str(t), "3"],
                                 capture_output=True, text=True, check=True).stdout
            v = out.strip().split(",")
            sim, dp1, ph, dp2, tot = map(float, v[3:8])
            rows.append([n, t, round(sim, 6), round(dp1, 6), round(ph, 6),
                         round(dp2, 6), round(tot, 6),
                         round(100 * (dp1 + ph + dp2) / tot, 1)])
    write("e6_scenes.csv", ["shots", "threads", "t_similarity", "t_thread_dp",
                            "t_phases", "t_scene_dp", "total", "serial_pct"], rows)
    for r in rows:
        print("E6", r)
    fig, ax = plt.subplots(figsize=(6, 4))
    for t in (1, 4, 8):
        rr = [r for r in rows if r[1] == t]
        ax.semilogx([r[0] for r in rr], [r[7] for r in rr], "o-", label=f"{t} thread(s)")
    ax.set(xlabel="number of shots", ylabel="serial (DP) share of scene-layer time, %",
           title="E6  Serial fraction of the scene layer")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "e6_scenes.png"), dpi=130)


if __name__ == "__main__":
    main()

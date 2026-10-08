"""Main study: Architecture A (data parallelism), workers 1..12, real videos.
Writes results/study_raw.csv  (video, arch, workers, rep, seconds, frames)
Every configuration: 1 untimed warm-up + REPS timed runs.
Baselines: "seq" = single-threaded, left to the OS scheduler (original method);
           "seqP" = single-threaded, pinned to logical CPU 0 (a performance core with its
           hyper-thread sibling idle) - the fair best-case baseline on a hybrid CPU.
Refuses to run unless the machine is on AC power and quiet (tools/osstudy.exe env)."""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
SMOKE = os.environ.get("STUDY_SMOKE") == "1"          # plumbing test only, never for results
OUTDIR = os.environ.get("STUDY_DIR") or os.path.join(ROOT, "results")
OUT = os.path.join(OUTDIR, "study_raw.csv")
REPS = 2 if SMOKE else int(os.environ.get("STUDY_REPS", "5"))
WORKERS = [1, 2, 4] if SMOKE else list(range(1, 13))
PAT = re.compile(r"frames=(\d+) cuts=\d+\ntime: parallel-stage=[\d.]+s threshold=[\d.]+s total=([\d.]+)s")

VIDEOS = [("bbb", "bbb_160x90.raw")] + [(f"rai{i}", f"rai_{i}_160x90.raw") for i in range(1, 11)]
if SMOKE:
    VIDEOS = VIDEOS[:2]
elif os.environ.get("STUDY_NVIDEOS"):
    VIDEOS = VIDEOS[:int(os.environ["STUDY_NVIDEOS"])]


def baseline_mask():
    """Pin the single-threaded baseline to the FASTEST performance-core thread measured by the OS study
    (results/os_study/cpuspeed.csv, best-of-N), not to an arbitrary CPU: a slow baseline would inflate the speedup."""
    if os.environ.get("STUDY_BASE_MASK"):
        return os.environ["STUDY_BASE_MASK"]
    try:
        d = os.path.join(ROOT, "results", "os_study")
        topo = {int(r["logical"]): int(r["efficiency_class"]) for r in csv.DictReader(open(os.path.join(d, "cpu_topology.csv")))}
        sp = {int(r["cpu"]): float(r["min_s"]) for r in csv.DictReader(open(os.path.join(d, "cpuspeed.csv")))}
        best = min((t, c) for c, t in sp.items() if topo.get(c, 0) > 0)[1]
        os.makedirs(OUTDIR, exist_ok=True)
        open(os.path.join(OUTDIR, "baseline_cpu.txt"), "w").write(f"baseline pinned to logical CPU {best} (fastest P-core thread, best-of-N {sp[best]:.4f} s)")
        return format(1 << best, "x")
    except Exception:
        return "1"


def run(raw, mode, t, mask=None):
    env = {**os.environ, **({"SHOTSEG_AFFINITY": mask} if mask else {})}
    if os.environ.get("STUDY_PRIORITY") == "high":
        env["SHOTSEG_PRIORITY"] = "high"
    exe_mode = "seq" if mode == "seqP" else mode
    out = subprocess.run([EXE, os.path.join(ROOT, "data", raw), "160", "90", exe_mode, str(t)],
                         cwd=ROOT, capture_output=True, text=True, check=True, env=env).stdout
    m = PAT.search(out)
    return int(m.group(1)), float(m.group(2))


BASE_MASK = baseline_mask()


def measure(name, raw):
    rows = []
    configs = [("seq", 1), ("seqP", 1)] + [("a", t) for t in WORKERS]
    if name == "bbb":                       # short comparison only
        configs += [("b", t) for t in WORKERS]
    for mode, t in configs:
        mask = BASE_MASK if mode == "seqP" else None
        run(raw, mode, t, mask)             # warm-up
        for rep in range(REPS):
            n, sec = run(raw, mode, t, mask)
            rows.append([name, mode, t, rep, sec, n])
    return rows


def noisy(rows):
    """fraction of configurations whose slowest repetition is > 1.5x the fastest"""
    by = {}
    for r in rows:
        by.setdefault((r[1], r[2]), []).append(r[4])
    bad = sum(1 for v in by.values() if max(v) > 1.5 * min(v))
    return bad / len(by)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from quiet import wait_quiet
    rows = []
    for name, raw in VIDEOS:
        for attempt in range(3):
            if not SMOKE and "--force" not in sys.argv:
                wait_quiet(what=f"video {name}")
            vr = measure(name, raw)
            frac = noisy(vr)
            print(f"  {name}: {100 * frac:.0f}% noisy configs (attempt {attempt + 1})", flush=True)
            if frac < 0.25 or SMOKE or os.environ.get("STUDY_STAT") == "min":
                break
        rows += vr
        print("done", name, flush=True)
        with open(OUT, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["video", "arch", "workers", "rep", "seconds", "frames"])
            w.writerows(rows)


if __name__ == "__main__":
    main()

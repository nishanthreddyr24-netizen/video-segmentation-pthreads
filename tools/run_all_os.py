"""One command for the whole OS-level study on this machine (Windows, MinGW-w64).

    python tools/run_all_os.py            full study, ~45 min; needs AC power + a quiet machine
    python tools/run_all_os.py --level 1  ~18 min  essentials: topology, CPU-set scaling incl. single core, compute/io/mmap split, per-worker analysis, pinned-baseline main study (4 videos)
    python tools/run_all_os.py --level 2  ~25 min  + compute/io/mmap split, per-worker analysis, Windows replication of zhaymn (core sweeps)
    python tools/run_all_os.py --level 3  ~75 min  everything (default), incl. Linux/WSL2 and all frame sizes
    add --robust to any level: measure while you keep working (high priority, interleaved rounds, best-of-N);
    the laptop will feel sluggish for a few seconds at a time during the many-worker runs
    python tools/run_all_os.py --smoke    ~2 min plumbing test; numbers are NOT valid, written to results/_smoke

Steps
  1 build        shotseg, osstudy, cpu_topology, osbench (zhaymn's harness)
  2 gate         refuses to continue unless on AC power and background CPU load is low
  3 os study     CPU topology, per-CPU speed, scaling inside CPU sets x {full, compute, io, mmap}
  4 replication  zhaymn's complete harness re-run here (same sizes/resolutions/workers): crossover sweeps for 4
                 frame sizes, chunk/overhead study, OS primitive costs, Windows and Linux (WSL2) -> device 2
  5 main study   Architecture A, 1..12 workers, 11 videos, baseline pinned to a P-core
  3b per-worker  chunks, frames, busy time, user/kernel CPU time, CPUs visited, for each worker thread
  6 plots        results/os_study/os_study.png, workers.png, breakeven.png, results/main_study.png
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE = "--smoke" in sys.argv
ROBUST = "--robust" in sys.argv
if ROBUST:   # measure on a busy laptop: high priority, interleaved rounds, best-of-N
    os.environ.update(OS_PRIORITY="high", OS_MAXLOAD="101", OS_ROUNDS="15", OS_STAT="min",
                      STUDY_PRIORITY="high", STUDY_STAT="min", STUDY_REPS="7")
if "--maxload" in sys.argv:
    os.environ["OS_MAXLOAD"] = sys.argv[sys.argv.index("--maxload") + 1]
os.environ.setdefault("OS_MAXLOAD", "20")
LEVEL = int(sys.argv[sys.argv.index("--level") + 1]) if "--level" in sys.argv else 3
GCC_DIR = r"D:\tools\mingw64\bin"
ENV = {**os.environ, "PATH": GCC_DIR + os.pathsep + os.environ["PATH"]}
PY = sys.executable
OSB = os.path.join(ROOT, "tools", "osbench.exe")
OUT = os.path.join(ROOT, "results", "_smoke" if SMOKE else "os_study")
STUDY_DIR = os.path.join(ROOT, "results", "_smoke_study") if SMOKE else os.path.join(ROOT, "results")
T0 = time.time()
sys.path.insert(0, os.path.join(ROOT, "tools"))
from quiet import wait_quiet  # noqa: E402


def step(msg):
    print(f"\n=== [{(time.time() - T0) / 60:5.1f} min] {msg}", flush=True)


def run(args, env=None, out=None, check=True):
    kw = dict(cwd=ROOT, env=env or ENV, check=check)
    if out:
        with open(out, "w") as f:
            return subprocess.run(args, stdout=f, **kw)
    return subprocess.run(args, **kw)


def main():
    os.makedirs(OUT, exist_ok=True)
    step("1 build")
    C = ["c/common.c", "c/threshold.c", "c/seq.c", "c/arch_a.c", "c/arch_b.c"]
    run(["gcc", "-O2", "-Wall", "-Wextra", "-pthread", "-o", "c/shotseg.exe", "c/main.c", *C, "c/scenes.c",
         "c/scene_bench.c", "c/features.c", "-lm"])
    run(["gcc", "-O2", "-pthread", "-o", "tools/osstudy.exe", "tools/osstudy.c", "c/common.c", "-lm"])
    run(["gcc", "-O2", "-o", "tools/cpu_topology.exe", "tools/cpu_topology.c"])
    run(["gcc", "-O2", "-pthread", "-Ic", "-o", "tools/osbench.exe", "tools/osbench.c", *C, "-lm"])
    print("built")

    step("2 wait for an idle moment (AC power, background load < %s%%)" % os.environ["OS_MAXLOAD"])
    if SMOKE:
        print("(smoke mode: not waiting, results are not valid)")
    else:
        print(wait_quiet(what="start"))

    step("3 OS study: CPU sets x variants")
    env = {**ENV, "OS_OUT": OUT}
    if LEVEL == 1:
        env.update(OS_SETS="all,p4,e4,core8,c1", OS_VARIANTS="full", OS_VARIANTS_ALL="full,compute,io,mmap", OS_WRUNS="3")
    elif LEVEL == 2:
        env.update(OS_SETS="all,p4,e4,core8,c1")
    if SMOKE:
        env.update(OS_N="400", OS_SETS="all,p4,c1", OS_NOGATE="1", OS_WSMOKE="1", OS_WRUNS="2")
    run([PY, "tools/run_osstudy.py"], env=env)

    step("4 replicate zhaymn's whole OS study on this machine (Windows + Linux/WSL2) -> device 2")
    if LEVEL >= 2:
        run([PY, "tools/replicate_zhaymn.py"] + (["--smoke"] if SMOKE else []) + (["--level2"] if LEVEL == 2 else []))
    else:
        print("skipped at level 1 (zhaymn's published numbers are used for the second device)")

    step("5 main study with pinned baseline")
    env = {**ENV, "STUDY_DIR": STUDY_DIR}
    if LEVEL == 1:
        env["STUDY_NVIDEOS"] = "4"
    if SMOKE:
        env["STUDY_SMOKE"] = "1"
    os.makedirs(STUDY_DIR, exist_ok=True)
    run([PY, "tools/study.py"], env=env)

    step("6 plots")
    run([PY, "tools/plot_osstudy.py", OUT])
    if os.path.exists(os.path.join(OUT, "workers.csv")) and sum(1 for _ in open(os.path.join(OUT, "workers.csv"))) > 1:
        run([PY, "tools/plot_workers.py", OUT])
    if os.path.isdir(os.path.join(OUT, "device2")):
        run([PY, "tools/plot_breakeven.py", os.path.join(OUT, "device2")])
        run([PY, "tools/plot_devices.py", os.path.join(OUT, "device2"), OUT])
    run([PY, "tools/plot_study.py"], env=env)
    step("done. outputs in " + OUT + " and " + STUDY_DIR)


if __name__ == "__main__":
    main()

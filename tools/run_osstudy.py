"""Run the OS-level studies on this machine (Windows).  Writes results/os_study/*.csv

  1. cpu_topology     which logical CPU is a P-core / hyper-thread / E-core
  2. cpuspeed         single-thread speed on each logical CPU (pinned)
  3. scale_<set>      scaling 1..12 workers inside a CPU set, for 4 variants
                      (full / compute / io / mmap)  -> separates compute, file I/O and core type

Refuses to run unless the machine is on AC power and quiet.   usage: python tools/run_osstudy.py"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quiet import wait_quiet, check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "tools", "osstudy.exe")
RAW = os.path.join(ROOT, "data", "bbb_160x90.raw")
OUT = os.environ.get("OS_OUT") or os.path.join(ROOT, "results", "os_study")
N = os.environ.get("OS_N", "6000")
SETS = os.environ.get("OS_SETS", "all,p8,p4,e4,core8,c1,c2,c3").split(",")
NOGATE = os.environ.get("OS_NOGATE") == "1"          # plumbing test only
VARIANTS = os.environ.get("OS_VARIANTS", "full,compute,io,mmap")
WCONFIGS = [("all", 12), ("all", 8), ("p8", 8), ("core8", 8), ("p4", 4), ("e4", 4), ("c1", 4)]
WRUNS = int(os.environ.get("OS_WRUNS", "5"))


def noisy_fraction(path):
    import csv
    rows = list(csv.DictReader(open(path)))
    bad = [r for r in rows if float(r["p90_s"]) > 1.5 * float(r["min_s"])]
    return len(bad) / max(1, len(rows))


def sh(args, outfile):
    print(" ".join(os.path.basename(a) for a in args[:3]), "->", os.path.basename(outfile), flush=True)
    with open(outfile, "w") as f:
        subprocess.run(args, cwd=ROOT, stdout=f, check=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    line = "gate skipped" if NOGATE else wait_quiet(what="os study")
    print(line)
    open(os.path.join(OUT, "environment.txt"), "w").write(line + "\n")
    sh([os.path.join(ROOT, "tools", "cpu_topology.exe")], os.path.join(OUT, "cpu_topology.csv"))
    sh([EXE, "cpuspeed", RAW, "160", "90", N], os.path.join(OUT, "cpuspeed.csv"))
    for s in SETS:
        # re-check quiet between sets so a background job can't silently spoil one
        out = os.path.join(OUT, f"scale_{s}.csv")
        for attempt in range(3):          # a set that turns out noisy (you started working) is repeated
            if not NOGATE:
                wait_quiet(what=f"set {s}")
            variants = os.environ.get("OS_VARIANTS_ALL", VARIANTS) if s == "all" else VARIANTS
            rounds = os.environ.get("OS_ROUNDS")
            open(os.path.join(OUT, "load_log.txt"), "a").write(f"{s} before: {check(101)[1]}\n")
            if rounds:
                sh([EXE, "scalei", RAW, "160", "90", N, s, variants, "12", rounds], out)
            else:
                sh([EXE, "scale", RAW, "160", "90", N, s, variants, "12"], out)
            open(os.path.join(OUT, "load_log.txt"), "a").write(f"{s} after:  {check(101)[1]}\n")
            frac = noisy_fraction(out)
            print(f"   noise: {100 * frac:.0f}% of configurations had p90 > 1.5 x min", flush=True)
            if frac < 0.25 or NOGATE or os.environ.get("OS_STAT") == "min":
                break
            print("   too noisy, repeating this set", flush=True)
        open(os.path.join(OUT, "noise.txt"), "a").write(f"{s}: {100 * frac:.0f}% noisy configs, attempts={attempt + 1}\n")
    if WRUNS == 0:
        print("per-worker analysis skipped at this level")
        print("done")
        return
    # per-worker analysis: chunks/frames/busy/CPU time per thread and which CPUs it ran on
    rows = []
    for (st, P) in WCONFIGS if not os.environ.get("OS_WSMOKE") else WCONFIGS[:2]:
        for run in range(WRUNS):
            o = subprocess.run([EXE, "workers", RAW, "160", "90", N, st, str(P), "4", "1" if not rows else "0"],
                               cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip().splitlines()
            for line in o:
                if line.startswith("set,"):
                    hdr = line + ",run"
                    if not rows: rows.append(hdr)
                else:
                    rows.append(line + f",{run}")
    open(os.path.join(OUT, "workers.csv"), "w").write("\n".join(rows) + "\n")
    print("workers.csv:", len(rows) - 1, "worker rows")
    print("done")


if __name__ == "__main__":
    main()

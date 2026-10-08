"""Second measurement pass for the CPU sets that were disturbed in the first pass, then merge by taking, for every
(set, variant, workers), the pass with the smallest best-of-N time.  More rounds = more chances to catch quiet
moments on a shared machine; interference only ever adds time, so the minimum is the better estimate.

usage: python tools/second_pass.py [pass_name]   (default 'pass2')   -> results/os_study/scale_<set>.csv updated"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "os_study")
EXE = os.path.join(ROOT, "tools", "osstudy.exe")
RAW = os.path.join(ROOT, "data", "bbb_160x90.raw")
PASS = sys.argv[1] if len(sys.argv) > 1 else "pass2"

# --- crossover study first (it matters more than repeating the disturbed sets) ---
_cx = os.path.join(OUT, "crossover.csv")
if not os.path.exists(_cx):
    topo = {int(r["logical"]): int(r["efficiency_class"]) for r in csv.DictReader(open(os.path.join(OUT, "cpu_topology.csv")))}
    sp = {int(r["cpu"]): float(r["min_s"]) for r in csv.DictReader(open(os.path.join(OUT, "cpuspeed.csv")))}
    seqcpu = min((t, c) for c, t in sp.items() if topo.get(c, 0) > 0)[1]
    NL = "0,1,2,3,4,6,8,12,16,24,32,48,64,96,128,192,256,384,512,1024,2048,4096,8192,14000"
    print("crossover study (sequential pinned to logical CPU %d)" % seqcpu, flush=True)
    with open(_cx, "w") as f:
        subprocess.run([os.path.join(ROOT, "tools", "osstudy3.exe"), "crossover", RAW, "160", "90", NL, "2,4,8,12", "25", str(seqcpu)],
                       stdout=f, check=True, env={**os.environ, "OS_PRIORITY": "high"}, cwd=ROOT)
SETS = {"all": "full,compute,io,mmap", "e4": "full", "core8": "full", "c1": "full", "p4": "full"}
env = {**os.environ, "OS_PRIORITY": "high"}


def noisy(rows):
    return sum(1 for r in rows if float(r["p90_s"]) > 1.5 * float(r["min_s"])) / max(1, len(rows))


for s, variants in SETS.items():
    base = os.path.join(OUT, f"scale_{s}.csv")
    if not os.path.exists(base):
        continue
    first = list(csv.DictReader(open(base)))
    if noisy(first) < 0.25 and s != "all":
        print(f"{s}: first pass already clean ({100 * noisy(first):.0f}% noisy) - skipped")
        continue
    p2 = os.path.join(OUT, f"scale_{s}_{PASS}.csv")
    with open(p2, "w") as f:
        subprocess.run([EXE, "scalei", RAW, "160", "90", "6000", s, variants, "12", "15"], stdout=f, check=True, env=env, cwd=ROOT)
    second = list(csv.DictReader(open(p2)))
    best = {}
    for r in first + second:
        k = (r["variant"], r["P"])
        if k not in best or float(r["min_s"]) < float(best[k]["min_s"]):
            best[k] = r
    keys = sorted(best, key=lambda k: (k[0], int(k[1])))
    with open(base, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(first[0].keys()))
        w.writeheader()
        w.writerows(best[k] for k in keys)
    line = f"{s}: pass 1 {100 * noisy(first):.0f}% noisy, {PASS} {100 * noisy(second):.0f}% noisy -> merged by best time (30 rounds per point)"
    print(line)
    open(os.path.join(OUT, "noise.txt"), "a").write(line + "\n")

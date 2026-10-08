"""Phase 3: rerun the crossover study and the Device-2 data-size/overhead replication that were disturbed in phase 2,
with a sanity check (large-job speedup must show real multi-core scaling)."""
import csv
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "os_study")
ENV = {**os.environ, "OS_PRIORITY": "high", "OS_MAXLOAD": "101"}
RAW = os.path.join(ROOT, "data", "bbb_160x90.raw")
log = lambda m: print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)

topo = {int(r["logical"]): int(r["efficiency_class"]) for r in csv.DictReader(open(os.path.join(OUT, "cpu_topology.csv")))}
sp = {int(r["cpu"]): float(r["min_s"]) for r in csv.DictReader(open(os.path.join(OUT, "cpuspeed.csv")))}
seqcpu = min((t, c) for c, t in sp.items() if topo.get(c, 0) > 0)[1]
NL = "0,1,2,3,4,6,8,12,16,24,32,48,64,96,128,192,256,384,512,1024,2048,4096,8192,14000"
for attempt in range(3):
    log(f"crossover study, attempt {attempt + 1} (sequential pinned to CPU {seqcpu})")
    with open(os.path.join(OUT, "crossover.csv"), "w") as f:
        subprocess.run([os.path.join(ROOT, "tools", "osstudy3.exe"), "crossover", RAW, "160", "90", NL, "2,4,8,12", "25", str(seqcpu)],
                       stdout=f, check=True, env=ENV, cwd=ROOT)
    rows = {(int(r["frames"]), r["config"]): float(r["min_s"]) for r in csv.DictReader(open(os.path.join(OUT, "crossover.csv")))}
    s12 = rows[(14000, "seq")] / rows[(14000, "P12")]
    log(f"sanity: 12-worker speedup at 14000 frames = {s12:.2f}x (must be > 3.5x)")
    if s12 > 3.5:
        break
log("replication of data-size / overhead study (Windows, level 2)")
subprocess.run([sys.executable, "tools/replicate_zhaymn.py", "--level2"], check=True, env=ENV, cwd=ROOT)
log("phase 3 finished")

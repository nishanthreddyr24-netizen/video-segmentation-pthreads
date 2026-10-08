"""Phase 2 (run after run_all_os.py --level 1 --robust): the studies that matter most for the report.
  1 readeff   read-efficiency study: 11 ways of getting frames to the workers (stdio batch sizes, Win32 ReadFile,
              mmap, mmap+prefetch, compute-only ceiling, I/O-only) x 1..12 workers
  2 device-2 replication of zhaymn's data-size / overhead / OS-primitive study (Windows, level 2)
  3 second pass over the CPU sets that were disturbed (only if time remains)
usage: python tools/run_phase2.py [--deadline HH:MM]   (stages that would start after the deadline are skipped)"""
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "os_study")
EXE = os.path.join(ROOT, "tools", "osstudy2.exe")
RAW = os.path.join(ROOT, "data", "bbb_160x90.raw")
ENV = {**os.environ, "OS_PRIORITY": "high", "OS_MAXLOAD": "101"}
PY = sys.executable
deadline = None
if "--deadline" in sys.argv:
    h, m = sys.argv[sys.argv.index("--deadline") + 1].split(":")
    deadline = datetime.datetime.now().replace(hour=int(h), minute=int(m), second=0)


def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)


def can_start(est_min, name):
    if deadline and datetime.datetime.now() + datetime.timedelta(minutes=est_min) > deadline:
        log(f"SKIP {name}: would not finish before {deadline:%H:%M}")
        return False
    return True


VARS = "full,fb4,fb16,fb64,rf1,rf16,mmap,mmappf,compute,io,rfio16"
if can_start(7, "readeff"):
    log("1 read-efficiency study")
    with open(os.path.join(OUT, "readeff.csv"), "w") as f:
        subprocess.run([EXE, "scalei", RAW, "160", "90", "6000", "all", VARS, "12", "12"], stdout=f, check=True, env=ENV, cwd=ROOT)
if can_start(10, "replication"):
    log("2 replication of the data-size / overhead / primitive study on this laptop (Windows)")
    subprocess.run([PY, "tools/replicate_zhaymn.py", "--level2"], check=True, env=ENV, cwd=ROOT)
if can_start(12, "second pass"):
    log("3 second pass on disturbed sets")
    subprocess.run([PY, "tools/second_pass.py", "pass2"], check=True, env=ENV, cwd=ROOT)
log("phase 2 finished")

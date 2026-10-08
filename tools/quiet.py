"""wait_quiet(): block until the machine is on AC power and background CPU load is low for several
consecutive checks, then return.  Lets the OS study run in the gaps of a busy workday: each stage
waits for an idle moment instead of aborting, and nothing has to be closed.

Threshold: OS_MAXLOAD (percent of the whole CPU, default 20) - measured by `osstudy.exe env`.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDY = os.path.join(ROOT, "tools", "osstudy.exe")


def check(maxload):
    r = subprocess.run([STUDY, "env", str(maxload)], capture_output=True, text=True)
    first = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "(no output)"
    return r.returncode == 0, first


def wait_quiet(maxload=None, need=3, poll=10, timeout_h=8, what=""):
    """need = consecutive quiet checks (each check samples load for 2 s) before we go."""
    maxload = maxload if maxload is not None else float(os.environ.get("OS_MAXLOAD", "20"))
    t0, good, last = time.time(), 0, 0.0
    while True:
        ok, line = check(maxload)
        good = good + 1 if ok else 0
        if good >= need:
            return line
        if time.time() - t0 > timeout_h * 3600:
            sys.exit(f"gave up waiting for a quiet machine after {timeout_h} h")
        if time.time() - last > 60:
            print(f"  [{what}] waiting for a quiet moment: {line}  (limit {maxload:.0f}%) - resumes automatically",
                  flush=True)
            last = time.time()
        time.sleep(poll)

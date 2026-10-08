"""Replicate zhaymn's OS-level study (tools/osbench.c, results/os_analysis/) on THIS machine,
using exactly the same programs, sizes, resolutions and worker counts, so the two devices can be compared.
Writes the same file names as the original study into <out>/device2/ :
    sw_win_{32,160,640,1280}.csv  sw_winhigh_160.csv  ac_win.csv  prims_win.csv  frame_win.txt
    sw_lin_{32,160}.csv           ac_lin.csv          prims_lin.csv                (via WSL2, if available)

usage: python tools/replicate_zhaymn.py [--smoke] [--no-linux]
Refuses to run unless the machine is on AC power and quiet (except --smoke)."""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from quiet import wait_quiet  # noqa: E402
SMOKE = "--smoke" in sys.argv
LEVEL2 = "--level2" in sys.argv                      # Windows only, core sweeps (160x90, 32x18), prims, achunks
NOLIN = "--no-linux" in sys.argv or LEVEL2
OSB = os.path.join(ROOT, "tools", "osbench.exe")
STUDY = os.path.join(ROOT, "tools", "osstudy.exe")
OUT = os.path.join(ROOT, "results", "_smoke" if SMOKE else "os_study", "device2")
DATA = os.path.join(ROOT, "data", "os_rep_smoke" if SMOKE else "os_rep")
WSL = "Ubuntu-22.04"
T0 = time.time()

# sizes exactly as in the original study (frame counts per run)
if SMOKE:
    VID = {"32": (32, 18, 256), "160": (160, 90, 128), "640": (640, 360, 16), "1280": (1280, 720, 8)}
    LISTS = {"32": "1,16,256", "160": "1,8,64", "640": "1,4,16", "1280": "1,4,8", "high": "1,8,64"}
    AC = "0,4,64"
else:
    VID = {"32": (32, 18, 16384), "160": (160, 90, 16384), "640": (640, 360, 512), "1280": (1280, 720, 128)}
    LISTS = {"32": "1,4,16,64,256,1024,4096,16384",
             "160": "1,2,4,8,16,32,64,128,256,512,1024,4096,16384",
             "640": "1,2,4,8,16,32,64,128,512",
             "1280": "1,2,4,8,16,32,128",
             "high": "1,2,4,8,16,32,64,128,256,512,1024,2000"}
    AC = "0,4,8,16,32,64,128,256,1024,4096"
LIN_LISTS = dict(LISTS)
if not SMOKE:
    LIN_LISTS["160"] = "1,2,4,8,16,32,64,128,256,512,1024,4096"     # original Linux run stopped at 4096


def log(msg):
    print(f"[{(time.time() - T0) / 60:5.1f} min] {msg}", flush=True)


def gate():
    if not SMOKE:
        wait_quiet(what="replication")


def to_file(args, path, **kw):
    if os.environ.get("OS_PRIORITY") == "high" and "creationflags" not in kw:
        kw["creationflags"] = 0x00000080          # HIGH_PRIORITY_CLASS: run ahead of background work
    with open(path, "w") as f:
        subprocess.run(args, stdout=f, check=True, cwd=ROOT, **kw)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    log("generate synthetic videos (same generator as the original study)")
    raws = {}
    for k, (w, h, n) in VID.items():
        raws[k] = os.path.join(DATA, f"synth_{k}.raw")
        if not os.path.exists(raws[k]) or os.path.getsize(raws[k]) < w * h * 3 * n:
            subprocess.run([OSB, "gen", raws[k], str(w), str(h), str(n)], check=True, cwd=ROOT)

    if LEVEL2:
        VID.pop("640"); VID.pop("1280")
    log("Windows: OS primitive costs")
    gate()
    to_file([OSB, "prims", os.path.join(ROOT, "tools", "osbench.c")], os.path.join(OUT, "prims_win.csv"))
    to_file([OSB, "frame", raws["160"], "160", "90"], os.path.join(OUT, "frame_win.txt"))
    log("Windows: chunk-count / overhead study (achunks)")
    gate()
    to_file([OSB, "achunks", raws["160"], "160", "90", AC], os.path.join(OUT, "ac_win.csv"))
    for k in [k for k in ("160", "32", "640", "1280") if k in VID]:
        log(f"Windows: crossover sweep {VID[k][0]}x{VID[k][1]}")
        gate()
        to_file([OSB, "sweep", raws[k], str(VID[k][0]), str(VID[k][1]), LISTS[k]], os.path.join(OUT, f"sw_win_{k}.csv"))
    if LEVEL2:
        log("level 2: skipping 640/1280/high-priority runs and Linux")
        return
    log("Windows: crossover sweep 160x90 at HIGH priority")
    gate()
    to_file([OSB, "sweep", raws["160"], "160", "90", LISTS["high"]], os.path.join(OUT, "sw_winhigh_160.csv"),
            creationflags=0x00000080)   # HIGH_PRIORITY_CLASS

    if NOLIN:
        log("Linux part skipped (--no-linux)")
        return
    log("Linux (WSL2): build")
    wsl = ["wsl", "-d", WSL, "--"]
    work = "/tmp/osrep"
    src = "/mnt/" + ROOT[0].lower() + ROOT[2:].replace("\\", "/")
    sh = (f"set -e; rm -rf {work}; mkdir -p {work}; cd {work}; cp {src}/tools/osbench.c {src}/c/*.c {src}/c/*.h . ; "
          "rm -f main.c scenes.c scene_bench.c features.c scene_api.c; "
          "gcc -O2 -pthread -o osbench osbench.c common.c threshold.c seq.c arch_a.c arch_b.c -lm")
    subprocess.run(wsl + ["bash", "-c", sh], check=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    lin_raw = {}
    for k in ("160", "32"):
        w, h, n = VID[k]
        lin_raw[k] = f"{work}/synth_{k}.raw"
        subprocess.run(wsl + ["bash", "-c", f"cd {work} && ./osbench gen {lin_raw[k]} {w} {h} {n}"], check=True)

    def lin(cmd, outname):
        gate()
        out = subprocess.run(wsl + ["bash", "-c", f"cd {work} && {cmd}"], capture_output=True, text=True, check=True).stdout
        open(os.path.join(OUT, outname), "w").write(out)

    log("Linux: primitives + achunks")
    lin("./osbench prims osbench.c", "prims_lin.csv")
    lin(f"./osbench achunks {lin_raw['160']} 160 90 {AC}", "ac_lin.csv")
    for k in ("160", "32"):
        log(f"Linux: crossover sweep {VID[k][0]}x{VID[k][1]}")
        lin(f"./osbench sweep {lin_raw[k]} {VID[k][0]} {VID[k][1]} {LIN_LISTS[k]}", f"sw_lin_{k}.csv")
    subprocess.run(wsl + ["bash", "-c", f"rm -rf {work}"])
    log("done")


if __name__ == "__main__":
    main()

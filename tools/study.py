"""Main study: Architecture A (data parallelism), workers 1..12, real videos.
Writes results/study_raw.csv  (video, arch, workers, rep, seconds, frames)
Every configuration: 1 untimed warm-up + REPS timed runs."""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
OUT = os.path.join(ROOT, "results", "study_raw.csv")
REPS = 5
WORKERS = list(range(1, 13))
PAT = re.compile(r"frames=(\d+) cuts=\d+\ntime: parallel-stage=[\d.]+s threshold=[\d.]+s total=([\d.]+)s")

VIDEOS = [("bbb", "bbb_160x90.raw")] + [(f"rai{i}", f"rai_{i}_160x90.raw") for i in range(1, 11)]


def run(raw, mode, t):
    out = subprocess.run([EXE, os.path.join(ROOT, "data", raw), "160", "90", mode, str(t)],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    m = PAT.search(out)
    return int(m.group(1)), float(m.group(2))


def main():
    rows = []
    for name, raw in VIDEOS:
        configs = [("seq", 1)] + [("a", t) for t in WORKERS]
        if name == "bbb":                       # short comparison only
            configs += [("b", t) for t in WORKERS]
        for mode, t in configs:
            run(raw, mode, t)                   # warm-up
            for rep in range(REPS):
                n, sec = run(raw, mode, t)
                rows.append([name, mode, t, rep, sec, n])
        print("done", name, flush=True)
        with open(OUT, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["video", "arch", "workers", "rep", "seconds", "frames"])
            w.writerows(rows)


if __name__ == "__main__":
    main()

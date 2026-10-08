"""Collect every number the final report needs into results/report_data.json
(and prepare device-1 figures from zhaymn's CSVs).  Run before tools/make_final_report.js."""
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda *p: os.path.join(ROOT, *p)
D1 = R("results", "os_analysis")
OUT = {}


def sweep(path):
    t = defaultdict(dict)
    for l in open(path):
        r = l.strip().split(",")
        if len(r) >= 13 and r[0] != "os":
            t[int(r[2])][(r[4], int(r[5]))] = float(r[6])
    return t


def best(t, n):
    s = t[n].get(("seq", 1))
    a = [(s / v, P) for (m, P), v in t[n].items() if m == "A"]
    return max(a) if (s and a) else (float("nan"), 0)


# ---------------- device 1 (zhaymn) -----------------
rows = []
for res, nm in (("32", "32x18"), ("160", "160x90"), ("640", "640x360"), ("1280", "1280x720")):
    row = [nm]
    for tag in ("win", "lin"):
        p = os.path.join(D1, f"sw_{tag}_{res}.csv")
        if not os.path.exists(p):
            row += ["-", "-"]
            continue
        t = sweep(p)
        fw = next((n for n in sorted(t) if ("seq", 1) in t[n] and best(t, n)[0] > 1), None)
        row += [f"{fw} frames" if fw else "not reached", f"{t[fw][('seq', 1)] * 1e3:.2f} ms" if fw else "-"]
    t = sweep(os.path.join(D1, f"sw_win_{res}.csv"))
    nmax = max(n for n in t if ("seq", 1) in t[n])
    b = best(t, nmax)
    row += [f"{b[0]:.2f}x at {nmax} frames (P={b[1]})"]
    rows.append(row)
OUT["dev1_breakeven"] = rows
t = sweep(os.path.join(D1, "sw_win_160.csv"))
OUT["dev1_160_win"] = [[n, round(t[n][("seq", 1)] * 1e6), round(best(t, n)[0], 2), best(t, n)[1]] for n in sorted(t) if ("seq", 1) in t[n]]
t = sweep(os.path.join(D1, "sw_lin_160.csv"))
OUT["dev1_160_lin"] = [[n, round(t[n][("seq", 1)] * 1e6), round(best(t, n)[0], 2), best(t, n)[1]] for n in sorted(t) if ("seq", 1) in t[n]]
OUT["dev1_prims"] = {l.split(",")[0]: float(l.split(",")[1]) for l in open(os.path.join(D1, "prims_win.csv")) if "," in l}

# device-1 break-even figure (reuse plot_breakeven on copies, so zhaymn's folder stays untouched)
d1 = R("results", "os_study", "device1")
os.makedirs(d1, exist_ok=True)
for res in ("32", "160", "640", "1280"):
    shutil.copy(os.path.join(D1, f"sw_win_{res}.csv"), os.path.join(d1, f"sw_win_{res}.csv"))
subprocess.run([sys.executable, R("tools", "plot_breakeven.py"), d1], check=True, capture_output=True)

# ---------------- our device ------------------------
os_dir = R("results", "os_study")
OUT["dev2"] = {
    "os_study": os.path.exists(os.path.join(os_dir, "os_study.png")),
    "workers": os.path.exists(os.path.join(os_dir, "workers.png")),
    "devices": os.path.exists(os.path.join(os_dir, "devices.png")),
    "noise": open(os.path.join(os_dir, "noise.txt")).read().strip() if os.path.exists(os.path.join(os_dir, "noise.txt")) else "",
    "environment": open(os.path.join(os_dir, "environment.txt")).read().strip() if os.path.exists(os.path.join(os_dir, "environment.txt")) else "",
}
raw = R("results", "study_raw.csv")
OUT["main_new"] = os.path.exists(raw) and any(r["arch"] == "seqP" for r in csv.DictReader(open(raw)))
if OUT["main_new"]:
    import statistics as st
    by = defaultdict(list)
    for r in csv.DictReader(open(raw)):
        by[(r["video"], r["arch"], int(r["workers"]))].append(float(r["seconds"]))
    stat = min if os.environ.get("STUDY_STAT") == "min" else st.median
    vids = sorted({k[0] for k in by})
    ratio = st.mean(stat(by[(v, "seq", 1)]) / stat(by[(v, "seqP", 1)]) for v in vids)
    W = sorted({k[2] for k in by if k[1] == "a"})
    OUT["baseline"] = {"videos": len(vids), "stat": "best of reps" if stat is min else "median",
                       "unpinned_over_pinned_time": round(ratio, 3),
                       "speedup": {str(w): {"pinned": round(st.mean(stat(by[(v, "seqP", 1)]) / stat(by[(v, "a", w)]) for v in vids), 2),
                                            "unpinned": round(st.mean(stat(by[(v, "seq", 1)]) / stat(by[(v, "a", w)]) for v in vids), 2)}
                                   for w in W}}
json.dump(OUT, open(R("results", "report_data.json"), "w"), indent=1)
print(json.dumps({k: (v if k.startswith("dev2") or k == "main_new" else "...") for k, v in OUT.items()}, indent=1))

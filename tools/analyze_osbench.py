"""Summarise sweep CSVs: speedup vs seq per (os,res,N,mode,P) + crossover N."""
import csv, glob, sys
from collections import defaultdict

rows = []
for fn in sys.argv[1:]:
    with open(fn) as f:
        lines = [l for l in f if l.strip() and not l.startswith("os,")]
    for l in lines:
        r = l.strip().split(",")
        rows.append(dict(os=r[0], res=r[1], N=int(r[2]), mb=float(r[3]), mode=r[4], P=int(r[5]),
                         med=float(r[6]), cpu=float(r[9]) + float(r[10]), sys=float(r[10]),
                         vcs=float(r[11]), ivcs=float(r[12])))

seq = {(r["os"], r["res"], r["N"]): r["med"] for r in rows if r["mode"] == "seq"}
groups = defaultdict(list)
for r in rows:
    groups[(r["os"], r["res"])].append(r)

for (os_, res), rs in groups.items():
    Ns = sorted({r["N"] for r in rs})
    print(f"\n=== {os_} {res} : speedup vs sequential (median) ===")
    cfgs = [("A", p) for p in (2, 4, 6, 8, 12, 16)] + [("B", p) for p in (2, 4, 8, 16)]
    print(f"{'N':>6} {'MB':>7} {'seq_us':>10} " + " ".join(f"{m}{p:>2}" .rjust(6) for m, p in cfgs) + "  best")
    for N in Ns:
        s = seq[(os_, res, N)]
        line = f"{N:>6} {next(r['mb'] for r in rs if r['N']==N):>7.1f} {s*1e6:>10.0f} "
        best = ("seq", 1.0)
        for m, p in cfgs:
            t = next((r["med"] for r in rs if r["N"] == N and r["mode"] == m and r["P"] == p), None)
            sp = s / t if t else float("nan")
            if sp > best[1]: best = (f"{m}{p}", sp)
            line += f"{sp:6.2f} "
        print(line + f"  {best[0]} {best[1]:.2f}x")
    # crossover: smallest N where A-P beats seq and stays ahead
    for m, p in cfgs:
        win = [N for N in Ns if (t := next((r["med"] for r in rs if r["N"] == N and r["mode"] == m and r["P"] == p), None)) and t < seq[(os_, res, N)]]
        lose = [N for N in Ns if N not in win]
        cross = min([N for N in Ns if all(n in win for n in Ns if n >= N)], default=None)
        print(f"  crossover {m}{p}: wins for N >= {cross}")
    # cpu efficiency at the largest N
    N = Ns[-1]
    print(f"  at N={N}: cpu-time/wall and sys share")
    for r in sorted((r for r in rs if r["N"] == N), key=lambda r: (r["mode"], r["P"])):
        print(f"    {r['mode']}{r['P']:>2} wall={r['med']*1e3:8.2f}ms cpu={r['cpu']*1e3:8.2f}ms "
              f"cpu/seqcpu={r['cpu']/seq[(os_,res,N)]:5.2f} sys%={100*r['sys']/max(r['cpu'],1e-9):5.1f} "
              f"vcs={r['vcs']:.0f} ivcs={r['ivcs']:.0f}")

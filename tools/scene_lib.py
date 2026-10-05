"""Python access to the C scene layer: descriptor caches + ctypes call into c/libscene.dll."""
import ctypes
import os
import subprocess

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "c", "shotseg.exe")
DLL = os.path.join(ROOT, "c", "libscene.dll")
CACHE = os.path.join(ROOT, "data", "cache")
VIDEOS = list(range(1, 11))

# descriptor layout (must match c/features.h)
OFF = (0, 64, 352)
NCELLS = (1, 9, 9)
BINS = (64, 32, 8)
FD = 424

_lib = ctypes.CDLL(DLL)
_lib.scenes_run.restype = ctypes.c_long
_arr = np.ctypeslib.ndpointer


def build_cache(i, threads=8, force=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"rai_{i}.feat")
    if force or not os.path.exists(path):
        raw = os.path.join(ROOT, "data", f"rai_{i}_160x90.raw")
        out = subprocess.run([EXE, raw, "160", "90", "featdump", str(threads), path],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
        print(f"video {i}: ", out.strip().splitlines()[-1])
    return path


def load_cache(i):
    path = build_cache(i)
    with open(path, "rb") as f:
        ns = int(np.fromfile(f, "<i8", 1)[0])
        K = int(np.fromfile(f, "<i4", 1)[0])
        fd = int(np.fromfile(f, "<i4", 1)[0])
        nfr = int(np.fromfile(f, "<i8", 1)[0])
        starts = np.fromfile(f, "<i8", ns)
        ends = np.fromfile(f, "<i8", ns)
        kf = np.fromfile(f, "<f4", ns * K * fd).reshape(ns, K, fd)
        mh = np.fromfile(f, "<f4", ns * 64).reshape(ns, 1, 64)
    assert fd == FD
    return dict(ns=ns, K=K, nframes=nfr, starts=starts, ends=ends, kf=kf, mh=mh)


def legacy_kf(c):
    """The original representation: mean global histogram of all frames of the shot,
    one 'keyframe', global block only."""
    full = np.zeros((c["ns"], 1, FD), np.float32)
    full[:, 0, :64] = c["mh"][:, 0, :]
    return full


DEFAULT = dict(T=18, k=9, tau=0.4, lam_new=0.4, mu=0.05, lam_scene=0.3, max_phases=8)


def run_scenes(c, kf, klo, khi, w, params=None, nthreads=1):
    """Return predicted scene-start frames (excluding frame 0)."""
    p = {**DEFAULT, **(params or {})}
    kf = np.ascontiguousarray(kf, np.float32)
    K = kf.shape[1]
    off, nc, bn = (np.array(x, np.int32) for x in (OFF, NCELLS, BINS))
    wv = np.array(w, np.float64)
    out = np.zeros(c["ns"] + 1, np.int64)
    n = _lib.scenes_run(
        kf.ctypes.data_as(ctypes.c_void_p), ctypes.c_long(c["ns"]), K, FD, klo, khi, 3,
        off.ctypes.data_as(ctypes.c_void_p), nc.ctypes.data_as(ctypes.c_void_p),
        bn.ctypes.data_as(ctypes.c_void_p), wv.ctypes.data_as(ctypes.c_void_p),
        p["T"], p["k"], ctypes.c_double(p["tau"]), ctypes.c_double(p["lam_new"]),
        ctypes.c_double(p["mu"]), ctypes.c_double(p["lam_scene"]), p["max_phases"],
        nthreads, out.ctypes.data_as(ctypes.c_void_p), ctypes.c_long(len(out)))
    firsts = out[:n]
    starts = c["starts"][firsts]
    return [int(s) for s in starts if s > 0]

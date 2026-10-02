"""Precision / recall / F1 of predicted boundaries vs ground truth.
usage: python tools/evaluate.py TRUTH.json cuts.txt [scenes.txt]
A prediction is correct if within `tol` frames of an unmatched true boundary
(the TRECVid-style tolerance-window protocol, one-to-one matching)."""
import json
import sys


def prf(pred, truth, tol):
    truth, used, tp = sorted(truth), set(), 0
    for p in sorted(pred):
        for i, t in enumerate(truth):
            if i not in used and abs(p - t) <= tol:
                used.add(i)
                tp += 1
                break
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(truth) if truth else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1


def load(p):
    return [int(x) for x in open(p).read().split()]


if __name__ == "__main__":
    gt = json.load(open(sys.argv[1]))
    P, R, F = prf(load(sys.argv[2]), gt["cuts"], 2)
    print(f"shot cuts : P={P:.3f} R={R:.3f} F1={F:.3f}  (tol 2 frames, "
          f"{len(load(sys.argv[2]))} predicted / {len(gt['cuts'])} true)")
    if len(sys.argv) > 3:
        sc = load(sys.argv[3])
        P, R, F = prf([s for s in sc if s > 0], gt["scene_starts"][1:], 3)
        print(f"scenes    : P={P:.3f} R={R:.3f} F1={F:.3f}  (tol 3 frames, "
              f"{len(sc)} predicted / {len(gt['scene_starts'])} true)")

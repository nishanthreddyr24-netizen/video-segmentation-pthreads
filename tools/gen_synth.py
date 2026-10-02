"""Synthetic video with KNOWN shot cuts and scene boundaries.

Each scene has its own hue; inside a scene two "camera angles" (A/B, different
hue offset + saturation) alternate like a dialogue: A B A B ...  A moving
rectangle and per-frame noise keep frames from being identical.

usage: python tools/gen_synth.py OUT.raw [--scenes 40] [--w 160] [--h 90] [--seed 1]
writes OUT.raw (BGR24, no header) and OUT.json {cuts, scene_starts, n_frames}
"""
import argparse
import json

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--scenes", type=int, default=40)
    ap.add_argument("--w", type=int, default=160)
    ap.add_argument("--h", type=int, default=90)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    w, h = a.w, a.h
    noise_pool = rng.integers(-3, 4, size=(8, h, w, 3), dtype=np.int16)

    cuts, scene_starts, frame = [], [], 0
    with open(a.out, "wb") as f:
        for sc in range(a.scenes):
            hue = (sc * 55) % 180
            scene_starts.append(frame)
            for shot in range(int(rng.integers(4, 9))):
                if frame:
                    cuts.append(frame)
                angle = shot % 2
                hh = (hue + (-12 if angle == 0 else 12)) % 180
                ss = 220 if angle == 0 else 120
                base = np.full((h, w, 3), (hh, ss, 180), np.uint8)
                base = cv2.cvtColor(base, cv2.COLOR_HSV2BGR).astype(np.int16)
                for t in range(int(rng.integers(30, 91))):
                    img = base + noise_pool[(frame + t) % 8]
                    x = (t * 2) % (w - 20)
                    img[h // 2 - 8:h // 2 + 8, x:x + 16] = (128, 128, 128)
                    f.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
                    frame += 1
    with open(a.out.rsplit(".", 1)[0] + ".json", "w") as f:
        json.dump({"cuts": cuts, "scene_starts": scene_starts,
                   "n_frames": frame, "w": w, "h": h}, f)
    print(f"{a.out}: {frame} frames, {len(cuts) + 1} shots, {a.scenes} scenes")


if __name__ == "__main__":
    main()

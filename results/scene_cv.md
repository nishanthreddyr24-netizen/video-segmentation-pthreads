# Scene segmentation: richer classical features, leave-one-video-out

Parameters (tau, lam_new, mu, lam_scene, max_phases; 672 combinations) are chosen on 9 videos and scored on the 10th. Pooled over all 10 held-out videos (116 true boundaries). 95% interval resamples whole videos.

| features | F1 @1 s | F1 @2 s | F1 @5 s | P / R @2 s | predicted / true scenes | F1@2 s 95% interval |
|---|---|---|---|---|---|---|
| legacy: mean global hist (old method) | 0.219 | 0.287 | 0.362 | 0.26 / 0.33 | 159 / 126 | 0.20 - 0.36 |
| global hist, 1 keyframe | 0.249 | 0.304 | 0.405 | 0.28 / 0.34 | 151 / 126 | 0.22 - 0.36 |
| global hist, 3 keyframes | 0.242 | 0.304 | 0.394 | 0.25 / 0.38 | 183 / 126 | 0.23 - 0.36 |
| spatial 3x3 colour grid, 3 keyframes | 0.247 | 0.290 | 0.328 | 0.19 / 0.59 | 363 / 126 | 0.23 - 0.35 |
| edge orientation 3x3, 3 keyframes | 0.161 | 0.239 | 0.367 | 0.18 / 0.37 | 254 / 126 | 0.17 - 0.32 |
| spatial + edge, 3 keyframes | 0.192 | 0.244 | 0.347 | 0.21 / 0.28 | 165 / 126 | 0.17 - 0.31 |
| **FULL: global + spatial + edge, 3 keyframes** | 0.284 | **0.348** | 0.468 | 0.30 / 0.42 | 176 / 126 | 0.25 - 0.44 |
| global + spatial + edge, 5 keyframes | 0.296 | 0.361 | 0.462 | 0.31 / 0.43 | 171 / 126 | 0.27 - 0.45 |
| *baseline: every detected cut = boundary* | 0.156 | 0.167 | 0.179 | 0.09 / 0.91 | - | 0.13 - 0.21 |
| *baseline: evenly spaced, true #scenes* | 0.017 | 0.043 | 0.172 | 0.04 / 0.04 | - | 0.01 - 0.07 |

## Optimistic reference (parameters chosen on all 10 videos, scored on the same 10 - do NOT quote)

| features | F1 @2 s in-sample | F1 @2 s held-out | gap |
|---|---|---|---|
| legacy: mean global hist (old method) | 0.361 | 0.287 | +0.075 |
| global hist, 1 keyframe | 0.356 | 0.304 | +0.053 |
| global hist, 3 keyframes | 0.355 | 0.304 | +0.050 |
| spatial 3x3 colour grid, 3 keyframes | 0.326 | 0.290 | +0.036 |
| edge orientation 3x3, 3 keyframes | 0.274 | 0.239 | +0.036 |
| spatial + edge, 3 keyframes | 0.324 | 0.244 | +0.080 |
| FULL: global + spatial + edge, 3 keyframes | 0.363 | 0.348 | +0.015 |
| global + spatial + edge, 5 keyframes | 0.366 | 0.361 | +0.005 |

## Parameter stability across folds (main method)

- tau: 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.04, 0.02, 0.04
- lam_scene: 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8
- mu: 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.08
- max_phases: 8, 8, 8, 8, 8, 8, 8, 8, 8, 8
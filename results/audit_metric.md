# Metric audit (RAI scene dataset)

## 1. Ground truth integrity
| video | frames (raw) | last GT frame | scenes | gaps | shortest / median / longest scene (s) | shots found |
|---|---|---|---|---|---|---|
| 1 | 14541 | 14541 | 7 | 0 | 6 / 30 / 359 | 99 |
| 2 | 14283 | 14283 | 12 | 0 | 7 / 25 / 254 | 62 |
| 3 | 14266 | 14266 | 16 | 0 | 8 / 27 / 114 | 105 |
| 4 | 14760 | 14760 | 22 | 0 | 3 / 18 / 130 | 149 |
| 5 | 14775 | 14775 | 13 | 0 | 6 / 28 / 152 | 206 |
| 6 | 15000 | 15000 | 5 | 0 | 45 / 93 / 238 | 63 |
| 7 | 15000 | 15000 | 9 | 0 | 15 / 33 / 183 | 122 |
| 8 | 15000 | 15000 | 12 | 0 | 1 / 46 / 133 | 179 |
| 9 | 15000 | 15000 | 14 | 0 | 14 / 30 / 124 | 88 |
| 10 | 15000 | 15000 | 16 | 0 | 8 / 23 / 138 | 81 |

No gaps, and every video's last labelled frame equals its frame count, so labels and frames line up. **Total: 126 scenes = 116 true boundaries** across 10 videos. That is a very small test set: one video can move the pooled score a lot (see the bootstrap below).

## 2. Recall ceiling imposed by shot detection
Scene boundaries that fall within tolerance of ANY detected cut. If this is low, no scene method can score well, and the shot stage is the bottleneck.

| video | true boundaries | within 1 s of a cut | within 2 s | within 5 s |
|---|---|---|---|---|
| 1 | 6 | 6 | 6 | 6 |
| 2 | 11 | 11 | 11 | 11 |
| 3 | 15 | 15 | 15 | 15 |
| 4 | 21 | 14 | 15 | 19 |
| 5 | 12 | 8 | 12 | 12 |
| 6 | 4 | 3 | 4 | 4 |
| 7 | 8 | 8 | 8 | 8 |
| 8 | 11 | 11 | 11 | 11 |
| 9 | 13 | 11 | 11 | 13 |
| 10 | 15 | 11 | 12 | 14 |
| **all** | **116** | **98 (84%)** | **105 (91%)** | **113 (97%)** |

## 3. Does the scorer used so far agree with a clean re-implementation?
Legacy method (mean global histogram, default parameters), all 10 videos, pooled:

| tolerance | P / R / F1 (new matcher) | F1 (old greedy scorer) |
|---|---|---|
| 1s | 0.216 / 0.069 / 0.105 | 0.105 |
| 2s | 0.216 / 0.069 / 0.105 | 0.105 |
| 5s | 0.297 / 0.095 / 0.144 | 0.144 |

The earlier report quoted 0.105 / 0.105 / 0.144 for this setting (1 s / 2 s / 5 s); matching it confirms the refactored C code reproduces the old method.

## 4. How good is 'random', and how noisy is the score?
| method (all 10 videos, pooled) | F1 @1 s | F1 @2 s | F1 @5 s | F1@2 s 95% CI (resampling videos) |
|---|---|---|---|---|
| legacy, default params | 0.105 | 0.105 | 0.144 | 0.00 - 0.18 |
| random boundaries, same count as legacy | 0.024 | 0.046 | 0.110 | - |
| every detected cut = scene boundary | 0.156 | 0.167 | 0.179 | - |
| evenly spaced, true number of scenes | 0.017 | 0.043 | 0.172 | - |

The resampling interval is the honest statement of the noise: with only 116 true boundaries, differences of a few hundredths in F1 are not distinguishable from chance.

## 5. Metrics deliberately not used
I also tried coverage/overflow (Vendrig & Worring), but could not verify my implementation against a reference (it produced overflow values above 1), so it is excluded rather than reported unverified.

## Audit conclusions
- Labels are aligned; the scorer matches an independent re-implementation, so the 0.13 was not a bug.
- **The baseline that matters is not random.** Calling every detected cut a scene boundary scores F1 0.167 at 2 s, and evenly spaced scenes score 0.172 at 5 s. A scene method must beat these to show it adds anything.
- Shot detection leaves a recall ceiling of **91%** at 2 s (97% at 5 s): scene boundaries are mostly at detected cuts, so the shot stage is not the main limit.
- The test set is tiny, so every result must be reported with its interval, and tuned with held-out evaluation (leave-one-video-out), never on the videos being scored.
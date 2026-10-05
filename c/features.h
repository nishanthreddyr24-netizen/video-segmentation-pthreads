/* features.h - richer per-keyframe descriptors for the scene layer.
 *
 * One keyframe descriptor (FD_TOTAL floats) =
 *   block 0  global HSV histogram            1 cell  x 64 bins  (8 hue x 8 sat)
 *   block 1  3x3 grid of HSV histograms      9 cells x 32 bins  (8 hue x 4 sat)
 *   block 2  3x3 grid edge-orientation hist  9 cells x  8 bins  (Sobel, magnitude-weighted)
 * Every cell histogram is L1-normalised on its own.
 * The grid blocks keep WHERE colours/edges are, which a global histogram loses. */
#ifndef FEATURES_H
#define FEATURES_H

#include "common.h"
#include "scenes.h"

#define KF_PER_SHOT 5 /* keyframes at 10%, 30%, 50%, 70%, 90% of each shot */

#define G_OFF 0
#define G_CELLS 1
#define G_BINS 64
#define S_OFF (G_OFF + G_CELLS * G_BINS)
#define S_CELLS 9
#define S_BINS 32
#define E_OFF (S_OFF + S_CELLS * S_BINS)
#define E_CELLS 9
#define E_BINS 8
#define FD_TOTAL (E_OFF + E_CELLS * E_BINS) /* 424 */

void frame_rich(const uint8_t *bgr, int w, int h, float *out /* FD_TOTAL */);

/* Parallel over shots: for each shot read KF_PER_SHOT frames and describe them.
 * out = ns * KF_PER_SHOT * FD_TOTAL floats. */
int shot_keyframe_features(const Video *v, const Shot *shots, long ns,
                           int nthreads, float *out);

#endif

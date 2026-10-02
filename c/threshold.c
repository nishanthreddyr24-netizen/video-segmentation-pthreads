/* Adaptive threshold: the SERIAL stage that runs after all chunks are merged.
 * Doing it here (not per chunk) means chunk borders cannot create
 * inconsistent thresholds. */
#include <math.h>
#include <stdlib.h>

#include "common.h"

long adaptive_threshold(const float *diffs, long n, int window, double k,
                        int min_gap, double min_abs, long *cuts_out) {
    if (n <= 0) return 0;
    int half = window / 2;
    /* prefix sums -> O(1) window mean/std for every position */
    double *c1 = malloc((n + 1) * sizeof(double));
    double *c2 = malloc((n + 1) * sizeof(double));
    c1[0] = c2[0] = 0;
    for (long i = 0; i < n; i++) {
        c1[i + 1] = c1[i] + diffs[i];
        c2[i + 1] = c2[i] + (double)diffs[i] * diffs[i];
    }
    long nc = 0;
    for (long i = 1; i < n; i++) {
        long lo = i - half < 0 ? 0 : i - half;
        long hi = i + half + 1 > n ? n : i + half + 1;
        double cnt = (double)(hi - lo - 1);
        if (cnt < 1) cnt = 1;
        double d = diffs[i];
        double s1 = c1[hi] - c1[lo] - d;              /* leave centre out */
        double s2 = c2[hi] - c2[lo] - d * d;
        double mean = s1 / cnt;
        double var = s2 / cnt - mean * mean;
        double sd = var > 0 ? sqrt(var) : 0;
        if (!(d > mean + k * sd) || d < min_abs) continue;
        int is_max = 1;                               /* local maximum? */
        for (long j = lo; j < hi; j++)
            if (diffs[j] > d) { is_max = 0; break; }
        if (!is_max) continue;
        if (nc > 0 && i - cuts_out[nc - 1] < min_gap) {
            if (d > diffs[cuts_out[nc - 1]]) cuts_out[nc - 1] = i;
            continue;
        }
        cuts_out[nc++] = i;
    }
    free(c1);
    free(c2);
    return nc;
}

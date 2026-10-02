/* Step 1: single-threaded baseline. One loop, one frame at a time. */
#define _FILE_OFFSET_BITS 64
#include <stdio.h>
#include <stdlib.h>

#include "common.h"

int detect_sequential(const Video *v, ShotResult *r) {
    double t0 = now_sec();
    FILE *f = fopen(v->path, "rb");
    if (!f) return -1;
    uint8_t *buf = malloc(v->frame_bytes);
    int npix = v->w * v->h;
    for (long i = 0; i < v->n; i++) {
        if (fread(buf, 1, v->frame_bytes, f) != v->frame_bytes) break;
        float *h = r->hists + (size_t)i * NBINS;
        frame_hist(buf, npix, h);
        r->diffs[i] = i ? bhattacharyya(h - NBINS, h) : 0.f;
    }
    fclose(f);
    free(buf);
    double t1 = now_sec();
    r->ncuts = adaptive_threshold(r->diffs, v->n, 25, 4.0, 8, 0.15, r->cuts);
    double t2 = now_sec();
    r->t_parallel = t1 - t0;
    r->t_threshold = t2 - t1;
    r->t_total = t2 - t0;
    return 0;
}

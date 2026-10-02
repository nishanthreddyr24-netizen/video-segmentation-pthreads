/* common.h - shared types and helpers for the shot-segmentation project. */
#ifndef COMMON_H
#define COMMON_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define HBINS 8
#define SBINS 8
#define NBINS (HBINS * SBINS) /* 64-dim colour histogram per frame */

/* A raw video: n frames of w*h*3 bytes (BGR), stored back-to-back, no header.
 * Frame i therefore lives at byte offset i * frame_bytes -> any thread can
 * jump straight to its own chunk. */
typedef struct {
    const char *path;
    int w, h;
    long n;             /* number of frames */
    size_t frame_bytes; /* w*h*3 */
} Video;

/* Result of a shot-detection run. diffs[i] = distance(frame i-1, frame i). */
typedef struct {
    long n;
    float *diffs;   /* n floats */
    float *hists;   /* n * NBINS floats (kept for the scene layer) */
    long *cuts;     /* frame indices where a new shot starts */
    long ncuts;
    double t_parallel, t_threshold, t_total; /* seconds */
} ShotResult;

/* --- common.c --- */
double now_sec(void);                       /* monotonic wall clock */
int video_open(Video *v, const char *path, int w, int h);
void frame_hist(const uint8_t *bgr, int npix, float *out); /* L1-normalised */
float bhattacharyya(const float *a, const float *b);       /* sqrt(1-BC) */
void shotresult_alloc(ShotResult *r, long n);
void shotresult_free(ShotResult *r);

/* --- threshold.c --- */
long adaptive_threshold(const float *diffs, long n, int window, double k,
                        int min_gap, double min_abs, long *cuts_out);

/* --- detectors --- */
int detect_sequential(const Video *v, ShotResult *r);           /* step 1 */
int detect_chunked(const Video *v, int nthreads, int chunks_per_thread,
                   ShotResult *r);                              /* arch A */
int detect_pipeline(const Video *v, int nthreads, int queue_size,
                    ShotResult *r);                             /* arch B */

#endif

/* Architecture A: chunk-based data parallelism with POSIX threads.
 *
 * - The video is cut into n_chunks contiguous ranges.
 * - Worker threads pull chunk numbers from a shared counter (mutex-protected)
 *   -> dynamic load balancing.
 * - Each worker has its OWN FILE* (its own file position), so no sharing.
 * - Results go into disjoint slices of r->diffs / r->hists -> no data race,
 *   no lock needed for the output.
 */
#define _FILE_OFFSET_BITS 64
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#include "common.h"

typedef struct {
    const Video *v;
    ShotResult *r;
    long n_chunks;
    long next;             /* next unclaimed chunk (guarded by lock) */
    pthread_mutex_t lock;
} Shared;

static void chunk_range(long n, long n_chunks, long k, long *s, long *e) {
    *s = n * k / n_chunks;          /* same split as numpy.linspace */
    *e = n * (k + 1) / n_chunks;
}

static void process_chunk(const Video *v, ShotResult *r, FILE *f, uint8_t *buf,
                          long start, long end) {
    int npix = v->w * v->h;
    float prev[NBINS];
    int have_prev = 0;
    if (start > 0) {                /* 1-frame overlap */
        fseeko(f, (off_t)(start - 1) * (off_t)v->frame_bytes, SEEK_SET);
        if (fread(buf, 1, v->frame_bytes, f) == v->frame_bytes) {
            frame_hist(buf, npix, prev);
            have_prev = 1;
        }
    } else {
        fseeko(f, 0, SEEK_SET);
    }
    for (long i = start; i < end; i++) {
        if (fread(buf, 1, v->frame_bytes, f) != v->frame_bytes) break;
        float *h = r->hists + (size_t)i * NBINS;
        frame_hist(buf, npix, h);
        r->diffs[i] = have_prev ? bhattacharyya(prev, h) : 0.f;
        for (int b = 0; b < NBINS; b++) prev[b] = h[b];
        have_prev = 1;
    }
}

static void *worker(void *arg) {
    Shared *sh = arg;
    FILE *f = fopen(sh->v->path, "rb");
    uint8_t *buf = malloc(sh->v->frame_bytes);
    for (;;) {
        pthread_mutex_lock(&sh->lock);          /* critical section */
        long k = sh->next++;
        pthread_mutex_unlock(&sh->lock);
        if (k >= sh->n_chunks) break;
        long s, e;
        chunk_range(sh->v->n, sh->n_chunks, k, &s, &e);
        if (e > s) process_chunk(sh->v, sh->r, f, buf, s, e);
    }
    free(buf);
    fclose(f);
    return NULL;
}

int detect_chunked(const Video *v, int nthreads, int chunks_per_thread,
                   ShotResult *r) {
    double t0 = now_sec();
    Shared sh = {.v = v, .r = r, .n_chunks = (long)nthreads * chunks_per_thread,
                 .next = 0};
    if (sh.n_chunks > v->n) sh.n_chunks = v->n;
    pthread_mutex_init(&sh.lock, NULL);
    pthread_t *th = malloc(nthreads * sizeof *th);
    for (int i = 0; i < nthreads; i++)
        pthread_create(&th[i], NULL, worker, &sh);
    for (int i = 0; i < nthreads; i++) pthread_join(th[i], NULL);
    pthread_mutex_destroy(&sh.lock);
    free(th);
    double t1 = now_sec();
    /* serial stage, after the merge */
    r->ncuts = adaptive_threshold(r->diffs, v->n, 25, 4.0, 8, 0.15, r->cuts);
    double t2 = now_sec();
    r->t_parallel = t1 - t0;
    r->t_threshold = t2 - t1;
    r->t_total = t2 - t0;
    return 0;
}

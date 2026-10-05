#define _FILE_OFFSET_BITS 64
#include "features.h"

#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

#define PI_F 3.14159265f

static void norm_cell(float *c, int n) {
    float s = 0.f;
    for (int i = 0; i < n; i++) s += c[i];
    if (s > 1e-6f) {
        float inv = 1.f / s;
        for (int i = 0; i < n; i++) c[i] *= inv;
    }
}

void frame_rich(const uint8_t *bgr, int w, int h, float *out) {
    memset(out, 0, FD_TOTAL * sizeof(float));
    float *G = out + G_OFF, *S = out + S_OFF, *E = out + E_OFF;
    uint8_t *gray = malloc((size_t)w * h);
    for (int y = 0; y < h; y++) {
        int cy = y * 3 / h;
        for (int x = 0; x < w; x++) {
            const uint8_t *p = bgr + 3 * ((size_t)y * w + x);
            int b = p[0], g = p[1], r = p[2];
            gray[(size_t)y * w + x] = (uint8_t)((29 * b + 150 * g + 77 * r) >> 8);
            int mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
            int mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
            int d = mx - mn;
            int s = mx ? (255 * d) / mx : 0;
            float hh = 0.f;
            if (d) {
                if (mx == r)      hh = 60.f * (float)(g - b) / d;
                else if (mx == g) hh = 120.f + 60.f * (float)(b - r) / d;
                else              hh = 240.f + 60.f * (float)(r - g) / d;
                if (hh < 0) hh += 360.f;
            }
            int hb = (int)(hh * 0.5f * 8 / 180.f);
            if (hb > 7) hb = 7;
            G[hb * 8 + s * 8 / 256] += 1.f;
            int cell = cy * 3 + x * 3 / w;
            S[cell * S_BINS + hb * 4 + s * 4 / 256] += 1.f;
        }
    }
    norm_cell(G, G_BINS);
    for (int c = 0; c < S_CELLS; c++) norm_cell(S + c * S_BINS, S_BINS);
    /* Sobel gradient, unsigned orientation in 8 bins, weighted by magnitude */
    for (int y = 1; y < h - 1; y++) {
        int cy = y * 3 / h;
        for (int x = 1; x < w - 1; x++) {
            const uint8_t *q = gray + (size_t)y * w + x;
            int gx = (q[-w + 1] + 2 * q[1] + q[w + 1]) - (q[-w - 1] + 2 * q[-1] + q[w - 1]);
            int gy = (q[w - 1] + 2 * q[w] + q[w + 1]) - (q[-w - 1] + 2 * q[-w] + q[-w + 1]);
            float mag = sqrtf((float)(gx * gx + gy * gy));
            if (mag < 8.f) continue; /* ignore flat/noise pixels */
            float a = atan2f((float)gy, (float)gx);
            if (a < 0) a += PI_F;
            int ob = (int)(a * E_BINS / PI_F);
            if (ob >= E_BINS) ob = E_BINS - 1;
            E[(cy * 3 + x * 3 / w) * E_BINS + ob] += mag;
        }
    }
    for (int c = 0; c < E_CELLS; c++) norm_cell(E + c * E_BINS, E_BINS);
    free(gray);
}

typedef struct {
    const Video *v;
    const Shot *shots;
    long lo, hi;
    float *out;
} Job;

static void *kf_worker(void *arg) {
    Job *j = arg;
    FILE *f = fopen(j->v->path, "rb");
    uint8_t *buf = malloc(j->v->frame_bytes);
    if (!f || !buf) return NULL;
    for (long s = j->lo; s < j->hi; s++) {
        long len = j->shots[s].end - j->shots[s].start;
        for (int k = 0; k < KF_PER_SHOT; k++) {
            long fr = j->shots[s].start + len * (2 * k + 1) / (2 * KF_PER_SHOT);
            fseeko(f, (off_t)fr * (off_t)j->v->frame_bytes, SEEK_SET);
            float *dst = j->out + ((size_t)s * KF_PER_SHOT + k) * FD_TOTAL;
            if (fread(buf, 1, j->v->frame_bytes, f) == j->v->frame_bytes)
                frame_rich(buf, j->v->w, j->v->h, dst);
        }
    }
    free(buf);
    fclose(f);
    return NULL;
}

int shot_keyframe_features(const Video *v, const Shot *shots, long ns,
                           int nthreads, float *out) {
    if (nthreads < 1) nthreads = 1;
    pthread_t *th = malloc(nthreads * sizeof *th);
    Job *jobs = malloc(nthreads * sizeof *jobs);
    for (int t = 0; t < nthreads; t++) {
        jobs[t] = (Job){v, shots, ns * t / nthreads, ns * (t + 1) / nthreads, out};
        pthread_create(&th[t], NULL, kf_worker, &jobs[t]);
    }
    for (int t = 0; t < nthreads; t++) pthread_join(th[t], NULL);
    free(th);
    free(jobs);
    return 0;
}

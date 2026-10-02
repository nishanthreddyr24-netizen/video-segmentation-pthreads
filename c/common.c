#define _FILE_OFFSET_BITS 64
#include "common.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int video_open(Video *v, const char *path, int w, int h) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fseeko(f, 0, SEEK_END);
    off_t size = ftello(f);
    fclose(f);
    v->path = path;
    v->w = w;
    v->h = h;
    v->frame_bytes = (size_t)w * h * 3;
    v->n = (long)(size / (off_t)v->frame_bytes);
    return 0;
}

/* Colour histogram over (Hue, Saturation), 8x8 bins, hue on OpenCV's 0..180
 * scale. Value (brightness) is ignored so lighting changes matter less. */
void frame_hist(const uint8_t *bgr, int npix, float *out) {
    int cnt[NBINS];
    memset(cnt, 0, sizeof cnt);
    for (int i = 0; i < npix; i++) {
        int b = bgr[3 * i], g = bgr[3 * i + 1], r = bgr[3 * i + 2];
        int mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
        int mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
        int d = mx - mn;
        int s = mx ? (255 * d) / mx : 0;
        float h = 0.f;
        if (d) {
            if (mx == r)      h = 60.f * (float)(g - b) / d;
            else if (mx == g) h = 120.f + 60.f * (float)(b - r) / d;
            else              h = 240.f + 60.f * (float)(r - g) / d;
            if (h < 0) h += 360.f;
        }
        int hb = (int)(h * 0.5f * HBINS / 180.f);
        if (hb >= HBINS) hb = HBINS - 1;
        int sb = s * SBINS / 256;
        cnt[hb * SBINS + sb]++;
    }
    float inv = 1.f / (float)npix;
    for (int i = 0; i < NBINS; i++) out[i] = cnt[i] * inv;
}

/* d = sqrt(1 - BC),  BC = sum_i sqrt(p_i * q_i)  (OpenCV's variant). */
float bhattacharyya(const float *a, const float *b) {
    float bc = 0.f;
    for (int i = 0; i < NBINS; i++) bc += sqrtf(a[i] * b[i]);
    float v = 1.f - bc;
    return v > 0.f ? sqrtf(v) : 0.f;
}

void shotresult_alloc(ShotResult *r, long n) {
    memset(r, 0, sizeof *r);
    r->n = n;
    r->diffs = calloc(n, sizeof(float));
    r->hists = calloc((size_t)n * NBINS, sizeof(float));
    r->cuts = calloc(n, sizeof(long));
}

void shotresult_free(ShotResult *r) {
    free(r->diffs);
    free(r->hists);
    free(r->cuts);
}

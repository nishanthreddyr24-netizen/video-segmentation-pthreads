#include "scenes.h"

#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

#define INF 1e30f

SceneParams scene_defaults(void) {
    SceneParams p = {18, 9, 0.4, 0.4, 0.05, 0.3, 8};
    return p;
}

long shots_from_cuts(const long *cuts, long ncuts, long nframes, Shot *out) {
    long ns = 0, prev = 0;
    for (long i = 0; i <= ncuts; i++) {
        long e = i < ncuts ? cuts[i] : nframes;
        if (e > prev) out[ns++] = (Shot){prev, e};
        prev = e;
    }
    return ns;
}

/* A shot is represented by the mean histogram of its frames. */
void shot_features(const float *hists, const Shot *shots, long ns, float *feat) {
    for (long s = 0; s < ns; s++) {
        float *f = feat + (size_t)s * NBINS;
        memset(f, 0, NBINS * sizeof(float));
        for (long i = shots[s].start; i < shots[s].end; i++)
            for (int b = 0; b < NBINS; b++) f[b] += hists[(size_t)i * NBINS + b];
        float inv = 1.f / (float)(shots[s].end - shots[s].start);
        for (int b = 0; b < NBINS; b++) f[b] *= inv;
    }
}

/* chi-square histogram distance, in [0,1] for L1-normalised inputs */
static float chi2(const float *a, const float *b) {
    float d = 0.f;
    for (int i = 0; i < NBINS; i++) {
        float s = a[i] + b[i];
        if (s > 1e-9f) d += (a[i] - b[i]) * (a[i] - b[i]) / s;
    }
    return 0.5f * d;
}

/* ---- Stage 1: pairwise similarity (PARALLEL) ------------------------ */
typedef struct {
    const float *feat;
    long ns, lo, hi; /* rows [lo,hi) */
    int T;
    float *D;        /* ns x T ; D[i*T+o-1] = dist(shot i, shot i+o) */
} SimJob;

static void *sim_worker(void *arg) {
    SimJob *j = arg;
    for (long i = j->lo; i < j->hi; i++)
        for (int o = 1; o <= j->T; o++)
            j->D[(size_t)i * j->T + (o - 1)] =
                (i + o < j->ns)
                    ? chi2(j->feat + (size_t)i * NBINS,
                           j->feat + (size_t)(i + o) * NBINS)
                    : INF;
    return NULL;
}

/* ---- Stage 2: thread inference, Viterbi over parent offset (SERIAL) - */
static void infer_threads(const float *D, long ns, const SceneParams *p,
                          long *thread_id, long *n_threads_out) {
    int K = p->k, T = p->T, S = K + 1;
    float *dp = malloc((size_t)ns * S * sizeof(float));
    signed char *bp = malloc((size_t)ns * S);
    for (long i = 0; i < ns; i++) {
        for (int s = 0; s < S; s++) {
            float u;
            if (s == 0) u = (float)p->lam_new;
            else if (i - s < 0 || s > T) u = INF;
            else {
                float d = D[(size_t)(i - s) * T + (s - 1)];
                u = d < p->tau ? d : INF;
            }
            float best = INF;
            int arg = 0;
            if (i == 0) {
                best = 0.f;
            } else {
                for (int sp = 0; sp < S; sp++) {
                    float c = dp[(size_t)(i - 1) * S + sp] +
                              (sp == s ? 0.f : (float)p->mu);
                    if (c < best) { best = c; arg = sp; }
                }
            }
            dp[(size_t)i * S + s] = u >= INF ? INF : u + best;
            bp[(size_t)i * S + s] = (signed char)arg;
        }
    }
    /* backtrack */
    int s = 0;
    float best = INF;
    for (int c = 0; c < S; c++)
        if (dp[(size_t)(ns - 1) * S + c] < best) { best = dp[(size_t)(ns - 1) * S + c]; s = c; }
    int *off = malloc(ns * sizeof(int));
    for (long i = ns - 1; i >= 0; i--) {
        off[i] = s;
        s = bp[(size_t)i * S + s];
    }
    long nt = 0;
    for (long i = 0; i < ns; i++)
        thread_id[i] = off[i] == 0 ? nt++ : thread_id[i - off[i]];
    *n_threads_out = nt;
    free(off);
    free(dp);
    free(bp);
}

int segment_scenes(const float *feat, long ns, int nthreads,
                   const SceneParams *p, SceneResult *out) {
    memset(out, 0, sizeof *out);
    out->nshots = ns;
    if (ns <= 0) return 0;
    double t0 = now_sec();

    /* stage 1 */
    float *D = malloc((size_t)ns * p->T * sizeof(float));
    pthread_t *th = malloc(nthreads * sizeof *th);
    SimJob *jobs = malloc(nthreads * sizeof *jobs);
    for (int t = 0; t < nthreads; t++) {
        jobs[t] = (SimJob){feat, ns, ns * t / nthreads, ns * (t + 1) / nthreads,
                           p->T, D};
        pthread_create(&th[t], NULL, sim_worker, &jobs[t]);
    }
    for (int t = 0; t < nthreads; t++) pthread_join(th[t], NULL);
    free(th);
    free(jobs);
    double t1 = now_sec();

    /* stage 2 */
    long *tid = malloc(ns * sizeof(long)), nthr = 0;
    infer_threads(D, ns, p, tid, &nthr);
    free(D);
    double t2 = now_sec();

    /* stage 3: phases = groups of overlapping thread spans */
    long *first = malloc(nthr * sizeof(long)), *last = malloc(nthr * sizeof(long));
    for (long t = 0; t < nthr; t++) first[t] = -1;
    for (long i = 0; i < ns; i++) {
        if (first[tid[i]] < 0) first[tid[i]] = i;
        last[tid[i]] = i;
    }
    long *ph_start = malloc((ns + 1) * sizeof(long)); /* shot idx where phase begins */
    long np = 0, cur_end = -1;
    for (long t = 0; t < nthr; t++) {        /* threads are ordered by first */
        if (first[t] > cur_end) { ph_start[np++] = first[t]; cur_end = last[t]; }
        else if (last[t] > cur_end) cur_end = last[t];
    }
    ph_start[np] = ns;
    free(first);
    free(last);
    free(tid);
    double t3 = now_sec();

    /* stage 4: DP that groups phases into scenes */
    float *pf = calloc((size_t)np * NBINS, sizeof(float));
    for (long q = 0; q < np; q++) {
        for (long s = ph_start[q]; s < ph_start[q + 1]; s++)
            for (int b = 0; b < NBINS; b++) pf[q * NBINS + b] += feat[s * NBINS + b];
        float inv = 1.f / (float)(ph_start[q + 1] - ph_start[q]);
        for (int b = 0; b < NBINS; b++) pf[q * NBINS + b] *= inv;
    }
    double *best = malloc((np + 1) * sizeof(double));
    long *from = malloc((np + 1) * sizeof(long));
    best[0] = 0;
    for (long j = 1; j <= np; j++) {
        best[j] = 1e30;
        long lo = j - p->max_phases > 0 ? j - p->max_phases : 0;
        for (long i = lo; i < j; i++) {       /* group = phases [i, j) */
            float mean[NBINS] = {0};
            for (long q = i; q < j; q++)
                for (int b = 0; b < NBINS; b++) mean[b] += pf[q * NBINS + b];
            for (int b = 0; b < NBINS; b++) mean[b] /= (float)(j - i);
            double cost = p->lam_scene;
            for (long q = i; q < j; q++) cost += chi2(pf + q * NBINS, mean);
            if (best[i] + cost < best[j]) { best[j] = best[i] + cost; from[j] = i; }
        }
    }
    long ns_cnt = 0;
    for (long j = np; j > 0; j = from[j]) ns_cnt++;
    out->scene_first_shot = malloc(ns_cnt * sizeof(long));
    long w = ns_cnt;
    for (long j = np; j > 0; j = from[j]) out->scene_first_shot[--w] = ph_start[from[j]];
    out->nscenes = ns_cnt;
    out->nphases = np;
    free(pf);
    free(best);
    free(from);
    free(ph_start);
    double t4 = now_sec();

    out->t_sim = t1 - t0;
    out->t_dp_thread = t2 - t1;
    out->t_phase = t3 - t2;
    out->t_dp_scene = t4 - t3;
    return 0;
}

void sceneresult_free(SceneResult *r) { free(r->scene_first_shot); }

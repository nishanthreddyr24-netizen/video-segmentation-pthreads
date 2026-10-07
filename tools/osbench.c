/* OS-level benchmark harness for the shot-segmentation project.
 *   osbench gen   OUT.raw W H NFRAMES          synthetic BGR video
 *   osbench prims                               OS primitive costs
 *   osbench sweep FILE W H N1,N2,..             crossover sweep (CSV)
 *   osbench frame FILE W H                      per-frame cost breakdown
 */
#define _FILE_OFFSET_BITS 64
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "common.h"
#ifdef _WIN32
#include <windows.h>
static void cpu_times(double *u, double *s) {
    FILETIME c, e, k, us;
    GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &us);
    *u = (((unsigned long long)us.dwHighDateTime << 32) | us.dwLowDateTime) * 1e-7;
    *s = (((unsigned long long)k.dwHighDateTime << 32) | k.dwLowDateTime) * 1e-7;
}
static void ctxsw(long *v, long *iv) { *v = *iv = -1; }
#else
#include <sys/resource.h>
static void cpu_times(double *u, double *s) {
    struct rusage r; getrusage(RUSAGE_SELF, &r);
    *u = r.ru_utime.tv_sec + r.ru_utime.tv_usec * 1e-6;
    *s = r.ru_stime.tv_sec + r.ru_stime.tv_usec * 1e-6;
}
static void ctxsw(long *v, long *iv) {
    struct rusage r; getrusage(RUSAGE_SELF, &r);
    *v = r.ru_nvcsw; *iv = r.ru_nivcsw;
}
#endif

static unsigned long long rs = 88172645463325252ULL;
static unsigned rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return (unsigned)(rs >> 32); }

static int gen(const char *out, int w, int h, long n) {
    FILE *f = fopen(out, "wb");
    if (!f) return 1;
    size_t fb = (size_t)w * h * 3;
    uint8_t *img = malloc(fb);
    long i = 0;
    while (i < n) {
        int len = 30 + rnd() % 61;
        int B = rnd() % 256, G = rnd() % 256, R = rnd() % 256;
        for (int t = 0; t < len && i < n; t++, i++) {
            for (size_t p = 0; p < fb; p += 3) {
                int nz = (int)(rnd() % 7) - 3;
                int c[3] = {B + nz, G + nz, R + nz};
                for (int k = 0; k < 3; k++) img[p + k] = c[k] < 0 ? 0 : c[k] > 255 ? 255 : c[k];
            }
            int x0 = (t * 2) % (w > 20 ? w - 16 : 1);
            for (int y = h / 2 - h / 10; y < h / 2 + h / 10; y++)
                for (int x = x0; x < x0 + w / 10 && x < w; x++)
                    memset(img + ((size_t)y * w + x) * 3, 128, 3);
            fwrite(img, 1, fb, f);
        }
    }
    fclose(f);
    free(img);
    printf("wrote %s: %ld frames %dx%d (%.1f MB)\n", out, n, w, h, n * fb / 1e6);
    return 0;
}

/* ---------------- primitives ---------------- */
static void *noop(void *a) { return a; }
static pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;
static volatile long counter;
static long iters;
static void *hammer(void *a) {
    for (long i = 0; i < iters; i++) { pthread_mutex_lock(&m); counter++; pthread_mutex_unlock(&m); }
    return a;
}
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;
static int turn, pp_rounds;
static void *ponger(void *a) {
    for (int i = 0; i < pp_rounds; i++) {
        pthread_mutex_lock(&m);
        while (turn != 1) pthread_cond_wait(&cv, &m);
        turn = 0; pthread_cond_broadcast(&cv);
        pthread_mutex_unlock(&m);
    }
    return a;
}
static int prims(const char *rpath) {
    /* 1. thread create + join */
    int N = 2000;
    double t0 = now_sec();
    for (int i = 0; i < N; i++) { pthread_t t; pthread_create(&t, NULL, noop, NULL); pthread_join(t, NULL); }
    double tcj = (now_sec() - t0) / N;
    printf("thread_create_join_us,%.2f\n", tcj * 1e6);
    /* 1b. create P threads then join all (what detect_chunked does) */
    for (int P = 2; P <= 16; P *= 2) {
        pthread_t th[16];
        int R = 500;
        t0 = now_sec();
        for (int r = 0; r < R; r++) {
            for (int i = 0; i < P; i++) pthread_create(&th[i], NULL, noop, NULL);
            for (int i = 0; i < P; i++) pthread_join(th[i], NULL);
        }
        printf("spawn_join_%d_threads_us,%.2f\n", P, (now_sec() - t0) / R * 1e6);
    }
    /* 2. uncontended mutex */
    long M = 20000000;
    t0 = now_sec();
    for (long i = 0; i < M; i++) { pthread_mutex_lock(&m); counter++; pthread_mutex_unlock(&m); }
    printf("mutex_uncontended_ns,%.2f\n", (now_sec() - t0) / M * 1e9);
    /* 3. contended mutex, P threads hammering */
    for (int P = 2; P <= 16; P *= 2) {
        pthread_t th[16];
        iters = 2000000 / P;
        t0 = now_sec();
        for (int i = 0; i < P; i++) pthread_create(&th[i], NULL, hammer, NULL);
        for (int i = 0; i < P; i++) pthread_join(th[i], NULL);
        printf("mutex_contended_%dthr_ns_per_op,%.2f\n", P, (now_sec() - t0) / (iters * P) * 1e9);
    }
    /* 4. condvar ping-pong: one round trip = 2 sleep/wake hand-offs */
    pp_rounds = 50000; turn = 0;
    pthread_t pt; pthread_create(&pt, NULL, ponger, NULL);
    t0 = now_sec();
    for (int i = 0; i < pp_rounds; i++) {
        pthread_mutex_lock(&m);
        turn = 1; pthread_cond_broadcast(&cv);
        while (turn != 0) pthread_cond_wait(&cv, &m);
        pthread_mutex_unlock(&m);
    }
    pthread_join(pt, NULL);
    printf("condvar_handoff_us,%.2f\n", (now_sec() - t0) / pp_rounds / 2 * 1e6);
    /* 5. fopen + fclose (each Arch-A worker opens its own FILE*) */
    t0 = now_sec();
    for (int i = 0; i < 2000; i++) { FILE *f = fopen(rpath, "rb"); fclose(f); }
    printf("fopen_fclose_us,%.2f\n", (now_sec() - t0) / 2000 * 1e6);
    return 0;
}

/* ---------------- per-frame breakdown ---------------- */
static void *volatile sinkp;
static int frame(const char *path, int w, int h) {
    Video v; if (video_open(&v, path, w, h)) return 1;
    long n = v.n > 2000 ? 2000 : v.n;
    uint8_t *buf = malloc(v.frame_bytes);
    float hist[NBINS], prev[NBINS] = {0};
    FILE *f = fopen(path, "rb");
    for (long i = 0; i < n; i++) fread(buf, 1, v.frame_bytes, f);  /* warm cache */
    fseeko(f, 0, SEEK_SET);
    double t0 = now_sec();
    for (long i = 0; i < n; i++) fread(buf, 1, v.frame_bytes, f);
    double tr = (now_sec() - t0) / n;
    t0 = now_sec();
    volatile float sink = 0;
    for (long i = 0; i < n; i++) { frame_hist(buf, w * h, hist); sink += bhattacharyya(prev, hist); }
    double tc = (now_sec() - t0) / n;
    t0 = now_sec();
    for (long i = 0; i < n; i++) { void *p = malloc(v.frame_bytes); sinkp = p; ((volatile char *)p)[0] = 1; free(p); }
    double tm = (now_sec() - t0) / n;
    printf("%dx%d,frame_bytes=%zu,read_us=%.2f,compute_us=%.2f,malloc_free_us=%.3f,read_GBps=%.2f\n",
           w, h, v.frame_bytes, tr * 1e6, tc * 1e6, tm * 1e6, v.frame_bytes / tr / 1e9);
    fclose(f); free(buf);
    return 0;
}

/* ---------------- sweep ---------------- */
static double run_once(Video *v, char mode, int P) {
    ShotResult r; shotresult_alloc(&r, v->n);
    if (mode == 's') detect_sequential(v, &r);
    else if (mode == 'a') detect_chunked(v, P, 4, &r);
    else detect_pipeline(v, P, 64, &r);
    double t = r.t_total;
    shotresult_free(&r);
    return t;
}
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return x < y ? -1 : x > y; }
static int sweep(const char *path, int w, int h, char *list) {
    Video v; if (video_open(&v, path, w, h)) return 1;
    long full = v.n;
    int Ps[] = {2, 4, 6, 8, 12, 16};
    printf("os,res,frames,mb,mode,P,median_s,min_s,reps,cpu_user_s,cpu_sys_s,vol_csw,invol_csw\n");
    run_once(&v, 'a', 16);  /* warm page cache */
    for (char *tok = strtok(list, ","); tok; tok = strtok(NULL, ",")) {
        long N = atol(tok); if (N > full) N = full;
        v.n = N;
        for (int mi = 0; mi < 3; mi++) {
            char mode = "sab"[mi];
            int np = mode == 's' ? 1 : 6;
            for (int pi = 0; pi < np; pi++) {
                int P = mode == 's' ? 1 : Ps[pi];
                double ts[401]; int reps = 0; double acc = 0;
                double u0, s0, u1, s1; long v0, i0, v1, i1;
                run_once(&v, mode, P);  /* warm-up */
                cpu_times(&u0, &s0); ctxsw(&v0, &i0);
                while (reps < 401 && (reps < 7 || acc < 0.3)) { ts[reps] = run_once(&v, mode, P); acc += ts[reps++]; }
                cpu_times(&u1, &s1); ctxsw(&v1, &i1);
                qsort(ts, reps, sizeof(double), cmpd);
                printf("%s,%dx%d,%ld,%.2f,%s,%d,%.7f,%.7f,%d,%.6f,%.6f,%.1f,%.1f\n",
#ifdef _WIN32
                       "windows",
#else
                       "linux",
#endif
                       w, h, N, N * v.frame_bytes / 1e6, mode == 's' ? "seq" : mode == 'a' ? "A" : "B", P,
                       ts[reps / 2], ts[0], reps, (u1 - u0) / reps, (s1 - s0) / reps,
                       (double)(v1 - v0) / reps, (double)(i1 - i0) / reps);
                fflush(stdout);
            }
        }
    }
    return 0;
}


/* ---------------- Arch A only: chunk granularity + overhead split ---------------- */
static int achunks(const char *path, int w, int h, char *list) {
    Video v; if (video_open(&v, path, w, h)) return 1;
    long full = v.n;
    int Ps[] = {1, 4, 8, 16}, Cs[] = {1, 4, 16, 64};
    printf("os,frames,P,cpt,n_chunks,redundant_frames,median_total_s,median_par_s,median_thr_s,seq_s\n");
    { ShotResult r; shotresult_alloc(&r, v.n); detect_chunked(&v, 16, 4, &r); shotresult_free(&r); }
    for (char *tok = strtok(list, ","); tok; tok = strtok(NULL, ",")) {
        long N = atol(tok); if (N > full) N = full; v.n = N;
        double ss[101]; int sr = 0; double acc = 0;
        while (sr < 101 && (sr < 9 || acc < 0.2)) {
            ShotResult r; shotresult_alloc(&r, N); detect_sequential(&v, &r);
            acc += ss[sr++] = r.t_total; shotresult_free(&r);
        }
        qsort(ss, sr, sizeof(double), cmpd);
        for (int pi = 0; pi < 4; pi++) for (int ci = 0; ci < 4; ci++) {
            int P = Ps[pi], C = Cs[ci];
            double tt[101], tp[101], th[101]; int reps = 0; acc = 0;
            while (reps < 101 && (reps < 9 || acc < 0.2)) {
                ShotResult r; shotresult_alloc(&r, N); detect_chunked(&v, P, C, &r);
                tt[reps] = r.t_total; tp[reps] = r.t_parallel; th[reps] = r.t_threshold;
                acc += tt[reps++]; shotresult_free(&r);
            }
            qsort(tt, reps, sizeof(double), cmpd); qsort(tp, reps, sizeof(double), cmpd); qsort(th, reps, sizeof(double), cmpd);
            long nc = (long)P * C; if (nc > N) nc = N;
            printf("%s,%ld,%d,%d,%ld,%ld,%.7f,%.7f,%.7f,%.7f\n",
#ifdef _WIN32
                   "windows",
#else
                   "linux",
#endif
                   N, P, C, nc, nc > 0 ? nc - 1 : 0, tt[reps / 2], tp[reps / 2], th[reps / 2], ss[sr / 2]);
            fflush(stdout);
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc >= 6 && !strcmp(argv[1], "gen")) return gen(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]));
    if (argc >= 2 && !strcmp(argv[1], "prims")) return prims(argc > 2 ? argv[2] : "osbench.c");
    if (argc >= 5 && !strcmp(argv[1], "frame")) return frame(argv[2], atoi(argv[3]), atoi(argv[4]));
    if (argc >= 6 && !strcmp(argv[1], "sweep")) return sweep(argv[2], atoi(argv[3]), atoi(argv[4]), argv[5]);
    if (argc >= 6 && !strcmp(argv[1], "achunks")) return achunks(argv[2], atoi(argv[3]), atoi(argv[4]), argv[5]);
    fprintf(stderr, "usage: see source\n");
    return 1;
}

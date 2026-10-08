/* osstudy.c - OS-level scaling study of the chunked shot-detection workload (Windows).
 *
 * Question: why does speedup stop at ~5x on a hybrid CPU (4 P-cores with hyper-threading
 * + 4 E-cores)?  This program separates the candidate causes by changing ONE thing at a time:
 *
 *   cpu set    which logical CPUs the process may use (SetProcessAffinityMask)
 *   variant    full    = fread each frame + histogram          (what arch_a.c does)
 *              compute = histogram on cache-resident frames     (no file I/O at all)
 *              io      = fread each frame, touch it, no compute (file-cache copy only)
 *              mmap    = histogram straight from a mapped file  (no read syscall, no copy)
 *
 * modes:
 *   env                                   power / background-load check (exit 2 if not quiet)
 *   cpuspeed <raw> <w> <h> <N>            1 worker pinned to each logical CPU in turn
 *   scale <raw> <w> <h> <N> <set> <variants,csv> <maxP>
 *   check <raw> <w> <h> <N>               correctness: all variants give the same checksum
 *
 * build (from repo root, MinGW-w64):
 *   gcc -O2 -pthread -o tools/osstudy.exe tools/osstudy.c c/common.c -lm            */
#define _WIN32_WINNT 0x0A00
#define _FILE_OFFSET_BITS 64
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#include "../c/common.h"

/* Read strategies (each reads frames AND computes their histogram unless noted):
 *   full   stdio fread, ONE frame per call           (what arch_a.c does)
 *   fb4/fb16/fb64   stdio fread, 4/16/64 frames per call   (fewer calls, bigger copies)
 *   rf1/rf16        Win32 ReadFile with FILE_FLAG_SEQUENTIAL_SCAN, 1 / 16 frames per call
 *   mmap            memory-mapped file, no read call and no copy
 *   mmappf          mmap + PrefetchVirtualMemory of the worker's whole range first
 *   compute         histogram of frames already in memory (the ceiling: no file access at all)
 *   io              fread only, no compute      rfio16  ReadFile 16 frames/call, no compute      */
enum { V_FULL, V_COMPUTE, V_IO, V_MMAP, V_FB4, V_FB16, V_FB64, V_RF1, V_RF16, V_MMAPPF, V_RFIO16, V_NV };
static const char *VNAME[] = {"full", "compute", "io", "mmap", "fb4", "fb16", "fb64", "rf1", "rf16", "mmappf", "rfio16"};
static int vparse(const char *t) {
    for (int i = 0; i < V_NV; i++) if (!strcmp(t, VNAME[i])) return i;
    return V_MMAP;
}

typedef struct {
    int variant;
    const Video *v;
    long lo, hi;
    const uint8_t *map;     /* mmap base (whole file) */
    const uint8_t *frames;  /* 64 preloaded frames, for compute */
    double sink;            /* checksum so nothing is optimised away */
} Job;

static void *worker_ext(void *arg) {      /* batched stdio / Win32 ReadFile / mmap with prefetch */
    Job *j = arg;
    const Video *v = j->v;
    int npix = v->w * v->h, batch = 1, winapi = 0, compute = 1;
    float h[NBINS];
    double sink = 0;
    switch (j->variant) {
    case V_FB4: batch = 4; break;
    case V_FB16: batch = 16; break;
    case V_FB64: batch = 64; break;
    case V_RF1: winapi = 1; break;
    case V_RF16: winapi = 1; batch = 16; break;
    case V_RFIO16: winapi = 1; batch = 16; compute = 0; break;
    default: break;
    }
    if (j->variant == V_MMAPPF) {
        WIN32_MEMORY_RANGE_ENTRY e = {(PVOID)(j->map + (size_t)j->lo * v->frame_bytes),
                                      (SIZE_T)(j->hi - j->lo) * v->frame_bytes};
        PrefetchVirtualMemory(GetCurrentProcess(), 1, &e, 0);
        for (long i = j->lo; i < j->hi; i++) {
            frame_hist(j->map + (size_t)i * v->frame_bytes, npix, h);
            sink += h[0] + h[NBINS - 1];
        }
        j->sink = sink;
        return NULL;
    }
    uint8_t *buf = malloc((size_t)batch * v->frame_bytes);
    FILE *f = NULL;
    HANDLE hf = INVALID_HANDLE_VALUE;
    if (winapi) {
        hf = CreateFileA(v->path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, NULL);
        LARGE_INTEGER off; off.QuadPart = (long long)j->lo * (long long)v->frame_bytes;
        SetFilePointerEx(hf, off, NULL, FILE_BEGIN);
    } else {
        f = fopen(v->path, "rb");
        _fseeki64(f, (long long)j->lo * (long long)v->frame_bytes, SEEK_SET);
    }
    for (long i = j->lo; i < j->hi; i += batch) {
        long n = j->hi - i < batch ? j->hi - i : batch;
        size_t want = (size_t)n * v->frame_bytes;
        if (winapi) {
            DWORD got = 0;
            if (!ReadFile(hf, buf, (DWORD)want, &got, NULL) || got != want) break;
        } else if (fread(buf, 1, want, f) != want) break;
        for (long k = 0; k < n; k++) {
            if (compute) { frame_hist(buf + (size_t)k * v->frame_bytes, npix, h); sink += h[0] + h[NBINS - 1]; }
            else sink += buf[(size_t)k * v->frame_bytes] + buf[(size_t)(k + 1) * v->frame_bytes - 1];
        }
    }
    j->sink = sink;
    if (f) fclose(f);
    if (hf != INVALID_HANDLE_VALUE) CloseHandle(hf);
    free(buf);
    return NULL;
}

static void *worker(void *arg) {
    Job *j = arg;
    if (j->variant >= V_FB4) return worker_ext(arg);
    const Video *v = j->v;
    int npix = v->w * v->h;
    float h[NBINS];
    double sink = 0;
    FILE *f = NULL;
    uint8_t *buf = NULL;
    if (j->variant == V_FULL || j->variant == V_IO) {
        f = fopen(v->path, "rb");
        buf = malloc(v->frame_bytes);
        if (!f || !buf) return NULL;
        _fseeki64(f, (long long)j->lo * (long long)v->frame_bytes, SEEK_SET);
    }
    for (long i = j->lo; i < j->hi; i++) {
        switch (j->variant) {
        case V_FULL:
            if (fread(buf, 1, v->frame_bytes, f) != v->frame_bytes) goto done;
            frame_hist(buf, npix, h);
            sink += h[0] + h[NBINS - 1];
            break;
        case V_IO:
            if (fread(buf, 1, v->frame_bytes, f) != v->frame_bytes) goto done;
            sink += buf[0] + buf[v->frame_bytes - 1] + buf[v->frame_bytes / 2];
            break;
        case V_COMPUTE:
            frame_hist(j->frames + (size_t)(i & 63) * v->frame_bytes, npix, h);
            sink += h[0] + h[NBINS - 1];
            break;
        case V_MMAP:
            frame_hist(j->map + (size_t)i * v->frame_bytes, npix, h);
            sink += h[0] + h[NBINS - 1];
            break;
        }
    }
done:
    j->sink = sink;
    if (f) fclose(f);
    free(buf);
    return NULL;
}

static double ft2s(FILETIME a) { return (((unsigned long long)a.dwHighDateTime << 32) | a.dwLowDateTime) * 1e-7; }

/* one timed run with P workers over frames [0,N); returns wall seconds, checksum, cpu user/sys */
static double run_once(const Video *v, int variant, int P, long N, const uint8_t *map,
                       const uint8_t *frames, double *chk, double *cu, double *cs) {
    pthread_t *th = malloc(P * sizeof *th);
    Job *jobs = malloc(P * sizeof *jobs);
    FILETIME c, e, k0, u0, k1, u1;
    GetProcessTimes(GetCurrentProcess(), &c, &e, &k0, &u0);
    double t0 = now_sec();
    for (int t = 0; t < P; t++) {
        jobs[t] = (Job){variant, v, N * t / P, N * (t + 1) / P, map, frames, 0};
        pthread_create(&th[t], NULL, worker, &jobs[t]);
    }
    for (int t = 0; t < P; t++) pthread_join(th[t], NULL);
    double dt = now_sec() - t0;
    GetProcessTimes(GetCurrentProcess(), &c, &e, &k1, &u1);
    double s = 0;
    for (int t = 0; t < P; t++) s += jobs[t].sink;
    if (chk) *chk = s;
    if (cu) *cu = ft2s(u1) - ft2s(u0);
    if (cs) *cs = ft2s(k1) - ft2s(k0);
    free(th);
    free(jobs);
    return dt;
}

static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }

typedef struct { const uint8_t *map; const uint8_t *frames; HANDLE fh, mh; } Res;

static int open_res(const Video *v, Res *r) {
    r->fh = CreateFileA(v->path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (r->fh == INVALID_HANDLE_VALUE) return -1;
    r->mh = CreateFileMappingA(r->fh, NULL, PAGE_READONLY, 0, 0, NULL);
    r->map = r->mh ? MapViewOfFile(r->mh, FILE_MAP_READ, 0, 0, 0) : NULL;
    if (!r->map) return -1;
    uint8_t *fr = malloc(64 * v->frame_bytes);
    memcpy(fr, r->map, 64 * v->frame_bytes);
    r->frames = fr;
    return 0;
}

static DWORD_PTR SETMASK(const char *name) {
    if (!strcmp(name, "all"))   return 0xFFF;  /* 12 logical CPUs                              */
    if (!strcmp(name, "p8"))    return 0x0FF;  /* 4 P-cores x 2 hyper-threads                  */
    if (!strcmp(name, "p4"))    return 0x055;  /* 1 thread on each of 4 P-cores                */
    if (!strcmp(name, "e4"))    return 0xF00;  /* 4 E-cores                                    */
    if (!strcmp(name, "core8")) return 0xF55;  /* 1 thread per physical core: 4 P + 4 E        */
    if (!strcmp(name, "c1"))    return 0x001;  /* ONE logical CPU (single core)                */
    if (!strcmp(name, "c2"))    return 0x005;  /* 2 P-cores, one thread each                   */
    if (!strcmp(name, "c3"))    return 0x015;  /* 3 P-cores, one thread each                   */
    return (DWORD_PTR)strtoull(name, NULL, 16);
}

static int cmd_env(double lim) {
    SYSTEM_POWER_STATUS ps;
    GetSystemPowerStatus(&ps);
    FILETIME i0, k0, u0, i1, k1, u1;
    GetSystemTimes(&i0, &k0, &u0);
    Sleep(2000);
    GetSystemTimes(&i1, &k1, &u1);
    double idle = ft2s(i1) - ft2s(i0), tot = (ft2s(k1) - ft2s(k0)) + (ft2s(u1) - ft2s(u0));
    double busy = tot > 0 ? 100.0 * (1.0 - idle / tot) : 0;
    printf("ac_power=%s battery=%d%% background_cpu_load=%.1f%%\n",
           ps.ACLineStatus == 1 ? "yes" : (ps.ACLineStatus == 0 ? "NO (battery)" : "unknown"),
           ps.BatteryLifePercent, busy);
    int ok = ps.ACLineStatus == 1 && busy < lim;
    if (!ok) printf("NOT QUIET (limit %.0f%%, needs AC power)\n", lim);
    return ok ? 0 : 2;
}

static int cmd_scale(const char *raw, int w, int h, long N, const char *setname, char *variants, int maxP,
                     int cpuspeed_mode) {
    Video v;
    if (video_open(&v, raw, w, h) || N > v.n) { fprintf(stderr, "bad video / N\n"); return 1; }
    Res r;
    if (open_res(&v, &r)) { fprintf(stderr, "map failed\n"); return 1; }
    for (long i = 0; i < N; i++) (void)r.map[(size_t)i * v.frame_bytes];   /* warm page cache + mapping */
    if (!cpuspeed_mode) printf("set,variant,P,median_s,min_s,reps,cpu_user_s,cpu_sys_s,fps,p90_s\n");
    else printf("cpu,median_s,min_s,reps,fps\n");
    char *save = NULL;
    for (char *tok = strtok_s(variants, ",", &save); tok; tok = strtok_s(NULL, ",", &save)) {
        int var = vparse(tok);
        int lo = cpuspeed_mode ? 0 : 1, hi = cpuspeed_mode ? 12 : maxP;
        for (int P = lo; P <= hi; P++) {
            DWORD_PTR mask = cpuspeed_mode ? ((DWORD_PTR)1 << P) : SETMASK(setname);
            SetProcessAffinityMask(GetCurrentProcess(), mask);
            Sleep(30);
            int workers = cpuspeed_mode ? 1 : P;
            if (cpuspeed_mode && P >= 12) break;
            run_once(&v, var, workers, N, r.map, r.frames, NULL, NULL, NULL);   /* warm-up */
            double ts[40], cu = 0, cs = 0, acc = 0;
            int reps = 0;
            while (reps < 40 && (reps < 7 || acc < 1.5)) {
                double a, b;
                ts[reps] = run_once(&v, var, workers, N, r.map, r.frames, NULL, &a, &b);
                cu += a; cs += b; acc += ts[reps++];
            }
            double med, mn, p90;
            qsort(ts, reps, sizeof(double), cmpd);
            med = ts[reps / 2]; mn = ts[0];
            p90 = ts[(reps * 9) / 10 < reps ? (reps * 9) / 10 : reps - 1];   /* noise indicator: p90 vs min */
            if (cpuspeed_mode) printf("%d,%.6f,%.6f,%d,%.0f\n", P, med, mn, reps, N / med);
            else printf("%s,%s,%d,%.6f,%.6f,%d,%.4f,%.4f,%.0f,%.6f\n", setname, VNAME[var], P, med, mn, reps,
                        cu / reps, cs / reps, N / med, p90);
            fflush(stdout);
        }
    }
    return 0;
}

static int cmd_check(const char *raw, int w, int h, long N) {
    Video v;
    if (video_open(&v, raw, w, h) || N > v.n) return 1;
    Res r;
    if (open_res(&v, &r)) return 1;
    double ref = 0, c;
    run_once(&v, V_FULL, 1, N, r.map, r.frames, &ref, NULL, NULL);
    int bad = 0;
    for (int P = 1; P <= 12; P += 3) {
        run_once(&v, V_FULL, P, N, r.map, r.frames, &c, NULL, NULL);
        int ok1 = fabs(c - ref) < 1e-6 * fabs(ref);
        double m;
        run_once(&v, V_MMAP, P, N, r.map, r.frames, &m, NULL, NULL);
        int ok2 = fabs(m - ref) < 1e-6 * fabs(ref);
        printf("P=%2d  full checksum %s   mmap checksum %s   (ref %.6f)\n", P, ok1 ? "OK" : "MISMATCH",
               ok2 ? "OK" : "MISMATCH", ref);
        bad |= !(ok1 && ok2);
    }
    return bad;
}

/* ---- per-worker analysis: dynamic chunk scheduling exactly like arch_a.c, with per-thread stats ---- */
typedef struct {
    const Video *v;
    long n_chunks, N;
    long next;
    pthread_mutex_t lock;
} WShared;

typedef struct {
    WShared *sh;
    int id;
    long chunks, frames;
    double busy_s, user_s, kernel_s;
    unsigned short cpu_chunks[64];   /* chunks whose processing STARTED on each logical CPU */
    double t_first, t_last;
} WStat;

static void *wworker(void *arg) {
    WStat *w = arg;
    WShared *sh = w->sh;
    const Video *v = sh->v;
    FILE *f = fopen(v->path, "rb");
    uint8_t *buf = malloc(v->frame_bytes);
    float h[NBINS];
    int npix = v->w * v->h;
    double sink = 0, t_start = now_sec();
    w->t_first = -1;
    for (;;) {
        pthread_mutex_lock(&sh->lock);
        long k = sh->next++;
        pthread_mutex_unlock(&sh->lock);
        if (k >= sh->n_chunks) break;
        long s = sh->N * k / sh->n_chunks, e = sh->N * (k + 1) / sh->n_chunks;
        DWORD cpu = GetCurrentProcessorNumber();
        if (cpu < 64) w->cpu_chunks[cpu]++;
        if (w->t_first < 0) w->t_first = now_sec();
        _fseeki64(f, (long long)s * (long long)v->frame_bytes, SEEK_SET);
        for (long i = s; i < e; i++) {
            if (fread(buf, 1, v->frame_bytes, f) != v->frame_bytes) break;
            frame_hist(buf, npix, h);
            sink += h[0];
        }
        w->chunks++;
        w->frames += e - s;
        w->t_last = now_sec();
    }
    w->busy_s = w->t_last - w->t_first;
    FILETIME c, e2, k2, u2;
    GetThreadTimes(GetCurrentThread(), &c, &e2, &k2, &u2);
    w->user_s = ft2s(u2);
    w->kernel_s = ft2s(k2);
    (void)t_start; (void)sink;
    free(buf);
    fclose(f);
    return NULL;
}

/* workers <raw> <w> <h> <N> <set> <P> <chunks_per_worker> [header 0/1] */
static int cmd_workers(const char *raw, int w, int h, long N, const char *setname, int P, int cpw, int header) {
    Video v;
    if (video_open(&v, raw, w, h) || N > v.n) { fprintf(stderr, "bad video / N\n"); return 1; }
    SetProcessAffinityMask(GetCurrentProcess(), SETMASK(setname));
    Res r;
    if (open_res(&v, &r)) return 1;
    for (long i = 0; i < N; i++) (void)r.map[(size_t)i * v.frame_bytes];   /* warm page cache */
    Sleep(30);
    WShared sh;
    memset(&sh, 0, sizeof sh);
    sh.v = &v; sh.n_chunks = (long)P * cpw; sh.N = N;
    pthread_mutex_init(&sh.lock, NULL);
    WStat *st = calloc(P, sizeof *st);
    pthread_t *th = malloc(P * sizeof *th);
    double t0 = now_sec();
    for (int t = 0; t < P; t++) { st[t].sh = &sh; st[t].id = t; pthread_create(&th[t], NULL, wworker, &st[t]); }
    for (int t = 0; t < P; t++) pthread_join(th[t], NULL);
    double wall = now_sec() - t0;
    if (header) printf("set,P,chunks_per_worker,N,wall_s,worker,chunks,frames,busy_s,user_s,kernel_s,cpus\n");
    for (int t = 0; t < P; t++) {
        printf("%s,%d,%d,%ld,%.6f,%d,%ld,%ld,%.6f,%.6f,%.6f,", setname, P, cpw, N, wall, t, st[t].chunks,
               st[t].frames, st[t].busy_s, st[t].user_s, st[t].kernel_s);
        int first = 1;
        for (int c = 0; c < 64; c++)
            if (st[t].cpu_chunks[c]) { printf("%s%d:%d", first ? "" : ";", c, st[t].cpu_chunks[c]); first = 0; }
        printf("\n");
    }
    return 0;
}

/* ---- crossover study: at what job size does a FIXED number of threads beat a pure sequential loop?
 * "seq" = the worker function run directly on the calling thread (no thread is created), pinned to the
 * fastest performance-core thread.  "P<k>" = k worker threads over all CPUs.  N = 0 frames measures the pure
 * fixed cost of a parallel run (create, open file, claim, join).  Interleaved rounds, best-of-N. */
static double run_seq_once(const Video *v, long N, const uint8_t *map, const uint8_t *frames, int seqcpu) {
    Job j = {V_FULL, v, 0, N, map, frames, 0};
    HANDLE th = GetCurrentThread();
    DWORD_PTR prev = seqcpu >= 0 ? SetThreadAffinityMask(th, (DWORD_PTR)1 << seqcpu) : 0;
    double t0 = now_sec();
    worker(&j);
    double dt = now_sec() - t0;
    if (seqcpu >= 0 && prev) SetThreadAffinityMask(th, prev);
    return dt;
}

static int cmd_cross(const char *raw, int w, int h, char *nlist, char *plist, int R, int seqcpu) {
    Video v;
    if (video_open(&v, raw, w, h) || R > 64) { fprintf(stderr, "bad args\n"); return 1; }
    Res r;
    if (open_res(&v, &r)) return 1;
    long Ns[64]; int Ps[16], nn = 0, np = 0;
    char *save = NULL;
    for (char *t = strtok_s(nlist, ",", &save); t && nn < 64; t = strtok_s(NULL, ",", &save)) { Ns[nn] = atol(t); if (Ns[nn] > v.n) Ns[nn] = v.n; nn++; }
    save = NULL;
    for (char *t = strtok_s(plist, ",", &save); t && np < 16; t = strtok_s(NULL, ",", &save)) Ps[np++] = atoi(t);
    for (long i = 0; i < v.n; i++) (void)r.map[(size_t)i * v.frame_bytes];            /* warm the whole file */
    int ncfg = np + 1;                                                                   /* config 0 = seq */
    double *ts = calloc((size_t)nn * ncfg * R, sizeof(double));
    SetProcessAffinityMask(GetCurrentProcess(), 0xFFF);
    Sleep(30);
    for (int round = -1; round < R; round++)
        for (int a = 0; a < nn; a++)
            for (int c = 0; c < ncfg; c++) {
                double t;
                if (c == 0) t = Ns[a] > 0 ? run_seq_once(&v, Ns[a], r.map, r.frames, seqcpu) : 0.0;
                else t = run_once(&v, V_FULL, Ps[c - 1], Ns[a], r.map, r.frames, NULL, NULL, NULL);
                if (round >= 0) ts[((size_t)a * ncfg + c) * R + round] = t;
            }
    printf("frames,config,median_s,min_s,p90_s,reps\n");
    for (int a = 0; a < nn; a++)
        for (int c = 0; c < ncfg; c++) {
            double *x = ts + ((size_t)a * ncfg + c) * R;
            qsort(x, R, sizeof(double), cmpd);
            char name[16];
            if (c == 0) snprintf(name, sizeof name, "seq"); else snprintf(name, sizeof name, "P%d", Ps[c - 1]);
            printf("%ld,%s,%.8f,%.8f,%.8f,%d\n", Ns[a], name, x[R / 2], x[0], x[(R * 9) / 10 < R ? (R * 9) / 10 : R - 1], R);
        }
    free(ts);
    return 0;
}

/* ---- interleaved scaling: round-robin over ALL configurations, R rounds.  Background load that drifts
 * over time then hits every configuration equally; the minimum over rounds is the interference-free
 * estimate (noise only ever adds time).  Output format identical to `scale`. ---- */
static int cmd_scalei(const char *raw, int w, int h, long N, const char *setname, char *variants, int maxP, int R) {
    Video v;
    if (video_open(&v, raw, w, h) || N > v.n || R > 64) { fprintf(stderr, "bad args\n"); return 1; }
    Res r;
    if (open_res(&v, &r)) return 1;
    for (long i = 0; i < N; i++) (void)r.map[(size_t)i * v.frame_bytes];
    int vars[V_NV], nv = 0;
    char *save = NULL;
    for (char *tok = strtok_s(variants, ",", &save); tok && nv < V_NV; tok = strtok_s(NULL, ",", &save))
        vars[nv++] = vparse(tok);
    int ncfg = nv * maxP;
    double (*ts)[64] = calloc(ncfg, sizeof *ts);
    double *cu = calloc(ncfg, sizeof(double)), *cs = calloc(ncfg, sizeof(double));
    SetProcessAffinityMask(GetCurrentProcess(), SETMASK(setname));
    Sleep(30);
    for (int round = -1; round < R; round++)            /* round -1 is a warm-up pass */
        for (int c = 0; c < ncfg; c++) {
            double a = 0, b = 0;
            double t = run_once(&v, vars[c / maxP], c % maxP + 1, N, r.map, r.frames, NULL, &a, &b);
            if (round >= 0) { ts[c][round] = t; cu[c] += a; cs[c] += b; }
        }
    printf("set,variant,P,median_s,min_s,reps,cpu_user_s,cpu_sys_s,fps,p90_s\n");
    for (int c = 0; c < ncfg; c++) {
        qsort(ts[c], R, sizeof(double), cmpd);
        double med = ts[c][R / 2], mn = ts[c][0], p90 = ts[c][(R * 9) / 10 < R ? (R * 9) / 10 : R - 1];
        printf("%s,%s,%d,%.6f,%.6f,%d,%.4f,%.4f,%.0f,%.6f\n", setname, VNAME[vars[c / maxP]], c % maxP + 1, med, mn, R,
               cu[c] / R, cs[c] / R, N / med, p90);
    }
    return 0;
}

int main(int argc, char **argv) {
    {   /* OS_PRIORITY=high|above : run the benchmark ahead of background work */
        const char *pr = getenv("OS_PRIORITY");
        if (pr && !strcmp(pr, "high")) SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
        else if (pr && !strcmp(pr, "above")) SetPriorityClass(GetCurrentProcess(), ABOVE_NORMAL_PRIORITY_CLASS);
    }
    if (argc >= 9 && !strcmp(argv[1], "crossover")) {          /* crossover raw w h Nlist Plist rounds seqcpu */
        char *nl = _strdup(argv[5]), *pl = _strdup(argv[6]);
        return cmd_cross(argv[2], atoi(argv[3]), atoi(argv[4]), nl, pl, atoi(argv[7]), atoi(argv[8]));
    }
    if (argc >= 10 && !strcmp(argv[1], "scalei")) {
        char *vv = _strdup(argv[7]);
        return cmd_scalei(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]), argv[6], vv, atoi(argv[8]), atoi(argv[9]));
    }
    if (argc >= 2 && !strcmp(argv[1], "env")) return cmd_env(argc > 2 ? atof(argv[2]) : 12.0);
    if (argc >= 9 && !strcmp(argv[1], "workers"))
        return cmd_workers(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]), argv[6], atoi(argv[7]), atoi(argv[8]), argc > 9 ? atoi(argv[9]) : 1);
    if (argc >= 6 && !strcmp(argv[1], "check")) return cmd_check(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]));
    if (argc >= 6 && !strcmp(argv[1], "cpuspeed")) {
        char v[] = "full";
        return cmd_scale(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]), "single", v, 12, 1);
    }
    if (argc >= 9 && !strcmp(argv[1], "scale")) {
        char *vv = _strdup(argv[7]);
        return cmd_scale(argv[2], atoi(argv[3]), atoi(argv[4]), atol(argv[5]), argv[6], vv, atoi(argv[8]), 0);
    }
    fprintf(stderr, "usage: see source header\n");
    return 1;
}

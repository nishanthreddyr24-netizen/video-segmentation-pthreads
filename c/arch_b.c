/* Architecture B: reader -> bounded queue -> worker pool -> merger.
 * Classic producer/consumer with one mutex and two condition variables.
 * Decoding (file read) is SERIAL here: one reader feeds everyone. */
#define _FILE_OFFSET_BITS 64
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

#include "common.h"

typedef struct {
    long idx;
    uint8_t *data; /* NULL = poison pill: "no more frames" */
} Item;

typedef struct {
    Item *buf;
    int cap, head, tail, count;
    pthread_mutex_t lock;
    pthread_cond_t not_full, not_empty;
} Queue;

static void q_init(Queue *q, int cap) {
    q->buf = malloc(cap * sizeof(Item));
    q->cap = cap;
    q->head = q->tail = q->count = 0;
    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_full, NULL);
    pthread_cond_init(&q->not_empty, NULL);
}

static void q_destroy(Queue *q) {
    free(q->buf);
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->not_full);
    pthread_cond_destroy(&q->not_empty);
}

static void q_put(Queue *q, Item it) {
    pthread_mutex_lock(&q->lock);
    while (q->count == q->cap)                  /* full -> sleep */
        pthread_cond_wait(&q->not_full, &q->lock);
    q->buf[q->tail] = it;
    q->tail = (q->tail + 1) % q->cap;
    q->count++;
    pthread_cond_signal(&q->not_empty);
    pthread_mutex_unlock(&q->lock);
}

static Item q_get(Queue *q) {
    pthread_mutex_lock(&q->lock);
    while (q->count == 0)                       /* empty -> sleep */
        pthread_cond_wait(&q->not_empty, &q->lock);
    Item it = q->buf[q->head];
    q->head = (q->head + 1) % q->cap;
    q->count--;
    pthread_cond_signal(&q->not_full);
    pthread_mutex_unlock(&q->lock);
    return it;
}

typedef struct {
    const Video *v;
    ShotResult *r;
    int nworkers;
    Queue q;
    /* merger hand-off: done[i]=1 once hists[i] is written */
    char *done;
    pthread_mutex_t dlock;
    pthread_cond_t dcond;
} Pipe;

static void *reader(void *arg) {
    Pipe *p = arg;
    FILE *f = fopen(p->v->path, "rb");
    for (long i = 0; i < p->v->n; i++) {
        uint8_t *fr = malloc(p->v->frame_bytes);
        if (fread(fr, 1, p->v->frame_bytes, f) != p->v->frame_bytes) {
            free(fr);
            break;
        }
        q_put(&p->q, (Item){i, fr});
    }
    fclose(f);
    for (int i = 0; i < p->nworkers; i++) q_put(&p->q, (Item){-1, NULL});
    return NULL;
}

static void *worker(void *arg) {
    Pipe *p = arg;
    int npix = p->v->w * p->v->h;
    for (;;) {
        Item it = q_get(&p->q);
        if (!it.data) break;
        frame_hist(it.data, npix, p->r->hists + (size_t)it.idx * NBINS);
        free(it.data);
        pthread_mutex_lock(&p->dlock);
        p->done[it.idx] = 1;
        pthread_cond_signal(&p->dcond);
        pthread_mutex_unlock(&p->dlock);
    }
    return NULL;
}

static void *merger(void *arg) {
    Pipe *p = arg;
    long n = p->v->n, nxt = 0;
    while (nxt < n) {
        long avail = nxt;
        pthread_mutex_lock(&p->dlock);
        while (!p->done[nxt]) pthread_cond_wait(&p->dcond, &p->dlock);
        while (avail < n && p->done[avail]) avail++;   /* ready run */
        pthread_mutex_unlock(&p->dlock);
        for (; nxt < avail; nxt++) {
            float *h = p->r->hists + (size_t)nxt * NBINS;
            p->r->diffs[nxt] = nxt ? bhattacharyya(h - NBINS, h) : 0.f;
        }
    }
    return NULL;
}

int detect_pipeline(const Video *v, int nthreads, int queue_size,
                    ShotResult *r) {
    double t0 = now_sec();
    Pipe p = {.v = v, .r = r, .nworkers = nthreads};
    q_init(&p.q, queue_size);
    p.done = calloc(v->n, 1);
    pthread_mutex_init(&p.dlock, NULL);
    pthread_cond_init(&p.dcond, NULL);

    pthread_t rd, mg, *w = malloc(nthreads * sizeof *w);
    pthread_create(&rd, NULL, reader, &p);
    pthread_create(&mg, NULL, merger, &p);
    for (int i = 0; i < nthreads; i++) pthread_create(&w[i], NULL, worker, &p);
    pthread_join(rd, NULL);
    for (int i = 0; i < nthreads; i++) pthread_join(w[i], NULL);
    pthread_join(mg, NULL);
    double t1 = now_sec();

    q_destroy(&p.q);
    pthread_mutex_destroy(&p.dlock);
    pthread_cond_destroy(&p.dcond);
    free(p.done);
    free(w);
    r->ncuts = adaptive_threshold(r->diffs, v->n, 25, 4.0, 8, 0.15, r->cuts);
    double t2 = now_sec();
    r->t_parallel = t1 - t0;
    r->t_threshold = t2 - t1;
    r->t_total = t2 - t0;
    return 0;
}

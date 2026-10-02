/* Experiment 6: time the four scene-layer stages on N synthetic shots,
 * without any video I/O. Shots come in scenes of 4..8 shots, two alternating
 * "angles" per scene, each angle a noisy sparse histogram. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "scenes.h"

static unsigned long long rs = 88172645463325252ULL;
static double rnd(void) { /* xorshift64 */
    rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17;
    return (rs >> 11) * (1.0 / 9007199254740992.0);
}

int scene_bench(long ns, int nt, int reps) {
    float *feat = calloc((size_t)ns * NBINS, sizeof(float));
    long i = 0;
    while (i < ns) {
        int len = 4 + (int)(rnd() * 5);
        int pk[2] = {(int)(rnd() * NBINS), (int)(rnd() * NBINS)};
        for (int j = 0; j < len && i < ns; j++, i++) {
            float *f = feat + (size_t)i * NBINS;
            for (int b = 0; b < NBINS; b++) f[b] = (float)rnd() * 0.01f;
            f[pk[j & 1]] += 1.0f;
            float sum = 0; for (int b = 0; b < NBINS; b++) sum += f[b];
            for (int b = 0; b < NBINS; b++) f[b] /= sum;
        }
    }
    SceneParams p = scene_defaults();
    double best[4] = {1e9, 1e9, 1e9, 1e9}, bt = 1e9;
    long nsc = 0;
    for (int r = 0; r < reps; r++) {
        SceneResult sr;
        segment_scenes(feat, ns, nt, &p, &sr);
        double t = sr.t_sim + sr.t_dp_thread + sr.t_phase + sr.t_dp_scene;
        if (t < bt) {
            bt = t;
            best[0] = sr.t_sim; best[1] = sr.t_dp_thread;
            best[2] = sr.t_phase; best[3] = sr.t_dp_scene;
        }
        nsc = sr.nscenes;
        sceneresult_free(&sr);
    }
    printf("%ld,%d,%ld,%.6f,%.6f,%.6f,%.6f,%.6f\n", ns, nt, nsc, best[0],
           best[1], best[2], best[3], bt);
    free(feat);
    return 0;
}

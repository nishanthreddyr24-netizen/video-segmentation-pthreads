/* scene_api.c - flat C entry point so Python (ctypes) can run the scene layer
 * thousands of times on cached descriptors without re-reading any video. */
#include <stdint.h>
#include <stdlib.h>

#include "features.h"
#include "scenes.h"

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

/* kf: ns x K x fd.  blocks: nb, off[], ncells[], bins[], w[] describe the layout.
 * Writes the first-shot index of every scene into first_out; returns #scenes. */
EXPORT long scenes_run(const float *kf, long ns, int K, int fd, int klo, int khi,
                       int nb, const int *off, const int *ncells, const int *bins,
                       const double *w, int T, int k, double tau, double lam_new,
                       double mu, double lam_scene, int max_phases, int nthreads,
                       int64_t *first_out, long max_out) {
    FeatLayout L = {0};
    L.nblocks = nb;
    L.fd = fd;
    for (int i = 0; i < nb; i++) {
        L.off[i] = off[i]; L.ncells[i] = ncells[i]; L.bins[i] = bins[i]; L.w[i] = w[i];
    }
    SceneParams p = {T, k, tau, lam_new, mu, lam_scene, max_phases};
    SceneResult sr;
    segment_scenes(kf, ns, K, klo, khi, &L, nthreads, &p, &sr);
    long n = sr.nscenes < max_out ? sr.nscenes : max_out;
    for (long i = 0; i < n; i++) first_out[i] = sr.scene_first_shot[i];
    long total = sr.nscenes;
    sceneresult_free(&sr);
    return total;
}

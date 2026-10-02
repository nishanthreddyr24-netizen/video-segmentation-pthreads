/* usage: shotseg <raw file> <w> <h> <mode> [threads] [chunks_per_thread|queue]
 *   mode: seq | a | b
 * Prints timing + cuts; writes results\diffs_<mode>.bin / cuts_<mode>.txt   */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common.h"
#include "scenes.h"

int main(int argc, char **argv) {
    if (argc >= 5 && !strcmp(argv[1], "scenebench")) /* scenebench N threads reps */
        return scene_bench(atol(argv[2]), atoi(argv[3]), atoi(argv[4]));
    if (argc < 5) {
        fprintf(stderr, "usage: %s file w h seq|a|b [threads] [extra]\n", argv[0]);
        return 1;
    }
    Video v;
    if (video_open(&v, argv[1], atoi(argv[2]), atoi(argv[3])) != 0) {
        fprintf(stderr, "cannot open %s\n", argv[1]);
        return 1;
    }
    const char *mode = argv[4];
    int nt = argc > 5 ? atoi(argv[5]) : 4;
    int extra = argc > 6 ? atoi(argv[6]) : 0;
    ShotResult r;
    shotresult_alloc(&r, v.n);

    int rc;
    if (!strcmp(mode, "seq"))    rc = detect_sequential(&v, &r);
    else if (!strcmp(mode, "a") || !strcmp(mode, "scenes")) rc = detect_chunked(&v, nt, extra ? extra : 4, &r);
    else if (!strcmp(mode, "b")) rc = detect_pipeline(&v, nt, extra ? extra : 64, &r);
    else { fprintf(stderr, "unknown mode\n"); return 1; }
    if (rc) { fprintf(stderr, "detector failed\n"); return 1; }

    printf("mode=%s threads=%d frames=%ld cuts=%ld\n", mode, nt, v.n, r.ncuts);
    printf("time: parallel-stage=%.3fs threshold=%.4fs total=%.3fs  (%.0f frames/s)\n",
           r.t_parallel, r.t_threshold, r.t_total, v.n / r.t_total);

    char name[128];
    snprintf(name, sizeof name, "results/cuts_%s_%d.txt", mode, nt);
    FILE *f = fopen(name, "w");
    if (f) {
        for (long i = 0; i < r.ncuts; i++) fprintf(f, "%ld\n", r.cuts[i]);
        fclose(f);
    }
    snprintf(name, sizeof name, "results/diffs_%s_%d.bin", mode, nt);
    f = fopen(name, "wb");
    if (f) {
        fwrite(r.diffs, sizeof(float), v.n, f);
        fclose(f);
    }
    if (!strcmp(mode, "scenes")) {
        Shot *shots = malloc((r.ncuts + 1) * sizeof(Shot));
        long ns = shots_from_cuts(r.cuts, r.ncuts, v.n, shots);
        float *feat = malloc((size_t)ns * NBINS * sizeof(float));
        shot_features(r.hists, shots, ns, feat);
        SceneParams sp = scene_defaults();
        /* optional overrides for parameter studies */
        if (getenv("SCENE_TAU"))      sp.tau = atof(getenv("SCENE_TAU"));
        if (getenv("SCENE_LAMNEW"))   sp.lam_new = atof(getenv("SCENE_LAMNEW"));
        if (getenv("SCENE_MU"))       sp.mu = atof(getenv("SCENE_MU"));
        if (getenv("SCENE_LAMSCENE")) sp.lam_scene = atof(getenv("SCENE_LAMSCENE"));
        if (getenv("SCENE_K"))        sp.k = atoi(getenv("SCENE_K"));
        SceneResult sr;
        segment_scenes(feat, ns, nt, &sp, &sr);
        double tot = sr.t_sim + sr.t_dp_thread + sr.t_phase + sr.t_dp_scene;
        printf("shots=%ld phases=%ld scenes=%ld\n", ns, sr.nphases, sr.nscenes);
        printf("scene stages: similarity(par)=%.5fs thread-DP=%.5fs phases=%.6fs scene-DP=%.5fs  serial=%.0f%%\n",
               sr.t_sim, sr.t_dp_thread, sr.t_phase, sr.t_dp_scene,
               100.0 * (sr.t_dp_thread + sr.t_phase + sr.t_dp_scene) / tot);
        snprintf(name, sizeof name, "results/scenes_%d.txt", nt);
        f = fopen(name, "w");
        if (f) {
            for (long i = 0; i < sr.nscenes; i++)
                fprintf(f, "%ld\n", shots[sr.scene_first_shot[i]].start);
            fclose(f);
        }
        sceneresult_free(&sr);
        free(shots);
        free(feat);
    }
    shotresult_free(&r);
    return 0;
}

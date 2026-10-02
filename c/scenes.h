/* scenes.h - simplified Liu et al. (2013) scene segmentation.
 * NOTE: "shot thread" = chain of visually similar shots (editing concept),
 * NOT a CPU thread. */
#ifndef SCENES_H
#define SCENES_H

#include "common.h"

typedef struct { long start, end; } Shot; /* [start, end) in frames */

typedef struct {
    int T;              /* context window (shots)          default 18  */
    int k;              /* max parent jump (shots)         default 9   */
    double tau;         /* max distance to link to parent  default 0.4 */
    double lam_new;     /* cost of starting a new thread   default 0.4 */
    double mu;          /* cost of changing parent offset  default 0.05*/
    double lam_scene;   /* cost of opening a new scene     default 0.3 */
    int max_phases;     /* max phases per scene            default 8   */
} SceneParams;

typedef struct {
    long nshots, nphases, nscenes;
    long *scene_first_shot; /* nscenes entries */
    double t_sim, t_dp_thread, t_phase, t_dp_scene; /* seconds per stage */
} SceneResult;

SceneParams scene_defaults(void);
long shots_from_cuts(const long *cuts, long ncuts, long nframes, Shot *out);
void shot_features(const float *hists, const Shot *shots, long ns, float *feat);
int segment_scenes(const float *feat, long ns, int nthreads,
                   const SceneParams *p, SceneResult *out);
void sceneresult_free(SceneResult *r);
/* synthetic N-shot benchmark of the scene layer only (Experiment 6) */
int scene_bench(long nshots, int nthreads, int reps);

#endif

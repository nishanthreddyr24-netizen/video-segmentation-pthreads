"""Grid search of scene parameters on DEV videos only; objective = pooled F1 at 2 s tolerance."""
import itertools, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_rai import evaluate

DEV = [1, 2, 3, 4, 5]
rows = []
for tau, mu, lam in itertools.product((0.03, 0.06, 0.1, 0.15, 0.25), (0.02, 0.05), (0.03, 0.06, 0.1, 0.2)):
    env = {"SCENE_TAU": str(tau), "SCENE_LAMNEW": str(tau), "SCENE_MU": str(mu), "SCENE_LAMSCENE": str(lam)}
    r = evaluate(DEV, 8, (), verbose=False, env=env)
    rows.append((r[50][2], tau, mu, lam, r[50][0], r[50][1]))
rows.sort(reverse=True)
print("F1@2s   tau   mu   lam_scene  P  R   (dev videos 1-5)")
for f, tau, mu, lam, P, R in rows[:8]:
    print(f"{f:.3f}  {tau:<5} {mu:<5} {lam:<6}  {P:.2f} {R:.2f}")

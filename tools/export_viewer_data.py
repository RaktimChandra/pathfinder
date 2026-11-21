"""Export compact per-sequence data for the interactive results page (docs/index.html)."""
import sys, glob, os, json, warnings
import numpy as np
warnings.filterwarnings('ignore'); sys.path.insert(0, 'src'); sys.path.insert(0, 'tools')
import main as M
from research_common import load_gt
from baselines import const
r = json.load(open('results/baselines.json'))
files = sorted(glob.glob('data/deg/*_H1.csv')) + sorted(glob.glob('data/deg_hold/*_H1.csv')) + sorted(glob.glob('data/deg_mh/*_H1.csv'))
out = {}
for f in files:
    b = os.path.basename(f)[:-4]; seq = b.rsplit('_', 1)[0]; g = 'data/raw/%s_gt.csv' % seq
    M.run(f, '/tmp/v_e.txt', sigma_out='/tmp/v_s.txt')
    gts, P, *_ = load_gt(g)
    e = np.loadtxt('/tmp/v_e.txt'); t = e[:, 0]; pe = e[:, 1:4]; tg = gts * 1e-9
    sg = np.loadtxt('/tmp/v_s.txt')[:, 1:4]
    m = (t >= tg[0]) & (t <= tg[-1]); t, pe, sg = t[m], pe[m], sg[m]
    pg = np.stack([np.interp(t, tg, P[:, k]) for k in range(3)], 1)
    mu1, mu2 = pe.mean(0), pg.mean(0); H = (pe - mu1).T @ (pg - mu2)
    U, S, Vt = np.linalg.svd(H); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(Vt.T @ U.T)); R = Vt.T @ D @ U.T
    pa = (R @ (pe - mu1).T).T + mu2
    err = np.linalg.norm(pa - pg, axis=1); s3 = np.linalg.norm(sg, axis=1)
    d = np.loadtxt(f, delimiter=',', comments='#'); dead = np.all(d[:, 1:7] == 0, axis=1)
    tf = (d[dead, 0].min() * 1e-9 - t[0]) if dead.any() else None
    step = max(1, len(t) // 600); i = np.arange(0, len(t), step)
    out[seq] = dict(t=np.round(t[i] - t[0], 2).tolist(), gt=np.round(pg[i] - mu2, 3).tolist(), est=np.round(pa[i] - mu2, 3).tolist(),
                    err=np.round(err[i], 3).tolist(), sig=np.round(s3[i], 3).tolist(), t_fail=None if tf is None else round(float(tf), 2),
                    scores={h: {k: {m2: round(r[seq + '_' + h][k][m2], 3) for m2 in ['ate_rmse', 'waypoint_rmse', 'blind5_rmse', 'dropout_rmse']} for k in ['ours', 'const']} for h in ['H1', 'H2']},
                    naive=round((r[seq + '_H1']['naive']['ate_rmse'] + r[seq + '_H2']['naive']['ate_rmse']) / 2, 1))
    print(seq, len(i), flush=True)
data = json.dumps(out, separators=(',', ':')).replace('</', '<\\/')
open('docs/index.html', 'w').write(open('tools/viewer_template.html').read().replace('__DATA__', data))
print('wrote docs/index.html')

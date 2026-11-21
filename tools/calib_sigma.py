"""Calibration of the optional --sigma output: is the true (SE(3)-aligned) position error
inside the reported 1-sigma as often as it should be? Per-axis target is 68.3%."""
import sys, glob, os, json, warnings
import numpy as np
warnings.filterwarnings('ignore'); sys.path.insert(0, 'src'); sys.path.insert(0, 'tools')
import main as M
from research_common import load_gt

def aligned_err(est, gt_csv):
    gts, P, *_ = load_gt(gt_csv)
    e = np.loadtxt(est); t = e[:, 0]; pe = e[:, 1:4]; tg = gts * 1e-9
    m = (t >= tg[0]) & (t <= tg[-1]); t, pe = t[m], pe[m]
    pg = np.stack([np.interp(t, tg, P[:, k]) for k in range(3)], 1)
    mu1, mu2 = pe.mean(0), pg.mean(0); H = (pe - mu1).T @ (pg - mu2)
    U, S, Vt = np.linalg.svd(H); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(Vt.T @ U.T)); R = Vt.T @ D @ U.T
    pa = (R @ (pe - mu1).T).T + mu2
    return m, (pa - pg) @ R   # error expressed back in the estimate's frame (sigma's axes)

if __name__ == '__main__':
    files = sorted(glob.glob('data/deg/*.csv')) + sorted(glob.glob('data/deg_hold/*.csv')) + sorted(glob.glob('data/deg_mh/*.csv'))
    z = {}
    for f in files:
        b = os.path.basename(f)[:-4]; g = 'data/raw/%s_gt.csv' % b.rsplit('_', 1)[0]
        M.run(f, '/tmp/cs_e.txt', P={'sigma_scale': 1.0}, sigma_out='/tmp/cs_s.txt')
        m, err = aligned_err('/tmp/cs_e.txt', g)
        sg = np.loadtxt('/tmp/cs_s.txt')[:, 1:4][m]
        z[b] = (np.abs(err) / np.maximum(sg, 1e-6))[::20]       # thin to ~10 Hz
        print('%-24s raw coverage %.2f  median |e|/sigma %.2f' % (b, (z[b] < 1).mean(), np.median(z[b])), flush=True)
    seqs = sorted({k.rsplit('_', 1)[0] for k in z})
    # leave-one-sequence-out: scale = 68.3th percentile of |e|/sigma on the other sequences
    cov = {}; scales = []
    for s in seqs:
        tr = np.concatenate([v.ravel() for k, v in z.items() if not k.startswith(s + '_')])
        sc = np.percentile(tr, 68.27); scales.append(sc)
        for k, v in z.items():
            if k.startswith(s + '_'):
                cov[k] = dict(cov1=float((v < sc).mean()), cov2=float((v < 2 * sc).mean()))
    allz = np.concatenate([v.ravel() for v in z.values()])
    final = float(np.percentile(allz, 68.27))
    out = dict(final_scale=final, loo_scales=[float(x) for x in scales],
               loo_coverage_1sigma_mean=float(np.mean([c['cov1'] for c in cov.values()])),
               loo_coverage_2sigma_mean=float(np.mean([c['cov2'] for c in cov.values()])),
               per_file=cov)
    json.dump(out, open('results/sigma_calibration.json', 'w'), indent=1)
    print('final scale %.3f | LOO scales %.3f-%.3f | held-out coverage 1s %.3f 2s %.3f (targets 0.683, 0.954)' % (
        final, min(scales), max(scales), out['loo_coverage_1sigma_mean'], out['loo_coverage_2sigma_mean']))

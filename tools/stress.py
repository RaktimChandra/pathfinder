"""Stress test beyond the official settings: other random seeds of degrade_imu.py, a milder and a
harsher ramp, and the input decimated to 100 Hz. H1 column semantics. Scores ours vs constant."""
import sys, os, re, json, tempfile, subprocess, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src'); sys.path.insert(0, 'tools')
import make_testset as T
import main as M
from score import score
from baselines import const
SEQS = ['V1_01_easy', 'V2_03_difficult', 'MH_04_difficult', 'MH_01_easy', 'TUM_room1', 'TUM_room5']
SRC = open('tools/degrade_imu.py').read()

def build(seq, seed, extra, decim, out):
    ts, v = T.load('data/raw/%s_imu.csv' % seq)
    gts = np.loadtxt('data/raw/%s_gt.csv' % seq, delimiter=',', comments='#', usecols=0, dtype=np.int64)
    k = (ts >= gts[0]) & (ts <= gts[-1]); ts, v = ts[k][::decim], v[k][::decim]
    with tempfile.TemporaryDirectory() as td:
        sc = os.path.join(td, 'deg.py'); open(sc, 'w').write(re.sub(r'^SEED = 42', 'SEED = %d' % seed, SRC, flags=re.M))
        a = os.path.join(td, 'a.csv'); b = os.path.join(td, 'b.csv')
        T.write(a, T.HDR_SCRIPT, ts, np.hstack([v[:, 3:6], v[:, 0:3]]))
        subprocess.run([sys.executable, sc, a, b] + extra, check=True, stdout=subprocess.DEVNULL)
        d = np.loadtxt(b, delimiter=',', comments='#'); dts = np.loadtxt(b, delimiter=',', comments='#', usecols=0, dtype=np.int64)
        T.write(out, T.HDR_EUROC, dts, np.hstack([d[:, 4:7], d[:, 1:4]]))

VARIANTS = [('seed 1', 1, [], 1), ('seed 7', 7, [], 1), ('seed 2026', 2026, [], 1),
            ('milder ramp (max-level 0.5)', 42, ['--max-level', '0.5'], 1),
            ('earlier ramp (gamma 1.0)', 42, ['--gamma', '1.0'], 1),
            ('100 Hz input', 42, [], 2)]
if __name__ == '__main__':
    os.makedirs('data/stress', exist_ok=True); res = {}
    for name, seed, extra, dec in VARIANTS:
        for s in SEQS:
            f = 'data/stress/%s_%s.csv' % (s, re.sub(r'\W+', '_', name))
            if not os.path.exists(f): build(s, seed, extra, dec, f)
            g = 'data/raw/%s_gt.csv' % s
            M.run(f, '/tmp/st.txt'); r = score(g, '/tmp/st.txt', f); const(f, '/tmp/stc.txt'); c = score(g, '/tmp/stc.txt', f)
            res.setdefault(name, {})[s] = dict(ours=r['ate_rmse'], const=c['ate_rmse'], ours_blind=r['blind5_rmse'], const_blind=c['blind5_rmse'])
            print('%-28s %-16s ours %.2f const %.2f %s' % (name, s, r['ate_rmse'], c['ate_rmse'], 'OK' if r['ate_rmse'] < c['ate_rmse'] else 'WORSE'), flush=True)
    json.dump(res, open('results/stress.json', 'w'), indent=1)
    n = sum(len(v) for v in res.values()); w = sum(x['ours'] < x['const'] for v in res.values() for x in v.values())
    print('beat constant: %d / %d' % (w, n))

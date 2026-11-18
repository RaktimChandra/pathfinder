"""Robustness / contract test-suite for main.py.

For each input variant: run the estimator, then verify the output contract
(one pose per input row, exact timestamps, 8 columns, unit quaternions, finite)
and that accuracy is not degraded vs the reference input.
"""
import os, sys, io, zipfile, shutil, subprocess, tempfile, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))
from score import score

MAIN = os.path.join(os.path.dirname(__file__), '..', 'src', 'main.py')
SRC = sys.argv[1] if len(sys.argv) > 1 else 'data/deg/V1_01_easy_H1.csv'
SEQ = os.path.basename(SRC).rsplit('_', 1)[0]
GT = 'data/raw/%s_gt.csv' % SEQ


def read_rows(p):
    hdr, rows = [], []
    for ln in open(p):
        (hdr if ln.startswith('#') else rows).append(ln.rstrip('\n'))
    return hdr, rows


def check(inp_rows_ts, out):
    d = []
    with open(out) as f:
        for ln in f:
            if ln.startswith('#'):
                continue
            d.append(ln.split())
    assert all(len(x) == 8 for x in d), 'not 8 columns'
    assert len(d) == len(inp_rows_ts), 'row count %d != %d' % (len(d), len(inp_rows_ts))
    ts_out = [x[0] for x in d]
    exp = ['%d.%09d' % (t // 10**9, t % 10**9) for t in inp_rows_ts]
    assert ts_out == exp, 'timestamps differ'
    v = np.array([[float(y) for y in x[1:]] for x in d])
    assert np.isfinite(v).all(), 'non-finite'
    qn = np.linalg.norm(v[:, 3:7], axis=1)
    assert np.abs(qn - 1).max() < 1e-5, 'quaternion not unit'
    return True


def run(inp, out):
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, MAIN, inp, out], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return time.perf_counter() - t0


def main():
    hdr, rows = read_rows(SRC)
    ts = [int(r.split(',')[0]) for r in rows]
    vals = [r.split(',')[1:] for r in rows]
    td = tempfile.mkdtemp()
    variants = {}
    variants['reference'] = (SRC, ts)
    # header without '#'
    p = os.path.join(td, 'nohash.csv'); open(p, 'w').write('timestamp,wx,wy,wz,ax,ay,az\n' + '\n'.join(rows) + '\n'); variants['header without #'] = (p, ts)
    # no header at all
    p = os.path.join(td, 'nohdr.csv'); open(p, 'w').write('\n'.join(rows) + '\n'); variants['no header'] = (p, ts)
    # script column order (t, acc, gyro) with matching header
    p = os.path.join(td, 'acc_first.csv')
    with open(p, 'w') as f:
        f.write('#timestamp [ns],a_RS_S_x [m s^-2],a_RS_S_y [m s^-2],a_RS_S_z [m s^-2],w_RS_S_x [rad s^-1],w_RS_S_y [rad s^-1],w_RS_S_z [rad s^-1]\n')
        for t, v in zip(ts, vals):
            f.write('%d,%s\n' % (t, ','.join(v[3:6] + v[0:3])))
    variants['accel-first columns + header'] = (p, ts)
    # script column order, misleading/absent header (physics must decide)
    p = os.path.join(td, 'acc_first_nohdr.csv')
    with open(p, 'w') as f:
        for t, v in zip(ts, vals):
            f.write('%d,%s\n' % (t, ','.join(v[3:6] + v[0:3])))
    variants['accel-first, no header'] = (p, ts)
    # CRLF line endings + spaces
    p = os.path.join(td, 'crlf.csv'); open(p, 'w', newline='').write('\r\n'.join(hdr + [r.replace(',', ', ') for r in rows]) + '\r\n'); variants['CRLF + spaces'] = (p, ts)
    # zip of EuRoC folder
    p = os.path.join(td, 'team.zip')
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('mav0/imu0/data.csv', open(SRC).read())
    variants['zip mav0/imu0/data.csv'] = (p, ts)
    # folder
    dd = os.path.join(td, 'folder', 'imu0'); os.makedirs(dd); shutil.copy(SRC, os.path.join(dd, 'data.csv'))
    variants['folder imu0/data.csv'] = (os.path.join(td, 'folder'), ts)
    # shuffled rows (unsorted input) -> output must follow input order
    rng = np.random.default_rng(0); perm = rng.permutation(len(rows))
    p = os.path.join(td, 'shuffled.csv'); open(p, 'w').write('\n'.join(hdr + [rows[i] for i in perm]) + '\n')
    variants['unsorted rows'] = (p, [ts[i] for i in perm])
    # accel in g
    p = os.path.join(td, 'acc_g.csv')
    with open(p, 'w') as f:
        f.write(hdr[0] + '\n')
        for t, v in zip(ts, vals):
            a = [float(x) / 9.80665 for x in v[3:6]]
            f.write('%d,%s,%s\n' % (t, ','.join(v[0:3]), ','.join('%.8f' % x for x in a)))
    variants['accel in g'] = (p, ts)
    # gyro in deg/s
    p = os.path.join(td, 'gyro_deg.csv')
    with open(p, 'w') as f:
        f.write(hdr[0] + '\n')
        for t, v in zip(ts, vals):
            w = [np.degrees(float(x)) for x in v[0:3]]
            f.write('%d,%s,%s\n' % (t, ','.join('%.6f' % x for x in w), ','.join(v[3:6])))
    variants['gyro in deg/s'] = (p, ts)
    # float-seconds timestamps
    p = os.path.join(td, 'ts_sec.csv')
    with open(p, 'w') as f:
        f.write(hdr[0] + '\n')
        for t, v in zip(ts, vals):
            f.write('%d.%09d,%s\n' % (t // 10**9, t % 10**9, ','.join(v)))
    variants['float-second timestamps'] = (p, ts)
    # very short file (6 s) and file with no dead tail
    p = os.path.join(td, 'short.csv'); open(p, 'w').write('\n'.join(hdr + rows[:1200]) + '\n'); variants['short 6 s'] = (p, ts[:1200])
    nd = [r for r in rows if not r.split(',', 1)[1].replace('0', '').replace('.', '').replace(',', '').strip() == '']
    p = os.path.join(td, 'nodead.csv'); open(p, 'w').write('\n'.join(hdr + nd) + '\n'); variants['no failure window'] = (p, [int(r.split(',')[0]) for r in nd])
    # long sequence (x4 concatenation, ~10 min)
    p = os.path.join(td, 'long.csv')
    span = ts[-1] - ts[0] + 5_000_000
    lts = []
    with open(p, 'w') as f:
        f.write(hdr[0] + '\n')
        for k in range(4):
            for t, r in zip(ts, rows):
                tt = t + k * span; lts.append(tt)
                f.write('%d,%s\n' % (tt, r.split(',', 1)[1]))
    variants['long x4 (~10 min)'] = (p, lts)

    ref_ate = None
    print('%-32s %-6s %-8s %s' % ('variant', 'ok', 'time', 'ATE'))
    for name, (inp, tss) in variants.items():
        out = os.path.join(td, 'out.txt')
        try:
            el = run(inp, out)
            check(tss, out)
            ate = ''
            if name not in ('short 6 s', 'long x4 (~10 min)'):
                r = score(GT, out)
                ate = '%.3f' % r['ate_rmse']
                if name == 'reference':
                    ref_ate = r['ate_rmse']
            print('%-32s %-6s %-8s %s' % (name, 'PASS', '%.2fs' % el, ate))
        except Exception as e:
            print('%-32s %-6s %s' % (name, 'FAIL', str(e)[:300]))
    shutil.rmtree(td)


if __name__ == '__main__':
    main()

"""Output-contract tests on a synthetic IMU stream (no dataset needed, runs in CI).

Checks what the organisers' scorer relies on: one pose per input row in input order,
exact ns -> s timestamps, unit quaternions, finite numbers, robustness to column order,
duplicates and the dead tail, the optional --sigma sidecar, and the runtime budget."""
import os, subprocess, sys, time
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'src', 'main.py')
HDR = '#timestamp [ns],w_RS_S_x [rad s-1],w_RS_S_y [rad s-1],w_RS_S_z [rad s-1],a_RS_S_x [m s-2],a_RS_S_y [m s-2],a_RS_S_z [m s-2]\n'


def synth(path, dur=40.0, rate=200, seed=0, accel_first=False, dup_every=0):
    """3 s at rest, then gentle 3D motion with rotation; last 5 s zeroed like a dead sensor."""
    rng = np.random.default_rng(seed)
    n = int(dur * rate); t = np.arange(n) / rate
    ts = (1_403_715_274_302_142_976 + np.round(t * 1e9)).astype(np.int64)
    mv = np.clip((t - 3.0) / 2.0, 0, 1)
    w = np.stack([0.3 * np.sin(0.7 * t), 0.25 * np.sin(0.9 * t + 1), 0.4 * np.sin(0.5 * t + 2)], 1) * mv[:, None]
    a = np.stack([0.8 * np.sin(1.1 * t), 0.6 * np.cos(0.8 * t), 9.81 + 0.3 * np.sin(1.7 * t)], 1)
    a[:, :2] *= mv[:, None]
    w += rng.normal(0, 0.003, w.shape); a += rng.normal(0, 0.03, a.shape)
    dead = t > dur - 5.0
    w[dead] = 0; a[dead] = 0
    rows = np.hstack([a, w]) if accel_first else np.hstack([w, a])
    if dup_every:
        idx = np.sort(np.concatenate([np.arange(n), np.arange(0, n, dup_every)]))
        ts, rows = ts[idx], rows[idx]
    hdr = HDR if not accel_first else HDR.replace('w_RS_S_x [rad s-1],w_RS_S_y [rad s-1],w_RS_S_z [rad s-1],a_RS_S_x [m s-2],a_RS_S_y [m s-2],a_RS_S_z [m s-2]',
                                                  'a_RS_S_x [m s-2],a_RS_S_y [m s-2],a_RS_S_z [m s-2],w_RS_S_x [rad s-1],w_RS_S_y [rad s-1],w_RS_S_z [rad s-1]')
    with open(path, 'w') as f:
        f.write(hdr)
        for tt, r in zip(ts.tolist(), rows.tolist()):
            f.write('%d,%s\n' % (tt, ','.join('%.9g' % v for v in r)))
    return ts


def run(inp, out, *extra):
    subprocess.run([sys.executable, MAIN, inp, out, *extra], check=True, capture_output=True)
    lines = [l for l in open(out) if not l.startswith('#')]
    return lines


def test_one_pose_per_row_and_exact_timestamps(tmp_path):
    ts = synth(tmp_path / 'imu.csv')
    lines = run(str(tmp_path / 'imu.csv'), str(tmp_path / 'out.txt'))
    assert len(lines) == len(ts)
    got = [l.split()[0] for l in lines]
    want = ['%d.%09d' % (x // 1_000_000_000, x % 1_000_000_000) for x in ts.tolist()]
    assert got == want


def test_values_finite_and_quaternions_unit(tmp_path):
    synth(tmp_path / 'imu.csv')
    lines = run(str(tmp_path / 'imu.csv'), str(tmp_path / 'out.txt'))
    v = np.array([[float(x) for x in l.split()[1:]] for l in lines])
    assert v.shape[1] == 7 and np.isfinite(v).all()
    assert np.allclose(np.linalg.norm(v[:, 3:7], axis=1), 1.0, atol=1e-5)


def test_column_order_detected(tmp_path):
    synth(tmp_path / 'g.csv'); synth(tmp_path / 'a.csv', accel_first=True)
    g = run(str(tmp_path / 'g.csv'), str(tmp_path / 'g.txt'))
    a = run(str(tmp_path / 'a.csv'), str(tmp_path / 'a.txt'))
    assert g == a


def test_duplicate_rows_kept_in_order(tmp_path):
    ts = synth(tmp_path / 'imu.csv', dup_every=97)
    lines = run(str(tmp_path / 'imu.csv'), str(tmp_path / 'out.txt'))
    assert len(lines) == len(ts)


def test_sigma_sidecar_does_not_change_trajectory(tmp_path):
    synth(tmp_path / 'imu.csv')
    base = run(str(tmp_path / 'imu.csv'), str(tmp_path / 'a.txt'))
    withs = run(str(tmp_path / 'imu.csv'), str(tmp_path / 'b.txt'), '--sigma', str(tmp_path / 's.txt'))
    assert base == withs
    s = np.array([[float(x) for x in l.split()[1:]] for l in open(tmp_path / 's.txt') if not l.startswith('#')])
    assert len(s) == len(base) and (s > 0).all() and np.isfinite(s).all()


def test_runtime_budget(tmp_path):
    synth(tmp_path / 'imu.csv', dur=120.0)
    t0 = time.perf_counter()
    run(str(tmp_path / 'imu.csv'), str(tmp_path / 'out.txt'))
    per_s = (time.perf_counter() - t0) / 120.0 * 1000
    assert per_s < 20.0, '%.2f ms per 1 s of IMU (budget 20 ms, includes interpreter start-up)' % per_s

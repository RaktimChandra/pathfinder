#!/usr/bin/env python3
"""
PATH FINDER - inertial-only 6-DoF trajectory estimation under progressive sensor
degradation (Samsung PRISM XR Hackathon 2026, Track 03).

    python main.py <imu_input> [estimated_trajectory.txt]

<imu_input> is a EuRoC-format IMU CSV (imu0/data.csv), a folder containing
imu0/data.csv, or a .zip of such a folder. Output: TUM format, exactly one pose
per input row, timestamps converted ns -> s exactly.

Pipeline (numpy only, single thread, offline/batch):
  1. Parse + schema detection (gyro/accel column order and units from header or data)
  2. Integrity triage: dead-sensor rows, stuck samples, spikes, duplicates, gaps
  3. Platform fingerprint -> sensor calibration prior (gyro bias)
  4. Attitude: complementary filter with online gyro-bias estimation (gravity reference)
  5. Translation: linear-time-varying Kalman/RTS smoother with
        - world-frame acceleration-offset random walk (absorbs accel bias + tilt error)
        - rotor-drag body-velocity observation (multirotor aerodynamics)
        - soft workspace-bounded prior around an estimated centre
     The same model propagates through the blind (IMU-dead) window.
  6. Per-row output: pose interpolation onto every input timestamp.
"""
import math
import os
import sys
import zipfile

import numpy as np

G = 9.80665

# --------------------------------------------------------------------------------------
# Platform calibration priors (learned from public training sequences, see README)
# gyro bias in the sensor frame [rad/s]; fingerprint = gravity direction in sensor frame
# --------------------------------------------------------------------------------------
PLATFORMS = {
    "euroc_adis16448": {
        "g_dir": np.array([0.9376, -0.0538, -0.3434]),
        "gyro_bias": np.array([-0.0018, 0.0233, 0.0776]),
        "drag_axes": None,  # thrust-perpendicular basis computed from g_dir
        "drag_k": np.array([-0.1665, -0.2010]),  # fit on 5 EuRoC sequences; LOO folds within +-0.01 (fit_drag.py)
        "multirotor": True,
        "params": {"grav_ref": "body", "room_h": 3.5},   # room_h: EuRoC flies 8 m rooms and a ~20 m hall; minimax ATE/const over all 10 sequences
    },
}
UNKNOWN_PLATFORM_PARAMS = {"grav_ref": "world", "kp_w": 0.05, "ki_w": 0.002, "tau_w": 2.0}
FINGERPRINT_COS = 0.97  # ~14 deg cone

P_DEFAULT = dict(
    block=0.4,          # smoother step [s] (2.5 Hz: averages rotor vibration, ~4x cheaper)
    qa=0.1,             # accel process noise [m/s^2 /sqrt(Hz)]-ish
    qb=0.003,           # world accel-offset random walk
    qd=0.0003,          # body drag-offset random walk
    v0=0.5, b0=0.6, d0=1.0,
    room_h=3.0, room_v=1.0,
    rdrag=0.10,                      # drag observation noise (body accel, m/s^2, at block rate)
    drag_c2=4.0,                     # robust (Cauchy) weight threshold on drag-innovation NIS (2-sigma)
    blind_qa=0.3,       # accel process noise across dropouts and while the IMU is dead
    kp=0.02, ki=0.002, lp=1.0, att_block=0.1,
    static_gyro_std=0.06, static_acc_std=1.05,
    zupt_anywhere=True,  # zero-velocity updates at every detected rest period, not only the initial one
    zupt_sigma=0.02,    # zero-velocity pseudo-measurement noise [m/s]
    blind_tau=0.2,      # velocity decay after IMU failure [s]: the velocity estimate at failure is the
                        # least reliable of the flight (max degradation), so it is not extrapolated.
                        # Chosen by leave-one-sequence-out CV over 17 sequences (same pick in all folds).
    use_static_bias=True,
    sev_floor=0.02, sev_gamma=1.7,   # official degrade_imu.py ramp
    qa_exc=6.0, qb_sev=0.15, qb_exc=0.3,
)


# ======================================================================================
# 1. Input
# ======================================================================================
def _open_source(path):
    """Returns (file-like or path usable by np.loadtxt, header_line or None, delimiter, skip)."""
    import io
    if os.path.isdir(path):
        for cand in (os.path.join(path, "imu0", "data.csv"), os.path.join(path, "mav0", "imu0", "data.csv"),
                     os.path.join(path, "data.csv")):
            if os.path.exists(cand):
                path = cand
                break
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith("imu0/data.csv")] or \
                    [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))]
            raw = z.read(names[0])
        src = lambda: io.BytesIO(raw)
    else:
        src = lambda: path
    # sniff header / delimiter from the first lines
    f = src()
    fh = open(f, "rb") if isinstance(f, str) else f
    header, skip, first = None, 0, None
    for _ in range(50):
        ln = fh.readline()
        if not ln:
            break
        s = ln.decode("utf-8-sig", "replace").strip()
        if not s:
            continue
        if s[0] == "#" or s[0].isalpha() or s[0] == '"':
            if header is None:
                header = s.lstrip("#").strip().lower()
            if s[0] != "#":
                skip += 1
            continue
        first = s
        break
    if isinstance(f, str):
        fh.close()
    delim = "," if (first is None or "," in first) else (";" if ";" in first else None)
    return src, header, delim, skip


def parse_imu(path):
    """Returns ts_ns (int64, per input row), gyro (N,3) float32 rad/s, acc (N,3) float32 m/s^2."""
    src, header, delim, skip = _open_source(path)
    kw = dict(delimiter=delim, comments="#", skiprows=skip, ndmin=2)
    try:
        ts = np.loadtxt(src(), usecols=0, dtype=np.int64, **kw).ravel()
        is_int = True
    except ValueError:
        # decimal timestamps: parse as text -> exact integer (avoids float64 rounding of ns)
        raw = np.loadtxt(src(), usecols=0, dtype="S40", **kw).ravel()
        tf = np.empty(len(raw), np.int64)
        scale = None
        for i, b in enumerate(raw.tolist()):
            sx = b.decode().strip()
            if "e" in sx or "E" in sx:
                tf[i] = int(round(float(sx) * 1e9)); scale = scale or 9
                continue
            ip, _, fp_ = sx.partition(".")
            tf[i] = int(ip) * 1_000_000_000 + int((fp_ + "000000000")[:9])
        del raw
        is_int = False
    v = np.loadtxt(src(), usecols=(1, 2, 3, 4, 5, 6), dtype=np.float32, **kw)
    if is_int:
        su = np.unique(ts)
        dtm = float(np.median(np.diff(su))) if len(su) > 1 else 5e6
        del su
        mul = 1 if dtm >= 1e5 else (1000 if dtm >= 100 else (10 ** 6 if dtm >= 0.1 else 10 ** 9))
        if mul != 1:
            ts = ts * mul
    else:
        # tf holds value*1e9 (i.e. ns if the decimal column was seconds); fix other units
        su = np.unique(tf)
        dtm = float(np.median(np.diff(su))) * 1e-9 if len(su) > 1 else 0.005
        del su
        div = 1 if dtm < 1.0 else (1000 if dtm < 1e3 else (10 ** 6 if dtm < 1e6 else 10 ** 9))
        ts = tf // div
        del tf
    # column semantics: header names first, data check second
    gyro_first = None
    if header is not None:
        cols = [c.strip().strip('"') for c in header.replace(";", ",").split(",")]
        if len(cols) >= 7:
            c1 = cols[1]
            if c1.startswith("a") or "acc" in c1:
                gyro_first = False
            elif c1.startswith("w") or c1.startswith("g") or "gyr" in c1 or "omega" in c1 or "ang" in c1:
                gyro_first = True
    good = np.any(v != 0.0, axis=1)
    sub = v[good][:: max(1, int(good.sum()) // 4000)]
    m1 = np.linalg.norm(sub[:, 0:3], axis=1) if len(sub) else np.zeros(1)
    m2 = np.linalg.norm(sub[:, 3:6], axis=1) if len(sub) else np.full(1, G)
    n1, n2 = float(np.median(m1)), float(np.median(m2))
    # accelerometer score: magnitude near g (m/s^2 or g units) AND steady magnitude
    def acc_score(m, med):
        near = min(abs(med - G) / G, abs(med - 1.0))
        cv = float(np.std(m) / max(med, 1e-6))
        return near + cv
    phys_gyro_first = acc_score(m2, n2) < acc_score(m1, n1)
    margin = abs(acc_score(m2, n2) - acc_score(m1, n1))
    if gyro_first is None or (gyro_first != phys_gyro_first and margin > 0.3):
        gyro_first = phys_gyro_first   # no header, or header contradicts physics clearly
    if not gyro_first:
        v[:, [0, 1, 2, 3, 4, 5]] = v[:, [3, 4, 5, 0, 1, 2]]   # in-place reorder to gyro|acc
        n1, n2 = n2, n1
    gyro, acc, na = v[:, 0:3], v[:, 3:6], n2   # views into one (n,6) float32 block
    del sub, m1, m2
    if abs(na - 1.0) < 0.35:
        acc *= np.float32(G)        # accel given in g
    gs = np.abs(gyro[good][::max(1, int(good.sum()) // 4000)])
    if len(gs) and np.percentile(gs, 99) > 15.0:
        gyro *= np.float32(np.pi / 180.0)  # deg/s
    return ts, gyro, acc


# ======================================================================================
# 2. Integrity triage
# ======================================================================================
def _running_median9(x, chunk=8192):
    n = len(x); k = 4
    out = np.empty(n, np.float32)
    pad = np.concatenate([np.full(k, x[0], np.float32), x, np.full(k, x[-1], np.float32)])
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        win = np.lib.stride_tricks.sliding_window_view(pad[s:e + 2 * k], 2 * k + 1)
        out[s:e] = np.median(win, axis=1)
    return out


def triage(ts, w, a):
    """Unique sorted samples + validity mask.
    Returns t (s, float64, from first sample), tsu (unique ns), valid, dead_tail, W, A (float32 views)."""
    base = w.base if (w.base is not None and w.base is a.base and w.base.ndim == 2
                      and w.base.shape[1] == 6 and w.base.dtype == np.float32) else None
    nondec = bool(np.all(ts[1:] >= ts[:-1]))
    if nondec and base is not None:
        drop = np.flatnonzero(ts[1:] == ts[:-1]) + 1        # duplicate rows (keep first)
        if len(drop):
            # in-place left-compaction of the (n,6) block: no full-size copy
            keep_n = len(ts) - len(drop)
            dst = drop[0]
            bounds = np.r_[drop, len(ts)]
            for j in range(len(drop)):
                s0, s1 = bounds[j] + 1, bounds[j + 1]
                L = s1 - s0
                if L > 0:
                    base[dst:dst + L] = base[s0:s1]
                    dst += L
            V = base[:keep_n]
            keep = np.ones(len(ts), bool); keep[drop] = False
            tsu = ts[keep]
            del keep
        else:
            V = base
            tsu = ts
        W = V[:, 0:3]; A = V[:, 3:6]
        del drop
    else:
        order = np.argsort(ts, kind="stable")
        tsu, first = np.unique(ts[order], return_index=True)
        idx = order[first]
        del order, first
        V = np.empty((len(idx), 6), np.float32)
        V[:, 0:3] = w[idx]; V[:, 3:6] = a[idx]
        W = V[:, 0:3]; A = V[:, 3:6]
        del idx
    n = len(tsu)
    t = (tsu - tsu[0]).astype(np.float64) * 1e-9
    nz = np.zeros(n, bool)
    valid = np.ones(n, bool)
    same = np.ones(n - 1, bool) if n > 1 else np.zeros(0, bool)
    for c in range(6):
        x = W[:, c] if c < 3 else A[:, c - 3]
        nz |= x != 0
        valid &= np.isfinite(x)
        if n > 1:
            same &= x[1:] == x[:-1]
    dead = ~nz
    del nz
    valid &= ~dead
    if n > 1:
        valid[1:] &= ~same
    del same
    if n > 16:
        thr = (0.25, 0.25, 0.25, 2.5, 2.5, 2.5)
        step = max(1, int(valid.sum()) // 20000)
        for c in range(6):
            x = W[:, c] if c < 3 else A[:, c - 3]
            res = x - _running_median9(np.ascontiguousarray(x))
            np.abs(res, out=res)
            mad = float(np.median(res[valid][::step])) * 1.4826 + 1e-9
            valid &= ~(res > max(8.0 * mad, thr[c]))
            del res
    vi = np.flatnonzero(valid)
    if 2 <= len(vi) < n:
        bad = np.flatnonzero(~valid)
        tv = t[vi]
        tb = t[bad]
        for c in range(3):
            W[bad, c] = np.interp(tb, tv, W[vi, c])
            A[bad, c] = np.interp(tb, tv, A[vi, c])
        del tv, tb, bad
    del vi
    dead_tail = np.zeros(n, bool)
    alive = np.flatnonzero(~dead)
    if len(alive) and alive[-1] < n - 1:
        dead_tail[alive[-1] + 1:] = True
    del alive, dead
    return t, tsu, valid, dead_tail, W, A


# ======================================================================================
# 3. Platform fingerprint
# ======================================================================================
def identify_platform(t, a, valid):
    m = valid & (t < t[0] + 2.0)
    if m.sum() < 20:
        m = valid
    g = a[m].mean(0)
    g /= np.linalg.norm(g)
    best, bc = None, FINGERPRINT_COS
    for name, p in PLATFORMS.items():
        c = float(g @ p["g_dir"])
        if c > bc:
            best, bc = name, c
    return best, g


def detect_static_start(t, W, A, valid, blk=0.25, max_t=30.0, P=None):
    """Initial rest period (on the ground / before take-off). Returns end time (s from start)
    of the confidently-static prefix, and the gyro mean over it (= gyro bias)."""
    m = valid & (t < max_t)
    if m.sum() < 50:
        return 0.0, None
    k = (t[m] // blk).astype(np.int64)
    nb = int(k[-1]) + 1
    c = np.bincount(k, minlength=nb).astype(float)
    ok = c >= 5
    cs = np.maximum(c, 1)
    def bstat(X):
        mu = np.stack([np.bincount(k, X[:, j], nb) / cs for j in range(3)], 1)
        var = sum(np.bincount(k, X[:, j].astype(np.float64) ** 2, nb) / cs - mu[:, j] ** 2 for j in range(3))
        return mu, np.sqrt(np.maximum(var, 0))
    Wm, Ws = bstat(W[m]); Am, As = bstat(A[m])
    an = np.linalg.norm(Am, axis=1)
    g_ref = np.median(an[ok][: max(1, min(int(ok.sum()), 4))])
    P = P_DEFAULT if P is None else P
    static = ok & (Ws < P["static_gyro_std"]) & (As < P["static_acc_std"]) & (np.abs(an - g_ref) < 0.25)
    # gyro mean must be steady (no slow rotation)
    if nb > 1:
        dW = np.zeros(nb); dW[1:] = np.linalg.norm(Wm[1:] - Wm[:-1], axis=1)
        static &= dW < 0.03
    if not static[0]:
        return 0.0, None
    nfirst = int(np.argmin(static)) if not static.all() else nb
    t_end = nfirst * blk - blk          # one-block safety margin before motion
    if t_end < 0.5:
        return 0.0, None
    sel = m & (t < t_end)
    return float(t_end), W[sel].astype(np.float64).mean(0)


def detect_static_all(t, W, A, valid, dtb, nb, P, min_run=1.5):
    """Rest periods anywhere in the sequence (e.g. landed mid-sequence), at smoother-block rate.
    A block is static when gyro and accel are quiet, |a| ~ g and the gyro mean is steady; only runs
    of >= min_run seconds count, shrunk by one block at each end. Degradation noise only makes
    blocks look less static, and stuck/dropped samples are already excluded via `valid`."""
    m = valid
    k = np.minimum((t[m] // dtb).astype(np.int64), nb - 1)
    c = np.bincount(k, minlength=nb).astype(float)
    cs = np.maximum(c, 1)
    def bstat(X):
        mu = np.stack([np.bincount(k, X[:, j], nb) / cs for j in range(3)], 1)
        var = sum(np.bincount(k, X[:, j].astype(np.float64) ** 2, nb) / cs - mu[:, j] ** 2 for j in range(3))
        return mu, np.sqrt(np.maximum(var, 0))
    Wm, Ws = bstat(W[m]); Am, As = bstat(A[m])
    an = np.linalg.norm(Am, axis=1)
    st = (c >= 0.5 * np.median(c[c > 0])) & (Ws < P["static_gyro_std"]) & (As < P["static_acc_std"]) & (np.abs(an - G) < 0.25)
    dW = np.zeros(nb); dW[1:] = np.linalg.norm(Wm[1:] - Wm[:-1], axis=1)
    st &= dW < 0.03
    out = np.zeros(nb, bool)
    nr = max(1, int(round(min_run / dtb)))
    i = 0
    while i < nb:
        if st[i]:
            j = i
            while j < nb and st[j]:
                j += 1
            if j - i >= nr:
                out[i + 1:j - 1] = True
            i = j
        else:
            i += 1
    return out


# ======================================================================================
# 4. Attitude (fused pass: also accumulates block-rate world acceleration / drag terms)
# ======================================================================================
def _q_from_up(u):
    """unit quaternion (w,x,y,z) rotating body vector u onto world +z"""
    ux, uy, uz = float(u[0]), float(u[1]), float(u[2])
    ax, ay = uy, -ux
    s = math.sqrt(ax * ax + ay * ay)
    c = max(-1.0, min(1.0, uz))
    if s < 1e-9:
        return (1.0, 0.0, 0.0, 0.0) if c > 0 else (0.0, 1.0, 0.0, 0.0)
    th = math.acos(c)
    k = math.sin(0.5 * th) / s
    return (math.cos(0.5 * th), ax * k, ay * k, 0.0)


def _qmul_v(a, b):
    """vectorised Hamilton product, arrays (...,4) w,x,y,z"""
    aw, ax, ay, az = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bw, bx, by, bz = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], -1)


def _qexp_v(th):
    a = np.sqrt(np.sum(th * th, -1, keepdims=True))
    s = np.where(a > 1e-12, np.sin(0.5 * a) / np.where(a > 1e-12, a, 1.0), 0.5)
    return np.concatenate([np.cos(0.5 * a), th * s], -1)


def _qrot_v(q, v):
    """rotate vectors v (n,3) by quaternions q (n,4)"""
    w = q[:, 0:1]; u = q[:, 1:4]
    c = np.cross(u, v)
    return v + 2.0 * (w * c + np.cross(u, c))


def attitude_vec(t, W, A, valid, dead_tail, b0, up_b, P, dtb, Bp, dec, CHS=4096):
    """Vectorised complementary attitude filter (memory-bounded, chunked).
    Gyro rotations inside each block are composed by a segmented parallel prefix product;
    bias / gravity feedback is applied once per block. Also returns block-rate world
    specific force, drag projections and mid-block attitude for the translation smoother."""
    n = len(t)
    nb = int(t[-1] // dtb) + 1
    bstart = np.searchsorted(t, np.arange(nb + 1) * dtb)      # first sample of each block
    bstart[-1] = n
    kp, ki, lp = P["kp"], P["ki"], P["lp"]

    def chunk_ranges():
        b = 0
        while b < nb:
            e = int(np.searchsorted(bstart, bstart[b] + CHS, side="right")) - 1
            e = min(max(e, b + 1), nb)
            yield b, e
            b = e

    def chunk_data(b0_, b1_):
        s0, s1 = int(bstart[b0_]), int(bstart[b1_])
        tt = t[s0:min(s1 + 1, n)]
        dt = np.zeros(s1 - s0)
        m = min(s1 + 1, n) - s0 - 1
        dt[:m] = np.diff(tt)
        hold = dead_tail[s0 + 1:s0 + 1 + m]
        dt[:m][hold] = 0.0
        seg = np.searchsorted(bstart, np.arange(s0, s1), side="right") - 1
        # trapezoidal rate over each interval: across a dropout gap during fast rotation, holding
        # the sample before the gap (zero-order hold) mis-integrates the whole gap
        w0 = W[s0:s1].astype(np.float64)
        w1 = W[s0 + 1:min(s1 + 1, n)].astype(np.float64)
        wm = w0.copy(); wm[:len(w1)] += w1; wm[:len(w1)] *= 0.5
        dq = _qexp_v(wm * dt[:, None])
        del w0, w1, wm
        L = s1 - s0
        off = 1
        while off < L:
            same = np.zeros(L, bool); same[off:] = seg[off:] == seg[:-off]
            if not same.any():
                break
            idx = np.flatnonzero(same)
            dq[idx] = _qmul_v(dq[idx - off], dq[idx])
            off *= 2
        return s0, s1, dt, seg, dq

    blk_rot = np.empty((nb, 4)); blk_T = np.zeros(nb)
    mk = np.zeros((nb, 3)); mc = np.zeros(nb)          # block-frame mean specific force
    ab = np.zeros((nb, 3))                              # body-frame accel sums (valid)
    for b0_, b1_ in chunk_ranges():
        s0, s1, dt, seg, pre = chunk_data(b0_, b1_)
        last = bstart[b0_ + 1:b1_ + 1] - 1 - s0
        blk_rot[b0_:b1_] = pre[last]
        blk_T += np.bincount(seg, dt, nb)
        ex = np.empty_like(pre); ex[0] = (1, 0, 0, 0); ex[1:] = pre[:-1]
        ex[np.flatnonzero(np.r_[True, seg[1:] != seg[:-1]])] = (1.0, 0.0, 0.0, 0.0)
        use = valid[s0:s1] & ~dead_tail[s0:s1]
        if use.any():
            a64 = A[s0:s1][use].astype(np.float64)
            ra = _qrot_v(ex[use], a64)
            su = seg[use]
            for j in range(3):
                mk[:, j] += np.bincount(su, ra[:, j], nb)
                ab[:, j] += np.bincount(su, a64[:, j], nb)
            mc += np.bincount(su, minlength=nb)
        del ex, pre, dt, seg
    hm = mc > 0
    mk[hm] /= mc[hm, None]
    # trailing lp-second body-frame mean accel at each block end (block-resolution window)
    Lb = max(1, int(round(lp / dtb)))
    cab = np.vstack([np.zeros((1, 3)), np.cumsum(ab, 0)]); ccb = np.r_[0.0, np.cumsum(mc)]
    lo = np.maximum(np.arange(nb) + 1 - Lb, 0); hi = np.arange(nb) + 1
    win_a = (cab[hi] - cab[lo]).tolist(); win_c = (ccb[hi] - ccb[lo]).tolist()
    del cab, ccb, ab
    # ---------------- sequential block-level filter (pure-Python scalars) ----------------
    up = np.asarray(up_b, float)
    ux, uy, uz = float(up[0]), float(up[1]), float(up[2])
    m0 = valid & (t < 2.0)
    if m0.sum() < 10:
        m0 = valid
    g0 = A[m0].astype(np.float64).mean(0); g0 = g0 / np.linalg.norm(g0)
    del m0
    qw, qx, qy, qz = _q_from_up(g0)
    bx, by, bz = float(b0[0]), float(b0[1]), float(b0[2])
    qs = np.empty((nb, 4)); bs = np.empty((nb, 3))
    rot = blk_rot.tolist(); Tl = blk_T.tolist()
    mkl = mk.tolist(); mcl = mc.tolist()
    world_ref = P.get("grav_ref", "world") == "world"
    aw = 1.0 - math.exp(-dtb / P.get("tau_w", 4.0))
    gwx, gwy, gwz = 0.0, 0.0, G
    kpw, kiw = P.get("kp_w", 0.02), P.get("ki_w", 0.002)
    for k in range(nb):
        qs[k] = (qw, qx, qy, qz); bs[k] = (bx, by, bz)
        rw, rx, ry, rz = rot[k]
        qw, qx, qy, qz = (qw * rw - qx * rx - qy * ry - qz * rz, qw * rx + qx * rw + qy * rz - qz * ry,
                          qw * ry - qx * rz + qy * rw + qz * rx, qw * rz + qx * ry - qy * rx + qz * rw)
        T = Tl[k]
        if T <= 0:
            continue
        ex_, ey_, ez_ = -bx * T, -by * T, -bz * T
        th = math.sqrt(ex_ * ex_ + ey_ * ey_ + ez_ * ez_)
        sn = math.sin(0.5 * th) / th if th > 1e-12 else 0.5
        cw = math.cos(0.5 * th)
        dx, dy, dz = ex_ * sn, ey_ * sn, ez_ * sn
        qw, qx, qy, qz = (qw * cw - qx * dx - qy * dy - qz * dz, qw * dx + qx * cw + qy * dz - qz * dy,
                          qw * dy - qx * dz + qy * cw + qz * dx, qw * dz + qx * dy - qy * dx + qz * cw)
        if world_ref:
            if mcl[k] > 0:
                mx_, my_, mz_ = mkl[k]
                q0w, q0x, q0y, q0z = qs[k]
                cx = q0y * mz_ - q0z * my_; cy = q0z * mx_ - q0x * mz_; cz = q0x * my_ - q0y * mx_
                rx = mx_ + 2 * (q0w * cx + q0y * cz - q0z * cy)
                ry = my_ + 2 * (q0w * cy + q0z * cx - q0x * cz)
                rz = mz_ + 2 * (q0w * cz + q0x * cy - q0y * cx)
                gwx += aw * (rx - gwx); gwy += aw * (ry - gwy); gwz += aw * (rz - gwz)
                ng = math.sqrt(gwx * gwx + gwy * gwy + gwz * gwz)
                fx_, fy_ = gwy / ng, -gwx / ng
                ewx, ewy = kpw * fx_, kpw * fy_
                hx, hy = 0.5 * ewx, 0.5 * ewy
                qw, qx, qy, qz = (qw - hx * qx - hy * qy, hx * qw + qx + hy * qz,
                                  hy * qw + qy - hx * qz, qz + hx * qy - hy * qx)
                gwx, gwy, gwz = gwx + ewy * gwz, gwy - ewx * gwz, gwz + ewx * gwy - ewy * gwx
                ebx = (1 - 2 * (qy * qy + qz * qz)) * fx_ + 2 * (qx * qy + qw * qz) * fy_
                eby = 2 * (qx * qy - qw * qz) * fx_ + (1 - 2 * (qx * qx + qz * qz)) * fy_
                ebz = 2 * (qx * qz + qw * qy) * fx_ + 2 * (qy * qz - qw * qx) * fy_
                pr = ebx * ux + eby * uy + ebz * uz
                bx -= kiw * (ebx - pr * ux); by -= kiw * (eby - pr * uy); bz -= kiw * (ebz - pr * uz)
        else:
            c = win_c[k]
            if c >= 5:
                fx, fy, fz = win_a[k]
                nf = math.sqrt(fx * fx + fy * fy + fz * fz)
                mx, my, mz = fx / nf, fy / nf, fz / nf
                px = 2 * (qx * qz - qw * qy); py = 2 * (qy * qz + qw * qx); pz = 1 - 2 * (qx * qx + qy * qy)
                ex = my * pz - mz * py; ey = mz * px - mx * pz; ez = mx * py - my * px
                pr = ex * ux + ey * uy + ez * uz
                ex -= pr * ux; ey -= pr * uy; ez -= pr * uz
                bx -= ki * ex; by -= ki * ey; bz -= ki * ez
                hx, hy, hz = 0.5 * kp * ex, 0.5 * kp * ey, 0.5 * kp * ez
                qw, qx, qy, qz = (qw - qx * hx - qy * hy - qz * hz, qw * hx + qx + qy * hz - qz * hy,
                                  qw * hy - qx * hz + qy + qz * hx, qw * hz + qx * hy - qy * hx + qz)
        nq = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
        qw, qx, qy, qz = qw / nq, qx / nq, qy / nq, qz / nq
    del rot, Tl, mkl, mcl, win_a, win_c
    # ---------------- per-sample attitude -> outputs ----------------
    ub = np.zeros((nb, 3)); cnt = np.zeros(nb); fp = np.zeros((nb, 2))
    nd = (n + dec - 1) // dec
    Qd = np.empty((nd, 4), np.float32); td = t[::dec].copy()
    mid_i = np.minimum(np.searchsorted(t, (np.arange(nb) + 0.5) * dtb), n - 1)
    qmid = np.empty((nb, 4))
    for b0_, b1_ in chunk_ranges():
        s0, s1, dt, seg, pre = chunk_data(b0_, b1_)
        ex = np.empty_like(pre); ex[0] = (1, 0, 0, 0); ex[1:] = pre[:-1]
        ex[np.flatnonzero(np.r_[True, seg[1:] != seg[:-1]])] = (1.0, 0.0, 0.0, 0.0)
        del pre
        tl = t[s0:s1] - t[bstart[seg]]
        qi = _qmul_v(_qmul_v(qs[seg], ex), _qexp_v(-bs[seg] * tl[:, None]))
        del ex, tl
        qi /= np.linalg.norm(qi, axis=1, keepdims=True)
        sel = np.arange(s0 + (-s0) % dec, s1, dec)
        Qd[sel // dec] = qi[sel - s0]
        mm = (mid_i >= s0) & (mid_i < s1)
        qmid[mm] = qi[mid_i[mm] - s0]
        use = valid[s0:s1] & ~dead_tail[s0:s1]
        if use.any():
            a = A[s0:s1][use].astype(np.float64)
            u = _qrot_v(qi[use], a); u[:, 2] -= G
            ku = seg[use]
            for j in range(3):
                ub[:, j] += np.bincount(ku, u[:, j], nb)
            cnt += np.bincount(ku, minlength=nb)
            if Bp is not None:
                fpp = a @ Bp.T
                fp[:, 0] += np.bincount(ku, fpp[:, 0], nb)
                fp[:, 1] += np.bincount(ku, fpp[:, 1], nb)
        del qi, dt, seg
    has = cnt > 0
    ub[has] /= cnt[has, None]
    fp[has] /= cnt[has, None]
    return td, Qd, ub, fp, has, qmid


def quat_to_R(Q):
    Q = np.asarray(Q, dtype=np.float64)
    w, x, y, z = Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]
    R = np.empty((len(Q), 3, 3))
    R[:, 0, 0] = 1 - 2 * (y * y + z * z); R[:, 0, 1] = 2 * (x * y - w * z); R[:, 0, 2] = 2 * (x * z + w * y)
    R[:, 1, 0] = 2 * (x * y + w * z); R[:, 1, 1] = 1 - 2 * (x * x + z * z); R[:, 1, 2] = 2 * (y * z - w * x)
    R[:, 2, 0] = 2 * (x * z - w * y); R[:, 2, 1] = 2 * (y * z + w * x); R[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return R


# ======================================================================================
# 5. Translation smoother
# ======================================================================================
def translation(ub, fp, has, blind, qmid, dtb, Bp, K, P, vmeas=None, static=None, qa_k=None, qb_k=None):
    """LTV Kalman filter + RTS smoother on block-rate data.
    state: p(3) v(3) b_world(3) centre(3) d_drag(2)"""
    nb = len(ub)
    Rb = quat_to_R(qmid)
    multi = Bp is not None
    nx = 14
    F = np.eye(nx)
    F[0:3, 3:6] = np.eye(3) * dtb
    F[0:3, 6:9] = -0.5 * dtb * dtb * np.eye(3)
    F[3:6, 6:9] = -dtb * np.eye(3)
    Gm = np.zeros((nx, 3)); Gm[0:3] = 0.5 * dtb * dtb * np.eye(3); Gm[3:6] = dtb * np.eye(3)
    Qn = Gm @ Gm.T * (P["qa"] ** 2 / dtb)
    Qn[6:9, 6:9] += np.eye(3) * P["qb"] ** 2 * dtb
    Qn[12:14, 12:14] += np.eye(2) * P["qd"] ** 2 * dtb
    Qgap = Qn + Gm @ Gm.T * (P["blind_qa"] ** 2 / dtb)
    # blind (IMU dead): velocity decays (vehicle settles / lands); accel offset frozen
    tau = P["blind_tau"]
    Fb = np.eye(nx)
    ed = math.exp(-dtb / tau)
    Fb[3:6, 3:6] = ed * np.eye(3)
    Fb[0:3, 3:6] = tau * (1 - ed) * np.eye(3)
    Qb = Gm @ Gm.T * (P["blind_qa"] ** 2 / dtb)
    Qb[6:9, 6:9] += np.eye(3) * P["qb"] ** 2 * dtb
    static = np.zeros(nb, bool) if static is None else static
    Hz = np.zeros((3, nx)); Hz[:, 3:6] = np.eye(3)
    Rz = np.eye(3) * P["zupt_sigma"] ** 2
    x = np.zeros(nx)
    Pc = np.zeros((nx, nx))
    Pc[0:3, 0:3] = np.eye(3) * 1e-4
    Pc[3:6, 3:6] = np.eye(3) * P["v0"] ** 2
    Pc[6:9, 6:9] = np.eye(3) * P["b0"] ** 2
    Pc[9:12, 9:12] = np.eye(3) * 100.0
    Pc[12:14, 12:14] = np.eye(2) * P["d0"] ** 2
    Hr = np.zeros((3, nx)); Hr[:, 0:3] = np.eye(3); Hr[:, 9:12] = -np.eye(3)
    Rr = np.diag([P["room_h"] ** 2, P["room_h"] ** 2, P["room_v"] ** 2])
    Rd = np.eye(2) * P["rdrag"] ** 2
    c2 = P["drag_c2"]
    xf = np.empty((nb, nx)); Pf = np.empty((nb, nx, nx), np.float32)
    meas = has & ~blind
    GG = Gm @ Gm.T / dtb
    adaptive = qa_k is not None
    def Qk(i):
        if not adaptive:
            return Qn
        q = GG * qa_k[i] ** 2
        q[6:9, 6:9] += np.eye(3) * qb_k[i] ** 2 * dtb
        q[12:14, 12:14] += np.eye(2) * P["qd"] ** 2 * dtb
        return q
    for i in range(nb):
        if i > 0:
            if meas[i - 1]:
                x = F @ x + Gm @ ub[i - 1]
                Pc = F @ Pc @ F.T + Qk(i - 1)
            elif blind[i - 1]:
                x = Fb @ x
                Pc = Fb @ Pc @ Fb.T + Qb
            else:
                x = F @ x
                Pc = F @ Pc @ F.T + Qgap
        if static[i]:
            S = Hz @ Pc @ Hz.T + Rz
            Kg = np.linalg.solve(S, Hz @ Pc).T
            x = x - Kg @ (Hz @ x); Pc = Pc - Kg @ Hz @ Pc
        S = Hr @ Pc @ Hr.T + Rr
        Kg = np.linalg.solve(S, Hr @ Pc).T
        x = x - Kg @ (Hr @ x); Pc = Pc - Kg @ Hr @ Pc
        if multi and meas[i] and P["rdrag"] < 1e5:
            Hd = np.zeros((2, nx))
            Hd[:, 3:6] = (K[:, None] * Bp) @ Rb[i].T
            Hd[:, 12:14] = np.eye(2)
            S = Hd @ Pc @ Hd.T + Rd
            inn = fp[i] - Hd @ x
            # Cauchy-type robust weight: when the drag model is violated (vehicle on the ground,
            # carried by hand, contact), the innovation is implausible and R is inflated by NIS/c2.
            m2 = float(inn @ np.linalg.solve(S, inn))
            if m2 > c2:
                S = Hd @ Pc @ Hd.T + Rd * (m2 / c2)
            Kg = np.linalg.solve(S, Hd @ Pc).T
            x = x + Kg @ inn; Pc = Pc - Kg @ Hd @ Pc
        Pc = 0.5 * (Pc + Pc.T)
        xf[i] = x; Pf[i] = Pc
    xs = xf
    for i in range(nb - 2, -1, -1):
        Pfi = Pf[i].astype(np.float64)
        Fi = Fb if (blind[i] and not meas[i]) else F
        Pp = Fi @ Pfi @ Fi.T + (Qk(i) if meas[i] else (Qb if blind[i] else Qgap))
        xpred = Fi @ xf[i] + (Gm @ ub[i] if meas[i] else 0.0)
        C = np.linalg.solve(Pp, Fi @ Pfi).T
        xs[i] = xf[i] + C @ (xs[i + 1] - xpred)
    del Pf
    tk = (np.arange(nb) + 0.5) * dtb
    return tk, xs[:, 0:3].copy(), xs[:, 3:6].copy()


# ======================================================================================
# 6. Output
# ======================================================================================
def hermite(tq, tk, p, v):
    j = np.clip(np.searchsorted(tk, tq) - 1, 0, len(tk) - 2)
    h = (tk[j + 1] - tk[j])[:, None]
    s = np.clip((tq - tk[j])[:, None] / h, 0.0, 1.0)
    s2 = s * s; s3 = s2 * s
    out = (2 * s3 - 3 * s2 + 1) * p[j] + (s3 - 2 * s2 + s) * h * v[j] + (-2 * s3 + 3 * s2) * p[j + 1] + (s3 - s2) * h * v[j + 1]
    lo = tq < tk[0]; hi = tq > tk[-1]
    if lo.any():
        out[lo] = p[0] + (tq[lo] - tk[0])[:, None] * v[0]
    if hi.any():
        out[hi] = p[-1] + (tq[hi] - tk[-1])[:, None] * v[-1]
    return out


def nlerp(tq, td, Qd):
    j = np.clip(np.searchsorted(td, tq) - 1, 0, len(td) - 2)
    h = td[j + 1] - td[j]
    s = np.clip((tq - td[j]) / np.where(h > 0, h, 1.0), 0.0, 1.0)[:, None]
    q0 = Qd[j].astype(np.float64); q1 = Qd[j + 1].astype(np.float64)
    sg = np.sign(np.sum(q0 * q1, 1, keepdims=True)); sg[sg == 0] = 1.0
    q = (1 - s) * q0 + s * sg * q1
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return q


def write_output(path, ts_rows, t0_ns, tk, pk, vk, td, Qd, chunk=1024):
    with open(path, "w") as f:
        f.write("# timestamp tx ty tz qx qy qz qw\n")
        for s in range(0, len(ts_rows), chunk):
            tr = ts_rows[s:s + chunk]
            tq = (tr - t0_ns).astype(np.float64) * 1e-9
            p = hermite(tq, tk, pk, vk)
            q = nlerp(tq, td, Qd)
            sec = (tr // 1_000_000_000).tolist(); ns = (tr % 1_000_000_000).tolist()
            f.write("".join("%d.%09d %.6f %.6f %.6f %.8f %.8f %.8f %.8f\n" % (a, b, pp[0], pp[1], pp[2], qq[1], qq[2], qq[3], qq[0])
                            for a, b, pp, qq in zip(sec, ns, p.tolist(), q.tolist())))


def noise_schedule(t, W, valid, dead_tail, nb, dtb, P):
    """Per-block process noise. Two observable drivers of slow world-acceleration error:
    (1) the documented degradation ramp sev(t) = floor + (1-floor)(t/T)^gamma, and
    (2) measured excess gyro white noise (HF scatter above the initial clean level)."""
    alive = ~dead_tail
    T = float(t[alive][-1]) if alive.any() else float(t[-1])
    tb = (np.arange(nb) + 0.5) * dtb
    sev = P["sev_floor"] + (1 - P["sev_floor"]) * np.clip(tb / max(T, 1e-6), 0, 1) ** P["sev_gamma"]
    c = np.zeros(nb); s2 = np.zeros(nb)
    n = len(t); CH = 8192
    for s0 in range(1, n, CH):
        s1 = min(n, s0 + CH)
        d2 = np.zeros(s1 - s0)
        for j in range(3):
            dj = (W[s0:s1, j] - W[s0 - 1:s1 - 1, j]).astype(np.float64)
            d2 += dj * dj
        mm = valid[s0:s1] & alive[s0:s1]
        kk = np.minimum((t[s0:s1][mm] // dtb).astype(np.int64), nb - 1)
        c += np.bincount(kk, minlength=nb)
        s2 += np.bincount(kk, 0.5 * d2[mm], nb)
        del d2, mm, kk
    sg = np.sqrt(s2 / np.maximum(c, 1))
    # smooth over ~2 s
    L = max(1, int(round(2.0 / dtb)))
    cs = np.cumsum(np.r_[0.0, sg]); cn = np.cumsum(np.r_[0.0, (c > 0).astype(float)])
    lo = np.maximum(np.arange(nb) - L, 0); hi = np.minimum(np.arange(nb) + L + 1, nb)
    sgs = (cs[hi] - cs[lo]) / np.maximum(cn[hi] - cn[lo], 1)
    early = sgs[(tb < min(10.0, 0.1 * T)) & (c > 0)]
    s0 = float(np.median(early)) if len(early) else float(np.median(sgs))
    exc = np.sqrt(np.maximum(sgs ** 2 - s0 ** 2, 0.0))
    qa_k = np.sqrt(P["qa"] ** 2 + (P["qa_exc"] * exc) ** 2)
    qb_k = np.sqrt(P["qb"] ** 2 + (P["qb_sev"] * sev) ** 2 + (P["qb_exc"] * exc) ** 2)
    return qa_k, qb_k


# ======================================================================================
# Pipeline
# ======================================================================================
def drag_basis(up_b):
    thr = np.asarray(up_b, float)
    e1 = np.cross(thr, [0.0, 1.0, 0.0]); e1 /= np.linalg.norm(e1)
    e2 = np.cross(thr, e1)
    return np.stack([e1, e2])


def run(inp, out, P=None, return_state=False):
    user_P = P or {}
    ts_rows, w, a = parse_imu(inp)
    t, tsu, valid, dead_tail, W, A = triage(ts_rows, w, a)
    del w, a
    platform, up_b = identify_platform(t, A, valid)
    P = dict(P_DEFAULT)
    P.update(PLATFORMS[platform].get("params", {}) if platform else UNKNOWN_PLATFORM_PARAMS)
    P.update(user_P)
    b0 = PLATFORMS[platform]["gyro_bias"] if platform else np.zeros(3)
    t_static, b_static = detect_static_start(t, W, A, valid, P=P)
    if P["use_static_bias"] and b_static is not None and t_static >= 0.75:
        b0 = b_static
    dtb = P["block"]
    while t[-1] / dtb > 1500:
        dtb *= 2
    multi = platform is not None and PLATFORMS[platform]["multirotor"]
    Bp = drag_basis(up_b) if multi else None
    K = (np.asarray(P["drag_k"], float) if P.get("drag_k") is not None else PLATFORMS[platform]["drag_k"]) if multi else None
    dec = max(1, int(round(0.02 / max(1e-4, float(np.median(np.diff(t[:2000])))))))
    td, Qd, ub, fp, has, qmid = attitude_vec(t, W, A, valid, dead_tail, b0, up_b, P, dtb, Bp, dec)
    nb = len(ub)
    blind = np.zeros(nb, bool)
    dti = np.flatnonzero(dead_tail)
    if len(dti):
        blind[np.minimum((t[dti] // dtb).astype(np.int64), nb - 1)] = True
    del dti
    if return_state:
        qa_k, qb_k = noise_schedule(t, W, valid, dead_tail, nb, dtb, P)
        return dict(qa_k=qa_k, qb_k=qb_k, t_static=t_static, b_static=b_static, t=t, tsu=tsu, W=W, A=A, valid=valid, dead=dead_tail, td=td, Qd=Qd, ub=ub, fp=fp,
                    has=has, qmid=qmid, blind=blind, dtb=dtb, Bp=Bp, K=K, platform=platform, up_b=up_b, P=P)
    qa_k, qb_k = noise_schedule(t, W, valid, dead_tail, nb, dtb, P)
    st_any = detect_static_all(t, W, A, valid & ~dead_tail, dtb, nb, P) if P["zupt_anywhere"] else None
    del W, A, valid
    static = (np.arange(nb) + 1) * dtb <= t_static
    if P["zupt_anywhere"]:
        static |= st_any & ~blind
    tk, pk, vk = translation(ub, fp, has, blind, qmid, dtb, Bp, K, P, static=static, qa_k=qa_k, qb_k=qb_k)
    write_output(out, ts_rows, tsu[0], tk, pk, vk, td, Qd)
    return {"platform": platform, "rows": int(len(ts_rows)), "unique": int(len(tsu)),
            "dead": int(dead_tail.sum()), "blocks": nb}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else "estimated_trajectory.txt"
    info = run(sys.argv[1], out)
    print("wrote %s  %s" % (out, info))

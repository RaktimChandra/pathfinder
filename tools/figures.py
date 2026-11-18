"""Deck / README figures in the submission template's palette (dark surface).
Palette validated with the dataviz validator (dark mode, surface #0A0E1A): all checks pass.
Usage: python tools/figures.py  -> docs/figures/*.png
"""
import os, sys, json, copy
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
sys.path.insert(0, 'src'); sys.path.insert(0, 'tools')
import main as M
from research_common import load_gt, load_imu, qmat
from evo.tools import file_interface
from evo.core import sync
from score import load_est

SURF = '#0A0E1A'; PANEL = '#0D1B3E'; INK = '#E8EDF5'; INK2 = '#9AA6BC'; GRID = '#1C2740'
OURS = '#1499BA'; CONST = '#C47318'; NAIVE = '#8C7FE0'; ACCENT = '#00B4D8'
OUT = 'docs/figures'
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
    'text.color': INK, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
    'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 13, 'axes.titleweight': 'bold',
    'axes.titlelocation': 'left', 'axes.spines.top': False, 'axes.spines.right': False,
    'legend.frameon': False, 'lines.linewidth': 2.0, 'axes.titlepad': 10,
})


def aligned(seq, est_path):
    gt = file_interface.read_euroc_csv_trajectory('data/raw/%s_gt.csv' % seq)
    e = load_est(est_path)
    g, e = sync.associate_trajectories(gt, e, max_diff=0.003)
    ea = copy.deepcopy(e); ea.align(g, correct_scale=False)
    return g.timestamps - g.timestamps[0], g.positions_xyz, ea.positions_xyz


def fig_hero(name='V2_02_medium_H1', seq='V2_02_medium'):
    t, P, E = aligned(seq, 'results/%s.txt' % name)
    _, _, N = aligned(seq, 'results/base_naive_%s.txt' % name)
    fig = plt.figure(figsize=(12, 5.0))
    ax = fig.add_axes([0.06, 0.2, 0.36, 0.7])
    ax.plot(P[:, 0], P[:, 1], color=INK, lw=1.6, label='Ground truth')
    ax.plot(E[:, 0], E[:, 1], color=OURS, lw=1.8, label='Path Finder (IMU only)')
    ax.set_aspect('equal'); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
    ax.set_title('Top-down view (%s)' % seq.replace('_', ' '))
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=9.5)
    ax2 = fig.add_axes([0.52, 0.2, 0.45, 0.7])
    en = np.linalg.norm(N - P, axis=1); eo = np.linalg.norm(E - P, axis=1)
    ax2.semilogy(t, en, color=NAIVE, lw=1.8)
    ax2.semilogy(t, eo, color=OURS, lw=1.8)
    ax2.text(t[-1] * 0.30, en[int(len(en) * 0.30)] * 2.2, 'textbook strapdown integration', color=NAIVE, fontsize=10, fontweight='bold')
    ax2.text(t[-1] * 0.30, max(eo.max() * 1.6, 3.5), 'Path Finder', color=OURS, fontsize=10, fontweight='bold')
    ax2.axvspan(t[-1] - 5, t[-1], color=PANEL, zorder=0)
    ax2.text(t[-1] - 4.8, 0.06, 'IMU dead\n(blind 5 s)', color=INK2, fontsize=8.5)
    ax2.set_ylim(0.05, max(en.max() * 3, 10)); ax2.set_xlabel('time [s]'); ax2.set_ylabel('position error [m] (log)')
    ax2.set_title('Error after SE(3) alignment')
    fig.savefig(OUT + '/hero.png', dpi=200); plt.close(fig)


def fig_bars():
    r = json.load(open('results/baselines.json'))
    keys = [k for k in r if k.endswith('_H1')]
    grp = lambda k: (0 if k.startswith('V') else 1 if k.startswith('MH') else 2, k)
    keys = sorted(keys, key=grp)
    lab = [k.replace('_H1', '').replace('_easy', '').replace('_medium', '').replace('_difficult', '').replace('TUM_', 'TUM-VI ').replace('_', ' ') for k in keys]
    o = [np.mean([r[k]['ours']['ate_rmse'], r[k.replace('_H1', '_H2')]['ours']['ate_rmse']]) for k in keys]
    c = [np.mean([r[k]['const']['ate_rmse'], r[k.replace('_H1', '_H2')]['const']['ate_rmse']]) for k in keys]
    nv = [np.mean([r[k]['naive']['ate_rmse'], r[k.replace('_H1', '_H2')]['naive']['ate_rmse']]) for k in keys]
    y = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(8.5, 0.62 * len(keys) + 1.4))
    h = 0.36
    ax.barh(y - h / 2 - 0.02, c, h, color=CONST, label='Constant-position baseline')
    ax.barh(y + h / 2 + 0.02, o, h, color=OURS, label='Path Finder')
    for i in range(len(keys)):
        ax.text(o[i] + 0.04, y[i] + h / 2 + 0.02, '%.2f m' % o[i], va='center', fontsize=9.5, color=INK)
        ax.text(c[i] + 0.04, y[i] - h / 2 - 0.02, '%.2f m' % c[i], va='center', fontsize=9.5, color=INK2)
        ax.text(max(c) * 1.32, y[i], 'naive: %s' % ('%.1f km' % (nv[i] / 1000) if nv[i] > 1000 else '%.0f m' % nv[i]),
                va='center', fontsize=9.5, color=NAIVE)
    ax.set_yticks(y); ax.set_yticklabels(lab); ax.invert_yaxis()
    ax.set_xlim(0, max(c) * 1.75); ax.set_xlabel('ATE RMSE [m]  (mean of both degradation variants)')
    ax.grid(axis='y', visible=False); ax.set_axisbelow(True)
    ax.set_title('Absolute trajectory error per sequence')
    ax.legend(loc='lower center', bbox_to_anchor=(0.42, 1.0), ncol=2, fontsize=9.5)
    ax.set_title('Absolute trajectory error per sequence', pad=30)
    fig.tight_layout(); fig.savefig(OUT + '/ate_bars.png', dpi=200); plt.close(fig)


def fig_spectrum():
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for seq, lab in [('V1_01_easy', 'EuRoC V1 01'), ('V2_02_medium', 'EuRoC V2 02'), ('TUM_room1', 'TUM-VI room1')]:
        gts, P, *_ = load_gt('data/raw/%s_gt.csv' % seq)
        tg = (gts - gts[0]) * 1e-9; tu = np.arange(0, tg[-1], 0.01)
        x = np.stack([np.interp(tu, tg, P[:, j]) for j in range(3)], 1); x -= x.mean(0)
        F = (np.abs(np.fft.rfft(x, axis=0)) ** 2).sum(1); f = np.fft.rfftfreq(len(x), 0.01)
        c = np.cumsum(F) / F.sum()
        col = {'EuRoC V1 01': OURS, 'EuRoC V2 02': CONST, 'TUM-VI room1': NAIVE}[lab]
        ax.semilogx(f[1:], c[1:] * 100, color=col, label=lab)
    ax.axvline(0.05, color=INK2, lw=1, ls='--'); ax.text(0.054, 8, '0.05 Hz', color=INK2, fontsize=9)
    ax.set_xlim(0.005, 5); ax.set_ylim(0, 101)
    ax.set_xlabel('frequency [Hz]'); ax.set_ylabel('cumulative position power [%]')
    ax.set_title('Where trajectory energy lives')
    ax.legend(loc='lower right', fontsize=9)
    fig.tight_layout(); fig.savefig(OUT + '/spectrum.png', dpi=200); plt.close(fig)


def fig_drag(seq='V2_02_medium'):
    gts, P, Q, V, BW, BA = load_gt('data/raw/%s_gt.csv' % seq)
    ts, w, a = load_imu('data/raw/%s_imu.csv' % seq)
    k = (ts >= gts[0]) & (ts <= gts[-1]); ts, w, a = ts[k], w[k], a[k]
    t = (ts - gts[0]) * 1e-9; tg = (gts - gts[0]) * 1e-9
    vw = np.stack([np.interp(t, tg, V[:, i]) for i in range(3)], 1)
    i = np.clip(np.searchsorted(tg, t), 0, len(tg) - 1); R = qmat(Q[i]); vb = np.einsum('nji,nj->ni', R, vw)
    up = a[t < 2].mean(0); up /= np.linalg.norm(up); Bp = M.drag_basis(up)
    n = 100; m = len(t) // n * n
    fb = (a[:m] @ Bp.T).reshape(-1, n, 2).mean(1); vp = (vb[:m] @ Bp.T).reshape(-1, n, 2).mean(1)
    ax_i = 1
    x = vp[:, ax_i]; y = fb[:, ax_i] - np.median(fb[:, ax_i])
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.scatter(x, y, s=10, color=OURS, alpha=0.55, linewidths=0)
    K = M.PLATFORMS['euroc_adis16448']['drag_k'][ax_i]
    xx = np.linspace(x.min(), x.max(), 10); ax.plot(xx, K * xx, color=INK, lw=1.6)
    ax.text(xx[-1], K * xx[-1] - 0.08, 'k = %.2f s$^{-1}$' % K, color=INK, ha='right', va='top', fontsize=10)
    ax.set_xlabel('body velocity, perp. to thrust [m/s]  (ground truth)'); ax.set_ylabel('accel, perp. to thrust [m/s²]')
    ax.set_title('Rotor drag: the accelerometer feels velocity')
    fig.tight_layout(); fig.savefig(OUT + '/drag.png', dpi=200); plt.close(fig)


def fig_blind(name='V1_01_easy_H1', seq='V1_01_easy'):
    gts, P, Q, V, *_ = load_gt('data/raw/%s_gt.csv' % seq)
    st = M.run('data/deg/%s.csv' % name, '/tmp/fb.txt', return_state=True)
    tsu, dead = st['tsu'], st['dead']
    tf = tsu[np.flatnonzero(dead)[0]]
    tg = (gts - tf) * 1e-9
    sp = np.linalg.norm(V, axis=1)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    m = (tg > -6) & (tg < 5.2)
    ax.plot(tg[m], sp[m], color=INK, label='true speed (GT)')
    v0 = sp[np.searchsorted(tg, 0)]
    tt = np.linspace(0, 5, 50)
    ax.plot(tt, v0 * np.exp(-tt / M.P_DEFAULT['blind_tau']), color=OURS, label='decay model (ours)')
    ax.plot(tt, np.full_like(tt, v0), color=CONST, ls='--', label='constant velocity')
    ax.axvspan(0, 5, color=PANEL, zorder=0); ax.text(0.15, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] > 0 else 0.5, 'IMU dead', color=INK2, fontsize=9)
    ax.set_xlabel('time from IMU failure [s]'); ax.set_ylabel('speed [m/s]')
    ax.set_title('Blind window: the vehicle settles, it does not cruise')
    ax.legend(loc='upper right', fontsize=9)
    fig.tight_layout(); fig.savefig(OUT + '/blind.png', dpi=200); plt.close(fig)


def fig_arch():
    fig = plt.figure(figsize=(12, 4.2)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 12); ax.set_ylim(0, 4.2); ax.axis('off')
    def box(x, y, w, h, title, sub, col=PANEL, edge=ACCENT):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.12', fc=col, ec=edge, lw=1.3))
        ax.text(x + 0.14, y + h - 0.22, title, fontsize=11.5, fontweight='bold', color=INK, va='top')
        ax.text(x + 0.14, y + h - 0.58, sub, fontsize=8.8, color=INK2, va='top', linespacing=1.35)
    def arrow(x0, y0, x1, y1):
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='-|>', color=INK2, lw=1.2))
    box(0.2, 2.25, 2.1, 1.65, '1  Ingest', 'schema + unit detection\n(header or physics)\nexact ns timestamps')
    box(0.2, 0.3, 2.1, 1.65, '2  Integrity triage', 'dead-sensor rows\nstuck · spikes · duplicates\ngap-aware dt')
    box(2.75, 2.25, 2.3, 1.65, '3  Platform & rest', 'gravity fingerprint\ntake-off detection\nfull gyro bias at rest')
    box(2.75, 0.3, 2.3, 1.65, '4  Attitude', 'segmented prefix-product\ngyro integration +\ngravity feedback per block')
    box(5.5, 0.3, 3.45, 3.6, '5  Translation smoother', 'linear-time-varying\nKalman filter + RTS\n\nstate: p · v · accel offset\n        workspace centre · drag offset\n\nobservations:\n • world acceleration (2.5 Hz)\n • rotor-drag body velocity\n • zero-velocity at rest\n • bounded-workspace prior\n\nprocess noise follows the\ndegradation severity')
    box(9.4, 2.25, 2.4, 1.65, '6  Blind window', 'IMU dead → velocity\ndecays (landing model)\nuncertainty grows')
    box(9.4, 0.3, 2.4, 1.65, '7  Output', 'one pose per input row\nHermite p · nlerp q\nTUM format')
    arrow(1.25, 2.25, 1.25, 1.95); arrow(2.3, 1.1, 2.75, 1.1); arrow(2.3, 3.07, 2.75, 3.07); arrow(3.9, 2.25, 3.9, 1.95)
    arrow(5.05, 1.1, 5.5, 1.1); arrow(5.05, 3.07, 5.5, 3.07); arrow(8.95, 3.07, 9.4, 3.07); arrow(8.95, 1.1, 9.4, 1.1)
    fig.savefig(OUT + '/architecture.png', dpi=200); plt.close(fig)


def fig_bars_wide():
    """Column version of the per-sequence ATE chart, for 16:9 slides and video."""
    r = json.load(open('results/baselines.json'))
    keys = sorted([k for k in r if k.endswith('_H1')], key=lambda k: (0 if k.startswith('V') else 1 if k.startswith('MH') else 2, k))
    lab = [k.replace('_H1', '').replace('_easy', '').replace('_medium', '').replace('_difficult', '').replace('TUM_room', 'TUM r').replace('_', ' ') for k in keys]
    m = lambda k, who: np.mean([r[k][who]['ate_rmse'], r[k.replace('_H1', '_H2')][who]['ate_rmse']])
    o = [m(k, 'ours') for k in keys]; c = [m(k, 'const') for k in keys]
    x = np.arange(len(keys)); h = 0.38
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.bar(x - h / 2 - 0.02, c, h, color=CONST, label='Constant-position baseline')
    ax.bar(x + h / 2 + 0.02, o, h, color=OURS, label='Path Finder')
    for i in range(len(keys)):
        ax.text(x[i] + h / 2 + 0.02, o[i] + 0.08, '%.2f' % o[i], ha='center', va='bottom', fontsize=8.5, color=INK)
    for xx, t in [(2, 'EuRoC Vicon rooms'), (7, 'EuRoC Machine Hall'), (11, 'TUM-VI rooms')]:
        ax.text(xx, max(c) * 1.13, t, ha='center', fontsize=10, color=INK2)
    for xx in [4.5, 9.5]:
        ax.axvline(xx, color=GRID, lw=1.0)
    ax.set_xticks(x); ax.set_xticklabels(lab, fontsize=9.5); ax.set_xlim(-0.6, len(keys) - 0.4)
    ax.set_ylim(0, max(c) * 1.22); ax.set_ylabel('ATE RMSE [m]'); ax.grid(axis='x', visible=False); ax.set_axisbelow(True)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=9.5)
    ax.set_title('Absolute trajectory error, mean of both degradation readings  ·  26 / 26 files beat the baseline', pad=28, fontsize=12)
    fig.tight_layout(); fig.savefig(OUT + '/ate_bars_wide.png', dpi=200); plt.close(fig)


def fig_mh_blind():
    """Machine Hall blind test: frozen estimator vs after the robust-drag fix."""
    fr = json.load(open('results/blind_mh.json')); r = json.load(open('results/baselines.json'))
    seqs = ['MH_01_easy', 'MH_02_easy', 'MH_03_medium', 'MH_04_difficult', 'MH_05_difficult']
    m = lambda d, s, who: np.mean([d[s + '_H1'][who]['ate_rmse'], d[s + '_H2'][who]['ate_rmse']])
    a = [m(fr, s, 'ours') for s in seqs]; c = [m(r, s, 'const') for s in seqs]; f = [m(r, s, 'ours') for s in seqs]
    x = np.arange(len(seqs)); h = 0.27
    fig, ax = plt.subplots(figsize=(11, 4.4))
    for off, v, col, lb in [(-h - 0.03, a, NAIVE, 'Frozen estimator, first blind run'), (0, c, CONST, 'Constant-position baseline'),
                            (h + 0.03, f, OURS, 'After robust drag weighting + rest detection')]:
        ax.bar(x + off, v, h, color=col, label=lb)
        for i in range(len(seqs)):
            ax.text(x[i] + off, v[i] + 0.15, '%.1f' % v[i], ha='center', va='bottom', fontsize=9, color=INK if col != CONST else INK2)
    ax.set_xticks(x); ax.set_xticklabels([s.replace('_', ' ') for s in seqs]); ax.set_ylabel('ATE RMSE [m]')
    ax.set_ylim(0, max(a) * 1.15); ax.grid(axis='x', visible=False); ax.set_axisbelow(True)
    ax.legend(loc='upper right', fontsize=9.5)
    for xi in (0, 1):
        ax.annotate('hand-carried start, then parked\nwith rotors off: drag model invalid' if xi else '', xy=(xi - h - 0.03 + 0.16, a[xi] - 0.6),
                    xytext=(1.55, 11.0), fontsize=10, color=INK2, arrowprops=dict(arrowstyle='->', color=INK2, lw=1.0))
    ax.set_title('Blind test on an unseen 20 m hall: what failed, and the fix', pad=10)
    fig.tight_layout(); fig.savefig(OUT + '/mh_blind.png', dpi=200); plt.close(fig)


if __name__ == '__main__':
    for f in (globals()[n] for n in sys.argv[1:]) if sys.argv[1:] else [fig_arch, fig_hero, fig_bars, fig_bars_wide, fig_mh_blind, fig_spectrum, fig_drag, fig_blind]:
        f(); print('ok', f.__name__)

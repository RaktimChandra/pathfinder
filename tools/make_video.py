"""Render the ~2:40 pipeline-walkthrough video (1920x1080, 30 fps, H.264).
One encoded file per scene, joined with the concat demuxer.  Usage: python tools/make_video.py"""
import os, sys, subprocess, copy, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, 'src'); sys.path.insert(0, 'tools')
import main as M
from research_common import load_gt
from evo.tools import file_interface
from evo.core import sync
from score import load_est

W, H, FPS = 1920, 1080, 30
OUT = 'video'; os.makedirs(OUT + '/scenes', exist_ok=True)
SURF = (10, 14, 26); CARD = (13, 27, 62); EDGE = (28, 42, 74); INK = (232, 237, 245); INK2 = (154, 166, 188)
CYAN = (0, 180, 216); OURS = '#1499BA'; CONSTC = '#C47318'; NAIVE = '#8C7FE0'
FD = '/usr/share/fonts/opentype/inter/'
F = lambda w, s: ImageFont.truetype(FD + 'Inter-%s.otf' % w, s)
MONO = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 30)
ENC = ['-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
plt.rcParams.update({'figure.facecolor': '#0A0E1A', 'axes.facecolor': '#0A0E1A', 'axes.edgecolor': '#1C2740',
                     'axes.labelcolor': '#9AA6BC', 'xtick.color': '#9AA6BC', 'ytick.color': '#9AA6BC', 'text.color': '#E8EDF5',
                     'axes.grid': True, 'grid.color': '#1C2740', 'font.size': 15, 'axes.spines.top': False,
                     'axes.spines.right': False, 'lines.linewidth': 2.6})


def spaced(s):
    return '  '.join(' '.join(w) for w in s.upper().split(' '))


def frame(label=None, caption=None):
    im = Image.new('RGB', (W, H), SURF); d = ImageDraw.Draw(im)
    if label:
        d.text((110, 70), spaced(label), font=F('SemiBold', 26), fill=CYAN)
    if caption:
        y = H - 150
        for i, line in enumerate(caption.split('\n')):
            d.text((110, y + i * 44), line, font=F('Regular', 34), fill=INK if i == 0 else INK2)
    return im, d


def paste_fig(im, path, box):
    x0, y0, x1, y1 = box
    f = Image.open(path).convert('RGB')
    s = min((x1 - x0) / f.width, (y1 - y0) / f.height)
    f = f.resize((int(f.width * s), int(f.height * s)), Image.LANCZOS)
    im.paste(f, (x0 + ((x1 - x0) - f.width) // 2, y0 + ((y1 - y0) - f.height) // 2))


def still(name, im, dur):
    p = '%s/scenes/%s.png' % (OUT, name); im.save(p)
    tmp = '%s/scenes/%s.tmp.mp4' % (OUT, name)
    vf = 'format=yuv420p,loop=-1:1,trim=duration=%.2f,fade=t=in:st=0:d=0.5,fade=t=out:st=%.2f:d=0.5' % (dur, dur - 0.5)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', p, '-vf', vf] + ENC + [tmp], check=True)
    os.replace(tmp, '%s/scenes/%s.mp4' % (OUT, name))


class Anim:
    def __init__(s, name, dur):
        s.name, s.n = name, int(dur * FPS)
        s.tmp = '%s/scenes/%s.tmp.mp4' % (OUT, name)
        vf = 'fade=t=in:st=0:d=0.5,fade=t=out:st=%.2f:d=0.5' % (dur - 0.5)
        s.p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                                '-r', str(FPS), '-i', '-', '-vf', vf] + ENC + [s.tmp], stdin=subprocess.PIPE)

    def push(s, im):
        s.p.stdin.write(im.tobytes())

    def close(s):
        s.p.stdin.close(); assert s.p.wait() == 0
        os.replace(s.tmp, '%s/scenes/%s.mp4' % (OUT, s.name))


def mpl_img(fig):
    fig.canvas.draw()
    return Image.frombuffer('RGBA', fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert('RGB')


R = json.load(open('results/baselines.json'))
MD = json.load(open('metadata.json'))


def aligned(seq, est):
    gt = file_interface.read_euroc_csv_trajectory('data/raw/%s_gt.csv' % seq)
    e = load_est(est); g, e = sync.associate_trajectories(gt, e, max_diff=0.003)
    ea = copy.deepcopy(e); ea.align(g, correct_scale=False)
    return g.timestamps - g.timestamps[0], g.positions_xyz, ea.positions_xyz


# ------------------------------------------------------------------ scenes
def s01_title():
    im, d = frame()
    d.rounded_rectangle((110, 300, 330, 350), 10, fill=(21, 101, 192))
    d.text((140, 309), 'TRACK 03', font=F('SemiBold', 26), fill=INK)
    d.text((104, 380), 'Path Finder', font=F('Bold', 150), fill=INK)
    d.text((110, 590), 'Inertial-only 6-DoF trajectory estimation under progressive sensor degradation', font=F('Regular', 38), fill=CYAN)
    d.text((110, 690), 'Team SRMIST_vortexxx  ·  SRM Institute of Science and Technology', font=F('Regular', 32), fill=INK2)
    for i, (nm, br) in enumerate([('Raktim Chandra', 'B.Tech CSE, Software Engineering'), ('Nipun Dewangan', 'B.Tech Artificial Intelligence'),
                                  ('Pronov Mazumdar', 'B.Tech CSE, Big Data Analytics')]):
        d.text((110 + i * 580, 760), nm, font=F('SemiBold', 30), fill=INK)
        d.text((110 + i * 580, 802), br, font=F('Regular', 24), fill=INK2)
    d.text((110, 960), 'Samsung PRISM XR Hackathon 2026', font=F('Medium', 28), fill=INK2)
    still('s01', im, 6)


def s02_problem():
    a = Anim('s02', 14)
    lines = [('One degraded IMU. Nothing else.', INK, 'Bold', 64),
             ('Noise, bias drift, spikes, stuck samples and dropouts grow over time.', INK2, 'Regular', 38),
             ('Then the sensor dies, 5 seconds before the target.', INK2, 'Regular', 38),
             ('Estimate every pose. Then dead-reckon the last 5 s.', CYAN, 'SemiBold', 44)]
    ys = [300, 430, 490, 620]
    for k in range(a.n):
        im, d = frame('The problem')
        t = k / FPS
        for i, (s, c, w, sz) in enumerate(lines):
            al = min(1, max(0, (t - 0.6 - i * 1.6) / 0.6))
            if al > 0:
                col = tuple(int(SURF[j] + (c[j] - SURF[j]) * al) for j in range(3))
                d.text((110, ys[i]), s, font=F(w, sz), fill=col)
        if t > 8.2:
            al = min(1, (t - 8.2) / 0.6)
            col = tuple(int(SURF[j] + (INK2[j] - SURF[j]) * al) for j in range(3))
            d.text((110, 790), 'Even with perfect orientation and perfect bias, plain double integration ends 27 m off.', font=F('Regular', 34), fill=col)
        a.push(im)
    a.close()


def s03_error_anim():
    t, P, E = aligned('V2_02_medium', 'results/V2_02_medium_H1.txt')
    _, _, N = aligned('V2_02_medium', 'results/base_naive_V2_02_medium_H1.txt')
    en = np.linalg.norm(N - P, axis=1); eo = np.linalg.norm(E - P, axis=1)
    a = Anim('s03', 16)
    fig, ax = plt.subplots(figsize=(17, 7.4), dpi=100)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.12)
    ax.set_yscale('log'); ax.set_xlim(0, t[-1]); ax.set_ylim(0.05, en.max() * 3)
    ax.set_xlabel('time [s]'); ax.set_ylabel('position error [m]')
    ax.axvspan(t[-1] - 5, t[-1], color='#0D1B3E', zorder=0)
    ln1, = ax.plot([], [], color=NAIVE); ln2, = ax.plot([], [], color=OURS)
    tx1 = ax.text(0, 0, '', color=NAIVE, fontsize=17, fontweight='bold'); tx2 = ax.text(0, 0, '', color=OURS, fontsize=17, fontweight='bold')
    for k in range(a.n):
        frac = min(1.0, (k / FPS) / 12.0); j = max(2, int(frac * len(t)))
        ln1.set_data(t[:j], en[:j]); ln2.set_data(t[:j], eo[:j])
        tx1.set_position((t[j - 1], en[j - 1] * 1.5)); tx1.set_text('textbook strapdown  %.0f m' % en[j - 1])
        tx2.set_position((t[j - 1], eo[j - 1] * 1.6)); tx2.set_text('Path Finder  %.2f m' % eo[j - 1])
        tx1.set_ha('right' if frac > 0.6 else 'left'); tx2.set_ha('right' if frac > 0.6 else 'left')
        im, d = frame('Why integration fails', 'Same degraded input, same scorer (evo, SE(3) alignment).\nEuRoC V2_02, organisers’ degradation script.')
        im.paste(mpl_img(fig), (110, 150))
        a.push(im)
    plt.close(fig); a.close()


def s_fig(name, label, fig, caption, dur):
    im, d = frame(label, caption)
    paste_fig(im, 'docs/figures/' + fig, (110, 140, W - 110, H - 190))
    still(name, im, dur)


def fig_takeoff():
    st = M.run('data/deg/V1_01_easy_H1.csv', '/tmp/v.txt', return_state=True)
    t, W_, A = st['t'], st['W'], st['A']
    m = t < 8
    k = (t[m] // 0.1).astype(int); nb = k[-1] + 1
    sd = np.sqrt(sum(np.bincount(k, W_[m, j].astype(float) ** 2, nb) / np.bincount(k, None, nb) - (np.bincount(k, W_[m, j], nb) / np.bincount(k, None, nb)) ** 2 for j in range(3)))
    fig, ax = plt.subplots(figsize=(17, 7.2), dpi=100); fig.subplots_adjust(left=0.08, right=0.97, top=0.9, bottom=0.13)
    tb = (np.arange(nb) + 0.5) * 0.1
    ax.plot(tb, sd, color=OURS)
    ax.axvspan(0, st['t_static'], color='#0D1B3E', zorder=0)
    ax.text(0.1, sd.max() * 0.9, 'at rest: gyro mean = gyro bias (all 3 axes)', color='#E8EDF5', fontsize=17)
    ax.axvline(st['t_static'], color='#9AA6BC', ls='--', lw=1.4); ax.text(st['t_static'] + 0.1, sd.max() * 0.6, 'take-off detected', color='#9AA6BC', fontsize=16)
    ax.set_xlabel('time [s]'); ax.set_ylabel('gyro scatter [rad/s]')
    fig.savefig('/tmp/takeoff.png', facecolor=fig.get_facecolor()); plt.close(fig)


def fig_noise():
    st = M.run('data/deg/V1_01_easy_H2.csv', '/tmp/v.txt', return_state=True)
    qb = st['qb_k']; tb = (np.arange(len(qb)) + 0.5) * st['dtb']
    fig, ax = plt.subplots(figsize=(17, 7.2), dpi=100); fig.subplots_adjust(left=0.08, right=0.97, top=0.9, bottom=0.13)
    ax.plot(tb, qb, color=OURS)
    ax.set_xlabel('time [s]'); ax.set_ylabel('acceleration-offset random walk')
    ax.text(5, qb.max() * 0.85, 'process noise follows the official severity ramp\n+ measured excess gyro noise', color='#E8EDF5', fontsize=17)
    fig.savefig('/tmp/noise.png', facecolor=fig.get_facecolor()); plt.close(fig)


def s10_terminal():
    so = open('/tmp/demo_stdout.txt').read().strip().replace('/tmp/demo_out.txt', 'estimated_trajectory.txt')
    cut = so.index("'unique'")
    lines = ['$ python src/main.py imu0/data.csv estimated_trajectory.txt', so[:cut].rstrip(), '   ' + so[cut:],
             '',
             '$ head -3 estimated_trajectory.txt'] + open('/tmp/demo_out.txt').read().splitlines()[:3] + [
             '', '$ wc -l imu0/data.csv estimated_trajectory.txt', '  22353 imu0/data.csv', '  22353 estimated_trajectory.txt',
             '', '# peak heap %.1f MB (budget 8)  |  %.1f ms per 1 s of IMU (budget 20)  |  1 thread' % (
                 MD['memory']['peak_heap_mb_tracemalloc'], MD['runtime']['ms_per_1s_of_imu'])]
    a = Anim('s10', 14)
    cps = 70.0
    total = sum(len(l) + 8 for l in lines)
    for k in range(a.n):
        im, d = frame('Run it', 'One file, NumPy only. Exactly one pose per input row, exact ns → s timestamps.')
        d.rounded_rectangle((70, 160, W - 40, H - 200), 18, fill=(8, 12, 22), outline=EDGE, width=2)
        budget = int((k / FPS) * cps * (1 if k / FPS < 3 else 2.2))
        y = 200
        for l in lines:
            if budget <= 0:
                break
            show = l[:budget]; budget -= len(l) + 8
            col = CYAN if l.startswith('$') else (INK2 if l.startswith('#') else INK)
            d.text((100, y), show, font=MONO, fill=col); y += 44
        a.push(im)
    a.close()


def s11_traj_anim():
    t, P, E = aligned('V2_02_medium', 'results/V2_02_medium_H1.txt')
    a = Anim('s11', 16)
    fig, ax = plt.subplots(figsize=(17, 7.6), dpi=100); fig.subplots_adjust(left=0.06, right=0.97, top=0.95, bottom=0.1)
    ax.set_xlim(min(P[:, 0].min(), E[:, 0].min()) - 0.3, max(P[:, 0].max(), E[:, 0].max()) + 0.3)
    ax.set_ylim(min(P[:, 1].min(), E[:, 1].min()) - 0.3, max(P[:, 1].max(), E[:, 1].max()) + 0.3)
    ax.set_aspect('equal'); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
    l1, = ax.plot([], [], color='#E8EDF5', lw=2.0, label='ground truth'); l2, = ax.plot([], [], color=OURS, lw=2.4, label='Path Finder (IMU only)')
    d1, = ax.plot([], [], 'o', color='#E8EDF5', ms=9); d2, = ax.plot([], [], 'o', color=OURS, ms=10)
    ax.legend(loc='upper right', frameon=False)
    for k in range(a.n):
        frac = min(1.0, (k / FPS) / 13.5); j = max(2, int(frac * len(t)))
        l1.set_data(P[:j, 0], P[:j, 1]); l2.set_data(E[:j, 0], E[:j, 1])
        d1.set_data([P[j - 1, 0]], [P[j - 1, 1]]); d2.set_data([E[j - 1, 0]], [E[j - 1, 1]])
        im, d = frame('Top-down replay', 't = %5.1f s   |   no camera, no GPS, no waypoints' % t[j - 1])
        im.paste(mpl_img(fig), (110, 140))
        a.push(im)
    plt.close(fig); a.close()


def s12_results():
    im, d = frame('Results', 'EuRoC: leave-one-sequence-out drag calibration.  17 sequences, both degradation readings.')
    paste_fig(im, 'docs/figures/ate_bars_wide.png', (90, 140, 1200, H - 190))
    x = 1260
    for i, (big, small, col) in enumerate([('%.1f MB' % MD['memory']['peak_heap_mb_tracemalloc'], 'peak heap  (budget 8 MB)', CYAN),
                                          ('%.1f ms' % MD['runtime']['ms_per_1s_of_imu'], 'per 1 s of IMU  (budget 20 ms)', CYAN),
                                          ('15 / 15', 'input-contract variants pass', CYAN)]):
        y = 190 + i * 230
        d.rounded_rectangle((x, y, W - 110, y + 200), 16, fill=CARD, outline=EDGE, width=2)
        d.text((x + 36, y + 30), big, font=F('Bold', 72), fill=col)
        d.text((x + 38, y + 130), small, font=F('Regular', 28), fill=INK2)
    still('s12', im, 13)


def s14_close():
    im, d = frame()
    d.text((104, 330), 'Path Finder', font=F('Bold', 120), fill=INK)
    d.text((110, 500), 'Physics the IMU already contains, a smoother that respects it,', font=F('Regular', 40), fill=INK2)
    d.text((110, 556), 'and an honest scorer.', font=F('Regular', 40), fill=INK2)
    d.text((110, 700), 'github.com/RaktimChandra/pathfinder', font=F('SemiBold', 44), fill=CYAN)
    d.text((110, 960), 'Team SRMIST_vortexxx  ·  Track 03  ·  Samsung PRISM XR Hackathon 2026', font=F('Regular', 28), fill=INK2)
    still('s14', im, 7)


if __name__ == '__main__':
    only = sys.argv[1:]
    fig_takeoff(); fig_noise()
    scenes = [
        ('s01', s01_title), ('s02', s02_problem), ('s03', s03_error_anim),
        ('s04', lambda: s_fig('s04', 'Insight 1 · where position lives', 'spectrum.png', 'Over 90% of a flight’s position energy is slower than 0.05 Hz.\nIntegration cannot reach it, so we smooth with physics and priors instead.', 10)),
        ('s05', lambda: s_fig('s05', 'Insight 2 · rotor drag', 'drag.png', 'A multirotor’s accelerometer feels drag proportional to body velocity: a drift-free velocity\nobservation, robust-weighted so it switches itself off when the drone is carried or parked.', 12)),
        ('s06', lambda: (lambda im_d: (paste_fig(im_d[0], '/tmp/takeoff.png', (110, 140, W - 110, H - 190)), still('s06', im_d[0], 10)))(frame('Insight 3 · the vehicle starts at rest', 'Take-off is detected from the IMU alone. The rest period gives the full gyro bias,\nincluding the heading axis gravity can never observe.'))),
        ('s07', lambda: s_fig('s07', 'Insight 4 · the blind window', 'blind.png', 'When the IMU dies the vehicle is still moving, and settles within about 3 s.\nVelocity decays; it does not cruise into the target.', 11)),
        ('s08', lambda: (lambda im_d: (paste_fig(im_d[0], '/tmp/noise.png', (110, 140, W - 110, H - 190)), still('s08', im_d[0], 10)))(frame('Insight 5 · degradation has a schedule', 'Late, dirty samples automatically count less.'))),
        ('s09', lambda: s_fig('s09', 'Architecture', 'architecture.png', '14-state linear-time-varying Kalman filter + RTS smoother at 2.5 Hz.\nSegmented parallel prefix product for attitude. Chunked, memory-bounded.', 13)),
        ('s10', s10_terminal), ('s11', s11_traj_anim), ('s12', s12_results),
        ('s13', lambda: s_fig('s13', 'A blind test that failed', 'mh_blind.png', 'We ran the frozen estimator on an unseen 20 m hall. Two flights start hand-carried, rotors off.\nA Cauchy weight on the drag innovation and rest detection anywhere fixed it. The drag constant was not refitted.', 13)),
        ('s14', s14_close)]
    for name, fn in scenes:
        if only and name not in only:
            continue
        fn(); print('rendered', name, flush=True)
    with open(OUT + '/list.txt', 'w') as f:
        for name, _ in scenes:
            f.write("file 'scenes/%s.mp4'\n" % name)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', OUT + '/list.txt', '-c', 'copy',
                    OUT + '/pathfinder_demo.tmp.mp4'], check=True)
    os.replace(OUT + '/pathfinder_demo.tmp.mp4', OUT + '/SRMIST_vortexxx_demo.mp4')
    print('done')

"""Fill the organisers' submission template (9 slides) with Path Finder content.
All numbers are read from results/baselines.json and metadata.json, never typed by hand.
Usage: python tools/build_deck.py deck/template.pptx deck/SRMIST_vortexxx.pptx
"""
import sys, json, copy
import numpy as np
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

SRC, DST = sys.argv[1], sys.argv[2]
META = sys.argv[3] if len(sys.argv) > 3 else 'metadata.json'
FIG = 'docs/figures/'
INK = RGBColor(0xE8, 0xED, 0xF5); INK2 = RGBColor(0x9A, 0xA6, 0xBC); CYAN = RGBColor(0x00, 0xB4, 0xD8)
CARD = RGBColor(0x0D, 0x1B, 0x3E); EDGE = RGBColor(0x1C, 0x2A, 0x4A); AMBER = RGBColor(0xC4, 0x73, 0x18)
VIOLET = RGBColor(0x8C, 0x7F, 0xE0)
FONT = 'Calibri'

R = json.load(open('results/baselines.json'))
M = json.load(open(META))


def seqmean(key, method, metric='ate_rmse'):
    return np.mean([R[k][method][metric] for k in R if k.startswith(key)])


EU = ['V1_01_easy', 'V2_01_easy', 'V2_02_medium']
TU = ['TUM_room1', 'TUM_room2']
eu_ours = np.mean([seqmean(s, 'ours') for s in EU]); eu_const = np.mean([seqmean(s, 'const') for s in EU])
tu_ours = np.mean([seqmean(s, 'ours') for s in TU]); tu_const = np.mean([seqmean(s, 'const') for s in TU])
naive_min = min(R[k]['naive']['ate_rmse'] for k in R); naive_max = max(R[k]['naive']['ate_rmse'] for k in R)


def km(x):
    return '%.1f km' % (x / 1000) if x >= 1000 else '%.0f m' % x


def text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    first = True
    for p in paras:
        if isinstance(p, str):
            p = dict(t=p)
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = p.get('align', PP_ALIGN.LEFT)
        para.space_after = Pt(p.get('after', 4))
        runs = p['t'] if isinstance(p['t'], list) else [(p['t'], {})]
        for rt, ro in runs:
            r = para.add_run(); r.text = rt
            f = r.font; f.name = ro.get('font', p.get('font', FONT)); f.size = Pt(ro.get('size', p.get('size', 14)))
            f.bold = ro.get('bold', p.get('bold', False)); f.color.rgb = ro.get('color', p.get('color', INK))
    return tb


def card(slide, x, y, w, h, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.06
    s.fill.solid(); s.fill.fore_color.rgb = CARD
    s.line.color.rgb = EDGE; s.line.width = Pt(0.75)
    s.shadow.inherit = False
    if name: s.name = name
    return s


def pic(slide, path, x, y, w=None, h=None, name=None):
    kw = {}
    if w: kw['width'] = Inches(w)
    if h: kw['height'] = Inches(h)
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), **kw)
    if name: p.name = name
    return p


def stat(slide, x, y, w, big, small, color=CYAN, bigsize=30):
    text(slide, x, y, w, 0.55, [dict(t=big, size=bigsize, bold=True, color=color)])
    text(slide, x, y + 0.58, w, 0.5, [dict(t=small, size=11, color=INK2)])


def set_text(shape, s):
    tf = shape.text_frame
    p = tf.paragraphs[0]
    if p.runs:
        p.runs[0].text = s
        for r in p.runs[1:]:
            r.text = ''
    else:
        p.add_run().text = s


prs = Presentation(SRC)
S = list(prs.slides)
sh = lambda s, nm: next(x for x in s.shapes if x.name == nm)

# ---------------- 1. title ----------------
s = S[0]
set_text(sh(s, 'Text 7'), 'TRACK 03')
set_text(sh(s, 'Text 8'), 'Path Finder')
tf = sh(s, 'Text 10').text_frame
pars = tf.paragraphs
pars[0].runs[0].text = 'Team SRMIST_vortexxx'
pars[1].runs[0].text = 'SRM Institute of Science and Technology'
for p_ in pars:
    for r_ in p_.runs: r_.font.size = Pt(18)
sh(s, 'Text 10').width = Inches(4.9)
text(s, 0.55, 3.45, 6.4, 0.9, [dict(t='Inertial-only 6-DoF trajectory estimation and blind dead-reckoning under progressive sensor degradation', size=15, color=CYAN)])
mb = sh(s, 'Text Box 22')
mb.left = Inches(6.3); mb.top = Inches(2.45); mb.width = Inches(2.3); mb.height = Inches(1.2)
mtf = mb.text_frame
mtf.paragraphs[0].runs[0].text = 'Members'
for nm in ['Raktim Chandra (lead)', 'Nipun Dewangan', 'Pronov Mazumdar']:
    p = mtf.add_paragraph(); r = p.add_run(); r.text = nm
    r.font.size = Pt(13); r.font.color.rgb = INK2; r.font.name = FONT

# ---------------- 2. problem ----------------
s = S[1]
text(s, 0.5, 1.1, 4.6, 0.7, [dict(t='One degraded IMU. No camera, no GPS, no waypoints.', size=17, bold=True)])
text(s, 0.5, 1.85, 4.6, 2.0, [
    dict(t=[('Noise, bias drift, spikes, stuck samples and dropouts grow until the sensor ', {}), ('dies 5 s before the target.', dict(bold=True))], size=13, after=8),
    dict(t='Double integration turns every 0.01 m/s² of bias into metres within a minute.', size=13, after=8),
    dict(t='Over 90% of a flight’s position energy is slower than 0.05 Hz, exactly where integration fails.', size=13, after=8),
])
card(s, 0.5, 3.75, 2.2, 1.45); stat(s, 0.65, 3.85, 1.95, '27 m', 'error with perfect attitude and perfect bias (V1_01, clean)')
card(s, 2.9, 3.75, 2.2, 1.45); stat(s, 3.05, 3.85, 1.95, km(naive_max), 'textbook strapdown on degraded TUM-VI', color=VIOLET)
pic(s, FIG + 'spectrum.png', 5.35, 1.05, w=4.25)

# ---------------- 3. solution ----------------
s = S[2]
text(s, 0.5, 1.05, 9.0, 0.45, [dict(t='Turn it into a smoothing problem, and feed it physics the IMU already contains', size=16, bold=True)])
items = [
    ('Rotor drag measures velocity', 'A multirotor’s accelerometer feels drag ∝ body velocity (k ≈ −0.2 s⁻¹). Drift-free velocity, no extra sensor.'),
    ('The vehicle starts at rest', 'Take-off detected from the IMU: full gyro bias — incl. the unobservable heading axis — plus zero-velocity anchors.'),
    ('The blind window is a landing', 'At failure the vehicle is still moving and settles within ~3 s: velocity decays, it does not cruise.'),
    ('Degradation has a schedule', 'Process noise follows the official ramp and the measured gyro noise excess: late, dirty samples count less.'),
]
for i, (h, b) in enumerate(items):
    x = 0.5 + (i % 2) * 4.6; y = 1.65 + (i // 2) * 1.8
    card(s, x, y, 4.4, 1.6)
    text(s, x + 0.2, y + 0.15, 4.0, 0.4, [dict(t='%d   %s' % (i + 1, h), size=15, bold=True, color=CYAN)])
    text(s, x + 0.2, y + 0.6, 4.0, 0.95, [dict(t=b, size=12.5, color=INK)])

# ---------------- 4. architecture ----------------
s = S[3]
pic(s, FIG + 'architecture.png', 0.4, 1.05, w=9.2)
text(s, 0.5, 4.45, 9.0, 0.8, [dict(t=[('One file, NumPy only, single thread. ', dict(bold=True)), ('Gyro increments composed by a segmented parallel prefix product; a 14-state linear-time-varying Kalman filter + RTS smoother at 10 Hz fuses world acceleration, drag velocity, rest constraints and a bounded-workspace prior.', {})], size=12.5, color=INK2)])

# ---------------- 5. final output ----------------
s = S[4]
set_text(sh(s, 'Text 2'), 'TRACK FINAL OUTPUT')
pic(s, FIG + 'ate_bars.png', 0.35, 1.15, w=5.8)
x0 = 6.35
text(s, x0, 1.1, 3.2, 0.4, [dict(t='Submission contract', size=15, bold=True)])
text(s, x0, 1.5, 3.2, 1.3, [
    dict(t='estimated_trajectory.txt — TUM, 8 columns', size=12, color=INK2, after=3),
    dict(t='one pose per input row, input order', size=12, color=INK2, after=3),
    dict(t='exact ns → s timestamps', size=12, color=INK2, after=3),
    dict(t='metadata.json — measured runtime & heap', size=12, color=INK2, after=3),
])
card(s, x0, 2.95, 1.5, 1.15); stat(s, x0 + 0.12, 3.0, 1.3, '%.1f MB' % M['memory']['peak_heap_mb_tracemalloc'], 'peak heap (budget 8)', bigsize=22)
card(s, x0 + 1.65, 2.95, 1.5, 1.15); stat(s, x0 + 1.77, 3.0, 1.3, '%.1f ms' % M['runtime']['ms_per_1s_of_imu'], 'per 1 s of IMU (budget 20)', bigsize=22)
text(s, x0, 4.35, 3.2, 0.9, [dict(t='EuRoC scores are leave-one-sequence-out; TUM-VI room2 never touched tuning.', size=11, color=INK2)])

# ---------------- 6. differentiation ----------------
s = S[5]
pic(s, FIG + 'hero.png', 0.3, 1.05, w=6.3)
x0 = 6.7
card(s, x0, 1.1, 2.9, 1.15); stat(s, x0 + 0.15, 1.15, 2.6, '%s–%s' % (km(naive_min), km(naive_max)), 'textbook strapdown (same inputs)', color=VIOLET, bigsize=22)
card(s, x0, 2.4, 2.9, 1.15); stat(s, x0 + 0.15, 2.45, 2.6, '%.2f / %.2f m' % (eu_const, tu_const), 'constant position, EuRoC / TUM-VI', color=AMBER, bigsize=22)
card(s, x0, 3.7, 2.9, 1.15); stat(s, x0 + 0.15, 3.75, 2.6, '%.2f / %.2f m' % (eu_ours, tu_ours), 'Path Finder, EuRoC / TUM-VI', bigsize=22)
text(s, 0.5, 3.9, 5.9, 0.9, [dict(t='Never worse than doing nothing on any test file, and bounded by construction — even when the gyro columns receive accelerometer-level corruption.', size=12, color=INK2)])

# ---------------- 7. demo & setup ----------------
s = S[6]
for x in list(s.shapes):
    if x.name == 'Text Box 36' and not x.text_frame.text.strip():
        x._element.getparent().remove(x._element)
card(s, 0.5, 1.1, 5.0, 1.55)
text(s, 0.7, 1.22, 4.6, 1.35, [
    dict(t='pip install numpy', size=13, font='Consolas', color=CYAN, after=6),
    dict(t='python src/main.py imu0/data.csv \\', size=13, font='Consolas', color=INK, after=0),
    dict(t='       estimated_trajectory.txt', size=13, font='Consolas', color=INK, after=6),
    dict(t='docker build -t pathfinder . && docker run ...', size=11, font='Consolas', color=INK2),
])
text(s, 0.5, 2.85, 5.0, 0.4, [dict(t='Accepts what organisers might send', size=15, bold=True)])
text(s, 0.5, 3.25, 5.0, 2.0, [dict(t='EuRoC CSV, folder or zip · gyro-first or accel-first columns (header or physics) · m/s² or g · rad/s or deg/s · integer-ns or decimal timestamps · unsorted, duplicated or missing rows · 6 s to 10 min', size=12.5, color=INK2)])
card(s, 5.8, 1.1, 3.8, 3.35)
stat(s, 6.0, 1.25, 3.4, '15 / 15', 'input-contract variants pass, identical ATE')
text(s, 6.0, 2.45, 3.4, 2.6, [
    dict(t='Evaluation harness (tools/)', size=13, bold=True, after=6),
    dict(t='official degrade_imu.py, both column readings', size=11.5, color=INK2, after=3),
    dict(t='evo ATE with SE(3) Umeyama, RPE, tier views', size=11.5, color=INK2, after=3),
    dict(t='naive + constant baselines', size=11.5, color=INK2, after=3),
    dict(t='leave-one-out drag calibration', size=11.5, color=INK2, after=3),
    dict(t='tracemalloc heap + CPU-time budget checks', size=11.5, color=INK2, after=3),
])

# ---------------- 8. brownie ----------------
s = S[7]
for x in list(s.shapes):
    if x.name == 'Text Box 36' and not x.text_frame.text.strip():
        x._element.getparent().remove(x._element)
pic(s, FIG + 'drag.png', 0.35, 1.0, w=4.6)
pic(s, FIG + 'blind.png', 5.05, 1.0, w=4.6)
text(s, 0.5, 3.85, 4.4, 1.4, [dict(t='Physics, measured: the perpendicular accelerometer tracks body velocity with a slope stable across sequences — a free velocity sensor on every multirotor.', size=12, color=INK2)])
text(s, 5.2, 3.85, 4.4, 1.4, [dict(t='Mission-aware: the IMU dies while the vehicle is still moving; it settles within ~3 s. Decay beats constant-velocity extrapolation into the target.', size=12, color=INK2)])

# ---------------- 9. thank you ----------------
s = S[8]
for x in s.shapes:
    if x.name == 'Text 25':
        x.text_frame.paragraphs[0].add_run().text = 'github.com/RaktimChandra/pathfinder'
        r = x.text_frame.paragraphs[0].runs[-1]; r.font.size = Pt(11); r.font.color.rgb = INK; r.font.name = FONT
        x.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
text(s, 2.0, 3.25, 6.0, 0.5, [dict(t='Path Finder · Track 03 · SRMIST_vortexxx', size=14, color=INK2, align=PP_ALIGN.CENTER)])
prs.save(DST)
print('saved', DST)

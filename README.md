# Path Finder — inertial-only trajectory estimation under sensor degradation

**Samsung PRISM XR Hackathon 2026 · Track 03 · Team SRMIST_vortexxx (SRM Institute of Science and Technology)**

Path Finder reconstructs a 6-DoF trajectory from a single degraded IMU stream: rising noise, bias and scale drift, spikes, stuck samples, dropouts, and a sensor that dies five seconds before the end. It uses no camera, no GPS, no waypoints and no ground truth at run time. It is one Python file that needs only NumPy, runs single-threaded, and outputs exactly one pose per input row.

![Path Finder vs textbook strapdown integration](docs/figures/hero.png)

## Results

Each sequence was scored with **evo** using the organisers' protocol: SE(3) Umeyama alignment, then ATE RMSE. Inputs were produced by the **official `degrade_imu.py`** (default settings, seed 42) under both column interpretations described in [Evaluation protocol](#evaluation-protocol). Lower is better.

| Sequence | Naive strapdown | Constant position | **Path Finder** |
|---|---:|---:|---:|
| EuRoC V1_01 | 1.4 km | 1.85 m | **1.36 m** |
| EuRoC V1_02 † | 349 m | 1.78 m | **0.80 m** |
| EuRoC V1_03 † | 530 m | 1.58 m | **1.44 m** |
| EuRoC V2_01 | 830 m | 2.30 m | **2.03 m** |
| EuRoC V2_02 | 507 m | 2.11 m | **1.40 m** |
| EuRoC MH_01 ‡ | 50.4 km | 4.33 m | **3.90 m** |
| EuRoC MH_02 ‡ | 34.4 km | 4.66 m | **4.31 m** |
| EuRoC MH_03 ‡ | 31.5 km | 3.58 m | **2.34 m** |
| EuRoC MH_04 ‡ | 17.8 km | 6.80 m | **4.54 m** |
| EuRoC MH_05 ‡ | 1.6 km | 6.87 m | **4.83 m** |
| TUM-VI room1 | 12.5 km | 1.00 m | **0.46 m** |
| TUM-VI room2 † | 12.1 km | 1.22 m | **0.52 m** |
| TUM-VI room3 † | 17.3 km | 1.25 m | **0.49 m** |

Each number is the mean of the two degradation readings (H1, H2). Every EuRoC number is **leave-one-sequence-out**: the drag calibration used to score a sequence was fitted only on the other sequences (see `tools/fit_drag.py`).

† Blind tests for the original design. Their first scores were V1_02 **0.89 m**, V1_03 **1.59 m**, TUM-VI room2 **0.68 m** and room3 **0.48 m** (constant baselines: 1.78, 1.58, 1.22 and 1.25 m). The global smoother step (0.1 s → 0.4 s) was later chosen on all sequences.

‡ **Machine Hall: a blind test that failed, and what we changed.** The Machine Hall is a ~20 m industrial hall, more than twice the size of the rooms we developed in. We ran the frozen estimator on all five sequences before changing anything. It beat the constant baseline on MH_03–05, but was **2.5–3× worse on MH_01 and MH_02** (10.8 m and 14.2 m against 4.3 m and 4.7 m). The cause was physical. Those two flights begin with the drone carried by hand and then left on the floor with its rotors off. The rotor-drag model, which says sideways body acceleration is proportional to airspeed, does not hold when nothing is flying, so it reported several m/s of velocity that did not exist. We made three changes:

1. **Robust drag weighting:** a Cauchy weight on the drag innovation. When the normalised innovation squared exceeds 4 (2σ), its noise is inflated in proportion. This is a standard robust-estimation rule with a conventional threshold, and it changes the Vicon results by at most ±0.03 m.
2. **Rest detection over the whole sequence:** zero-velocity updates at every rest period of at least 1.5 s, not only the one at take-off.
3. **Workspace prior:** σ = 3.0 → 3.5 m for the EuRoC platform only. This value minimises the worst-case ratio against the constant baseline over all ten EuRoC sequences.

![Machine Hall blind test](docs/figures/mh_blind.png)

Change 3 was tuned with the Machine Hall in view, so the ‡ rows are development results, not blind results. The rotor-drag constant was **not** refitted. Fitted independently on the Machine Hall, it comes out as k = [−0.166, −0.215], against [−0.166, −0.201] from the Vicon rooms. That agreement is independent evidence that the drag model describes the vehicle and not the room.

All **26 test files** (13 sequences × 2 degradation readings) beat the constant baseline.

| Tier view (mean, ours / constant) | EuRoC Vicon rooms | EuRoC Machine Hall | TUM-VI rooms |
|---|---:|---:|---:|
| ATE (whole trajectory) | **1.41** / 1.92 m | **3.98** / 5.25 m | **0.49** / 1.16 m |
| Waypoints (every 10 s) | **1.42** / 1.92 m | **4.06** / 5.45 m | **0.50** / 1.21 m |
| Blind 5 s window | **1.92** / 1.94 m | **3.25** / 4.21 m | 0.72 / **0.68** m |
| 2 s after each dropout | **1.43** / 1.95 m | **3.13** / 5.03 m | **0.61** / 1.14 m |

The blind window is the hardest tier. Once the IMU is dead, the error is set almost entirely by the position error at the moment of failure, and that error comes from the slow component of position, which an IMU alone cannot observe. We tested three ideas for the blind window: a return-to-launch prior, faster velocity decay, and a home-position prior. None improved it consistently, so none ships.

**Ablation** (same protocol; `tools/ablation.py`; mean ATE / blind-window RMSE):

| Configuration | Vicon rooms | Machine Hall | TUM-VI |
|---|---:|---:|---:|
| **final** | **1.41** / 1.92 m | **3.98** / 3.25 m | **0.49** / 0.72 m |
| without: rotor-drag velocity | 1.65 / 1.89 m | 5.13 / 4.20 m | 0.49 / 0.72 m |
| without: degradation-aware noise | 2.69 / 4.95 m | 5.81 / 8.91 m | 1.62 / 3.41 m |
| without: robust drag weighting | 1.40 / 1.91 m | 8.02 / 3.51 m | 0.49 / 0.72 m |
| without: rest-period bias / ZUPT | 1.55 / 1.85 m | 4.24 / 3.23 m | 0.49 / 0.72 m |
| constant-velocity blind window | 1.41 / 1.93 m | 3.99 / 3.48 m | 0.49 / 0.72 m |

![ATE per sequence](docs/figures/ate_bars.png)

**Resource budget** (measured by `tools/make_metadata.py` on a 143.6 s EuRoC file):

| | Budget | Measured |
|---|---:|---:|
| Peak memory (heap, `tracemalloc`) | ≤ 8 MB | **3.0 MB** (4.4 MB counting NumPy's own import) |
| Compute per 1 s of IMU (single thread) | ≤ 20 ms | **1.2–1.7 ms** (≈ 9–12 ms even with `tracemalloc` running) |
| Threads · network · GPU | 1 · none · none | 1 · none · none |

Memory grows by about 0.014 MB per second of input. A 430 s file peaks at 6.9 MB (8.7 MB counting the NumPy import), so inputs up to about 400 s stay under 8 MB by either count. The longest EuRoC or TUM-VI room sequence is 182 s (MH_01, 3.2 MB).

## Run it

```bash
pip install numpy                        # the only dependency
python src/main.py path/to/imu0/data.csv estimated_trajectory.txt
# also accepted: a folder containing imu0/data.csv (or mav0/imu0/data.csv), or a .zip of it
```

With Docker:

```bash
docker build -t pathfinder .
docker run --rm -v "$PWD/data:/data" pathfinder /data/imu0/data.csv /data/estimated_trajectory.txt
```

The output is `estimated_trajectory.txt` in TUM format (`timestamp tx ty tz qx qy qz qw`):
- exactly one pose per input row, in input order (duplicate rows and blind-window rows included)
- timestamps converted from integer nanoseconds to seconds exactly (`%d.%09d`), with no float rounding

## How it works

![Architecture](docs/figures/architecture.png)

The design follows a few physical facts we measured before writing the estimator.

**1. Integration alone cannot recover where the vehicle is.** In EuRoC, more than 90% of the position signal's energy lies below 0.05 Hz, which corresponds to periods longer than 20 s. Over those timescales, double-integrated accelerometer error grows quadratically. We checked this directly: with the true orientation and the true accelerometer bias supplied, naive integration still ends **27 m** off on V1_01. So we treat position as a smoothing problem with physically motivated observations, not as integration.

![Spectrum](docs/figures/spectrum.png)

**2. A multirotor's accelerometer measures its velocity.** Rotor drag puts a force in the plane perpendicular to the thrust axis, proportional to the vehicle's velocity in its own frame. On EuRoC, the fitted coefficient is about −0.2 s⁻¹ on both perpendicular axes, and it is stable across sequences. This gives a velocity observation that does not drift. Removing it raises EuRoC ATE from 1.41 to 1.67 m.

![Rotor drag](docs/figures/drag.png)

**3. The vehicle starts at rest.** Every EuRoC flight sits on the ground for 1.5–3.5 s before take-off. We detect that rest period from the IMU (low gyro scatter, steady specific force) and use it three ways:
- the mean gyro reading there gives the full gyro bias, **including the vertical axis**, which gravity can never observe
- the rest period gives zero-velocity constraints for the smoother
- the vehicle's own sensor mounting gives a fingerprint that identifies the platform

**4. The blind window is a landing, not a cruise.** At the moment the IMU dies, EuRoC vehicles are still moving, and they come to rest within about 3 s. So during the blind window, our model decays velocity exponentially and lets uncertainty grow, rather than extrapolating at constant velocity.

![Blind window](docs/figures/blind.png)

**5. Degradation follows a known schedule.** The official script ramps severity as `0.02 + 0.98·(t/T)^1.7`. It also adds white gyro noise that we can measure directly, as high-frequency scatter above the clean level at the start of the run. The smoother's process noise follows both, so late, unreliable samples automatically get less weight. This is the most important component: without it, EuRoC ATE rises from 1.41 to 1.94 m and TUM-VI ATE from 0.49 to 1.42 m.

### Pipeline (`src/main.py`)

| Stage | What it does |
|---|---|
| **Ingest** | Accepts EuRoC CSV, a folder or a zip. Detects whether gyro or accelerometer columns come first, from the header names, and checks that against physics: an accelerometer's magnitude stays steady near *g*. Detects m/s² vs *g*, rad/s vs deg/s, and integer-ns vs decimal timestamps. |
| **Integrity triage** | Handles dead-sensor rows (all zeros), stuck samples, spikes (running median plus MAD gate), duplicate timestamps (compacted in place) and dropouts (gap-aware Δt). |
| **Platform and rest** | Identifies the platform from the gravity direction in the sensor frame. Measures the gyro bias during the initial rest, and detects every later rest period (≥ 1.5 s of quiet gyro and accelerometer with \|a\| ≈ g) for zero-velocity updates. |
| **Attitude** | Complementary filter. Gyro increments within each 0.1 s block are composed with a segmented parallel prefix product (vectorised), and gravity feedback runs once per block. Recognised multirotors use a body-frame gravity reference; anything else uses a world-frame reference, averaged over seconds, that is robust to aggressive handheld motion. |
| **Translation smoother** | Linear-time-varying Kalman filter plus RTS smoother at 2.5 Hz (0.4 s blocks, which average out rotor vibration). 14 states: position, velocity, world-frame acceleration offset (accelerometer bias plus residual tilt), workspace centre, drag offset. Observations: block-averaged world acceleration, rotor-drag body velocity (Cauchy-weighted, so it switches itself off when the vehicle is not flying), zero velocity at rest, and a soft bounded-workspace prior. |
| **Blind window** | Velocity-decay dynamics after the failure. Orientation is held. |
| **Output** | Cubic Hermite interpolation of position and normalised quaternion interpolation (nlerp) of orientation, evaluated at every input row and written in chunks. |

Memory stays small by design: one float32 (n,6) buffer, chunked processing everywhere, orientation stored at 50 Hz, and smoother history kept in float32. The smoother runs at 2.5 Hz.

## Evaluation protocol

Everything in `tools/` reproduces the numbers above.

| Script | Purpose |
|---|---|
| `make_testset.py` | Builds degraded inputs with the official `degrade_imu.py`. **H1:** reorder columns so accelerometer noise goes on the accelerometer, degrade, restore EuRoC order. **H2:** feed the EuRoC file to the script as is, so the gyro columns receive accelerometer-level corruption. The clean IMU is first cropped to the ground-truth span, so the hidden 5 s failure window is covered by ground truth. |
| `score.py` | evo ATE (SE(3) Umeyama, no scale), RPE, rotation error, and three tier views: waypoints every 10 s, the blind window, and the 2 s after each dropout. |
| `baselines.py` | Naive strapdown and constant-position references on the same inputs and scorer. |
| `fit_drag.py` | Rotor-drag calibration, with leave-one-sequence-out folds. |
| `blind_mh.py`, `oracle_gate.py` | The Machine Hall blind test of the frozen estimator, and the oracle experiment (ground-truth rest and flight masks) used to find the cause of the MH_01/MH_02 failure. |
| `robustness.py` | Input-contract suite. 15 variants: no header, header without `#`, accelerometer-first columns with and without a header, CRLF line endings, zip, folder, unsorted rows, *g* units, deg/s, decimal timestamps, a 6 s file, no failure window, and a 10-minute file. Every variant must pass the output contract, and every variant scores the same ATE as the reference. |
| `perf.py`, `make_metadata.py` | Peak heap (`tracemalloc`) and CPU time per second of IMU. |

Ground truth comes from EuRoC MAV (`state_groundtruth_estimate0`) and TUM-VI (motion capture, rooms). The datasets are not redistributed; `tools/` documents how to fetch them.

## Honest limitations

- **IMU-only position has a floor.** The slow component of position is unobservable from an IMU alone. Our gains over the constant baseline come from physics (drag, rest, landing), from the degradation model, and from bounded-workspace priors.
- **The bounded-workspace prior assumes indoor flight.** It matches EuRoC (8 m rooms and a ~20 m hall) and TUM-VI. In the larger hall it is a weaker constraint, and our margin over the constant baseline on the two longest flights (MH_01, MH_02) is only 8–10%. An open-field mission would need it switched off: set `room_h` / `room_v` to large values.
- **Heading drift is unobservable after take-off.** Bias random walk on the vertical gyro axis cannot be seen without a heading reference. The rest-period bias removes the static part of it.
- **`degrade_imu.py` quirk:** in the H2 interpretation, the script auto-detects "accelerometer units" from the gyro columns. With fast handheld rotation, the gyro magnitude near 1 makes it treat the gyro as *g* units, which scales that corruption down about 10× on TUM-VI.

## Submission bundle

`SRMIST_vortexxx.zip` follows the layout on the organisers' Track 3 slide:

```
SRMIST_vortexxx.zip
├── estimated_trajectory.txt   # output of src/main.py on the evaluation input
├── metadata.json              # measured runtime, peak heap, platform, versions
└── src/
    ├── main.py
    └── README.md
```

To regenerate it on the organisers' evaluation input:

```bash
python src/main.py <evaluation_folder_or_zip> estimated_trajectory.txt
python tools/make_metadata.py <evaluation_folder_or_zip> estimated_trajectory.txt metadata.json
```

Until that input is released, the bundled `estimated_trajectory.txt` is the output on EuRoC V1_01 degraded with the official script (H1 reading).

## Repository layout

```
src/main.py            the estimator (single file, NumPy only)
src/README.md          short run instructions (submission bundle)
tools/                 evaluation harness, baselines, calibration, figures
docs/figures/          figures used here and in the deck
Dockerfile, requirements.txt
estimated_trajectory.txt, metadata.json   submission outputs
```

## References

- Burri et al., *The EuRoC micro aerial vehicle datasets*, IJRR 2016.
- Schubert et al., *The TUM VI benchmark for evaluating visual-inertial odometry*, IROS 2018.
- Leishman, Macdonald, Beard, McLain, *Quadrotors and accelerometers: state estimation with an improved dynamic model*, IEEE CSM 2014.
- Brossard, Bonnabel, Barrau, *Denoising IMU gyroscopes with deep learning for open-loop attitude estimation*, RA-L 2020.
- Rauch, Tung, Striebel, *Maximum likelihood estimates of linear dynamic systems*, AIAA J. 1965.
- Grupp, *evo: Python package for the evaluation of odometry and SLAM*, 2017.

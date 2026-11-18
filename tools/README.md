# Evaluation harness

Put the organisers' `degrade_imu.py` (Track 3 student package) in this folder, and the raw
sequences under `data/raw/` as `<SEQ>_imu.csv` (EuRoC `imu0/data.csv`) and `<SEQ>_gt.csv`
(EuRoC `state_groundtruth_estimate0/data.csv`; for TUM-VI, convert with `tum2euroc_gt.py`).

    python tools/make_testset.py data/raw/V2_02_medium_imu.csv data/raw/V2_02_medium_gt.csv data/deg V2_02_medium
    python tools/evalall.py                       # run + score every file in data/deg
    python tools/baselines.py                     # naive strapdown / constant / ours
    python tools/robustness.py data/deg/V2_02_medium_H1.csv
    python tools/perf.py data/deg/V2_02_medium_H1.csv
    python tools/fit_drag.py V1_01_easy V2_01_easy V2_02_medium   # leave-one-out drag fit
    python tools/figures.py && python tools/build_deck.py deck/template.pptx deck/out.pptx

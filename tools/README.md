# Evaluation harness

Put the organisers' `degrade_imu.py` (Track 3 student package) in this folder, and the raw
sequences under `data/raw/` as `<SEQ>_imu.csv` (EuRoC `imu0/data.csv`) and `<SEQ>_gt.csv`
(EuRoC `state_groundtruth_estimate0/data.csv`; for TUM-VI, convert with `tum2euroc_gt.py`).

    python tools/make_testset.py data/raw/V2_02_medium_imu.csv data/raw/V2_02_medium_gt.csv data/deg V2_02_medium
    python tools/evalall.py                 # run + score every file in data/deg
    python tools/baselines.py               # naive strapdown / constant / ours (EuRoC: LOO drag calibration)
    python tools/ablation.py                # one component removed at a time
    python tools/robustness.py data/deg/V2_02_medium_H1.csv
    python tools/perf.py data/deg/V2_02_medium_H1.csv
    python tools/blind_new.py V2_03_difficult TUM_room4   # fresh sequences in data/deg_new
    python tools/blind_mh.py                # Machine Hall test sets (make_testset.py ... data/deg_mh ...)
    python tools/oracle_gate.py MH_01_easy_H1   # ground-truth-mask diagnosis used for the MH_01/02 failure
    python tools/fit_drag.py V1_01_easy V1_02_medium V1_03_difficult V2_01_easy V2_02_medium
    python tools/figures.py && python tools/build_deck.py deck/template.pptx deck/out.pptx
    python tools/make_video.py

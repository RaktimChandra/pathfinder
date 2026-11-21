# Path Finder — run instructions

Requirements: Python 3.8+ and NumPy. Nothing else.

    pip install numpy
    python main.py <imu_input> [estimated_trajectory.txt]

`<imu_input>` can be a EuRoC IMU CSV (`imu0/data.csv`), a folder containing
`imu0/data.csv` or `mav0/imu0/data.csv`, or a `.zip` of such a folder.

The output is TUM format, `timestamp tx ty tz qx qy qz qw`, with exactly one pose per input
row in input order. Timestamps are converted from nanoseconds to seconds exactly.

Optional: add `--sigma sigma.txt` to also write each row's calibrated 1-sigma position
uncertainty in metres. The trajectory file is identical with or without it.

It runs single-threaded and offline, with peak heap of about 3 MB and about 2 ms of
compute per second of IMU. See the top-level README for the method and the evaluation.

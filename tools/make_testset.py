#!/usr/bin/env python3
"""Build degraded evaluation inputs from a clean EuRoC-format IMU CSV + ground truth.

The organisers' input is EuRoC format (t, gyro xyz, accel xyz), but the official
degrade_imu.py expects (t, accel xyz, gyro xyz). Two hypotheses for how the hidden
test was produced, both generated here:

  H1 "correct":  reorder -> degrade -> reorder back (accel noise on accel, gyro noise on gyro)
  H2 "naive":    degrade the EuRoC file as-is (gyro columns receive accel-level corruption)

The clean IMU is cropped to the ground-truth time span first, so the 5 s failure
window is covered by ground truth (as the organisers' hidden GT must be).

Usage: make_testset.py <imu.csv> <gt.csv> <out_dir> <name>
"""
import os, sys, subprocess, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
HDR_EUROC = "#timestamp [ns],w_RS_S_x [rad s^-1],w_RS_S_y [rad s^-1],w_RS_S_z [rad s^-1],a_RS_S_x [m s^-2],a_RS_S_y [m s^-2],a_RS_S_z [m s^-2]"
HDR_SCRIPT = "#timestamp [ns],a_x,a_y,a_z,w_x,w_y,w_z"


def load(path):
    d = np.loadtxt(path, delimiter=",", comments="#", dtype=np.float64)
    ts = np.loadtxt(path, delimiter=",", comments="#", usecols=0, dtype=np.int64)
    return ts, d[:, 1:]


def write(path, hdr, ts, vals):
    with open(path, "w") as f:
        f.write(hdr + "\n")
        for t, v in zip(ts, vals):
            f.write("%d,%s\n" % (t, ",".join(repr(float(x)) for x in v)))


def degrade(inp, out):
    subprocess.run([sys.executable, os.path.join(HERE, "degrade_imu.py"), inp, out,
                    "--meta", out + ".meta.json"], check=True, stdout=subprocess.DEVNULL)


def main():
    imu, gt, out_dir, name = sys.argv[1:5]
    os.makedirs(out_dir, exist_ok=True)
    ts, v = load(imu)
    gts = np.loadtxt(gt, delimiter=",", comments="#", usecols=0, dtype=np.int64)
    keep = (ts >= gts[0]) & (ts <= gts[-1])
    ts, v = ts[keep], v[keep]
    gyr, acc = v[:, 0:3], v[:, 3:6]
    with tempfile.TemporaryDirectory() as td:
        # H1: correct column semantics
        a = os.path.join(td, "in_h1.csv"); b = os.path.join(td, "out_h1.csv")
        write(a, HDR_SCRIPT, ts, np.hstack([acc, gyr]))
        degrade(a, b)
        d = np.loadtxt(b, delimiter=",", comments="#"); dts = np.loadtxt(b, delimiter=",", comments="#", usecols=0, dtype=np.int64)
        write(os.path.join(out_dir, name + "_H1.csv"), HDR_EUROC, dts, np.hstack([d[:, 4:7], d[:, 1:4]]))
        os.replace(b + ".meta.json", os.path.join(out_dir, name + "_H1.meta.json"))
        # H2: naive (EuRoC file straight through the script)
        a = os.path.join(td, "in_h2.csv"); b = os.path.join(out_dir, name + "_H2.csv")
        write(a, HDR_EUROC, ts, np.hstack([gyr, acc]))
        degrade(a, b)
        os.replace(b + ".meta.json", os.path.join(out_dir, name + "_H2.meta.json"))
    print("wrote", name)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Score an estimated_trajectory.txt against EuRoC ground truth, mirroring the
organisers' stated protocol: evo, SE(3) Umeyama alignment (no scale), ATE RMSE,
RPE. Adds the three tier views from the brief (approximations: the exact
waypoint set is hidden):
  waypoints  - aligned position error at GT samples every 10 s
  blind5     - error over the final 5 s of the input (IMU failure window)
  dropout    - error over the 2 s after each input gap > 50 ms

Usage: score.py <gt.csv> <estimated_trajectory.txt> [<input_imu.csv>] [--json]
"""
import sys, json, copy
import numpy as np
from evo.tools import file_interface
from evo.core import sync, metrics
from evo.core.trajectory import PoseTrajectory3D


def load_est(path):
    d = np.loadtxt(path, comments="#")
    t = d[:, 0]
    _, idx = np.unique(t, return_index=True)  # duplicate timestamps -> keep first
    d = d[np.sort(idx)]
    return PoseTrajectory3D(positions_xyz=d[:, 1:4],
                            orientations_quat_wxyz=d[:, [7, 4, 5, 6]], timestamps=d[:, 0])


def score(gt_path, est_path, imu_path=None):
    gt = file_interface.read_euroc_csv_trajectory(gt_path)
    est = load_est(est_path)
    g, e = sync.associate_trajectories(gt, est, max_diff=0.003)
    e_al = copy.deepcopy(e)
    e_al.align(g, correct_scale=False)
    err = np.linalg.norm(e_al.positions_xyz - g.positions_xyz, axis=1)
    t = g.timestamps
    out = {"n": int(len(t)), "ate_rmse": float(np.sqrt(np.mean(err ** 2))),
           "ate_max": float(err.max())}
    # RPE translation, delta 1 s
    rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=200,
                      delta_unit=metrics.Unit.frames, all_pairs=False)
    rpe.process_data((g, e))
    out["rpe_trans_1s"] = float(rpe.get_statistic(metrics.StatisticsType.rmse))
    rper = metrics.RPE(metrics.PoseRelation.rotation_angle_deg, delta=200,
                       delta_unit=metrics.Unit.frames, all_pairs=False)
    rper.process_data((g, e))
    out["rpe_rot_deg_1s"] = float(rper.get_statistic(metrics.StatisticsType.rmse))
    ape_r = metrics.APE(metrics.PoseRelation.rotation_angle_deg)
    ape_r.process_data((g, e_al))
    out["ate_rot_deg"] = float(ape_r.get_statistic(metrics.StatisticsType.rmse))
    # tiers
    wp = np.arange(t[0] + 10.0, t[-1] - 5.0, 10.0)
    wi = np.clip(np.searchsorted(t, wp), 0, len(t) - 1)
    out["waypoint_rmse"] = float(np.sqrt(np.mean(err[wi] ** 2)))
    if imu_path:
        its = np.loadtxt(imu_path, delimiter=",", comments="#", usecols=0, dtype=np.int64) * 1e-9
        tb = its[-1] - 5.0
        m = t >= tb
        out["blind5_rmse"] = float(np.sqrt(np.mean(err[m] ** 2))) if m.any() else None
        # end-point error of the blind segment (the "strike")
        out["blind5_final"] = float(err[m][-1]) if m.any() else None
        gaps = np.flatnonzero(np.diff(its) > 0.05)
        mask = np.zeros_like(t, bool)
        for k in gaps:
            mask |= (t >= its[k]) & (t <= its[k + 1] + 2.0)
        out["dropout_rmse"] = float(np.sqrt(np.mean(err[mask] ** 2))) if mask.any() else None
        out["n_gaps"] = int(len(gaps))
    # reference: the error of a constant (non-moving) estimate after alignment
    out["const_baseline_rmse"] = float(np.sqrt(np.mean(np.sum((g.positions_xyz - g.positions_xyz.mean(0)) ** 2, 1))))
    return out


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    r = score(*a)
    if "--json" in sys.argv:
        print(json.dumps(r))
    else:
        for k, v in r.items():
            print("%-20s %s" % (k, ("%.4f" % v) if isinstance(v, float) else v))

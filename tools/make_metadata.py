"""Run main.py on an input and write metadata.json with *measured* resource usage.
Usage: make_metadata.py <imu_input> <estimated_trajectory.txt> <metadata.json>
Runtime is measured in a clean run (no tracer); peak heap in a separate tracemalloc run.
"""
import sys, os, json, time, gc, platform, tracemalloc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import numpy as np
import main as M

inp, out, meta = sys.argv[1:4]
# warm-up import paths (numpy lazy modules) so they are not attributed to the algorithm
M.parse_imu(inp)
gc.collect()
t0 = time.process_time(); w0 = time.perf_counter()
info = M.run(inp, out)
cpu = time.process_time() - t0; wall = time.perf_counter() - w0
gc.collect(); tracemalloc.start()
M.run(inp, os.devnull if os.name != 'nt' else 'NUL')
peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
ts, _, _ = M.parse_imu(inp)
dur = float((ts.max() - ts.min()) * 1e-9)
md = {
    "team": "SRMIST_vortexxx",
    "track": "Track 03 - Path Finder: Trajectory Estimation Under Sensor Degradation",
    "entrypoint": "python src/main.py <imu0/data.csv | folder | zip> estimated_trajectory.txt",
    "input_rows": info["rows"], "unique_timestamps": info["unique"], "imu_failure_rows": info["dead"],
    "sequence_duration_s": round(dur, 3),
    "detected_platform": info["platform"],
    "runtime": {"cpu_s": round(cpu, 4), "wall_s": round(wall, 4),
                "ms_per_1s_of_imu": round(1000 * cpu / dur, 3), "budget_ms_per_1s": 20.0},
    "memory": {"peak_heap_mb_tracemalloc": round(peak / 1e6, 3), "budget_mb": 8.0,
               "measured": "algorithm heap via tracemalloc (interpreter RSS excluded, per FAQ)"},
    "threads": 1, "network": False, "gpu": False,
    "dependencies": {"python": platform.python_version(), "numpy": np.__version__},
    "machine": {"system": platform.system(), "processor": platform.processor() or platform.machine()},
}
json.dump(md, open(meta, 'w'), indent=2)
print(json.dumps(md, indent=2))

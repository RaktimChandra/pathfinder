# AI disclosure

Team SRMIST_vortexxx used an AI assistant, **Anthropic's Claude (Opus 5.5)**, throughout this project. We disclose what it did so judges can weigh the work accordingly.

## What the AI assistant did

| Area | AI contribution |
|---|---|
| Research | Read the track brief, FAQ and the official `degrade_imu.py`; surveyed IMU dead-reckoning methods (rotor-drag models, complementary filters, Kalman/RTS smoothing). |
| Code | Wrote the estimator (`src/main.py`) and the evaluation tools in `tools/`, and debugged them against the public datasets. |
| Evaluation | Ran the experiments: blind tests, ablations, leave-one-sequence-out cross-validation, stress tests, runtime and memory measurement. |
| Materials | Generated the figures, filled the official deck template, rendered the captioned demo video, and drafted the README and the technical report. |

## What the team did

- Chose the track and the overall direction, and set the requirements (accuracy, honesty, resource budgets).
- Decided which approaches to keep, reviewed the results, and asked for the extra validation that is reported here.
- Ran the code on our own machine (the Windows laptop results in the README) and provided the downloaded datasets.
- Own the submission and are responsible for its content.

## What was not done

- **No AI model is part of the solution itself.** The estimator is classical signal processing and estimation (complementary filter, Kalman filter, RTS smoother) in NumPy. It has no learned weights and no network access.
- **No test data was fabricated.** Every number in the README comes from running the code on public datasets (EuRoC MAV, TUM-VI), degraded with the organisers' script. The scripts in `tools/` reproduce all of them.
- **Choices made after seeing data are disclosed.** The README marks which results were blind and which were not, and reports the first blind scores, including one blind test that failed.

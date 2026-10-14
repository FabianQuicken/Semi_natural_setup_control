# Independent recorder with frame-loss diagnostics

All new code is in this folder. It neither imports nor changes the original scripts.
Run one process per experiment module, as before. Do not run the old and new
recorders against the same cameras simultaneously.

## Setup and launch

Use a Python environment with the Basler pylon runtime installed, then:

```powershell
python -m pip install -r optimized_recording/requirements.txt
```

The original files disagree about top1: `variables.py` uses `40439818`, while
`run_single_module.py` lists `40439817`. Confirm the physical serial in pylon Viewer.
The example below uses the mapping in `variables.py`; replace it if necessary.
Run these in two terminals, from the repository root:

```powershell
python optimized_recording/run_single_module.py --top-serial 40439818 --side-serial 40357253 --label module1 --fps 30
python optimized_recording/run_single_module.py --top-serial 40405188 --side-serial 40405187 --label module2 --fps 30
```

Defaults: Mono8, 1920x1080, 4000 microseconds exposure, 30 FPS camera acquisition
and video playback, motion-triggered recording, five seconds without motion to
stop a clip, ten-minute splits. Trigger and automatic exposure are explicitly
disabled. Unsupported camera settings fail visibly; there is no silent fallback.
These settings stay on the camera for its current session and are not saved to
a camera user-set. Confirm your desired settings before switching recorders.

Use `--mode continuous --duration 120` for an initial two-minute measurement.
Add `--preview` for a 5 FPS preview (`q` stops, `r` records for at least 30 seconds).
Without preview, stop with Ctrl+C. Queued frames drain before files close.
The output directory is printed at launch and defaults to `optimized_recording/recordings`.
Use `--output D:\recordings` to select another disk.

## What changed and why

- Each camera has an acquisition thread and a separate writer thread. Compression,
  file I/O, and grayscale-to-BGR conversion run outside acquisition.
- `GrabStrategy_OneByOne` retains ordered SDK results instead of intentionally
  replacing older frames. Images are copied before releasing SDK buffers.
- A bounded queue holds 64 raw Mono8 frames per camera. At Full HD, both queues
  together use up to about 253 MiB, plus SDK buffers and encoder overhead.
  A full queue counts the rejected frame and stops both cameras, then drains accepted
  frames. Increasing buffers only absorbs bursts; it cannot fix sustained overload.
- Motion detection reuses consecutive captured top-camera frames. It counts changed
  pixels rather than summing a large array of 0/255 values. Default thresholds retain
  the original score units. `--motion-scale 2` reduces processing but changes detection
  sensitivity: recalibrate on representative footage before using it in an experiment.
- Motion timeout and clip splitting use monotonic elapsed time, not frame counts.
  Splitting does not stop acquisition or wait to rediscover motion.
- Preview is disabled by default and refreshes independently. OpenCV uses one internal
  processing thread to reduce contention when running two module processes.
- MJPG is the default codec to try for this pipeline; it is not a measured guarantee
  of better performance. `--codec XVID` permits comparison with the original codec.
  MJPG can produce larger files, so watch disk capacity and sustained throughput.
- Writers are checked on opening and explicitly released. Exceptions stop the module
  and are recorded rather than allowing stale frames to be reused.

The legacy FPS prompt does not update the `fps` imported from `variables.py` by
the initialization and recording modules. The new `--fps` sets both acquisition
and video FPS, but exposure, bus bandwidth, and hardware can still limit actual FPS.

## Reading the diagnostics

`session.json` contains per-camera acquisition and writer summaries:

| Field | Meaning |
|---|---|
| `received` / `host_observed_fps` | Successful grabs and observed retrieval cadence, including idle observation |
| `block_id_gap_frames` | Missing IDs between successful grabs; acquisition/transport/SDK loss evidence, not encoder loss |
| `block_id_discontinuities` | Duplicate, reset, or unconfigured wrap; investigate rather than interpreting as a huge loss |
| `missing_block_ids` | ID unavailable; zero gaps cannot establish completeness |
| `sdk_skipped` | SDK-reported skipped images; may overlap ID gaps, so do not add them together |
| `host_cadence_warnings` | Retrieval interval >1.5 frame periods; timing warning, not proof of a missing frame |
| `selected` / `enqueued` / `queue_dropped` | Recording-selected frames, admitted frames, and explicit queue losses |
| `queue_high_water` / `max_write_ms` | Buffer pressure and worst observed conversion/write duration |
| `write_calls_completed` | Writes that returned without failure; **not proof of encoded output** |
| `enqueued_without_completed_write` | Accepted frames without a completed write, e.g. writer failure |
| `errors`, `grab_failures`, `timeouts` | Explicit failures; stop and investigate |

`top_frames.csv` and `side_frames.csv` log each completed write with its clip-local
zero-based video index, capture sequence, block ID, raw camera timestamp ticks,
host monotonic timestamp, preceding ID gap, SDK skip count, and write duration.
Recording selection excludes idle frames intentionally. Acquisition counters cover
the whole session; CSV rows cover completed recording writes only. Queue-rejected
frames are counted in the summary, not added as successful CSV rows.

Camera ticks are device-specific: they are not assumed to be nanoseconds and are
not compared across cameras. Host timestamps mark retrieval, not exposure. The
shared motion gate is evaluated by each capture thread, so clip edges can differ
by a frame and this does not provide hardware synchronization or pre-trigger video.

For a confirmed legacy GigE counter ranging from 1 through 65535, pass
`--block-id-modulus 65535`. Leave this unset for extended IDs/USB or unknown devices.
No ID gaps can be observed before the first or after the last successful grab.
A camera producing too few frames without incrementing IDs for missed exposures
will not necessarily show ID gaps; compare measured cadence against the request.

### Verify saved videos after both modules stop

```powershell
python optimized_recording/verify_videos.py "optimized_recording/recordings/SESSION_FOLDER"
```

This fully decodes every video and compares its decoded count against completed
write calls, creating `verification.json`. It does not trust AVI FPS or container
frame-count metadata. Missing, unreadable, short, or extra-frame output fails the
count check. No clips produces an unverified/false result. `--verify` runs the same
check automatically on exit when clips exist, but avoid doing this while another
module is still recording because decoding competes for CPU and disk bandwidth.

Check **both** reports: decoded counts can match even when acquisition or queue
loss occurred. A passing count check also does not prove pixel integrity or rule
out substituted/duplicated images. The recorder does not pad or duplicate frames.
AVI remains constant-FPS: gaps shorten apparent playback time. Use the CSV timing
for actual capture cadence rather than assuming playback time equals elapsed time.

The live console shows queue depth, completed writes, and explicit queue losses
every five seconds. Summaries finalize on graceful exit; abrupt termination or
power loss may leave unfinished videos/CSV and `session.json` marked `recording`.
Do not treat such a session as verified. An indefinitely blocked storage driver
can also prevent queue draining; Python cannot safely interrupt a native write.

## Hardware-free checks

```powershell
python -m unittest discover -s optimized_recording -p "test_*.py" -v
python optimized_recording/run_single_module.py --simulate --mode continuous --duration 3 --width 320 --height 240 --split-seconds 1 --verify
```

Tests cover sequence gaps and rollover, motion gating, explicit overflow, failed
writer opening, SDK buffer ownership, real MJPG output, clip splitting, full decode
counts, pixel ordering, and missing-file detection. Simulation needs NumPy and
OpenCV only. It does not establish achievable performance on your cameras.

Start with a short continuous run on both real modules concurrently. Compare
frame rates, ID gaps, queue high-water marks, and decoded counts. Repeat at the
full experiment duration before relying on the new recorder. Hardware performance
and pypylon API behavior have not been tested in the development environment.

References: [Basler buffer strategies](https://docs.baslerweb.com/pylonapi/cpp/pylon_programmingguide),
[Basler grab metadata](https://docs.baslerweb.com/pylonapi/cpp/class_pylon_1_1_c_grab_result_data),
[OpenCV VideoWriter](https://docs.opencv.org/4.x/dd/d9e/classcv_1_1VideoWriter.html).

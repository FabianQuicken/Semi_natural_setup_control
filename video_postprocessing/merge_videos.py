"""Merge recorder clips onto a continuous timeline, filling missing time with black."""

import argparse
import csv
import json
import math
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

import cv2
import numpy as np


def read_timeline(folder, camera):
    """Validate the metadata before starting an expensive encode."""
    try:
        session = json.loads((folder / 'session.json').read_text(encoding='utf-8-sig'))
    except (FileNotFoundError, json.JSONDecodeError):
        session = {}
    if not isinstance(session, dict):
        session = {}
    try:
        fps = float(session['configuration']['fps'])
    except (KeyError, TypeError, ValueError):
        fps = None
    if fps is not None and (not math.isfinite(fps) or fps <= 0):
        fps = None
    try:
        selected = next((c for c in session['cameras'] if c['name'] == camera), None)
        metadata = selected['writer']['clips']
        complete = isinstance(metadata, list) and all(
            isinstance(c, dict) and 'file' in c and 'write_calls_completed' in c
            for c in metadata)
    except (KeyError, TypeError):
        metadata, complete = [], False
    fallback = session.get('status') != 'stopped' or not complete or fps is None
    if fallback:
        warnings.warn('Incomplete session.json: using frame CSV and AVI files. '
                      'Run only after recording has ended.', RuntimeWarning)
    clips = {}
    for clip in ([] if fallback else metadata):
        filename = clip['file']
        if Path(filename).name != filename or not filename.startswith(camera + '_'):
            raise ValueError(f'Unexpected clip filename: {filename}')
        segment = int(Path(filename).stem.removeprefix(camera + '_'))
        if segment in clips:
            raise ValueError(f'Duplicate segment: {segment}')
        if not (folder / filename).is_file():
            raise ValueError(f'Missing video: {filename}')
        clips[segment] = clip
    counts = {}
    previous_time = None
    previous_segment = None
    first_time = None
    with (folder / f'{camera}_frames.csv').open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            segment = int(row['segment'])
            index = int(row['video_frame_index'])
            timestamp = int(row['host_monotonic_ns'])
            if fallback and segment not in clips:
                filename = f'{camera}_{segment:06d}.avi'
                if not (folder / filename).is_file():
                    raise ValueError(f'Missing video: {filename}')
                clips[segment] = dict(file=filename)
            if segment not in clips:
                raise ValueError(f'CSV references unknown segment {segment}')
            if segment != previous_segment and segment in counts:
                raise ValueError('CSV returns to an earlier segment')
            if index != counts.get(segment, 0):
                raise ValueError(f'Nonsequential video_frame_index in segment {segment}')
            if previous_time is not None and timestamp <= previous_time:
                raise ValueError('CSV host timestamps must be strictly increasing')
            if first_time is None:
                first_time = timestamp
            previous_time, previous_segment = timestamp, segment
            counts[segment] = index + 1
    if first_time is None:
        raise ValueError('No recorded frames in CSV')
    if set(counts) != set(clips):
        raise ValueError('CSV and session.json contain different segments')
    for segment, clip in clips.items():
        if fallback:
            clip['write_calls_completed'] = counts[segment]
        elif counts[segment] != clip['write_calls_completed']:
            raise ValueError(f'CSV/frame count mismatch for {clip["file"]}')
    if fps is None:
        for clip in clips.values():
            capture = cv2.VideoCapture(str(folder / clip['file']))
            try:
                candidate = capture.get(cv2.CAP_PROP_FPS)
            finally:
                capture.release()
            if not math.isfinite(candidate) or candidate <= 0:
                raise ValueError(f'Cannot determine FPS from {clip["file"]}')
            if fps is not None and not math.isclose(fps, candidate, rel_tol=1e-6):
                raise ValueError('Video segments have different FPS')
            fps = candidate
    return fps, clips, first_time


def filler_frame(shape):
    """Default filler when no positively classified segment end is available."""
    return np.zeros(shape, dtype=np.uint8)


def prediction_points(data, threshold):
    """Read single/multi-animal DLC columns without assuming individual names."""
    if len(data) != 1 or 'coords' not in data.columns.names:
        raise ValueError('Expected a DLC H5 table with exactly one frame and coords columns')
    axis = data.columns.names.index('coords')
    points = []
    likelihoods = 0
    for column in data.columns:
        if column[axis] != 'likelihood':
            continue
        likelihoods += 1
        value = float(data.iloc[0][column])
        if not np.isfinite(value) or value <= threshold:
            continue
        coordinates = []
        for coordinate in ('x', 'y'):
            key = list(column)
            key[axis] = coordinate
            coordinates.append(float(data.iloc[0][tuple(key)]))
        if not all(np.isfinite(coordinates)):
            raise ValueError('Confident DLC prediction has invalid coordinates')
        label = '/'.join(str(v) for i, v in enumerate(column) if i != axis)
        points.append((*coordinates, value, label))
    if not likelihoods:
        raise ValueError('DLC H5 has no likelihood columns')
    return points


class DLCFrameChecker:
    def __init__(self, config, threshold, root):
        self.config = Path(config).resolve()
        if not self.config.is_file():
            raise ValueError(f'DLC config does not exist: {self.config}')
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError('DLC likelihood must be between 0 and 1')
        try:
            import deeplabcut
            import pandas
        except ImportError as exc:
            raise RuntimeError('DLC mode requires DeepLabCut, pandas and PyTables in this environment') from exc
        self.dlc, self.pandas = deeplabcut, pandas
        self.threshold = threshold
        root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='run_', dir=root))
        for name in ('accepted', 'rejected', 'analysis'):
            (self.root / name).mkdir()

    def check(self, frame, filename, fps, fill_count):
        name = Path(filename).stem
        destination = self.root / 'analysis' / name
        destination.mkdir()
        video = destination / f'{name}_last.avi'
        height, width = frame.shape[:2]
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), fps, (width, height))
        try:
            if not writer.isOpened():
                raise RuntimeError(f'Cannot create DLC input: {video}')
            writer.write(frame)
        finally:
            writer.release()
        self.dlc.analyze_videos(str(self.config), [str(video)],
                                destfolder=str(destination), auto_track=True)
        results = list(destination.glob(f'{video.stem}*.h5'))
        if len(results) != 1:
            raise RuntimeError(f'Expected one DLC H5 result in {destination}, found {len(results)}')
        points = prediction_points(self.pandas.read_hdf(results[0]), self.threshold)
        accepted = bool(points)
        preview = frame.copy()
        for x, y, likelihood, label in points:
            position = (int(round(x)), int(round(y)))
            cv2.circle(preview, position, 4, (0, 255, 0), -1)
            cv2.putText(preview, f'{label}: {likelihood:.2f}', position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        path = self.root / ('accepted' if accepted else 'rejected') / f'{name}_last.png'
        if not cv2.imwrite(str(path), preview):
            raise RuntimeError(f'Cannot save DLC control image: {path}')
        (destination / 'decision.json').write_text(json.dumps(dict(
            source=filename, config=str(self.config), threshold=self.threshold,
            accepted=accepted, gap_frames=fill_count,
            filled_frames=fill_count if accepted else 0,
            predictions=points), indent=2), encoding='utf-8')
        return accepted


def merge(folder, camera, output=None, ffmpeg='ffmpeg', crf=18,
          dlc_config=None, dlc_likelihood=0.6, dlc_control_dir=None):
    folder = Path(folder).resolve()
    output = Path(output).resolve() if output else folder / f'{camera}_merged.mp4'
    if output.suffix.lower() != '.mp4':
        raise ValueError('Output must have the .mp4 extension')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    executable = shutil.which(ffmpeg)
    if executable is None:
        raise ValueError('FFmpeg not found. Install it or specify --ffmpeg PATH.')
    fps, clips, origin = read_timeline(folder, camera)
    if not output.parent.is_dir():
        raise ValueError(f'Output directory does not exist: {output.parent}')
    checker = DLCFrameChecker(dlc_config, dlc_likelihood,
                              Path(dlc_control_dir).resolve() if dlc_control_dir else
                              folder / f'{camera}_dlc_control') if dlc_config else None
    # Keep RAM use bounded: stream the CSV and decode only one frame at a time.
    capture = None
    process = None
    written = recorded = black_count = delayed = 0
    held_count = 0
    last_frame = None
    current = None
    shape = None
    with tempfile.TemporaryDirectory(prefix='video_merge_', dir=output.parent) as temp:
        temporary = Path(temp) / 'merged.mp4'
        with (Path(temp) / 'ffmpeg.log').open('w+b') as log:
            try:
                with (folder / f'{camera}_frames.csv').open(newline='', encoding='utf-8-sig') as handle:
                    for row in csv.DictReader(handle):
                        segment = int(row['segment'])
                        target = math.floor((int(row['host_monotonic_ns']) - origin) * fps / 1e9 + 0.5)
                        missing = max(0, target - written)
                        hold = False
                        if segment != current:
                            if capture is not None:
                                if capture.read()[0]:
                                    raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
                                capture.release()
                                if checker is not None:
                                    hold = checker.check(last_frame, clips[current]['file'], fps, missing)
                            filename = clips[segment]['file']
                            print(f'Processing {filename}', flush=True)
                            capture = cv2.VideoCapture(str(folder / filename))
                            if not capture.isOpened():
                                raise ValueError(f'Cannot open {filename}')
                            current = segment
                        ok, frame = capture.read()
                        if not ok:
                            raise ValueError(f'Cannot decode {clips[segment]["file"]}, frame {row["video_frame_index"]}')
                        if shape is None:
                            shape = frame.shape
                            height, width = shape[:2]
                            if width % 2 or height % 2:
                                raise ValueError('H.264 output requires even image dimensions')
                            black = filler_frame(shape).tobytes()
                            process = subprocess.Popen([
                                executable, '-hide_banner', '-loglevel', 'error', '-nostdin',
                                '-f', 'rawvideo', '-pixel_format', 'bgr24', '-video_size',
                                f'{width}x{height}', '-framerate', str(fps), '-i', 'pipe:0',
                                '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', str(crf),
                                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary),
                            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
                        if frame.shape != shape:
                            raise ValueError('Image dimensions change between frames/segments')
                        target = math.floor((int(row['host_monotonic_ns']) - origin) * fps / 1e9 + 0.5)
                        # Host retrieval jitter can map two real frames to one slot.
                        # Preserve every real frame rather than discard image information.
                        delayed += target < written
                        missing = max(0, target - written)
                        for _ in range(missing):
                            process.stdin.write(last_frame.tobytes() if hold else black)
                        process.stdin.write(frame.tobytes())
                        held_count += missing if hold else 0
                        black_count += 0 if hold else missing
                        last_frame = frame
                        recorded += 1
                        written += missing + 1
                if capture.read()[0]:
                    raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
                if checker is not None:
                    checker.check(last_frame, clips[current]['file'], fps, 0)
                process.stdin.close()
                if process.wait() != 0:
                    raise RuntimeError('FFmpeg encoding failed')
            except (BrokenPipeError, RuntimeError) as exc:
                if process is not None:
                    process.kill()
                    process.wait()
                log.seek(0)
                raise RuntimeError(f'{exc}\n{log.read().decode(errors="replace")}') from exc
            finally:
                if capture is not None:
                    capture.release()
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    if not process.stdin.closed:
                        try:
                            process.stdin.close()
                        except OSError:
                            pass  # A terminated encoder may have closed its pipe already.
        # Publish only a successfully encoded result; never replace an existing file.
        with temporary.open('rb') as source, output.open('xb') as destination:
            shutil.copyfileobj(source, destination)
    result = dict(output=str(output), fps=fps, recorded_frames=recorded,
                  black_frames=black_count, held_frames=held_count, total_frames=written,
                  duration_seconds=written / fps, frames_shifted_by_timing_jitter=delayed)
    if checker is not None:
        result['dlc_control_dir'] = str(checker.root)
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Recording folder containing frame CSVs and AVI segments')
    parser.add_argument('camera', choices=('side', 'top'))
    parser.add_argument('--output', type=Path, help='Output MP4; default: CAMERA_merged.mp4 in recording folder')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable or full path')
    parser.add_argument('--dlc-config', type=Path, help='DLC config.yaml; enables segment-end analysis')
    parser.add_argument('--dlc-likelihood', type=float, default=0.6, help='Strict likelihood threshold (default: 0.6)')
    parser.add_argument('--dlc-control-dir', type=Path, help='Root for DLC inputs, results and control images')
    parser.add_argument('--crf', type=int, default=18, choices=range(0, 52), metavar='0..51',
                        help='H.264 quality: lower is better/larger; 18 by default (lossy)')
    args = parser.parse_args()
    try:
        merge(args.folder, args.camera, args.output, args.ffmpeg, args.crf,
              args.dlc_config, args.dlc_likelihood, args.dlc_control_dir)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()

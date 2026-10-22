"""Merge recorder clips onto a continuous timeline, with timestamped gap filling and boundary controls."""

import argparse
import csv
import hashlib
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


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def save_image(path, frame):
    if not cv2.imwrite(str(path), frame):
        raise OSError(f'Cannot save control image: {path}')


class DLCFrameChecker:
    """Presence inference without temporal tracking of one-frame clips.

    Import/model/inference errors are handled by the merge's boundary decision.
    Control-file IO errors remain fatal rather than silently losing the audit.
    """

    def __init__(self, config, threshold, root, shuffle=2):
        self.config = Path(config).resolve()
        self.threshold, self.root, self.shuffle = threshold, root, shuffle
        self.dlc = self.pandas = None
        self.initialization_error = None

    def check(self, frame, filename, fps, fill_count):
        destination = self.root / Path(filename).stem
        destination.mkdir(parents=True)
        video = destination / 'last.avi'
        height, width = frame.shape[:2]
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), fps, (width, height))
        try:
            if not writer.isOpened():
                raise OSError(f'Cannot create DLC input: {video}')
            writer.write(frame)
        finally:
            writer.release()
        # Catch only the optional inference step, not audit image/JSON writes.
        try:
            if self.initialization_error:
                raise RuntimeError(self.initialization_error)
            if self.dlc is None:
                try:
                    import deeplabcut
                    import pandas
                    self.dlc, self.pandas = deeplabcut, pandas
                except Exception as exc:
                    self.initialization_error = f'{type(exc).__name__}: {exc}'
                    raise
            self.dlc.analyze_videos(
                str(self.config), [str(video)], destfolder=str(destination),
                auto_track=False, save_as_df=True, batch_size=1, shuffle=self.shuffle)
            results = list(destination.glob('last*.h5'))
            if len(results) != 1:
                raise RuntimeError(f'Expected one DLC H5 result, found {len(results)}')
            points = prediction_points(self.pandas.read_hdf(results[0]), self.threshold)
            if any(not (0 <= x < width and 0 <= y < height) for x, y, _, _ in points):
                raise ValueError('DLC prediction outside image bounds')
            decision = dict(mode='hold' if points else 'black',
                            reason='dlc_mouse_detected' if points else 'dlc_no_confident_points',
                            predictions=points)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            warnings.warn(f'DLC failed for {filename}; filling black: {error}', RuntimeWarning)
            decision = dict(mode='black', reason='dlc_error', error=error, predictions=[])
        preview = frame.copy()
        for x, y, likelihood, label in decision['predictions']:
            position = (int(round(x)), int(round(y)))
            cv2.circle(preview, position, 4, (0, 255, 0), -1)
            cv2.putText(preview, f'{label}: {likelihood:.2f}', position,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        save_image(destination / 'prediction.png', preview)
        decision.update(config=str(self.config), threshold=self.threshold, shuffle=self.shuffle)
        write_json(destination / 'decision.json', decision)
        return decision


def load_decisions(path, folder, camera):
    document = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if 'decisions' in document:
        if Path(document['source_folder']).resolve() != folder or document['camera'] != camera:
            raise ValueError('Gap decisions belong to another recording/camera')
        with (folder / f'{camera}_frames.csv').open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != document['timeline_sha256']:
            raise ValueError('Frame CSV changed since gap classification')
        document = document['decisions']
    if not isinstance(document, dict) or any(v not in ('hold', 'black') for v in document.values()):
        raise ValueError('Gap decisions must map AVI filenames to hold or black')
    return document


def merge(folder, camera, output=None, ffmpeg='ffmpeg', crf=18,
          dlc_config=None, dlc_likelihood=0.6, dlc_control_dir=None,
          gap_decisions=None, destination=None, short_gap_seconds=0.1, dlc_shuffle=2):
    folder = Path(folder).resolve()
    if camera not in ('top', 'side'):
        raise ValueError('Camera must be top or side')
    if not math.isfinite(short_gap_seconds) or short_gap_seconds < 0:
        raise ValueError('Short-gap seconds must be finite and nonnegative')
    if not math.isfinite(dlc_likelihood) or not 0 <= dlc_likelihood <= 1:
        raise ValueError('DLC likelihood must be between 0 and 1')
    if dlc_shuffle < 1:
        raise ValueError('DLC shuffle must be positive')
    if dlc_config and gap_decisions:
        raise ValueError('Choose DLC inference or gap decisions, not both')
    destination = Path(destination).resolve() if destination else (
        Path(output).resolve().parent if output else folder / f'{camera}_merge')
    output = Path(output).resolve() if output else destination / f'{camera}_merged.mp4'
    if output.suffix.lower() != '.mp4' or not output.is_relative_to(destination):
        raise ValueError('Output must be an MP4 inside the destination directory')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    executable = shutil.which(ffmpeg)
    if executable is None:
        raise ValueError('FFmpeg not found. Install it or specify --ffmpeg PATH.')
    # Avoid orphaning the real encoder when killing a Chocolatey launcher.
    real_encoder = Path(executable).parent.parent / 'lib/ffmpeg/tools/ffmpeg/bin/ffmpeg.exe'
    if Path(executable).parent.name.lower() == 'bin' and real_encoder.is_file():
        executable = str(real_encoder)
    fps, clips, origin = read_timeline(folder, camera)
    decisions = load_decisions(gap_decisions, folder, camera) if gap_decisions else None
    if decisions is not None and any(clip['file'] not in decisions for clip in clips.values()):
        raise ValueError('Gap decisions must contain every source segment')
    controls = destination / 'control'
    dlc_root = Path(dlc_control_dir).resolve() if dlc_control_dir else controls / 'dlc'
    if not dlc_root.is_relative_to(controls):
        raise ValueError('DLC control directory must be inside destination/control')
    destination.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never reuse/overwrite controls from an earlier or interrupted run.
    controls.mkdir()
    checker = DLCFrameChecker(dlc_config, dlc_likelihood, dlc_root, dlc_shuffle) if dlc_config else None
    capture = process = last_frame = current = shape = segment_control = None
    segment_info = None
    written = recorded = black_count = held_count = dropped = dlc_errors = 0
    intra_held = intra_black = 0
    gaps_path = controls / 'gaps.jsonl'

    def finish_segment(next_filename, missing, next_timestamp):
        nonlocal dlc_errors
        save_image(segment_control / 'last.png', last_frame)
        if next_filename is None:
            decision = dict(mode='none', reason='end_of_recording')
        elif not missing:
            decision = dict(mode='none', reason='contiguous_segments')
        elif decisions is not None:
            decision = dict(mode=decisions[clips[current]['file']], reason='reviewed_decision')
        elif checker:
            decision = checker.check(last_frame, clips[current]['file'], fps, missing)
        else:
            decision = dict(mode='black', reason='no_presence_classifier')
        dlc_errors += decision['reason'] == 'dlc_error'
        boundary = dict(previous=clips[current]['file'], next=next_filename,
                        kind='between_fragments', output_start_frame=written,
                        fill_frames=missing, fill_seconds=missing / fps,
                        source_interval_seconds=(next_timestamp - segment_info['last_timestamp_ns']) / 1e9
                        if next_timestamp is not None else None, **decision)
        write_json(segment_control / 'decision.json', dict(**segment_info, following_gap=boundary))
        if next_filename is not None:
            gaps.write(json.dumps(boundary, allow_nan=False) + '\n')
            gaps.flush()
        return decision['mode'] == 'hold'

    write_json(destination / 'status.json', dict(status='running', source=str(folder), camera=camera))
    try:
        with tempfile.TemporaryDirectory(prefix='video_merge_', dir=destination) as temp:
            temporary = Path(temp) / 'merged.mp4'
            with (destination / 'ffmpeg.log').open('w+b') as log, gaps_path.open('x', encoding='utf-8') as gaps:
                try:
                    with (folder / f'{camera}_frames.csv').open(newline='', encoding='utf-8-sig') as handle:
                        for row in csv.DictReader(handle):
                            segment = int(row['segment'])
                            timestamp = int(row['host_monotonic_ns'])
                            target = math.floor((timestamp - origin) * fps / 1e9 + 0.5)
                            missing = max(0, target - written)
                            boundary = segment != current
                            hold = False
                            if boundary:
                                if capture is not None:
                                    if capture.read()[0]:
                                        raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
                                    capture.release()
                                    hold = finish_segment(clips[segment]['file'], missing, timestamp)
                                current = segment
                                filename = clips[segment]['file']
                                print(f'Processing {filename}', flush=True)
                                segment_control = controls / Path(filename).stem
                                segment_control.mkdir()
                                segment_info = dict(source=filename, first_timestamp_ns=timestamp,
                                                    last_timestamp_ns=timestamp, recorded_frames=0,
                                                    omitted_collisions=0, within_fragment_held_frames=0,
                                                    within_fragment_black_frames=0)
                                capture = cv2.VideoCapture(str(folder / filename))
                                if not capture.isOpened():
                                    raise ValueError(f'Cannot open {filename}')
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
                                    '-f', 'rawvideo', '-pixel_format', 'bgr24', '-video_size', f'{width}x{height}',
                                    '-framerate', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264',
                                    '-preset', 'fast', '-crf', str(crf), '-pix_fmt', 'yuv420p',
                                    '-movflags', '+faststart', str(temporary)],
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
                            if frame.shape != shape:
                                raise ValueError('Image dimensions change between frames/segments')
                            if boundary:
                                save_image(segment_control / 'first.png', frame)
                            recorded += 1
                            segment_info['recorded_frames'] += 1
                            segment_info['last_timestamp_ns'] = timestamp
                            if target < written:
                                dropped += 1
                                segment_info['omitted_collisions'] += 1
                                last_frame = frame
                                continue
                            if missing and not boundary:
                                hold = missing / fps <= short_gap_seconds + 1e-12
                                event = dict(kind='within_fragment', source=clips[segment]['file'],
                                             before_source_frame=int(row['video_frame_index']),
                                             output_start_frame=written, fill_frames=missing,
                                             fill_seconds=missing / fps, mode='hold' if hold else 'black',
                                             reason='short_timestamp_gap' if hold else 'long_timestamp_gap')
                                gaps.write(json.dumps(event) + '\n')
                                segment_info['within_fragment_held_frames' if hold else 'within_fragment_black_frames'] += missing
                                intra_held += missing if hold else 0
                                intra_black += 0 if hold else missing
                            if missing:
                                filler = last_frame.tobytes() if hold else black
                                for _ in range(missing):
                                    process.stdin.write(filler)
                            process.stdin.write(frame.tobytes())
                            held_count += missing if hold else 0
                            black_count += 0 if hold else missing
                            written += missing + 1
                            last_frame = frame
                    if capture.read()[0]:
                        raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
                    finish_segment(None, 0, None)
                    process.stdin.close()
                    if process.wait() != 0:
                        log.seek(0)
                        raise RuntimeError(f'FFmpeg encoding failed: {log.read().decode(errors="replace")}')
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
                                pass
            with temporary.open('rb') as source, output.open('xb') as target_file:
                shutil.copyfileobj(source, target_file)
    except Exception as exc:
        write_json(destination / 'status.json', dict(status='failed', error=f'{type(exc).__name__}: {exc}'))
        raise
    result = dict(output=str(output), destination=str(destination), control_dir=str(controls),
                  fps=fps, recorded_frames=recorded, black_frames=black_count, held_frames=held_count,
                  within_fragment_held_frames=intra_held, within_fragment_black_frames=intra_black,
                  short_gap_seconds=short_gap_seconds, total_frames=written, duration_seconds=written / fps,
                  frames_omitted_at_colliding_timestamps=dropped, dlc_errors=dlc_errors)
    if checker:
        result['dlc_control_dir'] = str(dlc_root)
    write_json(destination / 'summary.json', result)
    write_json(destination / 'status.json', dict(status='complete'))
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Recording folder containing frame CSV and AVI segments')
    parser.add_argument('camera', choices=('side', 'top'))
    parser.add_argument('--destination', type=Path, help='Results directory; default: RECORDING/CAMERA_merge')
    parser.add_argument('--output', type=Path, help='MP4 path inside destination; default: CAMERA_merged.mp4')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable or full path')
    parser.add_argument('--gap-decisions', type=Path, help='Reviewed black/hold JSON; replaces DLC inference')
    parser.add_argument('--dlc-config', type=Path, help='DLC config.yaml; enables presence inference')
    parser.add_argument('--dlc-shuffle', type=int, default=2, help='Trained shuffle (default: 2)')
    parser.add_argument('--dlc-likelihood', type=float, default=0.6, help='Strict likelihood threshold')
    parser.add_argument('--dlc-control-dir', type=Path, help='DLC results directory inside destination/control')
    parser.add_argument('--short-gap-seconds', type=float, default=0.1,
                        help='Repeat previous image for within-fragment missing time up to this length; 0 disables')
    parser.add_argument('--crf', type=int, default=18, choices=range(0, 52), metavar='0..51')
    args = parser.parse_args()
    try:
        merge(args.folder, args.camera, args.output, args.ffmpeg, args.crf,
              args.dlc_config, args.dlc_likelihood, args.dlc_control_dir,
              args.gap_decisions, args.destination, args.short_gap_seconds, args.dlc_shuffle)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()

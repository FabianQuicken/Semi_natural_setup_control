"""Merge recorder clips onto a continuous timeline, filling missing time with black."""

import argparse
import csv
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def read_timeline(folder, camera):
    """Validate the metadata before starting an expensive encode."""
    session = json.loads((folder / 'session.json').read_text(encoding='utf-8-sig'))
    if session.get('status') != 'stopped':
        raise ValueError('Session is not marked stopped; finish recording first.')
    fps = float(session['configuration']['fps'])
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid FPS in session.json')
    selected = next((c for c in session['cameras'] if c['name'] == camera), None)
    if selected is None:
        raise ValueError(f'Camera {camera!r} is absent from session.json')
    clips = {}
    for clip in selected['writer']['clips']:
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
        if counts[segment] != clip['write_calls_completed']:
            raise ValueError(f'CSV/frame count mismatch for {clip["file"]}')
    return fps, clips, first_time


def filler_frame(shape):
    """Extension point for future sleep detection; currently always black."""
    return np.zeros(shape, dtype=np.uint8)


def merge(folder, camera, output=None, ffmpeg='ffmpeg', crf=18):
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
    # Keep RAM use bounded: stream the CSV and decode only one frame at a time.
    capture = None
    process = None
    written = recorded = black_count = delayed = 0
    current = None
    shape = None
    with tempfile.TemporaryDirectory(prefix='video_merge_', dir=output.parent) as temp:
        temporary = Path(temp) / 'merged.mp4'
        with (Path(temp) / 'ffmpeg.log').open('w+b') as log:
            try:
                with (folder / f'{camera}_frames.csv').open(newline='', encoding='utf-8-sig') as handle:
                    for row in csv.DictReader(handle):
                        segment = int(row['segment'])
                        if segment != current:
                            if capture is not None:
                                if capture.read()[0]:
                                    raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
                                capture.release()
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
                            process.stdin.write(black)
                        process.stdin.write(frame.tobytes())
                        black_count += missing
                        recorded += 1
                        written += missing + 1
                if capture.read()[0]:
                    raise ValueError(f'Video has more frames than CSV: {clips[current]["file"]}')
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
                  black_frames=black_count, total_frames=written,
                  duration_seconds=written / fps, frames_shifted_by_timing_jitter=delayed)
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path, help='Recording folder containing session.json')
    parser.add_argument('camera', choices=('side', 'top'))
    parser.add_argument('--output', type=Path, help='Output MP4; default: CAMERA_merged.mp4 in recording folder')
    parser.add_argument('--ffmpeg', default='ffmpeg', help='FFmpeg executable or full path')
    parser.add_argument('--crf', type=int, default=18, choices=range(0, 52), metavar='0..51',
                        help='H.264 quality: lower is better/larger; 18 by default (lossy)')
    args = parser.parse_args()
    try:
        merge(args.folder, args.camera, args.output, args.ffmpeg, args.crf)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()

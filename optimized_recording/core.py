"""Acquisition-independent recording primitives. No imports from the legacy scripts."""
import csv
import json
import queue
import threading
import time
from pathlib import Path

import cv2


def save_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


class FrameTracker:
    """Block IDs identify gaps, while host cadence is only a timing warning."""
    def __init__(self, fps, modulus=None):
        self.fps, self.modulus = fps, modulus
        self.previous_id = self.previous_time = None
        self.first_time = None
        self.stats = dict(received=0, block_id_gap_frames=0, block_id_discontinuities=0,
                          missing_block_ids=0, sdk_skipped=0, host_cadence_warnings=0)

    def observe(self, block_id, now, skipped=0):
        gap = 0
        if block_id is None or block_id in (0, (1 << 64) - 1):
            self.stats['missing_block_ids'] += 1
            self.previous_id = None
        else:
            if self.previous_id is not None:
                delta = block_id - self.previous_id
                if delta < 0 and self.modulus:
                    delta += self.modulus
                if delta > 0:
                    gap = delta - 1
                    self.stats['block_id_gap_frames'] += gap
                else:
                    self.stats['block_id_discontinuities'] += 1
            self.previous_id = block_id
        if self.previous_time is not None and now - self.previous_time > 1.5 / self.fps:
            self.stats['host_cadence_warnings'] += 1
        if self.first_time is None:
            self.first_time = now
        self.previous_time = now
        self.stats['received'] += 1
        self.stats['sdk_skipped'] += skipped
        return gap

    def report(self):
        span = (self.previous_time or 0) - (self.first_time or 0)
        return {**self.stats, 'host_observed_fps':
                (self.stats['received'] - 1) / span if span > 0 else None}


class RecordingGate:
    """Shared top-camera motion gate; time based stop and continuous clip splitting."""
    def __init__(self, continuous=False, idle_seconds=5, split_seconds=600):
        self.continuous = continuous
        self.idle_seconds, self.split_seconds = idle_seconds, split_seconds
        self.lock = threading.Lock()
        self.until = 0
        self.started = None
        self.segment = 0

    def trigger(self, now, seconds=None):
        with self.lock:
            self.until = max(self.until, now + (self.idle_seconds if seconds is None else seconds))

    def select(self, now):
        with self.lock:
            if not self.continuous and now >= self.until:
                self.started = None
                return None
            if self.started is None or now - self.started >= self.split_seconds:
                self.segment += 1
                self.started = now
            return self.segment


class MotionDetector:
    def __init__(self, start_threshold=200000, continue_threshold=10000, scale=1):
        self.previous = None
        self.start_threshold, self.continue_threshold = start_threshold, continue_threshold
        self.scale = scale

    def update(self, frame, active):
        small = frame if self.scale == 1 else cv2.resize(
            frame, None, fx=1 / self.scale, fy=1 / self.scale, interpolation=cv2.INTER_AREA)
        moved = False
        if self.previous is not None:
            changed = cv2.compare(cv2.absdiff(self.previous, small), 20, cv2.CMP_GT)
            score = cv2.countNonZero(changed) * 255 * self.scale ** 2
            moved = score >= (self.continue_threshold if active else self.start_threshold)
        self.previous = small
        return moved


class VideoSink(threading.Thread):
    """One bounded queue and encoder per camera. Overflow stops the whole module."""
    def __init__(self, folder, name, fps, codec, capacity, stop):
        super().__init__(name=f'writer-{name}')
        self.folder, self.camera_name = Path(folder), name
        self.fps, self.codec, self.stop = fps, codec, stop
        self.queue = queue.Queue(capacity)
        self.finished = threading.Event()
        self.stats = dict(selected=0, enqueued=0, queue_dropped=0, queue_high_water=0,
                          write_calls_completed=0, max_write_ms=0, errors=[])
        self.clips = []

    def submit(self, packet):
        self.stats['selected'] += 1
        try:
            self.queue.put_nowait(packet)
            self.stats['enqueued'] += 1
            self.stats['queue_high_water'] = max(self.stats['queue_high_water'], self.queue.qsize())
        except queue.Full:
            self.stats['queue_dropped'] += 1
            self.stop.set()

    def run(self):
        writer = None
        current = None
        try:
            with (self.folder / f'{self.camera_name}_frames.csv').open('w', newline='') as handle:
                log = csv.writer(handle)
                log.writerow(['segment', 'video_frame_index', 'capture_sequence', 'block_id',
                              'camera_timestamp_ticks', 'host_monotonic_ns', 'block_gap_before',
                              'sdk_skipped_before', 'write_ms'])
                while not self.finished.is_set() or not self.queue.empty():
                    try:
                        packet = self.queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    segment, sequence, block, ticks, host, gap, skipped, frame = packet
                    if segment != current:
                        if writer is not None:
                            writer.release()
                        filename = f'{self.camera_name}_{segment:06d}.avi'
                        height, width = frame.shape
                        writer = cv2.VideoWriter(str(self.folder / filename),
                                                 cv2.VideoWriter_fourcc(*self.codec),
                                                 self.fps, (width, height), True)
                        if not writer.isOpened():
                            raise RuntimeError(f'Cannot open video writer: {filename} ({self.codec})')
                        self.clips.append(dict(file=filename, write_calls_completed=0,
                                               first_host_ns=host, last_host_ns=host))
                        current = segment
                    started = time.perf_counter()
                    result = writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
                    if result is False:
                        raise RuntimeError('VideoWriter.write reported failure')
                    elapsed = (time.perf_counter() - started) * 1000
                    clip = self.clips[-1]
                    log.writerow([segment, clip['write_calls_completed'], sequence, block, ticks,
                                  host, gap, skipped, round(elapsed, 3)])
                    clip['write_calls_completed'] += 1
                    clip['last_host_ns'] = host
                    self.stats['write_calls_completed'] += 1
                    self.stats['max_write_ms'] = max(self.stats['max_write_ms'], elapsed)
        except Exception as exc:
            self.stats['errors'].append(repr(exc))
            self.stop.set()
        finally:
            if writer is not None:
                try:
                    writer.release()
                except Exception as exc:
                    self.stats['errors'].append(f'Writer cleanup: {exc!r}')
                    self.stop.set()

    def report(self):
        return {**self.stats, 'enqueued_without_completed_write':
                self.stats['enqueued'] - self.stats['write_calls_completed'], 'clips': self.clips}


def verify_session(folder):
    """Decode every frame after acquisition stops; never trust container FPS/count alone."""
    folder = Path(folder)
    session = json.loads((folder / 'session.json').read_text(encoding='utf-8'))
    checks = []
    for camera in session['cameras']:
        for clip in camera['writer']['clips']:
            capture = cv2.VideoCapture(str(folder / clip['file']))
            opened = capture.isOpened()
            count = 0
            try:
                while True:
                    ok, _ = capture.read()
                    if not ok:
                        break
                    count += 1
            finally:
                capture.release()
            expected = clip['write_calls_completed']
            checks.append(dict(file=clip['file'], expected=expected, decoded=count,
                               matched=opened and count == expected))
    result = dict(clips=checks, all_video_counts_match=bool(checks) and all(c['matched'] for c in checks),
                  note='Count agreement does not prove image integrity or absence of camera-side losses.')
    save_json(folder / 'verification.json', result)
    return result

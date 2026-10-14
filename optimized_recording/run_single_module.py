"""Independent recorder: python optimized_recording/run_single_module.py --help."""
import argparse
from datetime import datetime
import math
from pathlib import Path
import threading
import time

import cv2
import numpy as np

from core import FrameTracker, MotionDetector, RecordingGate, VideoSink, save_json, verify_session


def optional_value(result, method):
    try:
        return int(getattr(result, method)())
    except (AttributeError, RuntimeError):
        return None


def open_cameras(args):
    from pypylon import pylon
    factory = pylon.TlFactory.GetInstance()
    devices = {d.GetSerialNumber(): d for d in factory.EnumerateDevices()}
    cameras = []
    try:
        for serial in (args.top_serial, args.side_serial):
            if serial not in devices:
                raise RuntimeError(f'Camera {serial} not found; available: {list(devices)}')
            camera = pylon.InstantCamera(factory.CreateDevice(devices[serial]))
            cameras.append(camera)
            camera.Open()
            camera.Width.SetValue(args.width)
            camera.Height.SetValue(args.height)
            camera.PixelFormat.SetValue('Mono8')
            camera.TriggerMode.SetValue('Off')
            camera.ExposureAuto.SetValue('Off')
            camera.ExposureTime.SetValue(args.exposure_us)
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRate.SetValue(args.fps)
            camera.MaxNumBuffer.SetValue(args.camera_buffers)
        return cameras, pylon
    except BaseException:
        for camera in cameras:
            if camera.IsOpen():
                camera.Close()
        raise


def capture_loop(index, camera, pylon, args, sink, gate, stop, report, preview):
    tracker = FrameTracker(args.fps, args.block_id_modulus)
    detector = MotionDetector(args.start_threshold, args.continue_threshold, args.motion_scale)
    errors = []
    failed = timeouts = 0
    sequence = 0
    first_ticks = last_ticks = None
    timestamp_discontinuities = 0
    next_frame = time.perf_counter()
    try:
        if camera is not None:
            camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
        while not stop.is_set():
            if camera is None:
                if stop.wait(max(0, next_frame - time.perf_counter())):
                    break
                next_frame += 1 / args.fps
                frame = np.full((args.height, args.width), sequence % 256, np.uint8)
                block, ticks, skipped = sequence + 1, time.perf_counter_ns(), 0
            else:
                result = camera.RetrieveResult(1000, pylon.TimeoutHandling_Return)
                if result is None:
                    timeouts += 1
                    raise RuntimeError('No camera frame received within 1000 ms')
                try:
                    if not result.GrabSucceeded():
                        failed += 1
                        raise RuntimeError(f'Grab failed: {result.GetErrorDescription()}')
                    block = optional_value(result, 'GetBlockID')
                    ticks = optional_value(result, 'GetTimeStamp')
                    skipped = optional_value(result, 'GetNumberOfSkippedImages') or 0
                    # Own the pixels before returning the SDK buffer to its pool.
                    frame = result.Array.copy()
                finally:
                    result.Release()
            host = time.perf_counter_ns()
            now = host / 1e9
            if ticks is not None:
                if first_ticks is None:
                    first_ticks = ticks
                if last_ticks is not None and ticks <= last_ticks:
                    timestamp_discontinuities += 1
                last_ticks = ticks
            gap = tracker.observe(block, now, skipped)
            sequence += 1
            if index == 0 and args.mode == 'motion':
                active = gate.select(now) is not None
                if detector.update(frame, active):
                    gate.trigger(now)
            segment = gate.select(now)
            if segment is not None:
                sink.submit((segment, sequence, block, ticks, host, gap, skipped, frame))
            # Only the latest preview reference is kept. Preview skips are intentional.
            preview[index] = frame
    except Exception as exc:
        errors.append(repr(exc))
        stop.set()
    finally:
        if camera is not None:
            try:
                if camera.IsGrabbing():
                    camera.StopGrabbing()
                camera.Close()
            except Exception as exc:
                errors.append(f'Camera cleanup: {exc!r}')
                stop.set()
        report.update(tracker.report(), grab_failures=failed, timeouts=timeouts, errors=errors,
                      first_camera_timestamp_ticks=first_ticks, last_camera_timestamp_ticks=last_ticks,
                      camera_timestamp_discontinuities=timestamp_discontinuities)
        sink.finished.set()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--top-serial', help='Explicit because legacy top1 serial numbers disagree')
    parser.add_argument('--side-serial')
    parser.add_argument('--label', default='experiment')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'recordings')
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--exposure-us', type=float, default=4000)
    parser.add_argument('--codec', default='MJPG', help='FourCC; compare MJPG and XVID on your machine')
    parser.add_argument('--queue-frames', type=int, default=64)
    parser.add_argument('--camera-buffers', type=int, default=32)
    parser.add_argument('--mode', choices=['motion', 'continuous'], default='motion')
    parser.add_argument('--idle-seconds', type=float, default=5)
    parser.add_argument('--split-seconds', type=float, default=600)
    parser.add_argument('--duration', type=float, default=0, help='Session seconds; 0 runs until Ctrl+C/q')
    parser.add_argument('--start-threshold', type=float, default=200000)
    parser.add_argument('--continue-threshold', type=float, default=10000)
    parser.add_argument('--motion-scale', type=int, default=1, help='Downsample factor; recalibrate thresholds if >1')
    parser.add_argument('--block-id-modulus', type=int, choices=[65535], help='Only for confirmed legacy GigE IDs 1..65535')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--preview-fps', type=float, default=5)
    parser.add_argument('--verify', action='store_true', help='Fully decode files after capture stops')
    parser.add_argument('--simulate', action='store_true', help='Synthetic cameras, no pypylon needed')
    args = parser.parse_args()
    for key in ('fps', 'width', 'height', 'exposure_us', 'queue_frames', 'camera_buffers',
                'idle_seconds', 'split_seconds', 'motion_scale', 'preview_fps'):
        value = getattr(args, key)
        if not math.isfinite(value) or value <= 0:
            parser.error(f'--{key.replace("_", "-")} must be positive and finite')
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error('--duration must be finite and nonnegative')
    for value in (args.start_threshold, args.continue_threshold):
        if not math.isfinite(value) or value < 0:
            parser.error('Motion thresholds must be finite and nonnegative')
    if args.width % 2 or args.height % 2:
        parser.error('Use even width and height to prevent codec cropping')
    if args.motion_scale > min(args.width, args.height):
        parser.error('--motion-scale exceeds image dimensions')
    if len(args.codec) != 4:
        parser.error('--codec must have four characters')
    if not args.simulate and (not args.top_serial or not args.side_serial or args.top_serial == args.side_serial):
        parser.error('Provide two distinct --top-serial and --side-serial values')
    return args


def main():
    args = parse_args()
    cv2.setNumThreads(1)  # Avoid oversubscription when running two module processes.
    label = ''.join(c if c.isalnum() or c in '-_' else '_' for c in args.label)[:80]
    folder = args.output / f'{datetime.now():%Y%m%d_%H%M%S_%f}_{label}'
    folder.mkdir(parents=True, exist_ok=False)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    session = dict(status='starting', configuration=config, cameras=[])
    save_json(folder / 'session.json', session)
    print(f'Output: {folder.resolve()}', flush=True)
    print(f'Queue image budget: {2 * args.queue_frames * args.width * args.height / 2**20:.1f} MiB '
          '(plus SDK buffers, preview, and encoder memory)', flush=True)
    stop = threading.Event()
    gate = RecordingGate(args.mode == 'continuous', args.idle_seconds, args.split_seconds)
    preview = [None, None]
    sinks, workers, cameras = [], [], []
    origin = time.perf_counter()
    run_errors = []
    try:
        cameras, pylon = ([None, None], None) if args.simulate else open_cameras(args)
        for index, name in enumerate(('top', 'side')):
            report = dict(name=name, serial=(args.top_serial, args.side_serial)[index], acquisition={})
            session['cameras'].append(report)
            sink = VideoSink(folder, name, args.fps, args.codec, args.queue_frames, stop)
            sink.start()
            sinks.append(sink)
            worker = threading.Thread(target=capture_loop, name=f'capture-{name}', args=(
                index, cameras[index], pylon, args, sink, gate, stop, report['acquisition'], preview))
            worker.start()
            workers.append(worker)
        session['status'] = 'recording'
        save_json(folder / 'session.json', session)
        last_status = 0
        while not stop.wait(1 / args.preview_fps if args.preview else 0.1):
            now = time.perf_counter()
            if args.duration and now - origin >= args.duration:
                break
            if args.preview:
                for name, frame in zip(('top', 'side'), preview):
                    if frame is not None:
                        cv2.imshow(name, cv2.resize(frame, (720, 405)))
                key = cv2.waitKey(1) & 0xff
                if key == ord('q'):
                    break
                if key == ord('r'):
                    gate.trigger(now, 30)
            if now - last_status >= 5:
                print(' | '.join(f'{s.camera_name}: queued={s.queue.qsize()} '
                                 f'written={s.stats["write_calls_completed"]} '
                                 f'dropped={s.stats["queue_dropped"]}' for s in sinks), flush=True)
                last_status = now
    except KeyboardInterrupt:
        print('Stopping acquisition and draining writer queues...', flush=True)
    except Exception as exc:
        run_errors.append(repr(exc))
    finally:
        stop.set()
        for worker in workers:
            worker.join()
        for sink in sinks:
            sink.finished.set()
            sink.join()
        for camera in cameras:
            try:
                if camera is not None and camera.IsOpen():
                    camera.Close()
            except Exception as exc:
                run_errors.append(f'Camera cleanup: {exc!r}')
        if args.preview:
            cv2.destroyAllWindows()
        for report, sink in zip(session['cameras'], sinks):
            report['writer'] = sink.report()
        session['errors'] = run_errors
        session['status'] = 'stopped'
        session['elapsed_seconds'] = time.perf_counter() - origin
        session['has_loss_or_errors'] = bool(run_errors) or any(
            c['acquisition'].get('errors') or c['acquisition'].get('block_id_gap_frames') or
            c['acquisition'].get('block_id_discontinuities') or
            c['acquisition'].get('camera_timestamp_discontinuities') or
            c['acquisition'].get('sdk_skipped') or c['writer']['errors'] or
            c['writer']['queue_dropped'] or c['writer']['enqueued_without_completed_write']
            for c in session['cameras'])
        save_json(folder / 'session.json', session)
    if args.verify and not run_errors and any(s.clips for s in sinks):
        result = verify_session(folder)
        if not result['all_video_counts_match']:
            session['has_loss_or_errors'] = True
            save_json(folder / 'session.json', session)
    print(f'Finished. Loss/error detected: {session["has_loss_or_errors"]}. See {folder / "session.json"}')
    return 1 if session['has_loss_or_errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

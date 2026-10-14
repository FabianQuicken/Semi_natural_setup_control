import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from core import FrameTracker, MotionDetector, RecordingGate, VideoSink, save_json, verify_session
from run_single_module import capture_loop
from types import SimpleNamespace


class RecordingTests(unittest.TestCase):
    def test_block_gaps_wrap_missing_and_cadence(self):
        tracker = FrameTracker(30, 65535)
        for block, now in [(65534, 0), (65535, .03), (1, .06), (4, .2), (None, .23), (10, .26)]:
            tracker.observe(block, now)
        self.assertEqual(tracker.stats['block_id_gap_frames'], 2)
        self.assertEqual(tracker.stats['missing_block_ids'], 1)
        self.assertEqual(tracker.stats['host_cadence_warnings'], 1)
        unknown = FrameTracker(30)
        unknown.observe(100, 1)
        unknown.observe(1, 2)
        self.assertEqual(unknown.stats['block_id_discontinuities'], 1)
        self.assertEqual(unknown.stats['block_id_gap_frames'], 0)

    def test_motion_gate_idle_manual_and_split(self):
        gate = RecordingGate(idle_seconds=5, split_seconds=2)
        self.assertIsNone(gate.select(10))
        gate.trigger(10)
        self.assertEqual(gate.select(10), 1)
        self.assertEqual(gate.select(12), 2)
        self.assertIsNone(gate.select(15))
        gate.trigger(20, 30)
        self.assertEqual(gate.select(20), 3)
        gate.trigger(21)  # Motion must not shorten manual recording.
        self.assertIsNotNone(gate.select(49))
        self.assertIsNone(gate.select(50))

    def test_motion_threshold(self):
        detector = MotionDetector()
        black = np.zeros((64, 64), np.uint8)
        self.assertFalse(detector.update(black, False))
        self.assertFalse(detector.update(black, False))
        self.assertTrue(detector.update(black + 30, False))

    def test_overflow_stops_and_accounts(self):
        sink = VideoSink('.', 'fake', 30, 'MJPG', 1, threading.Event())
        sink.submit(('first',))
        sink.submit(('second',))
        self.assertTrue(sink.stop.is_set())
        self.assertEqual(sink.stats['selected'], 2)
        self.assertEqual(sink.stats['queue_dropped'], 1)
        self.assertEqual(sink.report()['enqueued_without_completed_write'], 1)

    def test_real_codec_split_decode_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = VideoSink(directory, 'top', 30, 'MJPG', 32, threading.Event())
            for number in range(12):
                sink.submit((1 if number < 6 else 2, number, number + 1, number, number * 33333333,
                             0, 0, np.full((48, 64), number * 10, np.uint8)))
            sink.finished.set()
            sink.start()
            sink.join(10)
            self.assertFalse(sink.is_alive())
            self.assertFalse(sink.stats['errors'])
            self.assertEqual(sink.stats['write_calls_completed'], 12)
            save_json(Path(directory) / 'session.json', {'cameras': [{'writer': sink.report()}]})
            result = verify_session(directory)
            self.assertTrue(result['all_video_counts_match'])
            self.assertEqual([clip['decoded'] for clip in result['clips']], [6, 6])
            capture = cv2.VideoCapture(str(Path(directory) / 'top_000001.avi'))
            for number in range(6):
                ok, frame = capture.read()
                self.assertTrue(ok)
                self.assertAlmostEqual(float(frame.mean()), number * 10, delta=2)
            capture.release()
            (Path(directory) / 'top_000001.avi').unlink()
            self.assertFalse(verify_session(directory)['all_video_counts_match'])

    def test_writer_open_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = VideoSink(directory, 'top', 30, 'MJPG', 1, threading.Event())
            sink.submit((1, 1, 1, 1, 1, 0, 0, np.zeros((48, 64), np.uint8)))
            sink.finished.set()
            with patch('core.cv2.VideoWriter') as writer:
                writer.return_value.isOpened.return_value = False
                sink.run()
            self.assertTrue(sink.stop.is_set())
            self.assertTrue(sink.stats['errors'])
            self.assertEqual(sink.report()['enqueued_without_completed_write'], 1)

    def test_copy_precedes_release_and_camera_cleanup(self):
        stop = threading.Event()
        frame = np.full((48, 64), 77, np.uint8)

        class Result:
            Array = frame
            def GrabSucceeded(self): return True
            def GetBlockID(self): return 1
            def GetTimeStamp(self): return 100
            def GetNumberOfSkippedImages(self): return 0
            def Release(self):
                frame[:] = 0  # Emulate reuse of SDK-owned memory.
                stop.set()

        class Camera:
            closed = False
            def StartGrabbing(self, strategy): pass
            def RetrieveResult(self, timeout, handling): return Result()
            def IsGrabbing(self): return True
            def StopGrabbing(self): pass
            def Close(self): self.closed = True

        camera = Camera()
        args = SimpleNamespace(fps=30, block_id_modulus=None, start_threshold=200000,
                               continue_threshold=10000, motion_scale=1, mode='continuous')
        sink = VideoSink('.', 'fake', 30, 'MJPG', 2, stop)
        report = {}
        capture_loop(0, camera, SimpleNamespace(GrabStrategy_OneByOne=0, TimeoutHandling_Return=0),
                     args, sink, RecordingGate(continuous=True), stop, report, [None, None])
        self.assertEqual(sink.queue.get()[-1].mean(), 77)
        self.assertTrue(camera.closed)
        self.assertTrue(sink.finished.is_set())
        self.assertFalse(report['errors'])

    def test_disk_failure_accounts_for_unwritten_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            sink = VideoSink(directory, 'top', 30, 'MJPG', 4, threading.Event())
            for i in range(3):
                sink.submit((1, i, i + 1, i, i, 0, 0, np.zeros((48, 64), np.uint8)))
            sink.finished.set()
            with patch('core.cv2.VideoWriter') as writer:
                writer.return_value.isOpened.return_value = True
                writer.return_value.write.side_effect = [None, OSError('disk full')]
                sink.run()
            self.assertTrue(sink.stop.is_set())
            self.assertEqual(sink.stats['write_calls_completed'], 1)
            self.assertEqual(sink.report()['enqueued_without_completed_write'], 2)


if __name__ == '__main__':
    unittest.main()

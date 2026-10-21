"""Small end-to-end tests using real AVI decoding and H.264 encoding."""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from video_postprocessing.merge_videos import merge


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required')
class MergeTests(unittest.TestCase):
    def fixture(self, folder, camera):
        clips = []
        for segment in (1, 2):
            filename = f'{camera}_{segment:06d}.avi'
            writer = cv2.VideoWriter(str(folder / filename), cv2.VideoWriter_fourcc(*'MJPG'),
                                     10, (32, 24))
            self.assertTrue(writer.isOpened())
            for _ in range(2):
                writer.write(np.full((24, 32, 3), segment * 80, dtype=np.uint8))
            writer.release()
            clips.append(dict(file=filename, write_calls_completed=2))
        (folder / 'session.json').write_text(json.dumps(dict(
            status='stopped', configuration=dict(fps=10),
            cameras=[dict(name=camera, writer=dict(clips=clips))])))
        with (folder / f'{camera}_frames.csv').open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['segment', 'video_frame_index', 'host_monotonic_ns'])
            for segment, index, offset in [(1, 0, 0), (1, 1, 200_000_000),
                                            (2, 0, 600_000_000), (2, 1, 700_000_000)]:
                writer.writerow([segment, index, 10_000_000_000 + offset])

    def test_timeline_and_black_frames_for_both_cameras(self):
        for camera in ('top', 'side'):
            with self.subTest(camera=camera), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                self.fixture(folder, camera)
                result = merge(folder, camera)
                self.assertEqual(result['black_frames'], 4)
                self.assertEqual(result['total_frames'], 8)
                capture = cv2.VideoCapture(result['output'])
                means = []
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    means.append(frame.mean())
                capture.release()
                self.assertEqual(len(means), 8)
                for index in (1, 3, 4, 5):
                    self.assertLess(means[index], 3)
                for index, value in [(0, 80), (2, 80), (6, 160), (7, 160)]:
                    self.assertAlmostEqual(means[index], value, delta=5)
                with self.assertRaises(FileExistsError):
                    merge(folder, camera)

    def test_truncated_source_does_not_publish_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.fixture(folder, 'top')
            path = folder / 'top_000002.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (32, 24))
            writer.write(np.full((24, 32, 3), 160, dtype=np.uint8))
            writer.release()
            with self.assertRaisesRegex(ValueError, 'Cannot decode'):
                merge(folder, 'top')
            self.assertFalse((folder / 'top_merged.mp4').exists())

    def test_csv_fallback(self):
        for camera in ('top', 'side'):
            for state in ('recording', 'missing_writer', 'missing_json', 'invalid_json'):
                with self.subTest(camera=camera, state=state), tempfile.TemporaryDirectory() as directory:
                    folder = Path(directory)
                    self.fixture(folder, camera)
                    path = folder / 'session.json'
                    session = json.loads(path.read_text())
                    if state == 'missing_json':
                        path.unlink()
                    elif state == 'invalid_json':
                        path.write_text('{')
                    else:
                        if state == 'recording':
                            session['status'] = 'recording'
                        del session['cameras'][0]['writer']
                        path.write_text(json.dumps(session))
                    with self.assertWarnsRegex(RuntimeWarning, 'using frame CSV'):
                        result = merge(folder, camera)
                    self.assertEqual(result['fps'], 10)
                    self.assertEqual(result['recorded_frames'], 4)
                    self.assertEqual(result['black_frames'], 4)
                    self.assertEqual(result['total_frames'], 8)

    def test_fallback_missing_video_does_not_publish_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.fixture(folder, 'top')
            (folder / 'session.json').unlink()
            (folder / 'top_000002.avi').unlink()
            with self.assertWarns(RuntimeWarning), self.assertRaisesRegex(ValueError, 'Missing video'):
                merge(folder, 'top')
            self.assertFalse((folder / 'top_merged.mp4').exists())


if __name__ == '__main__':
    unittest.main()

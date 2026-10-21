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


class DLCRegressionTests(unittest.TestCase):
    def test_single_and_multi_animal_h5(self):
        import pandas as pd
        from video_postprocessing.merge_videos import prediction_points
        for multi in (False, True):
            names = ['scorer', 'individuals', 'bodyparts', 'coords'] if multi else ['scorer', 'bodyparts', 'coords']
            prefix = ('model', 'mouse1', 'nose') if multi else ('model', 'nose')
            columns = pd.MultiIndex.from_tuples([(*prefix, c) for c in ('x', 'y', 'likelihood')], names=names)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'predictions.h5'
                for likelihood, expected in ((0.6, 0), (0.61, 1), (float('nan'), 0)):
                    pd.DataFrame([[10, 12, likelihood]], columns=columns).to_hdf(path, key='df_with_missing', mode='w')
                    self.assertEqual(len(prediction_points(pd.read_hdf(path), 0.6)), expected)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required')
    def test_dlc_fill_and_control_artifacts(self):
        import pandas as pd
        from types import SimpleNamespace
        from unittest.mock import patch
        for accepted in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                MergeTests().fixture(folder, 'top')
                config = folder / 'config.yaml'
                config.write_text('test config')
                calls = []
                def analyze(config, videos, destfolder, auto_track):
                    video = Path(videos[0])
                    capture = cv2.VideoCapture(str(video))
                    self.assertTrue(capture.read()[0])
                    self.assertFalse(capture.read()[0])
                    capture.release()
                    calls.append(video)
                    columns = pd.MultiIndex.from_product([['model'], ['mouse1'], ['nose'], ['x', 'y', 'likelihood']], names=['scorer', 'individuals', 'bodyparts', 'coords'])
                    pd.DataFrame([[10, 12, 0.9 if accepted else 0.2]], columns=columns).to_hdf(Path(destfolder) / (video.stem + 'DLC.h5'), key='df_with_missing')
                with patch.dict('sys.modules', {'deeplabcut': SimpleNamespace(analyze_videos=analyze)}):
                    result = merge(folder, 'top', dlc_config=config)
                self.assertEqual(len(calls), 2)
                self.assertEqual(result['held_frames'], 3 if accepted else 0)
                self.assertEqual(result['black_frames'], 1 if accepted else 4)
                root = Path(result['dlc_control_dir'])
                self.assertEqual(len(list((root / ('accepted' if accepted else 'rejected')).glob('*.png'))), 2)
                capture = cv2.VideoCapture(result['output'])
                means = []
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    means.append(frame.mean())
                capture.release()
                self.assertLess(means[1], 3)
                for index in (3, 4, 5):
                    self.assertAlmostEqual(means[index], 80 if accepted else 0, delta=5)


if __name__ == '__main__':
    unittest.main()

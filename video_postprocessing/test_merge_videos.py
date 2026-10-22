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
                self.assertEqual(result['black_frames'], 3)
                self.assertEqual(result['within_fragment_held_frames'], 1)
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
                for index in (3, 4, 5):
                    self.assertLess(means[index], 3)
                for index, value in [(0, 80), (1, 80), (2, 80), (6, 160), (7, 160)]:
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
            self.assertFalse((folder / 'top_merge' / 'top_merged.mp4').exists())

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
                    self.assertEqual(result['black_frames'], 3)
                    self.assertEqual(result['total_frames'], 8)

    def test_fallback_missing_video_does_not_publish_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.fixture(folder, 'top')
            (folder / 'session.json').unlink()
            (folder / 'top_000002.avi').unlink()
            with self.assertWarns(RuntimeWarning), self.assertRaisesRegex(ValueError, 'Missing video'):
                merge(folder, 'top')
            self.assertFalse((folder / 'top_merge' / 'top_merged.mp4').exists())


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
                def analyze(config, videos, destfolder, auto_track, save_as_df, batch_size, shuffle):
                    self.assertFalse(auto_track)
                    self.assertTrue(save_as_df)
                    self.assertEqual(shuffle, 2)
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
                self.assertEqual(len(calls), 1)
                self.assertEqual(result['held_frames'], 4 if accepted else 1)
                self.assertEqual(result['black_frames'], 0 if accepted else 3)
                root = Path(result['dlc_control_dir'])
                self.assertEqual(len(list(root.glob('*/prediction.png'))), 1)
                controls = Path(result['control_dir'])
                for segment, value in ((1, 80), (2, 160)):
                    directory = controls / f'top_{segment:06d}'
                    for name in ('first.png', 'last.png'):
                        image = cv2.imread(str(directory / name))
                        self.assertAlmostEqual(image.mean(), value, delta=3)
                    self.assertTrue((directory / 'decision.json').is_file())
                capture = cv2.VideoCapture(result['output'])
                means = []
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    means.append(frame.mean())
                capture.release()
                self.assertAlmostEqual(means[1], 80, delta=5)
                for index in (3, 4, 5):
                    self.assertAlmostEqual(means[index], 80 if accepted else 0, delta=5)


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is required')
class GapPolicyTests(unittest.TestCase):
    def test_long_internal_gap_remains_black_and_is_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            MergeTests().fixture(folder, 'top')
            result = merge(folder, 'top', short_gap_seconds=0.05)
            self.assertEqual(result['within_fragment_held_frames'], 0)
            self.assertEqual(result['within_fragment_black_frames'], 1)
            events = [json.loads(line) for line in (Path(result['control_dir']) / 'gaps.jsonl').read_text().splitlines()]
            self.assertEqual(events[0]['reason'], 'long_timestamp_gap')
            self.assertEqual(events[0]['mode'], 'black')
            self.assertEqual(events[1]['fill_frames'], 3)

    def test_reviewed_decisions_and_custom_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            MergeTests().fixture(folder, 'top')
            decisions = folder / 'review.json'
            decisions.write_text(json.dumps({'top_000001.avi': 'hold', 'top_000002.avi': 'black'}))
            destination = folder / 'results'
            result = merge(folder, 'top', destination=destination, gap_decisions=decisions)
            self.assertEqual(Path(result['output']).parent, destination)
            self.assertEqual(result['held_frames'], 4)
            data = json.loads((destination / 'control/top_000001/decision.json').read_text())
            self.assertEqual(data['following_gap']['reason'], 'reviewed_decision')
            self.assertEqual(data['following_gap']['fill_frames'], 3)
            self.assertEqual(json.loads((destination / 'status.json').read_text())['status'], 'complete')

    def test_collisions_keep_timeline_and_save_actual_source_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            MergeTests().fixture(folder, 'top')
            writer = cv2.VideoWriter(str(folder / 'top_000001.avi'),
                                     cv2.VideoWriter_fourcc(*'MJPG'), 10, (32, 24))
            for value in (60, 110):
                writer.write(np.full((24, 32, 3), value, dtype=np.uint8))
            writer.release()
            (folder / 'top_frames.csv').write_text(
                'segment,video_frame_index,host_monotonic_ns\n'
                '1,0,1000000000\n1,1,1001000000\n2,0,1200000000\n2,1,1300000000\n')
            result = merge(folder, 'top')
            self.assertEqual(result['total_frames'], 4)
            self.assertEqual(result['frames_omitted_at_colliding_timestamps'], 1)
            self.assertEqual(result['recorded_frames'], 4)
            end = cv2.imread(str(Path(result['control_dir']) / 'top_000001/last.png'))
            self.assertAlmostEqual(end.mean(), 110, delta=3)

    def test_dlc_failures_fill_black_and_preserve_controls(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import pandas as pd
        for failure in ('raise', 'missing_h5', 'malformed_h5', 'import'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                MergeTests().fixture(folder, 'top')
                def analyze(config, videos, destfolder, **kwargs):
                    if failure == 'raise':
                        raise RuntimeError('test inference failure')
                    if failure == 'malformed_h5':
                        pd.DataFrame([[1]]).to_hdf(Path(destfolder) / 'lastDLC.h5', key='data')
                module = None if failure == 'import' else SimpleNamespace(analyze_videos=analyze)
                with patch.dict('sys.modules', {'deeplabcut': module}), self.assertWarnsRegex(RuntimeWarning, 'filling black'):
                    result = merge(folder, 'top', dlc_config=folder / 'config.yaml')
                self.assertEqual(result['black_frames'], 3)
                self.assertEqual(result['within_fragment_held_frames'], 1)
                self.assertEqual(result['dlc_errors'], 1)
                data = json.loads((Path(result['control_dir']) / 'top_000001/decision.json').read_text())
                self.assertEqual(data['following_gap']['reason'], 'dlc_error')
                self.assertTrue(data['following_gap']['error'])
                cap = cv2.VideoCapture(result['output'])
                cap.set(cv2.CAP_PROP_POS_FRAMES, 3)
                ok, frame = cap.read()
                cap.release()
                self.assertTrue(ok)
                self.assertLess(frame.mean(), 3)


if __name__ == '__main__':
    unittest.main()

from pypylon import pylon
import cv2
import os
import time


class Camera:
    def __init__(self, device_info):
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(device_info))
        self.camera.Open()

    def set_parameters(self, width=None, height=None, exposure_time=None, frame_rate=None):
        if width is not None:
            self.camera.Width.SetValue(width)
        if height is not None:
            self.camera.Height.SetValue(height)
        if exposure_time is not None:
            self.camera.ExposureTime.SetValue(exposure_time)
        if frame_rate is not None:
            self.camera.AcquisitionFrameRateEnable.SetValue(True)
            self.camera.AcquisitionFrameRate.SetValue(frame_rate)

    def start_grabbing(self):
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    def retrieve_frame(self):
        grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        frame = grab_result.Array
        return frame

    def stop_grabbing(self):
        self.camera.StopGrabbing()
        self.camera.Close()


class CameraViewer:
    def __init__(self):
        self.window_names = ["Camera 1", "Camera 2", "Camera 3", "Camera 4", "Camera 5", "Camera 6"]
        self.cameras = []
        for window_name in self.window_names:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    def add_camera(self, device_info):
        if len(self.cameras) >= len(self.window_names):
            print("Maximum number of cameras reached.")
            return
        camera = Camera(device_info)
        self.cameras.append(camera)

    def set_camera_parameters(self, camera_index, width=None, height=None, exposure_time=None, frame_rate=None):
        if camera_index < 0 or camera_index >= len(self.cameras):
            print("Invalid camera index.")
            return
        camera = self.cameras[camera_index]
        camera.set_parameters(width, height, exposure_time, frame_rate)

    def show_frames(self):
        for camera in self.cameras:
            camera.start_grabbing()

        while all(camera.camera.IsGrabbing() for camera in self.cameras):
            frames = [camera.retrieve_frame() for camera in self.cameras]
            for i, frame in enumerate(frames):
                cv2.imshow(self.window_names[i], frame)
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break

    def close_cameras(self):
        for camera in self.cameras:
            camera.stop_grabbing()
        cv2.destroyAllWindows()


class PairedCameraRecorder:
    def __init__(self, camera1, camera2, output_file_prefix="video"):
        self.camera1 = camera1
        self.camera2 = camera2
        self.output_file_prefix = output_file_prefix
        self.video_writer1 = None
        self.video_writer2 = None

    def start_recording(self, width, height, frame_rate, output_path="./"):
        output_file1 = os.path.join(output_path, f"{self.output_file_prefix}_camera1.avi")
        output_file2 = os.path.join(output_path, f"{self.output_file_prefix}_camera2.avi")
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer1 = cv2.VideoWriter(output_file1, fourcc, frame_rate, (width, height))
        self.video_writer2 = cv2.VideoWriter(output_file2, fourcc, frame_rate, (width, height))

    def record_frames(self, duration_seconds):
        start_time = time.time()
        while self.camera1.camera.IsGrabbing() and self.camera2.camera.IsGrabbing():
            current_time = time.time()
            if current_time - start_time >= duration_seconds:
                break
            frame1 = self.camera1.retrieve_frame()
            frame2 = self.camera2.retrieve_frame()
            self.video_writer1.write(frame1)
            self.video_writer2.write(frame2)

    def stop_recording(self):
        self.video_writer1.release()
        self.video_writer2.release()


if __name__ == "__main__":
    camera_viewer = CameraViewer()
    infos = [i for i in pylon.TlFactory.GetInstance().EnumerateDevices()]
    for info in infos:
        camera_viewer.add_camera(info)

    # Set camera parameters
    camera_viewer.set_camera_parameters(camera_index=0, width=1920, height=1080, exposure_time=10000, frame_rate=30)

    # Show frames from cameras
    camera_viewer.show_frames()

    # Close cameras
    camera_viewer.close_cameras()

    # Initialize paired camera recorder
    paired_camera_recorder = PairedCameraRecorder(camera1=camera_viewer.cameras[0], camera2=camera_viewer.cameras[1])

    # Start recording
    paired_camera_recorder.start_recording(width=1920, height=1080, frame_rate=30)

    # Record frames
    paired_camera_recorder.record_frames(duration_seconds=10)

    # Stop recording
    paired_camera_recorder.stop_recording()

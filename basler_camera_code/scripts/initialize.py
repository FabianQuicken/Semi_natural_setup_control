from pypylon import pylon
import cv2

def get_camera_info():
    infos = []
    for i in pylon.TlFactory.GetInstance().EnumerateDevices():
        infos.append(i)
    return infos


def get_cameras(num_cameras=2):
    """
    Finds all cameras connected to the pc and saves them as object.
    Each camera object goes to a list of cameras. 
    Maybe put related cameras in one list for later synchronization?
    """
    camera_infos = get_camera_info()
    cameras = []
    for i in range(num_cameras):
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(camera_infos[i]))
        cameras.append(camera)
    return cameras

def set_camera_parameters(exposuretime = int, fps = int, width = 1920, height = 1080):
    """
    Sets the exposure time and frames per second of an camera object.
    Note: exposure time is given in MICROseconds (e.g. 10 ms --> 10000 µs)
    """
    cameras = get_cameras()
    for camera in cameras:
        camera.Open()
        camera.ExposureTime.SetValue(exposuretime)  # Set exposure time in microseconds (e.g., 10 ms)
        camera.AcquisitionFrameRateEnable.SetValue(True)
        camera.AcquisitionFrameRate.SetValue(fps)
        # set width and height, max. of the basler Aca1920-150um is 1984x1264
        camera.Width.SetValue(width)  
        camera.Height.SetValue(height) 
    return cameras

def activate_cameras(cameras):
    for camera in cameras:
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)


def grab_frames(cameras):
    frames = []
    for camera in cameras:
        grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grab_result.GrabSucceeded():
            frame = grab_result.Array
            frames.append(frame)
        grab_result.Release()
  
    return frames

#cameras = set_camera_parameters(exposuretime=10000, fps=30)
#activate_cameras(cameras)
cv2.namedWindow("Camera 1", cv2.WINDOW_NORMAL)
cv2.namedWindow("Camera 2", cv2.WINDOW_NORMAL)
infos = get_camera_info()
print(infos[1].GetSerialNumber())

camera1 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(infos[0]))
camera2 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(infos[1]))
camera1.Open()
camera2.Open()
camera1.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
camera2.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
while camera1.IsGrabbing():
    grab_result = camera1.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    grab_result2 = camera2.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    frame = grab_result.Array
    frame2 = grab_result2.Array
    cv2.imshow("Camera 1", frame)
    cv2.imshow("Camera 2", frame2)

    key = cv2.waitKey(1)
    if key & 0xFF == ord('q'):
        break

camera1.StopGrabbing()
camera2.StopGrabbing()

        
camera1.Close()
camera2.Close()


cv2.destroyAllWindows()

"""
while True:
    frames = grab_frames(cameras)
    print(frames[0])
    print(frames[1])
    cv2.imshow("Camera 1", frames[0])
    cv2.imshow("Camera 2", frames[1])


    if cv2.waitKey(1) & 0xFF == ord('q'):
                break

cv2.destroyAllWindows()
for camera in cameras:
     camera.StopGrabbing()
     camera.Close()


print(get_camera_info())
"""
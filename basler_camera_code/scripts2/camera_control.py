"""

THIS .py CONTAINS FUNCTIONS THAT CONTROL BASLER CAMERAS


"""

from pypylon import pylon


# find cameras and load their infos
def get_camera_info():
    """
    EnumerateDevices() creates a list of CDeviceInfo objects. Each of these objects contains camera information, 
    e.g. the serial number that can be extracted via object.GetSeriaLNumber() as a string.
    """
    c_infos = pylon.TlFactory.GetInstance().EnumerateDevices()
    for c_info in c_infos:
        print(f"Camera with serial number {c_info.GetSerialNumber()} was found.")
    return c_infos
    

# initialize camera objects
def camera_ini(info):
    """
    A camera class gets initialized based on the camera infos passed to the func.
    It also gets opened, so it is available for changing settings or start grabbing frames
    """
    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(info))
    cam.Open()
    print("Cam opened.")
    return cam


# adjust camera settings
def camera_settings(cam, height=1080, width=1920, fps=int, expo_time=int):
    """
    Changes the settings of the selected camera.
    Height/Weight display pixel resolution, frames per second, exposure time in MICROseconds.
    Default resolution is Full HD.
    """
    cam.Width.SetValue(width)  # Set width
    cam.Height.SetValue(height)  # Set height
    cam.ExposureTime.SetValue(expo_time)  # Set exposure time in MICROseconds (e.g., 10 ms)
    cam.AcquisitionFrameRateEnable.SetValue(True)
    cam.AcquisitionFrameRate.SetValue(fps)  # Set FPS (e.g., 30 frames per second)
    print("Adjusted cam settings.")
    return cam

# Start grabbing of frames for a recording.
def camera_grab(cam):
    """
    Camera starts grabbing frames based on the LatestImageOnly strategy.
    Note: LatestImageOnly is memory friendly, but frames might be missed.
    """
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

# Retrieve frames grabbed by the camera:
def get_frame(cam):
    """
    A grab result based on a strategy (see camera_grab()) is retrieved. The Camera waits a maximum of 5000 ms for a grab, 
    this value can be adjusted. The result gets transformed by .Array. 
    """
    frame = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException) # retrieves 'GrabResult' object (holds image data)
    img = frame.Array # saves image data as array
    frame.Release() # releases the resources bound by the RetrieveResult object to prevent memory clugging
    return img

# Shut down cameras after a recording
def close_camera(cam):
    cam.StopGrabbing()
    cam.Close()
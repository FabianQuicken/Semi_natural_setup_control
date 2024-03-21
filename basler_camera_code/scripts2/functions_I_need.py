# import packages here
from pypylon import pylon
import cv2
import numpy as np

cam_serial_numbers = ["40357253", "40405187"]

# # # # THIS PART IS FOR PYLON TO RUN THE CAMERAS AND GET FRAMES # # # #

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
    A camera class gets initialized based on the camera infos passed to the func
    it also gets opened, so it is available for changing settings or start grabbing frames
    """
    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(info))
    cam.Open()
    return cam


# adjust camera settings
def camera_settings(cam, height=1020, width=1920, fps=60, expo_time=10000):
    """
    Changes the settings of the selected camera
    """
    cam.Width.SetValue(width)  # Set width
    cam.Height.SetValue(height)  # Set height
    cam.ExposureTime.SetValue(expo_time)  # Set exposure time in microseconds (e.g., 10 ms)
    cam.AcquisitionFrameRateEnable.SetValue(True)
    cam.AcquisitionFrameRate.SetValue(fps)  # Set FPS (e.g., 30 frames per second)
    return cam

# Start grabbing of frames for a recording.
def camera_grab(cam):
    """
    Camera starts grabbing frames based on the LatestImageOnly strategy.
    """
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

# Retrieve frames grabbed by the camera:
def get_frame(cam):
    """
    A grab result based on a strategy (see camera_grab()) is retrieved. The Camera waits a maximum of 5000 ms for a grab, 
    this value can be adjusted. 
    """
    frame = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    return frame.Array

# Shut down cameras after a recording
def close_camera(cam):
    cam.StopGrabbing()
    cam.Close()

# # # # THIS PART IS FOR PYLON TO RUN THE CAMERAS AND GET FRAMES # # # #
    
# # # # THIS PART IS FOR DOING THE MOTION DETECTION # # # #
    
# calculate the difference between consecutive frames
def motion_detection(first_frame, second_frame, change_thresh = 10):
    """
    The func takes two frames that should be consecutive frames of the same camera. 
    It calculates the absolute difference for all pixels in the frame. 
    Then, based on a threshold, significant changes get filtered and returned.
    The sensitivity for real changes can be adjusted via the change_thresh parameter.
    Note: Images need to be binary, so only one color channel (black/white).
    """
    diff_frame = cv2.absdiff(first_frame, second_frame)
    _, thresh = cv2.threshold(diff_frame, change_thresh, 255, cv2.THRESH_BINARY)
    return thresh

def sum_motion(arr):
    """
    Sums up the array consisting of values showing change (0 vs 255).
    """
    print(len(arr))
    #print(np.sum(arr))
    #print((np.sum(arr)/len(arr)))
    return np.sum(arr)

def check_movement(motion_sum, thresh):
    if motion_sum >= thresh:
        return True
    elif motion_sum <= thresh:
        return False
    
# # # # THIS PART IS FOR DOING THE MOTION DETECTION # # # #
    
# # # # THIS PART IS FOR VIDEO RECORDING # # # # 
    
def create_video_name(cam):
    pass
    
def setup_video_writer(video_name=str, cam):
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(video_name, fourcc, 30.0, (cam.Width.Value, cam.Height.Value))
    pass

def write_frame_to_video():
    pass
    

    





# testing
camera_infos = get_camera_info()

# starts camera instance and opens the camera
camera_1 = camera_ini(camera_infos[0])
camera_2 = camera_ini(camera_infos[1])

# sets camera settings
camera_1 = camera_settings(camera_1)
camera_2 = camera_settings(camera_2)

# test code for recording
frames = 1000
recording = True
prev_frame = None
while recording:
    if not camera_1.IsGrabbing():
        camera_grab(camera_1)
    #camera_grab(camera_2)
    frame = get_frame(camera_1)
    #print(frame)
    #print(get_frame(camera_2))

    # test motion detection
    if prev_frame is not None:
        motion = motion_detection(first_frame=prev_frame, second_frame=frame)
        movement_present = check_movement(motion_sum=sum_motion(motion), thresh=50000000)
        #print(movement_present)

    prev_frame = frame
    # terminate loop
    frames -= 1
    if frames <= 0:
        recording = False

close_camera(camera_1)
#close_camera(camera_2)





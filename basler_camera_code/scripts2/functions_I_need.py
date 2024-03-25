# import packages here
from pypylon import pylon
import cv2
import numpy as np
from datetime import datetime

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
    A camera class gets initialized based on the camera infos passed to the func.
    It also gets opened, so it is available for changing settings or start grabbing frames
    """
    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(info))
    cam.Open()
    return cam


# adjust camera settings
def camera_settings(cam, height=1080, width=1920, fps=60, expo_time=10000):
    """
    Changes the settings of the selected camera.
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
    this value can be adjusted. The result gets transformed by .Array. 
    """
    frame = cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    img = frame.Array
    frame.Release()
    return img

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
    #print(len(arr))
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
    
def create_video_name(cam_num=str):
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    video_name = current_time + "_" + str(cam_num) + ".avi"
    return video_name
    
def setup_video_writer(cam, video_name=str, fps=float):
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(video_name, fourcc, fps, (cam.Width.Value, cam.Height.Value))
    return out

def convert_frame_format(img):
    if len(img.shape) == 2:
        # Convert grayscale to BGR format
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img

def write_frame_to_video():
    # doing this with .write() in the testing() for now
    pass

# # # # THIS PART IS FOR VISUALIZING CAMERAS # # # #

def open_camera_window():
    pass

def open_motion_detection_window():
    pass

# # # # THIS PART IS FOR VISUALIZING CAMERAS # # # # 
    


def testing():
    camera_infos = get_camera_info()

    # starts camera instance and opens the camera
    camera_1 = camera_ini(camera_infos[0])
    camera_2 = camera_ini(camera_infos[1])

    # sets camera settings
    camera_1 = camera_settings(camera_1)
    camera_2 = camera_settings(camera_2)

    # test code for recording
    frames = 300
    recording = True
    prev_frame1 = None
    prev_frame2 = None

    # test video recording (setting up recorder)
    video_name1 = create_video_name(cam_serial_numbers[0])
    output1 = setup_video_writer(cam=camera_1,video_name=video_name1,fps=60.0)

    video_name2 = create_video_name(cam_serial_numbers[1])
    output2 = setup_video_writer(cam=camera_2,video_name=video_name2,fps=60.0)

    
    while recording:
        if not camera_1.IsGrabbing():
            camera_grab(camera_1)
        frame1 = get_frame(camera_1)
        if not camera_2.IsGrabbing():
            camera_grab(camera_2)
        frame2 = get_frame(camera_2)

        # test motion detection
        if prev_frame1 is not None:
            motion = motion_detection(first_frame=prev_frame1, second_frame=frame1)
            movement_present1 = check_movement(motion_sum=sum_motion(motion), thresh=50000000)
            print(movement_present1)
        if prev_frame2 is not None:
            motion = motion_detection(first_frame=prev_frame2, second_frame=frame2)
            movement_present2 = check_movement(motion_sum=sum_motion(motion), thresh=50000000)
            print(movement_present2)

        # try to write frames into a video
        try:
            img1 = convert_frame_format(frame1)
            img2 = convert_frame_format(frame2)
        except:
            print("Cant convert Image Array Format.")
        finally:
            output1.write(img1)
            output2.write(img2)

        

        

        prev_frame1 = frame1
        prev_frame2 = frame2



        # terminate loop
        frames -= 1
        if frames <= 0:
            recording = False

    close_camera(camera_1)
    close_camera(camera_2)

testing()
    





# import packages here
from pypylon import pylon
import cv2
import numpy as np
from datetime import datetime
import time

cam_serial_numbers = ["40439818", "40357253", "40405188", "40405187"]
cam_id_name = {"40439818": "top1", "40357253": "side1", "40405188": "top2", "40405187": "side2"}
cam_name_id = {"top1": "40439818", "side1": "40357253", "top2": "40405188", "side2": "40405187"}

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
def camera_settings(cam, height=1080, width=1920, fps=30, expo_time=32000):
    """
    Changes the settings of the selected camera.
    Height/Weight display pixel resolution, frames per second, exposure time in MICROseconds.
    """
    cam.Width.SetValue(width)  # Set width
    cam.Height.SetValue(height)  # Set height
    cam.ExposureTime.SetValue(expo_time)  # Set exposure time in MICROseconds (e.g., 10 ms)
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
    #frame.Release()
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

def open_camera_windows(names=list):
    for name in names:
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(name, 720, 405)

def display_frames(names=list, frames=list):
    """
    Frames can be displayed without opening a camera window aswell.
    """
    for i in range(len(frames)):
        cv2.imshow(names[i], frames[i])


# # # # THIS PART IS FOR VISUALIZING CAMERAS # # # # 
        
# # # # THIS PART IS FOR STARTING AND CONTROLLING A RECORDING WHEN MOVEMENT IS PRESENT # # # # 

def record_while_mov(cams=list, cam_ids=list, mov_check_window=100):
    """
    This function should be used with a camera pair as cams argument. The continuous 
    movement detection will run on one camera, but both will record a video. 
    Camera IDs are needed to create video names, their order should correspond to the cams order.
    The mov_check_window determines the number of frames that can be "movement free" without stopping
    the recording.
    """
    # First, all parameters get initialized
    frames = [None, None] # grabbed frames will be stored here
    imgs = [None, None] # transformed grabbed frames will be stored here
    prev_frame = None # this will be used to save a frame for the next iteration
    counter=mov_check_window # the counter will count down while no movement is present
    movement_present = None # will save the outcome of frame/prevframe absdiff as Bool

    

    # video output needs to be defined
    cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0]
    cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1]
    vid_name1 = create_video_name(cam_num=cam_1_name) # videoname based on cam1 name + id
    vid_name2 = create_video_name(cam_num=cam_2_name) # videoname based on cam2 name + id

    # opens camera windows of both cameras where movement was detected by main()
    # also shows a window where the absdiff is visualized
    open_camera_windows(names=[cam_1_name, cam_2_name, f'Motion cam {cam_1_name}'])

    # initializes a VideoWriter instance for each camera and saves them into a list
    out1 = setup_video_writer(cam=cams[0],video_name=vid_name1,fps=30)
    out2 = setup_video_writer(cam=cams[1],video_name=vid_name2,fps=30)
    outs = [out1, out2]

    while counter > 0:
        print("recording...")
        try:
            # get the frames
            for i in range(len(cams)):
                if not cams[i].IsGrabbing():
                    camera_grab(cams[i])
                frames[i] = get_frame(cams[i])
        except:
            print("Grabbing frames not possible.")
        # constantly check movement in first camera
        if prev_frame is not None:
            motion = motion_detection(first_frame=prev_frame, second_frame=frames[0])
            movement_present = check_movement(motion_sum=sum_motion(motion), thresh=50000000)
            print(movement_present)

        # reset the counter if still movement there
        if movement_present:
            counter = mov_check_window
        prev_frame = frames[0]

        # write the frames into a video
        try:
            for i in range(len(frames)):
                imgs[i] = convert_frame_format(frames[i])
        except:
            print("Can't convert frames to image format for video writing.")

        try:
            for i in range(len(imgs)):
                outs[i].write(imgs[i])
        except:
            print("Could not write frame into videofile.")

        # display frames + waitKey func
        try:
            try:
                display_frames(names=[cam_1_name, cam_2_name, f'Motion cam {cam_1_name}'], frames=frames+[motion])
            except:
                display_frames(names=[cam_1_name, cam_2_name], frames=frames)
        except:
            print("Could not display frames.")
            break

        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            cv2.destroyAllWindows()
            break
            

        # finally: go down with the counter and check update movement_present
        counter -= 1
        if counter == 0:
            movement_present = False
        print(counter)

# # # # THIS PART IS FOR STARTING AND CONTROLLING A RECORDING WHEN MOVEMENT IS PRESENT # # # # 
        
# # # # THIS PART IS FOR CREATING CAMERA PAIRS # # # # 
        
def ini_cam_pair(module_num=int):
    """
    This func can be used to initialize a pair of related cameras.
    Each camera will get initialized and its settings adjusted based on the camera_settings func.
    Returns a list of both cameras, where the top camera is the first, and the side camera the second.
    Depends on the cam_name_id dic, where camera name keys (e.g. top1, side1, top2, ...) 
    and camera serial number values are stored.
    """

    module_num = str(module_num)
    cameras = [None, None]
    camera_infos = get_camera_info()

    print(f"Looking for cams top{module_num}, side{module_num}...\n")
    time.sleep(1)

    try:
        for i in range(len(camera_infos)):
            if camera_infos[i].GetSerialNumber() == cam_name_id[f"top{module_num}"]:
                cameras[0] = camera_ini(camera_infos[i]) # sets top camera as first element in list
                cameras[0] = camera_settings(cameras[0]) # adjusts camera settings
                # give user some feedback
                print(f"Found cam: top{module_num} with SerialNum: {cam_name_id[f'top{module_num}']}!")
                time.sleep(1)
                
            elif camera_infos[i].GetSerialNumber() == cam_name_id[f"side{module_num}"]:
                cameras[1] = camera_ini(camera_infos[i]) # sets side camera as second element in list
                cameras[1] = camera_settings(cameras[1]) # adjusts camera settings
                # give user some feedback
                print(f"Found cam: side{module_num} with SerialNum: {cam_name_id[f'side{module_num}']}!")
                time.sleep(1)
                
            else:
                # Gives info, if the cameras can't be found for the respective module.
                print(f"No cameras found for module {module_num}.")
                print(f"Tried to find cam: top{module_num} with SerialNum {cam_name_id[f'top{module_num}']} .\n")
                print(f"Tried to find cam: side{module_num} with SerialNum {cam_name_id[f'side{module_num}']} .\n")
                time.sleep(1)

    except:
        # print error if functionality of the try block is broken somehow
        # check camera_ini and camera_settings func
        # check if serial numbers and camera names are saved correctly
        print("Error while initializing camera pair.")
        time.sleep(1)

    # cameras can get returned now 
    finally:
        return cameras

# # # # THIS PART IS FOR CREATING CAMERA PAIRS # # # # 
        



def testing():

    frames = [None, None]
    prev_frames = [None, None]
    motion = [None, None]
    movement_present = [False, False]
    recording = True

    """
    camera_infos = get_camera_info()
    cameras = [1, 2]

    for i in range(len(cameras)):
        cameras[i] = camera_ini(camera_infos[i])
        cameras[i] = camera_settings(cameras[i])
    """
    cameras = ini_cam_pair(module_num=2)

    #open_camera_windows(names=['Camera 1', 'Camera 2', 'Motion 1', 'Motion 2'])

    counter = 100
    while recording:

        for i in range(len(cameras)):
            if not cameras[i].IsGrabbing():
                camera_grab(cameras[i])
            frames[i] = get_frame(cameras[i])
        for i in range(len(prev_frames)):
            if prev_frames[i] is not None:
                motion[i] = motion_detection(first_frame=prev_frames[i], second_frame=frames[i])
                movement_present[i] = check_movement(motion_sum=sum_motion(motion[i]), thresh=50000000)

        # we later only use one camera of a pair for motion detection
        if movement_present[0]:
            #cv2.destroyAllWindows()
            record_while_mov(cams=cameras,cam_ids=cam_serial_numbers)
            # for now, when movement was present in both cameras and the recording started, this hinders a second trigger of the 
            # record_while_mov with the same movement trigger
            for i in range(len(movement_present)):
                movement_present[i] = False
            for i in range(len(prev_frames)):
                prev_frames[i] = None
                frames[i] = None

        for i in range(len(prev_frames)):
            prev_frames[i] = frames[i]
        
        counter -= 1
        if counter < 0:
            recording = False
        print(f"total {counter}")

    for i in range(len(cameras)):
        close_camera(cameras[i])
        

testing()
    
    








def testing_old():
    """
    old testing function
    """
    camera_infos = get_camera_info()

    cameras = [1, 2]
    frames = [None, None]
    
    # starts camera instance and opens the camera
    camera_1 = camera_ini(camera_infos[0])
    camera_2 = camera_ini(camera_infos[1])

    # sets camera settings
    camera_1 = camera_settings(camera_1)
    camera_2 = camera_settings(camera_2)

    # test code for recording
    counter = 1500
    recording = True
    prev_frame1 = None
    prev_frame2 = None

    # test video recording (setting up recorder)
    video_name1 = create_video_name(cam_serial_numbers[0])
    #output1 = setup_video_writer(cam=camera_1,video_name=video_name1,fps=30.0)

    video_name2 = create_video_name(cam_serial_numbers[1])
    #output2 = setup_video_writer(cam=camera_2,video_name=video_name2,fps=30.0)

    open_camera_windows(names=['Camera 1', 'Camera 2', 'Motion 1', 'Motion 2'])

    while recording:
        
        if not camera_1.IsGrabbing():
            camera_grab(camera_1)
        frame1 = get_frame(camera_1)
        if not camera_2.IsGrabbing():
            camera_grab(camera_2)
        frame2 = get_frame(camera_2)
        
        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            break
        
        # test motion detection
        if prev_frame1 is not None:
            motion1 = motion_detection(first_frame=prev_frame1, second_frame=frame1)
            movement_present1 = check_movement(motion_sum=sum_motion(motion1), thresh=50000000)
            print(movement_present1)
        if prev_frame2 is not None:
            motion2 = motion_detection(first_frame=prev_frame2, second_frame=frame2)
            movement_present2 = check_movement(motion_sum=sum_motion(motion2), thresh=50000000)
            print(movement_present2)
        try:
            display_frames(names=['Camera 1', 'Camera 2', 'Motion 1', 'Motion 2'], frames=[frame1, frame2, motion1, motion2])
        except:
            display_frames(names=['Camera 1', 'Camera 2'], frames=[frame1, frame2])
        
        """
        # try to write frames into a video
        try:
            img1 = convert_frame_format(frame1)
            img2 = convert_frame_format(frame2)
            
        except:
            print("Cant convert Image Array Format.")
        finally:
            output1.write(img1)
            output2.write(img2)

        """
        prev_frame1 = frame1
        prev_frame2 = frame2

        # terminate loop
        counter -= 1
        if counter <= 0:
            recording = False
    
    close_camera(camera_1)
    close_camera(camera_2)
    
    cv2.destroyAllWindows()
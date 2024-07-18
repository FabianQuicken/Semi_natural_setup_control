# import packages here
from pypylon import pylon
import cv2
import numpy as np
from datetime import datetime
import time

cam_serial_numbers = ["40439818", "40357253", "40405188", "40405187"]
fps = int(input("At what fps do you want to record?\n"))
expo_time = int(input("What exposure time [milliseconds] do you want to set your cameras on?\n"))
expo_time = expo_time*1000 

# camera names, that are physically written on the respective camera aswell
# top1 and side1 should be used for module1 and so on
cam_id_name = {"40405188": "top1", "40405187": "side1", "40439818": "top2", "40405187": "side2"}
cam_name_id = {"top1": "40405188", "side1": "40405187", "top2": "40439818", "side2": "40405187"}

# ursprüngliche cam_id_name: {"40439818": "top1", "40357253": "side1", "40405188": "top2", "40405187": "side2"}
# ursprüngliche cam_name_id: {"top1": "40439818", "side1": "40357253", "top2": "40405188", "side2": "40405187"}


# here I bring the cam ids in a module format, like the cameras
cam_id_pairs = []
try:
    cam_ids_module1 = [cam_name_id["top1"], cam_name_id["side1"]]
    cam_id_pairs.append(cam_ids_module1)
except:
    print('Could not write cam_ids of module 1 in list')
try:
    cam_ids_module2 = [cam_name_id["top2"], cam_name_id["side2"]]
    cam_id_pairs.append(cam_ids_module2)
except:
    print('Could not write cam_ids of module 2 in list')
try:
    cam_ids_module3 = [cam_name_id["top3"], cam_name_id["side3"]]
    cam_id_pairs.append(cam_ids_module3)
except:
    print('Could not write cam_ids of module 3 in list')
print(cam_id_pairs)


# # # # START: THIS PART IS FOR PYLON TO RUN THE CAMERAS AND GET FRAMES # # # #

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
def camera_settings(cam, height=1080, width=1920, fps=fps, expo_time=expo_time):
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

# # # # END: THIS PART IS FOR PYLON TO RUN THE CAMERAS AND GET FRAMES # # # #
    
# # # # START: THIS PART IS FOR DOING THE MOTION DETECTION # # # #
    
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
    return np.sum(arr)

def check_movement(motion_sum, thresh):
    if motion_sum >= thresh:
        return True
    elif motion_sum <= thresh:
        return False
    
# # # # END: THIS PART IS FOR DOING THE MOTION DETECTION # # # #
    
# # # # START: THIS PART IS FOR VIDEO RECORDING # # # # 
    
def create_video_name(cam_num=str, paradigm="testing"):
    """
    This func generates the current daytime to generate a useful savename for generated videos.
    It returns the name based on this template: YYYY_MM_DD_HH_MM_SS_paradigmname_camname.avi
    """
    current_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S") # gets current date (from year to second, converted to a string and split by '_'.)
    video_name = current_time + "_" + paradigm + "_" + str(cam_num) + ".avi" # constructs a video name string
    return video_name
    
def setup_video_writer(cam, video_name=str, fps=float):
    """
    This func configures a video writer object, allowing to save video frames to a file.
    It takes the used camera object, a video name (see create_video_name()) and the fps setting as arguments.
    It returns the VideoWriter object.
    """
    fourcc = cv2.VideoWriter_fourcc(*'XVID') # generates FourCharacterCode specifiying the codec to compress frames, XVID is common for .avi
    out = cv2.VideoWriter(video_name, fourcc, fps, (cam.Width.Value, cam.Height.Value)) # constructs the VideoWriter object
    return out

def convert_frame_format(img):
    """
    
    """
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
        

def observe_while_not_rec(cams=list, cam_ids=list):
    frames = []
    for i in range(len(cams)):
        frames.append(None)
    # video output needs to be defined
    #cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0]
    #cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1]

    # opens camera windows of both cameras where movement was detected by main()
    open_camera_windows(names=cam_ids)
    try:
        # get the frames
        for i in range(len(cams)):
            if not cams[i].IsGrabbing():
                camera_grab(cams[i])
            frames[i] = get_frame(cams[i])
    except:
        print("Grabbing frames not possible.")
    try:
        display_frames(names=cam_ids, frames=frames)

    except:
        print("Could not display frames.")

    key = cv2.waitKey(1)
    if key & 0xFF == ord('q'):
        cv2.destroyAllWindows()
        return False
    else:
        return True
        

# # # # THIS PART IS FOR VISUALIZING CAMERAS # # # # 
        
# # # # THIS PART IS FOR STARTING AND CONTROLLING A RECORDING WHEN MOVEMENT IS PRESENT # # # # 

def record_while_mov(cams=list, cam_ids=list, mov_check_window=300, mov_thresh=500000000):
    """
    This function should be used with a camera pair as cams argument. The continuous 
    movement detection will run on one camera, but both will record a video. 
    Camera IDs are needed to create video names, their order should correspond to the cams order.
    The mov_check_window determines the number of frames that can be "movement free" without stopping
    the recording. The mov_thresh is used as thresh for the check_movement func.
    """
    # First, all parameters get initialized
    frames = [None, None] # grabbed frames will be stored here
    imgs = [None, None] # transformed grabbed frames will be stored here
    prev_frame = None # this will be used to save a frame for the next iteration
    counter=mov_check_window # the counter will count down while no movement is present
    movement_present = None # will save the outcome of frame/prevframe absdiff as Bool

    print(f"This is cam ids: {cam_ids}")
    print(f"This is cam ids 0: {cam_ids[0]}")

    # video output needs to be defined
    cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0]
    cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1]
    vid_name1 = create_video_name(cam_num=cam_1_name) # videoname based on cam1 name + id
    vid_name2 = create_video_name(cam_num=cam_2_name) # videoname based on cam2 name + id

    # opens camera windows of both cameras where movement was detected by main()
    # also shows a window where the absdiff is visualized
    open_camera_windows(names=[cam_1_name, cam_2_name, f'Motion cam {cam_1_name}'])

    # initializes a VideoWriter instance for each camera and saves them into a list
    out1 = setup_video_writer(cam=cams[0],video_name=vid_name1,fps=fps)
    out2 = setup_video_writer(cam=cams[1],video_name=vid_name2,fps=fps)
    outs = [out1, out2]

    while counter > 0:
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
            movement_present = check_movement(motion_sum=sum_motion(motion), thresh=mov_thresh)


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
            # tries to find the top camera
            if camera_infos[i].GetSerialNumber() == cam_name_id[f"top{module_num}"]:
                cameras[0] = camera_ini(camera_infos[i]) # sets top camera as first element in list
                cameras[0] = camera_settings(cameras[0]) # adjusts camera settings
                # give user some feedback
                print(f"Found cam: top{module_num} with SerialNum: {cam_name_id[f'top{module_num}']}!")
                time.sleep(1)

        for i in range(len(camera_infos)):
            # tries to finde the side camera
            if camera_infos[i].GetSerialNumber() == cam_name_id[f"side{module_num}"]:
                cameras[1] = camera_ini(camera_infos[i]) # sets side camera as second element in list
                cameras[1] = camera_settings(cameras[1]) # adjusts camera settings
                # give user some feedback
                print(f"Found cam: side{module_num} with SerialNum: {cam_name_id[f'side{module_num}']}!")
                time.sleep(1)

        # Gives info, if the cameras can't be found for the respective module.
        if cameras[0] is None:
            print(f"Cam not found. Tried to find cam: top{module_num} with SerialNum {cam_name_id[f'top{module_num}']} .\n")
            time.sleep(1)
        if cameras[1] is None:
            print(f"Cam not found. Tried to find cam: side{module_num} with SerialNum {cam_name_id[f'side{module_num}']} .\n")
            time.sleep(1)
        if cameras[0] is not None and cameras[1] is not None:
            return cameras

    except:
        # print error if functionality of the try block is broken somehow
        # check camera_ini and camera_settings func
        # check if serial numbers and camera names are saved correctly
        print("Error while initializing camera pair.")
        #raise ValueError
        time.sleep(1)


# # # # THIS PART IS FOR CREATING CAMERA PAIRS # # # # 



# needs to grab two consecutive frames
# should return true if movement present, false if not
# should perform this on the top camera of a module
    
def check_mov_periodic(cams, thresh=500000000):
    """
    Checks if movement is present in the top camera of a 
    passed camera module pair.
    Returns true/false if movement is present/not present.
    Based on the return, a decision can be made to record or video.
    Threshold for movement detection can be set.
    """

    first_frame = None
    second_frame = None
    try:
        if not cams[0].IsGrabbing():
                    camera_grab(cams[0])
        first_frame = get_frame(cams[0])
        second_frame = get_frame(cams[0])
        motion = motion_detection(first_frame=first_frame, second_frame=second_frame)
        movement_present = check_movement(motion_sum=sum_motion(motion), thresh=thresh)
        return movement_present
    except:
        print("Could not check for movement.")

# # # # THIS PART IS FOR AN INITIAL MOTION CHECK # # # # 

# # # # THIS PART IS FOR INITIALIZING ALL VARIABLES # # # #

def ini_var():
    paradigm = input("What paradigm will you record?\n")
    modules = list(input("What modules will be used? If using module 1 & 2, type: 12\n"))
    
    
    frames = []
    prev_frames = []
    movement_present = []
    all_cams = []
    camera_pairs_list = []


    if '1' in modules:
        try:
            cameras1 = ini_cam_pair(module_num=1)
            all_cams = all_cams + cameras1
            camera_pairs_list.append(cameras1)
        except:
            print("Could not create first camera module.")
    
    if '2' in modules:
        try:
            cameras2 = ini_cam_pair(module_num=2)
            all_cams = all_cams + cameras2
            camera_pairs_list.append(cameras2)
        except:
            print("Could not create second camera module.")

    if '3' in modules:
        try:
            cameras3 = ini_cam_pair(module_num=3)
            all_cams = all_cams + cameras3
            camera_pairs_list.append(cameras3)
        except:
            print("Could not create third camera module.")


    for _ in range(len(camera_pairs_list)):
        frames.append(None)
        prev_frames.append(None)
        movement_present.append(False) 
    return paradigm, modules, frames, prev_frames, movement_present, all_cams, camera_pairs_list

# # # # THIS PART IS FOR INITIALIZING ALL VARIABLES # # # #



paradigm, modules, frames, prev_frames, movement_present, all_cams, camera_pairs_list = ini_var()


def testing():
    
    """
    all_cams = []
    camera_pairs_list = []
    try:
        cameras1 = ini_cam_pair(module_num=1)
        all_cams = all_cams + cameras1
        camera_pairs_list.append(cameras1)
    except:
        print("Could not create first camera module.")
    try:
        cameras2 = ini_cam_pair(module_num=2)
        all_cams = all_cams + cameras2
        camera_pairs_list.append(cameras2)
    except:
        print("Could not create second camera module.")
    try:
        cameras3 = ini_cam_pair(module_num=3)
        all_cams = all_cams + cameras3
        camera_pairs_list.append(cameras3)
    except:
        print("Could not create third camera module.")

    print(f"camera pairs list: {camera_pairs_list}")

    frames = []
    prev_frames = []
    movement_present = []
    
    for i in range(len(camera_pairs_list)):
        frames.append(None)
        prev_frames.append(None)
        movement_present.append(False)
    """

    #frames = [None, None]
    #prev_frames = [None, None]
    #motion = [None, None]
    #movement_present = [False, False]
    recording = True

    # initializes a camera pair based on the module number
    #cameras1 = ini_cam_pair(module_num=1)
    #cameras2 = ini_cam_pair(module_num=2)
    #all_cams = cameras1 + cameras2
    #camera_pairs_list = [cameras1, cameras2]
    
    

    display_frame_counter = 0
    recording = True
    while recording:
        if display_frame_counter % 1 == 0:
        # here, an observer window for each camera should be opened
            recording = observe_while_not_rec(cams=all_cams, cam_ids=cam_serial_numbers[0:len(all_cams)])
        display_frame_counter += 1
            
        for i in range(len(camera_pairs_list)):
            
            # checks the top camera of each camera pair for movement
            movement_present[i] = check_mov_periodic(cams=camera_pairs_list[i])
        
    #for i in range(len(cameras1)):
            #if not cameras1[i].IsGrabbing():
                #camera_grab(cameras1[i])
            #frames[i] = get_frame(cameras1[i])
    #for i in range(len(prev_frames)):
            #if prev_frames[i] is not None:
                #motion[i] = motion_detection(first_frame=prev_frames[i], second_frame=frames[i])
                #movement_present[i] = check_movement(motion_sum=sum_motion(motion[i]), thresh=50000000)
        

        for i in range(len(camera_pairs_list)):
            if movement_present[i]:
                cv2.destroyAllWindows()
                record_while_mov(cams=camera_pairs_list[i], cam_ids=cam_id_pairs[i])
                movement_present[i] = False
                prev_frames[i] = None
                frames[i] = None
                cv2.destroyAllWindows()
        # we later only use one camera of a pair for motion detection
        """
        if movement_present[0]:
            #cv2.destroyAllWindows()
            record_while_mov(cams=cameras1,cam_ids=cam_serial_numbers)
            # for now, when movement was present in both cameras and the recording started, this hinders a second trigger of the 
            # record_while_mov with the same movement trigger
            for i in range(len(movement_present)):
                movement_present[i] = False
            for i in range(len(prev_frames)):
                prev_frames[i] = None
                frames[i] = None
        """

        for i in range(len(prev_frames)):
            prev_frames[i] = frames[i]

    for i in range(len(all_cams)):
        close_camera(all_cams[i])
        

testing()
    
    








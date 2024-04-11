cam_serial_numbers = ["40439818", "40357253", "40405188", "40405187"]

# camera names, that are physically written on the respective camera aswell
# top1 and side1 should be used for module1 and so on
cam_id_name = {"40439818": "top1", "40357253": "side1", "40405188": "top2", "40405187": "side2"}
cam_name_id = {"top1": "40439818", "side1": "40357253", "top2": "40405188", "side2": "40405187"}

from pypylon import pylon
import cv2
import numpy as np
from datetime import datetime
import time
import sys

def get_camera_info():
    """
    EnumerateDevices() creates a list of CDeviceInfo objects. Each of these objects contains camera information, 
    e.g. the serial number that can be extracted via object.GetSeriaLNumber() as a string.
    """
    c_infos = pylon.TlFactory.GetInstance().EnumerateDevices()
    for c_info in c_infos:
        print(f"Camera with serial number {c_info.GetSerialNumber()} was found.")
    return c_infos

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
    frame.Release()
    return img

# Shut down cameras after a recording
def close_camera(cam):
    cam.StopGrabbing()
    cam.Close()

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
    frames = [None, None]
    # video output needs to be defined
    cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0]
    cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1]

    # opens camera windows of both cameras where movement was detected by main()
    open_camera_windows(names=[cam_1_name, cam_2_name])
    try:
        # get the frames
        for i in range(len(cams)):
            if not cams[i].IsGrabbing():
                camera_grab(cams[i])
            frames[i] = get_frame(cams[i])
    except:
        print("Grabbing frames not possible.")
    print(frames)
    try:
        display_frames(names=[cam_1_name, cam_2_name], frames=frames)



    except:
        print("Could not display frames.")

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

paradigm, modules, frames, prev_frames, movement_present, all_cams, camera_pairs_list = ini_var()
print("modules:", all_cams)
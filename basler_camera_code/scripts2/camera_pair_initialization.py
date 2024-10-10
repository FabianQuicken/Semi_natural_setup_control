import time
from camera_control import get_camera_info, camera_ini, camera_settings
from variables import fps, expo_time, cam_name_id

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
                cameras[0] = camera_settings(cam=cameras[0], fps=fps, expo_time=expo_time) # adjusts camera settings
                # give user some feedback
                print(f"Found cam: top{module_num} with SerialNum: {cam_name_id[f'top{module_num}']}!")
                time.sleep(1)

        for i in range(len(camera_infos)):

            # tries to finde the side camera
            if camera_infos[i].GetSerialNumber() == cam_name_id[f"side{module_num}"]:
                cameras[1] = camera_ini(camera_infos[i]) # sets side camera as second element in list
                cameras[1] = camera_settings(cam=cameras[1], fps=fps, expo_time=expo_time) # adjusts camera settings
                
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
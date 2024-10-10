# import packages here
from camera_control import camera_grab, get_frame, close_camera
from motion_detection import motion_detection, sum_motion, check_movement
from observation import observe_while_not_rec
from record_video import record_while_mov, record_video
from camera_pair_initialization import ini_cam_pair
from variables import cam_name_id
import cv2
import time

cam_serial_numbers = ["40439818", "40357253", "40405188", "40405187"]
fps = int(input("At what fps do you want to record?\n"))
#expo_time = int(input("What exposure time [milliseconds] do you want to set your cameras on?\n"))
#expo_time = expo_time*1000 

# camera names, that are physically written on the respective camera aswell
# top1 and side1 should be used for module1 and so on


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



# # # # THIS PART IS FOR STARTING AND CONTROLLING A RECORDING WHEN MOVEMENT IS PRESENT # # # # 
        




# needs to grab two consecutive frames
# should return true if movement present, false if not
# should perform this on the top camera of a module
    
def check_mov_periodic(cams, thresh=500000):
    """
    Checks if movement is present in the top camera of a 
    passed camera module pair.
    Returns true/false if movement is present/not present.
    Based on the return, a decision can be made to record or video.
    Threshold for movement detection can be set.
    """

    first_frame = None
    second_frame = None
    
    
    if not cams[0].IsGrabbing():
        camera_grab(cams[0])

    first_frame = get_frame(cams[0])
    second_frame = get_frame(cams[0])
    
    motion = motion_detection(first_frame=first_frame, second_frame=second_frame)


    movement_present = check_movement(motion_sum=sum_motion(motion), thresh=thresh)

    return movement_present
    """
    except:
        print("Could not check for movement.")
    """

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

        # look out if the experimenter wants to record a video
        key = cv2.waitKey(1)
        if key & 0xFF == ord('r'):
            record_video(cams=camera_pairs_list[i], cam_ids=cam_id_pairs[i])

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
    
    








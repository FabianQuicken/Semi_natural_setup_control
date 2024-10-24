# import packages here
from camera_control import close_camera
from motion_detection import check_mov_periodic
from observation import observe_while_not_rec
from record_video import record_while_mov, record_video
from initialize_variables import ini_var
from variables import cam_name_id
import cv2

cam_serial_numbers = ["40439818", "40357253", "40405188", "40405187"]
fps = int(input("At what fps do you want to record?\n"))


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




paradigm, modules, frames, prev_frames, movement_present, all_cams, camera_pairs_list = ini_var()


def testing():

    #frames = [None, None]
    #prev_frames = [None, None]
    #motion = [None, None]
    #movement_present = [False, False]
    recording = True


    
    

    display_frame_counter = 0
    recording = True
    while recording:
        # here, an observer window for each camera should be opened
        # the check is for skipping display frames, to decrease workload
        if display_frame_counter % 2 == 0:
            recording = observe_while_not_rec(cams=all_cams, cam_ids=cam_serial_numbers[0:len(all_cams)])
        display_frame_counter += 1
            
        for i in range(len(camera_pairs_list)):
            
            # checks the top camera of each camera pair for movement
            movement_present[i] = check_mov_periodic(cams=camera_pairs_list[i])
        

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


        for i in range(len(prev_frames)):
            prev_frames[i] = frames[i]

    for i in range(len(all_cams)):
        close_camera(all_cams[i])
        

testing()
    
    








import cv2
from camera_control import camera_grab, get_frame



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
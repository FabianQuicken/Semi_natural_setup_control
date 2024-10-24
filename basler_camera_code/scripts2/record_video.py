import cv2
from camera_control import camera_grab, get_frame
from observation import open_camera_windows, display_frames
from video_recording import create_video_name, setup_video_writer, convert_frame_format
from motion_detection import motion_detection, sum_motion, check_movement
from variables import cam_id_name, fps



def record_while_mov(cams=list, cam_ids=list, paradigm=str, mov_check_window=300, mov_thresh=500000000):
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
    cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0] + '_' + paradigm
    cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1] + '_' + paradigm
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
        

def record_video(cams=list, cam_ids=list, paradigm=str, fps=fps):
    """
    This function should be used with a camera pair as cams argument. The recording should be 30 seconds in length. 
    Camera IDs are needed to create video names, their order should correspond to the cams order.
    The mov_check_window determines the number of frames that can be "movement free" without stopping
    the recording. The mov_thresh is used as thresh for the check_movement func.
    """
    # First, all parameters get initialized
    frames = [None, None] # grabbed frames will be stored here
    imgs = [None, None] # transformed grabbed frames will be stored here
    prev_frame = None # this will be used to save a frame for the next iteration
    counter=30*fps # counter will be set to 30 seconds


    print(f"This is cam ids: {cam_ids}")
    print(f"This is cam ids 0: {cam_ids[0]}")

    # video output needs to be defined
    cam_1_name = cam_id_name[cam_ids[0]] + '_' + cam_ids[0] + '_' + paradigm
    cam_2_name = cam_id_name[cam_ids[1]] + '_' + cam_ids[1] + '_' + paradigm
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
                display_frames(names=[cam_1_name, cam_2_name, f'Motion cam {cam_1_name}'], frames=frames)
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


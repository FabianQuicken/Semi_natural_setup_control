
import cv2
import numpy as np
from camera_control import camera_grab, get_frame

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
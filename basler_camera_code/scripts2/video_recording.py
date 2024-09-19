from datetime import datetime
import cv2


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